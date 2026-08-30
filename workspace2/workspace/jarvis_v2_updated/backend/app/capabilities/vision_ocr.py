"""
capabilities/vision_ocr.py

Implements "read this text from the photo" (Section 13.5) using Tesseract
via pytesseract. Needs the system `tesseract-ocr` binary installed
(`apt install tesseract-ocr` on Linux, `brew install tesseract` on macOS,
or the installer from github.com/UB-Mannheim/tesseract on Windows).

This is OCR on a still image the user provides (a photo, a screenshot) --
not live camera vision. Real-time camera understanding is a different,
much bigger feature (continuous frame capture + a vision model) that
belongs in a later phase, once there's a camera feed to work with.
"""

from __future__ import annotations

# OCR is optional. pytesseract also needs the native `tesseract` binary, which
# plenty of machines will not have. As hard imports these took the entire server
# down at startup -- chat, memory, everything -- over a feature the user may
# never touch. They now degrade to an actionable error raised only on use.
try:
    import pytesseract
except ImportError:  # pragma: no cover
    pytesseract = None

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


def ocr_available() -> bool:
    """True only if both the Python bindings and the tesseract binary are present."""
    if pytesseract is None or Image is None:
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def extract_text_from_image(path: str) -> str:
    if Image is None:
        raise RuntimeError(
            "Image reading needs the 'Pillow' package. Install it with: pip install Pillow"
        )
    if pytesseract is None:
        raise RuntimeError(
            "OCR needs the 'pytesseract' package plus the tesseract binary. "
            "Install with: pip install pytesseract && apt install tesseract-ocr"
        )
    image = Image.open(path)
    try:
        return pytesseract.image_to_string(image).strip()
    except pytesseract.TesseractNotFoundError as exc:  # pragma: no cover
        # The Python package alone is not enough; surface the real fix.
        raise RuntimeError(
            "The tesseract binary was not found. Install it with: "
            "apt install tesseract-ocr (Linux) or brew install tesseract (macOS)."
        ) from exc
