"""Reflection orchestration with explicit, non-mutating integration boundaries."""

from __future__ import annotations

from ..events.bus import EventBus
from ..events.model import (
    LessonGenerated, RecommendationGenerated, ReflectionCompleted, ReflectionFailed,
    ReflectionPayload, ReflectionStarted,
)
from ..knowledge.graph_models import EntityType
from ..knowledge.interface import KnowledgeAttribute, KnowledgeEntityDraft, KnowledgeInterface
from ..memory_fabric import MemoryAttribute, MemoryDraft, MemoryManager, MemoryType
from .models import (
    ReflectionLesson, ReflectionOutcome, ReflectionPattern, ReflectionRecommendation,
    ReflectionReport, ReflectionRequest, ReflectionResult, ReflectionSummary,
)
from .provider import (
    ReflectionProvider, ReflectionProviderMetadata, ReflectionProviderRegistry,
    RuleBasedReflectionProvider,
)


class ReflectionManager:
    """Analysis-only facade; recommendations are data and are never applied here."""

    DEFAULT_PROVIDER_ID = "rule_based"

    def __init__(
        self,
        *,
        registry: ReflectionProviderRegistry | None = None,
        provider_id: str = DEFAULT_PROVIDER_ID,
        event_bus: EventBus | None = None,
        memory_manager: MemoryManager | None = None,
        knowledge: KnowledgeInterface | None = None,
    ) -> None:
        self._registry = registry or ReflectionProviderRegistry()
        self._provider_id = provider_id
        self._event_bus = event_bus
        self._memory_manager = memory_manager
        self._knowledge = knowledge
        if not self._registry.discover():
            self._registry.register(ReflectionProviderMetadata(provider_id, "Rule-based Reflection"), lambda _: RuleBasedReflectionProvider())

    @property
    def registry(self) -> ReflectionProviderRegistry:
        return self._registry

    def reflect(self, request: ReflectionRequest) -> ReflectionResult:
        correlation_id = self._correlation_id(request)
        provisional_id = request.execution_result.execution_id if request.execution_result is not None else "pending"
        self._publish(ReflectionStarted, provisional_id, "", correlation_id)
        try:
            report = self._provider.reflect(request)
            memory_record_id = self._persist_to_memory(report, request)
            knowledge_entity_id = self._publish_to_knowledge(report, request)
        except Exception:
            self._publish(ReflectionFailed, provisional_id, "failed", correlation_id)
            raise
        self._publish(ReflectionCompleted, report.reflection_id, report.outcome.value, correlation_id)
        for lesson in report.lessons:
            self._publish(LessonGenerated, report.reflection_id, report.outcome.value, correlation_id, lesson.lesson_id)
        for recommendation in report.recommendations:
            self._publish(RecommendationGenerated, report.reflection_id, report.outcome.value, correlation_id, recommendation.recommendation_id)
        return ReflectionResult(report, memory_record_id, knowledge_entity_id)

    def analyze(self, request: ReflectionRequest) -> ReflectionReport:
        return self.reflect(request).report

    def evaluate(self, request: ReflectionRequest) -> ReflectionOutcome:
        return self.analyze(request).outcome

    def summarize(self, request: ReflectionRequest) -> ReflectionSummary:
        return self.analyze(request).summary

    def detect_patterns(self, request: ReflectionRequest) -> tuple[ReflectionPattern, ...]:
        return self.analyze(request).patterns

    def root_cause(self, request: ReflectionRequest) -> str:
        return self.analyze(request).root_cause

    def generate_lessons(self, request: ReflectionRequest) -> tuple[ReflectionLesson, ...]:
        return self.analyze(request).lessons

    def generate_recommendations(self, request: ReflectionRequest) -> tuple[ReflectionRecommendation, ...]:
        return self.analyze(request).recommendations

    def calculate_confidence(self, request: ReflectionRequest) -> float:
        return self.analyze(request).confidence

    def compare(self, first: ReflectionReport, second: ReflectionReport) -> float:
        """Positive values mean the second reflection scored better."""
        return round(second.score - first.score, 3)

    def score(self, report: ReflectionReport) -> float:
        return report.score

    def prioritize(self, reports: tuple[ReflectionReport, ...]) -> tuple[ReflectionReport, ...]:
        return tuple(sorted(reports, key=lambda report: (-report.score, -report.confidence, report.reflection_id)))

    def version(self, report: ReflectionReport) -> int:
        return report.version

    def shutdown(self) -> None:
        self._registry.shutdown()

    @property
    def _provider(self) -> ReflectionProvider:
        return self._registry.get(self._provider_id)

    def _persist_to_memory(self, report: ReflectionReport, request: ReflectionRequest) -> str | None:
        if not request.persist_to_memory or self._memory_manager is None:
            return None
        context = request.contexts[0] if request.contexts else None
        entry = self._memory_manager.store(
            MemoryDraft(
                memory_type=MemoryType.EPISODIC,
                title=report.summary.title,
                content=report.summary.description,
                summary=report.summary.description,
                tags=("reflection", report.outcome.value),
                metadata=(MemoryAttribute("reflection_id", report.reflection_id),),
                confidence=report.confidence,
                importance=max((lesson.importance for lesson in report.lessons), default=0.5),
                references=(),
            ),
            context=context,
        )
        return entry.memory_id

    def _publish_to_knowledge(self, report: ReflectionReport, request: ReflectionRequest) -> str | None:
        if not request.publish_to_knowledge or self._knowledge is None:
            return None
        entity = self._knowledge.create_entity(KnowledgeEntityDraft(
            entity_type=EntityType.GENERIC,
            label=report.summary.title,
            attributes=(KnowledgeAttribute("reflection_id", report.reflection_id), KnowledgeAttribute("outcome", report.outcome.value)),
            confidence=report.confidence,
            importance=max((lesson.importance for lesson in report.lessons), default=0.5),
            tags=("reflection", report.kind.value),
        ))
        return entity.entity_id

    @staticmethod
    def _correlation_id(request: ReflectionRequest) -> str:
        if request.contexts:
            return request.contexts[0].identity.correlation_id
        if request.execution_result is not None:
            return request.execution_result.execution_id
        return "reflection"

    def _publish(self, event_type, reflection_id: str, outcome: str, correlation_id: str, item_id: str = "") -> None:
        if self._event_bus is not None:
            self._event_bus.publish(event_type(
                source="reflection_engine",
                payload=ReflectionPayload(reflection_id, outcome, item_id),
                correlation_id=correlation_id,
            ))
