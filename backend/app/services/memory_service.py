from __future__ import annotations

import json
import logging
from typing import Any, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.models import MemoryRecord
from app.db.repositories.memory_repo import MemoryRepository
from app.db.repositories.profile_repo import ProfileRepository
from app.exceptions import AtlasError
from app.models.abstraction import ChatMessage
from app.models.provider_factory import get_model_client
from app.rag.vector_store import VectorStore
from app.schemas.memory import MemoryCreate, MemoryUpdate
from app.utils.text_utils import extract_json_payload

logger = logging.getLogger(__name__)


class MemoryService:
    """Manages long-term learner memory, extraction, summarization, and prompt context injection."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None):
        self.session = session
        self.settings = settings or get_settings()
        self.repo = MemoryRepository(session)
        self.profile_repo = ProfileRepository(session)
        self.vector_store = VectorStore(settings=self.settings)

    async def _require_profile(self, profile_id: str) -> None:
        profile = await self.profile_repo.get_by_id(profile_id)
        if not profile:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Profile not found")

    async def create_memory(self, profile_id: str, data: MemoryCreate) -> MemoryRecord:
        """Create a new memory record and index it into ChromaDB."""
        await self._require_profile(profile_id)

        record = await self.repo.create(
            profile_id=profile_id,
            category=data.category,
            subject=data.subject,
            content=data.content,
            confidence=data.confidence,
            source=data.source,
            source_id=data.source_id,
            is_active=True,
        )

        try:
            v_id = await self.vector_store.index_memory(
                profile_id=profile_id,
                memory_id=record.id,
                text=record.content,
                category=record.category,
                subject=record.subject,
                confidence=record.confidence,
                source=record.source,
                source_id=record.source_id,
                is_active=True,
            )
            record.embedding_id = v_id
            await self.repo.update(record, embedding_id=v_id)
        except Exception as e:
            logger.warning(f"Failed indexing memory into ChromaDB: {e}")

        return record

    async def get_memory(self, profile_id: str, memory_id: str) -> MemoryRecord:
        """Get a single memory record by ID."""
        record = await self.repo.get_by_id(memory_id)
        if not record or record.profile_id != profile_id:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Memory record not found")
        return record

    async def list_memories(
        self,
        profile_id: str,
        category: str | None = None,
        min_confidence: float = 0.0,
        is_active: bool | None = True,
    ) -> Sequence[MemoryRecord]:
        """List memory records for a profile."""
        await self._require_profile(profile_id)
        return await self.repo.get_by_profile_id(
            profile_id=profile_id,
            category=category,
            min_confidence=min_confidence,
            is_active=is_active,
        )

    async def update_memory(
        self, profile_id: str, memory_id: str, data: MemoryUpdate
    ) -> MemoryRecord:
        """Update a memory record in SQLite and ChromaDB."""
        record = await self.get_memory(profile_id, memory_id)
        update_data = data.model_dump(exclude_unset=True)

        record = await self.repo.update(record, **update_data)

        # Sync update with ChromaDB
        if record.is_active:
            try:
                await self.vector_store.index_memory(
                    profile_id=profile_id,
                    memory_id=record.id,
                    text=record.content,
                    category=record.category,
                    subject=record.subject,
                    confidence=record.confidence,
                    source=record.source,
                    source_id=record.source_id,
                    is_active=record.is_active,
                )
            except Exception as e:
                logger.warning(f"Error updating vector for memory {record.id}: {e}")
        else:
            await self.vector_store.delete_by_memory_id(profile_id, record.id)

        return record

    async def delete_memory(self, profile_id: str, memory_id: str) -> None:
        """Delete memory from SQLite and ChromaDB."""
        record = await self.get_memory(profile_id, memory_id)
        await self.vector_store.delete_by_memory_id(profile_id, record.id)
        await self.repo.delete(record.id)

    async def retrieve_relevant_memories(
        self, profile_id: str, query: str, top_k: int = 5
    ) -> list[MemoryRecord]:
        """Retrieve relevant active memory records via vector search and high-confidence facts."""
        vector_results = await self.vector_store.query_memory(
            profile_id=profile_id,
            query=query,
            top_k=top_k,
            is_active=True,
        )
        memory_ids = [r.source_id for r in vector_results]

        records: list[MemoryRecord] = []
        for m_id in memory_ids:
            rec = await self.repo.get_by_id(m_id)
            if rec and rec.is_active:
                records.append(rec)
        return records

    async def get_learner_profile_context(
        self, profile_id: str, topic: str | None = None
    ) -> str:
        """Assemble a structured <LEARNER_PROFILE> context block for tutor system prompt."""
        all_memories = await self.repo.get_by_profile_id(profile_id=profile_id, is_active=True)
        if not all_memories:
            return ""

        strengths = [m for m in all_memories if m.category == "strength"]
        weaknesses = [m for m in all_memories if m.category == "weakness"]
        preferences = [m for m in all_memories if m.category == "preference"]
        facts = [m for m in all_memories if m.category in ("fact", "context", "assessment", "completed")]

        lines = ["<LEARNER_PROFILE>"]
        if strengths:
            lines.append("Demonstrated Strengths:")
            for s in strengths[:4]:
                subj = f"[{s.subject}] " if s.subject else ""
                lines.append(f"- {subj}{s.content}")

        if weaknesses:
            lines.append("Learning Areas / Struggles (adapt explanations to assist with these):")
            for w in weaknesses[:5]:
                subj = f"[{w.subject}] " if w.subject else ""
                lines.append(f"- {subj}{w.content}")

        if preferences:
            lines.append("Learner Preferences:")
            for p in preferences[:3]:
                lines.append(f"- {p.content}")

        if facts:
            lines.append("Learner Background & Context:")
            for f in facts[:3]:
                lines.append(f"- {f.content}")

        lines.append("</LEARNER_PROFILE>")
        return "\n".join(lines)

    async def extract_memories_from_conversation(
        self, profile_id: str, session_id: str, messages: Sequence[Any]
    ) -> list[MemoryRecord]:
        """Analyze recent conversation turns to extract and persist learner memories."""
        if not messages or len(messages) < 2:
            return []

        # Format last 6 messages
        recent = messages[-6:]
        dialogue = "\n".join(
            f"{getattr(m, 'role', 'user').capitalize()}: {getattr(m, 'content', '')}"
            for m in recent
        )

        extraction_prompt = (
            "Analyze the following conversation between a student and an AI tutor.\n"
            "Identify any new strengths, weaknesses, learning preferences, or facts about the learner.\n"
            "Respond ONLY with a valid JSON array of objects with the exact schema:\n"
            "[\n"
            '  {"category": "strength" | "weakness" | "preference" | "fact", '
            '"subject": "topic name", "content": "statement about learner", "confidence": 0.5 to 1.0}\n'
            "]\n"
            "If no clear learner characteristics are evident, return [].\n\n"
            f"Conversation:\n{dialogue}"
        )

        extracted_records: list[MemoryRecord] = []
        try:
            client = get_model_client(self.settings)
            try:
                response = await client.chat_complete(
                    messages=[
                        ChatMessage(role="system", content="You are a precise learner memory extraction assistant. Return ONLY JSON."),
                        ChatMessage(role="user", content=extraction_prompt),
                    ],
                    temperature=0.2,
                    max_tokens=1000,
                )
                text = extract_json_payload(response.content)

                items = json.loads(text)
                if isinstance(items, list):
                    for item in items:
                        if not isinstance(item, dict) or "category" not in item or "content" not in item:
                            continue
                        cat = item["category"]
                        if cat not in ("strength", "weakness", "preference", "fact", "completed", "context", "assessment"):
                            cat = "fact"

                        content = str(item["content"]).strip()
                        subject = str(item.get("subject", "")).strip()
                        conf = float(item.get("confidence", 0.7))

                        # Check for existing similar memory (deduplication / reinforcement)
                        similar = await self.vector_store.query_memory(
                            profile_id=profile_id, query=content, top_k=1
                        )
                        if similar and similar[0].score >= 0.85:
                            existing_rec = await self.repo.get_by_id(similar[0].source_id)
                            if existing_rec:
                                updated = await self.repo.update_confidence(existing_rec.id, 0.2)
                                if updated:
                                    extracted_records.append(updated)
                                continue

                        # Insert new memory
                        new_mem = await self.create_memory(
                            profile_id=profile_id,
                            data=MemoryCreate(
                                category=cat,  # type: ignore
                                subject=subject,
                                content=content,
                                confidence=conf,
                                source="chat",
                                source_id=session_id,
                            ),
                        )
                        extracted_records.append(new_mem)

            finally:
                await client.close()

        except Exception as e:
            logger.warning(f"Memory extraction from chat failed (non-fatal): {e}")

        return extracted_records

    async def summarize_conversation(
        self, profile_id: str, session_id: str, messages: Sequence[Any]
    ) -> str:
        """Generate a concise session summary and store in vector database."""
        if not messages or len(messages) < 2:
            return ""

        dialogue = "\n".join(
            f"{getattr(m, 'role', 'user').capitalize()}: {getattr(m, 'content', '')}"
            for m in messages[-10:]
        )

        prompt = (
            "Summarize the following tutoring session in 2 concise sentences. "
            "Focus on the primary topics covered, problems solved, and learner progress.\n\n"
            f"Conversation:\n{dialogue}"
        )

        summary_text = ""
        try:
            client = get_model_client(self.settings)
            try:
                response = await client.chat_complete(
                    messages=[
                        ChatMessage(role="system", content="You summarize tutoring sessions concisely."),
                        ChatMessage(role="user", content=prompt),
                    ],
                    temperature=0.3,
                    max_tokens=300,
                )
                summary_text = response.content.strip()
                if summary_text:
                    await self.vector_store.index_chat_summary(
                        profile_id=profile_id,
                        summary_id=session_id,
                        session_id=session_id,
                        text=summary_text,
                    )
            finally:
                await client.close()
        except Exception as e:
            logger.warning(f"Chat summarization failed (non-fatal): {e}")

        return summary_text

    async def decay_old_records(self, profile_id: str | None = None) -> int:
        """Decay confidences across records and drop pruned records from ChromaDB."""
        pruned_ids = await self.repo.decay_confidences(profile_id=profile_id, decay_factor=0.95, prune_threshold=0.2)
        if profile_id and pruned_ids:
            for pid in pruned_ids:
                await self.vector_store.delete_by_memory_id(profile_id, pid)
        return len(pruned_ids)
