"""Adding to a syllabus must not cost the learner what they have already done.

Generating a roadmap used to archive the one in progress and build a fresh
set of nodes. Every topic got a new id, so all progress went back to zero and
every chat, note, quiz attempt and document filed against a topic was left
pointing at a row nobody would look at again -- for the sake of one extra
chapter in the syllabus.

Generation now folds a re-parsed syllabus into the roadmap already there,
while a syllabus for a genuinely different subject still starts its own.
"""

from __future__ import annotations

from typing import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.models.abstraction import BaseModelClient, ChatMessage, ChatResponse, StreamChunk

# Markdown headings, so the syllabus parses to the same shape every run:
# "# " a subject, "## " a chapter, "### " a topic.
NETWORKING = """# Networking
## Core Concepts
### Packet Switching
### Routing Basics
"""
NETWORKING_GROWN = """# Networking
## Core Concepts
### Packet Switching
### Routing Basics
### Congestion Control
"""
NETWORKING_SHRUNK = """# Networking
## Core Concepts
### Packet Switching
"""
GEOGRAPHY = """# Human Geography
## Settlement
### Population Density
### Urban Settlement
"""


class StubClient(BaseModelClient):
    """Keeps syllabus parsing on its deterministic non-AI path."""

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
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "reconcile-data"))
    monkeypatch.setenv("ATLAS_MODEL_PROVIDER", "ollama")

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    for target in (
        "app.routers.ws_chat.get_model_client",
        "app.services.roadmap_builders.get_model_client",
        "app.pipelines.syllabus_parser.get_model_client",
    ):
        monkeypatch.setattr(target, StubClient)

    with TestClient(create_app()) as c:
        yield c


def _profile(client: TestClient) -> str:
    return client.post(
        "/api/v1/profiles", json={"name": "Learner", "profile_type": "GATE"}
    ).json()["data"]["id"]


def _build(client: TestClient, profile_id: str, syllabus: str, name: str) -> dict:
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


def _titles(roadmap: dict) -> set[str]:
    return {n["title"] for n in roadmap["nodes"]}


def _node(roadmap: dict, title: str) -> dict:
    return next(n for n in roadmap["nodes"] if n["title"] == title)


def test_a_grown_syllabus_keeps_progress_and_the_topics_it_is_attached_to(client):
    profile_id = _profile(client)
    first = _build(client, profile_id, NETWORKING, "syllabus-v1")

    studied = _node(first, "Packet Switching")
    # Progress, and a conversation filed against the topic.
    client.patch(
        f"/api/v1/profiles/{profile_id}/roadmaps/{first['id']}/nodes/{studied['id']}",
        json={"status": "completed", "mastery_score": 0.8},
    )
    session_id = client.post(
        f"/api/v1/profiles/{profile_id}/sessions/for-topic",
        json={"topic": "Packet Switching", "roadmap_node_id": studied["id"]},
    ).json()["data"]["id"]

    second = _build(client, profile_id, NETWORKING_GROWN, "syllabus-v2")

    assert second["id"] == first["id"], "the roadmap in progress was replaced, not extended"
    assert "Congestion Control" in _titles(second), "the new chapter never arrived"

    carried = _node(second, "Packet Switching")
    assert carried["id"] == studied["id"], "the topic was rebuilt under a new id"
    assert carried["status"] == "completed", "finished work was reset"
    assert carried["mastery_score"] == 0.8

    # The thread is still about a topic that exists.
    session = client.get(f"/api/v1/profiles/{profile_id}/sessions/{session_id}").json()["data"]
    assert session["roadmap_node_id"] == studied["id"]
    assert studied["id"] in {n["id"] for n in second["nodes"]}


def test_a_different_subject_starts_its_own_roadmap(client):
    profile_id = _profile(client)
    networking = _build(client, profile_id, NETWORKING, "networking")
    geography = _build(client, profile_id, GEOGRAPHY, "geography")

    assert geography["id"] != networking["id"], "geography was folded into the networking roadmap"
    assert "Packet Switching" not in _titles(geography)

    # The old one is kept as history rather than thrown away.
    listed = client.get(f"/api/v1/profiles/{profile_id}/roadmaps").json()["data"]
    assert {r["id"] for r in listed} >= {networking["id"], geography["id"]}


def test_a_dropped_topic_survives_only_if_it_was_worked_on(client):
    profile_id = _profile(client)
    first = _build(client, profile_id, NETWORKING, "syllabus-v1")
    routing = _node(first, "Routing Basics")

    # Untouched: the syllabus dropping it is the whole story.
    second = _build(client, profile_id, NETWORKING_SHRUNK, "syllabus-v2")
    assert "Routing Basics" not in _titles(second), "an untouched dropped topic lingered"
    assert routing["id"] not in {n["id"] for n in second["nodes"]}


def test_a_dropped_topic_with_work_behind_it_is_kept(client):
    profile_id = _profile(client)
    first = _build(client, profile_id, NETWORKING, "syllabus-v1")
    routing = _node(first, "Routing Basics")

    client.post(
        f"/api/v1/profiles/{profile_id}/sessions/for-topic",
        json={"topic": "Routing Basics", "roadmap_node_id": routing["id"]},
    )

    second = _build(client, profile_id, NETWORKING_SHRUNK, "syllabus-v2")
    assert "Routing Basics" in _titles(second), (
        "a topic with a conversation behind it was deleted with the syllabus edit"
    )
    assert _node(second, "Routing Basics")["id"] == routing["id"]


NETWORKING_RENAMED_MODULE = """# Networking Fundamentals
## Core Concepts
### Packet Switching
### Routing Basics
"""


def test_a_reworded_module_still_takes_its_chapters_with_it(client):
    """Renaming the top of a syllabus is enough to break a naive update.

    The module no longer matches, so it arrives as a new node, while the
    chapters beneath it match and have to move under it. Writing those moves
    before the module exists fails on the foreign key and loses the whole
    update -- which is what a real syllabus, re-read and reworded slightly by
    the parser, does on the very first try.
    """
    profile_id = _profile(client)
    first = _build(client, profile_id, NETWORKING, "syllabus-v1")
    packet = _node(first, "Packet Switching")

    client.patch(
        f"/api/v1/profiles/{profile_id}/roadmaps/{first['id']}/nodes/{packet['id']}",
        json={"status": "in_progress"},
    )

    second = _build(client, profile_id, NETWORKING_RENAMED_MODULE, "syllabus-v2")

    assert "Networking Fundamentals" in _titles(second), "the reworded module never landed"
    carried = _node(second, "Packet Switching")
    assert carried["id"] == packet["id"], "the topic was rebuilt under a new id"
    assert carried["status"] == "in_progress", "progress was lost to a rename"

    # The chapter now hangs off the new module rather than a deleted one.
    chapter = _node(second, "Core Concepts")
    module = _node(second, "Networking Fundamentals")
    assert chapter["parent_id"] == module["id"]
