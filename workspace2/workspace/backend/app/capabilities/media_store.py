"""
capabilities/media_store.py

A tiny content-addressed cache for every binary JARVIS produces or fetches
(searched images, generated images, screenshots, extracted page assets).

The chat API never inlines megabytes of base64 into a JSON response. It
returns `{"url": "/v1/media/<id>", ...}` and the browser fetches the bytes
from the same origin that serves the UI. That keeps chat history small enough
to store in localStorage and makes repeat views free.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}


@dataclass
class MediaItem:
    media_id: str
    kind: str            # "image" | "audio" | "video" | "document"
    media_type: str
    url: str
    bytes: int
    caption: str = ""
    source: str = ""
    source_url: str = ""
    width: Optional[int] = None
    height: Optional[int] = None
    created_at: float = 0.0

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v not in (None, "")} | {
            "media_id": self.media_id,
            "url": self.url,
            "kind": self.kind,
        }


class MediaStore:
    def __init__(self, data_dir: Path, max_items: int = 400):
        self.root = Path(data_dir) / "media"
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"
        self.max_items = max_items
        self._index: dict[str, dict] = {}
        if self.index_path.exists():
            try:
                self._index = json.loads(self.index_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self._index = {}

    # ---- internals ------------------------------------------------------

    def _flush(self) -> None:
        try:
            self.index_path.write_text(json.dumps(self._index), encoding="utf-8")
        except OSError:
            pass

    def _prune(self) -> None:
        if len(self._index) <= self.max_items:
            return
        ordered = sorted(self._index.items(), key=lambda kv: kv[1].get("created_at", 0))
        for media_id, meta in ordered[: len(self._index) - self.max_items]:
            path = self.root / meta.get("filename", "")
            try:
                if path.is_file():
                    path.unlink()
            except OSError:
                pass
            self._index.pop(media_id, None)

    # ---- public ---------------------------------------------------------

    def save_bytes(
        self,
        raw: bytes,
        media_type: str = "image/png",
        kind: str = "image",
        caption: str = "",
        source: str = "",
        source_url: str = "",
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> MediaItem:
        digest = hashlib.sha256(raw).hexdigest()[:20]
        extension = _EXTENSIONS.get(media_type) or mimetypes.guess_extension(media_type) or ".bin"
        filename = f"{digest}{extension}"
        path = self.root / filename
        if not path.exists():
            path.write_bytes(raw)
        item = MediaItem(
            media_id=digest,
            kind=kind,
            media_type=media_type,
            url=f"/v1/media/{digest}",
            bytes=len(raw),
            caption=caption,
            source=source,
            source_url=source_url,
            width=width,
            height=height,
            created_at=time.time(),
        )
        self._index[digest] = asdict(item) | {"filename": filename}
        self._prune()
        self._flush()
        return item

    def get(self, media_id: str) -> Optional[tuple[Path, str]]:
        meta = self._index.get(media_id)
        if not meta:
            return None
        path = self.root / meta.get("filename", "")
        if not path.is_file():
            return None
        return path, meta.get("media_type", "application/octet-stream")

    def metadata(self, media_id: str) -> Optional[dict]:
        meta = self._index.get(media_id)
        if not meta:
            return None
        return {k: v for k, v in meta.items() if k != "filename"}

    def recent(self, limit: int = 30, kind: Optional[str] = None) -> list[dict]:
        items = sorted(self._index.values(), key=lambda m: m.get("created_at", 0), reverse=True)
        if kind:
            items = [i for i in items if i.get("kind") == kind]
        return [{k: v for k, v in item.items() if k != "filename"} for item in items[:limit]]

    def count(self) -> int:
        return len(self._index)
