"""The unified prompt must respect its declared token budget.

`build_unified_context` accepted `max_context_tokens` and never applied it, so
the assembled prompt could grow past the model's context window and be rejected
outright on long sessions with many documents.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.pipelines.chunker import DocumentChunker
from app.rag.context_assembler import AssembledContext


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNINGOS_DATA_DIR", str(tmp_path / "budget-data"))
    monkeypatch.setenv("LEARNINGOS_EMBEDDING_BACKEND", "hash")

    from app.config import get_settings

    get_settings.cache_clear()
    from app.services.unified_context_service import UnifiedContextService

    svc = UnifiedContextService(session=AsyncMock(), settings=get_settings())

    profile = type("P", (), {"id": "p1", "name": "Learner", "profile_type": "JEE"})()
    svc.profile_repo.get_by_id = AsyncMock(return_value=profile)
    svc.roadmap_repo.get_active_roadmap = AsyncMock(return_value=None)
    svc.memory_repo.get_by_profile_id = AsyncMock(return_value=[])
    svc.memory_service.get_learner_profile_context = AsyncMock(return_value="")
    return svc


def _huge_context(tokens: int) -> AssembledContext:
    body = "lorem ipsum dolor sit amet " * tokens
    return AssembledContext(
        context_block=f"<CONTEXT>\n{body}\n</CONTEXT>",
        system_prompt="",
        citations=[],
        total_tokens=tokens,
        chunk_count=1,
    )


async def test_rag_receives_the_remaining_budget(service):
    """RAG must be told how much room the other pillars left."""
    captured: dict = {}

    async def _capture(**kwargs):
        captured.update(kwargs)
        return _huge_context(50)

    service.rag_pipeline.retrieve_and_assemble = _capture

    await service.build_unified_context(
        profile_id="p1", query="entropy", max_context_tokens=3000
    )

    assert "max_context_tokens" in captured, "the budget was never passed through"
    assert 0 < captured["max_context_tokens"] < 3000


async def test_prompt_stays_within_budget_with_a_large_document_context(service):
    service.rag_pipeline.retrieve_and_assemble = AsyncMock(return_value=_huge_context(80))

    ctx = await service.build_unified_context(
        profile_id="p1", query="entropy", max_context_tokens=2000
    )

    counted = DocumentChunker().count_tokens(ctx.system_prompt)
    assert counted <= 2000, f"prompt used {counted} tokens against a 2000 budget"


async def test_tiny_budget_skips_retrieval_rather_than_overflowing(service):
    service.rag_pipeline.retrieve_and_assemble = AsyncMock(return_value=_huge_context(100))

    ctx = await service.build_unified_context(
        profile_id="p1", query="entropy", max_context_tokens=120
    )

    service.rag_pipeline.retrieve_and_assemble.assert_not_awaited()
    assert ctx.citations == []
