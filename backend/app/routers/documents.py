from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.database import get_db
from app.dependencies import get_settings_dependency
from app.schemas.document import DocumentResponse, DocumentStatusResponse
from app.services.ingestion_service import IngestionService
from app.tasks.document_pipeline_task import run_document_pipeline

router = APIRouter(prefix="/api/v1/profiles/{profile_id}/documents", tags=["documents"])


def envelope(data=None, error=None, meta=None):
    return {"data": data, "error": error, "meta": meta}


def get_ingestion_service(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
) -> IngestionService:
    return IngestionService(session, settings)


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def upload_document(
    profile_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    is_syllabus: bool = Form(False),
    service: IngestionService = Depends(get_ingestion_service),
):
    """Store the upload and return immediately.

    Extraction, OCR and chunking run afterwards; poll
    ``GET /documents/{id}/status`` (the frontend already does) for progress.
    """
    content = await file.read()
    document = await service.upload_document(
        profile_id, filename=file.filename or "upload", content=content, is_syllabus=is_syllabus
    )
    background_tasks.add_task(run_document_pipeline, document.id)
    return envelope(data=DocumentResponse.model_validate(document).model_dump())


@router.get("", response_model=dict)
async def list_documents(profile_id: str, service: IngestionService = Depends(get_ingestion_service)):
    documents = await service.list_documents(profile_id)
    return envelope(data=[DocumentResponse.model_validate(d).model_dump() for d in documents])


@router.get("/{document_id}", response_model=dict)
async def get_document(
    profile_id: str, document_id: str, service: IngestionService = Depends(get_ingestion_service)
):
    document = await service.get_document(profile_id, document_id)
    return envelope(data=DocumentResponse.model_validate(document).model_dump())


@router.get("/{document_id}/status", response_model=dict)
async def get_document_status(
    profile_id: str, document_id: str, service: IngestionService = Depends(get_ingestion_service)
):
    document = await service.get_document(profile_id, document_id)
    return envelope(data=DocumentStatusResponse.model_validate(document).model_dump())


@router.post("/{document_id}/reprocess", response_model=dict)
async def reprocess_document(
    profile_id: str,
    document_id: str,
    background_tasks: BackgroundTasks,
    service: IngestionService = Depends(get_ingestion_service),
):
    document = await service.reprocess_document(profile_id, document_id)
    background_tasks.add_task(run_document_pipeline, document.id)
    return envelope(data=DocumentResponse.model_validate(document).model_dump())


@router.post("/{document_id}/parse-syllabus", response_model=dict)
async def parse_document_syllabus(
    profile_id: str,
    document_id: str,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
):
    from app.services.syllabus_service import SyllabusService
    service = SyllabusService(session=session, settings=settings)
    syllabus = await service.parse_document_syllabus(profile_id, document_id)
    return envelope(data=syllabus.model_dump())


@router.delete("/{document_id}", response_model=dict)
async def delete_document(
    profile_id: str, document_id: str, service: IngestionService = Depends(get_ingestion_service)
):
    await service.delete_document(profile_id, document_id)
    return envelope(data={"success": True})
