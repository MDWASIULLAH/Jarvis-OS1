from __future__ import annotations

import pytest

from app.brain.decision_engine import Decision, DecisionEngine, RetryPolicy as DecisionRetryPolicy
from app.brain.intent_router import RoutingResult
from app.capabilities.builtins import build_builtin_registry
from app.capabilities.contracts import CapabilityContext, CapabilityMetadata
from app.capabilities.registry import CapabilityRegistry
from app.events.bus import EventBus
from app.events.model import EventType
from app.planning.models import ExecutionPlan, ExecutionMode, PlanStep, StepDependency
from app.planning.planner import PlanRejectedError, Planner
from app.planning.strategies import FutureAgentStrategy, ParallelStrategy, SequentialStrategy, SimplePlanStrategy


def _decision(*capabilities: str, **kwargs) -> Decision:
    routing = RoutingResult("info.factual", 0.9, entities={"query": "JARVIS"})
    return Decision(
        routing=routing,
        intent=routing.intent,
        confidence=routing.confidence,
        selected_capabilities=list(capabilities),
        **kwargs,
    )


def test_single_step_plan_uses_simple_strategy_and_metadata_only_registry_access():
    planner = Planner(build_builtin_registry())

    plan = planner.create_plan(_decision("knowledge_apis"))

    assert plan.strategy == "simple"
    assert len(plan.steps) == 1
    assert plan.steps[0].capability_id == "knowledge_apis"
    assert plan.steps[0].inputs[0].name == "query"


def test_multi_step_plan_is_linear_with_resolved_dependencies():
    planner = Planner(build_builtin_registry())

    plan = planner.create_plan(_decision("knowledge_apis", "web_research", "fun_space"))

    assert plan.strategy == "sequential"
    assert plan.topological_layers() == ((plan.steps[0].step_id,), (plan.steps[1].step_id,), (plan.steps[2].step_id,))
    assert plan.steps[1].dependencies[0].prerequisite_step_id == plan.steps[0].step_id


def test_parallel_plan_has_one_layer_and_parallel_step_metadata():
    planner = Planner(build_builtin_registry())

    plan = planner.create_plan(_decision("knowledge_apis", "web_research", requires_parallel_execution=True))

    assert plan.strategy == "parallel"
    assert len(plan.topological_layers()) == 1
    assert all(step.execution_mode is ExecutionMode.PARALLEL and step.can_run_parallel for step in plan.steps)


def test_dag_model_supports_branching_and_merge():
    a = PlanStep("a", "A", "root", "knowledge_apis")
    b = PlanStep("b", "B", "left", "web_research", dependencies=(StepDependency("a"),))
    c = PlanStep("c", "C", "right", "fun_space", dependencies=(StepDependency("a"),))
    d = PlanStep("d", "D", "merge", "knowledge_apis", dependencies=(StepDependency("b"), StepDependency("c")))
    plan = ExecutionPlan.new("decision", "graph", (a, b, c, d))

    assert plan.validate() == ()
    assert plan.topological_layers() == (("a",), ("b", "c"), ("d",))


def test_retry_rollback_confirmation_and_memory_checkpoints_are_generated():
    planner = Planner(build_builtin_registry())
    decision = _decision(
        "image_pipeline",
        requires_confirmation=True,
        requires_memory=True,
        retry_policy=DecisionRetryPolicy(max_attempts=3, backoff_seconds=1.0),
    )

    plan = planner.create_plan(decision)

    assert plan.steps[0].retry_policy.max_attempts == 3
    assert plan.steps[0].rollback_policy.mode.value == "manual"
    assert {checkpoint.checkpoint_type.value for checkpoint in plan.checkpoints} == {"confirmation", "memory"}


def test_strategy_selection_supports_all_declared_strategies():
    planner = Planner(build_builtin_registry())

    assert isinstance(planner.select_strategy(_decision("knowledge_apis")), SimplePlanStrategy)
    assert isinstance(planner.select_strategy(_decision("knowledge_apis", "web_research")), SequentialStrategy)
    assert isinstance(planner.select_strategy(_decision("knowledge_apis", requires_parallel_execution=True)), ParallelStrategy)
    assert isinstance(planner.select_strategy(_decision("knowledge_apis", requires_planner=True)), FutureAgentStrategy)


def test_planning_events_are_published_without_execution_events():
    bus = EventBus()
    observed: list[EventType] = []
    bus.subscribe(None, lambda event: observed.append(event.event_type))
    planner = Planner(build_builtin_registry(), event_bus=bus)

    planner.create_plan(_decision("knowledge_apis"), correlation_id="plan-123")

    assert observed == [EventType.PLAN_CREATED, EventType.PLAN_VALIDATED]
    assert all("capability" not in event_type.value for event_type in observed)


def test_invalid_plan_is_rejected_and_publishes_rejection():
    class InvalidStrategy(SimplePlanStrategy):
        def build(self, decision, registry):
            step = PlanStep("same", "invalid", "invalid", "knowledge_apis", dependencies=(StepDependency("missing"),))
            return ExecutionPlan.new(decision.decision_id, self.name, (step,))

    bus = EventBus()
    observed: list[EventType] = []
    bus.subscribe(None, lambda event: observed.append(event.event_type))
    planner = Planner(build_builtin_registry(), event_bus=bus)
    planner._simple = InvalidStrategy()

    with pytest.raises(PlanRejectedError, match="unknown step"):
        planner.create_plan(_decision("knowledge_apis"))

    assert observed == [EventType.PLAN_REJECTED]


def test_planner_accepts_decision_engine_output_without_loading_capabilities():
    registry = CapabilityRegistry()
    metadata = CapabilityMetadata("metadata_only", "Planning metadata", supported_intents=("task.code",))

    def factory(context: CapabilityContext):
        raise AssertionError("Planner must never initialize a capability")

    registry.register(metadata, factory)
    registry.initialize(CapabilityContext())
    decision = DecisionEngine(registry).decide(RoutingResult("task.code", 0.99))

    plan = Planner(registry).create_plan(decision)

    assert plan.steps[0].capability_id == "metadata_only"
