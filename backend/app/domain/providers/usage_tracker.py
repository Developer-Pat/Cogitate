"""
Usage tracking service.

Business logic for usage aggregation and analytics.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, UTC
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.infrastructure.database.models import UsageLog

logger = logging.getLogger(__name__)


class UsagePeriod(str, Enum):
    """Usage period types."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ALL_TIME = "all_time"


class UsageStats:
    """Usage statistics data class."""

    def __init__(
        self,
        total_tokens: int = 0,
        total_cost_usd: float = 0.0,
        total_requests: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        success_count: int = 0,
        error_count: int = 0,
        avg_response_time_ms: Optional[float] = None,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ):
        self.total_tokens = total_tokens
        self.total_cost_usd = total_cost_usd
        self.total_requests = total_requests
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.success_count = success_count
        self.error_count = error_count
        self.avg_response_time_ms = avg_response_time_ms
        self.period_start = period_start
        self.period_end = period_end

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "total_requests": self.total_requests,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "avg_response_time_ms": round(self.avg_response_time_ms, 2) if self.avg_response_time_ms else None,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
        }


class ModelUsage:
    """Model-specific usage data class."""

    def __init__(
        self,
        model: str,
        total_tokens: int = 0,
        total_cost_usd: float = 0.0,
        total_requests: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ):
        self.model = model
        self.total_tokens = total_tokens
        self.total_cost_usd = total_cost_usd
        self.total_requests = total_requests
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model": self.model,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "total_requests": self.total_requests,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
        }


class UsageTrend:
    """Usage trend data point."""

    def __init__(
        self,
        date: datetime,
        total_tokens: int = 0,
        total_cost_usd: float = 0.0,
        total_requests: int = 0,
    ):
        self.date = date
        self.total_tokens = total_tokens
        self.total_cost_usd = total_cost_usd
        self.total_requests = total_requests

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "date": self.date.isoformat(),
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "total_requests": self.total_requests,
        }


def _normalize_model_display(model: str) -> str:
    """Normalize a usage model string for display.

    Old chat path stored '{provider_id}/{provider}/{model}' (e.g.
    '3/deepseek/deepseek-v4-flash'); strip the leading numeric segment
    so the UI shows a clean '{provider}/{model}'.
    """
    if not model:
        return model
    parts = model.split("/")
    if len(parts) >= 3 and parts[0].isdigit():
        return "/".join(parts[1:])
    return model


class UsageTracker:
    """
    Service for usage tracking and aggregation.

    Provides usage statistics, trends, and cost breakdowns.
    """

    async def get_usage_summary(
        self,
        db: AsyncSession,
        period: UsagePeriod = UsagePeriod.MONTHLY,
        provider_id: Optional[int] = None,
    ) -> UsageStats:
        """
        Get usage summary for a period.

        Args:
            db: Database session
            period: Usage period (daily, weekly, monthly, all_time)
            provider_id: Optional provider ID filter

        Returns:
            UsageStats object
        """
        # Calculate period start
        now = datetime.now(UTC)
        period_start = self._get_period_start(period, now)

        # Build query filters
        filters = [UsageLog.created_at >= period_start] if period_start else []
        if provider_id:
            # Note: UsageLog doesn't have provider_id directly, it has provider name
            # We'll need to join with Provider or filter by provider name
            pass

        # Query usage logs
        from sqlalchemy import case

        success_case = case((UsageLog.success, 1), else_=0)
        error_case = case((~UsageLog.success, 1), else_=0)

        query = select(
            func.sum(UsageLog.total_tokens).label("total_tokens"),
            func.sum(UsageLog.cost_usd).label("total_cost_usd"),
            func.count(UsageLog.id).label("total_requests"),
            func.sum(UsageLog.prompt_tokens).label("prompt_tokens"),
            func.sum(UsageLog.completion_tokens).label("completion_tokens"),
            func.sum(success_case).label("success_count"),
            func.sum(error_case).label("error_count"),
            func.avg(UsageLog.response_time_ms).label("avg_response_time_ms"),
        ).where(and_(*filters)) if filters else select(
            func.sum(UsageLog.total_tokens).label("total_tokens"),
            func.sum(UsageLog.cost_usd).label("total_cost_usd"),
            func.count(UsageLog.id).label("total_requests"),
            func.sum(UsageLog.prompt_tokens).label("prompt_tokens"),
            func.sum(UsageLog.completion_tokens).label("completion_tokens"),
            func.sum(success_case).label("success_count"),
            func.sum(error_case).label("error_count"),
            func.avg(UsageLog.response_time_ms).label("avg_response_time_ms"),
        )

        result = await db.execute(query)
        row = result.first()

        if not row or row.total_tokens is None:
            return UsageStats(
                period_start=period_start,
                period_end=now,
            )

        return UsageStats(
            total_tokens=row.total_tokens or 0,
            total_cost_usd=row.total_cost_usd or 0.0,
            total_requests=row.total_requests or 0,
            prompt_tokens=row.prompt_tokens or 0,
            completion_tokens=row.completion_tokens or 0,
            success_count=row.success_count or 0,
            error_count=row.error_count or 0,
            avg_response_time_ms=row.avg_response_time_ms,
            period_start=period_start,
            period_end=now,
        )

    async def get_usage_by_provider(
        self,
        db: AsyncSession,
        period: UsagePeriod = UsagePeriod.MONTHLY,
    ) -> Dict[str, UsageStats]:
        """
        Get usage breakdown by provider.

        Args:
            db: Database session
            period: Usage period

        Returns:
            Dictionary of provider name -> UsageStats
        """
        period_start = self._get_period_start(period, datetime.now(UTC))

        filters = [UsageLog.created_at >= period_start] if period_start else []

        query = select(
            UsageLog.provider,
            func.sum(UsageLog.total_tokens).label("total_tokens"),
            func.sum(UsageLog.cost_usd).label("total_cost_usd"),
            func.count(UsageLog.id).label("total_requests"),
            func.sum(UsageLog.prompt_tokens).label("prompt_tokens"),
            func.sum(UsageLog.completion_tokens).label("completion_tokens"),
        )

        if filters:
            query = query.where(and_(*filters))

        query = query.group_by(UsageLog.provider)

        result = await db.execute(query)
        rows = result.fetchall()

        usage_by_provider = {}
        for row in rows:
            usage_by_provider[row.provider] = UsageStats(
                total_tokens=row.total_tokens or 0,
                total_cost_usd=row.total_cost_usd or 0.0,
                total_requests=row.total_requests or 0,
                prompt_tokens=row.prompt_tokens or 0,
                completion_tokens=row.completion_tokens or 0,
            )

        return usage_by_provider

    async def get_usage_by_model(
        self,
        db: AsyncSession,
        provider_id: Optional[int] = None,
        period: UsagePeriod = UsagePeriod.MONTHLY,
    ) -> List[ModelUsage]:
        """
        Get usage breakdown by model.

        Args:
            db: Database session
            provider_id: Optional provider ID filter
            period: Usage period

        Returns:
            List of ModelUsage objects
        """
        period_start = self._get_period_start(period, datetime.now(UTC))

        filters = [UsageLog.created_at >= period_start] if period_start else []

        query = select(
            UsageLog.model,
            func.sum(UsageLog.total_tokens).label("total_tokens"),
            func.sum(UsageLog.cost_usd).label("total_cost_usd"),
            func.count(UsageLog.id).label("total_requests"),
            func.sum(UsageLog.prompt_tokens).label("prompt_tokens"),
            func.sum(UsageLog.completion_tokens).label("completion_tokens"),
        )

        if filters:
            query = query.where(and_(*filters))

        query = query.group_by(UsageLog.model).order_by(
            func.sum(UsageLog.total_tokens).desc()
        )

        result = await db.execute(query)
        rows = result.fetchall()

        return [
            ModelUsage(
                model=_normalize_model_display(row.model),
                total_tokens=row.total_tokens or 0,
                total_cost_usd=row.total_cost_usd or 0.0,
                total_requests=row.total_requests or 0,
                prompt_tokens=row.prompt_tokens or 0,
                completion_tokens=row.completion_tokens or 0,
            )
            for row in rows
        ]

    async def get_usage_trend(
        self,
        db: AsyncSession,
        days: int = 30,
        provider_id: Optional[int] = None,
    ) -> List[UsageTrend]:
        """
        Get usage trend over time.

        Args:
            db: Database session
            days: Number of days to include
            provider_id: Optional provider ID filter

        Returns:
            List of UsageTrend objects (one per day)
        """
        period_start = datetime.now(UTC) - timedelta(days=days)

        filters = [UsageLog.created_at >= period_start]

        # Group by date (SQLite specific)
        query = select(
            func.date(UsageLog.created_at).label("date"),
            func.sum(UsageLog.total_tokens).label("total_tokens"),
            func.sum(UsageLog.cost_usd).label("total_cost_usd"),
            func.count(UsageLog.id).label("total_requests"),
        ).where(and_(*filters)).group_by(
            func.date(UsageLog.created_at)
        ).order_by(
            func.date(UsageLog.created_at)
        )

        result = await db.execute(query)
        rows = result.fetchall()

        return [
            UsageTrend(
                date=datetime.strptime(row.date, "%Y-%m-%d"),
                total_tokens=row.total_tokens or 0,
                total_cost_usd=row.total_cost_usd or 0.0,
                total_requests=row.total_requests or 0,
            )
            for row in rows
        ]

    async def get_cost_breakdown(
        self,
        db: AsyncSession,
        period: UsagePeriod = UsagePeriod.MONTHLY,
    ) -> Dict[str, float]:
        """
        Get cost breakdown by provider.

        Args:
            db: Database session
            period: Usage period

        Returns:
            Dictionary of provider name -> cost in USD
        """
        period_start = self._get_period_start(period, datetime.now(UTC))

        filters = [UsageLog.created_at >= period_start] if period_start else []

        query = select(
            UsageLog.provider,
            func.sum(UsageLog.cost_usd).label("total_cost_usd"),
        )

        if filters:
            query = query.where(and_(*filters))

        query = query.group_by(UsageLog.provider)

        result = await db.execute(query)
        rows = result.fetchall()

        return {row.provider: row.total_cost_usd or 0.0 for row in rows}

    async def reset_usage(
        self,
        db: AsyncSession,
        provider_id: Optional[int] = None,
    ) -> int:
        """
        Reset usage logs (for testing).

        Args:
            db: Database session
            provider_id: Optional provider ID filter

        Returns:
            Number of records deleted
        """
        # Note: This is a destructive operation - use with caution
        # In production, you might want to archive instead of delete
        if provider_id:
            # Would need to join with Provider to filter by ID
            pass

        # For now, just return 0 - implement if needed
        logger.warning("reset_usage called but not implemented for safety")
        return 0

    def _get_period_start(
        self,
        period: UsagePeriod,
        now: datetime,
    ) -> Optional[datetime]:
        """Get the start datetime for a period."""
        if period == UsagePeriod.DAILY:
            return now - timedelta(days=1)
        elif period == UsagePeriod.WEEKLY:
            return now - timedelta(weeks=1)
        elif period == UsagePeriod.MONTHLY:
            return now - timedelta(days=30)
        elif period == UsagePeriod.ALL_TIME:
            return None
        else:
            return now - timedelta(days=30)  # Default to monthly
