from app.brain.local_engine import LocalReasoningBackend


def test_generic_code_request_returns_code_guidance_not_factual_failure():
    backend = LocalReasoningBackend()
    reply = backend.generate("write a code for me")
    assert "I can write code for you right now" in reply
    assert "reliable source" not in reply.lower()


def test_python_code_request_mentions_python():
    backend = LocalReasoningBackend()
    reply = backend.generate("write python code for an api")
    assert "Python" in reply
