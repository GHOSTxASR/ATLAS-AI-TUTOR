from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.database import get_db
from app.dependencies import get_settings_dependency
from app.schemas.quiz import (
    AssessmentGenerateRequest,
    QuizGenerateRequest,
    QuizSubmitRequest,
)
from app.services.quiz_service import QuizService

router = APIRouter(prefix="/api/v1/profiles/{profile_id}/quiz", tags=["quiz"])


def envelope(data=None, error=None, meta=None):
    return {"data": data, "error": error, "meta": meta}


def get_quiz_service(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
) -> QuizService:
    return QuizService(session=session, settings=settings)


@router.post("/generate", response_model=dict, status_code=status.HTTP_201_CREATED)
async def generate_quiz(
    profile_id: str,
    data: QuizGenerateRequest,
    service: QuizService = Depends(get_quiz_service),
):
    quiz = await service.generate_quiz(profile_id=profile_id, data=data)
    return envelope(data=quiz.model_dump())


@router.post("/assessments", response_model=dict, status_code=status.HTTP_201_CREATED)
async def generate_assessment(
    profile_id: str,
    data: AssessmentGenerateRequest,
    service: QuizService = Depends(get_quiz_service),
):
    assessment = await service.generate_assessment(profile_id=profile_id, data=data)
    return envelope(data=assessment.model_dump())


@router.post("/{attempt_id}/submit", response_model=dict)
async def submit_quiz(
    profile_id: str,
    attempt_id: str,
    data: QuizSubmitRequest,
    service: QuizService = Depends(get_quiz_service),
):
    result = await service.submit_quiz(profile_id=profile_id, attempt_id=attempt_id, data=data)
    return envelope(data=result.model_dump())


@router.get("/history", response_model=dict)
async def get_quiz_history(
    profile_id: str,
    service: QuizService = Depends(get_quiz_service),
):
    history = await service.get_quiz_history(profile_id=profile_id)
    return envelope(data=[h.model_dump() for h in history])


@router.get("/{attempt_id}/results", response_model=dict)
async def get_quiz_results(
    profile_id: str,
    attempt_id: str,
    service: QuizService = Depends(get_quiz_service),
):
    result = await service.get_quiz_result(profile_id=profile_id, attempt_id=attempt_id)
    return envelope(data=result.model_dump())
