"""A model that streams nothing must not look like a finished answer.

Reasoning models -- and the "auto" routers that pick one for you -- sometimes
emit only their private thinking and no content at all. The socket used to
report that as a completed turn with empty text, so the interface showed the
learner their own question, no reply, and no hint that anything had failed.

Two behaviours are pinned here: an empty stream is retried once without
streaming, and a model that produces nothing either way reports an error.
"""

from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi.testclient import TestClient

from app.models.abstraction import BaseModelClient, ChatMessage, ChatResponse, StreamChunk
from app.routers.ws_chat import EMPTY_REPLY_RETRY_MAX_TOKENS


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "empty-stream-data"))
    monkeypatch.setenv("ATLAS_MODEL_PROVIDER", "ollama")

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


class SilentStreamClient(BaseModelClient):
    """Streams nothing, the way a reasoning model spending its whole budget
    on thinking does. Answers normally when asked without streaming."""

    completion_text = "Recovered answer."
    completions = 0
    last_max_tokens = 0

    def __init__(self, settings):
        pass

    async def chat_complete(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        SilentStreamClient.completions += 1
        SilentStreamClient.last_max_tokens = kwargs.get("max_tokens", 0)
        return ChatResponse(content=self.completion_text)

    async def chat_stream(self, messages: list[ChatMessage], **kwargs) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content="", done=True)

    async def close(self) -> None:
        return None

    def get_provider_name(self) -> str:
        return "silent"


class MuteClient(SilentStreamClient):
    """Produces nothing at all, however it is asked."""

    completion_text = ""


def _events(ws, content: str) -> list[dict]:
    ws.send_text(json.dumps({"content": content, "mode": "teaching"}))
    seen = []
    while True:
        event = ws.receive_json()
        seen.append(event)
        if event["type"] in ("done", "error"):
            return seen


def _session(client: TestClient) -> tuple[str, str]:
    profile_id = client.post(
        "/api/v1/profiles", json={"name": "Learner", "profile_type": "GATE"}
    ).json()["data"]["id"]
    session_id = client.post(
        f"/api/v1/profiles/{profile_id}/sessions", json={"title": "Studying"}
    ).json()["data"]["id"]
    return profile_id, session_id


def test_an_empty_stream_is_retried_without_streaming(tmp_path, monkeypatch):
    """The answer still arrives, rather than the turn ending in silence."""
    app = _make_app(tmp_path, monkeypatch)
    monkeypatch.setattr("app.routers.ws_chat.get_model_client", SilentStreamClient)
    SilentStreamClient.completions = 0

    with TestClient(app) as client:
        profile_id, session_id = _session(client)
        with client.websocket_connect(f"/ws/chat/{profile_id}/{session_id}") as ws:
            events = _events(ws, "Teach me encoding.")

        assert events[-1]["type"] == "done", events
        assert events[-1]["content"] == "Recovered answer."
        assert SilentStreamClient.completions == 1, "the fallback must be asked exactly once"
        # Retrying on the original budget reproduces the failure: a reasoning
        # model's thinking is charged against the same ceiling as its answer.
        assert SilentStreamClient.last_max_tokens >= EMPTY_REPLY_RETRY_MAX_TOKENS, (
            "the retry was given no more room than the attempt that came back empty"
        )

        # And it is a real message in the thread, not just something on screen.
        messages = client.get(
            f"/api/v1/profiles/{profile_id}/sessions/{session_id}"
        ).json()["data"]["messages"]
        assert [m["content"] for m in messages if m["role"] == "assistant"] == [
            "Recovered answer."
        ]


def test_a_model_that_returns_nothing_reports_an_error(tmp_path, monkeypatch):
    """No answer is a failed turn, and has to say so."""
    app = _make_app(tmp_path, monkeypatch)
    monkeypatch.setattr("app.routers.ws_chat.get_model_client", MuteClient)

    with TestClient(app) as client:
        profile_id, session_id = _session(client)
        with client.websocket_connect(f"/ws/chat/{profile_id}/{session_id}") as ws:
            events = _events(ws, "Teach me encoding.")

    final = events[-1]
    assert final["type"] == "error", f"an empty turn was reported as success: {events}"
    assert "empty response" in final["content"].lower()
