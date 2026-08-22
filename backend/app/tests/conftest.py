"""Shared test configuration.

The suite runs without any AI provider credentials, so it opts in to the
deterministic offline embedding backend. This is deliberately explicit: the
production default is a real embeddings API, and a failure there raises rather
than silently substituting meaningless vectors.

``test_embedder.py::test_production_default_never_uses_hash_backend`` guards
the distinction.
"""

from __future__ import annotations

import json
import os
from typing import AsyncIterator

import pytest

from app.models.abstraction import BaseModelClient, ChatMessage, ChatResponse, StreamChunk

os.environ.setdefault("LEARNINGOS_EMBEDDING_BACKEND", "hash")


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    """Settings are lru_cached; tests monkeypatch env vars between cases."""
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class StubLLM(BaseModelClient):
    """Model client returning a fixed payload.

    Services no longer substitute generated filler when a provider fails, so
    tests that exercise orchestration must supply a model explicitly.
    """

    def __init__(self, content: str = "stub response") -> None:
        self._content = content

    async def chat_complete(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        return ChatResponse(content=self._content)

    async def chat_stream(self, messages: list[ChatMessage], **kwargs) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content=self._content, done=False)
        yield StreamChunk(content="", done=True)

    async def close(self) -> None:
        return None

    def get_provider_name(self) -> str:
        return "stub"


# Three questions covering every supported type, so grading paths are exercised.
STUB_QUIZ_QUESTIONS = [
    {
        "id": "q1",
        "question_type": "mcq",
        "topic_title": "Stub Topic",
        "difficulty": "medium",
        "prompt": "Which option is correct?",
        "options": [
            {"id": "A", "text": "Correct option"},
            {"id": "B", "text": "Wrong option"},
            {"id": "C", "text": "Wrong option"},
            {"id": "D", "text": "Wrong option"},
        ],
        "correct_answer": "A",
        "explanation": "A is correct.",
    },
    {
        "id": "q2",
        "question_type": "numerical",
        "topic_title": "Stub Topic",
        "difficulty": "medium",
        "prompt": "Compute 5 * 2.4",
        "target_value": 12.0,
        "tolerance": 0.05,
        "correct_answer": "12.0",
        "explanation": "5 * 2.4 = 12.0",
    },
    {
        "id": "q3",
        "question_type": "short_answer",
        "topic_title": "Stub Topic",
        "difficulty": "medium",
        "prompt": "Why do boundary conditions matter?",
        "rubric": "Mentions boundary conditions and errors.",
        "correct_answer": "Boundary conditions prevent errors.",
        "explanation": "Boundary handling avoids failures.",
    },
]


@pytest.fixture
def stub_quiz_llm(monkeypatch):
    """Give quiz_service a deterministic model response."""
    monkeypatch.setattr(
        "app.services.quiz_service.get_model_client",
        lambda s: StubLLM(json.dumps(STUB_QUIZ_QUESTIONS)),
    )
    return STUB_QUIZ_QUESTIONS


STUB_NOTE_MARKDOWN = (
    "# Stub Lesson Note\n\n"
    "## 1. Executive Conceptual Foundation\n"
    "A deterministic note body used where a test exercises note persistence.\n"
)


@pytest.fixture
def stub_notes_llm(monkeypatch):
    """Give notes_service a deterministic model response."""
    monkeypatch.setattr(
        "app.services.notes_service.get_model_client",
        lambda s: StubLLM(STUB_NOTE_MARKDOWN),
    )
    return STUB_NOTE_MARKDOWN


def uploaded_document(client, profile_id: str, document_id: str) -> dict:
    """Fetch a document after its background pipeline has run.

    Upload responds immediately with status "pending"; extraction, chunking and
    embedding happen in a FastAPI background task. TestClient runs those before
    returning, so a follow-up GET sees the settled state - mirroring what the
    frontend's status polling observes.
    """
    resp = client.get(f"/api/v1/profiles/{profile_id}/documents/{document_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]
