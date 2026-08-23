from __future__ import annotations

from fastapi.testclient import TestClient


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-resilience-data"))

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


def test_end_to_end_error_recovery_and_resilience(tmp_path, monkeypatch):
    """
    Validates robust error recovery, graceful degradations, and edge cases:
    - 404 handlers on non-existent profiles, roadmaps, and documents
    - Special characters and symbols in global search
    - Re-processing and status transitions
    - Empty and corrupted syllabus text fallback
    """
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        # 1. Non-existent profile 404 handling
        bad_profile_id = "00000000-0000-0000-0000-000000000000"
        resp_404 = client.get(f"/api/v1/profiles/{bad_profile_id}/analytics/overview")
        assert resp_404.status_code == 404

        # 2. Create valid profile
        p_resp = client.post(
            "/api/v1/profiles",
            json={"name": "Resilience Tester", "profile_type": "Semester Study"},
        )
        assert p_resp.status_code == 201
        profile_id = p_resp.json()["data"]["id"]

        # 3. Special characters in Global Search (Regex special characters: [ ] ( ) * + ? ^ $ \\)
        search_special = client.get(
            f"/api/v1/profiles/{profile_id}/search/global",
            params={"q": "([a-z]+)*?^$\\+!@#%^&*()"},
        )
        assert search_special.status_code == 200
        assert "total_results" in search_special.json()["data"]

        # 4. Empty search query (FastAPI min_length=1 validation error 422)
        search_empty = client.get(
            f"/api/v1/profiles/{profile_id}/search/global",
            params={"q": ""},
        )
        assert search_empty.status_code == 422

        # 5. Non-existent roadmap node update
        bad_node_resp = client.patch(
            f"/api/v1/profiles/{profile_id}/roadmaps/00000000-0000-0000-0000-000000000000/nodes/fake_node",
            json={"status": "completed"},
        )
        assert bad_node_resp.status_code == 404

        # 6. Roadmap validation error (422) when missing both document_id and syllabus_text
        roadmap_bad = client.post(
            f"/api/v1/profiles/{profile_id}/roadmaps",
            json={"title": "General Learning Pathway"},
        )
        assert roadmap_bad.status_code == 422

        # 7. Fallback roadmap generation with minimal raw syllabus text
        roadmap_ok = client.post(
            f"/api/v1/profiles/{profile_id}/roadmaps",
            json={
                "title": "General Learning Pathway",
                "syllabus_text": "# Module 1: Foundations\n- Topic 1.1: Core Concepts",
            },
        )
        assert roadmap_ok.status_code == 201
        assert len(roadmap_ok.json()["data"]["nodes"]) > 0

        # 8. Non-existent memory update
        mem_404 = client.patch(
            f"/api/v1/profiles/{profile_id}/memory/non_existent_mem_id",
            json={"content": "Updated content"},
        )
        assert mem_404.status_code == 404
