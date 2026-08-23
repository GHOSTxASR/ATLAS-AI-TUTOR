from __future__ import annotations

from typing import AsyncIterator
import pytest
from fastapi.testclient import TestClient

from app.models.abstraction import BaseModelClient, ChatMessage, ChatResponse, StreamChunk
from app.rag.pipeline import RAGPipeline


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-data"))

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


def _create_profile(client: TestClient) -> str:
    response = client.post(
        "/api/v1/profiles",
        json={"name": "RAG Test Profile", "profile_type": "JEE"},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


class MockLLMClient(BaseModelClient):
    """Mock LLM client for chat and streaming."""

    def __init__(self, *args, **kwargs):
        pass

    async def chat_complete(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        return ChatResponse(content="According to [1], deadlocks occur when 4 conditions hold.")

    async def chat_stream(self, messages: list[ChatMessage], **kwargs) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content="According to [1], ", done=False)
        yield StreamChunk(content="deadlocks require mutual exclusion.", done=False)
        yield StreamChunk(content="", done=True)

    async def close(self) -> None:
        pass

    def get_provider_name(self) -> str:
        return "mock"


@pytest.mark.asyncio
async def test_rag_pipeline_retrieve_and_assemble(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _create_profile(client)

        content = (
            b"Operating System Deadlocks:\n"
            b"A deadlock occurs when processes are blocked because each process holds a resource "
            b"and waits for another resource held by another process. "
            b"The Banker's algorithm is a deadlock avoidance algorithm developed by Edsger Dijkstra."
        )

        upload = client.post(
            f"/api/v1/profiles/{profile_id}/documents",
            files={"file": ("os_deadlocks.txt", content, "text/plain")},
        )
        assert upload.status_code == 201

        from app.config import get_settings
        settings = get_settings()
        pipeline = RAGPipeline(settings=settings)

        assembled = await pipeline.retrieve_and_assemble(
            profile_id=profile_id,
            query="Explain deadlock conditions and Banker's algorithm",
            top_k_retrieve=5,
            top_k_final=3,
        )

        assert assembled.chunk_count >= 1
        assert "<CONTEXT>" in assembled.system_prompt
        assert "os_deadlocks.txt" in assembled.system_prompt
        assert len(assembled.citations) >= 1
        assert assembled.citations[0].filename == "os_deadlocks.txt"


def test_ws_chat_emits_citations_with_rag(tmp_path, monkeypatch):
    monkeypatch.setattr("app.routers.ws_chat.get_model_client", lambda s: MockLLMClient())
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _create_profile(client)

        # 1. Upload document
        content = b"Calculus fundamentals: The derivative measures the sensitivity to change of a function value."
        upload = client.post(
            f"/api/v1/profiles/{profile_id}/documents",
            files={"file": ("calculus.txt", content, "text/plain")},
        )
        assert upload.status_code == 201

        # 2. Create chat session
        session_resp = client.post(
            f"/api/v1/profiles/{profile_id}/sessions",
            json={"title": "Calculus Q&A"},
        )
        assert session_resp.status_code == 201
        session_id = session_resp.json()["data"]["id"]

        # 3. Connect WebSocket and send question
        with client.websocket_connect(f"/ws/chat/{profile_id}/{session_id}") as ws:
            ws.send_json({"content": "What does a derivative measure in calculus?"})

            # Receive user_saved
            msg1 = ws.receive_json()
            assert msg1["type"] == "user_saved"

            # Receive citations
            msg2 = ws.receive_json()
            assert msg2["type"] == "citations"
            assert len(msg2["citations"]) >= 1
            assert msg2["citations"][0]["filename"] == "calculus.txt"

            # Receive chunks
            chunks_received = []
            while True:
                msg = ws.receive_json()
                if msg["type"] == "chunk":
                    chunks_received.append(msg["content"])
                elif msg["type"] == "done":
                    assert len(msg["content"]) > 0
                    break

            assert len(chunks_received) >= 1
