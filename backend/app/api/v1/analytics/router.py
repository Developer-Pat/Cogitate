"""
Analytics API endpoints.

Provides REST API for usage analytics, cost tracking, and performance metrics.
"""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.domain.analytics.services import AnalyticsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


def get_analytics_service(db: Annotated[AsyncSession, Depends(get_db)]) -> AnalyticsService:
    """Dependency to get analytics service."""
    return AnalyticsService(db)


@router.get("/usage")
async def get_usage_stats(
    period: Annotated[
        str,
        Query(description="Time period (e.g., 7d, 30d, 90d)")
    ] = "7d",
    service: Annotated[AnalyticsService, Depends(get_analytics_service)] = None,  # type: ignore[assignment]
):
    """
    Get usage statistics for a time period.

    Args:
        period: Time period (default: 7d)
        service: Analytics service (injected)

    Returns:
        Usage statistics including requests, tokens, costs, and breakdowns
    """
    return await service.get_usage_stats(period)


@router.get("/costs")
async def get_cost_breakdown(
    period: Annotated[
        str,
        Query(description="Time period (e.g., 7d, 30d, 90d)")
    ] = "30d",
    service: Annotated[AnalyticsService, Depends(get_analytics_service)] = None,  # type: ignore[assignment]
):
    """
    Get cost breakdown for a time period.

    Args:
        period: Time period (default: 30d)
        service: Analytics service (injected)

    Returns:
        Cost breakdown by model with projections
    """
    return await service.get_cost_breakdown(period)


@router.get("/performance")
async def get_performance_metrics(
    agent_id: Annotated[
        Optional[int],
        Query(description="Filter by agent ID (optional)")
    ] = None,
    period: Annotated[
        str,
        Query(description="Time period (e.g., 7d, 30d, 90d)")
    ] = "7d",
    service: Annotated[AnalyticsService, Depends(get_analytics_service)] = None,  # type: ignore[assignment]
):
    """
    Get performance metrics.

    Args:
        agent_id: Optional agent ID to filter by
        period: Time period (default: 7d)
        service: Analytics service (injected)

    Returns:
        Performance metrics including response times, token stats, and error rates
    """
    return await service.get_performance_metrics(agent_id, period)
