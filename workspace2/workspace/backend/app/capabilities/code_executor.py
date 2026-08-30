"""
capabilities/code_executor.py

Implements the "run/debug this code" half of Section 2.9 -- runs Python in
a subprocess with a timeout and captures stdout/stderr/exit code.

Honest scope note: this is a *starting point*, not a hardened sandbox. It
stops infinite loops and shows real errors, which covers personal,
trusted-code use (the only use case JARVIS is meant for per Section 4).
For anything beyond that -- untrusted code, multi-user, internet-facing --
run this inside a container with no network access and real resource
limits (cgroups), not just a subprocess timeout.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass


@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool


def run_python(code: str, timeout_seconds: int = 5) -> ExecutionResult:
    fd, script_path = tempfile.mkstemp(suffix=".py")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(code)
        try:
            proc = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            return ExecutionResult(stdout=proc.stdout, stderr=proc.stderr, exit_code=proc.returncode, timed_out=False)
        except subprocess.TimeoutExpired as e:
            stdout = e.stdout or ""
            stderr = (e.stderr or "") + f"\n[Killed after exceeding {timeout_seconds}s timeout]"
            return ExecutionResult(stdout=stdout, stderr=stderr, exit_code=-1, timed_out=True)
    finally:
        os.unlink(script_path)
