"""
Debug API endpoints.

Provides REST API for debugging and error tracking.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)


def _announce(event: str, payload: dict) -> None:
    """THE CROSS-WINDOW SYNC (2026-08-25, the roadmap Phase 7):
    debug:<item_id>:<event> — the frontend's sync reloads the open pages."""
    try:
        from app.domain.messaging.services import publish
        publish(f"debug:{payload.get('item_id')}:{event}", payload)
    except Exception as e:  # pragma: no cover
        logger.error(f"  ❌ debug:{event} publish failed: {e}")


router = APIRouter(prefix="/debug", tags=["debug"])


# ═══════════════════════════════════════════════════════════
# Debug Actions Endpoints
# ═══════════════════════════════════════════════════════════

@router.get("/actions")
async def list_debug_actions():
    """
    Get available debug actions.
    
    Returns list of available debug actions for development/testing.
    """
    # Stub implementation - returns empty list
    # Can be extended with actual debug actions in the future
    return {
        "actions": [],
        "total": 0,
    }


@router.get("/actions/running")
async def get_running_actions():
    """
    Get currently running debug actions.
    """
    return {
        "running": [],
        "count": 0,
    }


@router.post("/actions/{action_id}/cancel")
async def cancel_debug_action(action_id: str):
    """
    Cancel a running debug action.
    """
    _announce("updated", {"item_id": action_id, "event": "updated"})

    return {
        "success": True,
        "message": f"Action {action_id} cancelled",
    }


@router.delete("/actions/history")
async def clear_actions_history():
    """
    Clear debug actions history.
    """
    _announce("deleted", {"item_id": "all", "event": "deleted"})

    return {
        "success": True,
        "message": "Actions history cleared",
    }


# ═══════════════════════════════════════════════════════════
# Error Tracking Endpoints
# ═══════════════════════════════════════════════════════════

@router.get("/errors")
async def list_errors(
    type: Optional[str] = Query(None, description="Filter by error type"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    status: Optional[str] = Query(None, description="Filter by status"),
    source: Optional[str] = Query(None, description="Filter by source"),
    search: Optional[str] = Query(None, description="Search in error messages"),
    from_date: Optional[str] = Query(None, alias="from", description="Filter from date"),
    to_date: Optional[str] = Query(None, alias="to", description="Filter to date"),
):
    """
    Get tracked errors with optional filters.
    
    Returns list of errors matching the specified filters.
    """
    # Stub implementation - returns empty list
    # Can be extended with actual error tracking in the future
    return {
        "errors": [],
        "total": 0,
        "filters": {
            "type": type,
            "severity": severity,
            "status": status,
            "source": source,
            "search": search,
            "from": from_date,
            "to": to_date,
        }
    }


@router.get("/errors/{error_id}")
async def get_error(error_id: str):
    """
    Get specific error by ID.
    """
    return {
        "error": None,
        "message": f"Error {error_id} not found",
    }


@router.post("/errors/{error_id}/resolve")
async def resolve_error(error_id: str):
    """
    Mark an error as resolved.
    """
    _announce("updated", {"item_id": error_id, "event": "updated"})

    return {
        "success": True,
        "message": f"Error {error_id} marked as resolved",
    }


@router.delete("/errors/{error_id}")
async def delete_error(error_id: str):
    """
    Delete a specific error.
    """
    _announce("deleted", {"item_id": error_id, "event": "deleted"})

    return {
        "success": True,
        "message": f"Error {error_id} deleted",
    }


@router.delete("/errors/resolved")
async def delete_resolved_errors():
    """
    Delete all resolved errors.
    """
    _announce("deleted", {"item_id": "all", "event": "deleted"})

    return {
        "success": True,
        "message": "Resolved errors deleted",
    }
