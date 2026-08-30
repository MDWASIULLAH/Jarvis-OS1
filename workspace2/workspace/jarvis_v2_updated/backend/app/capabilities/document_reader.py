"""
capabilities/document_reader.py

Implements JARVIS Section 2.8 (read side) -- extracting text from PDF and
DOCX files so JARVIS can summarize or answer questions about an uploaded
document.
"""

from __future__ import annotations

from pathlib import Path

# Document parsing is an optional capability. These used to be hard imports,
# which meant a missing pypdf took down the entire server -- chat, memory and
# every other feature included -- for a format the user may never upload. They
# now degrade to a clear error raised only when a document is actually read.
try:
    import pypdf
except ImportError:  # pragma: no cover
    pypdf = None

try:
    from docx import Document
except ImportError:  # pragma: no cover
    Document = None


def read_pdf_text(path: str) -> str:
    if pypdf is None:
        raise RuntimeError(
            "PDF support needs the 'pypdf' package. Install it with: pip install pypdf"
        )
    reader = pypdf.PdfReader(path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()


def read_docx_text(path: str) -> str:
    if Document is None:
        raise RuntimeError(
            "DOCX support needs the 'python-docx' package. Install it with: pip install python-docx"
        )
    doc = Document(path)
    paragraphs = [p.text for p in doc.paragraphs]
    return "\n".join(paragraphs).strip()


def read_document(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return read_pdf_text(path)
    if suffix == ".docx":
        return read_docx_text(path)
    raise ValueError(f"Unsupported document type: {suffix}")
