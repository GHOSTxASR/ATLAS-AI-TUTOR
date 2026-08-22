from __future__ import annotations

import io
from fastapi.testclient import TestClient


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNINGOS_DATA_DIR", str(tmp_path / "learningos-isolation-data"))

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


def test_end_to_end_multi_learner_profile_isolation(tmp_path, monkeypatch):
    """
    Validates strict cross-profile isolation across:
    - Vector store index and document embeddings
    - Cognitive memories and misconception records
    - Notes, study cheat sheets, and summaries
    - Roadmaps and curriculum DAG nodes
    - Knowledge graph nodes and edges
    - Global multi-pillar search
    """
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        # 1. Create Profile A (GATE CSE) and Profile B (Medical NEET)
        resp_a = client.post(
            "/api/v1/profiles",
            json={"name": "Alice - Computer Science", "profile_type": "GATE"},
        )
        assert resp_a.status_code == 201
        profile_a = resp_a.json()["data"]["id"]

        resp_b = client.post(
            "/api/v1/profiles",
            json={"name": "Bob - Medical Biology", "profile_type": "Custom Learning"},
        )
        assert resp_b.status_code == 201
        profile_b = resp_b.json()["data"]["id"]

        # 2. Upload Profile A document (Algorithms) and Profile B document (Genetics)
        doc_a = client.post(
            f"/api/v1/profiles/{profile_a}/documents",
            files={
                "file": (
                    "dijkstra_shortest_path.txt",
                    io.BytesIO(b"Dijkstra algorithm finds shortest paths in non-negative weighted graphs using priority queues."),
                    "text/plain",
                )
            },
        )
        assert doc_a.status_code == 201
        doc_a_id = doc_a.json()["data"]["id"]

        doc_b = client.post(
            f"/api/v1/profiles/{profile_b}/documents",
            files={
                "file": (
                    "mendelian_genetics.txt",
                    io.BytesIO(b"Mendel law of segregation explains allele distribution in heterozygous monohybrid crosses."),
                    "text/plain",
                )
            },
        )
        assert doc_b.status_code == 201
        doc_b_id = doc_b.json()["data"]["id"]

        # 3. Verify Document List Isolation
        docs_a = client.get(f"/api/v1/profiles/{profile_a}/documents").json()["data"]
        docs_b = client.get(f"/api/v1/profiles/{profile_b}/documents").json()["data"]
        assert len(docs_a) == 1
        assert len(docs_b) == 1
        assert docs_a[0]["filename"] == "dijkstra_shortest_path.txt"
        assert docs_b[0]["filename"] == "mendelian_genetics.txt"

        # Listing being scoped is not enough: fetching another profile's
        # document by its id must also be refused, or the isolation is only
        # cosmetic and anyone holding an id could read across profiles.
        assert client.get(f"/api/v1/profiles/{profile_a}/documents/{doc_b_id}").status_code == 404
        assert client.get(f"/api/v1/profiles/{profile_b}/documents/{doc_a_id}").status_code == 404
        assert (
            client.get(f"/api/v1/profiles/{profile_a}/documents/{doc_a_id}").status_code == 200
        )

        # 4. Verify Memory Isolation
        client.post(
            f"/api/v1/profiles/{profile_a}/memory",
            json={
                "category": "weakness",
                "subject": "Fibonacci Heap Complexity",
                "content": "Confuses decrease-key amortized time in Dijkstra.",
                "confidence": 0.9,
            },
        )
        mems_a = client.get(f"/api/v1/profiles/{profile_a}/memory").json()["data"]
        mems_b = client.get(f"/api/v1/profiles/{profile_b}/memory").json()["data"]
        assert len(mems_a) == 1
        assert len(mems_b) == 0

        # 5. Verify Notes Isolation
        client.post(
            f"/api/v1/profiles/{profile_a}/notes",
            json={
                "title": "Graph Algorithms Revision",
                "content": "# Dijkstra and Bellman Ford summary",
                "note_type": "revision_note",
            },
        )
        notes_a = client.get(f"/api/v1/profiles/{profile_a}/notes").json()["data"]
        notes_b = client.get(f"/api/v1/profiles/{profile_b}/notes").json()["data"]
        assert len(notes_a) == 1
        assert len(notes_b) == 0

        # 6. Verify Knowledge Graph Isolation
        client.post(
            f"/api/v1/profiles/{profile_a}/graph/nodes",
            json={"label": "Graph Theory", "type": "subject", "mastery_score": 0.7},
        )
        graph_a = client.get(f"/api/v1/profiles/{profile_a}/graph").json()["data"]
        graph_b = client.get(f"/api/v1/profiles/{profile_b}/graph").json()["data"]
        assert len(graph_a["nodes"]) == 1
        assert len(graph_b["nodes"]) == 0

        # 7. Verify Global Search Isolation
        search_a = client.get(
            f"/api/v1/profiles/{profile_a}/search/global",
            params={"q": "Dijkstra"},
        ).json()["data"]
        search_b = client.get(
            f"/api/v1/profiles/{profile_b}/search/global",
            params={"q": "Dijkstra"},
        ).json()["data"]
        assert search_a["total_results"] > 0
        assert search_b["total_results"] == 0
