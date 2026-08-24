from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.repositories.analytics_repo import AnalyticsRepository
from app.db.repositories.chat_repo import ChatMessageRepository, ChatSessionRepository
from app.db.repositories.profile_repo import ProfileRepository
from app.exceptions import AtlasError
from app.tasks.background import spawn
from app.tasks.memory_extraction_task import extract_session_memory_and_summary
from app.models.abstraction import ChatMessage as LLMMessage
from app.models.provider_factory import get_model_client
from app.models.resilience import provider_error_from
from app.schemas.chat import LearningMode, TutorChatRequest, TutorChatResponse
from app.services.unified_context_service import UnifiedContextService
from app.utils.date_utils import elapsed_study_minutes

logger = logging.getLogger(__name__)

MODE_SYSTEM_DIRECTIVES: dict[LearningMode, str] = {
    "teaching": (
        "### LEARNING MODE: TEACHING (Deep Conceptual Learning)\n"
        "- Deliver thorough, first-principles explanations from the ground up.\n"
        "- Use vivid intuitive analogies, clear visual mental models, and step-by-step logic.\n"
        "- Deconstruct complex formulas into their constituent parts.\n"
        "- End your response with a gentle Socratic check-for-understanding question to test the learner."
    ),
    "revision": (
        "### LEARNING MODE: REVISION (High-Yield Rapid Review)\n"
        "- Deliver a fast-paced, high-density conceptual refresher.\n"
        "- Highlight core definitions, critical equations, high-yield exam takeaways, and frequent pitfalls.\n"
        "- Eliminate conversational filler; focus strictly on structured, memorable review points."
    ),
    "summary": (
        "### LEARNING MODE: SUMMARY (Executive TL;DR Synthesis)\n"
        "- Distill the topic into an ultra-concise executive summary (3-5 structured bullet points or quick cheatsheet).\n"
        "- Provide only the core axiom, primary formula, and essential takeaway without lengthy exposition."
    ),
    "general_knowledge": (
        "### LEARNING MODE: GENERAL KNOWLEDGE (Interdisciplinary Curiosity)\n"
        "- Explore broader context beyond strict syllabus boundaries.\n"
        "- Discuss historical discovery context, cutting-edge industry applications, real-world analogies, and cross-domain connections."
    ),
    "quiz": (
        "### LEARNING MODE: QUIZ (Interactive Socratic Assessment)\n"
        "- Ask 1-2 targeted conceptual or problem-solving questions to evaluate the learner.\n"
        "- If the user answers, provide immediate constructive feedback and hints rather than giving away full solutions."
    ),
    "assessment": (
        "### LEARNING MODE: ASSESSMENT (Formal Evaluation)\n"
        "- Provide a structured multi-part examination problem.\n"
        "- Rigorously evaluate learner answers with scoring rubrics and step-by-step corrections."
    ),
}


class TutorOrchestrator:
    """Central AI Tutor engine orchestrating multi-mode learning prompts and unified 5-pillar context assembly."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None):
        self.session = session
        self.settings = settings or get_settings()
        self.profile_repo = ProfileRepository(session)
        self.session_repo = ChatSessionRepository(session)
        self.message_repo = ChatMessageRepository(session)
        self.analytics_repo = AnalyticsRepository(session)
        self.context_service = UnifiedContextService(session=session, settings=self.settings)

    def build_system_prompt(
        self,
        mode: LearningMode,
        profile_name: str,
        profile_type: str,
        topic_context: str | None = None,
        learner_memory: str | None = None,
        rag_context: str | None = None,
    ) -> str:
        """Construct mode-specific system prompt injecting persona, memory, roadmap topic, and RAG knowledge."""
        mode_instruction = MODE_SYSTEM_DIRECTIVES.get(mode, MODE_SYSTEM_DIRECTIVES["teaching"])

        sections: list[str] = [
            f"You are the Atlas AI Tutor, a personalized expert tutor for {profile_name} (Target Track: {profile_type}).",
            "Your mission is to guide the student toward true deep mastery and conceptual clarity.",
            "",
            mode_instruction,
            "",
        ]

        if topic_context:
            sections.append(f"### ACTIVE TOPIC / CURRICULUM CONTEXT:\n{topic_context}\n")

        if learner_memory:
            sections.append(f"### LEARNER PROFILE & MEMORY (Strengths, Weaknesses, Style):\n{learner_memory}\n")

        if rag_context:
            sections.append(f"### RETRIEVED SOURCE KNOWLEDGE & COURSE MATERIALS:\n{rag_context}\n")
        else:
            sections.append("Use your comprehensive academic knowledge to provide rigorous, accurate instruction.\n")

        return "\n".join(sections)

    async def handle_chat_turn(
        self,
        profile_id: str,
        request: TutorChatRequest,
    ) -> TutorChatResponse:
        """Complete chat turn with 5-pillar unified context assembly (Memory, Roadmap, Graph, Syllabus, RAG)."""
        turn_started_at = datetime.now(UTC)
        profile = await self.profile_repo.get_by_id(profile_id)
        if not profile:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Profile not found")

        # 1. Ensure or create session
        session_id = request.session_id
        if not session_id:
            session = await self.session_repo.create(profile_id=profile_id, title=f"Chat ({request.mode.title()})")
            session_id = session.id
        else:
            session = await self.session_repo.get_by_id(session_id)
            if not session or session.profile_id != profile_id:
                raise AtlasError(
                    status_code=404,
                    code="NOT_FOUND",
                    message="Chat session not found",
                )

        # 2. Persist user message
        await self.message_repo.create(session_id=session_id, role="user", content=request.content)

        # 3. Assemble 5-Pillar Unified Context
        unified_ctx = await self.context_service.build_unified_context(
            profile_id=profile_id,
            query=request.content,
            mode=request.mode,
            roadmap_node_id=request.roadmap_node_id,
            document_ids=request.document_ids,
        )

        mode_directive = MODE_SYSTEM_DIRECTIVES.get(request.mode, MODE_SYSTEM_DIRECTIVES["teaching"])
        full_system_prompt = f"{mode_directive}\n\n{unified_ctx.system_prompt}"

        # 4. Build History Messages
        history = await self.message_repo.get_by_session_id(session_id)
        llm_messages = [LLMMessage(role="system", content=full_system_prompt)]
        for msg in history[-10:]:
            llm_messages.append(LLMMessage(role=msg.role, content=msg.content))

        # 5. Generate AI response.
        #    A failure here is reported as an error, never papered over with
        #    generated filler: a tutor that invents confident-looking text when
        #    the model is unavailable actively misleads the student.
        ai_content = ""
        try:
            client = get_model_client(self.settings)
            try:
                resp = await client.chat_complete(
                    messages=llm_messages,
                    temperature=0.3 if request.mode in ("revision", "summary") else 0.5,
                    max_tokens=self.settings.model.max_tokens,
                )
                ai_content = resp.content.strip()
            finally:
                await client.close()
        except ValueError as e:
            # No provider/API key configured - an actionable setup problem.
            logger.warning("Tutor chat blocked by provider configuration: %s", e)
            raise AtlasError(
                status_code=503,
                code="PROVIDER_NOT_CONFIGURED",
                message=str(e),
            ) from None
        except Exception as e:
            error = provider_error_from(e)
            logger.warning("Tutor chat failed: %s", error.message)
            raise AtlasError(
                status_code=502,
                code="PROVIDER_ERROR",
                message=error.message,
                details={"provider": error.provider, "provider_status": error.status_code},
            ) from None

        if not ai_content:
            raise AtlasError(
                status_code=502,
                code="PROVIDER_EMPTY_RESPONSE",
                message="The AI provider returned an empty response. Try again.",
            )

        # 6. Persist assistant message
        assistant_msg = await self.message_repo.create(
            session_id=session_id, role="assistant", content=ai_content
        )

        # 7. Bump the session so it sorts to the top of the sidebar. The REST
        #    chat path never touched it at all.
        try:
            await self.session_repo.touch(session)
        except Exception as e:
            logger.warning("Could not update session timestamp: %s", e)

        # 8. Record study time. Nothing emitted chat_turn before, so the
        #    analytics dashboard reported zero chat minutes forever.
        try:
            await self.analytics_repo.log_event(
                profile_id=profile_id,
                event_type="chat_turn",
                entity_type="chat_session",
                entity_id=session_id,
                value=elapsed_study_minutes(turn_started_at),
                metadata_json=json.dumps({"mode": request.mode}),
            )
        except Exception as e:
            logger.warning("Could not record chat_turn analytics event: %s", e)

        # 9. Extract learner memories from the exchange.
        #    Only the WebSocket path did this, so a turn taken over REST left no
        #    trace in memory at all -- the same split that once left chat turns
        #    out of analytics. Detached and tracked, so it neither delays the
        #    reply nor gets collected mid-run.
        spawn(
            extract_session_memory_and_summary(
                profile_id=profile_id, session_id=session_id
            ),
            name=f"memory-extraction:{session_id}",
        )

        return TutorChatResponse(
            session_id=session_id,
            message_id=assistant_msg.id,
            content=ai_content,
            mode=request.mode,
            citations=unified_ctx.citations,
        )
