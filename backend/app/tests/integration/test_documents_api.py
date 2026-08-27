import io

from fastapi.testclient import TestClient

from app.tests.conftest import uploaded_document
from PIL import Image


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-data"))

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


def _create_profile(client: TestClient) -> str:
    response = client.post(
        "/api/v1/profiles",
        json={"name": "Doc Test Profile", "profile_type": "Custom Learning"},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_upload_list_get_delete_txt_document(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _create_profile(client)

        content = b"Recursion is when a function calls itself to solve a smaller subproblem."
        upload = client.post(
            f"/api/v1/profiles/{profile_id}/documents",
            files={"file": ("notes.txt", content, "text/plain")},
        )
        assert upload.status_code == 201
        document = upload.json()["data"]
        assert document["filename"] == "notes.txt"
        assert document["file_type"] == "txt"
        # Upload returns immediately; the pipeline settles the status after.
        assert document["status"] == "pending"
        document = uploaded_document(client, profile_id, document["id"])
        assert document["status"] in ("extracted", "indexed")
        assert document["word_count"] == len(content.split())
        assert document["error_message"] is None

        listing = client.get(f"/api/v1/profiles/{profile_id}/documents")
        assert listing.status_code == 200
        assert len(listing.json()["data"]) == 1

        detail = client.get(f"/api/v1/profiles/{profile_id}/documents/{document['id']}")
        assert detail.status_code == 200
        assert detail.json()["data"]["id"] == document["id"]

        status_resp = client.get(f"/api/v1/profiles/{profile_id}/documents/{document['id']}/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["data"]["status"] in ("extracted", "indexed")

        delete_resp = client.delete(f"/api/v1/profiles/{profile_id}/documents/{document['id']}")
        assert delete_resp.status_code == 200

        after_delete = client.get(f"/api/v1/profiles/{profile_id}/documents/{document['id']}")
        assert after_delete.status_code == 404


def test_duplicate_upload_is_rejected(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _create_profile(client)
        content = b"Same bytes every time."

        first = client.post(
            f"/api/v1/profiles/{profile_id}/documents",
            files={"file": ("a.txt", content, "text/plain")},
        )
        assert first.status_code == 201

        second = client.post(
            f"/api/v1/profiles/{profile_id}/documents",
            files={"file": ("b.txt", content, "text/plain")},
        )
        assert second.status_code == 409
        body = second.json()
        assert body["error"]["code"] == "CONFLICT"


def test_unsupported_file_type_is_rejected(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _create_profile(client)

        response = client.post(
            f"/api/v1/profiles/{profile_id}/documents",
            files={"file": ("app.exe", b"\x4d\x5a\x90\x00\x03\x00\x00\x00", "application/octet-stream")},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_upload_requires_existing_profile(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/profiles/does-not-exist/documents",
            files={"file": ("notes.txt", b"hello world", "text/plain")},
        )
        assert response.status_code == 404


def test_pdf_and_docx_extraction(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _create_profile(client)

        fitz = __import__("fitz")
        pdf_doc = fitz.open()
        page = pdf_doc.new_page()
        page.insert_text((72, 72), "Hello Atlas PDF content for extraction testing.")
        pdf_bytes = pdf_doc.tobytes()
        pdf_doc.close()

        pdf_upload = client.post(
            f"/api/v1/profiles/{profile_id}/documents",
            files={"file": ("syllabus.pdf", pdf_bytes, "application/pdf")},
        )
        assert pdf_upload.status_code == 201
        pdf_document = pdf_upload.json()["data"]
        assert pdf_document["file_type"] == "pdf"
        pdf_document = uploaded_document(client, profile_id, pdf_document["id"])
        assert pdf_document["status"] in ("extracted", "indexed")
        assert pdf_document["page_count"] == 1
        assert pdf_document["word_count"] and pdf_document["word_count"] > 0

        docx_module = __import__("docx")
        word_doc = docx_module.Document()
        word_doc.add_paragraph("Hello Atlas DOCX content for extraction testing.")
        buffer = io.BytesIO()
        word_doc.save(buffer)

        docx_upload = client.post(
            f"/api/v1/profiles/{profile_id}/documents",
            files={
                "file": (
                    "chapter1.docx",
                    buffer.getvalue(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        assert docx_upload.status_code == 201
        docx_document = docx_upload.json()["data"]
        assert docx_document["file_type"] == "docx"
        docx_document = uploaded_document(client, profile_id, docx_document["id"])
        assert docx_document["status"] in ("extracted", "indexed")
        assert docx_document["word_count"] and docx_document["word_count"] > 0


class _FakeOutput:
    DICT = "dict"


def _fake_image_to_data(image, lang=None, config=None, output_type=None):
    return {
        "level": [5, 5, 5],
        "page_num": [1, 1, 1],
        "block_num": [1, 1, 1],
        "par_num": [1, 1, 1],
        "line_num": [1, 1, 1],
        "word_num": [1, 2, 3],
        "left": [0, 10, 20],
        "top": [0, 0, 0],
        "width": [10, 10, 10],
        "height": [10, 10, 10],
        "conf": [95.0, 90.0, -1.0],
        "text": ["Scanned", "notes", ""],
    }


class _FakePytesseractSubmodule:
    tesseract_cmd: str = ""


class _FakePytesseract:
    Output = _FakeOutput
    pytesseract = _FakePytesseractSubmodule()

    def image_to_data(self, image, lang=None, config=None, output_type=None):
        return _fake_image_to_data(image, lang, config, output_type)


def test_image_upload_extracts_text_with_ocr(tmp_path, monkeypatch):
    """Milestone 09: an image upload runs the OCR pipeline and lands in 'extracted' or 'indexed'."""
    monkeypatch.setattr(
        "app.pipelines.ocr_pipeline._import_pytesseract", lambda: _FakePytesseract()
    )
    monkeypatch.setattr(
        "app.pipelines.ocr_pipeline.find_tesseract_executable",
        lambda configured_path="": "C:/fake/tesseract.exe",
    )

    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _create_profile(client)

        buffer = io.BytesIO()
        Image.new("RGB", (120, 40), color="white").save(buffer, format="PNG")

        upload = client.post(
            f"/api/v1/profiles/{profile_id}/documents",
            files={"file": ("scan.png", buffer.getvalue(), "image/png")},
        )
        assert upload.status_code == 201
        document = upload.json()["data"]

        assert document["file_type"] == "image"
        # Upload returns immediately; the pipeline settles the status after.
        assert document["status"] == "pending"
        document = uploaded_document(client, profile_id, document["id"])
        assert document["status"] in ("extracted", "indexed")
        assert document["word_count"] == 2
        assert document["error_message"] is None

        # The OCR text must be written to the extracted-text file on disk.
        extracted_path = (
            tmp_path
            / "atlas-data"
            / "profiles"
            / profile_id
            / "documents"
            / "extracted"
            / f"{document['id']}.txt"
        )
        assert extracted_path.exists()
        assert extracted_path.read_text(encoding="utf-8").strip() == "Scanned notes"


def test_image_upload_without_ocr_stays_pending(tmp_path, monkeypatch):
    """When Tesseract is missing, images degrade to pending_ocr with a clear message."""
    monkeypatch.setattr(
        "app.pipelines.ocr_pipeline._import_pytesseract", lambda: None
    )

    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _create_profile(client)

        buffer = io.BytesIO()
        Image.new("RGB", (120, 40), color="white").save(buffer, format="PNG")

        upload = client.post(
            f"/api/v1/profiles/{profile_id}/documents",
            files={"file": ("scan.png", buffer.getvalue(), "image/png")},
        )
        assert upload.status_code == 201
        document = upload.json()["data"]

        assert document["file_type"] == "image"
        document = uploaded_document(client, profile_id, document["id"])
        assert document["status"] == "pending_ocr"
        assert document["error_message"] is not None
        assert "Tesseract" in document["error_message"]


def test_upload_returns_before_extraction_runs(tmp_path, monkeypatch):
    """Upload must not block on extraction.

    Regression: the whole pipeline (extraction, OCR, chunking, embedding) ran
    inside the request, so a large scanned PDF held the connection open for
    minutes and timed out in the browser.
    """
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "async-upload-data"))

    from app.config import get_settings
    from app.services.ingestion_service import IngestionService

    get_settings.cache_clear()
    app = _make_app(tmp_path, monkeypatch)

    extraction_calls: list[str] = []
    original = IngestionService.process_document

    async def _tracked(self, document):
        extraction_calls.append(document.id)
        return await original(self, document)

    monkeypatch.setattr(IngestionService, "process_document", _tracked)

    with TestClient(app) as client:
        profile_id = _create_profile(client)
        upload = client.post(
            f"/api/v1/profiles/{profile_id}/documents",
            files={"file": ("async.txt", io.BytesIO(b"Some study material." * 50), "text/plain")},
        )
        assert upload.status_code == 201
        document = upload.json()["data"]

        # The response body is built before the background task runs.
        assert document["status"] == "pending"
        assert document["chunk_count"] == 0

        # ...and the background task then does the work.
        settled = uploaded_document(client, profile_id, document["id"])
        assert settled["status"] in ("extracted", "indexed")
        assert extraction_calls == [document["id"]]


def test_upload_over_the_configured_limit_is_rejected(tmp_path, monkeypatch):
    """The router-level size check, wired end to end through the real settings."""
    monkeypatch.setenv("ATLAS_MAX_FILE_SIZE_MB", "1")
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _create_profile(client)

        oversized = b"x" * (2 * 1024 * 1024)  # 2MB against a 1MB cap
        response = client.post(
            f"/api/v1/profiles/{profile_id}/documents",
            files={"file": ("big.txt", oversized, "text/plain")},
        )

        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert "1MB" in error["message"]
        assert error["details"] == {"max_file_size_mb": 1}
