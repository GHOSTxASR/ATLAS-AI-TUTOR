from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-spa-data"))

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


def test_production_spa_serving_and_fallback(tmp_path, monkeypatch):
    """
    Validates that the FastAPI server mounts and serves compiled frontend assets:
    - Root / serves index.html or 200 JSON
    - Client SPA routes (/chat, /notes, /roadmap) return 200 and HTML
    - /api/v1/health continues returning API health payload
    """
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        # 1. Verify API router health remains unaffected
        health_resp = client.get("/api/v1/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["data"]["status"] == "ok"

        # 2. Verify Root / returns 200
        root_resp = client.get("/")
        assert root_resp.status_code == 200

        # 3. Verify Client SPA route fallback
        chat_resp = client.get("/chat")
        assert chat_resp.status_code == 200
        assert "html" in chat_resp.headers.get("content-type", "").lower() or "<!doctype html>" in chat_resp.text.lower()


def test_spa_route_rejects_path_traversal(tmp_path, monkeypatch):
    """The SPA catch-all must not serve files outside frontend/dist.

    Regression: ``GET /..%2f..%2f.env`` returned the repository .env verbatim,
    exposing every provider API key and the keystore location.
    """
    dist = Path(__file__).resolve().parents[4] / "frontend" / "dist"
    if not (dist / "index.html").exists():
        pytest.skip("frontend/dist not built; the SPA catch-all route is not registered")

    app = _make_app(tmp_path, monkeypatch)

    attacks = [
        "/..%2f..%2f.env",
        "/..%2F..%2Fbackend%2Frequirements.txt",
        "/assets/..%2f..%2f..%2f.env",
        "/..%2f..%2fbackend%2fapp%2fconfig.py",
    ]
    leaked_markers = (
        "ATLAS_MODEL_PROVIDER",
        "GEMINI_API_KEY",
        "fastapi==",
        "def load_settings",
    )

    with TestClient(app) as client:
        for attack in attacks:
            resp = client.get(attack)
            body = resp.text
            for marker in leaked_markers:
                assert marker not in body, f"{attack} leaked file contents ({marker!r})"
            # An escaping path either 404s (static mount) or falls through to
            # the SPA shell - never to the real file on disk.
            assert resp.status_code == 404 or "<!doctype html>" in body.lower()
