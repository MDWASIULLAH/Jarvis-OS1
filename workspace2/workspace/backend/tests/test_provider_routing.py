"""Which provider gets asked to write free-form text.

The bug these pin down: a valid OpenRouter key was configured, verified, and
reported as connected -- and never used. `ModelRouter._request` only routes to
cloud when the caller passes `preference="cloud"` by name, and every caller in
the brain passed the literal string `"local"`. `_h_code_task` made it worse by
gating on `local_available`, which is true whenever the deterministic engine is
healthy (always), so it always took the "we have a model" branch, always asked
the local engine, and tagged the resulting clarification template
`code_generation ok=True detail="LLM"`.

Net effect for the user: "write me a function that reverses a string" answered
"send these details so I generate exactly what you want" on a machine that was
one routing decision away from writing the function.

These tests use the real LocalReasoningBackend -- the deterministic engine that
ships with JARVIS and is what `local` actually resolves to on a machine without
Ollama -- and a stand-in cloud backend, so no network is involved.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.brain.cognition import _looks_like_evidence_gap
from app.brain.llm_interface import ModelRouter
from app.brain.local_engine import LocalReasoningBackend
from app.capabilities.vision_ocr import ocr_available
from app.main import app

client = TestClient(app)


class _StandInCloud:
    """Enough of the backend protocol for provider registration; never called."""

    kind = "openai_compatible"
    model = "stand-in/model"

    def generate(self, prompt: str, system: str | None = None) -> str:  # pragma: no cover
        raise AssertionError("provider resolution must not call the backend")


def _router(*, cloud: bool, allow_cloud: bool) -> ModelRouter:
    return ModelRouter(
        local=LocalReasoningBackend(),
        cloud=_StandInCloud() if cloud else None,
        allow_cloud=allow_cloud,
    )


# ------------------------------------------------------- provider resolution

def test_configured_and_permitted_cloud_is_used_when_local_cannot_generate():
    """The whole bug in one assertion.

    The local engine composes from evidence and cannot write prose, so a
    configured, permitted cloud key is the only thing that can -- and must win
    without the user hand-picking it every message.
    """
    router = _router(cloud=True, allow_cloud=True)
    assert router.status()["generative_local"] is False
    assert router.generative_provider() == "cloud"


def test_cloud_is_not_used_when_the_user_has_not_permitted_it():
    """A saved key is not consent. JARVIS_ALLOW_CLOUD is the switch, and the
    privacy promise in /v1/status depends on this staying true."""
    assert _router(cloud=True, allow_cloud=False).generative_provider() is None


def test_no_provider_at_all_reports_none_rather_than_pretending():
    """This is what drives the honest "no language model is connected" banner;
    the old `local_available` gate reported a model on every install."""
    assert _router(cloud=False, allow_cloud=True).generative_provider() is None
    assert _router(cloud=False, allow_cloud=False).generative_provider() is None


def test_an_explicit_cloud_request_is_honoured():
    router = _router(cloud=True, allow_cloud=True)
    assert router.generative_provider("cloud") == "cloud"


def test_an_explicit_cloud_request_cannot_bypass_the_permission_gate():
    assert _router(cloud=True, allow_cloud=False).generative_provider("cloud") is None


# ------------------------------------------------------------ evidence gaps

def test_short_refusals_are_recognised_so_they_can_be_retried_unsourced():
    """Web results are titles plus one-line descriptions. Grounding strictly on
    them made the model refuse to explain a decorator -- something it knows
    perfectly well -- so a refusal has to be detectable to be recoverable."""
    assert _looks_like_evidence_gap("The evidence provided does not contain an explanation of that.")
    assert _looks_like_evidence_gap("The provided sources do not mention the answer.")
    assert _looks_like_evidence_gap("No information about that appears in the search results.")


def test_a_real_answer_is_never_mistaken_for_a_refusal():
    # A substantive answer may discuss what something does not do; length is
    # what separates that from a bare "the evidence doesn't cover this".
    long_answer = (
        "A decorator wraps a callable to extend it without editing the original. "
        "It does not modify the wrapped function's source, and it does not change "
        "its signature unless you use functools.wraps incorrectly. " * 4
    )
    assert not _looks_like_evidence_gap(long_answer)
    assert not _looks_like_evidence_gap("Paris is the capital of France [1].")


# ------------------------------------------------------- optional dependencies

def test_status_reports_whether_ocr_is_actually_installed():
    """Probed, not hardcoded: the AI Studio panel uses this to explain a missing
    Tesseract up front instead of after the user uploads a file."""
    features = client.get("/v1/status").json()["features"]
    assert features["ocr"] is ocr_available()


@pytest.mark.skipif(ocr_available(), reason="Tesseract is installed, so OCR does not degrade here.")
def test_missing_ocr_engine_returns_an_actionable_503_not_a_bare_500():
    """A missing optional binary is not a server fault. This used to escape as a
    500, indistinguishable in the UI from "JARVIS is broken", so nothing told the
    user that one install fixes it."""
    # A 1x1 PNG: valid image bytes, so the request only fails on the missing engine.
    png = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8AAAwAB"
        "/wD/AAAAAA=="
    )
    response = client.post("/v1/vision/ocr", json={"image_base64": png})
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "tesseract" in detail.lower()


def test_invalid_base64_is_still_a_400():
    response = client.post("/v1/vision/ocr", json={"image_base64": "not-base64!!"})
    assert response.status_code == 400
