"""Runtime configuration.

Configuration deliberately comes from the environment instead of source code.
That keeps API keys, device tokens, and personal endpoints out of the project.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """The small, dependency-free configuration surface for JARVIS Core."""
    data_dir: Path
    ollama_host: str
    ollama_model: str
    cloud_base_url: str | None
    cloud_api_key: str | None
    cloud_model: str | None
    allow_cloud: bool

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            data_dir=Path(os.getenv("JARVIS_DATA_DIR", str(Path.home() / ".jarvis"))),
            ollama_host=os.getenv("JARVIS_OLLAMA_HOST", "http://localhost:11434"),
            ollama_model=os.getenv("JARVIS_OLLAMA_MODEL", "llama3.1:8b"),
            cloud_base_url=os.getenv("JARVIS_CLOUD_BASE_URL") or None,
            cloud_api_key=os.getenv("JARVIS_CLOUD_API_KEY") or None,
            cloud_model=os.getenv("JARVIS_CLOUD_MODEL") or None,
            allow_cloud=_as_bool(os.getenv("JARVIS_ALLOW_CLOUD"), default=False),
        )
