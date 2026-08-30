"""Strongly typed execution state and result contracts."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum

from ..capabilities.contracts import CapabilityResult


class ExecutionState(str, Enum):
    PENDING = "pending"
    WAITING = "waiting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True)
class TimingInfo:
    started_at: float | None = None
    completed_at: float | None = None
    duration_seconds: float = 0.0


@dataclass(frozen=True)
class RetryInfo:
    attempts: int = 0
    max_attempts: int = 1
    exhausted: bool = False


@dataclass(frozen=True)
class FailureReport:
    step_id: str | None
    capability_id: str | None
    error_type: str
    message: str


@dataclass(frozen=True)
class RollbackReport:
    step_id: str
    capability_id: str
    attempted: bool
    succeeded: bool
    message: str = ""


@dataclass(frozen=True)
class StepResult:
    step_id: str
    capability_id: str | None
    state: ExecutionState
    output: CapabilityResult | None = None
    timing: TimingInfo = field(default_factory=TimingInfo)
    retry: RetryInfo = field(default_factory=RetryInfo)
    failure: FailureReport | None = None
    rollback: RollbackReport | None = None


@dataclass(frozen=True)
class ExecutionMetrics:
    total_steps: int
    completed_steps: int
    failed_steps: int
    skipped_steps: int
    cancelled_steps: int
    timed_out_steps: int
    rolled_back_steps: int
    duration_seconds: float


@dataclass(frozen=True)
class ExecutionResult:
    plan_id: str
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: ExecutionState = ExecutionState.PENDING
    steps: tuple[StepResult, ...] = ()
    metrics: ExecutionMetrics = field(default_factory=lambda: ExecutionMetrics(0, 0, 0, 0, 0, 0, 0, 0.0))
    failures: tuple[FailureReport, ...] = ()
    rollbacks: tuple[RollbackReport, ...] = ()
    timing: TimingInfo = field(default_factory=TimingInfo)
