from __future__ import annotations


from fastapi import APIRouter, BackgroundTasks, Depends, File, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.database import get_db
from app.dependencies import get_settings_dependency
from app.schemas.profile import ProfileCreate, ProfileResponse, ProfileUpdate
from app.services.profile_service import ProfileService
from app.tasks.document_pipeline_task import process_pending_documents_for_profile
from app.utils.file_utils import read_upload_within_limit

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])


def envelope(data=None, error=None, meta=None):
    return {"data": data, "error": error, "meta": meta}


def get_profile_service(session: AsyncSession = Depends(get_db)) -> ProfileService:
    return ProfileService(session)


@router.get("", response_model=dict)
async def list_profiles(service: ProfileService = Depends(get_profile_service)):
    profiles = await service.get_all_profiles()
    return envelope(data=[ProfileResponse.model_validate(p).model_dump() for p in profiles])


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_profile(
    data: ProfileCreate, service: ProfileService = Depends(get_profile_service)
):
    profile = await service.create_profile(data)
    return envelope(data=ProfileResponse.model_validate(profile).model_dump())


@router.post("/import", response_model=dict, status_code=status.HTTP_201_CREATED)
async def import_profile(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    service: ProfileService = Depends(get_profile_service),
    settings: Settings = Depends(get_settings_dependency),
):
    """Import a profile from an uploaded ZIP archive.

    Imported documents are re-indexed in the background; the archive contains
    the source files but not the vectors.
    """
    max_bytes = settings.ingestion.max_import_size_mb * 1024 * 1024
    content = await read_upload_within_limit(
        file,
        max_bytes,
        error_message=f"Import archive exceeds the {settings.ingestion.max_import_size_mb}MB limit.",
        error_details={"max_import_size_mb": settings.ingestion.max_import_size_mb},
    )
    profile = await service.import_profile(content)
    background_tasks.add_task(process_pending_documents_for_profile, profile.id)
    return envelope(data=ProfileResponse.model_validate(profile).model_dump())


@router.get("/{profile_id}", response_model=dict)
async def get_profile(
    profile_id: str, service: ProfileService = Depends(get_profile_service)
):
    profile = await service.get_profile(profile_id)
    return envelope(data=ProfileResponse.model_validate(profile).model_dump())


@router.patch("/{profile_id}", response_model=dict)
async def update_profile(
    profile_id: str,
    data: ProfileUpdate,
    service: ProfileService = Depends(get_profile_service),
):
    profile = await service.update_profile(profile_id, data)
    return envelope(data=ProfileResponse.model_validate(profile).model_dump())


@router.delete("/{profile_id}", response_model=dict)
async def delete_profile(
    profile_id: str, service: ProfileService = Depends(get_profile_service)
):
    await service.delete_profile(profile_id)
    return envelope(data={"success": True})


@router.post("/{profile_id}/export")
async def export_profile(
    profile_id: str, service: ProfileService = Depends(get_profile_service)
):
    """Export complete profile package as a downloadable ZIP."""
    zip_bytes = await service.export_profile(profile_id)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=profile_{profile_id}.zip"},
    )
