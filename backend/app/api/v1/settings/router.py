"""
User Settings API Router.

Provides REST endpoints for user settings persistence.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.domain.settings.schemas import (
    UserSettingsRequest,
    UserSettingsResponse,
)
from app.domain.settings.services import (
    get_or_create_user_settings,
    update_user_settings,
    DEFAULT_USER_KEY,
)

logger = logging.getLogger(__name__)


def _announce(event: str, payload: dict) -> None:
    """THE CROSS-WINDOW SYNC (2026-08-25, the roadmap Phase 7):
    setting:<id>:<event> — the frontend's sync reloads the open pages."""
    try:
        from app.domain.messaging.services import publish
        publish(f"setting:{payload.get('key')}:{event}", payload)
    except Exception as e:  # pragma: no cover
        logger.error(f"  ❌ setting:{event} publish failed: {e}")


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=UserSettingsResponse)
async def get_settings(
    user_key: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get user settings.

    Returns user settings from the database. If no settings exist,
    creates default empty settings.

    **Parameters:**
    - `user_key`: User identifier (default: "default" until auth implemented)

    **Returns:**
    - User settings object
    """
    key_to_use = user_key or DEFAULT_USER_KEY

    try:
        settings = await get_or_create_user_settings(db, key_to_use)
        logger.debug(f"Retrieved settings for user: {key_to_use}")

        return UserSettingsResponse(
            user_key=settings.user_key,
            settings=settings.settings,
            updated_at=settings.updated_at,
        )
    except Exception as e:
        logger.error(f"Failed to get settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve settings: {str(e)}")


@router.put("", response_model=UserSettingsResponse)
async def update_settings(
    request: UserSettingsRequest,
    user_key: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Update user settings.

    Persists user settings to the database. Settings are stored as a JSON blob
    and can contain any valid JSON structure.

    **Parameters:**
    - `user_key`: User identifier (default: "default" until auth implemented)

    **Request Body:**
    - `settings`: Settings object to persist

    **Returns:**
    - Updated user settings object
    """
    key_to_use = user_key or DEFAULT_USER_KEY

    try:
        settings = await update_user_settings(db, request.settings, key_to_use)
        logger.debug(f"Updated settings for user: {key_to_use}")

        _announce("updated", {"key": key_to_use, "event": "updated"})
        return UserSettingsResponse(
            user_key=settings.user_key,
            settings=settings.settings,
            updated_at=settings.updated_at,
        )
    except Exception as e:
        logger.error(f"Failed to update settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {str(e)}")


@router.delete("")
async def delete_settings(
    user_key: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Delete user settings.

    **Parameters:**
    - `user_key`: User identifier (default: "default" until auth implemented)

    **Returns:**
    - Success message
    """
    from app.domain.settings.services import delete_user_settings

    key_to_use = user_key or DEFAULT_USER_KEY

    try:
        deleted = await delete_user_settings(db, key_to_use)

        if deleted:
            logger.info(f"Deleted settings for user: {key_to_use}")
            _announce("deleted", {"key": key_to_use, "event": "deleted"})
            return {"message": f"Settings deleted for user: {key_to_use}"}
        else:
            logger.warning(f"Settings not found for user: {key_to_use}")
            raise HTTPException(status_code=404, detail=f"Settings not found for user: {key_to_use}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete settings: {str(e)}")
