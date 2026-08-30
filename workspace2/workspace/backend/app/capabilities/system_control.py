"""
capabilities/system_control.py

Implements JARVIS Section 2.10 -- system control. Low-risk actions (volume,
brightness) proceed immediately; destructive ones (shutdown, restart) must
go through the security gate's confirmation flow first (Section 4.2).

The actual OS hooks are platform-specific and left as placeholders on
purpose -- e.g. on Windows you'd shell out to a volume-control utility or
use pycaw, on macOS `osascript`, on Linux `amixer`/`brightnessctl`. Wire in
whichever fits your target OS once this is running on-device.
"""

from __future__ import annotations

import platform

from ..security.permissions import ActionDecision, ActionType, SecurityGate


class SystemControlModule:
    def __init__(self, security: SecurityGate):
        self.security = security
        self.os_name = platform.system()  # "Windows" | "Darwin" | "Linux"

    def set_volume(self, level_percent: int) -> str:
        decision = self.security.check_action(ActionType.APP_OPEN, target="volume-control")
        if not decision.allowed:
            return decision.reason
        # TODO: platform-specific volume call goes here.
        return f"Volume set to {level_percent}%."

    def request_shutdown(self) -> ActionDecision:
        return self.security.check_action(ActionType.SYSTEM_SHUTDOWN, target="local-machine")

    def execute_shutdown(self, confirmation_id: str) -> str:
        pending = self.security.confirm(confirmation_id)
        if pending is None:
            return "That confirmation expired -- ask me to shut down again if you still want to."
        # TODO: platform-specific shutdown call goes here. Left unimplemented
        # on purpose so this scaffold can never actually shut down a machine
        # while you're testing it.
        return "Shutting down now, Sir."
