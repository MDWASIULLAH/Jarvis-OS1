import tempfile
from pathlib import Path

from reportlab.pdfgen import canvas

from app.capabilities.document_reader import read_docx_text, read_document, read_pdf_text
from app.capabilities.document_writer import write_docx, write_pptx, write_xlsx


def test_docx_round_trip():
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "test.docx")
        write_docx(path, "Test Title", ["First paragraph.", "Second paragraph."])
        text = read_docx_text(path)
        assert "First paragraph." in text
        assert "Second paragraph." in text
        assert "Test Title" in text


def test_read_document_dispatches_by_extension():
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "test.docx")
        write_docx(path, "Dispatch Test", ["Hello from docx."])
        assert "Hello from docx." in read_document(path)


def test_pdf_text_extraction():
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "test.pdf")
        c = canvas.Canvas(path)
        c.drawString(100, 750, "Hello from a generated PDF.")
        c.save()
        text = read_pdf_text(path)
        assert "Hello from a generated PDF." in text


def test_pptx_creates_file_with_slides():
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "test.pptx")
        write_pptx(path, "Deck Title", [{"heading": "Slide One", "bullets": ["Point A", "Point B"]}])
        assert Path(path).exists()
        assert Path(path).stat().st_size > 0


def test_xlsx_creates_file_with_rows():
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "test.xlsx")
        write_xlsx(path, "Sheet1", ["Name", "Score"], [["Alice", 90], ["Bob", 85]])
        assert Path(path).exists()
        assert Path(path).stat().st_size > 0
