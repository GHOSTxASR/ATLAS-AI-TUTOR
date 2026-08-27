from __future__ import annotations

import io
import zipfile
from fastapi.testclient import TestClient


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-export-data"))

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


def test_profile_export_and_import_lifecycle(tmp_path, monkeypatch):
    """
    Validates full profile export and import pipeline:
    - Creates profile and records (memory, note)
    - Exports profile as ZIP archive
    - Imports ZIP into new profile
    - Verifies imported profile and restored records
    """
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        # 1. Create Profile
        p_resp = client.post("/api/v1/profiles", json={"name": "Exportable Learner", "profile_type": "JEE"})
        assert p_resp.status_code == 201
        profile_id = p_resp.json()["data"]["id"]

        # 2. Add Memory Record
        mem_resp = client.post(
            f"/api/v1/profiles/{profile_id}/memory",
            json={
                "category": "strength",
                "subject": "Integration",
                "content": "Mastered integration by parts.",
                "confidence": 0.9,
            },
        )
        assert mem_resp.status_code == 201

        # 3. Add Note
        note_resp = client.post(
            f"/api/v1/profiles/{profile_id}/notes",
            json={"title": "Calculus Notes", "content": "Formula sheet for integrals.", "note_type": "lesson_note"},
        )
        assert note_resp.status_code == 201

        # 3b. Add a chat session and message to verify domain records round-trip
        session_resp = client.post(
            f"/api/v1/profiles/{profile_id}/sessions",
            json={"title": "Imported Chat"},
        )
        assert session_resp.status_code == 201
        session_id = session_resp.json()["data"]["id"]
        message_resp = client.post(
            f"/api/v1/profiles/{profile_id}/sessions/{session_id}/messages",
            json={"role": "user", "content": "Remember this message."},
        )
        assert message_resp.status_code == 201

        # 4. Export Profile ZIP
        export_resp = client.post(f"/api/v1/profiles/{profile_id}/export")
        assert export_resp.status_code == 200
        assert export_resp.headers["content-type"] == "application/zip"
        zip_bytes = export_resp.content
        assert len(zip_bytes) > 0
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            assert "manifest.json" in archive.namelist()
            assert "chats.json" in archive.namelist()

        # 5. Import Profile ZIP
        import_resp = client.post(
            "/api/v1/profiles/import",
            files={"file": ("profile_backup.zip", io.BytesIO(zip_bytes), "application/zip")},
        )
        assert import_resp.status_code == 201
        imported_id = import_resp.json()["data"]["id"]
        assert imported_id != profile_id

        # 6. Verify restored memory in imported profile
        mems_resp = client.get(f"/api/v1/profiles/{imported_id}/memory")
        assert mems_resp.status_code == 200
        mems = mems_resp.json()["data"]
        assert len(mems) >= 1
        assert any("integration" in m["content"].lower() for m in mems)

        # 7. Verify chat records are restored with their messages
        sessions_resp = client.get(f"/api/v1/profiles/{imported_id}/sessions")
        assert sessions_resp.status_code == 200
        imported_sessions = sessions_resp.json()["data"]
        assert len(imported_sessions) == 1
        imported_session = client.get(
            f"/api/v1/profiles/{imported_id}/sessions/{imported_sessions[0]['id']}"
        )
        assert imported_session.status_code == 200
        assert imported_session.json()["data"]["messages"][0]["content"] == "Remember this message."


def test_imported_documents_are_reindexed(tmp_path, monkeypatch):
    """An imported profile's documents must become searchable again.

    Regression: documents were restored with status "indexed" but the archive
    carries no vectors and the new profile has its own collections, so their
    content was permanently invisible to retrieval.
    """
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        source_id = client.post(
            "/api/v1/profiles",
            json={"name": "Export Source", "profile_type": "JEE"},
        ).json()["data"]["id"]

        upload = client.post(
            f"/api/v1/profiles/{source_id}/documents",
            files={
                "file": (
                    "entropy.txt",
                    io.BytesIO(b"Entropy of an isolated system never decreases. " * 20),
                    "text/plain",
                )
            },
        )
        assert upload.status_code == 201
        original_id = upload.json()["data"]["id"]
        original = client.get(
            f"/api/v1/profiles/{source_id}/documents/{original_id}"
        ).json()["data"]
        assert original["status"] == "indexed"

        archive = client.post(f"/api/v1/profiles/{source_id}/export")
        assert archive.status_code == 200

        imported_id = client.post(
            "/api/v1/profiles/import",
            files={"file": ("profile.zip", io.BytesIO(archive.content), "application/zip")},
        ).json()["data"]["id"]

        documents = client.get(f"/api/v1/profiles/{imported_id}/documents").json()["data"]
        assert len(documents) == 1
        restored = documents[0]

    # The background re-index runs before TestClient returns, so by now the
    # document must be indexed under the *new* profile - not merely labelled so.
    assert restored["status"] == "indexed"
    assert restored["chunk_count"] >= 1
    assert restored["id"] != original_id


def test_import_over_the_configured_limit_is_rejected(tmp_path, monkeypatch):
    """The router-level size check on /profiles/import, wired to its own setting.

    A profile export bundles every document a profile has, so it gets a
    distinct, larger cap than a single document upload rather than reusing
    max_file_size_mb or being left unbounded.
    """
    monkeypatch.setenv("ATLAS_MAX_IMPORT_SIZE_MB", "1")
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        oversized = b"x" * (2 * 1024 * 1024)  # 2MB against a 1MB cap
        response = client.post(
            "/api/v1/profiles/import",
            files={"file": ("big.zip", oversized, "application/zip")},
        )

        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert "1MB" in error["message"]
        assert error["details"] == {"max_import_size_mb": 1}
