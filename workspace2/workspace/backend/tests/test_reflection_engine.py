from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.contexts import ContextCreateRequest, ContextIdentity, ContextKind, ContextManager
from app.events import EventBus, EventType, ReflectionPayload, ReflectionStarted
from app.execution.models import ExecutionMetrics, ExecutionResult, ExecutionState, FailureReport, StepResult, TimingInfo
from app.knowledge import KnowledgeGraph, KnowledgeGraphAdapter
from app.memory_fabric import MemoryManager
from app.reflection import (
    FailureCategory, ReflectionKind, ReflectionManager, ReflectionOutcome,
    ReflectionProviderContext, ReflectionProviderMetadata, ReflectionProviderRegistry,
    ReflectionRequest, RuleBasedReflectionProvider,
)


def _execution(state: ExecutionState = ExecutionState.COMPLETED, *, failures=(), failed_steps: int = 0, duration: float = 1.0) -> ExecutionResult:
    return ExecutionResult(
        plan_id="plan-1", execution_id="execution-1", state=state,
        steps=(StepResult("step-1", "demo", state),), failures=failures,
        metrics=ExecutionMetrics(1, 1 - failed_steps, failed_steps, 0, 0, int(state is ExecutionState.TIMED_OUT), 0, duration),
        timing=TimingInfo(1.0, 1.0 + duration, duration),
    )


def test_reflection_creation_success_analysis_and_lessons():
    result = ReflectionManager().reflect(ReflectionRequest(kind=ReflectionKind.EXECUTION, execution_result=_execution()))

    assert result.report.outcome is ReflectionOutcome.SUCCESS
    assert result.report.score > 0
    assert result.report.lessons[0].title == "Successful workflow"


def test_failure_partial_timeout_root_cause_and_recommendations():
    failure = FailureReport("step-1", "demo", "ProviderError", "provider unavailable")
    manager = ReflectionManager()
    failed = manager.reflect(ReflectionRequest(kind=ReflectionKind.EXECUTION, execution_result=_execution(ExecutionState.FAILED, failures=(failure,), failed_steps=1)))
    partial = manager.reflect(ReflectionRequest(kind=ReflectionKind.EXECUTION, execution_result=_execution(failures=(failure,), failed_steps=1)))
    timeout = manager.reflect(ReflectionRequest(kind=ReflectionKind.EXECUTION, execution_result=_execution(ExecutionState.TIMED_OUT)))

    assert failed.report.outcome is ReflectionOutcome.FAILURE
    assert failed.report.failure_category is FailureCategory.PROVIDER
    assert "provider unavailable" in failed.report.root_cause
    assert failed.report.recommendations
    assert partial.report.outcome is ReflectionOutcome.PARTIAL_SUCCESS
    assert timeout.report.outcome is ReflectionOutcome.TIMED_OUT


def test_pattern_detection_confidence_scoring_comparison_and_prioritization():
    manager = ReflectionManager()
    event = ReflectionStarted(source="test", payload=ReflectionPayload("r1"))
    request = ReflectionRequest(kind=ReflectionKind.EXECUTION, execution_result=_execution(), event_history=(event, event))
    first = manager.analyze(request)
    second = manager.analyze(ReflectionRequest(kind=ReflectionKind.EXECUTION, execution_result=_execution(ExecutionState.FAILED, failures=(FailureReport(None, None, "ToolError", "bad"),), failed_steps=1)))

    assert any(pattern.occurrence_count == 2 for pattern in first.patterns)
    assert 0.0 <= manager.calculate_confidence(request) <= 1.0
    assert manager.compare(second, first) > 0
    assert manager.prioritize((second, first))[0].reflection_id == first.reflection_id
    assert manager.version(first) == 1


def test_context_memory_and_knowledge_integrations_use_existing_boundaries():
    context = ContextManager().create(ContextCreateRequest(ContextKind.CONVERSATION, ContextIdentity(user_id="u-1", conversation_id="c-1")))
    memory = MemoryManager()
    knowledge = KnowledgeGraphAdapter(KnowledgeGraph())
    result = ReflectionManager(memory_manager=memory, knowledge=knowledge).reflect(
        ReflectionRequest(kind=ReflectionKind.EXECUTION, execution_result=_execution(), contexts=(context,), persist_to_memory=True, publish_to_knowledge=True)
    )

    assert result.memory_record_id is not None
    assert memory.retrieve(result.memory_record_id).owner_id == "u-1"
    assert result.knowledge_entity_id is not None
    assert knowledge.get_entity(result.knowledge_entity_id).label == result.report.summary.title


def test_events_and_dependency_injected_lazy_provider():
    bus = EventBus()
    events = []
    bus.subscribe(None, lambda event: events.append(event.event_type))
    created = []
    registry = ReflectionProviderRegistry(ReflectionProviderContext({"region": "test"}))
    registry.register(ReflectionProviderMetadata("custom", "Custom"), lambda context: created.append(context.require("region")) or RuleBasedReflectionProvider())
    report = ReflectionManager(registry=registry, provider_id="custom", event_bus=bus).reflect(
        ReflectionRequest(kind=ReflectionKind.EXECUTION, execution_result=_execution(ExecutionState.FAILED, failures=(FailureReport(None, None, "ToolError", "bad"),), failed_steps=1))
    ).report

    assert created == ["test"]
    assert EventType.REFLECTION_STARTED in events and EventType.REFLECTION_COMPLETED in events
    assert EventType.LESSON_GENERATED in events and EventType.RECOMMENDATION_GENERATED in events
    assert report.recommendations


def test_reflection_manager_is_safe_for_concurrent_analysis_and_legacy_modules_remain_available():
    manager = ReflectionManager()
    with ThreadPoolExecutor(max_workers=8) as executor:
        reports = list(executor.map(lambda _: manager.analyze(ReflectionRequest(kind=ReflectionKind.EXECUTION, execution_result=_execution())), range(20)))

    from app.memory.memory_store import ShortTermMemory
    legacy = ShortTermMemory()
    legacy.add("user", "compatibility")
    assert len({report.reflection_id for report in reports}) == 20
    assert legacy.recent()[0].content == "compatibility"
