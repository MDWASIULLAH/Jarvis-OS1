import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from app.capabilities.code_executor import run_python
from app.capabilities.image_pipeline import ImageGenerator
from app.capabilities.vision_ocr import extract_text_from_image


def test_ocr_reads_text_from_generated_image():
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "test.png")
        img = Image.new("RGB", (600, 150), color="white")
        draw = ImageDraw.Draw(img)
        # Reuse the app's font resolver instead of hardcoding one Linux path;
        # that path does not exist on macOS/Windows (or this sandbox), which
        # made the test fail for a missing font rather than a real OCR problem.
        font = ImageGenerator._font(40)
        draw.text((20, 45), "HELLO JARVIS", fill="black", font=font)
        img.save(path)

        text = extract_text_from_image(path)
        assert "HELLO" in text.upper()
        assert "JARVIS" in text.upper()


def test_code_executor_runs_simple_code():
    result = run_python("print('hello from sandbox')")
    assert result.exit_code == 0
    assert "hello from sandbox" in result.stdout
    assert result.timed_out is False


def test_code_executor_captures_errors():
    result = run_python("raise ValueError('boom')")
    assert result.exit_code != 0
    assert "ValueError" in result.stderr
    assert "boom" in result.stderr


def test_code_executor_enforces_timeout():
    result = run_python("while True:\n    pass", timeout_seconds=1)
    assert result.timed_out is True
