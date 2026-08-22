from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app.pipelines.document_extractor import DocumentExtractor
from app.pipelines.ocr_pipeline import (
    LOW_CONFIDENCE_THRESHOLD,
    LOW_OCR_QUALITY_WARNING,
    OcrPage,
    OcrPipeline,
    OcrResult,
    OcrUnavailableError,
    _join_hyphenated_lines,
    _join_orphan_characters,
    _preprocess_image,
    _words_to_text,
    find_tesseract_executable,
)


# ─────────────────────────────────────────────────────────────
# Fakes
# ─────────────────────────────────────────────────────────────
class FakeOutput:
    DICT = "dict"


def _make_data(
    words: list[tuple[str, float]],
) -> dict:
    """Build an image_to_data-style dict from (word, confidence) pairs."""
    return {
        "level": [5] * len(words),
        "page_num": [1] * len(words),
        "block_num": [1] * len(words),
        "par_num": [1] * len(words),
        "line_num": [1] * len(words),
        "word_num": list(range(1, len(words) + 1)),
        "left": [0] * len(words),
        "top": [0] * len(words),
        "width": [10] * len(words),
        "height": [10] * len(words),
        "conf": [confidence for _, confidence in words],
        "text": [word for word, _ in words],
    }


class _FakePytesseractSubmodule:
    """Mimics pytesseract.pytesseract, which holds tesseract_cmd."""

    tesseract_cmd: str = ""


class FakePytesseract:
    """In-memory stand-in for the real pytesseract module."""

    Output = FakeOutput
    pytesseract = _FakePytesseractSubmodule()

    def __init__(self, data: dict) -> None:
        self._data = data
        self.last_config: str | None = None
        self.last_lang: str | None = None

    def image_to_data(self, image, lang=None, config=None, output_type=None):
        self.last_lang = lang
        self.last_config = config
        return self._data


def _patch_ocr_available(monkeypatch, fake_pytesseract) -> None:
    monkeypatch.setattr(
        "app.pipelines.ocr_pipeline._import_pytesseract",
        lambda: fake_pytesseract,
    )
    monkeypatch.setattr(
        "app.pipelines.ocr_pipeline.find_tesseract_executable",
        lambda configured_path="": "C:/fake/tesseract.exe",
    )


# ─────────────────────────────────────────────────────────────
# Tesseract discovery
# ─────────────────────────────────────────────────────────────
def test_find_tesseract_executable_returns_configured_path(tmp_path: Path):
    fake = tmp_path / "tesseract.exe"
    fake.write_bytes(b"MZ")
    assert find_tesseract_executable(str(fake)) == str(fake)


def test_find_tesseract_executable_returns_none_when_missing(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("app.pipelines.ocr_pipeline.shutil.which", lambda _: None)
    assert find_tesseract_executable(str(tmp_path / "missing.exe")) is None


def test_pipeline_is_available_false_without_tesseract(monkeypatch):
    monkeypatch.setattr("app.pipelines.ocr_pipeline.shutil.which", lambda _: None)
    pipeline = OcrPipeline(language="eng", tesseract_path="C:/does/not/exist.exe")
    assert pipeline.is_available() is False


def test_pipeline_is_available_true_with_tesseract(monkeypatch):
    fake = FakePytesseract(_make_data([("Hi", 90.0)]))
    monkeypatch.setattr("app.pipelines.ocr_pipeline._import_pytesseract", lambda: fake)
    monkeypatch.setattr(
        "app.pipelines.ocr_pipeline.find_tesseract_executable",
        lambda configured_path="": "C:/fake/tesseract.exe",
    )
    assert OcrPipeline().is_available() is True


# ─────────────────────────────────────────────────────────────
# Pre-processing
# ─────────────────────────────────────────────────────────────
def test_preprocess_image_grayscales_and_upscales(tmp_path: Path):
    small = Image.new("RGB", (40, 20), color="white")
    processed = _preprocess_image(small)
    # Upscaled to at least the 300 DPI target dimension.
    assert max(processed.size) >= 1500
    # Grayscale (mode "L"), not RGB.
    assert processed.mode == "L"


# ─────────────────────────────────────────────────────────────
# Post-processing
# ─────────────────────────────────────────────────────────────
def test_join_hyphenated_lines():
    text = "This is a recog-\nnition test"
    assert _join_hyphenated_lines(text) == "This is a recognition test"


def test_join_orphan_characters():
    text = "T\nhe quick brown fox"
    assert _join_orphan_characters(text) == "The quick brown fox"


def test_join_orphan_characters_keeps_pronoun():
    # The pronoun "I" must never be merged with the next line.
    text = "I\nam learning"
    assert _join_orphan_characters(text) == "I\nam learning"


def test_words_to_text_drops_low_confidence_words():
    data = _make_data([("Recursion", 95.0), ("garbage", 20.0), ("works", 88.0)])
    text, confidence = _words_to_text(data)
    assert text == "Recursion works"
    assert confidence == pytest.approx(91.5)


def test_words_to_text_handles_empty_words():
    data = _make_data([("Hello", 95.0), ("", 90.0), ("world", 85.0)])
    text, _ = _words_to_text(data)
    assert text == "Hello world"


def test_words_to_text_empty_input():
    text, confidence = _words_to_text(_make_data([]))
    assert text == ""
    assert confidence == 0.0


# ─────────────────────────────────────────────────────────────
# ocr_image / ocr_pdf with a mocked pytesseract
# ─────────────────────────────────────────────────────────────
def test_ocr_image_extracts_text_and_confidence(monkeypatch, tmp_path: Path):
    image_path = tmp_path / "sample.png"
    Image.new("RGB", (80, 30), color="white").save(image_path)

    fake = FakePytesseract(_make_data([("Hello", 95.0), ("world", 90.0)]))
    _patch_ocr_available(monkeypatch, fake)

    page = OcrPipeline(language="eng").ocr_image(image_path, page_number=1)

    assert page.text == "Hello world"
    assert page.confidence == pytest.approx(92.5)
    assert page.page_number == 1
    assert fake.last_config is not None and "--psm 3" in fake.last_config
    assert fake.last_lang == "eng"


def test_ocr_image_flags_low_confidence(monkeypatch, tmp_path: Path):
    image_path = tmp_path / "blurry.png"
    Image.new("RGB", (80, 30), color="white").save(image_path)

    fake = FakePytesseract(_make_data([("Maybe", 50.0)]))
    _patch_ocr_available(monkeypatch, fake)

    page = OcrPipeline().ocr_image(image_path)
    assert page.confidence < LOW_CONFIDENCE_THRESHOLD
    assert LOW_OCR_QUALITY_WARNING in page.warnings


def test_ocr_image_empty_text_warns(monkeypatch, tmp_path: Path):
    image_path = tmp_path / "blank.png"
    Image.new("RGB", (80, 30), color="white").save(image_path)

    fake = FakePytesseract(_make_data([]))
    _patch_ocr_available(monkeypatch, fake)

    page = OcrPipeline().ocr_image(image_path)
    assert page.text == ""
    assert any("no readable text" in warning for warning in page.warnings)


def test_ocr_image_raises_when_unavailable(monkeypatch, tmp_path: Path):
    image_path = tmp_path / "sample.png"
    Image.new("RGB", (80, 30), color="white").save(image_path)

    monkeypatch.setattr("app.pipelines.ocr_pipeline._import_pytesseract", lambda: None)
    with pytest.raises(OcrUnavailableError):
        OcrPipeline().ocr_image(image_path)


def test_ocr_pdf_renders_each_page(monkeypatch, tmp_path: Path):
    import fitz

    pdf_path = tmp_path / "scanned.pdf"
    document = fitz.open()
    page = document.new_page()
    # Insert a real image so the page has no extractable text layer.
    image_path = tmp_path / "ink.png"
    Image.new("RGB", (60, 20), color="black").save(image_path)
    page.insert_image(page.rect, filename=str(image_path))
    document.save(str(pdf_path))
    document.close()

    fake = FakePytesseract(_make_data([("Page", 93.0), ("one", 89.0)]))
    _patch_ocr_available(monkeypatch, fake)

    result = OcrPipeline().ocr_pdf(pdf_path)
    assert len(result.pages) == 1
    assert result.text == "Page one"
    assert result.average_confidence == pytest.approx(91.0)


# ─────────────────────────────────────────────────────────────
# DocumentExtractor integration with OCR
# ─────────────────────────────────────────────────────────────
class FakeOcrPipeline:
    def __init__(self, page: OcrPage) -> None:
        self._page = page

    def is_available(self) -> bool:
        return True

    def ocr_image(self, image_source, page_number: int = 1) -> OcrPage:
        return self._page

    def ocr_pdf(self, pdf_path: Path) -> OcrResult:
        return OcrResult(pages=[self._page])


class UnavailableOcrPipeline:
    def is_available(self) -> bool:
        return False


def test_extractor_ocrs_standalone_image(tmp_path: Path):
    image_path = tmp_path / "notes.png"
    Image.new("RGB", (80, 30), color="white").save(image_path)

    page = OcrPage(page_number=1, text="Recursion explained", confidence=88.0)
    extractor = DocumentExtractor(ocr=FakeOcrPipeline(page))

    result = extractor.extract(image_path, "image")

    assert result.status == "extracted"
    assert result.text == "Recursion explained"
    assert result.word_count == 2
    assert result.pages[0].ocr_used is True
    assert result.pages[0].ocr_confidence == 88.0


def test_extractor_ocrs_scanned_pdf(tmp_path: Path):
    import fitz

    pdf_path = tmp_path / "scanned.pdf"
    document = fitz.open()
    page = document.new_page()
    image_path = tmp_path / "ink.png"
    Image.new("RGB", (60, 20), color="black").save(image_path)
    page.insert_image(page.rect, filename=str(image_path))
    document.save(str(pdf_path))
    document.close()

    page_result = OcrPage(page_number=1, text="Scanned content", confidence=91.0)
    extractor = DocumentExtractor(ocr=FakeOcrPipeline(page_result))

    result = extractor.extract(pdf_path, "pdf")

    assert result.status == "extracted"
    assert result.text == "Scanned content"
    assert result.is_image_pdf is True
    assert result.page_count == 1
    assert result.pages[0].ocr_used is True


def test_extractor_image_remains_pending_ocr_when_ocr_unavailable(tmp_path: Path):
    image_path = tmp_path / "notes.png"
    Image.new("RGB", (80, 30), color="white").save(image_path)

    extractor = DocumentExtractor(ocr=UnavailableOcrPipeline())

    result = extractor.extract(image_path, "image")

    assert result.status == "pending_ocr"
    assert result.text == ""
    assert result.error_message is not None
