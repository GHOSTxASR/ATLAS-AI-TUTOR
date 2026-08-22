from __future__ import annotations

import json
import logging
import traceback
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.db.database import async_session
from app.db.repositories.analytics_repo import AnalyticsRepository
from app.db.repositories.chat_repo import ChatMessageRepository, ChatSessionRepository
from app.db.repositories.profile_repo import ProfileRepository
from app.db.repositories.roadmap_repo import RoadmapRepository
from app.models.abstraction import ChatMessage as LLMMessage
from app.models.provider_factory import get_model_client
from app.models.resilience import provider_error_from, sanitize_provider_text
from app.rag.pipeline import RAGPipeline
from app.schemas.chat import LearningMode
from app.services.memory_service import MemoryService
from app.services.tutor_orchestrator import TutorOrchestrator
from app.tasks.background import spawn
from app.tasks.memory_extraction_task import extract_session_memory_and_summary
from app.utils.date_utils import elapsed_study_minutes

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket-chat"])


@router.websocket("/ws/chat/{profile_id}/{session_id}")
async def ws_chat(websocket: WebSocket, profile_id: str, session_id: str):
    """WebSocket endpoint for streaming AI tutor chat across Teaching, Revision, Summary, and General Knowledge modes.
    
    Client sends: {"content": "...", "mode": "teaching" | "revision" | "summary" | "general_knowledge", "document_ids": [...], "roadmap_node_id": "..."}
    Server sends: {"type": "citations", "citations": [...]} (if relevant context found)
                  {"type": "chunk", "content": "..."} for each token
                  {"type": "done", "message_id": "..."} when complete
                  {"type": "error", "content": "..."} on error
    """
    await websocket.accept()

    try:
        while True:
            # Wait for user message
            raw = await websocket.receive_text()
            turn_started_at = datetime.now(UTC)
            # Re-read settings each turn. Pinning them at connect time meant a
            # provider, model or API key changed on the Settings page was
            # ignored until the user reloaded the page.
            settings = get_settings()
            rag_pipeline = RAGPipeline(settings=settings)
            data = json.loads(raw)
            user_content = data.get("content", "").strip()
            mode: LearningMode = data.get("mode", "teaching")
            document_ids = data.get("document_ids")
            roadmap_node_id = data.get("roadmap_node_id")

            if not user_content:
                await websocket.send_json({"type": "error", "content": "Empty message"})
                continue

            async with async_session() as db:
                session_repo = ChatSessionRepository(db)
                message_repo = ChatMessageRepository(db)
                profile_repo = ProfileRepository(db)
                roadmap_repo = RoadmapRepository(db)
                memory_service = MemoryService(session=db, settings=settings)
                orchestrator = TutorOrchestrator(session=db, settings=settings)

                # Verify profile & session exist
                profile = await profile_repo.get_by_id(profile_id)
                chat_session = await session_repo.get_by_id(session_id)
                if not profile or not chat_session or chat_session.profile_id != profile_id:
                    await websocket.send_json({"type": "error", "content": "Session not found"})
                    continue

                node = None
                if roadmap_node_id:
                    node = await roadmap_repo.get_node(roadmap_node_id)
                    if not node or node.profile_id != profile_id:
                        await websocket.send_json({"type": "error", "content": "Roadmap node not found"})
                        continue

                # Persist user message
                user_msg = await message_repo.create(
                    session_id=session_id, role="user", content=user_content
                )
                await websocket.send_json({
                    "type": "user_saved",
                    "message_id": user_msg.id,
                    "content": user_content,
                    "mode": mode,
                })

                # Fetch active roadmap topic if provided
                topic_title = node.title if node else None

                # Fetch learner memory context (strengths, weaknesses, preferences)
                learner_context = ""
                try:
                    learner_context = await memory_service.get_learner_profile_context(
                        profile_id=profile_id, topic=topic_title
                    )
                except Exception as e:
                    logger.warning(f"Failed loading learner profile context: {e}")

                # Retrieve RAG context from uploaded documents
                rag_text = ""
                try:
                    assembled = await rag_pipeline.retrieve_and_assemble(
                        profile_id=profile_id,
                        query=user_content,
                        doc_ids=document_ids,
                        topic_context=topic_title,
                        roadmap_node_id=roadmap_node_id,
                        learner_profile_context=learner_context,
                    )
                    if assembled.citations:
                        await websocket.send_json({
                            "type": "citations",
                            "citations": [c.to_dict() for c in assembled.citations],
                        })
                    rag_text = assembled.context_block
                except Exception as e:
                    logger.warning(f"RAG retrieval skipped due to error: {e}")

                # Build mode-specific system prompt via TutorOrchestrator
                system_prompt = orchestrator.build_system_prompt(
                    mode=mode,
                    profile_name=profile.name,
                    profile_type=profile.profile_type,
                    topic_context=topic_title,
                    learner_memory=learner_context,
                    rag_context=rag_text,
                )

                # Load conversation history for context
                history = await message_repo.get_by_session_id(session_id)
                llm_messages = [LLMMessage(role="system", content=system_prompt)]
                for msg in history[-10:]:
                    llm_messages.append(LLMMessage(role=msg.role, content=msg.content))

                # Stream AI response
                full_response = ""
                try:
                    client = get_model_client(settings)
                    try:
                        async for chunk in client.chat_stream(
                            llm_messages,
                            model=settings.model.chat_model,
                            temperature=0.2 if mode in ("revision", "summary") else settings.model.temperature,
                            max_tokens=settings.model.max_tokens,
                        ):
                            if chunk.done:
                                break
                            if chunk.content:
                                full_response += chunk.content
                                await websocket.send_json({
                                    "type": "chunk",
                                    "content": chunk.content,
                                })
                    finally:
                        await client.close()

                except ValueError as e:
                    # Configuration problem (e.g. no API key set). The message
                    # is written by provider_factory and is safe to display.
                    await websocket.send_json({"type": "error", "content": str(e)})
                    continue

                except Exception as e:
                    # Never forward a raw provider exception: for key-in-query
                    # providers its message contains the API key.
                    error_msg = provider_error_from(e).message
                    logger.error(
                        "Stream error: %s",
                        sanitize_provider_text(traceback.format_exc()),
                    )
                    await websocket.send_json({"type": "error", "content": error_msg})
                    if not full_response:
                        continue

                # Persist assistant message
                if full_response:
                    assistant_msg = await message_repo.create(
                        session_id=session_id, role="assistant", content=full_response
                    )
                    await session_repo.touch(chat_session)

                    await websocket.send_json({
                        "type": "done",
                        "message_id": assistant_msg.id,
                        "content": full_response,
                        "mode": mode,
                    })

                    # Record study time for the analytics dashboard, which had
                    # no source of chat_turn events at all.
                    try:
                        await AnalyticsRepository(db).log_event(
                            profile_id=profile_id,
                            event_type="chat_turn",
                            entity_type="chat_session",
                            entity_id=session_id,
                            value=elapsed_study_minutes(turn_started_at),
                            metadata_json=json.dumps({"mode": mode}),
                        )
                    except Exception as e:
                        logger.warning("Could not record chat_turn analytics event: %s", e)

                    # Trigger background memory extraction & summarization.
                    # Tracked so the task cannot be garbage collected mid-run
                    # and so shutdown can drain it.
                    spawn(
                        extract_session_memory_and_summary(
                            profile_id=profile_id, session_id=session_id
                        ),
                        name=f"memory-extraction:{session_id}",
                    )
                else:
                    await websocket.send_json({
                        "type": "done",
                        "message_id": "",
                        "content": "",
                    })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: profile={profile_id}, session={session_id}")
    except Exception as e:
        logger.error("WebSocket error: %s", sanitize_provider_text(traceback.format_exc()))
        try:
            await websocket.send_json(
                {"type": "error", "content": sanitize_provider_text(str(e))}
            )
        except Exception:
            logger.debug("Unable to send WebSocket error to client after failure.", exc_info=True)
