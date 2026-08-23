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
        json={"name": "Notes API Tester", "profile_type": "GATE"},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_notes_api_full_lifecycle(tmp_path, monkeypatch, stub_notes_llm):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _create_profile(client)

        # 1. Generate AI Note
        gen_resp = client.post(
            f"/api/v1/profiles/{profile_id}/notes/generate",
            json={
                "topic_title": "Dijkstra Algorithm",
                "note_type": "cheat_sheet",
            },
        )
        assert gen_resp.status_code == 201
        note_data = gen_resp.json()["data"]
        note_id = note_data["id"]
        assert note_data["note_type"] == "cheat_sheet"
        assert len(note_data["content"]) > 0

        # 2. List Notes
        list_resp = client.get(f"/api/v1/profiles/{profile_id}/notes")
        assert list_resp.status_code == 200
        notes_list = list_resp.json()["data"]
        assert len(notes_list) == 1

        # 3. Get Single Note
        get_resp = client.get(f"/api/v1/profiles/{profile_id}/notes/{note_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["id"] == note_id

        # 4. Update Note
        patch_resp = client.patch(
            f"/api/v1/profiles/{profile_id}/notes/{note_id}",
            json={"title": "Custom Dijkstra Cheat Sheet"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["data"]["title"] == "Custom Dijkstra Cheat Sheet"

        # 5. Delete Note
        del_resp = client.delete(f"/api/v1/profiles/{profile_id}/notes/{note_id}")
        assert del_resp.status_code == 200

        # 6. Verify Deletion
        list_after = client.get(f"/api/v1/profiles/{profile_id}/notes")
        assert len(list_after.json()["data"]) == 0
