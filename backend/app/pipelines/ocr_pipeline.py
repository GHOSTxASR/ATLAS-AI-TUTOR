from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PIL import Image as PILImage

# ─────────────────────────────────────────────────────────────
# Configuration constants
# ─────────────────────────────────────────────────────────────
# Tesseract config modes (see 00_IMPLEMENTATION_PLAN.md section 22.2).
PSM = 3   # Fully automatic page segmentation
OEM = 3   # Default engine (LSTM neural nets + legacy)

# Words with confidence below this are discarded from the output.
WORD_CONFIDENCE_THRESHOLD = 40.0
# Documents with an average confidence below this are flagged in the UI.
LOW_CONFIDENCE_THRESHOLD = 60.0
LOW_OCR_QUALITY_WARNING = "Low OCR quality — document may not be searchable accurately."

# Pre-processing targets.
TARGET_MIN_DIMENSION = 1500  # Rough 300 DPI equivalent for a typical page
DESKEW_ANGLE_THRESHOLD_DEGREES = 2.0

TESSERACT_WINDOWS_CANDIDATES = (
    "C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
    "C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe",
)

INSTALL_HINT = (
    "Install Tesseract OCR (https://github.com/UB-Mannheim/tesseract/wiki) "
    "and set its path in settings.toml under [ingestion] tesseract_path."
)


class OcrUnavailableError(RuntimeError):
    """Raised when Tesseract is not installed or pytesseract is unavailable."""


def find_tesseract_executable(configured_path: str = "") -> str | None:
    """Locate the Tesseract executable.

    Resolution order:
    1. Explicitly configured path (``settings.ingestion.tesseract_path``).
    2. Well-known Windows install locations.
    3. ``tesseract`` on PATH.
    """
    if configured_path:
        path = Path(configured_path)
        if path.is_file():
            return str(path)

    for candidate in TESSERACT_WINDOWS_CANDIDATES:
        path = Path(candidate)
        if path.is_file():
            return str(path)

    found = shutil.which("tesseract")
    return found if found else None


def _import_pytesseract() -> Any | None:
    """Import pytesseract lazily so the rest of the app works without it."""
    try:
        import pytesseract

        return pytesseract
    except ImportError:
        return None


@dataclass
class OcrPage:
    """OCR result for a single page (or a standalone image)."""

    page_number: int
    text: str
    confidence: float = 0.0  # 0-100
    warnings: list[str] = field(default_factory=list)


@dataclass
class OcrResult:
    """OCR result for a whole document (one or more pages)."""

    pages: list[OcrPage] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(page.text for page in self.pages if page.text).strip()

    @property
    def average_confidence(self) -> float:
        confidences = [page.confidence for page in self.pages if page.text]
        if not confidences:
            return 0.0
        return round(sum(confidences) / len(confidences), 1)


# ─────────────────────────────────────────────────────────────
# Pre-processing
# ─────────────────────────────────────────────────────────────
def _scale_to_min_dimension(image: "PILImage.Image") -> "PILImage.Image":
    """Upscale small images so Tesseract sees roughly 300 DPI text."""
    from PIL import Image

    max_dimension = max(image.size)
    if max_dimension < TARGET_MIN_DIMENSION:
        scale = TARGET_MIN_DIMENSION / max_dimension
        new_size = (round(image.width * scale), round(image.height * scale))
        image = image.resize(new_size, Image.LANCZOS)
    return image


def _deskew(binary: Any) -> Any:
    """Rotate the image back if the detected skew exceeds 2 degrees."""
    import cv2

    try:
        # Text pixels are black (0) after THRESH_BINARY; invert so text is
        # white, then fit a minimum-area rectangle around it.
        coords = cv2.findNonZero(cv2.bitwise_not(binary))
        if coords is None:
            return binary
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = 90 + angle
        if abs(angle) < DESKEW_ANGLE_THRESHOLD_DEGREES:
            return binary
        height, width = binary.shape[:2]
        center = (width // 2, height // 2)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(
            binary,
            matrix,
            (width, height),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_REPLICATE,
        )
    except Exception:
        # Deskewing is best-effort; a failure must not kill OCR.
        return binary


def _preprocess_image(image: "PILImage.Image") -> "PILImage.Image":
    """Grayscale + Otsu threshold + deskew + 300 DPI scaling."""
    import cv2
    import numpy as np
    from PIL import Image

    image = _scale_to_min_dimension(image)
    array = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(array, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    binary = _deskew(binary)
    return Image.fromarray(binary)


# ─────────────────────────────────────────────────────────────
# Post-processing
# ─────────────────────────────────────────────────────────────
def _words_to_text(data: dict[str, Any]) -> tuple[str, float]:
    """Reconstruct line-oriented text from pytesseract's image_to_data dict.

    Discards words whose confidence is below ``WORD_CONFIDENCE_THRESHOLD`` and
    returns ``(text, average_confidence)``. Lines are grouped by their
    block/paragraph/line coordinates so reading order is preserved.
    """
    words_by_line: dict[tuple[int, int, int], list[tuple[str, float]]] = {}
    confidences: list[float] = []

    text_fields = data.get("text", [])
    conf_fields = data.get("conf", [])
    block_fields = data.get("block_num", [])
    par_fields = data.get("par_num", [])
    line_fields = data.get("line_num", [])

    for index, raw_word in enumerate(text_fields):
        if not raw_word or not str(raw_word).strip():
            continue
        try:
            confidence = float(conf_fields[index])
        except (TypeError, ValueError, IndexError):
            continue
        if confidence < WORD_CONFIDENCE_THRESHOLD:
            continue

        key = (
            int(block_fields[index]),
            int(par_fields[index]),
            int(line_fields[index]),
        )
        words_by_line.setdefault(key, []).append((str(raw_word), confidence))
        confidences.append(confidence)

    lines: list[str] = []
    for key in sorted(words_by_line):
        words = [word for word, _ in words_by_line[key]]
        lines.append(" ".join(words))

    average = round(sum(confidences) / len(confidences), 1) if confidences else 0.0
    return "\n".join(lines), average


def _join_hyphenated_lines(text: str) -> str:
    """Join words split across line breaks with a trailing hyphen (dehyphenation)."""
    lines = text.split("\n")
    joined: list[str] = []
    for line in lines:
        if joined and joined[-1].endswith("-"):
            # The previous line ended with a hyphen: drop it and attach this
            # line's content without a space.
            joined[-1] = joined[-1][:-1].rstrip() + line.strip()
        else:
            joined.append(line.rstrip())
    return "\n".join(joined)


def _join_orphan_characters(text: str) -> str:
    """Merge a single-character line with the line that follows it.

    OCR sometimes breaks a word so a lone character sits on its own line
    (e.g. ``"T\\nhe"`` -> ``"The"``). This is a best-effort heuristic:
    only merge when the continuation looks like the rest of the word.
    """
    lines = text.split("\n")
    joined: list[str] = []
    for line in lines:
        stripped = line.strip()
        if len(stripped) == 1 and stripped.isalpha() and stripped != "I":
            # Lone character: defer, in case the next line continues the word.
            joined.append(stripped)
        elif (
            joined
            and len(joined[-1].strip()) == 1
            and joined[-1].strip().isalpha()
            and joined[-1].strip() != "I"
            and stripped[:1].islower()
        ):
            # Previous line was a lone character and this line starts lowercase:
            # it is likely the rest of the word, so attach it.
            joined[-1] = (joined[-1].strip() + stripped).strip()
        else:
            joined.append(line)
    return "\n".join(joined)


# ─────────────────────────────────────────────────────────────
# OCR Pipeline
# ─────────────────────────────────────────────────────────────
class OcrPipeline:
    """Tesseract-based OCR for standalone images and scanned/image PDFs.

    Trigger conditions (00_IMPLEMENTATION_PLAN.md section 22.1):
    * File type is an image (PNG, JPG, TIFF, WEBP).
    * PDF is flagged as image-based (no extractable text layer).

    Degrades gracefully: when Tesseract or pytesseract is unavailable,
    ``is_available()`` returns ``False`` and the callers fall back to the
    ``pending_ocr`` document status instead of raising.
    """

    def __init__(self, language: str = "eng", tesseract_path: str = "") -> None:
        self.language = language
        self.tesseract_path = tesseract_path

    def is_available(self) -> bool:
        return _import_pytesseract() is not None and find_tesseract_executable(
            self.tesseract_path
        ) is not None

    def _require_pytesseract(self) -> Any:
        pytesseract = _import_pytesseract()
        if pytesseract is None:
            raise OcrUnavailableError(
                "pytesseract is not installed. Run: python install.py"
            )
        executable = find_tesseract_executable(self.tesseract_path)
        if executable is None:
            raise OcrUnavailableError(f"Tesseract OCR was not found. {INSTALL_HINT}")
        # pytesseract exposes tesseract_cmd on its submodule; be defensive in
        # case a vendored/custom wrapper exposes it directly on the module.
        command_module = getattr(pytesseract, "pytesseract", pytesseract)
        command_module.tesseract_cmd = executable
        return pytesseract

    def ocr_image(self, image_source: Path | "PILImage.Image", page_number: int = 1) -> OcrPage:
        """OCR a standalone image file or an in-memory PIL image."""
        from PIL import Image

        pytesseract = self._require_pytesseract()

        if isinstance(image_source, Path):
            with Image.open(image_source) as opened:
                image = opened.convert("RGB")
        else:
            image = image_source

        processed = _preprocess_image(image)
        config = f"--psm {PSM} --oem {OEM}"
        data = pytesseract.image_to_data(
            processed,
            lang=self.language,
            config=config,
            output_type=pytesseract.Output.DICT,
        )

        text, confidence = _words_to_text(data)
        text = _join_hyphenated_lines(text)
        text = _join_orphan_characters(text)

        warnings: list[str] = []
        if not text.strip():
            warnings.append(
                "OCR produced no readable text; the image may be blank or unreadable."
            )
        elif confidence < LOW_CONFIDENCE_THRESHOLD:
            warnings.append(LOW_OCR_QUALITY_WARNING)

        return OcrPage(
            page_number=page_number,
            text=text.strip(),
            confidence=confidence,
            warnings=warnings,
        )

    def ocr_pdf(self, pdf_path: Path) -> OcrResult:
        """Render each page of an image-based PDF to a 300 DPI bitmap and OCR it."""
        import fitz  # PyMuPDF
        from PIL import Image

        # Fail fast (before opening the document) if OCR is unavailable.
        self._require_pytesseract()

        pages: list[OcrPage] = []
        document_warnings: list[str] = []
        with fitz.open(pdf_path) as document:
            for index in range(document.page_count):
                page = document.load_page(index)
                pixmap = page.get_pixmap(dpi=300)
                image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                ocr_page = self.ocr_image(image, page_number=index + 1)
                pages.append(ocr_page)
                document_warnings.extend(ocr_page.warnings)

        return OcrResult(pages=pages, warnings=document_warnings)


OCRPipeline = OcrPipeline
