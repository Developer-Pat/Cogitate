"""
Agent Registry API router.

REST endpoints for managing DB-backed agent packages.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.domain.agent_registry.service import AgentRegistryService
from app.domain.agent_registry.schemas import (
    AGENT_LIFECYCLE_STATUSES,
    AgentPackageCreate,
    AgentPackageUpdate,
    AgentPackageResponse,
    AgentPackageListResponse,
    AgentPackageLineageResponse,
)

logger = logging.getLogger(__name__)


def _announce(event: str, payload: dict) -> None:
    """THE CROSS-WINDOW SYNC (2026-08-25, the roadmap Phase 6):
    agent-registry:<id>:<event> — the frontend's sync reloads the open pages."""
    try:
        from app.domain.messaging.services import publish
        publish(f"agent-registry:{payload.get('registry_id')}:{event}", payload)
    except Exception as e:  # pragma: no cover
        logger.error(f"  ❌ agent-registry:{event} publish failed: {e}")


router = APIRouter(prefix="/agent-registry", tags=["agent-registry"])


async def get_registry_service(
    db: AsyncSession = Depends(get_db_session),
) -> AgentRegistryService:
    """Dependency: get an initialized AgentRegistryService."""
    return AgentRegistryService(db)


# ── CRUD Endpoints ────────────────────────────────────────────────────────


@router.post("/packages", response_model=AgentPackageResponse, status_code=201)
async def create_package(
    data: AgentPackageCreate,
    service: AgentRegistryService = Depends(get_registry_service),
):
    """
    Create a new agent package.

    The package is stored in the database with its code, prompt,
    and lifecycle status.
    """
    try:
        package = await service.create(data)
        _announce("created", {
            "registry_id": getattr(package, "registry_id", None) or package.id,
            "event": "created",
            "name": getattr(package, "name", None),
        })
        return package
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/packages", response_model=AgentPackageListResponse)
async def list_packages(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[str] = Query(None, description="Filter by lifecycle status"),
    search: Optional[str] = Query(None, description="Search in name and role"),
    role: Optional[str] = Query(None, description="Filter by role"),
    service: AgentRegistryService = Depends(get_registry_service),
):
    """
    List agent packages with filtering and pagination.

    Supports filtering by status, search term, and role.
    """
    try:
        return await service.list(
            skip=skip, limit=limit, status=status,
            search=search, role=role,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# NOTE: /packages/active MUST be defined before /packages/{package_id}
# to avoid FastAPI matching "active" as an integer package_id.


@router.get("/packages/active", response_model=AgentPackageListResponse)
async def list_active_packages(
    limit: int = Query(100, ge=1, le=500),
    service: AgentRegistryService = Depends(get_registry_service),
):
    """
    List all active agent packages.

    Shortcut for GET /packages?status=active
    """
    packages = await service.get_active_packages(limit=limit)
    return AgentPackageListResponse(
        items=[AgentPackageResponse.model_validate(p) for p in packages],
        total=len(packages),
    )


@router.get("/packages/{package_id}", response_model=AgentPackageResponse)
async def get_package(
    package_id: int,
    service: AgentRegistryService = Depends(get_registry_service),
):
    """
    Get a specific agent package by ID.
    """
    package = await service.get_by_id(package_id)
    if not package:
        raise HTTPException(
            status_code=404,
            detail=f"Agent package {package_id} not found",
        )
    return package


@router.put("/packages/{package_id}", response_model=AgentPackageResponse)
async def update_package(
    package_id: int,
    data: AgentPackageUpdate,
    service: AgentRegistryService = Depends(get_registry_service),
):
    """
    Update an existing agent package.

    Only provided fields are updated. Status transitions are validated.
    """
    try:
        package = await service.update(package_id, data)
        if not package:
            raise HTTPException(
                status_code=404,
                detail=f"Agent package {package_id} not found",
            )
        _announce("updated", {
            "registry_id": getattr(package, "registry_id", None) or package.id,
            "event": "updated",
            "name": getattr(package, "name", None),
        })
        return package
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/packages/{package_id}", status_code=204)
async def delete_package(
    package_id: int,
    service: AgentRegistryService = Depends(get_registry_service),
):
    """
    Delete an agent package by ID.
    """
    deleted = await service.delete(package_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Agent package {package_id} not found",
        )
    _announce("deleted", {
        "registry_id": package_id,
        "event": "deleted",
    })


# ── Lifecycle Endpoints ───────────────────────────────────────────────────


@router.put(
    "/packages/{package_id}/status",
    response_model=AgentPackageResponse,
)
async def set_package_status(
    package_id: int,
    status: str = Query(..., description="Target lifecycle status"),
    service: AgentRegistryService = Depends(get_registry_service),
):
    """
    Change the lifecycle status of an agent package.

    Valid transitions:
    - experimental → active, archived, deprecated
    - active → experimental, archived, deprecated
    - archived → active, deprecated
    - deprecated → archived
    """
    if status not in AGENT_LIFECYCLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{status}'. "
            f"Must be one of: {', '.join(sorted(AGENT_LIFECYCLE_STATUSES))}",
        )

    try:
        package = await service.set_status(package_id, status)
        if not package:
            raise HTTPException(
                status_code=404,
                detail=f"Agent package {package_id} not found",
            )
        return package
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))




# ── Versioning / Lineage Endpoints ────────────────────────────────────────


@router.post(
    "/packages/{package_id}/versions",
    response_model=AgentPackageResponse,
    status_code=201,
)
async def create_package_version(
    package_id: int,
    new_name: Optional[str] = Query(None, description="Optional new name"),
    new_version: Optional[str] = Query(None, description="Version string"),
    service: AgentRegistryService = Depends(get_registry_service),
):
    """
    Create a new version derived from an existing package.

    The new package will have parent_version_id pointing to the source.
    New versions start with status 'experimental'.
    """
    try:
        package = await service.create_version(
            source_package_id=package_id,
            new_name=new_name,
            new_version=new_version,
        )
        return package
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/packages/{package_id}/lineage",
    response_model=AgentPackageLineageResponse,
)
async def get_package_lineage(
    package_id: int,
    service: AgentRegistryService = Depends(get_registry_service),
):
    """
    Get the full lineage tree for a package.

    Returns the package itself, its ancestors (parent chain),
    and its descendants (children chain).
    """
    lineage = await service.get_lineage(package_id)
    if not lineage:
        raise HTTPException(
            status_code=404,
            detail=f"Agent package {package_id} not found",
        )
    return lineage


# ── Bulk Operations ───────────────────────────────────────────────────────


@router.post("/packages/archive-by-role", response_model=dict)
async def archive_packages_by_role(
    role: str = Query(..., description="Role to archive"),
    service: AgentRegistryService = Depends(get_registry_service),
):
    """
    Archive all active/experimental packages with a given role.
    """
    count = await service.archive_all_by_role(role)
    return {"archived_count": count, "role": role}


# ── Nucleus Execution ─────────────────────────────────────────────────────


class NucleusExecuteRequest(BaseModel):
    """Request body for Nucleus execution."""
    context: Dict[str, Any] = Field(default_factory=dict)


@router.post("/packages/{package_id}/execute")
async def execute_package(
    package_id: int,
    body: NucleusExecuteRequest = Body(default=None),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Execute an agent package via the Nucleus harness.

    Loads the package code from the database and executes it in a
    restricted namespace, returning the result of ``run(context)``.

    This is the primary runtime endpoint for the Nucleus base harness.
    """
    from app.domain.agent_registry.nucleus import Nucleus

    nucleus = Nucleus(db)
    try:
        result = await nucleus.run_by_id(package_id, body.context if body else {})
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/execute")
async def execute_package_by_name(
    name: str,
    body: NucleusExecuteRequest = Body(default=None),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Execute an agent package by name via the Nucleus harness.

    Example::

        POST /api/v1/agent-registry/execute?name=hello_world
        {"context": {"name": "Nucleus"}}
    """
    from app.domain.agent_registry.nucleus import Nucleus

    nucleus = Nucleus(db)
    try:
        result = await nucleus.run(name, body.context if body else {})
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Status / Health ───────────────────────────────────────────────────────


@router.get("/status")
async def registry_status(
    service: AgentRegistryService = Depends(get_registry_service),
):
    """
    Get registry status summary.
    """
    packages = await service.list(limit=0)  # Just get total count
    active = await service.get_active_packages(limit=0)

    return {
        "total_packages": packages.total,
        "active_packages": len(active),
        "available_statuses": sorted(AGENT_LIFECYCLE_STATUSES),
    }
