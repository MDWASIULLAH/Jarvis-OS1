from app.brain.llm_interface import MockBackend
from app.capabilities.email_module import EmailModule
from app.security.permissions import SecurityGate


def test_compose_and_send_requires_confirmation():
    security = SecurityGate()
    llm = MockBackend()
    email = EmailModule(security, llm.generate)

    draft = email.compose_draft("boss@example.com", "requesting leave tomorrow")
    assert draft.to == "boss@example.com"
    assert draft.body  # non-empty

    decision = email.request_send(draft)
    assert decision.requires_confirmation is True

    # With no Gmail connected, execute_send must NOT claim success. It used to
    # return "Email sent successfully, Sir." without contacting any mail server,
    # and this assertion (`"sent" in result`) is what allowed that to pass.
    result = email.execute_send(decision.confirmation_id)
    assert "isn't connected" in result.lower()
    assert "connectors" in result.lower()


def test_send_delivers_over_smtp_when_gmail_is_connected(monkeypatch):
    """The approved draft reaches SMTP with the right recipient and subject."""
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            sent["endpoint"] = (host, port)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def login(self, address, password):
            sent["login"] = (address, password)

        def send_message(self, message):
            sent["to"] = message["To"]
            sent["from"] = message["From"]
            sent["subject"] = message["Subject"]

    monkeypatch.setattr("app.capabilities.email_module.smtplib.SMTP_SSL", FakeSMTP)

    security = SecurityGate()
    email = EmailModule(
        security,
        MockBackend().generate,
        # Spaces are how Google displays app passwords; they must be stripped.
        credentials=lambda: {"address": "me@gmail.com", "app_password": "abcd efgh ijkl mnop"},
    )

    draft = email.compose_draft("boss@example.com", "requesting leave tomorrow")
    decision = email.request_send(draft)
    result = email.execute_send(decision.confirmation_id)

    assert sent["endpoint"] == ("smtp.gmail.com", 465)
    assert sent["login"] == ("me@gmail.com", "abcdefghijklmnop")
    # Regression guard: the recipient used to be dropped by the security gate,
    # which left nobody to deliver to once the user approved the send.
    assert sent["to"] == "boss@example.com"
    assert sent["from"] == "me@gmail.com"
    assert "boss@example.com" in result
