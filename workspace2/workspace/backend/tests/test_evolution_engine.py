from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.contexts import ContextCreateRequest, ContextIdentity, ContextKind, ContextManager
from app.events import EventBus, EventType
from app.execution.models import ExecutionMetrics, ExecutionResult, ExecutionState, FailureReport
from app.evolution import (
    EvolutionManager, EvolutionProviderContext, EvolutionProviderMetadata,
    EvolutionProviderRegistry, EvolutionRequest, ImprovementMetric, OptimizationTarget,
    RuleBasedEvolutionProvider,
)
from app.knowledge import KnowledgeGraph, KnowledgeGraphAdapter
from app.memory_fabric import MemoryManager
from app.reflection import ReflectionKind, ReflectionManager, ReflectionRequest


def _reflection(failed: bool = False):
    result = ExecutionResult(
        plan_id="p", execution_id="e", state=ExecutionState.FAILED if failed else ExecutionState.COMPLETED,
        failures=(FailureReport("s", "tool", "ToolError", "tool failed"),) if failed else (),
        metrics=ExecutionMetrics(1, 0 if failed else 1, int(failed), 0, 0, 0, 0, 1.0),
    )
    return ReflectionManager().analyze(ReflectionRequest(kind=ReflectionKind.EXECUTION, execution_result=result))


def test_evolution_analysis_generates_failure_and_success_proposals():
    manager = EvolutionManager()
    failure_report = manager.analyze(EvolutionRequest(reflection_reports=(_reflection(True),)))
    success_report = manager.analyze(EvolutionRequest(reflection_reports=(_reflection(),)))

    assert failure_report.proposals[0].target is OptimizationTarget.RETRY_STRATEGY
    assert success_report.proposals[0].target is OptimizationTarget.WORKFLOW_EFFICIENCY
    assert failure_report.opportunities and failure_report.recommendations


def test_metrics_create_latency_opportunities_and_impact_risk_priority_contracts():
    manager = EvolutionManager()
    report = manager.analyze(EvolutionRequest(reflection_reports=(), execution_metrics=(ImprovementMetric("duration", 9.0, "seconds"),)))
    proposal = report.proposals[0]

    assert proposal.target is OptimizationTarget.LATENCY
    assert manager.score(proposal) == proposal.priority
    assert manager.estimate_impact(proposal) == proposal.impact
    assert manager.estimate_risk(proposal) == proposal.risk
    assert manager.prioritize(report.proposals)[0] == proposal
    assert manager.version(report) == 1 and manager.summarize(report)


def test_context_reflection_memory_and_knowledge_boundaries_are_integrated():
    context = ContextManager().create(ContextCreateRequest(ContextKind.CONVERSATION, ContextIdentity(user_id="u1")))
    memory = MemoryManager()
    knowledge = KnowledgeGraphAdapter(KnowledgeGraph())
    result = EvolutionManager(memory_manager=memory, knowledge=knowledge).evolve(
        EvolutionRequest(reflection_reports=(_reflection(True),), contexts=(context,), persist_to_memory=True, publish_to_knowledge=True)
    )

    assert result.memory_record_id is not None and memory.retrieve(result.memory_record_id).owner_id == "u1"
    assert result.knowledge_entity_id is not None
    assert knowledge.get_entity(result.knowledge_entity_id).label == "Evolution proposals"


def test_events_and_lazy_dependency_injection():
    bus = EventBus()
    events = []
    bus.subscribe(None, lambda event: events.append(event.event_type))
    created = []
    registry = EvolutionProviderRegistry(EvolutionProviderContext({"region": "test"}))
    registry.register(EvolutionProviderMetadata("custom", "Custom"), lambda context: created.append(context.require("region")) or RuleBasedEvolutionProvider())
    report = EvolutionManager(registry=registry, provider_id="custom", event_bus=bus).analyze(EvolutionRequest(reflection_reports=(_reflection(True),)))

    assert created == ["test"]
    assert EventType.EVOLUTION_STARTED in events and EventType.EVOLUTION_COMPLETED in events
    assert EventType.PROPOSAL_GENERATED in events and EventType.OPTIMIZATION_SUGGESTED in events
    assert report.proposals


def test_comparison_concurrency_and_completed_modules_compatibility():
    manager = EvolutionManager()
    failure = manager.analyze(EvolutionRequest(reflection_reports=(_reflection(True),)))
    success = manager.analyze(EvolutionRequest(reflection_reports=(_reflection(),)))
    with ThreadPoolExecutor(max_workers=8) as executor:
        reports = list(executor.map(lambda _: manager.analyze(EvolutionRequest(reflection_reports=(_reflection(),))), range(20)))

    from app.memory.memory_store import ShortTermMemory
    legacy = ShortTermMemory()
    legacy.add("user", "still works")
    assert isinstance(manager.compare_versions(failure, success), float)
    assert len({report.evolution_id for report in reports}) == 20
    assert legacy.recent()[0].content == "still works"
