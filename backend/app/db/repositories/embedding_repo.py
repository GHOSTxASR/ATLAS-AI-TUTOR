from __future__ import annotations

import json
from typing import Any, Sequence

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChunkEmbeddingQueue, EmbeddingCache
from app.db.repositories.base import BaseRepository


class EmbeddingRepository(BaseRepository[ChunkEmbeddingQueue]):
    def __init__(self, session: AsyncSession):
        super().__init__(model=ChunkEmbeddingQueue, session=session)

    async def enqueue_chunks(
        self,
        document_id: str,
        chunks: list[dict[str, Any]],
    ) -> list[ChunkEmbeddingQueue]:
        """Enqueue multiple chunks for a document."""
        queue_items: list[ChunkEmbeddingQueue] = []
        for chunk in chunks:
            item = ChunkEmbeddingQueue(
                document_id=document_id,
                chunk_index=chunk["chunk_index"],
                text=chunk["text"],
                page_number=chunk.get("page_number"),
                char_offset_start=chunk.get("char_offset_start"),
                char_offset_end=chunk.get("char_offset_end"),
                token_count=chunk.get("token_count"),
                section_title=chunk.get("section_title"),
                status="queued",
                retries=0,
            )
            self.session.add(item)
            queue_items.append(item)
        await self.session.commit()
        for item in queue_items:
            await self.session.refresh(item)
        return queue_items

    async def get_pending_chunks(self, batch_size: int = 100) -> Sequence[ChunkEmbeddingQueue]:
        """Fetch a batch of queued chunks ordered by creation."""
        result = await self.session.execute(
            select(ChunkEmbeddingQueue)
            .where(ChunkEmbeddingQueue.status == "queued")
            .order_by(ChunkEmbeddingQueue.created_at.asc(), ChunkEmbeddingQueue.chunk_index.asc())
            .limit(batch_size)
        )
        return result.scalars().all()

    async def mark_embedding(self, chunk_ids: list[str]) -> None:
        """Mark chunks as currently embedding."""
        if not chunk_ids:
            return
        await self.session.execute(
            update(ChunkEmbeddingQueue)
            .where(ChunkEmbeddingQueue.id.in_(chunk_ids))
            .values(status="embedding")
        )
        await self.session.commit()

    async def mark_chunks_done(self, chunk_ids: list[str]) -> None:
        """Mark a batch of chunks as successfully embedded."""
        if not chunk_ids:
            return
        await self.session.execute(
            update(ChunkEmbeddingQueue)
            .where(ChunkEmbeddingQueue.id.in_(chunk_ids))
            .values(status="done", error_message=None)
        )
        await self.session.commit()

    async def record_chunk_failure(
        self, chunk_id: str, error_message: str, max_retries: int = 3
    ) -> None:
        """Increment retries and set status to error if max_retries exceeded."""
        chunk = await self.get_by_id(chunk_id)
        if not chunk:
            return
        new_retries = chunk.retries + 1
        new_status = "error" if new_retries >= max_retries else "queued"
        chunk.retries = new_retries
        chunk.status = new_status
        chunk.error_message = error_message
        self.session.add(chunk)
        await self.session.commit()

    async def count_pending_for_document(self, document_id: str) -> int:
        """Count chunks that are still queued or embedding for a document."""
        result = await self.session.execute(
            select(func.count(ChunkEmbeddingQueue.id))
            .where(ChunkEmbeddingQueue.document_id == document_id)
            .where(ChunkEmbeddingQueue.status.in_(["queued", "embedding"]))
        )
        return result.scalar_one() or 0

    async def count_error_for_document(self, document_id: str) -> int:
        """Count chunks in error state for a document."""
        result = await self.session.execute(
            select(func.count(ChunkEmbeddingQueue.id))
            .where(ChunkEmbeddingQueue.document_id == document_id)
            .where(ChunkEmbeddingQueue.status == "error")
        )
        return result.scalar_one() or 0

    async def count_total_for_document(self, document_id: str) -> int:
        """Count total chunks for a document."""
        result = await self.session.execute(
            select(func.count(ChunkEmbeddingQueue.id))
            .where(ChunkEmbeddingQueue.document_id == document_id)
        )
        return result.scalar_one() or 0

    async def get_by_document_id(self, document_id: str) -> Sequence[ChunkEmbeddingQueue]:
        """Get all chunk queue records for a document."""
        result = await self.session.execute(
            select(ChunkEmbeddingQueue)
            .where(ChunkEmbeddingQueue.document_id == document_id)
            .order_by(ChunkEmbeddingQueue.chunk_index.asc())
        )
        return result.scalars().all()

    async def delete_by_document(self, document_id: str) -> None:
        """Delete all queue items for a given document."""
        await self.session.execute(
            delete(ChunkEmbeddingQueue).where(ChunkEmbeddingQueue.document_id == document_id)
        )
        await self.session.commit()

    async def get_cached_embedding(
        self, content_hash: str, embedding_model: str
    ) -> list[float] | None:
        """Check cache for precomputed vector."""
        result = await self.session.execute(
            select(EmbeddingCache)
            .where(EmbeddingCache.content_hash == content_hash)
            .where(EmbeddingCache.embedding_model == embedding_model)
        )
        entry = result.scalars().first()
        if entry:
            return json.loads(entry.vector_json)
        return None

    async def cache_embedding(
        self, content_hash: str, embedding_model: str, vector: list[float]
    ) -> None:
        """Save vector to cache."""
        entry = EmbeddingCache(
            content_hash=content_hash,
            embedding_model=embedding_model,
            vector_json=json.dumps(vector),
        )
        self.session.add(entry)
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
