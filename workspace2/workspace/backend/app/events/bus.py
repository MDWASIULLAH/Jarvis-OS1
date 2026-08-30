"""In-process, dependency-injected event dispatcher for JARVIS."""

from __future__ import annotations

import asyncio
import inspect
import threading
import time
import uuid
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Optional

from .model import DomainEvent, EventMetadata, EventPriority, EventType

SubscriberHandler = Callable[[DomainEvent[Any]], Any | Awaitable[Any]]


@dataclass(frozen=True)
class Subscription:
    identifier: str
    event_type: EventType | None
    priority: int
    name: str


@dataclass(frozen=True)
class DispatchOutcome:
    subscription_id: str
    subscriber_name: str
    succeeded: bool
    error_type: str = ""
    error_message: str = ""


@dataclass(frozen=True)
class PublishReport:
    event_id: str
    correlation_id: str
    outcomes: tuple[DispatchOutcome, ...]

    @property
    def failed(self) -> tuple[DispatchOutcome, ...]:
        return tuple(outcome for outcome in self.outcomes if not outcome.succeeded)


@dataclass(frozen=True)
class EventTrace:
    event_id: str
    correlation_id: str
    event_type: EventType
    source: str
    started_at: float
    completed_at: float
    metadata: EventMetadata
    outcomes: tuple[DispatchOutcome, ...]


@dataclass
class _Subscriber:
    subscription: Subscription
    handler: SubscriberHandler
    sequence: int


class EventBus:
    """Ordered event dispatcher with isolated subscriber failures.

    The bus is deliberately in-process and synchronous-by-default. Its typed
    event model and subscription contract are transport-neutral, so a future
    distributed adapter can bridge the same events without changing publishers.
    """

    def __init__(self, trace_limit: int = 1_000):
        self._subscribers: dict[str, _Subscriber] = {}
        self._lock = threading.RLock()
        self._sequence = 0
        self._traces: deque[EventTrace] = deque(maxlen=max(1, trace_limit))

    def subscribe(
        self,
        event_type: EventType | None,
        handler: SubscriberHandler,
        *,
        priority: int | EventPriority = EventPriority.NORMAL,
        name: str | None = None,
    ) -> Subscription:
        if not callable(handler):
            raise TypeError("Event subscriber must be callable.")
        subscription = Subscription(
            identifier=str(uuid.uuid4()),
            event_type=event_type,
            priority=int(priority),
            name=name or getattr(handler, "__qualname__", handler.__class__.__name__),
        )
        with self._lock:
            self._sequence += 1
            self._subscribers[subscription.identifier] = _Subscriber(subscription, handler, self._sequence)
        return subscription

    def unsubscribe(self, subscription: Subscription | str) -> bool:
        identifier = subscription.identifier if isinstance(subscription, Subscription) else subscription
        with self._lock:
            return self._subscribers.pop(identifier, None) is not None

    def publish(self, event: DomainEvent[Any]) -> PublishReport:
        """Synchronously publish an event to ordered synchronous subscribers.

        Coroutine subscribers are isolated as failed outcomes here instead of
        being executed on a private loop; callers already in async code should
        use ``publish_async`` so ordering and exception isolation stay explicit.
        """
        started = time.time()
        outcomes = tuple(self._dispatch_sync(subscriber, event) for subscriber in self._matching(event))
        report = PublishReport(event.event_id, event.correlation_id, outcomes)
        self._record_trace(event, started, report)
        return report

    async def publish_async(self, event: DomainEvent[Any]) -> PublishReport:
        """Publish to synchronous and coroutine subscribers in priority order."""
        started = time.time()
        outcomes = []
        for subscriber in self._matching(event):
            try:
                result = subscriber.handler(event)
                if inspect.isawaitable(result):
                    await result
                outcomes.append(DispatchOutcome(subscriber.subscription.identifier, subscriber.subscription.name, True))
            except Exception as exc:  # Subscriber failures are intentionally isolated.
                outcomes.append(
                    DispatchOutcome(
                        subscriber.subscription.identifier,
                        subscriber.subscription.name,
                        False,
                        type(exc).__name__,
                        str(exc),
                    )
                )
        report = PublishReport(event.event_id, event.correlation_id, tuple(outcomes))
        self._record_trace(event, started, report)
        return report

    def traces(self, *, correlation_id: str | None = None, limit: int = 100) -> list[EventTrace]:
        with self._lock:
            traces = list(self._traces)
        if correlation_id is not None:
            traces = [trace for trace in traces if trace.correlation_id == correlation_id]
        return list(reversed(traces[-max(1, limit):]))

    def subscriber_count(self, event_type: EventType | None = None) -> int:
        with self._lock:
            return sum(1 for item in self._subscribers.values() if event_type is None or item.subscription.event_type in (None, event_type))

    def _matching(self, event: DomainEvent[Any]) -> list[_Subscriber]:
        with self._lock:
            matches = [
                subscriber
                for subscriber in self._subscribers.values()
                if subscriber.subscription.event_type in (None, event.event_type)
            ]
        return sorted(matches, key=lambda item: (-item.subscription.priority, item.sequence))

    @staticmethod
    def _dispatch_sync(subscriber: _Subscriber, event: DomainEvent[Any]) -> DispatchOutcome:
        try:
            result = subscriber.handler(event)
            if inspect.isawaitable(result):
                if inspect.iscoroutine(result):
                    result.close()
                raise RuntimeError("Coroutine subscriber requires publish_async.")
            return DispatchOutcome(subscriber.subscription.identifier, subscriber.subscription.name, True)
        except Exception as exc:  # A failed subscriber must never stop later subscribers.
            return DispatchOutcome(
                subscriber.subscription.identifier,
                subscriber.subscription.name,
                False,
                type(exc).__name__,
                str(exc),
            )

    def _record_trace(self, event: DomainEvent[Any], started: float, report: PublishReport) -> None:
        trace = EventTrace(
            event_id=event.event_id,
            correlation_id=event.correlation_id,
            event_type=event.event_type,
            source=event.source,
            started_at=started,
            completed_at=time.time(),
            metadata=event.metadata,
            outcomes=report.outcomes,
        )
        with self._lock:
            self._traces.append(trace)
