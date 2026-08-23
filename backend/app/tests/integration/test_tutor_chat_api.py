from __future__ import annotations

from typing import AsyncIterator

from fastapi.testclient import TestClient

from app.models.abstraction import BaseModelClient, ChatMessage, ChatResponse, StreamChunk
from app.models.resilience import ProviderError


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-data"))

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


def _create_profile(client: TestClient) -> str:
    response = client.post(
        "/api/v1/profiles",
        json={"name": "Tutor API Tester", "profile_type": "GATE"},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


class MockTutorLLM(BaseModelClient):
    """Stand-in model client returning a deterministic answer."""

    def __init__(self, *args, **kwargs):
        pass

    async def chat_complete(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        return ChatResponse(content="Recursion is a function defined in terms of itself.")

    async def chat_stream(self, messages: list[ChatMessage], **kwargs) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content="", done=True)

    async def close(self) -> None:
        return None

    def get_provider_name(self) -> str:
        return "mock"


class FailingLLM(MockTutorLLM):
    async def chat_complete(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        raise ProviderError(
            "The AI provider is overloaded right now. Try again in a moment.",
            provider="gemini",
            status_code=503,
            retryable=True,
        )


class EmptyLLM(MockTutorLLM):
    async def chat_complete(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        return ChatResponse(content="   ")


def test_tutor_chat_api_modes(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "app.services.tutor_orchestrator.get_model_client", lambda s: MockTutorLLM()
    )

    with TestClient(app) as client:
        profile_id = _create_profile(client)

        for mode in ["teaching", "revision", "summary", "general_knowledge"]:
            resp = client.post(
                f"/api/v1/profiles/{profile_id}/tutor/chat",
                json={
                    "content": f"Explain recursion fundamentals in {mode} mode.",
                    "mode": mode,
                },
            )
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["mode"] == mode
            assert data["content"] == "Recursion is a function defined in terms of itself."
            assert "session_id" in data


def test_tutor_chat_reports_provider_failure_instead_of_fabricating(tmp_path, monkeypatch):
    """A provider outage must surface as an error, never as generated filler.

    Regression: the orchestrator caught every exception and returned hardcoded
    'teaching' boilerplate, so students received confident-looking text that no
    model had produced.
    """
    app = _make_app(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "app.services.tutor_orchestrator.get_model_client", lambda s: FailingLLM()
    )

    with TestClient(app) as client:
        profile_id = _create_profile(client)
        resp = client.post(
            f"/api/v1/profiles/{profile_id}/tutor/chat",
            json={"content": "Explain recursion.", "mode": "teaching"},
        )

    assert resp.status_code == 502
    body = resp.json()
    assert body["data"] is None
    assert body["error"]["code"] == "PROVIDER_ERROR"
    assert "overloaded" in body["error"]["message"]
    # The old canned fallback must be gone for good.
    assert "Core Concept" not in resp.text
    assert "assembly line" not in resp.text


def test_tutor_chat_reports_missing_provider_configuration(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)

    def _no_provider(_settings):
        raise ValueError("No Gemini API key configured. Set it on the Settings page.")

    monkeypatch.setattr("app.services.tutor_orchestrator.get_model_client", _no_provider)

    with TestClient(app) as client:
        profile_id = _create_profile(client)
        resp = client.post(
            f"/api/v1/profiles/{profile_id}/tutor/chat",
            json={"content": "Explain recursion.", "mode": "teaching"},
        )

    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "PROVIDER_NOT_CONFIGURED"
    assert "Settings page" in resp.json()["error"]["message"]


def test_tutor_chat_rejects_empty_model_response(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    monkeypatch.setattr("app.services.tutor_orchestrator.get_model_client", lambda s: EmptyLLM())

    with TestClient(app) as client:
        profile_id = _create_profile(client)
        resp = client.post(
            f"/api/v1/profiles/{profile_id}/tutor/chat",
            json={"content": "Explain recursion.", "mode": "teaching"},
        )

    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "PROVIDER_EMPTY_RESPONSE"
