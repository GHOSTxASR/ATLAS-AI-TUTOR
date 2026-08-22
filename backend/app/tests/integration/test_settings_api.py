from __future__ import annotations

from fastapi.testclient import TestClient


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNINGOS_DATA_DIR", str(tmp_path / "learningos-settings-data"))

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


def test_settings_endpoints(tmp_path, monkeypatch):
    """
    Validates settings endpoints:
    - GET /api/v1/settings/providers
    - GET /api/v1/settings/models
    - POST /api/v1/settings/test-connection
    """
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        # 1. List Providers
        p_resp = client.get("/api/v1/settings/providers")
        assert p_resp.status_code == 200
        providers = p_resp.json()["data"]["providers"]
        assert len(providers) >= 3

        # 2. List Models
        m_resp = client.get("/api/v1/settings/models?provider=openai")
        assert m_resp.status_code == 200
        models = m_resp.json()["data"]["models"]
        assert "gpt-4o" in models

        # 3. Test connection (returns ok or graceful provider error)
        t_resp = client.post("/api/v1/settings/test-connection", json={"provider": "ollama"})
        assert t_resp.status_code == 200
        assert "status" in t_resp.json()["data"]
