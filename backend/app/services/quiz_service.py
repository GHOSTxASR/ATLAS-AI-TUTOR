from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.repositories.analytics_repo import AnalyticsRepository
from app.db.repositories.memory_repo import MemoryRepository
from app.db.repositories.profile_repo import ProfileRepository
from app.db.repositories.quiz_repo import QuizRepository
from app.db.repositories.roadmap_repo import RoadmapRepository
from app.exceptions import AtlasError
from app.models.abstraction import ChatMessage
from app.models.provider_factory import get_model_client
from app.models.resilience import provider_error_from
from app.services.quiz_grading import (
    GradedAnswer,
    compute_letter_grade,
    grade_answer,
    overall_feedback,
)
from app.schemas.quiz import (
    AssessmentGenerateRequest,
    MasteryNodeUpdate,
    QuestionResult,
    QuizAttemptSummary,
    QuizGenerateRequest,
    QuizOption,
    QuizQuestionPublic,
    QuizResponse,
    QuizResultResponse,
    QuizSubmitRequest,
)
from app.utils.date_utils import elapsed_study_minutes
from app.utils.text_utils import extract_json_payload

logger = logging.getLogger(__name__)

#: A score at or above this is worth remembering as a strength; below
#: WEAKNESS_THRESHOLD, as a gap to revisit. The band between is ordinary
#: partial credit and says nothing worth storing.
STRENGTH_THRESHOLD = 0.85
WEAKNESS_THRESHOLD = 0.60

#: How much of the previous mastery survives a new quiz (an EMA).
MASTERY_WEIGHT = 0.5

#: Score at which a topic counts as done and stops blocking its successors.
COMPLETION_THRESHOLD = 0.8


def _build_question_prompt(topics: list[str], difficulty: str, question_count: int) -> str:
    """Ask for a mixed paper, showing the exact JSON shape expected back."""
    topics_str = ", ".join(topics)
    return (
        f"You are a rigorous academic assessment engine. Generate an assessment "
        f"covering topics: [{topics_str}].\n"
        f"Difficulty level: '{difficulty}'. Total questions needed: {question_count}.\n"
        "Include a balanced mix of:\n"
        "1. 'mcq': Multiple-choice with 4 distinct options ('A', 'B', 'C', 'D') "
        "and 1 correct answer.\n"
        "2. 'numerical': Calculation problem with 'target_value' (number) and "
        "'tolerance' (e.g. 0.05).\n"
        "3. 'short_answer': Analytical/conceptual question with an explicit "
        "grading rubric.\n\n"
        "Return ONLY a valid JSON array matching this format:\n"
        "[\n"
        "  {\n"
        '    "id": "q1",\n'
        '    "question_type": "mcq",\n'
        f'    "topic_title": "{topics[0]}",\n'
        f'    "difficulty": "{difficulty}",\n'
        '    "prompt": "Question prompt?",\n'
        '    "options": [\n'
        '      {"id": "A", "text": "Option A"},\n'
        '      {"id": "B", "text": "Option B"},\n'
        '      {"id": "C", "text": "Option C"},\n'
        '      {"id": "D", "text": "Option D"}\n'
        "    ],\n"
        '    "correct_answer": "A",\n'
        '    "explanation": "Explanation..."\n'
        "  }\n"
        "]"
    )


async def _request_questions(settings: Settings, prompt: str) -> list[dict[str, Any]]:
    """Ask the provider for a paper, or fail loudly.

    A quiz is only useful if a model actually wrote it. Substituting templated
    placeholder questions produced an assessment that tested nothing and
    reported a meaningless score, so every failure mode surfaces to the caller
    with the reason attached rather than degrading quietly.
    """
    questions: list[dict[str, Any]] = []
    try:
        client = get_model_client(settings)
        try:
            response = await client.chat_complete(
                messages=[
                    ChatMessage(
                        role="system",
                        content=(
                            "You create balanced academic assessment tests. "
                            "Return ONLY JSON."
                        ),
                    ),
                    ChatMessage(role="user", content=prompt),
                ],
                temperature=0.2,
                max_tokens=3500,
            )
            parsed = json.loads(extract_json_payload(response.content))
            if isinstance(parsed, list) and len(parsed) > 0:
                questions = parsed
        finally:
            await client.close()
    except ValueError as e:
        raise AtlasError(
            status_code=503, code="PROVIDER_NOT_CONFIGURED", message=str(e)
        ) from None
    except json.JSONDecodeError:
        raise AtlasError(
            status_code=502,
            code="PROVIDER_BAD_RESPONSE",
            message="The AI provider did not return a valid quiz. Try again.",
        ) from None
    except Exception as e:
        error = provider_error_from(e)
        logger.warning("Quiz generation failed: %s", error.message)
        raise AtlasError(
            status_code=502, code="PROVIDER_ERROR", message=error.message
        ) from None

    if not questions:
        raise AtlasError(
            status_code=502,
            code="PROVIDER_EMPTY_RESPONSE",
            message="The AI provider returned no quiz questions. Try again.",
        )
    return questions


class QuizService:
    """Orchestrates comprehensive assessment generation, multi-criteria grading, and automated mastery updates."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None):
        self.session = session
        self.settings = settings or get_settings()
        self.repo = QuizRepository(session)
        self.profile_repo = ProfileRepository(session)
        self.roadmap_repo = RoadmapRepository(session)
        self.analytics_repo = AnalyticsRepository(session)
        self.memory_repo = MemoryRepository(session)

    async def _require_profile(self, profile_id: str) -> None:
        profile = await self.profile_repo.get_by_id(profile_id)
        if not profile:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Profile not found")

    async def _get_owned_node(self, profile_id: str, node_id: str):
        node = await self.roadmap_repo.get_node(node_id)
        if not node or node.profile_id != profile_id:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Roadmap node not found")
        return node

    async def generate_quiz(self, profile_id: str, data: QuizGenerateRequest) -> QuizResponse:
        """Generate standard topic quiz."""
        await self._require_profile(profile_id)

        topic_title = data.topic_title or "General Curriculum Concepts"
        if data.roadmap_node_id:
            node = await self._get_owned_node(profile_id, data.roadmap_node_id)
            topic_title = node.title

        return await self._generate_questions_and_attempt(
            profile_id=profile_id,
            topics=[topic_title],
            roadmap_node_id=data.roadmap_node_id,
            mode=data.mode,
            question_count=data.question_count,
            time_limit_seconds=data.time_limit_seconds,
            difficulty=data.difficulty,
        )

    async def generate_assessment(
        self, profile_id: str, data: AssessmentGenerateRequest
    ) -> QuizResponse:
        """Generate comprehensive formal assessment across single or multiple topics."""
        await self._require_profile(profile_id)

        topics: list[str] = []
        roadmap_node_id: str | None = None

        if data.roadmap_node_ids and len(data.roadmap_node_ids) > 0:
            roadmap_node_id = data.roadmap_node_ids[0]
            for nid in data.roadmap_node_ids:
                node = await self._get_owned_node(profile_id, nid)
                topics.append(node.title)

        if not topics and data.topic_titles:
            topics = data.topic_titles

        if not topics and data.chapter_title:
            topics = [data.chapter_title]

        if not topics:
            # Gather all active roadmap topics
            active_roadmap = await self.roadmap_repo.get_active_roadmap(profile_id)
            if active_roadmap and active_roadmap.nodes:
                topics = [n.title for n in active_roadmap.nodes if n.node_type in ("topic", "bridge")][:10]

        if not topics:
            topics = ["Core Foundational Principles"]

        mode = "timed_assessment" if data.time_limit_seconds else "practice"
        return await self._generate_questions_and_attempt(
            profile_id=profile_id,
            topics=topics,
            roadmap_node_id=roadmap_node_id,
            mode=mode,
            question_count=data.question_count,
            time_limit_seconds=data.time_limit_seconds,
            difficulty=data.difficulty,
        )

    async def _generate_questions_and_attempt(
        self,
        profile_id: str,
        topics: list[str],
        roadmap_node_id: str | None,
        mode: str,
        question_count: int,
        time_limit_seconds: int | None,
        difficulty: str,
    ) -> QuizResponse:
        """Generate a paper, record the attempt, and return it without answers."""
        prompt = _build_question_prompt(topics, difficulty, question_count)
        questions = await _request_questions(self.settings, prompt)

        attempt = await self.repo.create_attempt(
            profile_id=profile_id,
            roadmap_node_id=roadmap_node_id,
            mode=mode,
            total_questions=len(questions),
            questions_json=json.dumps(questions),
            time_limit_seconds=time_limit_seconds,
        )

        # The public shape deliberately omits correct_answer, target_value and
        # rubric: the stored copy keeps them, the copy sent to the browser
        # does not.
        public_questions: list[QuizQuestionPublic] = []
        for q in questions:
            opts = [QuizOption(**o) for o in q.get("options", [])] if q.get("options") else None
            public_questions.append(
                QuizQuestionPublic(
                    id=str(q.get("id")),
                    question_type=q.get("question_type", "mcq"),
                    prompt=q.get("prompt", ""),
                    options=opts,
                    topic_title=q.get("topic_title", topics[0]),
                    difficulty=q.get("difficulty", difficulty),  # type: ignore
                )
            )

        return QuizResponse(
            id=attempt.id,
            profile_id=profile_id,
            roadmap_node_id=roadmap_node_id,
            mode=attempt.mode,
            total_questions=len(public_questions),
            time_limit_seconds=attempt.time_limit_seconds,
            difficulty=difficulty,
            questions=public_questions,
        )

    async def _grade_and_record(
        self,
        profile_id: str,
        attempt: Any,
        stored_questions: list[dict[str, Any]],
        answers_by_id: dict[str, str],
    ) -> tuple[list[QuestionResult], float, list[str], list[str]]:
        """Grade every answer, writing what it reveals to long-term memory.

        Mutates `stored_questions` in place with the score and feedback, which
        is what gets persisted back onto the attempt so a result page can be
        rebuilt later without re-grading.

        Returns the per-question results, the raw score total, and the
        strengths and weaknesses recorded.
        """
        question_results: list[QuestionResult] = []
        total_score_sum = 0.0
        strengths_recorded: list[str] = []
        weaknesses_recorded: list[str] = []

        for q in stored_questions:
            q_id = str(q.get("id"))
            q_topic = str(q.get("topic_title", "Concept"))
            prompt_text = q.get("prompt", "")
            user_ans = answers_by_id.get(q_id, "")

            graded = await grade_answer(self.settings, q, user_ans)
            total_score_sum += graded.score

            q["user_answer"] = user_ans
            q["score"] = graded.score
            q["feedback"] = graded.feedback
            q["error_category"] = graded.error_category

            await self._record_memory(profile_id, attempt.id, q_topic, prompt_text,
                                      user_ans, graded, strengths_recorded,
                                      weaknesses_recorded)

            question_results.append(
                QuestionResult(
                    question_id=q_id,
                    question_type=q.get("question_type", "mcq"),
                    prompt=prompt_text,
                    user_answer=user_ans,
                    correct_answer=str(q.get("correct_answer", "")).strip(),
                    is_correct=graded.is_correct,
                    score=round(graded.score, 2),
                    error_category=graded.error_category,
                    feedback=graded.feedback,
                    explanation=str(q.get("explanation", "")),
                    remediation_advice=graded.remediation,
                )
            )

        return question_results, total_score_sum, strengths_recorded, weaknesses_recorded

    async def _record_memory(
        self,
        profile_id: str,
        attempt_id: str,
        topic: str,
        prompt_text: str,
        user_answer: str,
        graded: GradedAnswer,
        strengths: list[str],
        weaknesses: list[str],
    ) -> None:
        """Note a clear strength or a clear weakness; say nothing about the middle.

        A weakness is only recorded when something was actually answered --
        a blank is evidence of running out of time, not of a misconception.
        """
        if graded.score >= STRENGTH_THRESHOLD:
            await self.memory_repo.create(
                profile_id=profile_id,
                category="strength",
                subject=topic,
                content=(
                    f"Demonstrated high mastery ({int(graded.score * 100)}%) "
                    f"in {topic}: {prompt_text[:80]}..."
                ),
                confidence=graded.score,
                source="quiz_assessment",
                source_id=attempt_id,
            )
            strengths.append(f"{topic}: Strong grasp")
        elif graded.score < WEAKNESS_THRESHOLD and user_answer:
            category = graded.error_category.replace("_", " ")
            await self.memory_repo.create(
                profile_id=profile_id,
                category="weakness",
                subject=topic,
                content=f"Struggled with {topic} ({category}): {graded.remediation}",
                confidence=0.85,
                source="quiz_assessment",
                source_id=attempt_id,
            )
            weaknesses.append(f"{topic}: {category}")

    async def _apply_mastery(
        self, profile_id: str, node_id: str, overall_score: float
    ) -> tuple[list[MasteryNodeUpdate], list[str], float]:
        """Move the topic's mastery toward this score and report what it unlocks.

        Mastery is an even blend of the old value and the new one, so a single
        bad quiz cannot erase a history of good ones and a single good quiz
        cannot certify a topic outright.
        """
        node = await self._get_owned_node(profile_id, node_id)
        old_mastery = node.mastery_score
        new_mastery = round(MASTERY_WEIGHT * old_mastery + (1 - MASTERY_WEIGHT) * overall_score, 2)

        node_fields: dict[str, Any] = {"mastery_score": new_mastery}
        if overall_score >= COMPLETION_THRESHOLD and node.status in ("not_started", "in_progress"):
            node_fields["status"] = "completed"
            node_fields["completed_at"] = datetime.now(timezone.utc)

        updated_node = await self.roadmap_repo.update_node(node, **node_fields)
        mastery_updates = [
            MasteryNodeUpdate(
                node_id=updated_node.id,
                node_title=updated_node.title,
                previous_mastery=old_mastery,
                new_mastery=new_mastery,
                status=updated_node.status,
                unlocked=True,
            )
        ]

        # A topic becomes reachable once every prerequisite is done or skipped.
        unlocked_nodes: list[str] = []
        active_roadmap = await self.roadmap_repo.get_active_roadmap(profile_id)
        if active_roadmap and active_roadmap.nodes:
            cleared = {
                n.id for n in active_roadmap.nodes if n.status in ("completed", "skipped")
            }
            for n in active_roadmap.nodes:
                if n.status == "completed":
                    continue
                incoming = [e.from_node_id for e in active_roadmap.edges if e.to_node_id == n.id]
                if incoming and all(dep in cleared for dep in incoming):
                    unlocked_nodes.append(n.title)

        return mastery_updates, unlocked_nodes, round(new_mastery - old_mastery, 2)

    async def submit_quiz(
        self, profile_id: str, attempt_id: str, data: QuizSubmitRequest
    ) -> QuizResultResponse:
        """Grade a submission, then fold what it says into the learner's state."""
        await self._require_profile(profile_id)

        attempt = await self.repo.get_attempt(attempt_id)
        if not attempt or attempt.profile_id != profile_id:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Quiz attempt not found")

        stored_questions: list[dict[str, Any]] = json.loads(attempt.questions_json)
        answers_by_id = {a.question_id: a.user_answer.strip() for a in data.answers}

        (
            question_results,
            total_score_sum,
            strengths_recorded,
            weaknesses_recorded,
        ) = await self._grade_and_record(profile_id, attempt, stored_questions, answers_by_id)

        total_questions = len(stored_questions)
        overall_score = round(total_score_sum / total_questions, 2) if total_questions > 0 else 0.0
        correct_count = sum(1 for r in question_results if r.is_correct)

        mastery_updates: list[MasteryNodeUpdate] = []
        unlocked_nodes: list[str] = []
        mastery_delta = 0.0
        if attempt.roadmap_node_id:
            mastery_updates, unlocked_nodes, mastery_delta = await self._apply_mastery(
                profile_id, attempt.roadmap_node_id, overall_score
            )

        letter_grade = compute_letter_grade(overall_score)

        # `value` is study *minutes* everywhere analytics reads it; storing the
        # 0-1 score here meant every quiz contributed int(0.85) = 0 minutes to
        # the study-time breakdown. The score lives in metadata.
        await self.analytics_repo.log_event(
            profile_id=profile_id,
            event_type="quiz_taken",
            entity_type="quiz",
            entity_id=attempt.id,
            value=elapsed_study_minutes(attempt.started_at),
            metadata_json=json.dumps({
                "score": overall_score,
                "letter_grade": letter_grade,
                "correct_count": correct_count,
                "total_questions": total_questions,
                "mode": attempt.mode,
            }),
        )

        attempt = await self.repo.save_results(
            attempt=attempt,
            score=overall_score,
            correct_count=correct_count,
            questions_json=json.dumps(stored_questions),
        )

        return QuizResultResponse(
            id=attempt.id,
            profile_id=profile_id,
            roadmap_node_id=attempt.roadmap_node_id,
            mode=attempt.mode,
            started_at=attempt.started_at,
            completed_at=attempt.completed_at,
            score=overall_score,
            letter_grade=letter_grade,
            total_questions=total_questions,
            correct_count=correct_count,
            time_limit_seconds=attempt.time_limit_seconds,
            question_results=question_results,
            mastery_updates=mastery_updates,
            strengths_recorded=strengths_recorded,
            weaknesses_recorded=weaknesses_recorded,
            unlocked_nodes=unlocked_nodes,
            overall_feedback=overall_feedback(overall_score),
            mastery_delta=mastery_delta,
        )

    async def get_quiz_result(self, profile_id: str, attempt_id: str) -> QuizResultResponse:
        """Fetch results of a past completed quiz attempt."""
        await self._require_profile(profile_id)
        attempt = await self.repo.get_attempt(attempt_id)
        if not attempt or attempt.profile_id != profile_id:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Quiz attempt not found")

        stored_questions = json.loads(attempt.questions_json)
        question_results: list[QuestionResult] = []
        for q in stored_questions:
            score = float(q.get("score", 0.0))
            question_results.append(
                QuestionResult(
                    question_id=str(q.get("id")),
                    question_type=q.get("question_type", "mcq"),
                    prompt=q.get("prompt", ""),
                    user_answer=q.get("user_answer", ""),
                    correct_answer=q.get("correct_answer", ""),
                    is_correct=score >= 0.7,
                    score=score,
                    error_category=q.get("error_category", "correct" if score >= 0.7 else "conceptual_misunderstanding"),
                    feedback=q.get("feedback", ""),
                    explanation=q.get("explanation", ""),
                    remediation_advice=q.get("remediation_advice", ""),
                )
            )

        score_val = attempt.score or 0.0
        return QuizResultResponse(
            id=attempt.id,
            profile_id=profile_id,
            roadmap_node_id=attempt.roadmap_node_id,
            mode=attempt.mode,
            started_at=attempt.started_at,
            completed_at=attempt.completed_at,
            score=score_val,
            letter_grade=compute_letter_grade(score_val),
            total_questions=attempt.total_questions,
            correct_count=attempt.correct_count or 0,
            time_limit_seconds=attempt.time_limit_seconds,
            question_results=question_results,
            overall_feedback="Detailed performance breakdown available.",
            mastery_delta=0.0,
        )

    async def get_quiz_history(self, profile_id: str) -> list[QuizAttemptSummary]:
        """List past quiz attempts, resolving each one's topic.

        Without a title the history could only be labelled by a slice of the
        attempt UUID ("Assessment #0bf811"), which tells the learner nothing
        about what was tested.
        """
        await self._require_profile(profile_id)
        attempts = await self.repo.list_by_profile(profile_id)

        node_titles: dict[str, str] = {}
        node_ids = {a.roadmap_node_id for a in attempts if a.roadmap_node_id}
        for node_id in node_ids:
            node = await self.roadmap_repo.get_node(node_id)
            if node and node.profile_id == profile_id:
                node_titles[node_id] = node.title

        summaries: list[QuizAttemptSummary] = []
        for attempt in attempts:
            summary = QuizAttemptSummary.model_validate(attempt)
            summary.topic_title = node_titles.get(attempt.roadmap_node_id or "")
            summaries.append(summary)
        return summaries
