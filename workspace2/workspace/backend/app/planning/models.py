"""Strongly typed, non-executing execution-plan model."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum


class StepStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    BLOCKED = "blocked"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ExecutionMode(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    DEFERRED = "deferred"


class CheckpointType(str, Enum):
    CONFIRMATION = "confirmation"
    MEMORY = "memory"
    REVIEW = "review"


class RollbackMode(str, Enum):
    NONE = "none"
    AUTOMATIC = "automatic"
    MANUAL = "manual"


@dataclass(frozen=True)
class PlanField:
    name: str
    value: str


@dataclass(frozen=True)
class ExpectedOutput:
    name: str
    description: str
    required: bool = True


@dataclass(frozen=True)
class StepDependency:
    """One directed dependency from this step to a prerequisite step."""

    prerequisite_step_id: str
    required_status: StepStatus = StepStatus.COMPLETED


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1
    backoff_seconds: float = 0.0
    retryable: bool = False


@dataclass(frozen=True)
class RollbackPolicy:
    mode: RollbackMode = RollbackMode.NONE
    instructions: str = "No rollback is required."


@dataclass(frozen=True)
class Checkpoint:
    checkpoint_id: str
    checkpoint_type: CheckpointType
    description: str
    before_step_id: str | None = None
    required: bool = True


@dataclass(frozen=True)
class PlanMetadata:
    strategy: str
    attributes: tuple[PlanField, ...] = ()


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    name: str
    description: str
    capability_id: str | None
    inputs: tuple[PlanField, ...] = ()
    expected_outputs: tuple[ExpectedOutput, ...] = ()
    dependencies: tuple[StepDependency, ...] = ()
    execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    timeout_seconds: float | None = None
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    rollback_policy: RollbackPolicy = field(default_factory=RollbackPolicy)
    requires_confirmation: bool = False
    requires_memory: bool = False
    can_run_parallel: bool = False
    metadata: tuple[PlanField, ...] = ()
    status: StepStatus = StepStatus.PENDING


@dataclass(frozen=True)
class ExecutionPlan:
    """A validated DAG description. It has no execution behaviour."""

    plan_id: str
    decision_id: str
    strategy: str
    steps: tuple[PlanStep, ...]
    checkpoints: tuple[Checkpoint, ...] = ()
    metadata: PlanMetadata = field(default_factory=lambda: PlanMetadata("unknown"))

    @classmethod
    def new(
        cls,
        decision_id: str,
        strategy: str,
        steps: tuple[PlanStep, ...],
        checkpoints: tuple[Checkpoint, ...] = (),
        metadata: PlanMetadata | None = None,
    ) -> "ExecutionPlan":
        return cls(
            plan_id=str(uuid.uuid4()),
            decision_id=decision_id,
            strategy=strategy,
            steps=steps,
            checkpoints=checkpoints,
            metadata=metadata or PlanMetadata(strategy),
        )

    def validate(self) -> tuple[str, ...]:
        step_ids = {step.step_id for step in self.steps}
        errors: list[str] = []
        if len(step_ids) != len(self.steps):
            errors.append("Plan contains duplicate step IDs.")
        for step in self.steps:
            for dependency in step.dependencies:
                if dependency.prerequisite_step_id == step.step_id:
                    errors.append(f"Step '{step.step_id}' cannot depend on itself.")
                elif dependency.prerequisite_step_id not in step_ids:
                    errors.append(
                        f"Step '{step.step_id}' depends on unknown step '{dependency.prerequisite_step_id}'."
                    )
        if not errors and self._has_cycle():
            errors.append("Plan dependency graph contains a cycle.")
        return tuple(errors)

    def topological_layers(self) -> tuple[tuple[str, ...], ...]:
        """Return stable DAG layers; steps in one layer may run in parallel."""
        if self.validate():
            return ()
        pending = {step.step_id: {dep.prerequisite_step_id for dep in step.dependencies} for step in self.steps}
        layers: list[tuple[str, ...]] = []
        while pending:
            ready = tuple(sorted(step_id for step_id, deps in pending.items() if not deps))
            if not ready:
                return ()
            layers.append(ready)
            for step_id in ready:
                pending.pop(step_id)
            for dependencies in pending.values():
                dependencies.difference_update(ready)
        return tuple(layers)

    def _has_cycle(self) -> bool:
        return bool(self.steps) and not self.topological_layers_unchecked()

    def topological_layers_unchecked(self) -> tuple[tuple[str, ...], ...]:
        pending = {step.step_id: {dep.prerequisite_step_id for dep in step.dependencies} for step in self.steps}
        layers: list[tuple[str, ...]] = []
        while pending:
            ready = tuple(sorted(step_id for step_id, deps in pending.items() if not deps))
            if not ready:
                return ()
            layers.append(ready)
            for step_id in ready:
                pending.pop(step_id)
            for dependencies in pending.values():
                dependencies.difference_update(ready)
        return tuple(layers)


# The requested ``Plan`` name is a stable alias for the executable-plan contract.
Plan = ExecutionPlan
