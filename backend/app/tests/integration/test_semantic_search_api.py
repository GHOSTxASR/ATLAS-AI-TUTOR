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
        json={"name": "Search Test Profile", "profile_type": "GATE"},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_semantic_search_api_endpoint(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _create_profile(client)

        # Upload document 1: OS
        doc1_content = (
            b"Process synchronization is the coordination of execution of multiple processes. "
            b"Semaphores and mutexes are synchronization primitives used to prevent race conditions."
        )
        upload1 = client.post(
            f"/api/v1/profiles/{profile_id}/documents",
            files={"file": ("os_sync.txt", doc1_content, "text/plain")},
        )
        assert upload1.status_code == 201
        doc1_id = upload1.json()["data"]["id"]

        # Upload document 2: DBMS
        doc2_content = (
            b"Database transactions satisfy ACID properties: Atomicity, Consistency, Isolation, and Durability. "
            b"Two-phase locking ensures serializability and concurrency control."
        )
        upload2 = client.post(
            f"/api/v1/profiles/{profile_id}/documents",
            files={"file": ("dbms_acid.txt", doc2_content, "text/plain")},
        )
        assert upload2.status_code == 201
        doc2_id = upload2.json()["data"]["id"]

        # 1. Broad Search across documents
        search_resp = client.post(
            f"/api/v1/profiles/{profile_id}/search",
            json={"query": "How do semaphores prevent race conditions in processes?", "top_k": 5},
        )
        assert search_resp.status_code == 200
        data = search_resp.json()["data"]
        assert data["total"] >= 1
        assert any(r["source_id"] == doc1_id for r in data["results"])

        # 2. Filtered Search by document_id
        filtered_resp = client.post(
            f"/api/v1/profiles/{profile_id}/search",
            json={
                "query": "concurrency and synchronization",
                "document_ids": [doc2_id],
                "top_k": 5,
            },
        )
        assert filtered_resp.status_code == 200
        filtered_data = filtered_resp.json()["data"]
        assert filtered_data["total"] >= 1
        assert all(r["source_id"] == doc2_id for r in filtered_data["results"])

        # 3. Non-existent profile search returns 404
        bad_profile_resp = client.post(
            "/api/v1/profiles/non-existent-profile-id/search",
            json={"query": "test query"},
        )
        assert bad_profile_resp.status_code == 404
