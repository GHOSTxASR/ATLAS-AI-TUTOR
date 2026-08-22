"""Every API failure must reach the client as the standard envelope.

The frontend reads `response.data.error.message` everywhere. Two paths bypassed
that contract, so failures showed up as a silent no-op in the UI:
  * FastAPI's default 422 body is `{"detail": [...]}`;
  * unknown /api routes fell through to the SPA catch-all and returned
    HTTP 200 with index.html.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNINGOS_DATA_DIR", str(tmp_path / "error-contract-data"))

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


def _assert_envelope(payload: dict) -> dict:
    assert set(payload) >= {"data", "error", "meta"}, payload
    assert payload["data"] is None
    assert payload["error"]["message"]
    return payload["error"]


def test_validation_error_uses_the_response_envelope(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/profiles",
            json={"name": "Bad Profile", "profile_type": "NotARealTrack"},
        )

    assert resp.status_code == 422
    assert "application/json" in resp.headers["content-type"]
    error = _assert_envelope(resp.json())
    assert error["code"] == "VALIDATION_ERROR"
    # The offending field should be identifiable from the message alone.
    assert "profile_type" in error["message"]


def test_missing_required_field_reports_the_field(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        resp = client.post("/api/v1/profiles", json={})

    assert resp.status_code == 422
    error = _assert_envelope(resp.json())
    assert "name" in error["message"]


def test_unknown_api_route_returns_json_404_not_the_spa_shell(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        resp = client.get("/api/v1/does-not-exist")

    assert resp.status_code == 404
    assert "html" not in resp.headers.get("content-type", "")
    error = _assert_envelope(resp.json())
    assert error["code"] in ("NOT_FOUND", "HTTP_404")


def test_unknown_nested_api_route_returns_json_404(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        resp = client.get("/api/v1/profiles/abc/not-a-resource")

    assert resp.status_code == 404
    assert "<!doctype html>" not in resp.text.lower()


def test_client_routes_still_serve_the_spa(tmp_path, monkeypatch):
    """The API 404 rule must not break client-side routing."""
    from pathlib import Path

    import pytest

    dist = Path(__file__).resolve().parents[4] / "frontend" / "dist"
    if not (dist / "index.html").exists():
        pytest.skip("frontend/dist not built")

    app = _make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        resp = client.get("/chat")

    assert resp.status_code == 200
    assert "<!doctype html>" in resp.text.lower()
