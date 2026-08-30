"""Evolution proposal orchestration; deliberately cannot apply proposals."""

from __future__ import annotations

from ..events.bus import EventBus
from ..events.model import (
    EvolutionCompleted, EvolutionFailed, EvolutionPayload, EvolutionStarted,
    OptimizationSuggested, ProposalGenerated,
)
from ..knowledge.graph_models import EntityType
from ..knowledge.interface import KnowledgeAttribute, KnowledgeEntityDraft, KnowledgeInterface
from ..memory_fabric import MemoryAttribute, MemoryDraft, MemoryManager, MemoryType
from .models import (
    EvolutionProposal, EvolutionReport, EvolutionRequest, EvolutionResult,
    ImpactAssessment, RiskAssessment,
)
from .provider import EvolutionProvider, EvolutionProviderMetadata, EvolutionProviderRegistry, RuleBasedEvolutionProvider


class EvolutionManager:
    DEFAULT_PROVIDER_ID = "rule_based"

    def __init__(self, *, registry: EvolutionProviderRegistry | None = None, provider_id: str = DEFAULT_PROVIDER_ID, event_bus: EventBus | None = None, memory_manager: MemoryManager | None = None, knowledge: KnowledgeInterface | None = None) -> None:
        self._registry = registry or EvolutionProviderRegistry()
        self._provider_id = provider_id
        self._event_bus = event_bus
        self._memory_manager = memory_manager
        self._knowledge = knowledge
        if not self._registry.discover():
            self._registry.register(EvolutionProviderMetadata(provider_id, "Rule-based Evolution"), lambda _: RuleBasedEvolutionProvider())

    @property
    def registry(self) -> EvolutionProviderRegistry:
        return self._registry

    def evolve(self, request: EvolutionRequest) -> EvolutionResult:
        correlation_id = request.contexts[0].identity.correlation_id if request.contexts else "evolution"
        self._publish(EvolutionStarted, "pending", correlation_id)
        try:
            report = self._provider.evolve(request)
            memory_id = self._persist(report, request)
            knowledge_id = self._knowledge_record(report, request)
        except Exception:
            self._publish(EvolutionFailed, "failed", correlation_id, status="failed")
            raise
        self._publish(EvolutionCompleted, report.evolution_id, correlation_id, status="completed")
        for proposal in report.proposals:
            self._publish(ProposalGenerated, report.evolution_id, correlation_id, proposal.proposal_id)
            self._publish(OptimizationSuggested, report.evolution_id, correlation_id, proposal.proposal_id)
        return EvolutionResult(report, memory_id, knowledge_id)

    def analyze(self, request: EvolutionRequest) -> EvolutionReport: return self.evolve(request).report
    def optimize(self, request: EvolutionRequest) -> tuple[EvolutionProposal, ...]: return self.analyze(request).proposals
    def generate_proposals(self, request: EvolutionRequest) -> tuple[EvolutionProposal, ...]: return self.analyze(request).proposals
    def prioritize(self, proposals: tuple[EvolutionProposal, ...]) -> tuple[EvolutionProposal, ...]: return tuple(sorted(proposals, key=lambda item: (-item.priority, -item.confidence, item.proposal_id)))
    def compare_versions(self, first: EvolutionReport, second: EvolutionReport) -> float: return round(sum(item.priority for item in second.proposals) - sum(item.priority for item in first.proposals), 3)
    def score(self, proposal: EvolutionProposal) -> float: return proposal.priority
    def estimate_impact(self, proposal: EvolutionProposal) -> ImpactAssessment: return proposal.impact
    def estimate_risk(self, proposal: EvolutionProposal) -> RiskAssessment: return proposal.risk
    def summarize(self, report: EvolutionReport) -> str: return report.summary
    def version(self, report: EvolutionReport) -> int: return report.version
    def shutdown(self) -> None: self._registry.shutdown()

    @property
    def _provider(self) -> EvolutionProvider: return self._registry.get(self._provider_id)

    def _persist(self, report: EvolutionReport, request: EvolutionRequest) -> str | None:
        if not request.persist_to_memory or self._memory_manager is None:
            return None
        entry = self._memory_manager.store(MemoryDraft(memory_type=MemoryType.SEMANTIC, title="Evolution proposals", content=report.summary, summary=report.summary, tags=("evolution",), metadata=(MemoryAttribute("evolution_id", report.evolution_id),)), context=request.contexts[0] if request.contexts else None)
        return entry.memory_id

    def _knowledge_record(self, report: EvolutionReport, request: EvolutionRequest) -> str | None:
        if not request.publish_to_knowledge or self._knowledge is None:
            return None
        entity = self._knowledge.create_entity(KnowledgeEntityDraft(EntityType.GENERIC, "Evolution proposals", attributes=(KnowledgeAttribute("evolution_id", report.evolution_id),), tags=("evolution",), importance=max((proposal.priority for proposal in report.proposals), default=0.5)))
        return entity.entity_id

    def _publish(self, event_type, evolution_id: str, correlation_id: str, proposal_id: str = "", status: str = "") -> None:
        if self._event_bus is not None:
            self._event_bus.publish(event_type(source="evolution_engine", payload=EvolutionPayload(evolution_id, proposal_id, status), correlation_id=correlation_id))
