"""Importing a profile archive must not be able to exhaust memory or disk.

An export bundles every document a profile owns, so it is the one upload that
is legitimately large. It used to be read into memory whole, which made the
size limit a memory limit -- and any limit generous enough for a real export
was too generous to be a safe memory bound.

The archive is now streamed to disk and read from there, so memory no longer
scales with it. That moves the risk rather than removing it: a decompression
bomb that would previously have been bounded by the memory limit could now
fill the drive instead. These pin both halves.
"""

from __future__ import annotations

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "import-safety-data"))

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


def _post_archive(client: TestClient, payload: bytes, name: str = "profile.zip"):
    return client.post(
        "/api/v1/profiles/import",
        files={"file": (name, payload, "application/zip")},
    )


def _minimal_export(extra_files: dict[str, bytes] | None = None) -> bytes:
    """The smallest archive the importer accepts as a profile."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("profile.json", '{"name": "Imported", "profile_type": "Custom Learning"}')
        for path, content in (extra_files or {}).items():
            zf.writestr(path, content)
    return buf.getvalue()


# ── The archive still has to be a real archive ────────────────────────


def test_a_file_that_is_not_a_zip_is_refused_clearly(tmp_path, monkeypatch):
    """Regression: this used to escape as an unhandled 500.

    Picking the wrong file in a file dialog is an ordinary mistake and should
    produce a sentence explaining it, not a server error.
    """
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        response = _post_archive(client, b"this is plainly not a zip archive")

        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "INVALID_ZIP"
        assert "not a valid ZIP" in error["message"]


def test_a_zip_without_profile_json_is_refused(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("something-else.txt", b"nope")

    with TestClient(app) as client:
        response = _post_archive(client, buf.getvalue())

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_ZIP"


# ── Decompression bombs ───────────────────────────────────────────────


def test_a_decompression_bomb_is_refused(tmp_path, monkeypatch):
    """50MB of zeroes compresses to about 48KB -- a thousandfold expansion.

    The archive is small enough to pass any size limit, and was previously
    extracted in full. Declared sizes are read from the archive directory, so
    this is refused without decompressing anything.

    The cap is set to 1MB here (giving a 10MB extraction budget) so a bomb
    that fits in a test can exceed it; at the shipped default the budget is
    5GB and the bomb would have to be correspondingly larger.
    """
    monkeypatch.setenv("ATLAS_MAX_IMPORT_SIZE_MB", "1")
    app = _make_app(tmp_path, monkeypatch)
    bomb = _minimal_export({"files/documents/raw/bomb.bin": b"\0" * (50 * 1024 * 1024)})

    # The premise of the test: it really is small enough to slip through.
    assert len(bomb) < 1024 * 1024, f"bomb archive was {len(bomb)} bytes"

    with TestClient(app) as client:
        response = _post_archive(client, bomb)

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_ZIP"
        # Nothing was created before it was refused.
        assert client.get("/api/v1/profiles").json()["data"] == []


def test_a_bomb_is_refused_before_anything_is_written(tmp_path, monkeypatch):
    """The check runs on the archive directory, ahead of any side effect.

    A bomb caught mid-extraction would already have created a profile and
    written part of the payload.
    """
    monkeypatch.setenv("ATLAS_MAX_IMPORT_SIZE_MB", "1")
    app = _make_app(tmp_path, monkeypatch)
    data_dir = tmp_path / "import-safety-data"
    bomb = _minimal_export({"files/documents/raw/bomb.bin": b"\0" * (80 * 1024 * 1024)})

    with TestClient(app) as client:
        before = sum(1 for _ in data_dir.rglob("*")) if data_dir.exists() else 0
        assert _post_archive(client, bomb).status_code == 422
        after = sum(1 for _ in data_dir.rglob("*")) if data_dir.exists() else 0

    assert after == before, "the refused import left files behind"


def test_a_highly_compressible_real_export_is_accepted(tmp_path, monkeypatch):
    """The guard must not reject real archives, and nearly did.

    A first attempt bounded expansion as a *ratio* against the archive, which
    rejects exactly the most legitimate exports: repeated prose compresses
    about 40x and a 1,300-node roadmap's JSON about 22x, so a real profile
    looks far more "bomb-like" by ratio than a modest bomb does. The bound is
    on total bytes written instead, which is the thing that threatens the
    disk.

    Text and JSON are used deliberately -- random bytes would not compress
    and would make this pass without testing anything.
    """
    app = _make_app(tmp_path, monkeypatch)
    prose = ("Newton's second law relates force, mass and acceleration. " * 200).encode()
    roadmap = json.dumps(
        [{
            "title": "Roadmap",
            "nodes": [
                {"id": f"n{i}", "title": f"Topic {i}", "description": "A study topic.",
                 "node_type": "topic", "status": "not_started", "order_index": i}
                for i in range(1300)
            ],
        }]
    ).encode()

    archive = _minimal_export(
        {f"files/documents/raw/notes-{i}.txt": prose for i in range(5)}
        | {"roadmaps.json": roadmap}
    )

    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        declared = sum(i.file_size for i in zf.infolist())
    ratio = declared / len(archive)
    assert ratio > 15, f"fixture is not compressible enough to be a real test (ratio {ratio:.0f}x)"

    with TestClient(app) as client:
        response = _post_archive(client, archive)
        assert response.status_code == 201, response.text
        assert response.json()["data"]["name"] == "Imported"


def test_a_real_import_leaves_no_temporary_file_behind(tmp_path, monkeypatch):
    """End to end, through the endpoint, on the real code path.

    Windows will not delete a file while a handle is open, so a ZipFile that
    outlived the archive would fail the cleanup silently on the platform most
    of Atlas's users are on. Testing the helper in isolation would not catch
    that -- only opening the archive the way the importer does will.
    """
    import tempfile
    from pathlib import Path

    app = _make_app(tmp_path, monkeypatch)
    temp_root = Path(tempfile.gettempdir())
    before = set(temp_root.glob("atlas-upload-*"))

    with TestClient(app) as client:
        assert _post_archive(client, _minimal_export()).status_code == 201
        # And on the failure path, where the handle is dropped by an exception.
        assert _post_archive(client, b"not a zip at all").status_code == 422

    assert set(temp_root.glob("atlas-upload-*")) == before


# ── Export, the mirror of the same problem ────────────────────────────


def test_export_leaves_no_archive_behind(tmp_path, monkeypatch):
    """The export is staged on disk and deleted once the response is sent.

    Held in memory the archive was resident *and* copied by `getvalue()`, so
    exporting peaked at roughly twice its size. Staging it on disk fixes that
    but introduces a file that has to be cleaned up.
    """
    import tempfile
    from pathlib import Path

    app = _make_app(tmp_path, monkeypatch)
    temp_root = Path(tempfile.gettempdir())
    before = set(temp_root.glob("atlas-export-*"))

    with TestClient(app) as client:
        pid = client.post(
            "/api/v1/profiles",
            json={"name": "Exportable", "profile_type": "Custom Learning"},
        ).json()["data"]["id"]

        response = client.post(f"/api/v1/profiles/{pid}/export")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        assert "attachment" in response.headers["content-disposition"]
        # The bytes really are a usable archive, not an empty file.
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            assert "profile.json" in zf.namelist()

    assert set(temp_root.glob("atlas-export-*")) == before


def test_a_stale_export_is_swept_but_a_fresh_one_is_not(tmp_path, monkeypatch):
    """Starlette skips the cleanup task when a client disconnects mid-download.

    Rather than leak one archive per cancelled download forever, each export
    clears out anything older than an hour. A concurrent export must survive
    that, so only genuinely old files are removed.
    """
    import os
    import tempfile
    import time
    from pathlib import Path

    from app.services.profile_service import _STALE_EXPORT_SECONDS, _sweep_stale_exports

    temp_root = Path(tempfile.gettempdir())
    stale = temp_root / "atlas-export-stale-test.zip"
    fresh = temp_root / "atlas-export-fresh-test.zip"
    stale.write_bytes(b"old")
    fresh.write_bytes(b"new")
    old_time = time.time() - _STALE_EXPORT_SECONDS - 60
    os.utime(stale, (old_time, old_time))

    try:
        _sweep_stale_exports()
        assert not stale.exists(), "an abandoned export was not swept"
        assert fresh.exists(), "the sweep removed an export that was still in use"
    finally:
        stale.unlink(missing_ok=True)
        fresh.unlink(missing_ok=True)


def test_export_import_round_trip_still_works_end_to_end(tmp_path, monkeypatch):
    """Both halves changed; this is the check that they still meet."""
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        pid = client.post(
            "/api/v1/profiles",
            json={"name": "RoundTrip", "profile_type": "Custom Learning"},
        ).json()["data"]["id"]
        client.post(
            f"/api/v1/profiles/{pid}/documents",
            files={"file": ("notes.txt", b"Force equals mass times acceleration. " * 50, "text/plain")},
        )

        archive = client.post(f"/api/v1/profiles/{pid}/export").content
        imported = client.post(
            "/api/v1/profiles/import",
            files={"file": ("profile.zip", archive, "application/zip")},
        )

        assert imported.status_code == 201
        new_id = imported.json()["data"]["id"]
        assert new_id != pid
        assert len(client.get(f"/api/v1/profiles/{new_id}/documents").json()["data"]) == 1


# ── The size limit still applies, and is no longer a memory bound ─────


def test_the_archive_size_limit_still_applies(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_MAX_IMPORT_SIZE_MB", "1")
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        response = _post_archive(client, b"x" * (2 * 1024 * 1024))

        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert error["details"] == {"max_import_size_mb": 1}


@pytest.mark.asyncio
async def test_the_temp_file_is_removed_on_success_and_on_failure(tmp_path):
    """The archive lands in a temp file, which must not accumulate.

    An import is the largest thing Atlas writes; leaking one copy per attempt
    would quietly fill the disk over time.
    """
    import tempfile
    from pathlib import Path

    from app.exceptions import AtlasError
    from app.utils.file_utils import upload_to_temp_file

    class _Upload:
        def __init__(self, data: bytes):
            self._data, self._pos = data, 0

        async def read(self, size: int) -> bytes:
            chunk = self._data[self._pos : self._pos + size]
            self._pos += len(chunk)
            return chunk

    temp_root = Path(tempfile.gettempdir())

    def atlas_temp_files() -> set[Path]:
        return set(temp_root.glob("atlas-upload-*"))

    before = atlas_temp_files()

    # Success: the path exists inside the block and is gone after it.
    async with upload_to_temp_file(_Upload(b"hello"), 1000, error_message="x") as path:
        assert path.exists()
        assert path.read_bytes() == b"hello"
        inside = path
    assert not inside.exists()

    # Failure: the limit trips mid-write, and cleanup still happens.
    with pytest.raises(AtlasError):
        async with upload_to_temp_file(
            _Upload(b"y" * 5000), 100, error_message="too big", chunk_size=50
        ):
            pass

    assert atlas_temp_files() == before, "a temporary upload file was left behind"
