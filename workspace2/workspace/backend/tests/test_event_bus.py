from __future__ import annotations

import asyncio

from app.brain.decision_engine import Decision, DecisionPriority, RetryPolicy, RiskLevel
from app.brain.intent_router import RoutingResult
from app.events.bus import EventBus
from app.events.model import (
    EventAttribute,
    EventMetadata,
    EventPriority,
    EventType,
    SystemError,
    SystemErrorPayload,
)


def _event(*, correlation_id: str = "corr-1", metadata: EventMetadata | None = None) -> SystemError:
    return SystemError(
        source="test",
        payload=SystemErrorPayload("TestError", "test event", "tests"),
        correlation_id=correlation_id,
        metadata=metadata or EventMetadata(),
    )


def test_registration_and_unregistering():
    bus = EventBus()
    subscription = bus.subscribe(EventType.SYSTEM_ERROR, lambda event: None)

    assert bus.subscriber_count(EventType.SYSTEM_ERROR) == 1
    assert bus.unsubscribe(subscription) is True
    assert bus.unsubscribe(subscription) is False
    assert bus.subscriber_count(EventType.SYSTEM_ERROR) == 0


def test_sync_publish_multiple_subscribers_and_priority_ordering():
    bus = EventBus()
    calls: list[str] = []
    bus.subscribe(EventType.SYSTEM_ERROR, lambda event: calls.append("normal"), priority=EventPriority.NORMAL)
    bus.subscribe(EventType.SYSTEM_ERROR, lambda event: calls.append("high"), priority=EventPriority.HIGH)
    bus.subscribe(None, lambda event: calls.append("all"), priority=EventPriority.LOW)

    report = bus.publish(_event())

    assert calls == ["high", "normal", "all"]
    assert all(outcome.succeeded for outcome in report.outcomes)


def test_failed_subscriber_isolated_from_remaining_subscribers():
    bus = EventBus()
    calls: list[str] = []

    def broken(event):
        raise ValueError("expected failure")

    bus.subscribe(EventType.SYSTEM_ERROR, broken, priority=100)
    bus.subscribe(EventType.SYSTEM_ERROR, lambda event: calls.append("still-called"))

    report = bus.publish(_event())

    assert calls == ["still-called"]
    assert len(report.failed) == 1
    assert report.failed[0].error_type == "ValueError"


def test_async_publish_awaits_coroutine_and_sync_subscribers_in_order():
    bus = EventBus()
    calls: list[str] = []

    async def asynchronous(event):
        await asyncio.sleep(0)
        calls.append("async")

    bus.subscribe(EventType.SYSTEM_ERROR, asynchronous, priority=80)
    bus.subscribe(EventType.SYSTEM_ERROR, lambda event: calls.append("sync"), priority=50)

    report = asyncio.run(bus.publish_async(_event()))

    assert calls == ["async", "sync"]
    assert all(outcome.succeeded for outcome in report.outcomes)


def test_correlation_ids_metadata_and_tracing_are_preserved():
    bus = EventBus()
    metadata = EventMetadata(trace_parent_id="parent-1", attributes=(EventAttribute("request_kind", "chat"),))
    event = _event(correlation_id="corr-42", metadata=metadata)

    bus.publish(event)
    traces = bus.traces(correlation_id="corr-42")

    assert event.event_id
    assert traces[0].event_id == event.event_id
    assert traces[0].correlation_id == "corr-42"
    assert traces[0].metadata.trace_parent_id == "parent-1"
    assert traces[0].metadata.value_for("request_kind") == "chat"


def test_decision_contract_keeps_legacy_fields_and_future_execution_defaults():
    routing = RoutingResult("task.code", 0.9)
    decision = Decision(
        routing=routing,
        intent=routing.intent,
        confidence=routing.confidence,
        priority=DecisionPriority.HIGH,
        risk_level=RiskLevel.MODERATE,
        retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=0.5),
        requires_planner=True,
        requires_memory=True,
        requires_confirmation=True,
    )

    payload = decision.to_dict()

    assert payload["needs_planning"] is True
    assert payload["needs_memory"] is True
    assert payload["requires_planner"] is True
    assert payload["requires_parallel_execution"] is False
    assert payload["retry_policy"]["max_attempts"] == 2
    assert payload["risk_level"] == "moderate"
