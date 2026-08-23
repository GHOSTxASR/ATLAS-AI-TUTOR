from __future__ import annotations

from fastapi.testclient import TestClient


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-data"))

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


def _create_profile(client: TestClient) -> str:
    response = client.post(
        "/api/v1/profiles",
        json={"name": "Context API Tester", "profile_type": "GATE"},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_tutor_context_inspection_api(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _create_profile(client)

        resp = client.get(
            f"/api/v1/profiles/{profile_id}/tutor/context?q=Thermodynamics&mode=teaching"
        )
        assert resp.status_code == 200
        data = resp.json()["data"]

        assert data["profile_id"] == profile_id
        assert data["mode"] == "teaching"
        assert "memory" in data
        assert "roadmap" in data
        assert "graph" in data
        assert "syllabus" in data
        assert "system_prompt" in data
        assert len(data["system_prompt"]) > 0
