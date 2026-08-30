"""Compatibility adapters for existing immutable JARVIS contexts."""

from __future__ import annotations

from .contracts import (
    ContextAttribute,
    ContextDeadline,
    ContextDependencies,
    ContextIdentity,
    ContextKind,
    ContextTelemetry,
    FabricContext,
    ImmutableContextState,
)


def adapt_execution_context(source, dependencies: ContextDependencies) -> FabricContext:
    """Map the existing ExecutionContext without changing it or its ownership."""
    from ..execution.context import ExecutionContext

    if not isinstance(source, ExecutionContext):
        raise TypeError("Expected ExecutionContext.")
    state = ImmutableContextState(tuple(ContextAttribute(key, str(value)) for key, value in source.shared_state.snapshot().items()))
    return FabricContext(
        context_id=source.execution_id,
        kind=ContextKind.EXECUTION,
        identity=ContextIdentity(source.correlation_id, source.execution_id, source.conversation_id, user_id=source.user_id, session_id=source.session_id),
        state=state,
        deadline=ContextDeadline(source.timeout_manager.deadline_monotonic),
        cancellation=source.cancellation_token,
        telemetry=ContextTelemetry(source.correlation_id),
        metadata=tuple(ContextAttribute(item.key, item.value) for item in source.metadata),
    )


def adapt_response_context(source, dependencies: ContextDependencies) -> FabricContext:
    """Map the existing ResponseContext through its owned execution identity."""
    from ..responses.context import ResponseContext

    if not isinstance(source, ResponseContext):
        raise TypeError("Expected ResponseContext.")
    execution = source.execution_context
    return FabricContext(
        context_id=source.response_id,
        kind=ContextKind.RESPONSE,
        identity=ContextIdentity(execution.correlation_id, execution.execution_id, execution.conversation_id, user_id=execution.user_id, session_id=execution.session_id),
        parent_context_id=execution.execution_id,
        deadline=ContextDeadline(execution.timeout_manager.deadline_monotonic),
        cancellation=execution.cancellation_token,
        telemetry=ContextTelemetry(execution.correlation_id),
        metadata=tuple(ContextAttribute(item.key, item.value) for item in source.metadata),
    )
