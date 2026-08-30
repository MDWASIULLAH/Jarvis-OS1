import base64
import io

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.capabilities.image_pipeline import ImageGenerator
from app.main import app

client = TestClient(app)


def _test_image_base64(text: str) -> str:
    img = Image.new("RGB", (500, 120), color="white")
    draw = ImageDraw.Draw(img)
    # Reuse the app's font resolver rather than hardcoding one Linux path,
    # which is absent on macOS/Windows and in this sandbox.
    font = ImageGenerator._font(36)
    draw.text((10, 35), text, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def test_chat_with_image_attachment_runs_real_ocr_first():
    b64 = _test_image_base64("INVOICE 4471")
    response = client.post(
        "/v1/chat",
        json={"text": "what does this say", "attachments": [{"name": "photo.png", "media_type": "image/png", "base64": b64}]},
    )
    assert response.status_code == 200
    assert "INVOICE 4471" in response.json()["reply"]


def test_chat_without_attachments_still_works_unchanged():
    # This guards that plain chat keeps working alongside the attachment path.
    # It used to assert the reply echoed "hello there" verbatim, which only held
    # while chat was an echo stub -- a greeting now gets an actual greeting, so
    # assert on a real, substantive reply instead of parroted input.
    response = client.post("/v1/chat", json={"text": "hello there"})
    assert response.status_code == 200
    reply = response.json()["reply"]
    assert len(reply.strip()) > 20
    assert "traceback" not in reply.lower()


def test_chat_gracefully_handles_a_broken_attachment():
    response = client.post(
        "/v1/chat",
        json={"text": "look at this", "attachments": [{"name": "broken.png", "media_type": "image/png", "base64": "not-valid-base64!!"}]},
    )
    assert response.status_code == 200  # never a 500 just because one attachment is bad


def test_search_endpoint_returns_expected_shape():
    response = client.get("/v1/search", params={"query": "capital of France"})
    assert response.status_code == 200
    body = response.json()
    assert "answer" in body
    assert body["engine"] == "duckduckgo_instant_answer"


def test_cors_headers_present_for_cross_origin_frontend():
    response = client.options(
        "/v1/status",
        headers={"Origin": "http://localhost:5500", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers.get("access-control-allow-origin") == "*"
