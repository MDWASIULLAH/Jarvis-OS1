"""Planner: converts a Decision into a validated, non-executing ExecutionPlan."""

from __future__ import annotations

from ..brain.decision_engine import Decision
from ..capabilities.registry import CapabilityRegistry
from ..events.bus import EventBus
from ..events.model import PlanCreated, PlanCreatedPayload, PlanRejected, PlanRejectedPayload, PlanValidated, PlanValidatedPayload
from .models import ExecutionPlan
from .strategies import FutureAgentStrategy, ParallelStrategy, PlanStrategy, SequentialStrategy, SimplePlanStrategy


class PlanRejectedError(ValueError):
    """Raised only when the generated plan fails static DAG validation."""


class Planner:
    """A pure strategy selector. It reads metadata but never executes a capability."""

    def __init__(self, registry: CapabilityRegistry, event_bus: EventBus | None = None):
        self._registry = registry
        self._event_bus = event_bus
        self._simple = SimplePlanStrategy()
        self._sequential = SequentialStrategy()
        self._parallel = ParallelStrategy()
        self._future_agent = FutureAgentStrategy()

    def create_plan(self, decision: Decision, *, correlation_id: str | None = None) -> ExecutionPlan:
        strategy = self.select_strategy(decision)
        try:
            plan = strategy.build(decision, self._registry)
            errors = plan.validate()
        except Exception as exc:
            self._publish_rejected(decision, str(exc), correlation_id)
            raise PlanRejectedError(str(exc)) from exc
        if errors:
            reason = "; ".join(errors)
            self._publish_rejected(decision, reason, correlation_id, plan.plan_id)
            raise PlanRejectedError(reason)
        if self._event_bus is not None:
            event_correlation = correlation_id or decision.telemetry.correlation_id or decision.decision_id
            self._event_bus.publish(
                PlanCreated(
                    source="planner",
                    payload=PlanCreatedPayload(plan.plan_id, decision.decision_id, len(plan.steps)),
                    correlation_id=event_correlation,
                )
            )
            self._event_bus.publish(
                PlanValidated(
                    source="planner",
                    payload=PlanValidatedPayload(plan.plan_id, len(plan.steps)),
                    correlation_id=event_correlation,
                )
            )
        return plan

    def select_strategy(self, decision: Decision) -> PlanStrategy:
        if decision.requires_parallel_execution:
            return self._parallel
        if decision.requires_planner:
            return self._future_agent
        if len(decision.selected_capabilities) <= 1:
            return self._simple
        return self._sequential

    def _publish_rejected(
        self,
        decision: Decision,
        reason: str,
        correlation_id: str | None,
        plan_id: str = "uncreated",
    ) -> None:
        if self._event_bus is not None:
            self._event_bus.publish(
                PlanRejected(
                    source="planner",
                    payload=PlanRejectedPayload(plan_id, reason),
                    correlation_id=correlation_id or decision.telemetry.correlation_id or decision.decision_id,
                )
            )
