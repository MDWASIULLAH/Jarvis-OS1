"""
connectors/store.py

Persistent, encrypted storage for connector credentials.

Secret values are encrypted at rest with the same AES-256-GCM helper the memory
system uses, and are never returned to the browser -- the API only ever exposes
a masked preview (`····abcd`). Non-secret values (a base URL, an email address)
are stored in the clear on purpose so the UI can show you what is configured.

Credentials already supplied through environment variables are reported as
connected too, so a setup configured via the environment doesn't misleadingly
show up as "not connected" in the UI.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Optional

from ..memory.memory_store import LocalEncryptor
from .registry import CATALOG, ConnectorSpec, get_spec

# Environment variables that already configure a connector elsewhere in the
# app. Listing them here keeps the UI honest about what is actually live.
_ENV_FALLBACKS: dict[str, dict[str, str]] = {
    "image_api": {
        "api_url": "JARVIS_IMAGE_API_URL",
        "api_key": "JARVIS_IMAGE_API_KEY",
        "model": "JARVIS_IMAGE_MODEL",
    },
    "cloud_llm": {
        "base_url": "JARVIS_CLOUD_BASE_URL",
        "api_key": "JARVIS_CLOUD_API_KEY",
        "model": "JARVIS_CLOUD_MODEL",
    },
}


def _mask(value: str) -> str:
    """Masked preview of a secret: enough to recognise, not enough to reuse."""
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) <= 4:
        return "·" * len(value)
    return "·" * 4 + value[-4:]


class ConnectorStore:
    """Reads and writes connector credentials for the local user."""

    def __init__(self, data_dir: Path):
        self.path = data_dir / "connectors.json"
        self._encryptor = LocalEncryptor(data_dir / "connectors.key")
        self._lock = threading.Lock()
        self._data: dict = self._load()

    # ----- persistence -----

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text("utf-8")) or {}
        except (json.JSONDecodeError, OSError):
            # A corrupt file must not take the whole app down; treat it as empty
            # and let the user reconnect.
            return {}

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)
        try:
            # Owner-only: this file holds encrypted secrets, but the plaintext
            # non-secret fields (addresses, hostnames) are private too.
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    # ----- credential access -----

    def credentials(self, connector_id: str) -> dict:
        """Decrypted values for internal use. Falls back to the environment."""
        spec = get_spec(connector_id)
        if spec is None:
            return {}

        entry = self._data.get(connector_id) or {}
        stored = entry.get("values") or {}
        out: dict[str, str] = {}

        for f in spec.fields:
            raw = stored.get(f.key)
            if raw is None or raw == "":
                continue
            if f.secret:
                try:
                    out[f.key] = self._encryptor.decrypt(raw)
                except Exception:
                    # A value encrypted under a rotated/lost key is unusable.
                    # Skip it so the connector reads as incomplete rather than
                    # failing with a decryption traceback at call time.
                    continue
            else:
                out[f.key] = raw

        # Environment wins only where nothing was saved through the UI, so an
        # explicit in-app connection always takes precedence.
        for key, env_name in _ENV_FALLBACKS.get(connector_id, {}).items():
            if not out.get(key):
                value = os.getenv(env_name)
                if value:
                    out[key] = value

        return out

    def is_connected(self, connector_id: str) -> bool:
        """True when every required field for the connector has a value."""
        spec = get_spec(connector_id)
        if spec is None:
            return False
        creds = self.credentials(connector_id)
        return all(
            str(creds.get(f.key, "") or "").strip()
            for f in spec.fields
            if f.required
        )

    def save(self, connector_id: str, values: dict) -> None:
        spec = get_spec(connector_id)
        if spec is None:
            raise KeyError(connector_id)

        with self._lock:
            entry = self._data.setdefault(connector_id, {})
            stored = entry.setdefault("values", {})

            for f in spec.fields:
                if f.key not in values:
                    continue
                incoming = str(values.get(f.key) or "").strip()
                if not incoming:
                    # An empty submission for a secret means "leave it alone",
                    # so re-saving a form without retyping the token does not
                    # silently wipe the stored credential.
                    if f.secret:
                        continue
                    stored.pop(f.key, None)
                    continue
                stored[f.key] = (
                    self._encryptor.encrypt(incoming) if f.secret else incoming
                )

            entry["connected_at"] = entry.get("connected_at") or time.time()
            entry["updated_at"] = time.time()
            self._flush()

    def delete(self, connector_id: str) -> bool:
        with self._lock:
            existed = connector_id in self._data
            self._data.pop(connector_id, None)
            self._flush()
            return existed

    def record_test(self, connector_id: str, ok: bool, message: str) -> None:
        """Remember the last verification so the UI can show it after a reload."""
        with self._lock:
            entry = self._data.setdefault(connector_id, {})
            entry["last_test"] = {
                "ok": ok,
                "message": message,
                "at": time.time(),
            }
            self._flush()

    # ----- presentation -----

    def status(self, spec: ConnectorSpec) -> dict:
        """Safe-to-serialise state for one connector."""
        entry = self._data.get(spec.id) or {}
        creds = self.credentials(spec.id)

        env_keys = _ENV_FALLBACKS.get(spec.id, {})
        stored_values = entry.get("values") or {}
        from_env = bool(
            env_keys
            and not stored_values
            and any(os.getenv(name) for name in env_keys.values())
        )

        values: dict[str, str] = {}
        for f in spec.fields:
            value = str(creds.get(f.key, "") or "")
            if not value:
                continue
            # Secrets leave the process masked, never in full.
            values[f.key] = _mask(value) if f.secret else value

        return {
            "id": spec.id,
            "connected": self.is_connected(spec.id),
            "from_environment": from_env,
            "values": values,
            "connected_at": entry.get("connected_at"),
            "updated_at": entry.get("updated_at"),
            "last_test": entry.get("last_test"),
        }

    def status_all(self) -> list[dict]:
        return [self.status(spec) for spec in CATALOG]
