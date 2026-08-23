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
        json={"name": "Roadmap API Profile", "profile_type": "GATE"},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_roadmap_full_api_lifecycle(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _create_profile(client)

        # 1. Upload syllabus document
        content = (
            b"# Data Structures\n"
            b"## Arrays and Lists\n"
            b"### Dynamic Arrays\n"
            b"- Allocation and growth\n"
            b"### Singly Linked Lists\n"
            b"- Node structures\n"
        )
        upload = client.post(
            f"/api/v1/profiles/{profile_id}/documents",
            files={"file": ("ds_syllabus.txt", content, "text/plain")},
            data={"is_syllabus": "true"},
        )
        assert upload.status_code == 201
        doc_id = upload.json()["data"]["id"]

        # 2. Generate Strict Roadmap via API
        gen_resp = client.post(
            f"/api/v1/profiles/{profile_id}/roadmaps",
            json={"document_id": doc_id, "mode": "strict", "title": "Data Structures Mastery"},
        )
        assert gen_resp.status_code == 201
        roadmap = gen_resp.json()["data"]
        roadmap_id = roadmap["id"]
        assert roadmap["mode"] == "strict"
        assert len(roadmap["nodes"]) >= 4

        # 3. Get Active Roadmap
        active_resp = client.get(f"/api/v1/profiles/{profile_id}/roadmaps/active")
        assert active_resp.status_code == 200
        active_data = active_resp.json()["data"]
        assert active_data["id"] == roadmap_id

        # 4. Update node status
        topic_nodes = [n for n in active_data["nodes"] if n["node_type"] == "topic"]
        node_1 = topic_nodes[0]
        node_2 = topic_nodes[1]

        patch_resp = client.patch(
            f"/api/v1/profiles/{profile_id}/roadmaps/{roadmap_id}/nodes/{node_1['id']}",
            json={"status": "completed", "mastery_score": 0.85},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["data"]["status"] == "completed"

        # Verify node_2 is now unlocked
        active_resp_after = client.get(f"/api/v1/profiles/{profile_id}/roadmaps/active")
        updated_nodes = active_resp_after.json()["data"]["nodes"]
        updated_node_2 = next(n for n in updated_nodes if n["id"] == node_2["id"])
        assert updated_node_2["unlocked"] is True

        # 5. Regenerate Roadmap and verify progress migration
        regen_resp = client.post(
            f"/api/v1/profiles/{profile_id}/roadmaps/{roadmap_id}/regenerate"
        )
        assert regen_resp.status_code == 200
        new_roadmap = regen_resp.json()["data"]
        assert new_roadmap["version"] == 2
        assert new_roadmap["is_active"] is True

        # Check that node 1's completed status was migrated
        new_topic_1 = next(
            (n for n in new_roadmap["nodes"] if n["title"] == node_1["title"]), None
        )
        assert new_topic_1 is not None
        assert new_topic_1["status"] == "completed"
        assert new_topic_1["mastery_score"] == 0.85
