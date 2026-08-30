"""Optional event subscribers owned by the Runtime composition root."""

from __future__ import annotations

from ..observability.audit import AuditLog
from .model import DomainEvent


class AuditEventObserver:
    """Records event lifecycle metadata without coupling publishers to audit storage."""

    def __init__(self, audit: AuditLog):
        self._audit = audit

    def handle(self, event: DomainEvent[object]) -> None:
        self._audit.record(
            "domain_event",
            "published",
            {
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "correlation_id": event.correlation_id,
                "source": event.source,
                "priority": int(event.priority),
            },
        )
