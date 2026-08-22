from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone


from app.config import get_settings
from app.db.database import async_session
from app.db.models import ChunkEmbeddingQueue
from app.db.repositories.document_repo import DocumentRepository
from app.db.repositories.embedding_repo import EmbeddingRepository
from app.pipelines.embedder import DocumentEmbedder
from app.security.redaction import redact_secrets

logger = logging.getLogger(__name__)


async def process_embedding_queue(batch_size: int = 100) -> int:
    """Process a batch of pending chunk embedding jobs from SQLite queue."""
    settings = get_settings()

    async with async_session() as session:
        embedding_repo = EmbeddingRepository(session)
        doc_repo = DocumentRepository(session)
        embedder = DocumentEmbedder(settings=settings, repo=embedding_repo)

        # 1. Fetch pending chunks
        pending_chunks = await embedding_repo.get_pending_chunks(batch_size=batch_size)
        if not pending_chunks:
            return 0

        chunk_ids = [c.id for c in pending_chunks]
        await embedding_repo.mark_embedding(chunk_ids)

        # 2. Group chunks by document_id
        grouped: dict[str, list[ChunkEmbeddingQueue]] = defaultdict(list)
        for chunk in pending_chunks:
            grouped[chunk.document_id].append(chunk)

        processed_count = 0

        # 3. Process each document's batch
        for doc_id, doc_chunks in grouped.items():
            document = await doc_repo.get_by_id(doc_id)
            if not document:
                # Document was deleted; purge its queue entries
                await embedding_repo.delete_by_document(doc_id)
                continue

            # Update document status to indexing
            if document.status != "indexing":
                await doc_repo.update(document, status="indexing")

            try:
                # Embed and index into ChromaDB
                indexed = await embedder.embed_and_index_chunks(
                    profile_id=document.profile_id,
                    document=document,
                    chunks=doc_chunks,
                )
                done_ids = [c.id for c in doc_chunks]
                await embedding_repo.mark_chunks_done(done_ids)
                processed_count += indexed

                # Check if all chunks for this document are complete
                remaining = await embedding_repo.count_pending_for_document(doc_id)
                errors = await embedding_repo.count_error_for_document(doc_id)

                if remaining == 0:
                    if errors > 0:
                        await doc_repo.update(
                            document,
                            status="error",
                            error_message=f"{errors} chunks failed to embed.",
                        )
                    else:
                        total_chunks = await embedding_repo.count_total_for_document(doc_id)
                        await doc_repo.update(
                            document,
                            status="indexed",
                            chunk_count=total_chunks,
                            indexed_at=datetime.now(timezone.utc),
                            error_message=None,
                        )

            except Exception as e:
                logger.error(f"Error processing embedding batch for document {doc_id}: {e}", exc_info=True)
                for chunk in doc_chunks:
                    await embedding_repo.record_chunk_failure(
                        chunk_id=chunk.id,
                        error_message=redact_secrets(str(e)),
                        max_retries=3,
                    )
                # Check if document now has permanent errors
                errors = await embedding_repo.count_error_for_document(doc_id)
                if errors > 0:
                    await doc_repo.update(
                        document,
                        status="error",
                        error_message=redact_secrets(f"Embedding error: {e}"),
                    )

        return processed_count


async def run_embedding_task_single_document(document_id: str) -> None:
    """Helper to process all queued chunks for a specific document immediately."""
    settings = get_settings()

    async with async_session() as session:
        embedding_repo = EmbeddingRepository(session)
        doc_repo = DocumentRepository(session)
        embedder = DocumentEmbedder(settings=settings, repo=embedding_repo)

        document = await doc_repo.get_by_id(document_id)
        if not document:
            return

        chunks = await embedding_repo.get_by_document_id(document_id)
        pending = [c for c in chunks if c.status in ("queued", "embedding")]
        if not pending:
            return

        await embedding_repo.mark_embedding([c.id for c in pending])
        await doc_repo.update(document, status="indexing")

        try:
            await embedder.embed_and_index_chunks(
                profile_id=document.profile_id,
                document=document,
                chunks=pending,
            )
            await embedding_repo.mark_chunks_done([c.id for c in pending])
            total_chunks = await embedding_repo.count_total_for_document(document_id)
            await doc_repo.update(
                document,
                status="indexed",
                chunk_count=total_chunks,
                indexed_at=datetime.now(timezone.utc),
                error_message=None,
            )
        except Exception as e:
            logger.error(f"Error embedding document {document_id}: {e}", exc_info=True)
            for c in pending:
                await embedding_repo.record_chunk_failure(c.id, str(e), max_retries=3)
            await doc_repo.update(
                document,
                status="error",
                error_message=redact_secrets(f"Embedding failed: {e}"),
            )
