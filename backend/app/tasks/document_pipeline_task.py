"""Background document processing.

Extraction (and OCR) used to run inline inside the upload request, so a large
scanned PDF held the HTTP connection open for minutes and timed out in the
browser. Upload now only stores the file and returns; this task does the work
and moves the document through its status states, which the frontend already
polls for.
"""

from __future__ import annotations

import logging

from app.config import get_settings
from app.db.database import async_session
from app.db.repositories.document_repo import DocumentRepository
from app.security.redaction import redact_secrets
from app.tasks.embedding_task import run_embedding_task_single_document
from app.services.ingestion_service import IngestionService

logger = logging.getLogger(__name__)

# Documents left in one of these states by an interrupted run can be retried.
RESUMABLE_STATUSES = ("pending", "extracting", "queuing")


async def run_document_pipeline(document_id: str) -> None:
    """Extract, chunk and queue a stored document for embedding."""
    settings = get_settings()

    async with async_session() as session:
        repo = DocumentRepository(session)
        document = await repo.get_by_id(document_id)
        if not document:
            logger.info("Document %s no longer exists; skipping pipeline.", document_id)
            return

        service = IngestionService(session, settings)
        try:
            document = await service.process_document(document)
        except Exception as e:
            logger.error("Document pipeline failed for %s", document_id, exc_info=True)
            try:
                await repo.update(
                    document,
                    status="error",
                    error_message=redact_secrets(f"Processing failed: {e}"),
                )
            except Exception:
                logger.debug("Could not record failure for %s", document_id, exc_info=True)
            return

    # Embed straight away rather than waiting up to one scheduler tick. The
    # queue marks its rows "embedding" first, so the periodic worker will not
    # pick up the same chunks; it remains the retry path for failures.
    if document.status == "queuing":
        await run_embedding_task_single_document(document_id)


async def process_pending_documents_for_profile(profile_id: str) -> int:
    """Run the pipeline over every not-yet-processed document in a profile.

    Used after a profile import: the archive carries the source files but no
    vectors, and the new profile has its own collections.
    """
    async with async_session() as session:
        repo = DocumentRepository(session)
        documents = await repo.get_by_profile_id(profile_id)
        pending = [d.id for d in documents if d.status in RESUMABLE_STATUSES]

    for document_id in pending:
        await run_document_pipeline(document_id)

    if pending:
        logger.info("Indexed %d imported document(s) for profile %s.", len(pending), profile_id)
    return len(pending)


async def resume_interrupted_documents() -> int:
    """Re-queue documents left mid-processing by a restart.

    Without this, a document interrupted between upload and extraction would
    sit at "pending" forever with no way to progress.
    """
    settings = get_settings()
    resumed = 0

    async with async_session() as session:
        repo = DocumentRepository(session)
        try:
            stuck = await repo.get_by_statuses(RESUMABLE_STATUSES)
        except Exception:
            logger.debug("Could not query interrupted documents.", exc_info=True)
            return 0

        service = IngestionService(session, settings)
        pending_ids: list[str] = []
        for document in stuck:
            try:
                processed = await service.process_document(document)
                resumed += 1
                if processed.status == "queuing":
                    pending_ids.append(processed.id)
            except Exception:
                logger.warning("Could not resume document %s", document.id, exc_info=True)

    for document_id in pending_ids:
        try:
            await run_embedding_task_single_document(document_id)
        except Exception:
            logger.warning("Could not embed resumed document %s", document_id, exc_info=True)

    if resumed:
        logger.info("Resumed %d interrupted document(s).", resumed)
    return resumed
