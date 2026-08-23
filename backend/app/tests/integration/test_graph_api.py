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
        json={"name": "Graph API Tester", "profile_type": "GATE"},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_graph_api_endpoints(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _create_profile(client)

        # 1. Create Node A
        n1_resp = client.post(
            f"/api/v1/profiles/{profile_id}/graph/nodes",
            json={
                "label": "Graph Theory",
                "type": "subject",
                "description": "Study of graphs and networks",
            },
        )
        assert n1_resp.status_code == 201
        n1 = n1_resp.json()["data"]

        # 2. Create Node B
        n2_resp = client.post(
            f"/api/v1/profiles/{profile_id}/graph/nodes",
            json={
                "label": "Dijkstra Algorithm",
                "type": "concept",
                "description": "Shortest path algorithm for non-negative weights",
                "mastery_score": 0.85,
            },
        )
        assert n2_resp.status_code == 201
        n2 = n2_resp.json()["data"]

        # 3. Create Edge between Node A and Node B
        edge_resp = client.post(
            f"/api/v1/profiles/{profile_id}/graph/edges",
            json={
                "source": n1["id"],
                "target": n2["id"],
                "type": "taught_in",
            },
        )
        assert edge_resp.status_code == 201

        # 4. Get Full Graph
        graph_resp = client.get(f"/api/v1/profiles/{profile_id}/graph")
        assert graph_resp.status_code == 200
        graph_data = graph_resp.json()["data"]
        assert len(graph_data["nodes"]) == 2
        assert len(graph_data["links"]) >= 1

        # 5. Search Nodes
        search_resp = client.get(f"/api/v1/profiles/{profile_id}/graph/search?q=Dijkstra")
        assert search_resp.status_code == 200
        search_results = search_resp.json()["data"]
        assert len(search_results) == 1
        assert search_results[0]["label"] == "Dijkstra Algorithm"

        # 6. Find Path
        path_resp = client.get(
            f"/api/v1/profiles/{profile_id}/graph/path?source_id={n1['id']}&target_id={n2['id']}"
        )
        assert path_resp.status_code == 200
        path_data = path_resp.json()["data"]
        assert path_data["path_found"] is True
        assert path_data["length"] == 1
