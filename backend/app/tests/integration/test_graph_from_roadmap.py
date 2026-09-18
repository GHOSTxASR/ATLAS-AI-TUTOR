"""Uploading a syllabus has to produce a graph, and one that means something.

The knowledge graph had no idea a curriculum existed. It filled up only from
ad-hoc "AI Extract" runs -- four to eight concepts at a time, each batch an
island with no edge to any other -- while the roadmap beside it held every
topic of the course in sequence. A learner who uploaded a syllabus got a
roadmap and an empty graph.

The roadmap is where the ordering is worked out, so building one now mirrors
its topics and their order into the graph.
"""

from __future__ import annotations

from typing import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.models.abstraction import BaseModelClient, ChatMessage, ChatResponse, StreamChunk

# Markdown headings parse to the same shape every run.
NETWORKING = """# Networking
## Core Concepts
### Packet Switching
### Routing Basics
### Congestion Control
"""
NETWORKING_GROWN = """# Networking
## Core Concepts
### Packet Switching
### Routing Basics
### Congestion Control
### Quality of Service
"""


class StubClient(BaseModelClient):
    """Keeps syllabus parsing and extraction off the network."""

    def __init__(self, settings):
        pass

    async def chat_complete(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        return ChatResponse(content="ok")

    async def chat_stream(self, messages: list[ChatMessage], **kwargs) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content="ok", done=False)
        yield StreamChunk(content="", done=True)

    async def close(self) -> None:
        return None

    def get_provider_name(self) -> str:
        return "stub"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "graph-roadmap-data"))
    monkeypatch.setenv("ATLAS_MODEL_PROVIDER", "ollama")

    from app.config import get_settings
    from app.db.repositories.graph_repo import GraphRepository
    from app.main import create_app

    get_settings.cache_clear()
    # The graph cache is shared across instances by design; a leftover entry
    # would leak one test's curriculum into the next.
    GraphRepository._graphs.clear()
    GraphRepository._locks.clear()

    for target in (
        "app.services.roadmap_builders.get_model_client",
        "app.pipelines.syllabus_parser.get_model_client",
        "app.services.graph_service.get_model_client",
    ):
        monkeypatch.setattr(target, StubClient)

    with TestClient(create_app()) as c:
        yield c


def _profile(client: TestClient) -> str:
    return client.post(
        "/api/v1/profiles", json={"name": "Learner", "profile_type": "GATE"}
    ).json()["data"]["id"]


def _build_roadmap(client: TestClient, profile_id: str, syllabus: str, name: str) -> dict:
    upload = client.post(
        f"/api/v1/profiles/{profile_id}/documents",
        files={"file": (f"{name}.txt", syllabus.encode(), "text/plain")},
        data={"is_syllabus": "true"},
    )
    assert upload.status_code == 201, upload.text
    created = client.post(
        f"/api/v1/profiles/{profile_id}/roadmaps",
        json={"document_id": upload.json()["data"]["id"], "mode": "strict"},
    )
    assert created.status_code == 201, created.text
    return created.json()["data"]


def _graph(client: TestClient, profile_id: str) -> dict:
    response = client.get(f"/api/v1/profiles/{profile_id}/graph")
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _chain(graph: dict) -> list[str]:
    """The graph's ordering read back as a single run of concept labels."""
    label = {n["id"]: n["label"] for n in graph["nodes"]}
    following = {
        link["source"]: link["target"]
        for link in graph["links"]
        if link["type"] == "prerequisite_of"
    }
    has_predecessor = set(following.values())
    starts = [n for n in following if n not in has_predecessor]
    if not starts:
        return []
    walk = [starts[0]]
    while walk[-1] in following:
        nxt = following[walk[-1]]
        if nxt in walk:  # a loop is not a learning order
            break
        walk.append(nxt)
    return [label[n] for n in walk]


def test_building_a_roadmap_fills_the_graph_in_learning_order(client):
    profile_id = _profile(client)

    assert _graph(client, profile_id)["nodes"] == [], "the graph should start empty"

    _build_roadmap(client, profile_id, NETWORKING, "syllabus-v1")
    graph = _graph(client, profile_id)

    labels = {n["label"] for n in graph["nodes"]}
    assert {"Packet Switching", "Routing Basics", "Congestion Control"} <= labels, (
        f"the syllabus topics never reached the graph: {labels}"
    )

    # Every topic joined up, in the order the syllabus teaches them -- not
    # three unconnected islands.
    assert _chain(graph) == ["Packet Switching", "Routing Basics", "Congestion Control"]

    for node in graph["nodes"]:
        assert node["roadmap_node_id"], f"{node['label']} is not tied to its topic"


def test_a_grown_syllabus_extends_the_chain_without_duplicating_it(client):
    profile_id = _profile(client)
    _build_roadmap(client, profile_id, NETWORKING, "syllabus-v1")
    before = _graph(client, profile_id)

    _build_roadmap(client, profile_id, NETWORKING_GROWN, "syllabus-v2")
    after = _graph(client, profile_id)

    labels = [n["label"] for n in after["nodes"]]
    assert len(labels) == len(set(labels)), f"concepts were duplicated: {labels}"
    assert len(after["nodes"]) == len(before["nodes"]) + 1
    assert _chain(after) == [
        "Packet Switching",
        "Routing Basics",
        "Congestion Control",
        "Quality of Service",
    ]


def test_the_learners_own_concepts_and_links_are_left_alone(client):
    """A graph built by hand before the syllabus arrived must survive it."""
    profile_id = _profile(client)

    mine = client.post(
        f"/api/v1/profiles/{profile_id}/graph/nodes",
        json={"label": "My own note to self", "type": "concept"},
    ).json()["data"]
    # Named exactly as the syllabus names it: the same concept, not a second one.
    overlapping = client.post(
        f"/api/v1/profiles/{profile_id}/graph/nodes",
        json={"label": "Routing Basics", "type": "concept", "description": "mine"},
    ).json()["data"]
    client.post(
        f"/api/v1/profiles/{profile_id}/graph/edges",
        json={"source": mine["id"], "target": overlapping["id"], "type": "related_to"},
    )

    _build_roadmap(client, profile_id, NETWORKING, "syllabus-v1")
    graph = _graph(client, profile_id)

    by_label = {n["label"]: n for n in graph["nodes"]}
    assert "My own note to self" in by_label, "a hand-made concept was dropped"

    adopted = by_label["Routing Basics"]
    assert adopted["id"] == overlapping["id"], "the curriculum duplicated an existing concept"
    assert adopted["roadmap_node_id"], "the adopted concept was never tied to its topic"

    kept = [
        link
        for link in graph["links"]
        if link["source"] == mine["id"] and link["target"] == overlapping["id"]
    ]
    assert kept, "the learner's own link was removed by the sync"


def test_extraction_reads_an_uploaded_document_without_it_being_pasted(client):
    """The text was extracted on upload; asking for it again was asking twice.

    The stub model returns nothing usable, so extraction falls back to reading
    lines off the source -- which is exactly what proves the document's text
    was loaded rather than an empty request being accepted.
    """
    profile_id = _profile(client)
    upload = client.post(
        f"/api/v1/profiles/{profile_id}/documents",
        files={
            "file": (
                "lecture-notes.txt",
                b"Sliding window protocol\nSelective repeat recovery\n",
                "text/plain",
            )
        },
        data={"is_syllabus": "false"},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["data"]["id"]

    enriched = client.post(
        f"/api/v1/profiles/{profile_id}/graph/enrich",
        json={"document_id": document_id},
    )
    assert enriched.status_code == 200, enriched.text

    graph = _graph(client, profile_id)
    labels = {n["label"] for n in graph["nodes"]}
    assert "Sliding window protocol" in labels, (
        f"the document's own text never reached the extractor: {labels}"
    )
    # And the source it came from is on the graph, named for the file.
    assert "lecture-notes.txt" in labels


def test_extraction_still_refuses_a_request_with_no_source(client):
    profile_id = _profile(client)
    response = client.post(f"/api/v1/profiles/{profile_id}/graph/enrich", json={})
    assert response.status_code == 422, response.text


def test_a_graph_that_predates_this_gets_the_curriculum_on_first_view(client):
    """Roadmaps built before the mirror existed must not stay unrepresented.

    Generating a roadmap keeps the graph in step from here on, but someone who
    built theirs last week would open the page and still find only whatever
    they had extracted by hand.
    """
    profile_id = _profile(client)
    _build_roadmap(client, profile_id, NETWORKING, "syllabus-v1")

    # Strip it back to what an older profile looks like: a roadmap, and a
    # graph that knows nothing about it.
    for node in _graph(client, profile_id)["nodes"]:
        client.delete(f"/api/v1/profiles/{profile_id}/graph/nodes/{node['id']}")
    assert _graph(client, profile_id)["nodes"] != [], (
        "opening the graph beside an existing roadmap left it empty"
    )

    assert _chain(_graph(client, profile_id)) == [
        "Packet Switching",
        "Routing Basics",
        "Congestion Control",
    ]
