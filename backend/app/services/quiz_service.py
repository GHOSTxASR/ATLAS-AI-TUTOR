from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.repositories.analytics_repo import AnalyticsRepository
from app.db.repositories.memory_repo import MemoryRepository
from app.db.repositories.profile_repo import ProfileRepository
from app.db.repositories.quiz_repo import QuizRepository
from app.db.repositories.roadmap_repo import RoadmapRepository
from app.exceptions import LearningOSError
from app.models.abstraction import ChatMessage
from app.models.provider_factory import get_model_client
from app.models.resilience import provider_error_from
from app.schemas.quiz import (
    AssessmentGenerateRequest,
    ErrorClassification,
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


def _compute_letter_grade(score: float) -> str:
    if score >= 0.90:
        return "A+"
    elif score >= 0.80:
        return "A"
    elif score >= 0.70:
        return "B"
    elif score >= 0.60:
        return "C"
    else:
        return "F"


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
            raise LearningOSError(status_code=404, code="NOT_FOUND", message="Profile not found")

    async def _get_owned_node(self, profile_id: str, node_id: str):
        node = await self.roadmap_repo.get_node(node_id)
        if not node or node.profile_id != profile_id:
            raise LearningOSError(status_code=404, code="NOT_FOUND", message="Roadmap node not found")
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
        """Core AI question generator for quizzes and multi-topic assessments."""
        topics_str = ", ".join(topics)
        prompt = (
            f"You are a rigorous academic assessment engine. Generate an assessment covering topics: [{topics_str}].\n"
            f"Difficulty level: '{difficulty}'. Total questions needed: {question_count}.\n"
            "Include a balanced mix of:\n"
            "1. 'mcq': Multiple-choice with 4 distinct options ('A', 'B', 'C', 'D') and 1 correct answer.\n"
            "2. 'numerical': Calculation problem with 'target_value' (number) and 'tolerance' (e.g. 0.05).\n"
            "3. 'short_answer': Analytical/conceptual question with an explicit grading rubric.\n\n"
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

        # A quiz is only useful if a model actually wrote it. Substituting
        # templated placeholder questions produced an assessment that tested
        # nothing and reported a meaningless score, so failures are surfaced.
        questions: list[dict[str, Any]] = []
        try:
            client = get_model_client(self.settings)
            try:
                response = await client.chat_complete(
                    messages=[
                        ChatMessage(role="system", content="You create balanced academic assessment tests. Return ONLY JSON."),
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
            raise LearningOSError(
                status_code=503, code="PROVIDER_NOT_CONFIGURED", message=str(e)
            ) from None
        except json.JSONDecodeError:
            raise LearningOSError(
                status_code=502,
                code="PROVIDER_BAD_RESPONSE",
                message="The AI provider did not return a valid quiz. Try again.",
            ) from None
        except Exception as e:
            error = provider_error_from(e)
            logger.warning("Quiz generation failed: %s", error.message)
            raise LearningOSError(
                status_code=502, code="PROVIDER_ERROR", message=error.message
            ) from None

        if not questions:
            raise LearningOSError(
                status_code=502,
                code="PROVIDER_EMPTY_RESPONSE",
                message="The AI provider returned no quiz questions. Try again.",
            )

        # Persist attempt
        attempt = await self.repo.create_attempt(
            profile_id=profile_id,
            roadmap_node_id=roadmap_node_id,
            mode=mode,
            total_questions=len(questions),
            questions_json=json.dumps(questions),
            time_limit_seconds=time_limit_seconds,
        )

        # Format public response
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

    async def submit_quiz(
        self, profile_id: str, attempt_id: str, data: QuizSubmitRequest
    ) -> QuizResultResponse:
        """Comprehensive evaluation of answers, mastery synchronization, and memory reinforcement."""
        await self._require_profile(profile_id)

        attempt = await self.repo.get_attempt(attempt_id)
        if not attempt or attempt.profile_id != profile_id:
            raise LearningOSError(status_code=404, code="NOT_FOUND", message="Quiz attempt not found")

        stored_questions: list[dict[str, Any]] = json.loads(attempt.questions_json)
        answers_by_id = {a.question_id: a.user_answer.strip() for a in data.answers}

        question_results: list[QuestionResult] = []
        total_score_sum = 0.0
        strengths_recorded: list[str] = []
        weaknesses_recorded: list[str] = []

        for q in stored_questions:
            q_id = str(q.get("id"))
            q_type = q.get("question_type", "mcq")
            q_topic = str(q.get("topic_title", "Concept"))
            prompt_text = q.get("prompt", "")
            user_ans = answers_by_id.get(q_id, "")
            correct_ans = str(q.get("correct_answer", "")).strip()
            explanation = str(q.get("explanation", ""))

            q_score = 0.0
            feedback = ""
            remediation = ""
            error_cat: ErrorClassification = "correct"
            is_correct = False

            if q_type == "mcq":
                is_correct = user_ans.upper() == correct_ans.upper()
                if is_correct:
                    q_score = 1.0
                    error_cat = "correct"
                    feedback = f"Correct! Option {correct_ans} is right."
                    remediation = "Solid understanding demonstrated."
                else:
                    q_score = 0.0
                    error_cat = "conceptual_misunderstanding"
                    feedback = f"Incorrect. Correct answer is {correct_ans}."
                    remediation = f"Review foundational rules of {q_topic}."

            elif q_type == "numerical":
                target_val = float(q.get("target_value") or correct_ans or 0.0)
                tolerance = float(q.get("tolerance") or 0.05)

                try:
                    num_match = re.search(r"[-+]?\d*\.?\d+", user_ans)
                    if num_match:
                        user_val = float(num_match.group())
                        diff = abs(user_val - target_val)
                        if diff <= tolerance or (target_val != 0 and diff / abs(target_val) <= tolerance):
                            is_correct = True
                            q_score = 1.0
                            error_cat = "correct"
                            feedback = f"Accurate calculation ({user_val} ≈ {target_val})."
                            remediation = "Calculation verified."
                        else:
                            is_correct = False
                            q_score = 0.0
                            error_cat = "calculation_error"
                            feedback = f"Incorrect value {user_val}. Target was {target_val}."
                            remediation = f"Double check formulas and arithmetic constants in {q_topic}."
                    else:
                        error_cat = "incomplete_answer"
                        feedback = f"No valid numerical answer found. Target was {target_val}."
                        remediation = "Enter a valid numeric value."
                except Exception:
                    error_cat = "calculation_error"
                    feedback = f"Failed to parse numerical value. Target was {target_val}."
                    remediation = "Verify numerical syntax."

            elif q_type == "short_answer":
                rubric = str(q.get("rubric", ""))
                q_score, feedback, error_cat, remediation = await self._evaluate_short_answer_detailed(
                    prompt_text, user_ans, correct_ans, rubric, q_topic
                )
                is_correct = q_score >= 0.7

            total_score_sum += q_score
            q["user_answer"] = user_ans
            q["score"] = q_score
            q["feedback"] = feedback
            q["error_category"] = error_cat

            # Record Long-Term Memory
            if q_score >= 0.85:
                strength_msg = f"Demonstrated high mastery ({int(q_score*100)}%) in {q_topic}: {prompt_text[:80]}..."
                await self.memory_repo.create(
                    profile_id=profile_id,
                    category="strength",
                    subject=q_topic,
                    content=strength_msg,
                    confidence=q_score,
                    source="quiz_assessment",
                    source_id=attempt.id,
                )
                strengths_recorded.append(f"{q_topic}: Strong grasp")
            elif q_score < 0.60 and user_ans:
                weakness_msg = f"Struggled with {q_topic} ({error_cat.replace('_', ' ')}): {remediation}"
                await self.memory_repo.create(
                    profile_id=profile_id,
                    category="weakness",
                    subject=q_topic,
                    content=weakness_msg,
                    confidence=0.85,
                    source="quiz_assessment",
                    source_id=attempt.id,
                )
                weaknesses_recorded.append(f"{q_topic}: {error_cat.replace('_', ' ')}")

            question_results.append(
                QuestionResult(
                    question_id=q_id,
                    question_type=q_type,
                    prompt=prompt_text,
                    user_answer=user_ans,
                    correct_answer=correct_ans,
                    is_correct=is_correct,
                    score=round(q_score, 2),
                    error_category=error_cat,
                    feedback=feedback,
                    explanation=explanation,
                    remediation_advice=remediation,
                )
            )

        total_questions = len(stored_questions)
        overall_score = round(total_score_sum / total_questions, 2) if total_questions > 0 else 0.0
        correct_count = sum(1 for r in question_results if r.is_correct)
        letter_grade = _compute_letter_grade(overall_score)

        # 1. Update Roadmap Node mastery & unlocks
        mastery_updates: list[MasteryNodeUpdate] = []
        unlocked_nodes: list[str] = []
        mastery_delta = 0.0

        if attempt.roadmap_node_id:
            node = await self._get_owned_node(profile_id, attempt.roadmap_node_id)
            old_mastery = node.mastery_score
            new_mastery = round(0.5 * old_mastery + 0.5 * overall_score, 2)
            mastery_delta = round(new_mastery - old_mastery, 2)

            node_fields: dict[str, Any] = {"mastery_score": new_mastery}
            if overall_score >= 0.8 and node.status in ("not_started", "in_progress"):
                node_fields["status"] = "completed"
                node_fields["completed_at"] = datetime.now(timezone.utc)

            updated_node = await self.roadmap_repo.update_node(node, **node_fields)
            mastery_updates.append(
                MasteryNodeUpdate(
                    node_id=updated_node.id,
                    node_title=updated_node.title,
                    previous_mastery=old_mastery,
                    new_mastery=new_mastery,
                    status=updated_node.status,
                    unlocked=True,
                )
            )

            # Check if this completed topic unlocks downstream nodes
            active_roadmap = await self.roadmap_repo.get_active_roadmap(profile_id)
            if active_roadmap and active_roadmap.nodes:
                for n in active_roadmap.nodes:
                    if n.status != "completed":
                        # Check incoming prerequisites
                        incoming = [e.from_node_id for e in active_roadmap.edges if e.to_node_id == n.id]
                        completed_nodes = {cn.id for cn in active_roadmap.nodes if cn.status in ("completed", "skipped")}
                        if incoming and all(dep in completed_nodes for dep in incoming):
                            unlocked_nodes.append(n.title)

        # 2. Log Analytics Event.
        #    `value` is study *minutes* everywhere analytics reads it; storing
        #    the 0-1 score here meant every quiz contributed int(0.85) = 0
        #    minutes to the study-time breakdown. The score lives in metadata.
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

        # 3. Overall qualitative feedback
        if overall_score >= 0.9:
            overall_fb = "Exceptional mastery demonstrated! Excellent depth across all examined concepts."
        elif overall_score >= 0.8:
            overall_fb = "High proficiency demonstrated. Ready to proceed to downstream dependent topics."
        elif overall_score >= 0.6:
            overall_fb = "Satisfactory conceptual grounding with minor calculation or definition gaps."
        else:
            overall_fb = "Needs targeted review. Remediation items have been saved to your learner profile."

        # 4. Save attempt results
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
            overall_feedback=overall_fb,
            mastery_delta=mastery_delta,
        )

    async def _evaluate_short_answer_detailed(
        self, prompt: str, user_answer: str, reference_answer: str, rubric: str, topic: str
    ) -> tuple[float, str, ErrorClassification, str]:
        """Grade conceptual short answers with detailed diagnostic categorization."""
        if not user_answer.strip():
            return 0.0, "No answer provided.", "incomplete_answer", f"Provide a complete explanation for {topic}."

        eval_prompt = (
            f"Question: {prompt}\n"
            f"Topic: {topic}\n"
            f"Grading Rubric / Criteria: {rubric}\n"
            f"Reference Model Answer: {reference_answer}\n"
            f"Learner's Answer: {user_answer}\n\n"
            "Evaluate the learner's answer on accuracy, completeness, and reasoning.\n"
            "Return ONLY a JSON object with this format:\n"
            "{\n"
            '  "score": 0.85,\n'
            '  "feedback": "Concise 1-sentence evaluation.",\n'
            '  "error_category": "correct" | "conceptual_misunderstanding" | "incomplete_answer" | "misread_question",\n'
            '  "remediation": "Actionable advice on what to review."\n'
            "}"
        )

        try:
            client = get_model_client(self.settings)
            try:
                response = await client.chat_complete(
                    messages=[
                        ChatMessage(role="system", content="You are an expert academic evaluator. Return ONLY JSON."),
                        ChatMessage(role="user", content=eval_prompt),
                    ],
                    temperature=0.0,
                    max_tokens=350,
                )
                raw = extract_json_payload(response.content)

                grade = json.loads(raw)
                score = float(grade.get("score", 0.75))
                error_cat = grade.get("error_category", "correct" if score >= 0.7 else "conceptual_misunderstanding")
                return (
                    score,
                    str(grade.get("feedback", "Good conceptual explanation.")),
                    error_cat,  # type: ignore
                    str(grade.get("remediation", f"Review core principles of {topic}.")),
                )
            finally:
                await client.close()
        except Exception:
            # Fallback heuristic: keyword matching
            ref_words = set(re.findall(r"\w+", (reference_answer + " " + rubric).lower()))
            user_words = set(re.findall(r"\w+", user_answer.lower()))
            overlap = len(ref_words & user_words)
            score = min(1.0, round(overlap / max(1, len(ref_words) * 0.4), 2))
            error_cat: ErrorClassification = "correct" if score >= 0.7 else "incomplete_answer"
            return (
                score,
                "Evaluated based on key concept terminology.",
                error_cat,
                f"Review essential definitions in {topic}.",
            )

    async def get_quiz_result(self, profile_id: str, attempt_id: str) -> QuizResultResponse:
        """Fetch results of a past completed quiz attempt."""
        await self._require_profile(profile_id)
        attempt = await self.repo.get_attempt(attempt_id)
        if not attempt or attempt.profile_id != profile_id:
            raise LearningOSError(status_code=404, code="NOT_FOUND", message="Quiz attempt not found")

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
            letter_grade=_compute_letter_grade(score_val),
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
