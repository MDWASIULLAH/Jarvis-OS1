"""Context Fabric public API."""

from .adapters import adapt_execution_context, adapt_response_context
from .contracts import (
    Context, ContextAttribute, ContextCancellationToken, ContextCreateRequest, ContextDeadline, ContextDependencies,
    ContextIdentity, ContextKind, ContextTelemetry, ContextUpdateRequest, FabricContext, ImmutableContextState,
)
from .manager import ContextManager, ContextVersionConflict
from .registry import ContextRegistry

__all__ = [
    "Context", "ContextAttribute", "ContextCancellationToken", "ContextCreateRequest", "ContextDeadline",
    "ContextDependencies", "ContextIdentity", "ContextKind", "ContextManager", "ContextRegistry", "ContextTelemetry",
    "ContextUpdateRequest", "ContextVersionConflict", "FabricContext", "ImmutableContextState", "adapt_execution_context",
    "adapt_response_context",
]
