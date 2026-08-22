from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import chardet

from app.pipelines.ocr_pipeline import OcrPipeline

SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "txt",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".gif": "image",
    ".bmp": "image",
    ".tiff": "image",
    ".tif": "image",
}

# Magic-byte signatures used to verify the browser-supplied MIME type/extension.
_MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    (b"%PDF-", "pdf"),
    (b"PK\x03\x04", "docx"),  # DOCX is a zip archive; extension disambiguates from other zip formats.
    (b"\x89PNG\r\n\x1a\n", "image"),
    (b"\xff\xd8\xff", "image"),  # JPEG
    (b"GIF87a", "image"),
    (b"GIF89a", "image"),
    (b"BM", "image"),
    (b"II*\x00", "image"),  # TIFF little-endian
    (b"MM\x00*", "image"),  # TIFF big-endian
    (b"RIFF", "image"),  # WEBP (RIFF....WEBP)
]


@dataclass
class PageResult:
    page_number: int
    text: str
    ocr_used: bool = False
    ocr_confidence: float | None = None


@dataclass
class ExtractionResult:
    text: str
    pages: list[PageResult] = field(default_factory=list)
    page_count: int | None = None
    word_count: int | None = None
    detected_type: str = ""
    is_image_pdf: bool = False
    warnings: list[str] = field(default_factory=list)
    status: str = "extracted"  # "extracted" | "pending_ocr" | "error"
    error_message: str | None = None


def detect_file_type(filename: str, content: bytes) -> str | None:
    """Best-effort file type detection using magic bytes with an extension fallback.

    Returns one of "pdf", "docx", "txt", "image", or None if unrecognized.
    Browser-supplied MIME types are never trusted (see 17_SECURITY_AND_PRIVACY.md).
    """
    header = content[:16]
    for signature, file_type in _MAGIC_SIGNATURES:
        if header.startswith(signature):
            return file_type

    suffix = Path(filename).suffix.lower()
    if suffix in SUPPORTED_EXTENSIONS:
        return SUPPORTED_EXTENSIONS[suffix]

    # No signature match and unknown extension: fall back to a crude text sniff test.
    try:
        content[:4096].decode("utf-8")
        return "txt"
    except UnicodeDecodeError:
        return None


class DocumentExtractor:
    """Extracts text and metadata from uploaded documents.

    Supports text-based PDF (PyMuPDF), DOCX (python-docx), TXT (chardet
    encoding detection), and — when an ``OcrPipeline`` is provided and
    Tesseract is available — images and scanned/image PDFs via OCR.
    Without OCR, images and scanned PDFs land in ``pending_ocr`` status.
    """

    def __init__(self, ocr: OcrPipeline | None = None) -> None:
        self.ocr = ocr

    def extract(self, file_path: Path, file_type: str) -> ExtractionResult:
        try:
            if file_type == "pdf":
                return self._extract_pdf(file_path)
            if file_type == "docx":
                return self._extract_docx(file_path)
            if file_type == "txt":
                return self._extract_txt(file_path)
            if file_type == "image":
                return self._describe_image(file_path)
        except Exception as exc:  # noqa: BLE001 - isolate per-document failures
            return ExtractionResult(
                text="",
                detected_type=file_type,
                status="error",
                error_message=f"Extraction failed: {exc}",
                warnings=[str(exc)],
            )
        return ExtractionResult(
            text="",
            detected_type=file_type,
            status="error",
            error_message=f"Unsupported file type: {file_type}",
        )

    def _extract_pdf(self, file_path: Path) -> ExtractionResult:
        import fitz  # PyMuPDF

        pages: list[PageResult] = []
        warnings: list[str] = []
        has_any_text = False

        try:
            doc = fitz.open(file_path)
        except Exception as exc:
            message = str(exc).lower()
            if "password" in message or "encrypt" in message:
                return ExtractionResult(
                    text="",
                    detected_type="pdf",
                    status="error",
                    error_message="Password protected PDF",
                )
            raise

        try:
            if doc.is_encrypted:
                return ExtractionResult(
                    text="",
                    detected_type="pdf",
                    status="error",
                    error_message="Password protected PDF",
                )

            page_count = doc.page_count
            for index in range(page_count):
                page = doc[index]
                page_text = cast(str, page.get_text("text")) or ""
                if page_text.strip():
                    has_any_text = True
                pages.append(PageResult(page_number=index + 1, text=page_text))
        finally:
            doc.close()

        full_text = "\n\n".join(p.text for p in pages)
        is_image_pdf = page_count > 0 and not has_any_text

        if is_image_pdf:
            if self.ocr is not None and self.ocr.is_available():
                ocr_result = self.ocr.ocr_pdf(file_path)
                ocr_pages = [
                    PageResult(
                        page_number=page.page_number,
                        text=page.text,
                        ocr_used=True,
                        ocr_confidence=page.confidence,
                    )
                    for page in ocr_result.pages
                ]
                full_text = ocr_result.text
                if full_text:
                    return ExtractionResult(
                        text=full_text,
                        pages=ocr_pages,
                        page_count=page_count,
                        word_count=len(full_text.split()),
                        detected_type="pdf",
                        is_image_pdf=True,
                        warnings=list(ocr_result.warnings),
                        status="extracted",
                    )
                return ExtractionResult(
                    text="",
                    pages=ocr_pages,
                    page_count=page_count,
                    word_count=0,
                    detected_type="pdf",
                    is_image_pdf=True,
                    warnings=list(ocr_result.warnings),
                    status="error",
                    error_message=(
                        "OCR produced no readable text. "
                        "The document may be blank or unreadable."
                    ),
                )

            warnings.append(
                "No extractable text found; this looks like a scanned/image PDF. "
                "OCR is unavailable (Tesseract not found). "
                "Install Tesseract OCR to enable scanned PDF processing."
            )
            return ExtractionResult(
                text="",
                pages=pages,
                page_count=page_count,
                word_count=0,
                detected_type="pdf",
                is_image_pdf=True,
                warnings=warnings,
                status="pending_ocr",
                error_message=(
                    "Scanned/image PDF: OCR unavailable. "
                    "Install Tesseract OCR and retry."
                ),
            )

        return ExtractionResult(
            text=full_text,
            pages=pages,
            page_count=page_count,
            word_count=len(full_text.split()),
            detected_type="pdf",
            is_image_pdf=False,
            warnings=warnings,
            status="extracted",
        )

    def _extract_docx(self, file_path: Path) -> ExtractionResult:
        import docx  # python-docx

        document = docx.Document(str(file_path))
        parts: list[str] = []
        for paragraph in document.paragraphs:
            if paragraph.text.strip():
                parts.append(paragraph.text)
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    parts.append(" | ".join(cells))

        full_text = "\n".join(parts)
        return ExtractionResult(
            text=full_text,
            pages=[PageResult(page_number=1, text=full_text)],
            page_count=None,
            word_count=len(full_text.split()),
            detected_type="docx",
            status="extracted",
        )

    def _extract_txt(self, file_path: Path) -> ExtractionResult:
        raw = file_path.read_bytes()
        encoding = "utf-8"
        if raw:
            detected = chardet.detect(raw)
            encoding = detected.get("encoding") or "utf-8"

        warnings: list[str] = []
        try:
            text = raw.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            warnings.append(f"Could not decode as {encoding}; falling back to latin-1.")
            text = raw.decode("latin-1", errors="replace")

        return ExtractionResult(
            text=text,
            pages=[PageResult(page_number=1, text=text)],
            page_count=None,
            word_count=len(text.split()),
            detected_type="txt",
            warnings=warnings,
            status="extracted",
        )

    def _describe_image(self, file_path: Path) -> ExtractionResult:
        if self.ocr is not None and self.ocr.is_available():
            result = self.ocr.ocr_image(file_path, page_number=1)
            if result.text:
                return ExtractionResult(
                    text=result.text,
                    pages=[
                        PageResult(
                            page_number=1,
                            text=result.text,
                            ocr_used=True,
                            ocr_confidence=result.confidence,
                        )
                    ],
                    page_count=1,
                    word_count=len(result.text.split()),
                    detected_type="image",
                    status="extracted",
                    warnings=list(result.warnings),
                )
            return ExtractionResult(
                text="",
                pages=[],
                page_count=1,
                word_count=0,
                detected_type="image",
                status="error",
                error_message=(
                    "OCR produced no readable text. The image may be blank or unreadable."
                ),
                warnings=list(result.warnings),
            )

        metadata_note = "image"
        try:
            from PIL import Image

            with Image.open(file_path) as img:
                metadata_note = f"{img.format} image, {img.width}x{img.height}px"
        except Exception:
            pass

        return ExtractionResult(
            text="",
            pages=[],
            page_count=1,
            word_count=0,
            detected_type="image",
            status="pending_ocr",
            error_message=(
                "Image text extraction requires OCR, which is unavailable "
                "(Tesseract not found). Install Tesseract OCR and retry."
            ),
            warnings=[metadata_note],
        )
