from __future__ import annotations

import time

import pytest

from app.contexts import (
    ContextAttribute,
    ContextCreateRequest,
    ContextDependencies,
    ContextIdentity,
    ContextKind,
    ContextManager,
    ContextRegistry,
    ContextUpdateRequest,
    ContextVersionConflict,
    FabricContext,
    ImmutableContextState,
)
from app.events.bus import EventBus
from app.events.model import EventType
from app.execution.context import ExecutionContext
from app.execution.models import ExecutionResult
from app.planning.models import ExecutionPlan, PlanField, PlanStep
from app.responses.context import ResponseContext


def _plan() -> ExecutionPlan:
    return ExecutionPlan.new("decision", "context", (PlanStep("step", "step", "step", "capability", metadata=(PlanField("operation", "run"),)),))


def test_context_creation_registry_and_dependency_injection():
    dependencies = ContextDependencies({"tenant": "acme"})
    registry = ContextRegistry(dependencies)

    def factory(request: ContextCreateRequest, services: ContextDependencies) -> FabricContext:
        return FabricContext(context_id="user-context", kind=request.kind, identity=request.identity, state=request.state.with_value("tenant", services.require("tenant")))

    registry.register(ContextKind.USER, factory)
    manager = ContextManager(registry=registry)
    context = manager.create(ContextCreateRequest(ContextKind.USER))

    assert ContextKind.USER in registry.discover()
    assert context.state.value_for("tenant") == "acme"


def test_context_lifecycle_cancellation_timeout_and_events():
    bus = EventBus()
    events: list[EventType] = []
    bus.subscribe(None, lambda event: events.append(event.event_type))
    manager = ContextManager(event_bus=bus)
    context = manager.create(ContextCreateRequest(ContextKind.SEARCH, timeout_seconds=0.01))
    updated = manager.update(context.context_id, ContextUpdateRequest(1, ImmutableContextState((ContextAttribute("stage", "running"),))))
    with pytest.raises(ContextVersionConflict):
        manager.update(updated.context_id, ContextUpdateRequest(1))
    time.sleep(0.02)
    disposed = manager.dispose(context.context_id)

    assert updated.version == 2 and updated.state.value_for("stage") == "running"
    assert updated.deadline.expired is True
    assert disposed.cancellation.cancelled is True
    assert events == [EventType.CONTEXT_CREATED, EventType.CONTEXT_UPDATED, EventType.CONTEXT_DISPOSED]


def test_context_clone_inheritance_and_immutable_state():
    manager = ContextManager()
    parent = manager.create(
        ContextCreateRequest(
            ContextKind.CONVERSATION,
            ContextIdentity(conversation_id="conversation", user_id="user"),
            ImmutableContextState((ContextAttribute("locale", "en"),)),
        )
    )
    clone = manager.clone(parent.context_id)
    child = manager.inherit(
        parent.context_id,
        ContextCreateRequest(ContextKind.EXECUTION, state=ImmutableContextState((ContextAttribute("locale", "hi"),))),
    )

    assert clone.parent_context_id == parent.context_id and clone.state == parent.state
    assert child.parent_context_id == parent.context_id
    assert child.identity.correlation_id == parent.identity.correlation_id
    assert child.identity.conversation_id == "conversation"
    assert child.state.value_for("locale") == "hi"
    assert parent.state.value_for("locale") == "en"


def test_existing_execution_and_response_contexts_work_through_adapters_without_mutation():
    plan = _plan()
    execution = ExecutionContext.create(plan, execution_id="execution", correlation_id="correlation", conversation_id="conversation")
    execution.shared_state.set("tool", "search")
    response = ResponseContext.create(ExecutionResult(plan.plan_id, execution_id="execution"), execution, response_id="response")
    manager = ContextManager()

    execution_envelope = manager.adapt(execution, register=True)
    response_envelope = manager.adapt(response)

    assert execution_envelope.kind is ContextKind.EXECUTION
    assert execution_envelope.state.value_for("tool") == "search"
    assert response_envelope.kind is ContextKind.RESPONSE
    assert response_envelope.parent_context_id == "execution"
    assert execution.execution_id == "execution" and response.response_id == "response"
