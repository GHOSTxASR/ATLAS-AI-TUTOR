from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.repositories.document_repo import DocumentRepository
from app.db.repositories.profile_repo import ProfileRepository
from app.exceptions import LearningOSError
from app.pipelines.document_extractor import DocumentExtractor
from app.pipelines.syllabus_parser import SyllabusParser
from app.schemas.syllabus import ParsedSyllabus

logger = logging.getLogger(__name__)


class SyllabusService:
    """Service orchestrating syllabus hierarchy extraction from uploaded documents and text."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None):
        self.session = session
        self.settings = settings or get_settings()
        self.doc_repo = DocumentRepository(session)
        self.profile_repo = ProfileRepository(session)
        self.parser = SyllabusParser(settings=self.settings)
        self.extractor = DocumentExtractor()

    async def _require_profile(self, profile_id: str) -> None:
        profile = await self.profile_repo.get_by_id(profile_id)
        if not profile:
            raise LearningOSError(status_code=404, code="NOT_FOUND", message="Profile not found")

    async def parse_document_syllabus(self, profile_id: str, document_id: str) -> ParsedSyllabus:
        """Extract structured syllabus from an uploaded document."""
        await self._require_profile(profile_id)

        document = await self.doc_repo.get_by_id(document_id)
        if not document or document.profile_id != profile_id:
            raise LearningOSError(status_code=404, code="NOT_FOUND", message="Document not found")

        # 1. Read from extracted text file if available
        extracted_path = (
            self.settings.paths.profiles_dir
            / profile_id
            / "documents"
            / "extracted"
            / f"{document.id}.txt"
        )

        text = ""
        if extracted_path.exists():
            text = extracted_path.read_text(encoding="utf-8", errors="ignore")

        # 2. If extracted text file doesn't exist, extract from raw file
        if not text.strip():
            raw_path = (
                self.settings.paths.profiles_dir
                / profile_id
                / "documents"
                / "raw"
                / document.file_path
            )
            if raw_path.exists():
                file_type = Path(document.filename).suffix.lower().lstrip(".")
                # Map extension to extractor's expected file_type
                ext_map = {"pdf": "pdf", "docx": "docx", "txt": "txt"}
                detected_type = ext_map.get(file_type, "txt")
                res = self.extractor.extract(raw_path, detected_type)
                text = res.text

        if not text.strip():
            raise LearningOSError(
                status_code=422,
                code="EXTRACTION_EMPTY",
                message="No text content could be extracted from the document to parse syllabus.",
            )

        title = Path(document.filename).stem.replace("_", " ").title()
        return await self.parser.parse_text(text=text, default_title=title)

    async def parse_raw_text(self, text: str, title: str = "Uploaded Syllabus") -> ParsedSyllabus:
        """Parse raw text string into a structured syllabus."""
        return await self.parser.parse_text(text=text, default_title=title)
