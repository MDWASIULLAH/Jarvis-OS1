"""DAG execution contracts and the registry-backed Tool Executor."""

from .context import (
    CapabilityCompatibilityAdapter,
    CapabilityInvocationStyle,
    CancellationToken,
    ContextCapability,
    ContextAttribute,
    ExecutionContext,
    ExecutionMetricsTracker,
    SharedExecutionState,
    TimeoutManager,
)
from .executor import ToolExecutor
from .middleware import ExecutionMiddleware, MiddlewarePipeline
from .models import (
    ExecutionMetrics,
    ExecutionResult,
    ExecutionState,
    FailureReport,
    RetryInfo,
    RollbackReport,
    StepResult,
    TimingInfo,
)

__all__ = [
    "CapabilityCompatibilityAdapter", "CapabilityInvocationStyle", "CancellationToken", "ContextAttribute", "ContextCapability",
    "ExecutionContext", "ExecutionMetrics", "ExecutionMetricsTracker", "ExecutionMiddleware", "ExecutionResult",
    "ExecutionState", "FailureReport", "MiddlewarePipeline", "RetryInfo", "RollbackReport", "SharedExecutionState",
    "StepResult", "TimeoutManager", "TimingInfo", "ToolExecutor",
]
