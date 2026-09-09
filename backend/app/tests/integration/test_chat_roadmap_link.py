"""Studying a topic in the tutor has to reach the roadmap.

A session opened from a roadmap topic stores that topic on the session. The
REST orchestrator read it; the WebSocket -- which is the path the interface
actually uses -- did not. So a thread explicitly about "Prototyping" was
tutored with no curriculum context, and the topic sat at "not started" no
matter how long you discussed it.

Both halves are pinned here: the socket resolves the session's topic without
being told it again, and finishing a turn moves the topic off "not started".
"""

from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi.testclient import TestClient

from app.models.abstraction import BaseModelClient, ChatMessage, ChatResponse, StreamChunk


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "chat-roadmap-data"))
    monkeypatch.setenv("ATLAS_MODEL_PROVIDER", "ollama")

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


class CapturingModelClient(BaseModelClient):
    """Streams a fixed reply and remembers the system prompt it was given."""

    last_system_prompt: str = ""

    def __init__(self, settings):
        pass

    async def chat_complete(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        return ChatResponse(content="ok")

    async def chat_stream(self, messages: list[ChatMessage], **kwargs) -> AsyncIterator[StreamChunk]:
        CapturingModelClient.last_system_prompt = next(
            (m.content for m in messages if m.role == "system"), ""
        )
        yield StreamChunk(content="Here is the explanation.", done=False)
        yield StreamChunk(content="", done=True)

    async def close(self) -> None:
        return None

    def get_provider_name(self) -> str:
        return "capturing"


def _one_turn(ws, content: str) -> str:
    ws.send_text(json.dumps({"content": content, "mode": "teaching"}))
    text = ""
    while True:
        event = ws.receive_json()
        if event["type"] == "chunk":
            text += event["content"]
        elif event["type"] in ("done", "error"):
            assert event["type"] == "done", event
            return text


def _roadmap_with_one_topic(client: TestClient, profile_id: str) -> dict:
    """A roadmap built from a tiny syllabus, returning its first topic node."""
    syllabus = "Module I: Networking\nPacket Switching\nRouting Basics\n"
    upload = client.post(
        f"/api/v1/profiles/{profile_id}/documents",
        files={"file": ("syl.txt", syllabus.encode(), "text/plain")},
        data={"is_syllabus": "true"},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["data"]["id"]

    created = client.post(
        f"/api/v1/profiles/{profile_id}/roadmaps",
        json={"document_id": document_id, "mode": "strict", "title": "Networking"},
    )
    assert created.status_code == 201, created.text
    nodes = created.json()["data"]["nodes"]
    topic = next(n for n in nodes if n["node_type"] == "topic")
    assert topic["status"] == "not_started"
    return topic


def test_socket_uses_the_session_topic_without_being_told_again(tmp_path, monkeypatch):
    """The client never resends the node id; the session already knows it."""
    app = _make_app(tmp_path, monkeypatch)
    monkeypatch.setattr("app.routers.ws_chat.get_model_client", CapturingModelClient)
    # Roadmap building resolves its own client, and so does syllabus parsing.
    monkeypatch.setattr(
        "app.services.roadmap_builders.get_model_client", CapturingModelClient
    )
    monkeypatch.setattr(
        "app.pipelines.syllabus_parser.get_model_client", CapturingModelClient
    )

    with TestClient(app) as client:
        profile_id = client.post(
            "/api/v1/profiles", json={"name": "Learner", "profile_type": "GATE"}
        ).json()["data"]["id"]
        topic = _roadmap_with_one_topic(client, profile_id)

        # Opened the way the roadmap opens it: keyed to the topic's node.
        session = client.post(
            f"/api/v1/profiles/{profile_id}/sessions/for-topic",
            json={"topic": topic["title"], "roadmap_node_id": topic["id"]},
        )
        assert session.status_code == 200, session.text
        session_id = session.json()["data"]["id"]

        with client.websocket_connect(f"/ws/chat/{profile_id}/{session_id}") as ws:
            # Deliberately no roadmap_node_id in the payload.
            _one_turn(ws, "Explain this to me.")

    assert topic["title"] in CapturingModelClient.last_system_prompt, (
        "the socket tutored without the topic the session was opened for"
    )


def test_a_tutoring_turn_moves_the_topic_off_not_started(tmp_path, monkeypatch):
    """Chatting about a topic is the only thing that advances it from the tutor.

    Mastery is deliberately not touched -- a conversation shows you started,
    not that you understood.
    """
    app = _make_app(tmp_path, monkeypatch)
    monkeypatch.setattr("app.routers.ws_chat.get_model_client", CapturingModelClient)
    # Roadmap building resolves its own client, and so does syllabus parsing.
    monkeypatch.setattr(
        "app.services.roadmap_builders.get_model_client", CapturingModelClient
    )
    monkeypatch.setattr(
        "app.pipelines.syllabus_parser.get_model_client", CapturingModelClient
    )

    with TestClient(app) as client:
        profile_id = client.post(
            "/api/v1/profiles", json={"name": "Learner", "profile_type": "GATE"}
        ).json()["data"]["id"]
        topic = _roadmap_with_one_topic(client, profile_id)

        opened = client.post(
            f"/api/v1/profiles/{profile_id}/sessions/for-topic",
            json={"topic": topic["title"], "roadmap_node_id": topic["id"]},
        ).json()["data"]
        # If the session does not carry the topic, nothing downstream can.
        assert opened["roadmap_node_id"] == topic["id"], opened
        session_id = opened["id"]

        with client.websocket_connect(f"/ws/chat/{profile_id}/{session_id}") as ws:
            _one_turn(ws, "Teach me this.")

        after = client.get(f"/api/v1/profiles/{profile_id}/roadmaps/active").json()["data"]
        moved = next(n for n in after["nodes"] if n["id"] == topic["id"])

    assert moved["status"] == "in_progress", "tutoring left the topic untouched"
    assert moved["mastery_score"] == 0.0, "a conversation must not confer mastery"


def test_an_unlinked_session_still_works(tmp_path, monkeypatch):
    """Most chats are not about a roadmap topic and must be unaffected."""
    app = _make_app(tmp_path, monkeypatch)
    monkeypatch.setattr("app.routers.ws_chat.get_model_client", CapturingModelClient)

    with TestClient(app) as client:
        profile_id = client.post(
            "/api/v1/profiles", json={"name": "Learner", "profile_type": "GATE"}
        ).json()["data"]["id"]
        session_id = client.post(
            f"/api/v1/profiles/{profile_id}/sessions", json={"title": "Just asking"}
        ).json()["data"]["id"]

        with client.websocket_connect(f"/ws/chat/{profile_id}/{session_id}") as ws:
            reply = _one_turn(ws, "What is a packet?")

    assert reply == "Here is the explanation."
