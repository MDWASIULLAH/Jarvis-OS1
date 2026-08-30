"""Test-wide isolation of the JARVIS data directory.

Every integration test drives the real `app.main:app`, which builds a Runtime
from `Settings.from_environment()`. Without this file that resolves to
`~/.jarvis` -- the user's live data directory -- so simply running the suite
mutated real state:

  * `test_tools_are_discovered_from_the_capability_registry` toggled
    `code_runner` off and never restored it, leaving `tool_state.json` at
    `{"code_runner": false}`. That silently disables code execution in the
    running app, which is the single most confusing failure mode here: chat
    would accept a coding request and then decline to run anything, with
    nothing in the UI to explain why.
  * memory facts, knowledge documents, tasks, and paired companion devices
    from test fixtures accumulated in the real databases.

`Settings.from_environment()` reads `JARVIS_DATA_DIR`, so pointing that at a
throwaway directory fixes all of it at once. This must happen at *import*
time rather than in a fixture: pytest imports conftest before the test
modules, and those modules do `from app.main import app` at module scope,
which constructs the Runtime immediately.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

# Claim a scratch data directory before any test module imports app.main.
_ISOLATED_DATA_DIR = Path(tempfile.mkdtemp(prefix="jarvis-tests-"))
os.environ["JARVIS_DATA_DIR"] = str(_ISOLATED_DATA_DIR)


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001 - pytest hook signature
    """Remove the scratch directory once the run is over.

    Best-effort: on Windows a SQLite handle can still be open when the session
    ends, and failing to clean up a temp directory must not fail the run.
    """
    shutil.rmtree(_ISOLATED_DATA_DIR, ignore_errors=True)
