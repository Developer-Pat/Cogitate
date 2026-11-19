"""
Usage tracking API endpoints.

Provides usage statistics, trends, and cost breakdowns.
"""

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.domain.providers.usage_tracker import UsagePeriod, UsageTracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/providers/usage", tags=["provider-usage"])


class UsageSummaryResponse(BaseModel):
    """Schema for usage summary response."""
    period: str
    total_tokens: int
    total_cost_usd: float
    total_requests: int
    prompt_tokens: int
    completion_tokens: int
    success_count: int
    error_count: int
    avg_response_time_ms: Optional[float]
    period_start: Optional[str]
    period_end: Optional[str]


class UsageByProviderResponse(BaseModel):
    """Schema for usage by provider response."""
    by_provider: Dict[str, UsageSummaryResponse]


class ModelUsageResponse(BaseModel):
    """Schema for model usage response."""
    model: str
    total_tokens: int
    total_cost_usd: float
    total_requests: int
    prompt_tokens: int
    completion_tokens: int


class UsageTrendResponse(BaseModel):
    """Schema for usage trend response."""
    date: str
    total_tokens: int
    total_cost_usd: float
    total_requests: int


class CostBreakdownResponse(BaseModel):
    """Schema for cost breakdown response."""
    period: str
    by_provider: Dict[str, float]
    total_cost_usd: float


@router.get("", response_model=UsageSummaryResponse)
async def get_usage_summary(
    period: str = Query("monthly", description="Usage period (daily, weekly, monthly, all_time)"),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get usage summary for a period.

    Args:
        period: Usage period (daily, weekly, monthly, all_time)
    """
    try:
        usage_period = UsagePeriod(period)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid period. Must be one of: daily, weekly, monthly, all_time",
        )

    tracker = UsageTracker()
    usage = await tracker.get_usage_summary(db, usage_period)

    return {
        "period": period,
        "total_tokens": usage.total_tokens,
        "total_cost_usd": round(usage.total_cost_usd, 4),
        "total_requests": usage.total_requests,
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "success_count": usage.success_count,
        "error_count": usage.error_count,
        "avg_response_time_ms": round(usage.avg_response_time_ms, 2) if usage.avg_response_time_ms else None,
        "period_start": usage.period_start.isoformat() if usage.period_start else None,
        "period_end": usage.period_end.isoformat() if usage.period_end else None,
    }


@router.get("/by-provider")
async def get_usage_by_provider(
    period: str = Query("monthly", description="Usage period"),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get usage breakdown by provider.

    Args:
        period: Usage period
    """
    try:
        usage_period = UsagePeriod(period)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid period. Must be one of: daily, weekly, monthly, all_time",
        )

    tracker = UsageTracker()
    usage_by_provider = await tracker.get_usage_by_provider(db, usage_period)

    return {
        "period": period,
        "by_provider": {
            provider: usage.to_dict()
            for provider, usage in usage_by_provider.items()
        },
    }


@router.get("/by-model", response_model=List[ModelUsageResponse])
async def get_usage_by_model(
    period: str = Query("monthly", description="Usage period"),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get usage breakdown by model.

    Args:
        period: Usage period
    """
    try:
        usage_period = UsagePeriod(period)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid period. Must be one of: daily, weekly, monthly, all_time",
        )

    tracker = UsageTracker()
    models = await tracker.get_usage_by_model(db, period=usage_period)

    return [model.to_dict() for model in models]


@router.get("/trend", response_model=List[UsageTrendResponse])
async def get_usage_trend(
    days: int = Query(30, ge=1, le=365, description="Number of days"),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get usage trend over time.

    Args:
        days: Number of days to include
    """
    tracker = UsageTracker()
    trends = await tracker.get_usage_trend(db, days)

    return [trend.to_dict() for trend in trends]


@router.get("/cost-breakdown", response_model=CostBreakdownResponse)
async def get_cost_breakdown(
    period: str = Query("monthly", description="Usage period"),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get cost breakdown by provider.

    Args:
        period: Usage period
    """
    try:
        usage_period = UsagePeriod(period)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid period. Must be one of: daily, weekly, monthly, all_time",
        )

    tracker = UsageTracker()
    breakdown = await tracker.get_cost_breakdown(db, usage_period)

    total_cost = sum(breakdown.values())

    return {
        "period": period,
        "by_provider": {k: round(v, 4) for k, v in breakdown.items()},
        "total_cost_usd": round(total_cost, 4),
    }


@router.post("/{provider_id}/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_usage(
    provider_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Reset usage logs for a provider.

    ⚠️ WARNING: This is a destructive operation.

    Args:
        provider_id: Provider ID
    """
    tracker = UsageTracker()
    await tracker.reset_usage(db, provider_id)

    # Always return 204 for safety (even if not implemented)
    logger.warning(f"Reset usage called for provider {provider_id} (no-op)")
