"""Immutable, provider-neutral contracts for completed-work reflection."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..contexts.contracts import Context
    from ..events.model import DomainEvent
    from ..execution.models import ExecutionResult
    from ..memory_fabric.models import MemoryEntry
    from ..planning.models import ExecutionPlan
    from ..responses.models import Response
    from ..search.models import SearchResponse


class ReflectionOutcome(str, Enum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    RETRIED = "retried"
    INTERRUPTED = "interrupted"
    UNKNOWN = "unknown"


class FailureCategory(str, Enum):
    DEPENDENCY = "dependency"
    TOOL = "tool"
    PROVIDER = "provider"
    CONTEXT = "context"
    EXTERNAL = "external"
    TIMEOUT = "timeout"
    CANCELLATION = "cancellation"
    UNKNOWN = "unknown"


class ReflectionKind(str, Enum):
    EXECUTION = "execution"
    RESPONSE = "response"
    SEARCH = "search"
    MEMORY = "memory"
    PLANNING = "planning"
    GENERIC = "generic"


@dataclass(frozen=True)
class ReflectionAttribute:
    key: str
    value: str


@dataclass(frozen=True)
class ReflectionMetric:
    name: str
    value: float
    unit: str = ""


@dataclass(frozen=True)
class ReflectionPattern:
    pattern_id: str
    title: str
    description: str
    occurrence_count: int = 1
    confidence: float = 0.5
    references: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReflectionRecommendation:
    recommendation_id: str
    title: str
    description: str
    confidence: float
    importance: float
    affected_modules: tuple[str, ...] = ()
    references: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReflectionLesson:
    lesson_id: str
    title: str
    description: str
    confidence: float
    importance: float
    affected_modules: tuple[str, ...] = ()
    references: tuple[str, ...] = ()
    recommendations: tuple[ReflectionRecommendation, ...] = ()


@dataclass(frozen=True)
class ReflectionSummary:
    title: str
    description: str
    outcome: ReflectionOutcome


@dataclass(frozen=True)
class ReflectionReport:
    reflection_id: str
    kind: ReflectionKind
    outcome: ReflectionOutcome
    summary: ReflectionSummary
    confidence: float
    score: float
    metrics: tuple[ReflectionMetric, ...] = ()
    patterns: tuple[ReflectionPattern, ...] = ()
    lessons: tuple[ReflectionLesson, ...] = ()
    recommendations: tuple[ReflectionRecommendation, ...] = ()
    failure_category: FailureCategory | None = None
    root_cause: str = ""
    references: tuple[str, ...] = ()
    metadata: tuple[ReflectionAttribute, ...] = ()
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# Public concise name used by integrations that model one reflection as its report.
Reflection = ReflectionReport


@dataclass(frozen=True, kw_only=True)
class ReflectionRequest:
    kind: ReflectionKind = ReflectionKind.GENERIC
    execution_result: "ExecutionResult | None" = None
    response: "Response | None" = None
    search_result: "SearchResponse | None" = None
    memory_entries: tuple["MemoryEntry", ...] = ()
    plan: "ExecutionPlan | None" = None
    contexts: tuple["Context", ...] = ()
    event_history: tuple["DomainEvent[Any]", ...] = ()
    metadata: tuple[ReflectionAttribute, ...] = ()
    persist_to_memory: bool = False
    publish_to_knowledge: bool = False


@dataclass(frozen=True)
class ReflectionResult:
    report: ReflectionReport
    memory_record_id: str | None = None
    knowledge_entity_id: str | None = None


def reflection_id() -> str:
    return str(uuid.uuid4())
