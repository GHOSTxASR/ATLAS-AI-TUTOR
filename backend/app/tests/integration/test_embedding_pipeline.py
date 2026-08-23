from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.tests.conftest import uploaded_document

from app.pipelines.embedder import DocumentEmbedder


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-data"))

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


def _create_profile(client: TestClient) -> str:
    response = client.post(
        "/api/v1/profiles",
        json={"name": "Embedding Test Profile", "profile_type": "JEE"},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


@pytest.mark.asyncio
async def test_full_embedding_pipeline_and_vector_query(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _create_profile(client)

        content = (
            b"Newton's laws of motion are three basic laws of classical mechanics "
            b"that describe the relationship between the motion of an object and the forces acting on it. "
            b"The first law states that an object at rest remains at rest unless acted upon by a net force. "
            b"The second law states that the force applied is proportional to the rate of change of momentum. "
            b"The third law states that for every action there is an equal and opposite reaction."
        )

        # 1. Upload document
        upload_resp = client.post(
            f"/api/v1/profiles/{profile_id}/documents",
            files={"file": ("physics_laws.txt", content, "text/plain")},
        )
        assert upload_resp.status_code == 201
        document = upload_resp.json()["data"]
        doc_id = document["id"]

        document = uploaded_document(client, profile_id, document["id"])
        assert document["status"] == "indexed"
        assert document["chunk_count"] >= 1
        assert document["indexed_at"] is not None

        # 2. Query vectors using DocumentEmbedder
        from app.config import get_settings
        settings = get_settings()
        embedder = DocumentEmbedder(settings=settings)

        results = await embedder.query_similar_chunks(
            profile_id=profile_id,
            query="Tell me about Newton's third law of motion",
            n_results=3,
        )

        assert len(results["ids"][0]) >= 1
        assert any("Newton" in doc for doc in results["documents"][0])
        # Verify metadata
        first_meta = results["metadatas"][0][0]
        assert first_meta["doc_id"] == doc_id
        assert first_meta["profile_id"] == profile_id
        assert first_meta["source_filename"] == "physics_laws.txt"
        assert first_meta["embedding_dim"] == 1536

        # 3. Test Delete
        del_resp = client.delete(f"/api/v1/profiles/{profile_id}/documents/{doc_id}")
        assert del_resp.status_code == 200

        # Verify vectors are gone
        post_del_results = await embedder.query_similar_chunks(
            profile_id=profile_id,
            query="Newton",
            n_results=3,
        )
        assert len(post_del_results["ids"][0]) == 0
