from fastapi.testclient import TestClient


def test_api_startup_health_and_profile_crud(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-data"))

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["error"] is None
        assert payload["data"]["status"] == "ok"

        create_response = client.post(
            "/api/v1/profiles",
            json={"name": "Integrity Test", "profile_type": "Custom Learning"},
        )
        assert create_response.status_code == 201
        profile = create_response.json()["data"]
        assert profile["id"]
        assert profile["name"] == "Integrity Test"

        list_response = client.get("/api/v1/profiles")
        assert list_response.status_code == 200
        profiles = list_response.json()["data"]
        assert any(item["id"] == profile["id"] for item in profiles)
