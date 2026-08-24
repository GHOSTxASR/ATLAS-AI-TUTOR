from __future__ import annotations


from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.database import get_db
from app.dependencies import get_settings_dependency
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    ChatSessionUpdate,
    TutorChatRequest,
)
from app.services.chat_service import ChatService
from app.services.tutor_orchestrator import TutorOrchestrator
from app.services.unified_context_service import UnifiedContextService

router = APIRouter(prefix="/api/v1/profiles/{profile_id}", tags=["chat"])


def envelope(data=None, error=None, meta=None):
    return {"data": data, "error": error, "meta": meta}


def get_chat_service(session: AsyncSession = Depends(get_db)) -> ChatService:
    return ChatService(session)


def get_tutor_orchestrator(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
) -> TutorOrchestrator:
    return TutorOrchestrator(session=session, settings=settings)


def get_unified_context_service(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
) -> UnifiedContextService:
    return UnifiedContextService(session=session, settings=settings)


@router.get("/sessions", response_model=dict)
async def list_sessions(
    profile_id: str,
    q: str | None = Query(None, description="Search query for chat title"),
    service: ChatService = Depends(get_chat_service),
):
    sessions = await service.get_all_sessions(profile_id, q)
    return envelope(data=[ChatSessionResponse.model_validate(s).model_dump() for s in sessions])


@router.post("/sessions", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_session(
    profile_id: str,
    data: ChatSessionCreate,
    service: ChatService = Depends(get_chat_service),
):
    session = await service.create_session(profile_id, data)
    return envelope(data=ChatSessionResponse.model_validate(session).model_dump())


@router.get("/sessions/{session_id}", response_model=dict)
async def get_session(
    profile_id: str,
    session_id: str,
    service: ChatService = Depends(get_chat_service),
):
    session = await service.get_session(profile_id, session_id)
    messages = await service.get_messages(profile_id, session_id)

    session_data = ChatSessionResponse.model_validate(session).model_dump()
    session_data["messages"] = [ChatMessageResponse.model_validate(m).model_dump() for m in messages]

    return envelope(data=session_data)


@router.patch("/sessions/{session_id}", response_model=dict)
async def update_session(
    profile_id: str,
    session_id: str,
    data: ChatSessionUpdate,
    service: ChatService = Depends(get_chat_service),
):
    session = await service.update_session(profile_id, session_id, data)
    return envelope(data=ChatSessionResponse.model_validate(session).model_dump())


@router.post("/sessions/{session_id}/autotitle", response_model=dict)
async def autotitle_session(
    profile_id: str,
    session_id: str,
    service: ChatService = Depends(get_chat_service),
):
    """Name a session after its opening message.

    Separate from the chat turn on purpose: the reply is what the user is
    waiting for, and a title is not worth adding a round trip to it. The client
    calls this once the first exchange is on screen. A session the user has
    already renamed is returned untouched.
    """
    session = await service.autotitle_session(profile_id, session_id)
    return envelope(data=ChatSessionResponse.model_validate(session).model_dump())


@router.delete("/sessions/{session_id}", response_model=dict)
async def delete_session(
    profile_id: str,
    session_id: str,
    service: ChatService = Depends(get_chat_service),
):
    await service.delete_session(profile_id, session_id)
    return envelope(data={"deleted": True})


@router.post("/sessions/{session_id}/messages", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_message(
    profile_id: str,
    session_id: str,
    data: ChatMessageCreate,
    service: ChatService = Depends(get_chat_service),
):
    message = await service.add_message(profile_id, session_id, data)
    return envelope(data=ChatMessageResponse.model_validate(message).model_dump())


@router.post("/tutor/chat", response_model=dict)
async def tutor_chat(
    profile_id: str,
    request: TutorChatRequest,
    orchestrator: TutorOrchestrator = Depends(get_tutor_orchestrator),
):
    response = await orchestrator.handle_chat_turn(profile_id=profile_id, request=request)
    return envelope(data=response.model_dump())


@router.get("/tutor/context", response_model=dict)
async def get_tutor_context(
    profile_id: str,
    q: str = Query("General overview", description="User query or concept"),
    mode: str = Query("teaching", description="Learning mode"),
    roadmap_node_id: str | None = Query(None, description="Active roadmap node ID"),
    context_service: UnifiedContextService = Depends(get_unified_context_service),
):
    ctx = await context_service.build_unified_context(
        profile_id=profile_id,
        query=q,
        mode=mode,
        roadmap_node_id=roadmap_node_id,
    )
    return envelope(data=ctx.model_dump())
