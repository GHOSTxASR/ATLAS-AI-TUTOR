from __future__ import annotations

from typing import AsyncIterator
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base, Roadmap, RoadmapEdge, RoadmapNode
from app.db.repositories.memory_repo import MemoryRepository
from app.db.repositories.profile_repo import ProfileRepository
from app.models.abstraction import BaseModelClient, ChatMessage, ChatResponse, StreamChunk
from app.schemas.quiz import (
    AssessmentGenerateRequest,
    QuizSubmitRequest,
    QuizUserAnswer,
)
from app.services.quiz_service import QuizService


class MockAssessmentLLM(BaseModelClient):
    """Mock LLM for comprehensive assessment generation and diagnostic evaluation."""

    async def chat_complete(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        content = messages[-1].content
        if "evaluate the learner's answer" in content.lower():
            # Detailed evaluation response
            return ChatResponse(
                content='{\n'
                        '  "score": 0.85,\n'
                        '  "feedback": "Thorough understanding of recurrence relations with clear base case reasoning.",\n'
                        '  "error_category": "correct",\n'
                        '  "remediation": "Review edge cases for unconstrained recursion."\n'
                        '}'
            )
        else:
            # Assessment question generation
            return ChatResponse(
                content='[\n'
                        '  {\n'
                        '    "id": "q1",\n'
                        '    "question_type": "mcq",\n'
                        '    "topic_title": "Recursion",\n'
                        '    "difficulty": "hard",\n'
                        '    "prompt": "What is the stack depth for naive Fibonacci of N?",\n'
                        '    "options": [\n'
                        '      {"id": "A", "text": "O(N)"},\n'
                        '      {"id": "B", "text": "O(2^N)"},\n'
                        '      {"id": "C", "text": "O(log N)"},\n'
                        '      {"id": "D", "text": "O(1)"}\n'
                        '    ],\n'
                        '    "correct_answer": "A",\n'
                        '    "explanation": "The maximum recursion depth on the call stack is proportional to N."\n'
                        '  },\n'
                        '  {\n'
                        '    "id": "q2",\n'
                        '    "question_type": "short_answer",\n'
                        '    "topic_title": "Dynamic Programming",\n'
                        '    "difficulty": "hard",\n'
                        '    "prompt": "Explain the difference between optimal substructure and overlapping subproblems.",\n'
                        '    "rubric": "Define optimal substructure as optimal solution from subproblems, and overlapping subproblems as repeated computations.",\n'
                        '    "correct_answer": "Optimal substructure means global optimum is constructed from subproblem optima; overlapping subproblems means subproblems repeat.",\n'
                        '    "explanation": "Both properties are prerequisites for dynamic programming."\n'
                        '  }\n'
                        ']'
            )

    async def chat_stream(self, messages: list[ChatMessage], **kwargs) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content="", done=True)

    async def close(self) -> None:
        pass

    def get_provider_name(self) -> str:
        return "mock_assessment_llm"


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
async def test_assessment_generation_evaluation_and_mastery(async_db_session: AsyncSession, tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-data"))
    monkeypatch.setattr("app.services.quiz_service.get_model_client", lambda s: MockAssessmentLLM())
    monkeypatch.setattr("app.services.quiz_grading.get_model_client", lambda s: MockAssessmentLLM())

    from app.config import get_settings
    get_settings.cache_clear()

    profile_repo = ProfileRepository(async_db_session)
    profile = await profile_repo.create(name="Assessment Student", profile_type="GATE")

    # 1. Create Roadmap with prerequisite chain to test automatic unlock
    roadmap = Roadmap(profile_id=profile.id, title="Algorithms Exam", mode="strict", is_active=True)
    async_db_session.add(roadmap)
    await async_db_session.flush()

    node1 = RoadmapNode(
        roadmap_id=roadmap.id,
        profile_id=profile.id,
        title="Recursion",
        node_type="topic",
        status="in_progress",
        mastery_score=0.4,
    )
    node2 = RoadmapNode(
        roadmap_id=roadmap.id,
        profile_id=profile.id,
        title="Dynamic Programming",
        node_type="topic",
        status="not_started",
        mastery_score=0.0,
    )
    async_db_session.add_all([node1, node2])
    await async_db_session.flush()

    # Edge: Node 1 -> Node 2
    async_db_session.add(
        RoadmapEdge(
            roadmap_id=roadmap.id,
            from_node_id=node1.id,
            to_node_id=node2.id,
            edge_type="sequential",
        )
    )
    await async_db_session.commit()

    service = QuizService(session=async_db_session)

    # 2. Generate Assessment for Node 1
    gen_req = AssessmentGenerateRequest(
        assessment_type="chapter_test",
        roadmap_node_ids=[node1.id],
        difficulty="hard",
        question_count=2,
        time_limit_seconds=600,
    )
    assessment = await service.generate_assessment(profile.id, gen_req)

    assert assessment.total_questions == 2
    assert assessment.mode == "timed_assessment"
    assert assessment.difficulty == "hard"

    # 3. Submit Assessment
    sub_req = QuizSubmitRequest(
        answers=[
            QuizUserAnswer(question_id="q1", user_answer="A"),  # Correct MCQ
            QuizUserAnswer(question_id="q2", user_answer="Optimal solutions compose into global solutions."),  # Short answer evaluated by LLM
        ]
    )
    eval_result = await service.submit_quiz(profile.id, assessment.id, sub_req)

    # 4. Verify Automatic Learning Evaluation & Mastery
    assert eval_result.score >= 0.85
    assert eval_result.letter_grade in ("A+", "A")
    assert len(eval_result.mastery_updates) == 1
    assert eval_result.mastery_updates[0].new_mastery > 0.4
    assert eval_result.mastery_updates[0].status == "completed"

    # 5. Verify Long-term Memory was reinforced
    memory_repo = MemoryRepository(async_db_session)
    strengths = await memory_repo.get_by_profile_id(profile.id, category="strength")
    assert len(strengths) >= 1
    assert "Recursion" in strengths[0].subject or "Recursion" in strengths[0].content

    # 6. Verify Downstream Node was detected for unlock
    assert len(eval_result.unlocked_nodes) >= 1
    assert "Dynamic Programming" in eval_result.unlocked_nodes[0]
