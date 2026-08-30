"""Swappable analysis-engine boundary for Reflection Engine implementations."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .models import (
    FailureCategory, ReflectionLesson, ReflectionMetric, ReflectionOutcome,
    ReflectionPattern, ReflectionRecommendation, ReflectionReport,
    ReflectionRequest, ReflectionSummary, reflection_id,
)


class ReflectionProviderContext:
    def __init__(self, services: dict[str, Any] | None = None) -> None:
        self._services = dict(services or {})

    def require(self, name: str) -> Any:
        try:
            return self._services[name]
        except KeyError as exc:
            raise LookupError(f"Reflection dependency is unavailable: {name}") from exc


@dataclass(frozen=True)
class ReflectionProviderMetadata:
    provider_id: str
    display_name: str
    priority: int = 0
    capabilities: tuple[str, ...] = ("reflection",)


class ReflectionProvider(ABC):
    @abstractmethod
    def initialize(self, context: ReflectionProviderContext) -> None: ...
    @abstractmethod
    def shutdown(self) -> None: ...
    @abstractmethod
    def reflect(self, request: ReflectionRequest) -> ReflectionReport: ...


class RuleBasedReflectionProvider(ReflectionProvider):
    """Deterministic baseline analysis; future model-backed providers plug in here."""

    def initialize(self, context: ReflectionProviderContext) -> None:
        del context

    def shutdown(self) -> None:
        return None

    def reflect(self, request: ReflectionRequest) -> ReflectionReport:
        outcome = self._outcome(request)
        failure_category, root_cause = self._failure(request, outcome)
        metrics = self._metrics(request)
        references = self._references(request)
        patterns = self._patterns(request, outcome, references)
        confidence = self._confidence(request, outcome)
        score = self._score(outcome, confidence)
        recommendations = self._recommendations(outcome, failure_category, metrics, references)
        lessons = self._lessons(outcome, root_cause, confidence, recommendations, references)
        summary = ReflectionSummary(
            title=f"{request.kind.value.replace('_', ' ').title()} reflection",
            description=self._description(outcome, root_cause),
            outcome=outcome,
        )
        return ReflectionReport(
            reflection_id=reflection_id(), kind=request.kind, outcome=outcome, summary=summary,
            confidence=confidence, score=score, metrics=metrics, patterns=patterns,
            lessons=lessons, recommendations=recommendations, failure_category=failure_category,
            root_cause=root_cause, references=references, metadata=request.metadata,
        )

    @staticmethod
    def _outcome(request: ReflectionRequest) -> ReflectionOutcome:
        if request.execution_result is not None:
            from ..execution.models import ExecutionState
            execution = request.execution_result
            if execution.state is ExecutionState.TIMED_OUT:
                return ReflectionOutcome.TIMED_OUT
            if execution.state is ExecutionState.CANCELLED:
                return ReflectionOutcome.CANCELLED
            if execution.state is ExecutionState.FAILED:
                return ReflectionOutcome.FAILURE
            if execution.failures or execution.metrics.failed_steps:
                return ReflectionOutcome.PARTIAL_SUCCESS
            if any(step.retry.attempts > 1 for step in execution.steps):
                return ReflectionOutcome.RETRIED
            if execution.state is ExecutionState.COMPLETED:
                return ReflectionOutcome.SUCCESS
        if request.response is not None:
            from ..responses.models import ResponseStatus
            if request.response.status is ResponseStatus.FAILED:
                return ReflectionOutcome.FAILURE
            if request.response.status is ResponseStatus.PARTIAL:
                return ReflectionOutcome.PARTIAL_SUCCESS
            return ReflectionOutcome.SUCCESS
        if request.search_result is not None:
            if request.search_result.cancelled:
                return ReflectionOutcome.CANCELLED
            return ReflectionOutcome.PARTIAL_SUCCESS if request.search_result.failures else ReflectionOutcome.SUCCESS
        return ReflectionOutcome.SUCCESS if request.memory_entries else ReflectionOutcome.UNKNOWN

    @staticmethod
    def _failure(request: ReflectionRequest, outcome: ReflectionOutcome) -> tuple[FailureCategory | None, str]:
        if outcome is ReflectionOutcome.TIMED_OUT:
            return FailureCategory.TIMEOUT, "Execution exceeded its configured timeout."
        if outcome is ReflectionOutcome.CANCELLED:
            return FailureCategory.CANCELLATION, "Execution or upstream request was cancelled."
        if request.execution_result is not None and request.execution_result.failures:
            failure = request.execution_result.failures[0]
            message = failure.message or failure.error_type
            lowered = f"{failure.error_type} {message}".lower()
            category = FailureCategory.PROVIDER if "provider" in lowered else FailureCategory.DEPENDENCY if "depend" in lowered else FailureCategory.TOOL
            return category, message
        if request.search_result is not None and request.search_result.failures:
            return FailureCategory.PROVIDER, request.search_result.failures[0].status
        return (FailureCategory.UNKNOWN, "Outcome data was incomplete.") if outcome is ReflectionOutcome.UNKNOWN else (None, "")

    @staticmethod
    def _metrics(request: ReflectionRequest) -> tuple[ReflectionMetric, ...]:
        if request.execution_result is None:
            return ()
        metrics = request.execution_result.metrics
        return (
            ReflectionMetric("duration", metrics.duration_seconds, "seconds"),
            ReflectionMetric("completed_steps", float(metrics.completed_steps), "count"),
            ReflectionMetric("failed_steps", float(metrics.failed_steps), "count"),
        )

    @staticmethod
    def _references(request: ReflectionRequest) -> tuple[str, ...]:
        references: list[str] = []
        if request.execution_result is not None:
            references.append(request.execution_result.execution_id)
        if request.response is not None and request.response.response_id:
            references.append(request.response.response_id)
        if request.search_result is not None:
            references.append(request.search_result.search_id)
        references.extend(entry.memory_id for entry in request.memory_entries)
        return tuple(references)

    @staticmethod
    def _patterns(request: ReflectionRequest, outcome: ReflectionOutcome, references: tuple[str, ...]) -> tuple[ReflectionPattern, ...]:
        event_types = Counter(event.event_type.value for event in request.event_history)
        patterns = [
            ReflectionPattern(f"outcome:{outcome.value}", f"{outcome.value.replace('_', ' ').title()} outcome", "Completed work exhibited this outcome.", 1, 0.75, references)
        ]
        for event_type, count in event_types.items():
            if count > 1:
                patterns.append(ReflectionPattern(f"event:{event_type}", "Repeated event", f"{event_type} occurred {count} times.", count, min(0.95, 0.5 + count / 10), references))
        return tuple(patterns)

    @staticmethod
    def _confidence(request: ReflectionRequest, outcome: ReflectionOutcome) -> float:
        evidence = sum(value is not None for value in (request.execution_result, request.response, request.search_result)) + bool(request.memory_entries)
        base = 0.45 + min(evidence, 3) * 0.15
        if outcome is ReflectionOutcome.UNKNOWN:
            base -= 0.2
        return round(max(0.0, min(1.0, base)), 3)

    @staticmethod
    def _score(outcome: ReflectionOutcome, confidence: float) -> float:
        quality = {
            ReflectionOutcome.SUCCESS: 1.0, ReflectionOutcome.RETRIED: 0.8,
            ReflectionOutcome.PARTIAL_SUCCESS: 0.6, ReflectionOutcome.CANCELLED: 0.3,
            ReflectionOutcome.TIMED_OUT: 0.2, ReflectionOutcome.FAILURE: 0.1,
            ReflectionOutcome.INTERRUPTED: 0.25, ReflectionOutcome.UNKNOWN: 0.0,
        }[outcome]
        return round(quality * confidence, 3)

    @staticmethod
    def _recommendations(outcome: ReflectionOutcome, category: FailureCategory | None, metrics: tuple[ReflectionMetric, ...], references: tuple[str, ...]) -> tuple[ReflectionRecommendation, ...]:
        if outcome in (ReflectionOutcome.FAILURE, ReflectionOutcome.PARTIAL_SUCCESS, ReflectionOutcome.TIMED_OUT):
            title = "Review retry and fallback strategy"
            description = "Review failure handling before repeating this workflow."
            modules = ("executor", "planner") if category is not FailureCategory.PROVIDER else ("provider",)
            return (ReflectionRecommendation("retry-fallback", title, description, 0.75, 0.8, modules, references),)
        duration = next((metric.value for metric in metrics if metric.name == "duration"), 0.0)
        if duration > 5.0:
            return (ReflectionRecommendation("performance", "Review execution duration", "Consider reducing slow workflow steps.", 0.65, 0.6, ("executor",), references),)
        return ()

    @staticmethod
    def _lessons(outcome: ReflectionOutcome, root_cause: str, confidence: float, recommendations: tuple[ReflectionRecommendation, ...], references: tuple[str, ...]) -> tuple[ReflectionLesson, ...]:
        if outcome is ReflectionOutcome.SUCCESS:
            return (ReflectionLesson("successful-workflow", "Successful workflow", "The completed workflow produced the expected outcome.", confidence, 0.5, ("workflow",), references),)
        description = root_cause or "The workflow needs more outcome evidence."
        return (ReflectionLesson("improvement-opportunity", "Improvement opportunity", description, confidence, 0.8, ("workflow",), references, recommendations),)

    @staticmethod
    def _description(outcome: ReflectionOutcome, root_cause: str) -> str:
        return f"Outcome: {outcome.value.replace('_', ' ')}." + (f" Root cause: {root_cause}" if root_cause else "")


ReflectionProviderFactory = Callable[[ReflectionProviderContext], ReflectionProvider]


@dataclass
class _Registration:
    metadata: ReflectionProviderMetadata
    factory: ReflectionProviderFactory
    instance: ReflectionProvider | None = None


class ReflectionProviderRegistry:
    def __init__(self, context: ReflectionProviderContext | None = None) -> None:
        self._context = context or ReflectionProviderContext()
        self._registrations: dict[str, _Registration] = {}
        self._lock = threading.RLock()

    def register(self, metadata: ReflectionProviderMetadata, factory: ReflectionProviderFactory) -> None:
        with self._lock:
            if not metadata.provider_id or metadata.provider_id in self._registrations:
                raise ValueError(f"Reflection provider is already registered: {metadata.provider_id}")
            self._registrations[metadata.provider_id] = _Registration(metadata, factory)

    def discover(self) -> tuple[ReflectionProviderMetadata, ...]:
        with self._lock:
            return tuple(sorted((item.metadata for item in self._registrations.values()), key=lambda item: (-item.priority, item.provider_id)))

    def get(self, provider_id: str) -> ReflectionProvider:
        with self._lock:
            try:
                registration = self._registrations[provider_id]
            except KeyError as exc:
                raise KeyError(f"Unknown reflection provider: {provider_id}") from exc
            if registration.instance is None:
                provider = registration.factory(self._context)
                if not isinstance(provider, ReflectionProvider):
                    raise TypeError("Reflection provider factory returned an invalid provider.")
                provider.initialize(self._context)
                registration.instance = provider
            return registration.instance

    def shutdown(self) -> None:
        with self._lock:
            providers = tuple(item.instance for item in self._registrations.values() if item.instance is not None)
            for item in self._registrations.values():
                item.instance = None
        for provider in providers:
            provider.shutdown()
