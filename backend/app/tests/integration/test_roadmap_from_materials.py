"""A learner with course materials and no syllabus still needs a roadmap.

Generation needed a syllabus document, and the only thing that could produce
a syllabus was a syllabus. So someone who had uploaded six lecture PDFs and
no syllabus could not get a roadmap at all -- the generate panel had nothing
to offer them and the button did nothing.

The materials are now read across and the curriculum they teach is written
out, which then goes through the same strict / adaptive / hybrid generation
as any other syllabus.
"""

from __future__ import annotations

import json
from typing import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.models.abstraction import BaseModelClient, ChatMessage, ChatResponse, StreamChunk

WRITTEN_SYLLABUS = {
    "title": "Design Thinking",
    "description": "A course in human-centred design.",
    "subjects": [
        {
            "title": "Foundations",
            "description": "",
            "chapters": [
                {
                    "title": "Empathy",
                    "description": "",
                    "topics": [
                        {"title": "Understanding Users", "description": "", "subtopics": []},
                        {"title": "Personas", "description": "", "subtopics": []},
                    ],
                },
                {
                    "title": "Ideation",
                    "description": "",
                    "topics": [
                        {"title": "Brainstorming", "description": "", "subtopics": []},
                    ],
                },
            ],
        }
    ],
}


class CurriculumWritingClient(BaseModelClient):
    """Answers the "write me a syllabus" call, and records what it was shown."""

    last_user_content: str = ""

    def __init__(self, settings):
        pass

    async def chat_complete(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        CurriculumWritingClient.last_user_content = next(
            (m.content for m in messages if m.role == "user"), ""
        )
        return ChatResponse(content=json.dumps(WRITTEN_SYLLABUS))

    async def chat_stream(self, messages: list[ChatMessage], **kwargs) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content="", done=True)

    async def close(self) -> None:
        return None

    def get_provider_name(self) -> str:
        return "curriculum-writer"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "materials-data"))
    monkeypatch.setenv("ATLAS_MODEL_PROVIDER", "ollama")

    from app.config import get_settings
    from app.db.repositories.graph_repo import GraphRepository
    from app.main import create_app

    get_settings.cache_clear()
    GraphRepository._graphs.clear()
    GraphRepository._locks.clear()
    monkeypatch.setattr(
        "app.pipelines.syllabus_parser.get_model_client", CurriculumWritingClient
    )
    monkeypatch.setattr(
        "app.services.roadmap_builders.get_model_client", CurriculumWritingClient
    )

    with TestClient(create_app()) as c:
        yield c


def _profile(client: TestClient) -> str:
    return client.post(
        "/api/v1/profiles", json={"name": "Learner", "profile_type": "GATE"}
    ).json()["data"]["id"]


def _upload(client: TestClient, profile_id: str, name: str, body: bytes) -> str:
    response = client.post(
        f"/api/v1/profiles/{profile_id}/documents",
        files={"file": (name, body, "text/plain")},
        data={"is_syllabus": "false"},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def test_a_roadmap_is_built_from_materials_when_no_syllabus_exists(client):
    profile_id = _profile(client)
    ids = [
        _upload(client, profile_id, "empathy.txt", b"Interviewing users and building personas.\n"),
        _upload(client, profile_id, "ideation.txt", b"Brainstorming and sketching ideas.\n"),
    ]

    created = client.post(
        f"/api/v1/profiles/{profile_id}/roadmaps",
        json={"document_ids": ids, "mode": "strict"},
    )
    assert created.status_code == 201, created.text
    roadmap = created.json()["data"]

    titles = {n["title"] for n in roadmap["nodes"] if n["node_type"] == "topic"}
    assert titles == {"Understanding Users", "Personas", "Brainstorming"}, titles

    # The model was actually shown the materials, not just the filenames.
    assert "Interviewing users" in CurriculumWritingClient.last_user_content
    assert "Brainstorming and sketching" in CurriculumWritingClient.last_user_content

    # The order lives in the edges, not in whatever order the rows come back:
    # the whole point is that the topics are chained the way they are taught.
    by_id = {n["id"]: n["title"] for n in roadmap["nodes"]}
    following = {by_id[e["from_node_id"]]: by_id[e["to_node_id"]] for e in roadmap["edges"]}
    start = next(t for t in titles if t not in set(following.values()))
    walk = [start]
    while walk[-1] in following:
        walk.append(following[walk[-1]])
    assert walk == ["Understanding Users", "Personas", "Brainstorming"], walk


def test_the_mode_still_applies_to_a_written_syllabus(client):
    """Whatever produced the syllabus, the learner still picks how to study it."""
    profile_id = _profile(client)
    doc = _upload(client, profile_id, "notes.txt", b"Interviewing users and personas.\n")

    created = client.post(
        f"/api/v1/profiles/{profile_id}/roadmaps",
        json={"document_ids": [doc], "mode": "hybrid"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["data"]["mode"] == "hybrid"


def test_asking_with_nothing_at_all_still_explains_itself(client):
    profile_id = _profile(client)
    response = client.post(f"/api/v1/profiles/{profile_id}/roadmaps", json={"mode": "strict"})
    assert response.status_code == 422, response.text
    assert "syllabus" in response.text.lower()
