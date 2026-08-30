from app.security.permissions import ActionType, SecurityGate


def test_blocks_financial_apps():
    gate = SecurityGate()
    decision = gate.check_action(ActionType.APP_OPEN, target="Open GPay and send money")
    assert decision.allowed is False
    assert decision.requires_confirmation is False


def test_email_send_requires_confirmation():
    gate = SecurityGate()
    decision = gate.check_action(ActionType.EMAIL_SEND, target="boss@example.com")
    assert decision.allowed is False
    assert decision.requires_confirmation is True
    assert decision.confirmation_id is not None


def test_confirmed_action_can_be_executed_once():
    gate = SecurityGate()
    decision = gate.check_action(ActionType.EMAIL_SEND, target="boss@example.com", payload={"subject": "hi"})
    pending = gate.confirm(decision.confirmation_id)
    assert pending is not None
    assert gate.confirm(decision.confirmation_id) is None  # can't reuse a confirmation


def test_low_risk_action_proceeds_without_confirmation():
    gate = SecurityGate()
    decision = gate.check_action(ActionType.WEB_SEARCH, target="react docs")
    assert decision.allowed is True
    assert decision.requires_confirmation is False
