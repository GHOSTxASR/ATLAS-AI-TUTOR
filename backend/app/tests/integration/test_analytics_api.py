from __future__ import annotations

from fastapi.testclient import TestClient


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNINGOS_DATA_DIR", str(tmp_path / "learningos-data"))

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


def _create_profile(client: TestClient) -> str:
    response = client.post(
        "/api/v1/profiles",
        json={"name": "Analytics Test User", "profile_type": "JEE"},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_analytics_api_endpoints(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _create_profile(client)

        # 1. Log an event
        event_resp = client.post(
            f"/api/v1/profiles/{profile_id}/analytics/events",
            json={
                "event_type": "time_logged",
                "entity_type": "roadmap_node",
                "value": 45,
                "metadata_json": '{"topic": "Calculus Integration"}',
            },
        )
        assert event_resp.status_code == 201

        # 2. Get Overview
        overview_resp = client.get(f"/api/v1/profiles/{profile_id}/analytics/overview")
        assert overview_resp.status_code == 200
        overview = overview_resp.json()["data"]
        assert "completion_percentage" in overview
        assert overview["total_study_minutes"] >= 45

        # 3. Get Heatmap
        heatmap_resp = client.get(f"/api/v1/profiles/{profile_id}/analytics/heatmap?days=14")
        assert heatmap_resp.status_code == 200
        heatmap = heatmap_resp.json()["data"]
        assert len(heatmap) == 14
        assert any(d["minutes"] >= 45 for d in heatmap)

        # 4. Get Mastery Distribution
        mastery_resp = client.get(f"/api/v1/profiles/{profile_id}/analytics/mastery")
        assert mastery_resp.status_code == 200
        mastery = mastery_resp.json()["data"]
        assert "mastered_count" in mastery
        assert "proficient_count" in mastery

        # 5. Get Learning Velocity
        velocity_resp = client.get(f"/api/v1/profiles/{profile_id}/analytics/velocity?days=7")
        assert velocity_resp.status_code == 200
        velocity = velocity_resp.json()["data"]
        assert len(velocity) == 7

        # 6. Get Weaknesses
        weaknesses_resp = client.get(f"/api/v1/profiles/{profile_id}/analytics/weaknesses")
        assert weaknesses_resp.status_code == 200
        weaknesses = weaknesses_resp.json()["data"]
        assert isinstance(weaknesses, list)
