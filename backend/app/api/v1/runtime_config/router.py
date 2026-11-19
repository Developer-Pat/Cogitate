"""
Runtime configuration API endpoints.

Provides REST API for runtime configuration operations.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.domain.runtime_config.schemas import (
    RuntimeConfigCreate,
    RuntimeConfigUpdate,
    RuntimeConfigResponse,
)
from app.domain.runtime_config.services import RuntimeConfigService

logger = logging.getLogger(__name__)


def _announce(event: str, payload: dict) -> None:
    """THE CROSS-WINDOW SYNC (2026-08-25, the roadmap Phase 7):
    runtime-config:<id>:<event> — the frontend's sync reloads the open pages."""
    try:
        from app.domain.messaging.services import publish
        publish(f"runtime-config:{payload.get('config_id')}:{event}", payload)
    except Exception as e:  # pragma: no cover
        logger.error(f"  ❌ runtime-config:{event} publish failed: {e}")


router = APIRouter(prefix="/runtime-config", tags=["runtime-config"])


def get_runtime_config_service(
    db: Annotated[AsyncSession, Depends(get_db)]
) -> RuntimeConfigService:
    """Dependency to get runtime config service."""
    return RuntimeConfigService(db)


@router.get(
    "/session/{session_id}",
    response_model=RuntimeConfigResponse,
)
async def get_session_config(
    session_id: int,
    service: Annotated[RuntimeConfigService, Depends(get_runtime_config_service)],
) -> RuntimeConfigResponse:
    """
    Get runtime config for a chat session.

    Args:
        session_id: Chat session ID
        service: Runtime config service

    Returns:
        Runtime config for the session

    Raises:
        HTTPException: 404 if config not found
    """
    config = await service.get_by_session_id(session_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runtime config for session {session_id} not found",
        )
    return RuntimeConfigResponse.model_validate(config)


@router.post(
    "/session/{session_id}",
    response_model=RuntimeConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_or_update_session_config(
    session_id: int,
    config_data: RuntimeConfigCreate,
    service: Annotated[RuntimeConfigService, Depends(get_runtime_config_service)],
) -> RuntimeConfigResponse:
    """
    Create or update runtime config for a chat session.

    Args:
        session_id: Chat session ID
        config_data: Runtime config data
        service: Runtime config service

    Returns:
        Created or updated runtime config
    """
    # Ensure session_id in URL matches payload
    config_data.session_id = session_id

    config = await service.create_or_update(config_data)
    _announce("created", {"config_id": config.id, "session_id": session_id, "event": "created"})
    return RuntimeConfigResponse.model_validate(config)


@router.put(
    "/session/{session_id}",
    response_model=RuntimeConfigResponse,
)
async def update_session_config(
    session_id: int,
    config_data: RuntimeConfigUpdate,
    service: Annotated[RuntimeConfigService, Depends(get_runtime_config_service)],
) -> RuntimeConfigResponse:
    """
    Update runtime config for a chat session (partial update).

    Args:
        session_id: Chat session ID
        config_data: Runtime config update data
        service: Runtime config service

    Returns:
        Updated runtime config

    Raises:
        HTTPException: 404 if config not found
    """
    config = await service.get_by_session_id(session_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runtime config for session {session_id} not found",
        )

    # Update only provided fields
    update_data = config_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)

    await service.db.flush()
    await service.db.refresh(config)

    _announce("updated", {"config_id": config.id, "session_id": session_id, "event": "updated"})
    return RuntimeConfigResponse.model_validate(config)


@router.delete(
    "/session/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_session_config(
    session_id: int,
    service: Annotated[RuntimeConfigService, Depends(get_runtime_config_service)],
) -> None:
    """
    Delete runtime config for a chat session (reset to agent defaults).

    Args:
        session_id: Chat session ID
        service: Runtime config service

    Raises:
        HTTPException: 404 if config not found
    """
    success = await service.delete_by_session_id(session_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runtime config for session {session_id} not found",
        )

    _announce("deleted", {"config_id": None, "session_id": session_id, "event": "deleted"})


@router.post(
    "/session/{session_id}/reset",
    response_model=RuntimeConfigResponse,
)
async def reset_session_config(
    session_id: int,
    service: Annotated[RuntimeConfigService, Depends(get_runtime_config_service)],
) -> dict:
    """
    Reset runtime config to agent defaults.

    Args:
        session_id: Chat session ID
        service: Runtime config service

    Returns:
        Success message
    """
    await service.reset_to_agent_defaults(session_id)
    return {"message": "Runtime config reset to agent defaults", "session_id": session_id}
