"""Context Fabric lifecycle manager."""

from __future__ import annotations

import threading
import uuid
from dataclasses import replace

from ..events.bus import EventBus
from ..events.model import ContextCreated, ContextDisposed, ContextPayload, ContextUpdated
from .adapters import adapt_execution_context, adapt_response_context
from .contracts import (
    Context,
    ContextCreateRequest,
    ContextDeadline,
    ContextDependencies,
    ContextIdentity,
    ContextKind,
    ContextUpdateRequest,
    FabricContext,
    ImmutableContextState,
)
from .registry import ContextRegistry


class ContextVersionConflict(RuntimeError):
    """A lifecycle update used an outdated Fabric context version."""


class ContextManager:
    """Owns Fabric envelopes while leaving existing context implementations intact."""

    def __init__(
        self,
        *,
        registry: ContextRegistry | None = None,
        dependencies: ContextDependencies | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._registry = registry or ContextRegistry(dependencies)
        self._event_bus = event_bus
        self._contexts: dict[str, Context] = {}
        self._lock = threading.RLock()
        for kind in ContextKind:
            if not self._registry.has_factory(kind):
                self._registry.register(kind, self._create_fabric_context)
        execution_type = self._execution_type()
        response_type = self._response_type()
        if not self._registry.has_adapter(execution_type):
            self._registry.register_adapter(execution_type, adapt_execution_context)
        if not self._registry.has_adapter(response_type):
            self._registry.register_adapter(response_type, adapt_response_context)

    @property
    def registry(self) -> ContextRegistry:
        return self._registry

    def create(self, request: ContextCreateRequest) -> Context:
        context = self._registry.create(request)
        with self._lock:
            if context.context_id in self._contexts:
                raise ValueError(f"Context already exists: {context.context_id}")
            self._contexts[context.context_id] = context
        self._publish(ContextCreated, context)
        return context

    def update(self, context_id: str, update: ContextUpdateRequest) -> Context:
        with self._lock:
            current = self.get(context_id)
            if current.version != update.expected_version:
                raise ContextVersionConflict(f"Expected version {update.expected_version}, found {current.version}.")
            replacement = current.with_update(state=update.state, metadata=update.metadata)
            self._contexts[context_id] = replacement
        self._publish(ContextUpdated, replacement)
        return replacement

    def dispose(self, context_id: str) -> Context:
        with self._lock:
            try:
                context = self._contexts.pop(context_id)
            except KeyError as exc:
                raise KeyError(f"Unknown context: {context_id}") from exc
        context.cancellation.cancel("Context disposed.")
        self._publish(ContextDisposed, context)
        return context

    def get(self, context_id: str) -> Context:
        with self._lock:
            try:
                return self._contexts[context_id]
            except KeyError as exc:
                raise KeyError(f"Unknown context: {context_id}") from exc

    def clone(self, context_id: str) -> Context:
        parent = self.get(context_id)
        request = ContextCreateRequest(
            kind=parent.kind,
            identity=parent.identity,
            state=parent.state,
            parent_context_id=parent.context_id,
            timeout_seconds=parent.deadline.remaining_seconds(),
            telemetry=parent.telemetry,
            metadata=parent.metadata,
        )
        return self.create(request)

    def inherit(self, parent_context_id: str, request: ContextCreateRequest) -> Context:
        parent = self.get(parent_context_id)
        inherited_identity = ContextIdentity(
            correlation_id=parent.identity.correlation_id,
            execution_id=request.identity.execution_id or parent.identity.execution_id,
            conversation_id=request.identity.conversation_id or parent.identity.conversation_id,
            mission_id=request.identity.mission_id or parent.identity.mission_id,
            user_id=request.identity.user_id or parent.identity.user_id,
            session_id=request.identity.session_id or parent.identity.session_id,
        )
        inherited = replace(
            request,
            identity=inherited_identity,
            state=parent.state.merge(request.state),
            parent_context_id=parent.context_id,
        )
        return self.create(inherited)

    def adapt(self, source: object, *, register: bool = False) -> Context:
        context = self._registry.adapt(source)
        if register:
            with self._lock:
                self._contexts[context.context_id] = context
        return context

    @staticmethod
    def _create_fabric_context(request: ContextCreateRequest, dependencies: ContextDependencies) -> FabricContext:
        return FabricContext(
            context_id=str(uuid.uuid4()),
            kind=request.kind,
            identity=request.identity,
            state=request.state,
            parent_context_id=request.parent_context_id,
            deadline=ContextDeadline.for_timeout(request.timeout_seconds),
            telemetry=request.telemetry,
            metadata=request.metadata,
        )

    @staticmethod
    def _execution_type():
        from ..execution.context import ExecutionContext
        return ExecutionContext

    @staticmethod
    def _response_type():
        from ..responses.context import ResponseContext
        return ResponseContext

    def _publish(self, event_type, context: Context) -> None:
        if self._event_bus is not None:
            self._event_bus.publish(
                event_type(
                    source="context_fabric",
                    payload=ContextPayload(context.context_id, context.kind.value, context.parent_context_id),
                    correlation_id=context.identity.correlation_id,
                )
            )
