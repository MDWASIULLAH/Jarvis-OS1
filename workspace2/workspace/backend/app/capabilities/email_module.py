"""
capabilities/email_module.py

Implements JARVIS Section 2.4 -- email read/compose/reply, always through a
draft -> preview -> explicit approval flow (Section 4.2, rule 1). Nothing is
ever sent silently.
"""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Callable, Optional

from ..security.permissions import ActionDecision, ActionType, SecurityGate

# Gmail's submission endpoint. Implicit TLS on 465 avoids the STARTTLS upgrade
# dance and is what Google documents for app passwords.
_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 465


@dataclass
class EmailDraft:
    to: str
    subject: str
    body: str


class EmailModule:
    def __init__(
        self,
        security: SecurityGate,
        llm_generate,
        credentials: Optional[Callable[[], dict]] = None,
    ):
        self.security = security
        self.llm_generate = llm_generate  # e.g. LLMBackend.generate
        # Called at send time (not construction) so connecting Gmail mid-session
        # takes effect without rebuilding this module.
        self._credentials = credentials or (lambda: {})

    def compose_draft(self, to: str, intent: str) -> EmailDraft:
        """intent e.g. 'leave request for tomorrow, family emergency'"""
        prompt = (
            f"Write a concise, professional email to {to}. "
            f"Context: {intent}. Start the reply with 'Subject: ...' on its own line."
        )
        text = self.llm_generate(prompt)
        subject, body = self._split_subject_body(text)
        return EmailDraft(to=to, subject=subject, body=body)

    @staticmethod
    def _split_subject_body(text: str):
        lines = text.splitlines()
        if lines and lines[0].lower().startswith("subject:"):
            return lines[0].split(":", 1)[1].strip(), "\n".join(lines[1:]).strip()
        return "No subject", text

    def request_send(self, draft: EmailDraft) -> ActionDecision:
        """Never sends directly -- routes through the security gate's
        confirmation flow."""
        return self.security.check_action(
            ActionType.EMAIL_SEND,
            target=draft.to,
            payload={"subject": draft.subject, "body": draft.body},
        )

    def execute_send(self, confirmation_id: str) -> str:
        """Actually deliver the approved draft over SMTP.

        This used to return "Email sent successfully, Sir." unconditionally
        without contacting any mail server -- so every send silently succeeded
        while nothing was ever delivered. It now sends for real and, when Gmail
        is not connected, says so instead of claiming success.
        """
        pending = self.security.confirm(confirmation_id)
        if pending is None:
            return "That confirmation expired or was never issued -- ask me to draft it again."

        creds = self._credentials() or {}
        address = (creds.get("address") or "").strip()
        # Google shows app passwords in spaced groups of four; the spaces are
        # for readability and must not be sent.
        password = (creds.get("app_password") or "").replace(" ", "").strip()
        if not address or not password:
            return (
                "I can't send that yet -- Gmail isn't connected. Open Connectors "
                "and add your Gmail address with a Google App Password, then ask "
                "me to send it again."
            )

        payload = pending.payload or {}
        message = EmailMessage()
        message["From"] = address
        message["To"] = pending.target
        message["Subject"] = payload.get("subject") or "No subject"
        message.set_content(payload.get("body") or "")

        try:
            with smtplib.SMTP_SSL(_SMTP_HOST, _SMTP_PORT, timeout=20) as smtp:
                smtp.login(address, password)
                smtp.send_message(message)
        except smtplib.SMTPAuthenticationError:
            return (
                "Gmail rejected the sign-in. Reconnect Gmail with a valid "
                "16-character App Password (2-step verification must be on)."
            )
        except smtplib.SMTPRecipientsRefused:
            return f"Gmail refused the recipient address {pending.target}."
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            return f"The message was not sent: {exc}"

        return f"Email sent to {pending.target}, Sir."
