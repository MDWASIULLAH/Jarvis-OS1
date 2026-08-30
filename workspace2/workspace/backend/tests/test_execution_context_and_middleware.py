from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError

import pytest

from app.capabilities.contracts import CapabilityContext, CapabilityMetadata, CapabilityRequest, CapabilityResult, HealthReport, HealthStatus, ValidationResult
from app.capabilities.registry import CapabilityRegistry
from app.execution.context import (
    CapabilityCompatibilityAdapter,
    CapabilityInvocationStyle,
    ContextAttribute,
    ExecutionContext,
)
from app.execution.executor import ToolExecutor
from app.execution.middleware import MiddlewarePipeline
from app.planning.models import ExecutionPlan, PlanField, PlanStep


class LegacyCapability:
    def __init__(self, name: str) -> None:
        self.metadata = CapabilityMetadata(name, name)
        self.requests: list[CapabilityRequest] = []

    def initialize(self, context: CapabilityContext) -> None:
        return None

    def validate(self, request: CapabilityRequest) -> ValidationResult:
        return ValidationResult(request.operation == "run", "operation must be run")

    def health(self) -> HealthReport:
        return HealthReport(HealthStatus.HEALTHY)

    def execute(self, request: CapabilityRequest) -> CapabilityResult:
        self.requests.append(request)
        return CapabilityResult(True, data="legacy")

    def rollback(self, rollback_token: str) -> CapabilityResult:
        return CapabilityResult(True)

    def shutdown(self) -> None:
        return None


class ContextCapability(LegacyCapability):
    execution_interface = CapabilityInvocationStyle.CONTEXT

    def __init__(self, name: str, events: list[str]) -> None:
        super().__init__(name)
        self.contexts: list[ExecutionContext] = []
        self.events = events

    def execute(self, context: ExecutionContext) -> CapabilityResult:
        self.contexts.append(context)
        self.events.append("capability")
        context.shared_state.set("capability", context.current_step.step_id if context.current_step else "")
        context.metrics.increment("capability.invocations")
        return CapabilityResult(True, data="context")


class RecordingMiddleware:
    def __init__(self, name: str, events: list[str]) -> None:
        self.name = name
        self.events = events

    def before_execute(self, context: ExecutionContext) -> ExecutionContext:
        self.events.append(f"before:{self.name}")
        return context

    def after_execute(self, context: ExecutionContext, result: CapabilityResult) -> CapabilityResult:
        self.events.append(f"after:{self.name}")
        return CapabilityResult(result.ok, data=f"{result.data}-{self.name}", message=result.message, rollback_token=result.rollback_token)


class FailingMiddleware:
    def before_execute(self, context: ExecutionContext) -> ExecutionContext:
        raise RuntimeError("middleware failed")

    def after_execute(self, context: ExecutionContext, result: CapabilityResult) -> CapabilityResult:
        return result


def _plan(name: str = "capability") -> ExecutionPlan:
    return ExecutionPlan.new(
        "decision",
        "context",
        (PlanStep(name, name, name, name, metadata=(PlanField("operation", "run"),)),),
    )


def _registry(capability: LegacyCapability) -> CapabilityRegistry:
    registry = CapabilityRegistry()
    registry.register(capability.metadata, lambda context: capability)
    registry.initialize(CapabilityContext())
    return registry


def test_execution_context_is_immutable_except_for_explicit_shared_state_and_metrics():
    plan = _plan()
    context = ExecutionContext.create(
        plan,
        execution_id="execution-1",
        correlation_id="correlation-1",
        conversation_id="conversation-1",
        session_id="session-1",
        user_id="user-1",
        metadata=(ContextAttribute("request_origin", "test"),),
    )

    assert context.execution_id == "execution-1"
    assert context.current_step is None
    with pytest.raises(FrozenInstanceError):
        context.user_id = "different"  # type: ignore[misc]

    context.shared_state.set("answer", 42)
    context.metrics.increment("steps.started")
    assert context.shared_state.snapshot() == {"answer": 42}
    assert context.metrics.snapshot() == (ContextAttribute("steps.started", "1"),)


def test_context_capability_receives_step_scoped_execution_context():
    events: list[str] = []
    capability = ContextCapability("capability", events)
    context = ExecutionContext.create(_plan(), conversation_id="conversation", session_id="session", user_id="user")

    result = ToolExecutor(_registry(capability)).execute(context.execution_plan, execution_context=context)

    received = capability.contexts[0]
    assert result.state.value == "completed"
    assert received.execution_id == context.execution_id
    assert received.current_step is not None and received.current_step.step_id == "capability"
    assert (received.conversation_id, received.session_id, received.user_id) == ("conversation", "session", "user")
    assert context.shared_state.get("capability") == "capability"


def test_registered_middleware_wraps_capability_in_entry_and_reverse_exit_order():
    events: list[str] = []
    capability = ContextCapability("capability", events)
    executor = ToolExecutor(_registry(capability), middleware=(RecordingMiddleware("first", events),))
    executor.register_middleware(RecordingMiddleware("second", events))

    result = executor.execute(_plan())

    assert events == ["before:first", "before:second", "capability", "after:second", "after:first"]
    assert result.steps[0].output is not None and result.steps[0].output.data == "context-second-first"


def test_middleware_exception_propagates_through_pipeline_and_executor_reports_failure():
    context = ExecutionContext.create(_plan())
    pipeline = MiddlewarePipeline((FailingMiddleware(),))

    async def invoke(value: ExecutionContext) -> CapabilityResult:
        return CapabilityResult(True)

    with pytest.raises(RuntimeError, match="middleware failed"):
        asyncio.run(pipeline.execute(context, invoke))

    capability = ContextCapability("capability", [])
    result = ToolExecutor(_registry(capability), middleware=(FailingMiddleware(),)).execute(_plan())
    assert result.steps[0].failure is not None
    assert result.steps[0].failure.message == "middleware failed"
    assert capability.contexts == []


def test_legacy_request_capability_remains_supported_by_compatibility_adapter():
    capability = LegacyCapability("capability")
    plan = _plan()
    context = ExecutionContext.create(plan, correlation_id="correlation-1").for_step(plan.steps[0])

    result = CapabilityCompatibilityAdapter().execute(capability, context)

    assert result.ok is True
    assert capability.requests[0].operation == "run"
    assert capability.requests[0].correlation_id == "correlation-1"
