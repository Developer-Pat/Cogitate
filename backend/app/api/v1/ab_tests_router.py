"""
A/B tests API router.

Provides HTTP endpoints for managing A/B tests:
- Create new A/B tests
- List A/B tests
- Get test details
- Update test configuration
- Delete tests
- Start/pause/stop tests
- Record test results
- Get test results and comparisons

URL Prefix: /api/v1/ab-tests
"""

import logging
from fastapi import APIRouter, HTTPException, Query, Path

from app.domain.workflows.schemas.version_config import (
    ABTestCreate,
    ABTestUpdate,
    ABTestResultRecord,
    ABTestResponse,
    ABTestListResponse,
    ABTestResultsSummary,
    ABTestComparison,
)
from app.domain.workflows.services.ab_test_service import ABTestService

from datetime import datetime, UTC
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ab-tests", tags=["A/B Testing"])
ab_test_service = ABTestService()


@router.post(
    "",
    response_model=ABTestResponse,
    status_code=201,
    summary="Create A/B Test",
    description="Create a new A/B test for comparing workflow versions"
)
async def create_ab_test(config: ABTestCreate):
    """
    Create a new A/B test.

    - **id**: Unique identifier for the test
    - **template_id**: Workflow template to test
    - **name**: Human-readable test name
    - **description**: Test description (optional)
    - **versions**: List of versions to compare (min 2)
    - **traffic_split**: Version -> percentage mapping (must sum to 100)
    - **metrics**: Metrics to track (optional)
    - **is_active**: Whether test starts active (default: True)

    **Returns**: Created test information

    **Raises**:
    - 400: Invalid traffic split (doesn't sum to 100)
    - 409: Test ID already exists
    """
    try:
        test = ab_test_service.create_test(config)
        logger.info(f"✅ API: Created A/B test {test.id} for template {test.template_id}")
        return ABTestResponse(
            id=test.id,
            template_id=test.template_id,
            name=test.name,
            description=test.description,
            versions=test.versions,
            traffic_split=test.traffic_split,
            metrics=test.metrics,
            is_active=test.is_active,
            started_at=datetime.now(UTC) if test.is_active else None,
            ended_at=None,
            created_at=datetime.now(UTC),
        )
    except ValueError as e:
        logger.error(f"❌ API: Invalid A/B test config - {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ API: Failed to create A/B test - {e}")
        if "UNIQUE constraint" in str(e):
            raise HTTPException(
                status_code=409,
                detail=f"A/B test {config.id} already exists"
            )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "",
    response_model=ABTestListResponse,
    summary="List A/B Tests",
    description="List all A/B tests"
)
async def list_ab_tests(
    active_only: bool = Query(False, description="Only return active tests")
):
    """
    List all A/B tests.

    - **active_only**: Filter to only active tests (default: False)

    **Returns**: List of A/B tests
    """
    try:
        tests = ab_test_service.list_tests(active_only=active_only)
        logger.info(f"✅ API: Listed {len(tests)} A/B tests")

        return ABTestListResponse(
            tests=[
                ABTestResponse(
                    id=t.id,
                    template_id=t.template_id,
                    name=t.name,
                    description=t.description,
                    versions=t.versions,
                    traffic_split=t.traffic_split,
                    metrics=t.metrics,
                    is_active=t.is_active,
                    started_at=datetime.now(UTC) if t.is_active else None,
                    ended_at=None,
                    created_at=datetime.now(UTC),
                )
                for t in tests
            ],
            total=len(tests)
        )
    except Exception as e:
        logger.error(f"❌ API: Failed to list A/B tests - {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/{test_id}",
    response_model=ABTestResponse,
    summary="Get A/B Test",
    description="Get details of a specific A/B test"
)
async def get_ab_test(test_id: str = Path(..., description="A/B test ID")):
    """
    Get details of a specific A/B test.

    - **test_id**: ID of the A/B test

    **Returns**: Test information

    **Raises**:
    - 404: Test not found
    """
    try:
        test = ab_test_service.get_test(test_id)
        if not test:
            logger.warning(f"⚠️ API: A/B test {test_id} not found")
            raise HTTPException(
                status_code=404,
                detail=f"A/B test {test_id} not found"
            )

        logger.info(f"✅ API: Retrieved A/B test {test_id}")
        return ABTestResponse(
            id=test.id,
            template_id=test.template_id,
            name=test.name,
            description=test.description,
            versions=test.versions,
            traffic_split=test.traffic_split,
            metrics=test.metrics,
            is_active=test.is_active,
            started_at=datetime.now(UTC) if test.is_active else None,
            ended_at=None,
            created_at=datetime.now(UTC),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ API: Failed to get A/B test - {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put(
    "/{test_id}",
    response_model=ABTestResponse,
    summary="Update A/B Test",
    description="Update an existing A/B test"
)
async def update_ab_test(
    test_id: str = Path(..., description="A/B test ID"),
    update: ABTestUpdate | None = None
):
    if update is None:
        raise HTTPException(status_code=400, detail="Update data is required")
    """
    Update an existing A/B test.

    - **test_id**: ID of the A/B test
    - **name**: New name (optional)
    - **description**: New description (optional)
    - **traffic_split**: New traffic split (optional)
    - **metrics**: New metrics to track (optional)
    - **is_active**: Active status (optional)

    **Returns**: Updated test information

    **Raises**:
    - 404: Test not found
    - 400: Invalid traffic split
    """
    try:
        test = ab_test_service.update_test(test_id, update)
        if not test:
            logger.warning(f"⚠️ API: A/B test {test_id} not found")
            raise HTTPException(
                status_code=404,
                detail=f"A/B test {test_id} not found"
            )

        logger.info(f"✅ API: Updated A/B test {test_id}")
        return ABTestResponse(
            id=test.id,
            template_id=test.template_id,
            name=test.name,
            description=test.description,
            versions=test.versions,
            traffic_split=test.traffic_split,
            metrics=test.metrics,
            is_active=test.is_active,
            started_at=datetime.now(UTC) if test.is_active else None,
            ended_at=None,
            created_at=datetime.now(UTC),
        )
    except ValueError as e:
        logger.error(f"❌ API: Invalid A/B test update - {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ API: Failed to update A/B test - {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete(
    "/{test_id}",
    status_code=204,
    summary="Delete A/B Test",
    description="Delete an A/B test"
)
async def delete_ab_test(test_id: str = Path(..., description="A/B test ID")):
    """
    Delete an A/B test.

    - **test_id**: ID of the A/B test

    **Raises**:
    - 404: Test not found
    """
    try:
        deleted = ab_test_service.delete_test(test_id)
        if not deleted:
            logger.warning(f"⚠️ API: A/B test {test_id} not found")
            raise HTTPException(
                status_code=404,
                detail=f"A/B test {test_id} not found"
            )

        logger.info(f"✅ API: Deleted A/B test {test_id}")
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ API: Failed to delete A/B test - {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/{test_id}/start",
    response_model=ABTestResponse,
    summary="Start A/B Test",
    description="Start an A/B test"
)
async def start_ab_test(test_id: str = Path(..., description="A/B test ID")):
    """
    Start an A/B test.

    - **test_id**: ID of the A/B test

    **Returns**: Updated test information

    **Raises**:
    - 404: Test not found
    """
    try:
        success = ab_test_service.start_test(test_id)
        if not success:
            logger.warning(f"⚠️ API: A/B test {test_id} not found")
            raise HTTPException(
                status_code=404,
                detail=f"A/B test {test_id} not found"
            )

        test = ab_test_service.get_test(test_id)
        if not test:
            logger.warning(f"⚠️ API: A/B test {test_id} not found after start")
            raise HTTPException(status_code=404, detail=f"A/B test {test_id} not found")
        logger.info(f"✅ API: Started A/B test {test_id}")
        return ABTestResponse(
            id=test.id,
            template_id=test.template_id,
            name=test.name,
            description=test.description,
            versions=test.versions,
            traffic_split=test.traffic_split,
            metrics=test.metrics,
            is_active=test.is_active,
            started_at=datetime.now(UTC),
            ended_at=None,
            created_at=datetime.now(UTC),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ API: Failed to start A/B test - {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/{test_id}/pause",
    response_model=ABTestResponse,
    summary="Pause A/B Test",
    description="Pause an A/B test (keeps data, stops new assignments)"
)
async def pause_ab_test(test_id: str = Path(..., description="A/B test ID")):
    """
    Pause an A/B test.

    The test retains all data but stops accepting new version assignments.

    - **test_id**: ID of the A/B test

    **Returns**: Updated test information

    **Raises**:
    - 404: Test not found
    """
    try:
        success = ab_test_service.pause_test(test_id)
        if not success:
            logger.warning(f"⚠️ API: A/B test {test_id} not found or already ended")
            raise HTTPException(
                status_code=404,
                detail=f"A/B test {test_id} not found or already ended"
            )

        test = ab_test_service.get_test(test_id)
        if not test:
            logger.warning(f"⚠️ API: A/B test {test_id} not found after pause")
            raise HTTPException(status_code=404, detail=f"A/B test {test_id} not found")
        logger.info(f"✅ API: Paused A/B test {test_id}")
        return ABTestResponse(
            id=test.id,
            template_id=test.template_id,
            name=test.name,
            description=test.description,
            versions=test.versions,
            traffic_split=test.traffic_split,
            metrics=test.metrics,
            is_active=test.is_active,
            started_at=test.started_at if hasattr(test, 'started_at') else None,
            ended_at=None,
            created_at=datetime.now(UTC),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ API: Failed to pause A/B test - {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/{test_id}/stop",
    response_model=ABTestResponse,
    summary="Stop A/B Test",
    description="Stop an A/B test (final, marks as ended)"
)
async def stop_ab_test(test_id: str = Path(..., description="A/B test ID")):
    """
    Stop an A/B test.

    This is final - the test is marked as ended.

    - **test_id**: ID of the A/B test

    **Returns**: Updated test information

    **Raises**:
    - 404: Test not found
    """
    try:
        success = ab_test_service.stop_test(test_id)
        if not success:
            logger.warning(f"⚠️ API: A/B test {test_id} not found")
            raise HTTPException(
                status_code=404,
                detail=f"A/B test {test_id} not found"
            )

        test = ab_test_service.get_test(test_id)
        if not test:
            logger.warning(f"⚠️ API: A/B test {test_id} not found after stop")
            raise HTTPException(status_code=404, detail=f"A/B test {test_id} not found")
        logger.info(f"✅ API: Stopped A/B test {test_id}")
        return ABTestResponse(
            id=test.id,
            template_id=test.template_id,
            name=test.name,
            description=test.description,
            versions=test.versions,
            traffic_split=test.traffic_split,
            metrics=test.metrics,
            is_active=test.is_active,
            started_at=datetime.now(UTC) if test.is_active else None,
            ended_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ API: Failed to stop A/B test - {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/{test_id}/record",
    status_code=201,
    summary="Record A/B Test Result",
    description="Record an execution result for an A/B test"
)
async def record_ab_test_result(
    test_id: str = Path(..., description="A/B test ID"),
    result: ABTestResultRecord | None = None
):
    """
    Record an A/B test execution result.

    - **test_id**: ID of the A/B test
    - **version**: Version that was executed
    - **execution_id**: ID of the workflow execution
    - **execution_time_ms**: Execution time in milliseconds (optional)
    - **tokens_used**: Number of tokens consumed (optional)
    - **quality_score**: Quality metric 0.0-1.0 (optional)
    - **success**: Whether execution succeeded (optional)
    - **error_message**: Error message if failed (optional)

    **Raises**:
    - 404: Test not found
    """
    if result is None:
        raise HTTPException(status_code=400, detail="Result data is required")
    try:
        recorded = ab_test_service.record_result(test_id, result)
        logger.info(f"✅ API: Recorded result for A/B test {test_id}, version {result.version}")
        return {
            "status": "recorded",
            "ab_test_id": recorded.ab_test_id,
            "version": recorded.version,
            "execution_id": recorded.execution_id,
        }
    except ValueError as e:
        logger.error(f"❌ API: A/B test not found - {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ API: Failed to record result - {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/{test_id}/results",
    response_model=ABTestResultsSummary,
    summary="Get A/B Test Results",
    description="Get aggregated results for an A/B test"
)
async def get_ab_test_results(test_id: str = Path(..., description="A/B test ID")):
    """
    Get aggregated results for an A/B test.

    Returns:
    - Per-version metrics (avg execution time, tokens, success rate)
    - Total executions
    - Recommended winner

    - **test_id**: ID of the A/B test

    **Raises**:
    - 404: Test not found
    """
    try:
        results = ab_test_service.get_results(test_id)
        logger.info(f"✅ API: Retrieved results for A/B test {test_id}")
        return results
    except ValueError as e:
        logger.error(f"❌ API: A/B test not found - {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ API: Failed to get results - {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/{test_id}/results/raw",
    summary="Get Raw A/B Test Results",
    description="Get raw (non-aggregated) results for an A/B test"
)
async def get_ab_test_results_raw(
    test_id: str = Path(..., description="A/B test ID"),
    limit: int = Query(100, description="Maximum results to return")
):
    """
    Get raw (non-aggregated) results for an A/B test.

    - **test_id**: ID of the A/B test
    - **limit**: Maximum number of results (default: 100)

    **Returns**: List of individual results
    """
    try:
        results = ab_test_service.get_raw_results(test_id, limit)
        logger.info(f"✅ API: Retrieved {len(results)} raw results for A/B test {test_id}")
        return {
            "test_id": test_id,
            "count": len(results),
            "results": [
                {
                    "ab_test_id": r.ab_test_id,
                    "template_id": r.template_id,
                    "version": r.version,
                    "execution_id": r.execution_id,
                    "execution_time_ms": r.execution_time_ms,
                    "tokens_used": r.tokens_used,
                    "quality_score": r.quality_score,
                    "success": r.success,
                    "error_message": r.error_message,
                }
                for r in results
            ]
        }
    except Exception as e:
        logger.error(f"❌ API: Failed to get raw results - {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/{test_id}/compare",
    response_model=ABTestComparison,
    summary="Compare A/B Test Versions",
    description="Compare all versions in an A/B test"
)
async def compare_ab_test_versions(test_id: str = Path(..., description="A/B test ID")):
    """
    Compare all versions in an A/B test.

    Provides:
    - Per-version metrics comparison
    - Improvement percentages
    - Winner recommendation

    - **test_id**: ID of the A/B test

    **Raises**:
    - 404: Test not found
    - 400: No data available for comparison
    """
    try:
        comparison = ab_test_service.compare_versions(test_id)
        if not comparison:
            logger.warning(f"⚠️ API: No data available for A/B test {test_id} comparison")
            raise HTTPException(
                status_code=400,
                detail=f"No data available for A/B test {test_id} comparison"
            )

        logger.info(f"✅ API: Compared versions for A/B test {test_id}")
        return comparison
    except ValueError as e:
        logger.error(f"❌ API: A/B test not found - {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ API: Failed to compare versions - {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/{test_id}/assign",
    summary="Assign Version",
    description="Assign a version based on traffic split (for workflow execution)"
)
async def assign_ab_test_version(test_id: str = Path(..., description="A/B test ID")):
    """
    Assign a version based on traffic split configuration.

    Used during workflow execution to determine which version to run.

    - **test_id**: ID of the A/B test

    **Returns**: Assigned version

    **Raises**:
    - 404: Test not found
    - 400: Test is not active
    """
    try:
        version = ab_test_service.assign_version(test_id)
        if not version:
            logger.warning(f"⚠️ API: Cannot assign version for A/B test {test_id}")
            raise HTTPException(
                status_code=400,
                detail=f"Cannot assign version for A/B test {test_id} (not found or inactive)"
            )

        logger.info(f"✅ API: Assigned version {version} for A/B test {test_id}")
        return {
            "test_id": test_id,
            "assigned_version": version
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ API: Failed to assign version - {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
