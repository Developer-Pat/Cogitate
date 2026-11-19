"""
Analytics domain service.

Business logic for usage analytics, cost tracking, and performance metrics.
"""

import logging
from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.infrastructure.database.models import UsageLog, Agent

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Service for analytics business logic.

    Handles usage statistics, cost analysis, and performance metrics.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize analytics service.

        Args:
            db: Async database session
        """
        self.db = db

    async def get_usage_stats(self, period: str = "7d") -> Dict[str, Any]:
        """
        Get usage statistics for a time period.

        Args:
            period: Time period (e.g., "7d", "30d", "90d")

        Returns:
            Dictionary with usage statistics
        """
        # Parse period
        days = self._parse_period(period)
        start_date = datetime.now(UTC) - timedelta(days=days)

        # Total requests
        total_requests_query = (
            select(func.count(UsageLog.id))
            .where(UsageLog.created_at >= start_date)
        )
        total_requests = await self.db.scalar(total_requests_query) or 0

        # Total tokens
        total_tokens_query = (
            select(func.sum(UsageLog.total_tokens))
            .where(UsageLog.created_at >= start_date)
        )
        total_tokens = await self.db.scalar(total_tokens_query) or 0

        # Total cost
        total_cost_query = (
            select(func.sum(UsageLog.cost_usd))
            .where(UsageLog.created_at >= start_date)
        )
        total_cost = await self.db.scalar(total_cost_query) or 0.0

        # Unique sessions
        unique_sessions_query = (
            select(func.count(func.distinct(UsageLog.session_id)))
            .where(UsageLog.created_at >= start_date)
        )
        unique_sessions = await self.db.scalar(unique_sessions_query) or 0

        # Success rate
        total_query = select(func.count(UsageLog.id)).where(UsageLog.created_at >= start_date)
        success_query = (
            select(func.count(UsageLog.id))
            .where(and_(UsageLog.created_at >= start_date, UsageLog.success))
        )
        total_count = await self.db.scalar(total_query) or 0
        success_count = await self.db.scalar(success_query) or 0
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0.0

        # Average response time
        avg_response_time_query = (
            select(func.avg(UsageLog.response_time_ms))
            .where(and_(UsageLog.created_at >= start_date, UsageLog.response_time_ms.isnot(None)))
        )
        avg_response_time = await self.db.scalar(avg_response_time_query) or 0.0

        # Usage by agent
        agent_usage_query = (
            select(
                Agent.id,
                Agent.name,
                func.count(UsageLog.id).label('requests'),
                func.sum(UsageLog.total_tokens).label('tokens'),
                func.sum(UsageLog.cost_usd).label('cost')
            )
            .join(UsageLog, Agent.id == UsageLog.agent_id)
            .where(UsageLog.created_at >= start_date)
            .group_by(Agent.id, Agent.name)
            .order_by(func.count(UsageLog.id).desc())
        )
        agent_result = await self.db.execute(agent_usage_query)
        usage_by_agent = [
            {
                "agent_id": row.id,
                "agent_name": row.name,
                "requests": row.requests,
                "tokens": row.tokens or 0,
                "cost_usd": float(row.cost) if row.cost else 0.0
            }
            for row in agent_result.all()
        ]

        # Usage by provider
        provider_usage_query = (
            select(
                UsageLog.provider,
                func.count(UsageLog.id).label('requests'),
                func.sum(UsageLog.total_tokens).label('tokens'),
                func.sum(UsageLog.cost_usd).label('cost')
            )
            .where(UsageLog.created_at >= start_date)
            .group_by(UsageLog.provider)
            .order_by(func.count(UsageLog.id).desc())
        )
        provider_result = await self.db.execute(provider_usage_query)
        usage_by_provider = [
            {
                "provider": row.provider,
                "requests": row.requests,
                "tokens": row.tokens or 0,
                "cost_usd": float(row.cost) if row.cost else 0.0
            }
            for row in provider_result.all()
        ]

        # Daily usage (for charts)
        daily_usage_query = (
            select(
                func.date(UsageLog.created_at).label('date'),
                func.count(UsageLog.id).label('requests'),
                func.sum(UsageLog.total_tokens).label('tokens'),
                func.sum(UsageLog.cost_usd).label('cost')
            )
            .where(UsageLog.created_at >= start_date)
            .group_by(func.date(UsageLog.created_at))
            .order_by(func.date(UsageLog.created_at))
        )
        daily_result = await self.db.execute(daily_usage_query)
        daily_usage = [
            {
                "date": str(row.date),
                "requests": row.requests,
                "tokens": row.tokens or 0,
                "cost_usd": float(row.cost) if row.cost else 0.0
            }
            for row in daily_result.all()
        ]

        return {
            "period": period,
            "days": days,
            "summary": {
                "total_requests": total_requests,
                "total_tokens": total_tokens,
                "total_cost_usd": round(total_cost, 4),
                "unique_sessions": unique_sessions,
                "success_rate": round(success_rate, 2),
                "avg_response_time_ms": round(avg_response_time, 2)
            },
            "usage_by_agent": usage_by_agent,
            "usage_by_provider": usage_by_provider,
            "daily_usage": daily_usage
        }

    async def get_cost_breakdown(self, period: str = "30d") -> Dict[str, Any]:
        """
        Get cost breakdown for a time period.

        Args:
            period: Time period (e.g., "7d", "30d", "90d")

        Returns:
            Dictionary with cost breakdown
        """
        days = self._parse_period(period)
        start_date = datetime.now(UTC) - timedelta(days=days)

        # Total cost
        total_cost_query = (
            select(func.sum(UsageLog.cost_usd))
            .where(UsageLog.created_at >= start_date)
        )
        total_cost = await self.db.scalar(total_cost_query) or 0.0

        # Cost by model
        cost_by_model_query = (
            select(
                UsageLog.model,
                func.sum(UsageLog.cost_usd).label('cost'),
                func.sum(UsageLog.total_tokens).label('tokens'),
                func.count(UsageLog.id).label('requests')
            )
            .where(UsageLog.created_at >= start_date)
            .group_by(UsageLog.model)
            .order_by(func.sum(UsageLog.cost_usd).desc())
        )
        model_result = await self.db.execute(cost_by_model_query)
        cost_by_model = [
            {
                "model": row.model,
                "cost_usd": round(float(row.cost), 4) if row.cost else 0.0,
                "tokens": row.tokens or 0,
                "requests": row.requests,
                "avg_cost_per_1k_tokens": round((float(row.cost) / (row.tokens or 1)) * 1000, 4) if row.cost else 0.0
            }
            for row in model_result.all()
        ]

        # Projected monthly cost
        days_elapsed = min(days, (datetime.now(UTC) - start_date).days)
        if days_elapsed > 0:
            daily_avg = total_cost / days_elapsed
            projected_monthly = daily_avg * 30
        else:
            projected_monthly = 0.0

        return {
            "period": period,
            "days": days,
            "total_cost_usd": round(total_cost, 4),
            "projected_monthly_cost_usd": round(projected_monthly, 2),
            "cost_by_model": cost_by_model
        }

    async def get_performance_metrics(self, agent_id: Optional[int] = None, period: str = "7d") -> Dict[str, Any]:
        """
        Get performance metrics.

        Args:
            agent_id: Optional agent ID to filter by
            period: Time period

        Returns:
            Dictionary with performance metrics
        """
        days = self._parse_period(period)
        start_date = datetime.now(UTC) - timedelta(days=days)

        # Base query
        base_filters = [UsageLog.created_at >= start_date]
        if agent_id:
            base_filters.append(UsageLog.agent_id == agent_id)

        # Response time percentiles
        response_times_query = (
            select(UsageLog.response_time_ms)
            .where(and_(*base_filters, UsageLog.response_time_ms.isnot(None)))
            .order_by(UsageLog.response_time_ms)
        )
        response_times_result = await self.db.execute(response_times_query)
        response_times = [r[0] for r in response_times_result.all() if r[0] is not None]

        if response_times:
            p50_idx = int(len(response_times) * 0.5)
            p95_idx = int(len(response_times) * 0.95)
            p99_idx = int(len(response_times) * 0.99)
            p50 = response_times[p50_idx] if p50_idx < len(response_times) else 0
            p95 = response_times[p95_idx] if p95_idx < len(response_times) else 0
            p99 = response_times[p99_idx] if p99_idx < len(response_times) else 0
            min_time = min(response_times)
            max_time = max(response_times)
            avg_time = sum(response_times) / len(response_times)
        else:
            p50 = p95 = p99 = min_time = max_time = avg_time = 0

        # Token statistics
        tokens_query = (
            select(
                func.sum(UsageLog.prompt_tokens).label('prompt'),
                func.sum(UsageLog.completion_tokens).label('completion'),
                func.sum(UsageLog.total_tokens).label('total'),
                func.avg(UsageLog.total_tokens).label('avg')
            )
            .where(and_(*base_filters))
        )
        tokens_result = await self.db.execute(tokens_query)
        tokens_row = tokens_result.first()
        
        token_stats = {
            "total_prompt_tokens": tokens_row.prompt or 0,
            "total_completion_tokens": tokens_row.completion or 0,
            "total_tokens": tokens_row.total or 0,
            "avg_tokens_per_request": round(tokens_row.avg or 0, 2)
        } if tokens_row else {"total_prompt_tokens": 0, "total_completion_tokens": 0, "total_tokens": 0, "avg_tokens_per_request": 0}

        # Error rate
        total_query = select(func.count(UsageLog.id)).where(and_(*base_filters))
        error_query = (
            select(func.count(UsageLog.id))
            .where(and_(*base_filters, ~UsageLog.success))
        )
        total_count = await self.db.scalar(total_query) or 0
        error_count = await self.db.scalar(error_query) or 0
        error_rate = (error_count / total_count * 100) if total_count > 0 else 0.0

        return {
            "period": period,
            "agent_id": agent_id,
            "response_time": {
                "p50_ms": round(p50, 2),
                "p95_ms": round(p95, 2),
                "p99_ms": round(p99, 2),
                "min_ms": round(min_time, 2),
                "max_ms": round(max_time, 2),
                "avg_ms": round(avg_time, 2)
            },
            "token_stats": token_stats,
            "error_rate": round(error_rate, 2),
            "total_requests": total_count
        }

    def _parse_period(self, period: str) -> int:
        """Parse period string to days."""
        if period.endswith('d'):
            return int(period[:-1])
        elif period.endswith('w'):
            return int(period[:-1]) * 7
        elif period.endswith('m'):
            return int(period[:-1]) * 30
        else:
            # Default to 7 days
            try:
                return int(period)
            except ValueError:
                return 7
