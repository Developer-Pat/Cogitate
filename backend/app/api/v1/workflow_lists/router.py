"""
Workflow Lists API router.

REST API endpoints for workflow list management.
"""

import logging
from typing import Optional, cast
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.services.workflow_list_service import WorkflowListService
from app.domain.workflow_lists.schemas import (
    WorkflowListCreate,
    WorkflowListUpdate,
    WorkflowListResponse,
    WorkflowListListResponse,
    WorkflowListWorkflowsResponse,
    WorkflowInListResponse,
)

logger = logging.getLogger(__name__)


def _announce(event: str, payload: dict) -> None:
    """THE CROSS-WINDOW SYNC (2026-08-25, the roadmap Phase 6):
    workflow-list:<id>:<event> — the frontend's sync reloads the open pages."""
    try:
        from app.domain.messaging.services import publish
        publish(f"workflow-list:{payload.get('list_id')}:{event}", payload)
    except Exception as e:  # pragma: no cover
        logger.error(f"  ❌ workflow-list:{event} publish failed: {e}")


router = APIRouter(prefix="/workflow-lists", tags=["Workflow Lists"])


@router.get("", response_model=WorkflowListListResponse)
async def list_workflow_lists(
    user_key: str = Query(default="default", description="User key"),
    tags: Optional[str] = Query(default=None, description="Comma-separated tags to filter by"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    all: bool = Query(False, description="Return all workflow lists without pagination limits"),
    db: AsyncSession = Depends(get_db_session)
):
    """
    List all workflow lists for a user.

    Returns workflow lists ordered by default status (default first) and name.
    Supports filtering by tags.

    Args:
        user_key: User key for filtering
        tags: Optional comma-separated tags to filter by
        limit: Maximum items per page
        offset: Pagination offset
        all: If True, return all workflow lists without pagination limits
    """
    service = WorkflowListService(db)
    
    # Parse tags if provided
    tag_list = None
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    
    # Override pagination if all=true
    if all:
        limit = 10000
        offset = 0
    
    workflow_lists, total = await service.list_workflow_lists(
        user_key, tag_list, limit, offset
    )

    return WorkflowListListResponse(
        workflow_lists=[service.to_response(wl) for wl in workflow_lists],
        total=total
    )


@router.get("/search", response_model=WorkflowListListResponse)
async def search_workflow_lists(
    q: str = Query(..., min_length=1, max_length=200, description="Search query for workflow lists (matches name, description)"),
    user_key: str = Query(default="default", description="User key"),
    tags: Optional[str] = Query(default=None, description="Comma-separated tags to filter by"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Search workflow lists by name or description (case-insensitive).

    Performs a case-insensitive search against workflow list name and
    description fields. Returns paginated results.

    Args:
        q: Search query string
        user_key: User key for filtering
        tags: Optional comma-separated tags to filter by
        limit: Maximum items per page
        offset: Pagination offset
    """
    service = WorkflowListService(db)

    # Parse tags if provided
    tag_list = None
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    workflow_lists, total = await service.search_workflow_lists(
        query=q, user_key=user_key, tags=tag_list, limit=limit, offset=offset
    )

    return WorkflowListListResponse(
        workflow_lists=[service.to_response(wl) for wl in workflow_lists],
        total=total
    )


@router.get("/{list_id}", response_model=WorkflowListResponse)
async def get_workflow_list(
    list_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get a single workflow list by ID.
    """
    service = WorkflowListService(db)
    workflow_list = await service.get_workflow_list(list_id)

    if not workflow_list:
        raise HTTPException(status_code=404, detail="Workflow list not found")

    return service.to_response(workflow_list)


@router.get("/{list_id}/workflows", response_model=WorkflowListWorkflowsResponse)
async def get_workflows_in_list(
    list_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get all workflows in a workflow list.

    Returns workflows in the order they appear in the list.
    """
    service = WorkflowListService(db)
    workflows = await service.get_workflows_in_list(list_id)

    return WorkflowListWorkflowsResponse(
        workflows=[cast(WorkflowInListResponse, service.workflow_to_response(wf)) for wf in workflows],
        total=len(workflows)
    )


@router.post("", response_model=WorkflowListResponse, status_code=201)
async def create_workflow_list(
    data: WorkflowListCreate,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Create a new workflow list.

    If is_default is True, this list becomes the default and any existing
    default list is unset.
    """
    service = WorkflowListService(db)
    workflow_list = await service.create_workflow_list(data)
    _announce("created", {
        "list_id": getattr(workflow_list, "list_id", None) or workflow_list.id,
        "event": "created",
        "name": getattr(workflow_list, "name", None),
    })
    return service.to_response(workflow_list)


@router.put("/{list_id}", response_model=WorkflowListResponse)
async def update_workflow_list(
    list_id: str,
    data: WorkflowListUpdate,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Update an existing workflow list.

    Can update name, description, workflow IDs, default status, and tags.
    """
    service = WorkflowListService(db)
    workflow_list = await service.update_workflow_list(list_id, data)

    if not workflow_list:
        raise HTTPException(status_code=404, detail="Workflow list not found")

    _announce("updated", {
        "list_id": getattr(workflow_list, "list_id", None) or workflow_list.id,
        "event": "updated",
        "name": getattr(workflow_list, "name", None),
    })
    return service.to_response(workflow_list)


@router.delete("/{list_id}", status_code=204)
async def delete_workflow_list(
    list_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Delete a workflow list.

    Cannot delete the last default workflow list for a user.
    """
    service = WorkflowListService(db)
    success = await service.delete_workflow_list(list_id)

    if not success:
        raise HTTPException(status_code=404, detail="Workflow list not found")

    _announce("deleted", {
        "list_id": list_id,
        "event": "deleted",
    })

@router.post("/{list_id}/workflows/{workflow_id}", response_model=WorkflowListResponse)
async def add_workflow_to_list(
    list_id: str,
    workflow_id: str,
    position: Optional[int] = Query(default=None, ge=0, description="Position to insert"),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Add a workflow to a workflow list.

    If position is specified, the workflow is inserted at that position.
    Otherwise, the workflow is appended to the end.
    """
    service = WorkflowListService(db)
    workflow_list = await service.add_workflow_to_list(list_id, workflow_id, position)

    if not workflow_list:
        raise HTTPException(status_code=404, detail="Workflow list not found")

    return service.to_response(workflow_list)


@router.delete("/{list_id}/workflows/{workflow_id}", response_model=WorkflowListResponse)
async def remove_workflow_from_list(
    list_id: str,
    workflow_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Remove a workflow from a workflow list.
    """
    service = WorkflowListService(db)
    workflow_list = await service.remove_workflow_from_list(list_id, workflow_id)

    if not workflow_list:
        raise HTTPException(status_code=404, detail="Workflow list not found")

    return service.to_response(workflow_list)
