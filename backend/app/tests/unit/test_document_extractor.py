from pathlib import Path

from app.pipelines.document_extractor import DocumentExtractor, detect_file_type


def test_detect_file_type_by_magic_bytes():
    assert detect_file_type("whatever.bin", b"%PDF-1.7 rest of file") == "pdf"
    assert detect_file_type("whatever.bin", b"\x89PNG\r\n\x1a\nrest") == "image"
    assert detect_file_type("whatever.bin", b"\xff\xd8\xffrest") == "image"


def test_detect_file_type_falls_back_to_extension():
    # No recognizable magic bytes, but a supported extension.
    assert detect_file_type("notes.txt", b"plain text content") == "txt"


def test_detect_file_type_rejects_unknown_binary():
    assert detect_file_type("app.exe", b"\x4d\x5a\x90\x00\x03\x00\x00\x00") is None


def test_extract_txt(tmp_path: Path):
    text = "Recursion calls itself until a base case is reached."
    file_path = tmp_path / "sample.txt"
    file_path.write_text(text, encoding="utf-8")

    result = DocumentExtractor().extract(file_path, "txt")

    assert result.status == "extracted"
    assert result.word_count == len(text.split())
    assert "Recursion" in result.text


def test_extract_docx(tmp_path: Path):
    import docx

    file_path = tmp_path / "sample.docx"
    document = docx.Document()
    document.add_paragraph("Chapter one covers arrays and linked lists.")
    document.save(str(file_path))

    result = DocumentExtractor().extract(file_path, "docx")

    assert result.status == "extracted"
    assert "arrays" in result.text
    assert result.word_count and result.word_count > 0


def test_extract_pdf_text_based(tmp_path: Path):
    import fitz

    file_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Binary search trees keep elements sorted.")
    doc.save(str(file_path))
    doc.close()

    result = DocumentExtractor().extract(file_path, "pdf")

    assert result.status == "extracted"
    assert result.page_count == 1
    assert result.is_image_pdf is False


def test_extract_image_defers_to_ocr_milestone(tmp_path: Path):
    from PIL import Image

    file_path = tmp_path / "sample.png"
    Image.new("RGB", (10, 10), color="white").save(file_path)

    result = DocumentExtractor().extract(file_path, "image")

    assert result.status == "pending_ocr"
    assert result.text == ""
    assert result.error_message is not None
