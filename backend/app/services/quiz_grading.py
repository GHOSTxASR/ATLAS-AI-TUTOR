from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.models.abstraction import ChatMessage
from app.models.provider_factory import get_model_client
from app.schemas.quiz import ErrorClassification
from app.utils.text_utils import extract_json_payload

logger = logging.getLogger(__name__)

#: Fraction of a question's marks that counts as knowing it. Shared by every
#: question type so a "correct" badge means the same thing across a paper.
PASS_THRESHOLD = 0.7


@dataclass(frozen=True)
class GradedAnswer:
    """What grading one answer produces, before anything is done with it."""

    score: float
    is_correct: bool
    feedback: str
    error_category: ErrorClassification
    remediation: str


def compute_letter_grade(score: float) -> str:
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


def overall_feedback(score: float) -> str:
    if score >= 0.9:
        return "Exceptional mastery demonstrated! Excellent depth across all examined concepts."
    elif score >= 0.8:
        return "High proficiency demonstrated. Ready to proceed to downstream dependent topics."
    elif score >= 0.6:
        return "Satisfactory conceptual grounding with minor calculation or definition gaps."
    return "Needs targeted review. Remediation items have been saved to your learner profile."


def grade_mcq(user_answer: str, correct_answer: str, topic: str) -> GradedAnswer:
    if user_answer.upper() == correct_answer.upper():
        return GradedAnswer(
            score=1.0,
            is_correct=True,
            feedback=f"Correct! Option {correct_answer} is right.",
            error_category="correct",
            remediation="Solid understanding demonstrated.",
        )
    return GradedAnswer(
        score=0.0,
        is_correct=False,
        feedback=f"Incorrect. Correct answer is {correct_answer}.",
        error_category="conceptual_misunderstanding",
        remediation=f"Review foundational rules of {topic}.",
    )


def grade_numerical(
    user_answer: str, question: dict[str, Any], correct_answer: str, topic: str
) -> GradedAnswer:
    """Score a numeric answer within either an absolute or a relative tolerance.

    The relative check is what makes one tolerance usable across a paper that
    mixes small constants with large ones: 0.05 absolute is generous on a
    coefficient of 0.3 and impossibly tight on a Reynolds number.
    """
    target_val = float(question.get("target_value") or correct_answer or 0.0)
    tolerance = float(question.get("tolerance") or 0.05)

    try:
        num_match = re.search(r"[-+]?\d*\.?\d+", user_answer)
        if not num_match:
            return GradedAnswer(
                score=0.0,
                is_correct=False,
                feedback=f"No valid numerical answer found. Target was {target_val}.",
                error_category="incomplete_answer",
                remediation="Enter a valid numeric value.",
            )

        user_val = float(num_match.group())
        diff = abs(user_val - target_val)
        within = diff <= tolerance or (target_val != 0 and diff / abs(target_val) <= tolerance)
        if within:
            return GradedAnswer(
                score=1.0,
                is_correct=True,
                feedback=f"Accurate calculation ({user_val} ≈ {target_val}).",
                error_category="correct",
                remediation="Calculation verified.",
            )
        return GradedAnswer(
            score=0.0,
            is_correct=False,
            feedback=f"Incorrect value {user_val}. Target was {target_val}.",
            error_category="calculation_error",
            remediation=f"Double check formulas and arithmetic constants in {topic}.",
        )
    except Exception:
        return GradedAnswer(
            score=0.0,
            is_correct=False,
            feedback=f"Failed to parse numerical value. Target was {target_val}.",
            error_category="calculation_error",
            remediation="Verify numerical syntax.",
        )


def _keyword_overlap_grade(
    user_answer: str, reference_answer: str, rubric: str, topic: str
) -> GradedAnswer:
    """Last-resort grade when the evaluator model is unreachable.

    Rewards terminology overlap, which is weak, but never blocks a submission
    on a provider outage.
    """
    ref_words = set(re.findall(r"\w+", (reference_answer + " " + rubric).lower()))
    user_words = set(re.findall(r"\w+", user_answer.lower()))
    overlap = len(ref_words & user_words)
    score = min(1.0, round(overlap / max(1, len(ref_words) * 0.4), 2))
    return GradedAnswer(
        score=score,
        is_correct=score >= PASS_THRESHOLD,
        feedback="Evaluated based on key concept terminology.",
        error_category="correct" if score >= PASS_THRESHOLD else "incomplete_answer",
        remediation=f"Review essential definitions in {topic}.",
    )


async def grade_short_answer(
    settings: Settings,
    prompt: str,
    user_answer: str,
    reference_answer: str,
    rubric: str,
    topic: str,
) -> GradedAnswer:
    """Grade a conceptual answer with a model, falling back to keyword overlap."""
    if not user_answer.strip():
        return GradedAnswer(
            score=0.0,
            is_correct=False,
            feedback="No answer provided.",
            error_category="incomplete_answer",
            remediation=f"Provide a complete explanation for {topic}.",
        )

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
        '  "error_category": "correct" | "conceptual_misunderstanding" | '
        '"incomplete_answer" | "misread_question",\n'
        '  "remediation": "Actionable advice on what to review."\n'
        "}"
    )

    try:
        client = get_model_client(settings)
        try:
            response = await client.chat_complete(
                messages=[
                    ChatMessage(
                        role="system",
                        content="You are an expert academic evaluator. Return ONLY JSON.",
                    ),
                    ChatMessage(role="user", content=eval_prompt),
                ],
                temperature=0.0,
                # A reasoning model bills its thinking against this budget, so a
                # tight one returns an empty content field and silently demotes
                # every short answer to the keyword fallback.
                max_tokens=2000,
            )
            raw = extract_json_payload(response.content)
            grade = json.loads(raw)
            # Reading the reply stays inside the guard: a model that answers
            # with a list, a string, or a score of "high" is as much an
            # evaluator failure as one that never answered, and both should
            # land on the fallback rather than fail the submission.
            score = float(grade.get("score", 0.75))
            default_cat = (
                "correct" if score >= PASS_THRESHOLD else "conceptual_misunderstanding"
            )
            return GradedAnswer(
                score=score,
                is_correct=score >= PASS_THRESHOLD,
                feedback=str(grade.get("feedback", "Good conceptual explanation.")),
                error_category=grade.get("error_category", default_cat),
                remediation=str(
                    grade.get("remediation", f"Review core principles of {topic}.")
                ),
            )
        finally:
            await client.close()
    except Exception as e:
        logger.warning("Short-answer evaluator unavailable, using keyword overlap: %s", e)
        return _keyword_overlap_grade(user_answer, reference_answer, rubric, topic)


async def grade_answer(
    settings: Settings, question: dict[str, Any], user_answer: str
) -> GradedAnswer:
    """Grade one stored question against the learner's answer."""
    q_type = question.get("question_type", "mcq")
    topic = str(question.get("topic_title", "Concept"))
    correct_answer = str(question.get("correct_answer", "")).strip()

    if q_type == "numerical":
        return grade_numerical(user_answer, question, correct_answer, topic)
    if q_type == "short_answer":
        return await grade_short_answer(
            settings,
            str(question.get("prompt", "")),
            user_answer,
            correct_answer,
            str(question.get("rubric", "")),
            topic,
        )
    return grade_mcq(user_answer, correct_answer, topic)
