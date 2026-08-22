from __future__ import annotations

from typing import AsyncIterator
from fastapi.testclient import TestClient

from app.models.abstraction import BaseModelClient, ChatMessage, ChatResponse, StreamChunk


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNINGOS_DATA_DIR", str(tmp_path / "learningos-data"))

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


def _create_profile(client: TestClient) -> str:
    response = client.post(
        "/api/v1/profiles",
        json={"name": "Memory API Profile", "profile_type": "GATE"},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


class RecordingLLMClient(BaseModelClient):
    """Mock LLM that records received messages for assertion."""

    last_received_messages: list[ChatMessage] = []

    async def chat_complete(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        RecordingLLMClient.last_received_messages = messages
        return ChatResponse(content="I see you have practiced this topic previously.")

    async def chat_stream(self, messages: list[ChatMessage], **kwargs) -> AsyncIterator[StreamChunk]:
        RecordingLLMClient.last_received_messages = messages
        yield StreamChunk(content="I will tailor this explanation based on your profile.", done=False)
        yield StreamChunk(content="", done=True)

    async def close(self) -> None:
        pass

    def get_provider_name(self) -> str:
        return "recording_mock"


def test_memory_crud_api_flow(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _create_profile(client)

        # 1. Create manual memory
        create_resp = client.post(
            f"/api/v1/profiles/{profile_id}/memory",
            json={
                "category": "weakness",
                "subject": "Linear Algebra",
                "content": "Struggles with eigenvalue matrix transformations",
                "confidence": 0.85,
            },
        )
        assert create_resp.status_code == 201
        mem1 = create_resp.json()["data"]
        mem1_id = mem1["id"]
        assert mem1["category"] == "weakness"
        assert mem1["subject"] == "Linear Algebra"
        assert mem1["confidence"] == 0.85

        # 2. Create another memory
        create_resp2 = client.post(
            f"/api/v1/profiles/{profile_id}/memory",
            json={
                "category": "preference",
                "subject": "General",
                "content": "Prefers visual geometric diagrams",
                "confidence": 1.0,
            },
        )
        assert create_resp2.status_code == 201

        # 3. List all memories
        list_resp = client.get(f"/api/v1/profiles/{profile_id}/memory")
        assert list_resp.status_code == 200
        assert len(list_resp.json()["data"]) == 2

        # 4. List with category filter
        weakness_resp = client.get(f"/api/v1/profiles/{profile_id}/memory?category=weakness")
        assert weakness_resp.status_code == 200
        assert len(weakness_resp.json()["data"]) == 1
        assert weakness_resp.json()["data"][0]["id"] == mem1_id

        # 5. Get single memory
        get_resp = client.get(f"/api/v1/profiles/{profile_id}/memory/{mem1_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["id"] == mem1_id

        # 6. Patch memory
        patch_resp = client.patch(
            f"/api/v1/profiles/{profile_id}/memory/{mem1_id}",
            json={"confidence": 0.95, "content": "Mastered eigenvalue calculations"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["data"]["confidence"] == 0.95
        assert patch_resp.json()["data"]["content"] == "Mastered eigenvalue calculations"

        # 7. Delete memory
        del_resp = client.delete(f"/api/v1/profiles/{profile_id}/memory/{mem1_id}")
        assert del_resp.status_code == 200

        # Verify deletion
        list_after_del = client.get(f"/api/v1/profiles/{profile_id}/memory")
        assert len(list_after_del.json()["data"]) == 1


def test_chat_remembers_learner_profile_memories(tmp_path, monkeypatch):
    monkeypatch.setattr("app.routers.ws_chat.get_model_client", lambda s: RecordingLLMClient())
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _create_profile(client)

        # 1. Create learner memory
        client.post(
            f"/api/v1/profiles/{profile_id}/memory",
            json={
                "category": "weakness",
                "subject": "Trees",
                "content": "Confuses AVL tree rotations",
                "confidence": 0.9,
            },
        )

        # 2. Start chat session
        session_resp = client.post(
            f"/api/v1/profiles/{profile_id}/sessions",
            json={"title": "Data Structures Session"},
        )
        session_id = session_resp.json()["data"]["id"]

        # 3. Connect WebSocket and send question
        with client.websocket_connect(f"/ws/chat/{profile_id}/{session_id}") as ws:
            ws.send_json({"content": "Explain balanced search trees."})

            # Consume user_saved and streaming tokens
            while True:
                msg = ws.receive_json()
                if msg["type"] == "done":
                    break

            # 4. Verify that RecordingLLMClient received system prompt containing <LEARNER_PROFILE>
            recorded_system = next(
                (m.content for m in RecordingLLMClient.last_received_messages if m.role == "system"), ""
            )
            assert "<LEARNER_PROFILE>" in recorded_system
            assert "Confuses AVL tree rotations" in recorded_system
