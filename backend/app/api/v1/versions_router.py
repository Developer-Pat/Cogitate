"""
Workflow versions API router.

Provides HTTP endpoints for managing workflow versions:
- Create new versions
- List versions for a template
- Get specific version details
- Update version configuration
- Delete versions
- Activate/deactivate versions
- Compare versions

URL Prefix: /api/v1/workflows/{template_id}/versions
"""

import logging
from fastapi import APIRouter, HTTPException, Query, Path

from app.domain.workflows.schemas.version_config import (
    VersionCreate,
    VersionUpdate,
    VersionResponse,
    VersionListResponse,
    VersionComparisonResult,
)
from app.domain.workflows.services.version_service import VersionService

from datetime import datetime, UTC
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflows", tags=["Workflow Versions"])
version_service = VersionService()


@router.post(
    "/{template_id}/versions",
    response_model=VersionResponse,
    status_code=201,
    summary="Create Workflow Version",
    description="Create a new version for a workflow template"
)
async def create_version(
    template_id: str = Path(..., description="Workflow template ID"),
    config: VersionCreate | None = None
):
    """
    Create a new workflow version.

    - **template_id**: ID of the workflow template
    - **version**: Version string (e.g., 'v1.0', 'v2.0')
    - **config**: Workflow configuration for this version
    - **changelog**: Description of changes
    - **created_by**: Optional creator identifier

    **Returns**: Created version information

    **Raises**:
    - 400: Invalid version format
    - 409: Version already exists
    """
    if config is None:
        raise HTTPException(status_code=400, detail="Version configuration is required")
    try:
        version = version_service.create_version(template_id, config)
        logger.info(f"✅ API: Created version {version.version} for template {template_id}")
        return VersionResponse(
            id=version.id,
            template_id=version.template_id,
            version=version.version,
            config=version.config,
            changelog=version.changelog,
            is_active=version.is_active,
            created_by=version.created_by,
            created_at=datetime.now(UTC),
        )
    except ValueError as e:
        logger.error(f"❌ API: Invalid version format - {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ API: Failed to create version - {e}")
        if "UNIQUE constraint" in str(e):
            raise HTTPException(
                status_code=409,
                detail=f"Version {config.version} already exists for template {template_id}"
            )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/{template_id}/versions",
    response_model=VersionListResponse,
    summary="List Workflow Versions",
    description="List all versions for a workflow template"
)
async def list_versions(
    template_id: str = Path(..., description="Workflow template ID"),
    active_only: bool = Query(False, description="Only return active versions")
):
    """
    List all versions for a workflow template.

    - **template_id**: ID of the workflow template
    - **active_only**: Filter to only active versions (default: False)

    **Returns**: List of versions with metadata
    """
    try:
        versions = version_service.list_versions(template_id, active_only=active_only)
        logger.info(f"✅ API: Listed {len(versions)} versions for template {template_id}")

        return VersionListResponse(
            versions=[
                VersionResponse(
                    id=v.id,
                    template_id=v.template_id,
                    version=v.version,
                    config=v.config,
                    changelog=v.changelog,
                    is_active=v.is_active,
                    created_by=v.created_by,
                    created_at=datetime.now(UTC),
                )
                for v in versions
            ],
            total=len(versions)
        )
    except Exception as e:
        logger.error(f"❌ API: Failed to list versions - {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ===========================================================================
# Static Routes (must be before dynamic routes)
# ===========================================================================

@router.get(
    "/{template_id}/versions/active",
    response_model=VersionResponse,
    summary="Get Active Workflow Version",
    description="Get the currently active version for a template"
)
async def get_active_version(
    template_id: str = Path(..., description="Workflow template ID")
):
    """
    Get the currently active version for a workflow template.

    - **template_id**: ID of the workflow template

    **Returns**: Active version information

    **Raises**:
    - 404: No active version found
    """
    try:
        v = version_service.get_active_version(template_id)
        if not v:
            logger.warning(f"⚠️ API: No active version found for template {template_id}")
            raise HTTPException(
                status_code=404,
                detail=f"No active version found for template {template_id}"
            )

        logger.info(f"✅ API: Retrieved active version {v.version} for template {template_id}")
        return VersionResponse(
            id=v.id,
            template_id=v.template_id,
            version=v.version,
            config=v.config,
            changelog=v.changelog,
            is_active=v.is_active,
            created_by=v.created_by,
            created_at=datetime.now(UTC),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ API: Failed to get active version - {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/{template_id}/versions/compare",
    response_model=VersionComparisonResult,
    summary="Compare Workflow Versions",
    description="Compare two workflow versions based on metrics"
)
async def compare_versions(
    template_id: str = Path(..., description="Workflow template ID"),
    v1: str = Query(..., description="First version to compare"),
    v2: str = Query(..., description="Second version to compare")
):
    """
    Compare two workflow versions.

    Compares versions based on:
    - Execution time (from A/B test results)
    - Token usage (from A/B test results)
    - Success rate (from A/B test results)

    - **template_id**: ID of the workflow template
    - **v1**: First version string
    - **v2**: Second version string

    **Returns**: Comparison result with recommendation

    **Raises**:
    - 404: One or both versions not found
    """
    try:
        result = version_service.compare_versions(template_id, v1, v2)
        if not result:
            logger.warning(f"⚠️ API: Cannot compare - versions not found for template {template_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Cannot compare versions {v1} and {v2} for template {template_id}"
            )

        logger.info(f"✅ API: Compared versions {v1} vs {v2} for template {template_id}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ API: Failed to compare versions - {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ===========================================================================
# Dynamic Routes (version-specific)
# ===========================================================================

@router.get(
    "/{template_id}/versions/{version}",
    response_model=VersionResponse,
    summary="Get Workflow Version",
    description="Get details of a specific workflow version"
)
async def get_version(
    template_id: str = Path(..., description="Workflow template ID"),
    version: str = Path(..., description="Version string (e.g., 'v1.0')")
):
    """
    Get details of a specific workflow version.

    - **template_id**: ID of the workflow template
    - **version**: Version string to retrieve

    **Returns**: Version information

    **Raises**:
    - 404: Version not found
    """
    try:
        v = version_service.get_version(template_id, version)
        if not v:
            logger.warning(f"⚠️ API: Version {version} not found for template {template_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Version {version} not found for template {template_id}"
            )

        logger.info(f"✅ API: Retrieved version {version} for template {template_id}")
        return VersionResponse(
            id=v.id,
            template_id=v.template_id,
            version=v.version,
            config=v.config,
            changelog=v.changelog,
            is_active=v.is_active,
            created_by=v.created_by,
            created_at=datetime.now(UTC),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ API: Failed to get version - {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put(
    "/{template_id}/versions/{version}",
    response_model=VersionResponse,
    summary="Update Workflow Version",
    description="Update an existing workflow version"
)
async def update_version(
    template_id: str = Path(..., description="Workflow template ID"),
    version: str = Path(..., description="Version string to update"),
    update: VersionUpdate | None = None
):
    """
    Update an existing workflow version.

    - **template_id**: ID of the workflow template
    - **version**: Version string to update
    - **config**: New configuration (optional)
    - **changelog**: New changelog (optional)
    - **is_active**: Active status (optional)

    **Returns**: Updated version information

    **Raises**:
    - 404: Version not found
    """
    try:
        if update is None:
            raise HTTPException(status_code=400, detail="Version update data is required")
        v = version_service.update_version(template_id, version, update)
        if not v:
            logger.warning(f"⚠️ API: Version {version} not found for template {template_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Version {version} not found for template {template_id}"
            )

        logger.info(f"✅ API: Updated version {version} for template {template_id}")
        return VersionResponse(
            id=v.id,
            template_id=v.template_id,
            version=v.version,
            config=v.config,
            changelog=v.changelog,
            is_active=v.is_active,
            created_by=v.created_by,
            created_at=datetime.now(UTC),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ API: Failed to update version - {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete(
    "/{template_id}/versions/{version}",
    status_code=204,
    summary="Delete Workflow Version",
    description="Delete a workflow version"
)
async def delete_version(
    template_id: str = Path(..., description="Workflow template ID"),
    version: str = Path(..., description="Version string to delete")
):
    """
    Delete a workflow version.

    - **template_id**: ID of the workflow template
    - **version**: Version string to delete

    **Raises**:
    - 404: Version not found
    """
    try:
        deleted = version_service.delete_version(template_id, version)
        if not deleted:
            logger.warning(f"⚠️ API: Version {version} not found for template {template_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Version {version} not found for template {template_id}"
            )

        logger.info(f"✅ API: Deleted version {version} for template {template_id}")
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ API: Failed to delete version - {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/{template_id}/versions/{version}/activate",
    response_model=VersionResponse,
    summary="Activate Workflow Version",
    description="Activate a workflow version (deactivates all others)"
)
async def activate_version(
    template_id: str = Path(..., description="Workflow template ID"),
    version: str = Path(..., description="Version string to activate")
):
    """
    Activate a workflow version.

    This deactivates all other versions for the template.

    - **template_id**: ID of the workflow template
    - **version**: Version string to activate

    **Returns**: Activated version information

    **Raises**:
    - 404: Version not found
    """
    try:
        success = version_service.activate_version(template_id, version)
        if not success:
            logger.warning(f"⚠️ API: Version {version} not found for template {template_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Version {version} not found for template {template_id}"
            )

        v = version_service.get_version(template_id, version)
        assert v is not None  # confirmed via activate_version returning True
        logger.info(f"✅ API: Activated version {version} for template {template_id}")
        return VersionResponse(
            id=v.id,
            template_id=v.template_id,
            version=v.version,
            config=v.config,
            changelog=v.changelog,
            is_active=v.is_active,
            created_by=v.created_by,
            created_at=datetime.now(UTC),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ API: Failed to activate version - {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/{template_id}/versions/{version}/deactivate",
    response_model=VersionResponse,
    summary="Deactivate Workflow Version",
    description="Deactivate a workflow version"
)
async def deactivate_version(
    template_id: str = Path(..., description="Workflow template ID"),
    version: str = Path(..., description="Version string to deactivate")
):
    """
    Deactivate a workflow version.

    - **template_id**: ID of the workflow template
    - **version**: Version string to deactivate

    **Returns**: Deactivated version information

    **Raises**:
    - 404: Version not found
    """
    try:
        success = version_service.deactivate_version(template_id, version)
        if not success:
            logger.warning(f"⚠️ API: Version {version} not found for template {template_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Version {version} not found for template {template_id}"
            )

        v = version_service.get_version(template_id, version)
        assert v is not None  # confirmed via deactivate_version returning True
        logger.info(f"✅ API: Deactivated version {version} for template {template_id}")
        return VersionResponse(
            id=v.id,
            template_id=v.template_id,
            version=v.version,
            config=v.config,
            changelog=v.changelog,
            is_active=v.is_active,
            created_by=v.created_by,
            created_at=datetime.now(UTC),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ API: Failed to deactivate version - {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
