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
        json={"name": "Global Search API Tester", "profile_type": "GATE"},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_global_search_endpoints(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _create_profile(client)

        # 1. Create a Note
        note_resp = client.post(
            f"/api/v1/profiles/{profile_id}/notes",
            json={
                "title": "Quantum Physics Principles",
                "content": "Superposition and quantum entanglement fundamentals.",
                "note_type": "lesson_note",
            },
        )
        assert note_resp.status_code == 201

        # 2. Test GET Global Search
        get_res = client.get(
            f"/api/v1/profiles/{profile_id}/search/global?q=Quantum&limit=5&include_semantic=false"
        )
        assert get_res.status_code == 200
        get_data = get_res.json()["data"]
        assert get_data["query"] == "Quantum"
        assert get_data["total_results"] >= 1
        assert len(get_data["notes"]) >= 1
        assert "Quantum" in get_data["notes"][0]["title"]

        # 3. Test POST Global Search
        post_res = client.post(
            f"/api/v1/profiles/{profile_id}/search/global",
            json={
                "query": "Quantum",
                "limit_per_category": 5,
                "include_semantic": False,
                "categories": ["notes"],
            },
        )
        assert post_res.status_code == 200
        post_data = post_res.json()["data"]
        assert len(post_data["notes"]) >= 1
