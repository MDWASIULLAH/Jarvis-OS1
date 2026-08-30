"""
main.py -- entrypoint.

Run with:  uvicorn app.main:app --reload

This serves both the JSON API and the frontend, so the whole assistant is a
single process on a single port: http://localhost:8000
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.routes import router
from .api.v1 import router as v1_router

app = FastAPI(title="JARVIS Local Agent")

# CORS stays permissive so the UI can also be opened straight off the
# filesystem or from a separate dev server during development. When the UI is
# served from the mount below it is same-origin and CORS is not involved at all.
# Wide open is acceptable here specifically because this binds to localhost and
# is a single-user personal assistant, not a multi-tenant public service.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes are registered before the static mount so that a file named like a
# route can never shadow the API.
app.include_router(router)
app.include_router(v1_router)


@app.get("/health")
def health():
    return {"status": "ok"}


# --- Frontend ---------------------------------------------------------------
# Mounting the UI at "/" removes the second server and the cross-origin setup
# that came with it: the browser loads the page and calls the API on one origin,
# so `fetch('/v1/chat')` just works with no CORS preflight and no port config.
#
# The mount is last because StaticFiles(html=True) claims every unmatched path;
# registering it earlier would swallow /v1/* and /health.
_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend-ui"

if (_FRONTEND_DIR / "index.html").is_file():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")
else:
    # Not fatal: the API is still fully usable on its own. Say so plainly
    # instead of failing at import time with a confusing stack trace.
    import logging

    logging.getLogger(__name__).warning(
        "Frontend not mounted: no index.html at %s. The API is still available.",
        _FRONTEND_DIR,
    )
