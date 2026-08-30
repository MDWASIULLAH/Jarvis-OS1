from __future__ import annotations

import asyncio
import time

from app.capabilities.contracts import CapabilityContext, CapabilityMetadata, CapabilityRequest, CapabilityResult, HealthReport, HealthStatus, ValidationResult
from app.capabilities.registry import CapabilityRegistry
from app.events.bus import EventBus
from app.events.model import EventType
from app.execution.executor import CancellationToken, ToolExecutor
from app.execution.models import ExecutionState
from app.planning.models import ExecutionMode, ExecutionPlan, PlanField, PlanStep, RetryPolicy, RollbackMode, RollbackPolicy, StepDependency


class FakeCapability:
    def __init__(self, metadata: CapabilityMetadata, calls: list[str], *, failures: int = 0, delay: float = 0.0, rollback_token: str | None = None):
        self.metadata = metadata
        self.calls = calls
        self.failures = failures
        self.delay = delay
        self.rollback_token = rollback_token
        self.rollback_calls: list[str] = []

    def initialize(self, context: CapabilityContext) -> None:
        return None

    def validate(self, request: CapabilityRequest) -> ValidationResult:
        return ValidationResult(request.operation == "run", "operation must be run")

    def health(self) -> HealthReport:
        return HealthReport(HealthStatus.HEALTHY)

    def execute(self, request: CapabilityRequest) -> CapabilityResult:
        self.calls.append(self.metadata.name)
        if self.delay:
            time.sleep(self.delay)
        if self.failures:
            self.failures -= 1
            return CapabilityResult(False, message="planned failure")
        return CapabilityResult(True, data=request.arguments, rollback_token=self.rollback_token)

    def rollback(self, rollback_token: str) -> CapabilityResult:
        self.rollback_calls.append(rollback_token)
        return CapabilityResult(True, message="rolled back")

    def shutdown(self) -> None:
        return None


def _registry(*specs):
    registry = CapabilityRegistry()
    for name, capability in specs:
        registry.register(capability.metadata, lambda context, capability=capability: capability)
    registry.initialize(CapabilityContext())
    return registry


def _capability(name: str, calls: list[str], **kwargs) -> FakeCapability:
    return FakeCapability(CapabilityMetadata(name, name), calls, **kwargs)


def _step(name: str, **kwargs) -> PlanStep:
    return PlanStep(
        step_id=name,
        name=name,
        description=name,
        capability_id=name,
        metadata=(PlanField("operation", "run"),),
        **kwargs,
    )


def test_sequential_execution_respects_dependencies_and_registry_execution():
    calls: list[str] = []
    registry = _registry(("first", _capability("first", calls)), ("second", _capability("second", calls)))
    first, second = _step("first"), _step("second", dependencies=(StepDependency("first"),))
    plan = ExecutionPlan.new("decision", "sequential", (first, second))

    result = ToolExecutor(registry).execute(plan)

    assert result.state is ExecutionState.COMPLETED
    assert calls == ["first", "second"]
    assert [step.state for step in result.steps] == [ExecutionState.COMPLETED, ExecutionState.COMPLETED]


def test_parallel_execution_runs_independent_steps_concurrently():
    calls: list[str] = []
    registry = _registry(("one", _capability("one", calls, delay=0.15)), ("two", _capability("two", calls, delay=0.15)))
    one = _step("one", execution_mode=ExecutionMode.PARALLEL, can_run_parallel=True)
    two = _step("two", execution_mode=ExecutionMode.PARALLEL, can_run_parallel=True)
    plan = ExecutionPlan.new("decision", "parallel", (one, two))

    result = ToolExecutor(registry).execute(plan)

    assert result.state is ExecutionState.COMPLETED
    assert result.metrics.duration_seconds < 0.27


def test_dependency_failure_skips_dependents_but_allows_independent_branches():
    calls: list[str] = []
    registry = _registry(
        ("failed", _capability("failed", calls, failures=1)),
        ("dependent", _capability("dependent", calls)),
        ("independent", _capability("independent", calls)),
    )
    failed = _step("failed")
    dependent = _step("dependent", dependencies=(StepDependency("failed"),))
    independent = _step("independent")
    plan = ExecutionPlan.new("decision", "graph", (failed, dependent, independent))

    result = ToolExecutor(registry).execute(plan)

    states = {step.step_id: step.state for step in result.steps}
    assert states == {"failed": ExecutionState.FAILED, "dependent": ExecutionState.SKIPPED, "independent": ExecutionState.COMPLETED}
    assert result.metrics.failed_steps == 1


def test_branch_and_merge_execute_only_after_all_dependencies_complete():
    calls: list[str] = []
    registry = _registry(
        ("a", _capability("a", calls)),
        ("b", _capability("b", calls, delay=0.03)),
        ("c", _capability("c", calls, delay=0.03)),
        ("d", _capability("d", calls)),
    )
    plan = ExecutionPlan.new(
        "decision",
        "branch-merge",
        (
            _step("a"),
            _step("b", dependencies=(StepDependency("a"),), execution_mode=ExecutionMode.PARALLEL, can_run_parallel=True),
            _step("c", dependencies=(StepDependency("a"),), execution_mode=ExecutionMode.PARALLEL, can_run_parallel=True),
            _step("d", dependencies=(StepDependency("b"), StepDependency("c"))),
        ),
    )

    result = ToolExecutor(registry).execute(plan)

    assert result.state is ExecutionState.COMPLETED
    assert calls[0] == "a"
    assert calls[-1] == "d"
    assert {step.state for step in result.steps} == {ExecutionState.COMPLETED}


def test_retry_and_automatic_rollback_are_executor_responsibilities():
    calls: list[str] = []
    reversible = _capability("reversible", calls, rollback_token="undo-1")
    failing = _capability("failing", calls, failures=1)
    registry = _registry(("reversible", reversible), ("failing", failing))
    first = _step("reversible", rollback_policy=RollbackPolicy(RollbackMode.AUTOMATIC, "undo"))
    second = _step("failing", dependencies=(StepDependency("reversible"),), retry_policy=RetryPolicy(max_attempts=2))
    plan = ExecutionPlan.new("decision", "rollback", (first, second))

    result = ToolExecutor(registry).execute(plan)

    assert result.steps[1].state is ExecutionState.COMPLETED
    assert reversible.rollback_calls == []

    failing.failures = 2
    result = ToolExecutor(registry).execute(plan)

    assert result.steps[0].state is ExecutionState.ROLLED_BACK
    assert reversible.rollback_calls == ["undo-1"]
    assert result.rollbacks[0].succeeded is True


def test_step_timeout_and_graceful_cancellation_propagate_to_remaining_steps():
    calls: list[str] = []
    registry = _registry(("slow", _capability("slow", calls, delay=0.1)), ("later", _capability("later", calls)))
    timed = ExecutionPlan.new("decision", "timeout", (_step("slow", timeout_seconds=0.01), _step("later", dependencies=(StepDependency("slow"),))))

    timeout_result = ToolExecutor(registry).execute(timed)

    assert timeout_result.steps[0].state is ExecutionState.TIMED_OUT
    assert timeout_result.steps[1].state is ExecutionState.SKIPPED

    token = CancellationToken()
    cancellation_plan = ExecutionPlan.new("decision", "cancel", (_step("slow"), _step("later", dependencies=(StepDependency("slow"),))))

    async def cancel_during_execution():
        task = asyncio.create_task(ToolExecutor(registry).execute_async(cancellation_plan, cancellation=token))
        await asyncio.sleep(0.01)
        token.cancel("user cancelled")
        return await task

    cancelled = asyncio.run(cancel_during_execution())

    assert cancelled.state is ExecutionState.CANCELLED
    assert cancelled.steps[0].state is ExecutionState.COMPLETED
    assert cancelled.steps[1].state is ExecutionState.CANCELLED


def test_whole_plan_timeout_stops_future_layers():
    calls: list[str] = []
    registry = _registry(("first", _capability("first", calls, delay=0.08)), ("second", _capability("second", calls)))
    plan = ExecutionPlan.new("decision", "timeout", (_step("first"), _step("second", dependencies=(StepDependency("first"),))))

    result = ToolExecutor(registry).execute(plan, plan_timeout_seconds=0.02)

    assert result.state is ExecutionState.TIMED_OUT
    assert result.steps[0].state is ExecutionState.TIMED_OUT
    assert result.steps[1].state is ExecutionState.TIMED_OUT
    assert calls == ["first"]


def test_execution_events_metrics_and_plan_compatibility():
    calls: list[str] = []
    registry = _registry(("only", _capability("only", calls)))
    bus = EventBus()
    events: list[EventType] = []
    bus.subscribe(None, lambda event: events.append(event.event_type))
    plan = ExecutionPlan.new("decision", "simple", (_step("only"),))

    result = ToolExecutor(registry, event_bus=bus).execute(plan, correlation_id="execution-1")

    assert result.plan_id == plan.plan_id
    assert result.metrics.total_steps == 1
    assert result.metrics.completed_steps == 1
    assert events == [EventType.EXECUTION_STARTED, EventType.CAPABILITY_STARTED, EventType.CAPABILITY_COMPLETED, EventType.EXECUTION_COMPLETED]


def test_planner_shaped_step_without_an_operation_is_safely_reported_not_inferred():
    calls: list[str] = []
    registry = _registry(("only", _capability("only", calls)))
    planner_step = PlanStep("only", "only", "only", "only")
    plan = ExecutionPlan.new("decision", "planner-compatibility", (planner_step,))

    result = ToolExecutor(registry).execute(plan)

    assert result.state is ExecutionState.FAILED
    assert result.steps[0].failure is not None
    assert result.steps[0].failure.message == "operation must be run"
    assert calls == []
