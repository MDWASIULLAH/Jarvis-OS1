"""Pure planning strategies. None of these classes execute capabilities."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..brain.decision_engine import Decision
from ..capabilities.registry import CapabilityRegistry
from .models import (
    Checkpoint,
    CheckpointType,
    ExecutionMode,
    ExecutionPlan,
    ExpectedOutput,
    PlanField,
    PlanMetadata,
    PlanStep,
    RetryPolicy,
    RollbackMode,
    RollbackPolicy,
    StepDependency,
)


class PlanStrategy(ABC):
    name: str

    @abstractmethod
    def build(self, decision: Decision, registry: CapabilityRegistry) -> ExecutionPlan:
        """Create a plan using registry metadata only."""


class SimplePlanStrategy(PlanStrategy):
    name = "simple"

    def build(self, decision: Decision, registry: CapabilityRegistry) -> ExecutionPlan:
        steps = tuple(_step_for(decision, registry, capability_id, index=0, mode=ExecutionMode.SEQUENTIAL) for capability_id in decision.selected_capabilities[:1])
        return _plan(decision, self.name, steps)


class SequentialStrategy(PlanStrategy):
    name = "sequential"

    def build(self, decision: Decision, registry: CapabilityRegistry) -> ExecutionPlan:
        steps: list[PlanStep] = []
        for index, capability_id in enumerate(decision.selected_capabilities):
            dependencies = (StepDependency(steps[-1].step_id),) if steps else ()
            steps.append(
                _step_for(
                    decision,
                    registry,
                    capability_id,
                    index=index,
                    mode=ExecutionMode.SEQUENTIAL,
                    dependencies=dependencies,
                )
            )
        return _plan(decision, self.name, tuple(steps))


class ParallelStrategy(PlanStrategy):
    name = "parallel"

    def build(self, decision: Decision, registry: CapabilityRegistry) -> ExecutionPlan:
        steps = tuple(
            _step_for(decision, registry, capability_id, index=index, mode=ExecutionMode.PARALLEL, can_run_parallel=True)
            for index, capability_id in enumerate(decision.selected_capabilities)
        )
        return _plan(decision, self.name, steps)


class FutureAgentStrategy(SequentialStrategy):
    """Produces a normal DAG while marking the strategy for a future agent planner."""

    name = "future_agent"


def _plan(decision: Decision, strategy: str, steps: tuple[PlanStep, ...]) -> ExecutionPlan:
    checkpoints: list[Checkpoint] = []
    if steps and decision.requires_confirmation:
        checkpoints.append(
            Checkpoint(strategy + "-confirmation", CheckpointType.CONFIRMATION, "User confirmation is required before execution.", steps[0].step_id)
        )
    if steps and decision.requires_memory:
        checkpoints.append(
            Checkpoint(strategy + "-memory", CheckpointType.MEMORY, "Read or update memory before execution.", steps[0].step_id)
        )
    return ExecutionPlan.new(
        decision.decision_id,
        strategy,
        steps,
        tuple(checkpoints),
        PlanMetadata(strategy, (PlanField("intent", decision.intent),)),
    )


def _step_for(
    decision: Decision,
    registry: CapabilityRegistry,
    capability_id: str,
    *,
    index: int,
    mode: ExecutionMode,
    dependencies: tuple[StepDependency, ...] = (),
    can_run_parallel: bool = False,
) -> PlanStep:
    metadata = registry.metadata(capability_id)
    inputs = tuple(PlanField(key, str(value)) for key, value in sorted((decision.routing.entities if decision.routing else {}).items()))
    destructive = bool({"file_write", "media_write", "desktop_control", "system_control"}.intersection(metadata.permissions))
    rollback = RollbackPolicy(
        RollbackMode.MANUAL if destructive else RollbackMode.NONE,
        "Review and reverse generated artifacts if required." if destructive else "No rollback is required.",
    )
    retry = RetryPolicy(
        max_attempts=decision.retry_policy.max_attempts,
        backoff_seconds=decision.retry_policy.backoff_seconds,
        retryable=decision.retry_policy.max_attempts > 1,
    )
    timeout = decision.timeout_seconds if decision.timeout_seconds is not None else (30.0 if "network" in metadata.permissions else 10.0)
    return PlanStep(
        step_id=f"step-{index + 1}-{capability_id}",
        name=metadata.display_name or capability_id.replace("_", " ").title(),
        description=f"Prepare {capability_id} for intent '{decision.intent}'.",
        capability_id=capability_id,
        inputs=inputs,
        expected_outputs=(ExpectedOutput("result", f"Result from {capability_id}"),),
        dependencies=dependencies,
        execution_mode=mode,
        timeout_seconds=timeout,
        retry_policy=retry,
        rollback_policy=rollback,
        requires_confirmation=decision.requires_confirmation,
        requires_memory=decision.requires_memory,
        can_run_parallel=can_run_parallel,
        metadata=(PlanField("capability_version", metadata.version),),
    )
