from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "frontend-v2"

SOURCE_DIRS = ("app", "components", "features", "layouts", "services", "store")

def _sources():
    for directory in SOURCE_DIRS:
        base = ROOT / directory
        if not base.is_dir():
            continue
        for path in base.rglob("*.ts*"):
            yield path, path.read_text(encoding="utf-8")

def test_exported_v2_frontend_is_the_mountable_application():
    assert (ROOT / "out" / "index.html").is_file()
    assert (ROOT / "app" / "page.tsx").is_file()
    assert (ROOT / "features" / "chat" / "chat-experience.tsx").is_file()

def test_v2_frontend_routes_backend_calls_through_one_resolver():
    """The API origin is resolved in one place, and stays relative in production.

    This used to assert a literal `fetch("/v1/chat/stream"`. That is only correct
    when FastAPI serves the exported UI from its own origin; under `next dev` the
    UI is on 3000 and the backend on 8000, so the relative path hit Next and 404'd
    -- the reason every panel rendered "Unavailable". The contract that actually
    matters is that calls go through services/backend.ts, which returns an empty
    base (i.e. same origin) whenever the page is already served by the backend.
    """
    resolver = (ROOT / "services" / "backend.ts").read_text(encoding="utf-8")
    chat = (ROOT / "features" / "chat" / "chat-service.ts").read_text(encoding="utf-8")
    client = (ROOT / "services" / "api-client.ts").read_text(encoding="utf-8")

    assert "backendBase" in resolver and "apiUrl" in resolver
    # Same-origin is preserved when FastAPI (or a proxy on 80/443) serves the UI.
    assert 'port === BACKEND_PORT || port === ""' in resolver and 'return ""' in resolver
    assert "NEXT_PUBLIC_JARVIS_API_URL" in resolver

    assert 'apiUrl("/v1/chat/stream")' in chat and "services/backend" in chat
    assert "apiUrl" in client

def test_v2_frontend_never_hardcodes_a_backend_origin_outside_the_resolver():
    """Only services/backend.ts may name a host; anything else breaks on deploy."""
    offenders = [
        str(path.relative_to(ROOT)).replace("\\", "/")
        for path, text in _sources()
        if path.name != "backend.ts" and ("127.0.0.1:8000" in text or "localhost:8000" in text)
    ]
    assert not offenders, f"hardcoded backend origin in {offenders}"

def test_v2_frontend_has_no_bare_relative_api_calls():
    """A relative /v1 call bypasses the resolver and 404s against `next dev`."""
    offenders = [
        str(path.relative_to(ROOT)).replace("\\", "/")
        for path, text in _sources()
        if 'fetch("/v1' in text or "fetch(`/v1" in text or "fetch('/v1" in text
    ]
    assert not offenders, f"relative backend call in {offenders}"
