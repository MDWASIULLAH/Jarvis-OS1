"""Swappable, analysis-only proposal generation providers."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..reflection.models import ReflectionOutcome
from .models import (
    EvolutionProposal, EvolutionRecommendation, EvolutionReport, EvolutionRequest,
    ImpactAssessment, ImprovementOpportunity, OptimizationPlan, OptimizationTarget,
    RiskAssessment, RiskLevel, evolution_id, proposal_id,
)


class EvolutionProviderContext:
    def __init__(self, services: dict[str, Any] | None = None) -> None:
        self._services = dict(services or {})

    def require(self, name: str) -> Any:
        try:
            return self._services[name]
        except KeyError as exc:
            raise LookupError(f"Evolution dependency is unavailable: {name}") from exc


@dataclass(frozen=True)
class EvolutionProviderMetadata:
    provider_id: str
    display_name: str
    priority: int = 0
    capabilities: tuple[str, ...] = ("evolution",)


class EvolutionProvider(ABC):
    @abstractmethod
    def initialize(self, context: EvolutionProviderContext) -> None: ...
    @abstractmethod
    def shutdown(self) -> None: ...
    @abstractmethod
    def evolve(self, request: EvolutionRequest) -> EvolutionReport: ...


class RuleBasedEvolutionProvider(EvolutionProvider):
    """Deterministic proposal generator; it only recommends future changes."""

    def initialize(self, context: EvolutionProviderContext) -> None:
        del context

    def shutdown(self) -> None:
        return None

    def evolve(self, request: EvolutionRequest) -> EvolutionReport:
        opportunities = self._opportunities(request)
        proposals = tuple(self._proposal(opportunity) for opportunity in opportunities)
        recommendations = tuple(EvolutionRecommendation(item.title, item.description, item.target, item.confidence) for item in proposals)
        return EvolutionReport(
            evolution_id=evolution_id(),
            summary=f"Generated {len(proposals)} improvement proposal(s) from {len(request.reflection_reports)} reflection report(s).",
            proposals=proposals,
            opportunities=opportunities,
            recommendations=recommendations,
            metrics=(*request.planner_metrics, *request.search_metrics, *request.memory_metrics, *request.execution_metrics, *request.response_metrics),
        )

    @staticmethod
    def _opportunities(request: EvolutionRequest) -> tuple[ImprovementOpportunity, ...]:
        opportunities: list[ImprovementOpportunity] = []
        for report in request.reflection_reports:
            if report.outcome in (ReflectionOutcome.FAILURE, ReflectionOutcome.PARTIAL_SUCCESS, ReflectionOutcome.TIMED_OUT):
                target = OptimizationTarget.RETRY_STRATEGY if report.outcome is not ReflectionOutcome.TIMED_OUT else OptimizationTarget.LATENCY
                title = "Strengthen retry and fallback policy" if target is OptimizationTarget.RETRY_STRATEGY else "Reduce timeout-prone workflow latency"
                opportunities.append(ImprovementOpportunity(
                    f"reflection:{report.reflection_id}", target, title,
                    report.root_cause or "Reflection reported incomplete workflow execution.",
                    report.confidence, report.references,
                ))
            elif report.outcome in (ReflectionOutcome.SUCCESS, ReflectionOutcome.RETRIED):
                opportunities.append(ImprovementOpportunity(
                    f"workflow:{report.reflection_id}", OptimizationTarget.WORKFLOW_EFFICIENCY,
                    "Capture successful workflow pattern", "A successful workflow can inform future optimization decisions.",
                    report.confidence, report.references,
                ))
        for metric in (*request.execution_metrics, *request.planner_metrics):
            if metric.name in ("duration", "latency") and metric.value > 5:
                opportunities.append(ImprovementOpportunity(
                    f"metric:{metric.name}", OptimizationTarget.LATENCY, "Review high-latency workflow",
                    f"{metric.name} measured {metric.value:g} {metric.unit}.", 0.7,
                ))
        return tuple(opportunities)

    @staticmethod
    def _proposal(opportunity: ImprovementOpportunity) -> EvolutionProposal:
        risk_level = RiskLevel.MEDIUM if opportunity.target in (OptimizationTarget.PLANNING, OptimizationTarget.PARALLEL_EXECUTION) else RiskLevel.LOW
        impact = ImpactAssessment(
            execution_improvement=0.2 if opportunity.target in (OptimizationTarget.RETRY_STRATEGY, OptimizationTarget.LATENCY, OptimizationTarget.WORKFLOW_EFFICIENCY) else 0.1,
            planner_improvement=0.15 if opportunity.target is OptimizationTarget.PLANNING else 0.0,
            search_improvement=0.15 if opportunity.target is OptimizationTarget.SEARCH else 0.0,
            memory_improvement=0.15 if opportunity.target is OptimizationTarget.MEMORY else 0.0,
            scalability_improvement=0.1,
        )
        risk = RiskAssessment(architectural=risk_level, compatibility=RiskLevel.LOW, operational=risk_level, performance=RiskLevel.LOW, implementation_complexity=risk_level)
        plan = OptimizationPlan(opportunity.target, ("Review evidence and affected interfaces.", "Draft a backward-compatible implementation plan.", "Validate with targeted tests."), risk_level)
        priority = round(opportunity.confidence * (1.0 - (0.25 if risk_level is RiskLevel.MEDIUM else 0.0)), 3)
        return EvolutionProposal(
            proposal_id(), opportunity.title, opportunity.rationale,
            opportunity.rationale, "Improve future workflow reliability or efficiency.",
            f"{risk_level.value} implementation risk.", opportunity.confidence, priority,
            (opportunity.target.value,), opportunity.references, risk_level,
            impact.execution_improvement, opportunity.target, impact, risk, plan,
        )


EvolutionProviderFactory = Callable[[EvolutionProviderContext], EvolutionProvider]


@dataclass
class _Registration:
    metadata: EvolutionProviderMetadata
    factory: EvolutionProviderFactory
    instance: EvolutionProvider | None = None


class EvolutionProviderRegistry:
    def __init__(self, context: EvolutionProviderContext | None = None) -> None:
        self._context = context or EvolutionProviderContext()
        self._registrations: dict[str, _Registration] = {}
        self._lock = threading.RLock()

    def register(self, metadata: EvolutionProviderMetadata, factory: EvolutionProviderFactory) -> None:
        with self._lock:
            if not metadata.provider_id or metadata.provider_id in self._registrations:
                raise ValueError(f"Evolution provider is already registered: {metadata.provider_id}")
            self._registrations[metadata.provider_id] = _Registration(metadata, factory)

    def discover(self) -> tuple[EvolutionProviderMetadata, ...]:
        with self._lock:
            return tuple(sorted((item.metadata for item in self._registrations.values()), key=lambda item: (-item.priority, item.provider_id)))

    def get(self, provider_id: str) -> EvolutionProvider:
        with self._lock:
            try:
                registration = self._registrations[provider_id]
            except KeyError as exc:
                raise KeyError(f"Unknown evolution provider: {provider_id}") from exc
            if registration.instance is None:
                provider = registration.factory(self._context)
                if not isinstance(provider, EvolutionProvider):
                    raise TypeError("Evolution provider factory returned an invalid provider.")
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
