"""Workspace file management and live preview.

Safe CRUD operations on workspace files, ZIP export, and a local
file server for live preview of HTML/CSS/JS projects.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1/workspace", tags=["Workspace"])


class FileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, pattern=r"^[a-zA-Z0-9_\-./]+$")
    content: str = ""
    parent: str = ""


class FileUpdate(BaseModel):
    content: str


class FileRename(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, pattern=r"^[a-zA-Z0-9_\-./]+$")


class FileMove(BaseModel):
    path: str = Field(..., min_length=1, max_length=500, pattern=r"^[a-zA-Z0-9_\-./]*$")


class FileEntry(BaseModel):
    name: str
    path: str
    kind: str  # "file" or "directory"
    size: int
    modified: float


_workspace_root: Optional[Path] = None


def get_workspace_root() -> Path:
    if _workspace_root is None:
        raise RuntimeError("Workspace root not set; call set_workspace_root first")
    return _workspace_root


def set_workspace_root(root: Path) -> None:
    global _workspace_root
    _workspace_root = root
    _workspace_root.mkdir(parents=True, exist_ok=True)


def _safe_path(relative: str) -> Path:
    """Resolve a relative path and block traversal outside workspace."""
    root = get_workspace_root()
    resolved = (root / relative).resolve()
    if not str(resolved).startswith(str(root.resolve())):
        raise HTTPException(status_code=403, detail="Path traversal not allowed")
    return resolved


def _ensure_parent(path: Path) -> None:
    parent = path.parent
    root = get_workspace_root().resolve()
    if not str(parent.resolve()).startswith(str(root)):
        raise HTTPException(status_code=403, detail="Cannot write outside workspace")
    parent.mkdir(parents=True, exist_ok=True)


# -- File CRUD ---------------------------------------------------------


@router.get("/files")
async def list_files(path: str = Query("", max_length=500)) -> list[FileEntry]:
    safe = _safe_path(path) if path else get_workspace_root()
    if not safe.exists():
        return []
    entries: list[FileEntry] = []
    for item in sorted(safe.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
        entries.append(FileEntry(
            name=item.name,
            path=str(item.relative_to(get_workspace_root())),
            kind="directory" if item.is_dir() else "file",
            size=item.stat().st_size if item.is_file() else 0,
            modified=item.stat().st_mtime,
        ))
    return entries


@router.get("/files/read")
async def read_file(path: str = Query(..., min_length=1, max_length=500)) -> dict:
    safe = _safe_path(path)
    if not safe.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    try:
        content = safe.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File is not valid UTF-8 text")
    return {"path": path, "content": content, "size": safe.stat().st_size}


@router.post("/files")
async def create_file(body: FileCreate) -> FileEntry:
    safe = _safe_path(body.name)
    if safe.exists():
        raise HTTPException(status_code=409, detail=f"'{body.name}' already exists")
    _ensure_parent(safe)
    safe.write_text(body.content, encoding="utf-8")
    return FileEntry(
        name=safe.name,
        path=str(safe.relative_to(get_workspace_root())),
        kind="file",
        size=safe.stat().st_size,
        modified=safe.stat().st_mtime,
    )


@router.put("/files/{path:path}")
async def update_file(path: str, body: FileUpdate) -> dict:
    safe = _safe_path(path)
    if not safe.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    safe.write_text(body.content, encoding="utf-8")
    return {"path": path, "size": safe.stat().st_size}


@router.delete("/files/{path:path}")
async def delete_file(path: str) -> dict:
    safe = _safe_path(path)
    if not safe.exists():
        raise HTTPException(status_code=404, detail="File not found")
    kind = "directory" if safe.is_dir() else "file"
    if safe.is_dir():
        shutil.rmtree(safe)
    else:
        safe.unlink()
    return {"path": path, "kind": kind, "deleted": True}


@router.put("/files/{path:path}/rename")
async def rename_file(path: str, body: FileRename) -> dict:
    safe = _safe_path(path)
    if not safe.exists():
        raise HTTPException(status_code=404, detail="File not found")
    new_safe = safe.parent / body.name
    if new_safe.exists():
        raise HTTPException(status_code=409, detail=f"'{body.name}' already exists")
    safe.rename(new_safe)
    new_path = str(new_safe.relative_to(get_workspace_root()))
    return {"old_path": path, "new_path": new_path}


@router.put("/files/move")
async def move_file(body: FileMove, src: str = Query(..., min_length=1, max_length=500)) -> dict:
    safe_src = _safe_path(src)
    if not safe_src.exists():
        raise HTTPException(status_code=404, detail=f"Source '{src}' not found")
    dst = _safe_path(body.path)
    if dst.exists():
        raise HTTPException(status_code=409, detail=f"Destination '{body.path}' already exists")
    _ensure_parent(dst)
    safe_src.rename(dst)
    return {"src": src, "dst": body.path}


# -- Directory ---------------------------------------------------------


@router.post("/directories")
async def create_directory(path: str = Query(..., min_length=1, max_length=500)) -> FileEntry:
    safe = _safe_path(path)
    if safe.exists():
        raise HTTPException(status_code=409, detail=f"'{path}' already exists")
    safe.mkdir(parents=True)
    return FileEntry(
        name=safe.name,
        path=str(safe.relative_to(get_workspace_root())),
        kind="directory",
        size=0,
        modified=safe.stat().st_mtime,
    )


# -- Zip Export --------------------------------------------------------


@router.get("/export")
async def export_workspace() -> FileResponse:
    import tempfile
    import zipfile

    root = get_workspace_root()
    zip_dir = root.parent / "_workspace_exports"
    zip_dir.mkdir(exist_ok=True)
    zip_path = zip_dir / f"workspace_{uuid.uuid4().hex[:8]}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in root.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(root))
    return FileResponse(zip_path, media_type="application/zip", filename="workspace.zip")


# -- Preview Serve -----------------------------------------------------


@router.get("/preview/{rest_of_path:path}")
async def serve_preview(rest_of_path: str = "") -> FileResponse:
    root = get_workspace_root()
    if not rest_of_path:
        rest_of_path = "index.html"
    safe = _safe_path(rest_of_path)
    if not safe.is_file():
        raise HTTPException(status_code=404, detail="File not found for preview")

    media_map = {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".json": "application/json",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".woff2": "font/woff2",
        ".woff": "font/woff",
        ".ico": "image/x-icon",
    }
    media_type = media_map.get(safe.suffix.lower(), "application/octet-stream")
    return FileResponse(safe, media_type=media_type)


# -- Upload files (binary) ---------------------------------------------


@router.post("/upload")
async def upload_file(file: UploadFile) -> FileEntry:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")
    safe = _safe_path(file.filename)
    if safe.exists():
        raise HTTPException(status_code=409, detail=f"'{file.filename}' already exists")
    _ensure_parent(safe)
    content = await file.read()
    safe.write_bytes(content)
    return FileEntry(
        name=safe.name,
        path=str(safe.relative_to(get_workspace_root())),
        kind="file",
        size=safe.stat().st_size,
        modified=safe.stat().st_mtime,
    )
