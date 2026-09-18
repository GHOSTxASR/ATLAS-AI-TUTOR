"""Reading back the text of a document the learner has already uploaded.

Extraction writes a plain-text copy beside the original, but that copy cannot
be relied on -- an upload from an older build, or a pass that failed -- so the
original is re-read when it is missing. The syllabus parser needed this, and
so does the knowledge graph; neither should have to know where the files sit.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import Document
from app.db.repositories.document_repo import DocumentRepository
from app.exceptions import AtlasError
from app.pipelines.document_extractor import DocumentExtractor

#: What the extractor is asked for, by file suffix. Anything unrecognised is
#: read as plain text rather than refused.
_EXTRACTOR_TYPES = {"pdf": "pdf", "docx": "docx", "txt": "txt"}


async def load_document_text(
    session: AsyncSession,
    settings: Settings,
    profile_id: str,
    document_id: str,
    extractor: DocumentExtractor | None = None,
) -> tuple[Document, str]:
    """Return an uploaded document and its text.

    Raises 404 if it is not this profile's document, and 422 if there is no
    text to be had from it.
    """
    document = await DocumentRepository(session).get_by_id(document_id)
    if not document or document.profile_id != profile_id:
        raise AtlasError(status_code=404, code="NOT_FOUND", message="Document not found")

    documents_dir = settings.paths.profiles_dir / profile_id / "documents"

    text = ""
    extracted_path = documents_dir / "extracted" / f"{document.id}.txt"
    if extracted_path.exists():
        text = extracted_path.read_text(encoding="utf-8", errors="ignore")

    if not text.strip():
        raw_path = documents_dir / "raw" / document.file_path
        if raw_path.exists():
            suffix = Path(document.filename).suffix.lower().lstrip(".")
            result = (extractor or DocumentExtractor()).extract(
                raw_path, _EXTRACTOR_TYPES.get(suffix, "txt")
            )
            text = result.text

    if not text.strip():
        raise AtlasError(
            status_code=422,
            code="EXTRACTION_EMPTY",
            message="No text content could be extracted from the document.",
        )

    return document, text
