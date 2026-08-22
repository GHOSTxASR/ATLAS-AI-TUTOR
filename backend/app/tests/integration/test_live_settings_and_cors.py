"""Settings changes must apply mid-session, and CORS must not be wide open."""

from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi.testclient import TestClient

from app.models.abstraction import BaseModelClient, ChatMessage, ChatResponse, StreamChunk


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNINGOS_DATA_DIR", str(tmp_path / "live-settings-data"))

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


class EchoModelClient(BaseModelClient):
    """Streams back whichever model name the settings currently name."""

    def __init__(self, settings):
        self._model = settings.model.chat_model

    async def chat_complete(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        return ChatResponse(content=self._model)

    async def chat_stream(self, messages: list[ChatMessage], **kwargs) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content=self._model, done=False)
        yield StreamChunk(content="", done=True)

    async def close(self) -> None:
        return None

    def get_provider_name(self) -> str:
        return "echo"


def test_model_change_applies_without_reconnecting(tmp_path, monkeypatch):
    """Regression: the socket pinned settings at connect time.

    Changing provider/model/API key on the Settings page had no effect until
    the user reloaded the page.
    """
    monkeypatch.setenv("LEARNINGOS_MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("LEARNINGOS_CHAT_MODEL", "model-before")
    app = _make_app(tmp_path, monkeypatch)
    monkeypatch.setattr("app.routers.ws_chat.get_model_client", EchoModelClient)

    with TestClient(app) as client:
        profile_id = client.post(
            "/api/v1/profiles", json={"name": "Live", "profile_type": "JEE"}
        ).json()["data"]["id"]
        session_id = client.post(
            f"/api/v1/profiles/{profile_id}/sessions", json={"title": "s"}
        ).json()["data"]["id"]

        with client.websocket_connect(f"/ws/chat/{profile_id}/{session_id}") as ws:
            first = _one_turn(ws, "hello")
            assert first == "model-before"

            # Change the model while the socket stays open.
            from app.config import get_settings

            monkeypatch.setenv("LEARNINGOS_CHAT_MODEL", "model-after")
            get_settings.cache_clear()

            second = _one_turn(ws, "hello again")

    assert second == "model-after", "the open socket kept using the stale model"


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


def test_cors_does_not_allow_arbitrary_origins(tmp_path, monkeypatch):
    """`allow_origins=["*"]` with credentials would let any site call this API."""
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        hostile = client.options(
            "/api/v1/health",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        allowed = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert hostile.headers.get("access-control-allow-origin") != "https://evil.example"
    assert hostile.headers.get("access-control-allow-origin") != "*"
    # The Vite dev server must still work.
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
