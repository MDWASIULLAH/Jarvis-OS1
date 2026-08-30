"""
security/permissions.py

Implements JARVIS Section 4 (Security & Safety Protocols).

This is the single choke point every capability (email, calendar, system
control, app control, ...) must pass through before doing anything that
touches the outside world. Nothing downstream should be able to bypass it.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ActionType(str, Enum):
    APP_OPEN = "app_open"
    WEB_SEARCH = "web_search"
    EMAIL_SEND = "email_send"
    FILE_DELETE = "file_delete"
    SYSTEM_SHUTDOWN = "system_shutdown"
    CALENDAR_ADD = "calendar_add"
    CLIPBOARD_ACCESS = "clipboard_access"
    FINANCIAL_TRANSACTION = "financial_transaction"
    BACKGROUND_MONITOR = "background_monitor"
    SCREEN_CAPTURE = "screen_capture"


# Section 4.1 -- hard-coded blocks. No confirmation flow can override these.
_BLOCKED_KEYWORDS = {
    "gpay", "google pay", "phonepe", "phone pe", "paytm", "amazon pay", "upi",
    "sbi yono", "yono", "hdfc bank", "icici", "banking app", "netbanking",
    "navi", "cred",
    "zerodha", "upstox", "groww", "crypto wallet", "binance", "coinbase",
    "metamask", "trading app",
}

# Section 4.2 -- these must show a preview and wait for explicit approval.
# APP_OPEN and SCREEN_CAPTURE are included because both genuinely touch the
# user's machine: launching a program and photographing the screen are exactly
# the actions that must never happen silently from a chat message.
_CONFIRMATION_REQUIRED = {
    ActionType.EMAIL_SEND,
    ActionType.FILE_DELETE,
    ActionType.SYSTEM_SHUTDOWN,
    ActionType.CALENDAR_ADD,
    ActionType.CLIPBOARD_ACCESS,
    ActionType.APP_OPEN,
    ActionType.SCREEN_CAPTURE,
}

_ALWAYS_BLOCKED = {
    ActionType.FINANCIAL_TRANSACTION,
    ActionType.BACKGROUND_MONITOR,
}


@dataclass
class ActionDecision:
    allowed: bool
    requires_confirmation: bool
    reason: str
    confirmation_id: Optional[str] = None


@dataclass
class _PendingAction:
    action_type: ActionType
    payload: dict
    # Who/what the action is aimed at (email recipient, app name, ...). This was
    # previously accepted by check_action and then thrown away, so by the time
    # the user approved an email there was no recipient left to send it to.
    target: str = ""
    created_at: float = field(default_factory=time.time)


class SecurityGate:
    """Single choke-point for anything JARVIS wants to do in the outside world."""

    def __init__(self, confirmation_ttl_seconds: int = 300):
        self._pending: dict = {}
        self._ttl = confirmation_ttl_seconds

    def _is_financial_target(self, text: str) -> bool:
        lower = text.lower()
        return any(keyword in lower for keyword in _BLOCKED_KEYWORDS)

    def check_action(
        self,
        action_type: ActionType,
        target: str = "",
        payload: Optional[dict] = None,
    ) -> ActionDecision:
        """Call this before executing ANY action that touches the outside world."""

        is_financial = self._is_financial_target(target) or action_type == ActionType.FINANCIAL_TRANSACTION

        if action_type in _ALWAYS_BLOCKED or is_financial:
            reason = (
                "I can't perform financial transactions or access payment/banking "
                "apps -- that's a hard-coded safety limit, not a judgment call I "
                "make each time. You'll need to complete this one manually."
                if is_financial
                else "I can't run in the background or monitor anything without "
                     "your explicit, per-use activation."
            )
            return ActionDecision(allowed=False, requires_confirmation=False, reason=reason)

        if action_type in _CONFIRMATION_REQUIRED:
            confirmation_id = str(uuid.uuid4())
            self._pending[confirmation_id] = _PendingAction(action_type, payload or {}, target=target)
            return ActionDecision(
                allowed=False,
                requires_confirmation=True,
                reason="This needs your confirmation before I go ahead.",
                confirmation_id=confirmation_id,
            )

        return ActionDecision(allowed=True, requires_confirmation=False, reason="Low-risk action, proceeding.")

    def confirm(self, confirmation_id: str) -> Optional[_PendingAction]:
        """User said yes -- pop and return the pending action so the caller can execute it."""
        pending = self._pending.pop(confirmation_id, None)
        if pending is not None and (time.time() - pending.created_at) > self._ttl:
            return None
        return pending

    def cancel(self, confirmation_id: str) -> bool:
        return self._pending.pop(confirmation_id, None) is not None
