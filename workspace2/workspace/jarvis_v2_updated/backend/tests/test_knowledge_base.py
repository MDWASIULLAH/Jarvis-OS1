import tempfile
from pathlib import Path

from app.knowledge.knowledge_base import KnowledgeBase


def test_ingest_and_search_returns_relevant_chunk():
    with tempfile.TemporaryDirectory() as tmp:
        kb = KnowledgeBase(Path(tmp))
        kb.ingest_text("Docker basics", "Docker containers package an application with its dependencies.", "manual")
        kb.ingest_text("Weather notes", "Bhubaneswar is usually warm and humid in the summer months.", "manual")

        results = kb.search("containers and dependencies", top_k=1)
        assert len(results) == 1
        assert "Docker" in results[0]["title"]


def test_knowledge_chunks_are_encrypted_on_disk():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        kb = KnowledgeBase(tmp_path)
        kb.ingest_text("Secret doc", "the-very-secret-marker-text", "manual")
        raw = (tmp_path / "knowledge.db").read_bytes()
        assert b"the-very-secret-marker-text" not in raw


def test_documents_lists_ingested_titles():
    with tempfile.TemporaryDirectory() as tmp:
        kb = KnowledgeBase(Path(tmp))
        kb.ingest_text("Doc A", "some content about kubernetes", "manual")
        docs = kb.documents()
        assert any(d["title"] == "Doc A" for d in docs)


def test_delete_document_removes_all_its_chunks():
    with tempfile.TemporaryDirectory() as tmp:
        kb = KnowledgeBase(Path(tmp))
        doc = kb.ingest_text("Doc to delete", "x" * 2000, "manual")  # long enough to span multiple chunks
        assert kb.delete_document(doc["document_id"]) is True
        assert kb.search("x", top_k=5) == []
        assert kb.delete_document(doc["document_id"]) is False  # already gone
