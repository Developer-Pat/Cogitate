"""
Session API endpoints.

Provides REST API for session management.
"""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.core.access_evidence import format_ids, record_destructive_evidence
from app.core.dependencies import get_db
from app.domain.sessions.schemas import (
    MessageCreate,
    SessionCreate,
    SessionListResponse,
    SessionResponse,
    SessionUpdate,
)
from app.domain.sessions.services import SessionService
from app.domain.title.services import get_title_service
from app.infrastructure.database.models import Agent

logger = logging.getLogger(__name__)


async def _attach_agent_models(
    responses: list[SessionResponse] | SessionResponse,
    service: SessionService,
) -> None:
    """Attach each session's agent model to its response (2026-09-06):
    the sessions payload never carried the model, so the frontend's
    converter fell back to 'llama3.2' + warned per session ('Session
    model missing'). One agents lookup per batch — the sessions know
    their agent_id; the model lives on agents.model."""
    items = responses if isinstance(responses, list) else [responses]
    agent_ids = {r.agent_id for r in items if r.agent_id is not None}
    if not agent_ids:
        return
    result = await service.db.execute(
        select(Agent.id, Agent.model).where(Agent.id.in_(agent_ids))
    )
    model_by_agent = {aid: model for aid, model in result.all()}
    for r in items:
        if r.agent_id in model_by_agent:
            r.model = model_by_agent[r.agent_id]


def _announce(event: str, payload: dict, scope: str | int | None = None) -> None:
    """THE CROSS-WINDOW SYNC (2026-08-25, the user's audit catch):
    the sessions' mutations used to die in the mutating window —
    the other tabs stayed stale. Publish the session event on the
    bus; the frontend's useSessionSync hears it + updates the
    shared store. The agents' adopt already follows this pattern.

    `scope` names the subject for a BULK change: a clear-all has no
    single session id, so the topic is session:all:<event> and the
    frontend's bulk branch reloads the whole list."""
    try:
        from app.domain.messaging.services import publish
        subject = payload.get('session_id') if scope is None else scope
        publish(f"session:{subject}:{event}", payload)
    except Exception as e:  # pragma: no cover
        logger.error(f"  ❌ session:{event} publish failed: {e}")

router = APIRouter(prefix="/sessions", tags=["sessions"])


def get_session_service(db: Annotated[AsyncSession, Depends(get_db)]) -> SessionService:
    """Dependency to get session service."""
    return SessionService(db)


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 10,
    include_messages: Annotated[bool, Query(description="Include full messages (slow) or titles only (fast)")] = False,
    agent_id: Annotated[Optional[int], Query(description="Filter by agent ID")] = None,
    unnamed_only: Annotated[bool, Query(description="Only show sessions with no title")] = False,
    source: Annotated[Optional[str], Query(description="Filter by session source ('agent' | 'exa')")] = None,
    service: Annotated[SessionService | None, Depends(get_session_service)] = None,
) -> SessionListResponse:
    """
    List all chat sessions with pagination.

    Args:
        page: Page number (default: 1)
        page_size: Items per page (default: 10, max: 100)
        include_messages: If True, include full message history (slow). If False, return titles only (fast).
        source: If set, only sessions from that surface ('agent' |
            'exa') — the agent chat requests 'agent', the Exa page
            'exa' (2026-09-04, the exa-leak dig).
        service: Session service

    Returns:
        Paginated list of sessions
    """
    if service is None:
        raise HTTPException(status_code=500, detail="Service not initialized")

    skip = (page - 1) * page_size
    sessions, total = await service.list_all(skip=skip, limit=page_size, agent_id=agent_id, unnamed_only=unnamed_only, source=source)

    # If include_messages is False, return titles only (faster, less bandwidth)
    if not include_messages:
        # THE COUNT IS FETCHED, NOT INFERRED (2026-09-15). `messages=[]` below is
        # deliberate (titles-only is the fast path), but it left the frontend with
        # nothing honest to display, so it read the lazily-loaded `messages` array
        # instead: 0 for unopened sessions, and a stale count for the open one
        # ("I deleted all the messages and it still shows 96"). One grouped COUNT
        # across the page's ids keeps the fast path fast and makes the number true.
        counts = await service.message_counts([s.id for s in sessions])
        responses = [
            SessionResponse(
                id=s.id,
                title=s.title,
                agent_id=s.agent_id,
                source=s.source,
                is_active=s.is_active,
                created_at=s.created_at,
                updated_at=s.updated_at,
                messages=[],  # Empty messages for titles-only
                message_count=counts.get(s.id, 0),
            )
            for s in sessions
        ]
        await _attach_agent_models(responses, service)
        return SessionListResponse(
            sessions=responses,
            total=total,
            page=page,
            page_size=page_size,
        )

    # Return full sessions with messages
    responses = [SessionResponse.model_validate(s) for s in sessions]
    await _attach_agent_models(responses, service)
    return SessionListResponse(
        sessions=responses,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/search", response_model=SessionListResponse)
async def search_sessions(
    q: Annotated[str, Query(min_length=1, max_length=200, description="Search query for session titles")],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 10,
    include_messages: Annotated[bool, Query(description="Include full messages (slow) or titles only (fast)")] = False,
    service: Annotated[SessionService | None, Depends(get_session_service)] = None,
) -> SessionListResponse:
    """
    Search sessions by title with pagination.

    Performs a case-insensitive search against session titles.
    Returns paginated results matching the search query.

    Args:
        q: Search query to match against session titles
        page: Page number (default: 1)
        page_size: Items per page (default: 10, max: 100)
        include_messages: If True, include full message history (slow). If False, return titles only (fast).
        service: Session service

    Returns:
        Paginated list of matching sessions
    """
    if service is None:
        raise HTTPException(status_code=500, detail="Service not initialized")

    skip = (page - 1) * page_size
    sessions, total = await service.search_by_title(query=q, skip=skip, limit=page_size)

    # If include_messages is False, return titles only
    if not include_messages:
        # Same count fix as list_sessions, for the same reason: `messages=[]` is
        # the fast path, so a caller wanting a count must be given a real one.
        counts = await service.message_counts([s.id for s in sessions])
        responses = [
            SessionResponse(
                id=s.id,
                title=s.title,
                agent_id=s.agent_id,
                is_active=s.is_active,
                created_at=s.created_at,
                updated_at=s.updated_at,
                messages=[],
                message_count=counts.get(s.id, 0),
            )
            for s in sessions
        ]
        await _attach_agent_models(responses, service)
        return SessionListResponse(
            sessions=responses,
            total=total,
            page=page,
            page_size=page_size,
        )

    # Return full sessions with messages
    responses = [SessionResponse.model_validate(s) for s in sessions]
    await _attach_agent_models(responses, service)
    return SessionListResponse(
        sessions=responses,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: int,
    service: Annotated[SessionService, Depends(get_session_service)],
) -> SessionResponse:
    """
    Get session by ID with messages.

    Args:
        session_id: Session ID
        service: Session service

    Returns:
        Session with messages

    Raises:
        HTTPException: 404 if session not found
    """
    session = await service.get_by_id(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    response = SessionResponse.model_validate(session)
    await _attach_agent_models(response, service)
    return response


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    session_data: SessionCreate,
    service: Annotated[SessionService, Depends(get_session_service)],
) -> SessionResponse:
    """
    Create a new chat session.

    Args:
        session_data: Session creation data
        service: Session service

    Returns:
        Created session
    """
    session = await service.create(session_data)
    _announce("created", {"session_id": session.id, "title": getattr(session, "title", None), "event": "created"})
    response = SessionResponse.model_validate(session)
    await _attach_agent_models(response, service)
    return response


@router.post("/{session_id}/messages", status_code=status.HTTP_201_CREATED)
async def add_session_message(
    session_id: int,
    message_data: MessageCreate,
    service: Annotated[SessionService, Depends(get_session_service)],
) -> dict:
    """
    Append a message to a session (the Exa bridge's save path, 2026-08-21).

    The normal chat persists messages inside its pipeline handler;
    the external surface (Exa) has no pipeline — this is the
    explicit save endpoint the bridge calls after streaming.
    """
    msg = await service.add_message(
        session_id, message_data.role, message_data.content
    )
    return {
        "id": msg.id,
        "session_id": msg.session_id,
        "role": msg.role,
        "content": msg.content,
    }


# THE SMART RENAME (2026-08-22, user): generate a title from the
# session's FULL conversation (the title service reads the first 5
# messages; the old callers passed only the first message — a "hello"
# produced a hello-title). The model is the DB default provider
# (local ollama/phi4-mini, configurable on the System page — NO
# hard-coded provider). Returns the generated title; the caller
# persists it via the existing PUT.
class TitleGenerationBody(BaseModel):
    """Optional request body for the smart-rename endpoint."""
    model: Optional[str] = Field(
        default=None,
        description="Model override (agent/custom preference); None = the DB default provider",
    )


@router.post("/{session_id}/title")
async def generate_session_title_from_conversation(
    session_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[SessionService, Depends(get_session_service)],
    body: Optional[TitleGenerationBody] = Body(default=None),
) -> dict:
    """Generate a title from the session's FULL conversation.

    Honors the per-request model override exactly like the chat-page
    rename path (/chat/generate-title) — the model source is decided
    by the caller (the title preference), not hardcoded to the DB
    default. model=None -> backend_default (the provider row).
    """
    session = await service.get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    messages = getattr(session, "messages", None) or []
    conv = [
        {"role": m.role if hasattr(m, "role") else "user",
         "content": m.content if hasattr(m, "content") else str(m)}
        for m in messages
    ]
    if not conv:
        raise HTTPException(status_code=400, detail="Session has no messages to name")
    title_service = get_title_service()
    generated = await title_service.generate_title(
        messages=conv,
        user_enabled=True,
        db=db,
        model_override=body.model if body else None,
    )
    if not generated:
        raise HTTPException(status_code=502, detail="Title generation failed (the local model may be busy)")
    return {"session_id": session_id, "title": generated, "source": "full-conversation", "model_override": body.model if body else None}


@router.put("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: int,
    session_data: SessionUpdate,
    service: Annotated[SessionService, Depends(get_session_service)],
) -> SessionResponse:
    """
    Update an existing session.

    Args:
        session_id: Session ID
        session_data: Session update data
        service: Session service

    Returns:
        Updated session

    Raises:
        HTTPException: 404 if session not found
    """
    session = await service.update(session_id, session_data)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    # THE CROSS-WINDOW RENAME (2026-08-25): the other tabs hear the
    # rename + update their store.
    _announce("updated", {"session_id": session_id, "title": getattr(session, "title", None), "event": "updated"})
    response = SessionResponse.model_validate(session)
    await _attach_agent_models(response, service)
    return response


# `:int` IS LOAD-BEARING (2026-09-19): without it this route swallowed
# DELETE /sessions/all — declared further down, the literal path reached this
# int parameter first and 422'd, so the delete-all endpoint was UNREACHABLE and
# the debugging Database Tools' "delete all sessions" button failed. The
# converter makes the id route match DIGITS ONLY, so no literal sibling can
# ever be swallowed by it again.
@router.delete("/{session_id:int}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: int,
    request: Request,
    service: Annotated[SessionService, Depends(get_session_service)],
) -> None:
    """
    Delete a session.

    Args:
        session_id: Session ID
        service: Session service

    Raises:
        HTTPException: 404 if session not found
    """
    logger.info("Delete session: id=%d", session_id)
    success = await service.delete(session_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    _announce("deleted", {"session_id": session_id, "event": "deleted"})
    record_destructive_evidence(
        request.url.path, f"deleted session id={session_id}"
    )


@router.post("/bulk-delete", status_code=status.HTTP_200_OK)
async def bulk_delete_sessions(
    session_ids: Annotated[list[int], Body()],
    request: Request,
    service: Annotated[SessionService, Depends(get_session_service)],
):
    """
    Delete multiple sessions at once using a single SQL query.

    Args:
        session_ids: List of session IDs to delete
        service: Session service

    Returns:
        dict: Deletion results
    """
    logger.info("Bulk delete request: ids=%s", session_ids)
    total_before = await service.count_all()
    deleted_count = await service.bulk_delete(session_ids)
    total_after = await service.count_all()

    logger.info("Bulk delete result: requested=%d deleted=%d before=%d after=%d", len(session_ids), deleted_count, total_before, total_after)
    # THE CROSS-WINDOW BULK (2026-08-25): the other tabs hear the
    # deletions + remove the rows.
    for sid in session_ids:
        _announce("deleted", {"session_id": sid, "event": "deleted"})
    # THE DESTRUCTIVE EVIDENCE (2026-09-11): the access journal alone
    # recorded only `POST ... 200` — it proved the request happened and
    # could not say WHAT it destroyed. Write the ids where the evidence
    # tool can find them.
    record_destructive_evidence(
        request.url.path,
        f"deleted={deleted_count} ids={format_ids(session_ids)}",
    )
    return {
        "deleted": session_ids,
        "failed": [],
        "total_requested": len(session_ids),
        "total_deleted": deleted_count,
        "total_failed": 0,
    }


@router.delete("", status_code=status.HTTP_200_OK)
async def clear_all_sessions(
    request: Request,
    service: Annotated[SessionService, Depends(get_session_service)],
):
    """
    Delete ALL sessions.

    This is a destructive action that removes every session from the database.
    Use with caution.

    Returns:
        dict: Deletion results with count of deleted sessions.
    """
    deleted_count = await service.clear_all()
    # This endpoint deleted EVERY session in silence (2026-09-11): no
    # logger call, no cross-tab announcement, and the access journal saw
    # only `DELETE /api/v1/sessions 200`. A total wipe must say so.
    logger.warning("Clear ALL sessions: deleted=%d", deleted_count)
    record_destructive_evidence(
        request.url.path,
        f"CLEARED ALL sessions: deleted={deleted_count}",
    )
    # ...and the OTHER TABS must hear it too (2026-09-19): the wipe was
    # silent ON THE BUS, so every other open tab kept rendering rows that
    # no longer existed. ONE event for the bulk wipe — there is no single
    # session id, hence scope='all' (session:all:cleared); the frontend's
    # bulk branch reloads the list.
    _announce("cleared", {"event": "cleared", "count": deleted_count, "scope": "all"}, scope="all")
    return {
        "success": True,
        "deleted_count": deleted_count,
        "message": f"All {deleted_count} sessions cleared successfully.",
    }


@router.get("/agent/{agent_id}")
async def get_agent_sessions(
    agent_id: int,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    service: Annotated[SessionService | None, Depends(get_session_service)] = None,
):
    """
    Get all sessions for a specific agent.

    Args:
        agent_id: Agent ID
        page: Page number
        page_size: Items per page
        service: Session service

    Returns:
        Paginated list of sessions for the agent
    """
    if service is None:
        raise HTTPException(status_code=500, detail="Service not initialized")

    skip = (page - 1) * page_size
    sessions, total = await service.get_agent_sessions(
        agent_id, skip=skip, limit=page_size
    )

    return {
        "sessions": [SessionResponse.model_validate(s) for s in sessions],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.delete("/all", status_code=status.HTTP_200_OK)
async def delete_all_sessions(
    request: Request,
    service: Annotated[SessionService, Depends(get_session_service)],
):
    """
    Delete ALL sessions and their messages.
    
    WARNING: This is a destructive operation that cannot be undone.
    Use with caution - primarily for development/testing.
    
    Returns:
        dict: Deletion summary
    """
    # Count before delete
    sessions, total = await service.list_all(skip=0, limit=10000, agent_id=None, unnamed_only=False)
    session_count = total
    
    # Delete all sessions (service.delete cascades to messages)
    deleted = []
    failed = []
    
    for session in sessions:
        try:
            success = await service.delete(session.id)
            if success:
                deleted.append(session.id)
            else:
                failed.append({"id": session.id, "reason": "not found"})
        except Exception as e:
            failed.append({"id": session.id, "reason": str(e)})
    
    # THE DESTRUCTIVE EVIDENCE (2026-09-11): like clear-all, this wiped
    # sessions with no logger call and no journal detail.
    logger.warning(
        "Delete ALL sessions: requested=%d deleted=%d failed=%d",
        session_count, len(deleted), len(failed),
    )
    record_destructive_evidence(
        request.url.path,
        f"DELETED ALL: deleted={len(deleted)} ids={format_ids(deleted)}",
    )
    # The bulk wipe announces ONCE (2026-09-19) — one event per deleted
    # session would flood the bus for a whole-database clear, and the
    # frontend only needs to know the list changed (scope='all').
    if deleted:
        _announce(
            "deleted_all",
            {"event": "deleted_all", "count": len(deleted), "scope": "all"},
            scope="all",
        )
    return {
        "deleted": deleted,
        "failed": failed,
        "total_requested": session_count,
        "total_deleted": len(deleted),
        "total_failed": len(failed),
    }
