from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import Document
from app.db.repositories.document_repo import DocumentRepository
from app.db.repositories.embedding_repo import EmbeddingRepository
from app.db.repositories.profile_repo import ProfileRepository
from app.exceptions import AtlasError
from app.pipelines.chunker import DocumentChunker
from app.pipelines.document_extractor import DocumentExtractor, detect_file_type
from app.pipelines.embedder import DocumentEmbedder
from app.pipelines.ocr_pipeline import OcrPipeline
from app.utils.file_utils import ensure_within_directory, sanitize_filename, sha256_bytes, unique_storage_name

ALLOWED_FILE_TYPES = {"pdf", "docx", "txt", "image"}


class IngestionService:
    """Orchestrates document upload, storage, extraction, chunking, and embedding."""

    def __init__(self, session: AsyncSession, settings: Settings):
        self.session = session
        self.settings = settings
        self.repo = DocumentRepository(session)
        self.profile_repo = ProfileRepository(session)
        self.embedding_repo = EmbeddingRepository(session)
        self.chunker = DocumentChunker()
        self.embedder = DocumentEmbedder(settings=settings, repo=self.embedding_repo)
        ocr = OcrPipeline(
            language=self.settings.ingestion.ocr_language,
            tesseract_path=self.settings.ingestion.tesseract_path,
        )
        self.extractor = DocumentExtractor(ocr=ocr)

    async def _require_profile(self, profile_id: str) -> None:
        profile = await self.profile_repo.get_by_id(profile_id)
        if not profile:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Profile not found")

    def _raw_dir(self, profile_id: str) -> Path:
        return self.settings.paths.profiles_dir / profile_id / "documents" / "raw"

    def _extracted_dir(self, profile_id: str) -> Path:
        return self.settings.paths.profiles_dir / profile_id / "documents" / "extracted"

    async def list_documents(self, profile_id: str) -> Sequence[Document]:
        await self._require_profile(profile_id)
        return await self.repo.get_by_profile_id(profile_id)

    async def get_document(self, profile_id: str, document_id: str) -> Document:
        document = await self.repo.get_by_id(document_id)
        if not document or document.profile_id != profile_id:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Document not found")
        return document

    async def upload_document(
        self, profile_id: str, filename: str, content: bytes, is_syllabus: bool = False
    ) -> Document:
        await self._require_profile(profile_id)

        if not content:
            raise AtlasError(
                status_code=422, code="VALIDATION_ERROR", message="Uploaded file is empty"
            )

        max_bytes = self.settings.ingestion.max_file_size_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise AtlasError(
                status_code=422,
                code="VALIDATION_ERROR",
                message=f"File exceeds the {self.settings.ingestion.max_file_size_mb}MB upload limit.",
                details={"max_file_size_mb": self.settings.ingestion.max_file_size_mb},
            )

        file_type = detect_file_type(filename, content)
        if file_type is None or file_type not in ALLOWED_FILE_TYPES:
            raise AtlasError(
                status_code=422,
                code="VALIDATION_ERROR",
                message="Unsupported file type. Supported: PDF, DOCX, TXT, and common image formats.",
            )

        content_hash = sha256_bytes(content)
        existing = await self.repo.get_by_hash(profile_id, content_hash)
        if existing:
            raise AtlasError(
                status_code=409,
                code="CONFLICT",
                message=f"This file was already uploaded as '{existing.filename}'.",
                details={"document_id": existing.id},
            )

        display_name = sanitize_filename(filename)
        storage_name = unique_storage_name(filename)

        raw_dir = self._raw_dir(profile_id)
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = ensure_within_directory(raw_dir, raw_dir / storage_name)
        raw_path.write_bytes(content)

        # Return as soon as the bytes are safely stored. Extraction, OCR and
        # chunking happen in a background task so a large scanned PDF cannot
        # hold the request open until the client times out.
        return await self.repo.create(
            profile_id=profile_id,
            filename=display_name,
            file_path=str(raw_path.relative_to(self.settings.paths.data_dir)),
            file_type=file_type,
            content_hash=content_hash,
            status="pending",
            is_syllabus=is_syllabus,
        )

    async def process_document(self, document: Document) -> Document:
        """Extract, chunk and queue a stored document. Safe to re-run."""
        return await self._run_pipeline(document)

    async def _run_pipeline(self, document: Document) -> Document:
        """Run text extraction and chunking, then hand off to the embed queue."""
        raw_path = self.settings.paths.data_dir / document.file_path
        result = await asyncio.to_thread(self.extractor.extract, raw_path, document.file_type)

        update_fields: dict[str, object] = {
            "status": result.status,
            "page_count": result.page_count,
            "word_count": result.word_count,
            "error_message": result.error_message,
        }

        if result.status != "extracted" or not result.text:
            return await self.repo.update(document, **update_fields)

        extracted_dir = self._extracted_dir(document.profile_id)
        extracted_dir.mkdir(parents=True, exist_ok=True)
        extracted_path = extracted_dir / f"{document.id}.txt"
        extracted_path.write_text(result.text, encoding="utf-8")
        update_fields["extracted_text_path"] = str(
            extracted_path.relative_to(self.settings.paths.data_dir)
        )

        # 2. Chunk text
        chunks = self.chunker.chunk_document(result.text, result.pages)
        if not chunks:
            update_fields["status"] = "indexed"
            update_fields["chunk_count"] = 0
            update_fields["indexed_at"] = datetime.now(timezone.utc)
            return await self.repo.update(document, **update_fields)

        update_fields["chunk_count"] = len(chunks)
        update_fields["status"] = "queuing"
        document = await self.repo.update(document, **update_fields)

        # 3. Enqueue chunks. The scheduler's embedding worker takes it from
        #    here; embedding inline as well used to double the API cost and
        #    race the worker over the same rows.
        await self.embedding_repo.enqueue_chunks(
            document_id=document.id,
            chunks=[c.to_dict() for c in chunks],
        )

        return document

    async def reprocess_document(self, profile_id: str, document_id: str) -> Document:
        """Clear existing vectors and queue, then reprocess document."""
        document = await self.get_document(profile_id, document_id)

        # Remove existing vectors and queue entries
        await self.embedder.delete_document_vectors(profile_id, document_id)
        await self.embedding_repo.delete_by_document(document_id)

        document = await self.repo.update(
            document,
            status="pending",
            chunk_count=0,
            indexed_at=None,
            error_message=None,
        )
        return document

    async def delete_document(self, profile_id: str, document_id: str) -> None:
        """Delete document files, vectors, queue entries, and database record."""
        document = await self.get_document(profile_id, document_id)

        # Delete ChromaDB vectors
        await self.embedder.delete_document_vectors(profile_id, document_id)

        # Delete queue entries
        await self.embedding_repo.delete_by_document(document_id)

        # Delete files
        raw_path = self.settings.paths.data_dir / document.file_path
        raw_path.unlink(missing_ok=True)

        if document.extracted_text_path:
            extracted_path = self.settings.paths.data_dir / document.extracted_text_path
            extracted_path.unlink(missing_ok=True)

        # Delete SQLite row
        await self.repo.delete(document.id)
