"""Small encrypted RAG store that remains usable without cloud embeddings."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..memory.memory_store import LocalEncryptor
from ..memory.semantic_search import SemanticIndex


class KnowledgeBase:
    """Stores user-added text locally, encrypted at rest, and searches it with TF-IDF."""

    def __init__(self, data_dir: Path):
        self._lock = threading.RLock()
        self._encryptor = LocalEncryptor(data_dir / "jarvis.key")
        self._connection = sqlite3.connect(str(data_dir / "knowledge.db"), check_same_thread=False)
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS knowledge_chunks (
               id TEXT PRIMARY KEY,
               document_id TEXT NOT NULL,
               title TEXT NOT NULL,
               source TEXT NOT NULL,
               chunk_index INTEGER NOT NULL,
               content_enc TEXT NOT NULL,
               metadata_json TEXT NOT NULL,
               created_at TEXT NOT NULL
            )"""
        )
        self._connection.commit()

    @staticmethod
    def _chunks(text: str, size: int = 900) -> list[str]:
        clean = " ".join(text.split())
        return [clean[position : position + size] for position in range(0, len(clean), size) if clean[position : position + size]]

    def ingest_text(self, title: str, text: str, source: str = "manual", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        if not text.strip():
            raise ValueError("Knowledge content cannot be empty.")
        document_id = str(uuid.uuid4())
        chunks = self._chunks(text)
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            for index, chunk in enumerate(chunks):
                self._connection.execute(
                    """INSERT INTO knowledge_chunks
                       (id, document_id, title, source, chunk_index, content_enc, metadata_json, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(uuid.uuid4()),
                        document_id,
                        title.strip() or "Untitled knowledge",
                        source.strip() or "manual",
                        index,
                        self._encryptor.encrypt(chunk),
                        json.dumps(metadata or {}, ensure_ascii=False),
                        now,
                    ),
                )
            self._connection.commit()
        return {"document_id": document_id, "title": title, "source": source, "chunks": len(chunks)}

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, document_id, title, source, chunk_index, content_enc, metadata_json FROM knowledge_chunks"
            ).fetchall()
        entries: dict[str, str] = {}
        lookup: dict[str, tuple[Any, ...]] = {}
        for row in rows:
            entries[row[0]] = self._encryptor.decrypt(row[5])
            lookup[row[0]] = row
        index = SemanticIndex()
        index.build(entries)
        results = []
        for hit in index.search(query, top_k=max(1, min(top_k, 20))):
            row = lookup[hit["key"]]
            results.append(
                {
                    "document_id": row[1],
                    "title": row[2],
                    "source": row[3],
                    "chunk_index": row[4],
                    "text": hit["text"],
                    "score": hit["score"],
                    "metadata": json.loads(row[6]),
                }
            )
        return results

    def documents(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """SELECT document_id, title, source, MIN(created_at), COUNT(*)
                   FROM knowledge_chunks GROUP BY document_id, title, source ORDER BY MIN(created_at) DESC"""
            ).fetchall()
        return [
            {"document_id": row[0], "title": row[1], "source": row[2], "created_at": row[3], "chunks": row[4]}
            for row in rows
        ]

    def delete_document(self, document_id: str) -> bool:
        with self._lock:
            cursor = self._connection.execute("DELETE FROM knowledge_chunks WHERE document_id = ?", (document_id,))
            self._connection.commit()
        return cursor.rowcount > 0

    def close(self) -> None:
        with self._lock:
            self._connection.close()
