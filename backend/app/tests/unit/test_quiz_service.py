from __future__ import annotations

from typing import AsyncIterator
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base, Roadmap, RoadmapNode
from app.db.repositories.profile_repo import ProfileRepository
from app.exceptions import AtlasError
from app.models.abstraction import BaseModelClient, ChatMessage, ChatResponse, StreamChunk
from app.schemas.quiz import QuizGenerateRequest, QuizSubmitRequest, QuizUserAnswer
from app.services.quiz_service import QuizService


class MockQuizLLM(BaseModelClient):
    """Mock LLM for quiz generation and short answer evaluation."""

    async def chat_complete(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        content = messages[-1].content
        if "learner's answer" in content.lower() or "evaluate" in content.lower() or "grade" in content.lower():
            # Grading short answer
            return ChatResponse(content='{"score": 0.9, "feedback": "Clear explanation of boundary conditions.", "error_category": "correct", "remediation": "Solid."}')
        else:
            # Generating quiz questions
            return ChatResponse(
                content='[\n'
                        '  {\n'
                        '    "id": "q1",\n'
                        '    "question_type": "mcq",\n'
                        '    "prompt": "What is the time complexity of binary search?",\n'
                        '    "options": [\n'
                        '      {"id": "A", "text": "O(log n)"},\n'
                        '      {"id": "B", "text": "O(n)"},\n'
                        '      {"id": "C", "text": "O(n log n)"},\n'
                        '      {"id": "D", "text": "O(1)"}\n'
                        '    ],\n'
                        '    "correct_answer": "A",\n'
                        '    "explanation": "Binary search divides the search interval in half each step."\n'
                        '  },\n'
                        '  {\n'
                        '    "id": "q2",\n'
                        '    "question_type": "numerical",\n'
                        '    "prompt": "Calculate log2(32).",\n'
                        '    "target_value": 5.0,\n'
                        '    "tolerance": 0.05,\n'
                        '    "correct_answer": "5.0",\n'
                        '    "explanation": "2^5 = 32, so log2(32) = 5."\n'
                        '  },\n'
                        '  {\n'
                        '    "id": "q3",\n'
                        '    "question_type": "short_answer",\n'
                        '    "prompt": "Explain why binary search requires a sorted array.",\n'
                        '    "rubric": "Must mention monotonic order enabling elimination of half the elements.",\n'
                        '    "correct_answer": "Sorting enables deterministic elimination of half the remaining elements each step.",\n'
                        '    "explanation": "Without sorted order, we cannot determine which half contains the target."\n'
                        '  }\n'
                        ']'
            )

    async def chat_stream(self, messages: list[ChatMessage], **kwargs) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content="", done=True)

    async def close(self) -> None:
        pass

    def get_provider_name(self) -> str:
        return "mock_quiz_llm"


@pytest.fixture
async def async_db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_quiz_generate_and_scoring_flow(async_db_session: AsyncSession, tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-data"))
    monkeypatch.setattr("app.services.quiz_service.get_model_client", lambda s: MockQuizLLM())
    monkeypatch.setattr("app.services.quiz_grading.get_model_client", lambda s: MockQuizLLM())

    from app.config import get_settings
    get_settings.cache_clear()

    profile_repo = ProfileRepository(async_db_session)
    profile = await profile_repo.create(name="Quiz Master", profile_type="GATE")

    # 1. Create a Roadmap and RoadmapNode to test mastery score updates
    roadmap = Roadmap(profile_id=profile.id, title="Algorithms", mode="strict", is_active=True)
    async_db_session.add(roadmap)
    await async_db_session.flush()

    node = RoadmapNode(
        roadmap_id=roadmap.id,
        profile_id=profile.id,
        title="Binary Search",
        node_type="topic",
        status="in_progress",
        mastery_score=0.4,
    )
    async_db_session.add(node)
    await async_db_session.commit()

    service = QuizService(session=async_db_session)

    # 2. Generate Quiz
    gen_req = QuizGenerateRequest(
        roadmap_node_id=node.id,
        mode="practice",
        question_count=3,
    )
    quiz_resp = await service.generate_quiz(profile.id, gen_req)

    assert quiz_resp.total_questions == 3
    assert len(quiz_resp.questions) == 3
    q_types = [q.question_type for q in quiz_resp.questions]
    assert "mcq" in q_types
    assert "numerical" in q_types
    assert "short_answer" in q_types

    # 3. Submit Answers
    # q1 (MCQ): "A" (Correct)
    # q2 (Numerical): "5.0" (Correct)
    # q3 (Short answer): "Sorting allows discarding half the elements." (Correct via mock LLM)
    submit_req = QuizSubmitRequest(
        answers=[
            QuizUserAnswer(question_id="q1", user_answer="A"),
            QuizUserAnswer(question_id="q2", user_answer="5.0"),
            QuizUserAnswer(question_id="q3", user_answer="Sorting allows discarding half the search space."),
        ]
    )
    result = await service.submit_quiz(profile.id, quiz_resp.id, submit_req)

    assert result.total_questions == 3
    assert result.correct_count == 3
    assert result.score >= 0.8
    assert result.mastery_delta > 0

    # 4. Verify node mastery updated in database
    await async_db_session.refresh(node)
    assert node.mastery_score > 0.4
    assert node.status == "completed"

    # 5. Verify history and results endpoints
    history = await service.get_quiz_history(profile.id)
    assert len(history) == 1
    assert history[0].score is not None

    past_result = await service.get_quiz_result(profile.id, quiz_resp.id)
    assert past_result.score == result.score


@pytest.mark.asyncio
async def test_quiz_rejects_roadmap_node_from_another_profile(async_db_session: AsyncSession):
    profile_repo = ProfileRepository(async_db_session)
    owner = await profile_repo.create(name="Node Owner", profile_type="GATE")
    other_profile = await profile_repo.create(name="Other Learner", profile_type="GATE")
    roadmap = Roadmap(profile_id=owner.id, title="Private roadmap", mode="strict", is_active=True)
    async_db_session.add(roadmap)
    await async_db_session.flush()
    node = RoadmapNode(
        roadmap_id=roadmap.id,
        profile_id=owner.id,
        title="Private topic",
        node_type="topic",
    )
    async_db_session.add(node)
    await async_db_session.commit()

    service = QuizService(session=async_db_session)

    with pytest.raises(AtlasError) as error:
        await service.generate_quiz(
            other_profile.id,
            QuizGenerateRequest(roadmap_node_id=node.id),
        )

    assert error.value.status_code == 404
