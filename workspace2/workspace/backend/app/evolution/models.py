"""Provider-neutral, immutable contracts for architecture improvement proposals."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..contexts.contracts import Context
    from ..events.model import DomainEvent
    from ..reflection.models import ReflectionReport


class OptimizationTarget(str, Enum):
    PLANNING = "planning"
    SEARCH = "search"
    MEMORY = "memory"
    CAPABILITY_SELECTION = "capability_selection"
    CONFIDENCE = "confidence"
    RETRY_STRATEGY = "retry_strategy"
    CONTEXT_USAGE = "context_usage"
    WORKFLOW_EFFICIENCY = "workflow_efficiency"
    RESOURCE_USAGE = "resource_usage"
    PARALLEL_EXECUTION = "parallel_execution"
    LATENCY = "latency"
    RELIABILITY = "reliability"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class ImprovementMetric:
    name: str
    value: float
    unit: str = ""


@dataclass(frozen=True)
class ImpactAssessment:
    execution_improvement: float = 0.0
    memory_improvement: float = 0.0
    planner_improvement: float = 0.0
    search_improvement: float = 0.0
    response_improvement: float = 0.0
    resource_reduction: float = 0.0
    scalability_improvement: float = 0.0


@dataclass(frozen=True)
class RiskAssessment:
    architectural: RiskLevel = RiskLevel.LOW
    compatibility: RiskLevel = RiskLevel.LOW
    operational: RiskLevel = RiskLevel.LOW
    performance: RiskLevel = RiskLevel.LOW
    implementation_complexity: RiskLevel = RiskLevel.LOW


@dataclass(frozen=True)
class ImprovementOpportunity:
    opportunity_id: str
    target: OptimizationTarget
    title: str
    rationale: str
    confidence: float
    references: tuple[str, ...] = ()


@dataclass(frozen=True)
class OptimizationPlan:
    target: OptimizationTarget
    steps: tuple[str, ...]
    implementation_complexity: RiskLevel


@dataclass(frozen=True)
class EvolutionRecommendation:
    title: str
    description: str
    target: OptimizationTarget
    confidence: float


@dataclass(frozen=True)
class EvolutionProposal:
    proposal_id: str
    title: str
    description: str
    rationale: str
    expected_benefit: str
    expected_risk: str
    confidence: float
    priority: float
    affected_modules: tuple[str, ...]
    references: tuple[str, ...]
    implementation_complexity: RiskLevel
    estimated_performance_improvement: float
    target: OptimizationTarget
    impact: ImpactAssessment
    risk: RiskAssessment
    optimization_plan: OptimizationPlan


@dataclass(frozen=True)
class EvolutionHistory:
    reports: tuple["EvolutionReport", ...] = ()


@dataclass(frozen=True)
class EvolutionReport:
    evolution_id: str
    summary: str
    proposals: tuple[EvolutionProposal, ...]
    opportunities: tuple[ImprovementOpportunity, ...]
    recommendations: tuple[EvolutionRecommendation, ...]
    metrics: tuple[ImprovementMetric, ...] = ()
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, kw_only=True)
class EvolutionRequest:
    reflection_reports: tuple["ReflectionReport", ...]
    planner_metrics: tuple[ImprovementMetric, ...] = ()
    search_metrics: tuple[ImprovementMetric, ...] = ()
    memory_metrics: tuple[ImprovementMetric, ...] = ()
    execution_metrics: tuple[ImprovementMetric, ...] = ()
    response_metrics: tuple[ImprovementMetric, ...] = ()
    contexts: tuple["Context", ...] = ()
    event_history: tuple["DomainEvent[Any]", ...] = ()
    persist_to_memory: bool = False
    publish_to_knowledge: bool = False


@dataclass(frozen=True)
class EvolutionResult:
    report: EvolutionReport
    memory_record_id: str | None = None
    knowledge_entity_id: str | None = None


def evolution_id() -> str:
    return str(uuid.uuid4())


def proposal_id() -> str:
    return str(uuid.uuid4())
