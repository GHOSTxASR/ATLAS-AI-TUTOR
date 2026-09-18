"""Mapping concepts should read what is already uploaded, and stay readable.

Extraction took one passage at a time and returned a flat list of terms, so
mapping a course meant opening the same dialog once per document and watching
the graph fill with everything each one happened to mention.

It now reads a set of documents in one pass, and asks for the shape of the
material -- main concepts, with the finer points hung underneath the concept
they belong to rather than dropped in beside it.
"""

from __future__ import annotations

import json
from typing import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.models.abstraction import BaseModelClient, ChatMessage, ChatResponse, StreamChunk

EXTRACTION = {
    "concepts": [
        {
            "label": "Empathy Mapping",
            "description": "Understanding what users feel.",
            "subtopics": ["Say-Think-Do-Feel", "Field interviews"],
        },
        {
            "label": "Personas",
            "description": "Composite users.",
            "subtopics": ["Primary persona"],
        },
    ],
    "relationships": [
        {"source": "Empathy Mapping", "target": "Personas", "type": "prerequisite_of"}
    ],
}


class ExtractingClient(BaseModelClient):
    """Returns a structured extraction, and counts how often it was asked."""

    calls = 0

    def __init__(self, settings):
        pass

    async def chat_complete(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        ExtractingClient.calls += 1
        return ChatResponse(content=json.dumps(EXTRACTION))

    async def chat_stream(self, messages: list[ChatMessage], **kwargs) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content="", done=True)

    async def close(self) -> None:
        return None

    def get_provider_name(self) -> str:
        return "extractor"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "extraction-data"))
    monkeypatch.setenv("ATLAS_MODEL_PROVIDER", "ollama")

    from app.config import get_settings
    from app.db.repositories.graph_repo import GraphRepository
    from app.main import create_app

    get_settings.cache_clear()
    GraphRepository._graphs.clear()
    GraphRepository._locks.clear()
    ExtractingClient.calls = 0
    monkeypatch.setattr("app.services.graph_service.get_model_client", ExtractingClient)

    with TestClient(create_app()) as c:
        yield c


def _profile(client: TestClient) -> str:
    return client.post(
        "/api/v1/profiles", json={"name": "Learner", "profile_type": "GATE"}
    ).json()["data"]["id"]


def _upload(client: TestClient, profile_id: str, name: str) -> str:
    # Contents differ per file: identical uploads are refused as duplicates.
    body = f"Interviews, empathy maps and personas. From {name}.\n".encode()
    response = client.post(
        f"/api/v1/profiles/{profile_id}/documents",
        files={"file": (name, body, "text/plain")},
        data={"is_syllabus": "false"},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def _graph(client: TestClient, profile_id: str) -> dict:
    return client.get(f"/api/v1/profiles/{profile_id}/graph").json()["data"]


def test_several_documents_are_read_in_one_pass(client):
    profile_id = _profile(client)
    ids = [_upload(client, profile_id, f"notes-{i}.txt") for i in range(3)]

    response = client.post(
        f"/api/v1/profiles/{profile_id}/graph/enrich", json={"document_ids": ids}
    )
    assert response.status_code == 200, response.text

    assert ExtractingClient.calls == 3, "each document should be read"
    labels = {n["label"] for n in _graph(client, profile_id)["nodes"]}
    for name in ("notes-0.txt", "notes-1.txt", "notes-2.txt"):
        assert name in labels, f"{name} was never mapped"


def test_finer_points_hang_off_the_concept_they_belong_to(client):
    profile_id = _profile(client)
    document_id = _upload(client, profile_id, "empathy.txt")

    client.post(
        f"/api/v1/profiles/{profile_id}/graph/enrich", json={"document_ids": [document_id]}
    )
    graph = _graph(client, profile_id)

    by_label = {n["label"]: n["id"] for n in graph["nodes"]}
    assert "Empathy Mapping" in by_label
    assert "Say-Think-Do-Feel" in by_label, "subtopics never reached the graph"

    attached = [
        link
        for link in graph["links"]
        if link["source"] == by_label["Say-Think-Do-Feel"]
        and link["target"] == by_label["Empathy Mapping"]
    ]
    assert attached, "a subtopic was left floating beside its concept instead of under it"

    # And the ordering between main concepts survived.
    ordered = [
        link
        for link in graph["links"]
        if link["source"] == by_label["Empathy Mapping"]
        and link["target"] == by_label["Personas"]
        and link["type"] == "prerequisite_of"
    ]
    assert ordered, "the prerequisite between the two concepts was lost"


def test_a_document_that_cannot_be_read_does_not_sink_the_rest(client):
    profile_id = _profile(client)
    good = _upload(client, profile_id, "readable.txt")

    response = client.post(
        f"/api/v1/profiles/{profile_id}/graph/enrich",
        json={"document_ids": ["does-not-exist", good]},
    )
    assert response.status_code == 200, response.text
    assert "Empathy Mapping" in {n["label"] for n in _graph(client, profile_id)["nodes"]}


def test_asking_with_no_source_is_still_refused(client):
    profile_id = _profile(client)
    response = client.post(f"/api/v1/profiles/{profile_id}/graph/enrich", json={})
    assert response.status_code == 422, response.text
