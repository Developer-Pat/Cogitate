"""
Provider Rate Limiting and Quota Management.

Handles rate limiting, quotas, and usage tracking for providers.
"""

import logging
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, UTC
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.infrastructure.database.models import UsageLog

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    In-memory rate limiter using token bucket algorithm.

    Features:
    - Configurable requests per minute/hour
    - Per-provider rate limits
    - Automatic token refill
    """

    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
    ):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Max requests per minute
            requests_per_hour: Max requests per hour
        """
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour

        # Token buckets per provider
        self._minute_buckets: Dict[str, List[float]] = defaultdict(list)
        self._hour_buckets: Dict[str, List[float]] = defaultdict(list)

    def _clean_old_tokens(self, bucket: List[float], window_seconds: float) -> List[float]:
        """Remove tokens older than the time window."""
        current_time = time.time()
        cutoff = current_time - window_seconds
        return [t for t in bucket if t > cutoff]

    def can_proceed(self, provider: str) -> bool:
        """
        Check if request can proceed for provider.

        Args:
            provider: Provider name

        Returns:
            True if request is allowed
        """
        # Clean old tokens
        self._minute_buckets[provider] = self._clean_old_tokens(
            self._minute_buckets[provider], 60
        )
        self._hour_buckets[provider] = self._clean_old_tokens(
            self._hour_buckets[provider], 3600
        )

        # Check limits
        if len(self._minute_buckets[provider]) >= self.requests_per_minute:
            logger.warning(f"⚠️ Rate limit exceeded for {provider} (per minute)")
            return False

        if len(self._hour_buckets[provider]) >= self.requests_per_hour:
            logger.warning(f"⚠️ Rate limit exceeded for {provider} (per hour)")
            return False

        return True

    def record_request(self, provider: str):
        """
        Record a request for provider.

        Args:
            provider: Provider name
        """
        current_time = time.time()
        self._minute_buckets[provider].append(current_time)
        self._hour_buckets[provider].append(current_time)

    def get_wait_time(self, provider: str) -> float:
        """
        Get time to wait before next request is allowed.

        Args:
            provider: Provider name

        Returns:
            Wait time in seconds (0 if allowed now)
        """
        current_time = time.time()

        # Check minute limit
        self._minute_buckets[provider] = self._clean_old_tokens(
            self._minute_buckets[provider], 60
        )
        if len(self._minute_buckets[provider]) >= self.requests_per_minute:
            oldest = min(self._minute_buckets[provider])
            return max(0, 60 - (current_time - oldest))

        # Check hour limit
        self._hour_buckets[provider] = self._clean_old_tokens(
            self._hour_buckets[provider], 3600
        )
        if len(self._hour_buckets[provider]) >= self.requests_per_hour:
            oldest = min(self._hour_buckets[provider])
            return max(0, 3600 - (current_time - oldest))

        return 0.0

    def reset(self, provider: Optional[str] = None):
        """
        Reset rate limiter.

        Args:
            provider: Provider to reset (None for all)
        """
        if provider:
            self._minute_buckets[provider] = []
            self._hour_buckets[provider] = []
        else:
            self._minute_buckets.clear()
            self._hour_buckets.clear()


class QuotaManager:
    """
    Manages usage quotas for providers.

    Features:
    - Daily/monthly token quotas
    - Cost quotas
    - Quota tracking per provider
    """

    def __init__(
        self,
        daily_token_limit: Optional[int] = None,
        monthly_token_limit: Optional[int] = None,
        daily_cost_limit: Optional[float] = None,
        monthly_cost_limit: Optional[float] = None,
    ):
        """
        Initialize quota manager.

        Args:
            daily_token_limit: Daily token limit (None for unlimited)
            monthly_token_limit: Monthly token limit
            daily_cost_limit: Daily cost limit in USD
            monthly_cost_limit: Monthly cost limit in USD
        """
        self.daily_token_limit = daily_token_limit
        self.monthly_token_limit = monthly_token_limit
        self.daily_cost_limit = daily_cost_limit
        self.monthly_cost_limit = monthly_cost_limit

    async def check_quota(
        self,
        db: AsyncSession,
        provider: str,
    ) -> Dict[str, Any]:
        """
        Check quota status for provider.

        Args:
            db: Database session
            provider: Provider name

        Returns:
            Quota status dictionary
        """
        now = datetime.now(UTC)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Get usage for today
        daily_query = select(
            func.sum(UsageLog.total_tokens),
            func.sum(UsageLog.cost_usd),
        ).where(
            and_(
                UsageLog.provider == provider,
                UsageLog.created_at >= start_of_day,
            )
        )
        daily_result = await db.execute(daily_query)
        daily_tokens, daily_cost = daily_result.one()
        daily_tokens = daily_tokens or 0
        daily_cost = daily_cost or 0.0

        # Get usage for this month
        monthly_query = select(
            func.sum(UsageLog.total_tokens),
            func.sum(UsageLog.cost_usd),
        ).where(
            and_(
                UsageLog.provider == provider,
                UsageLog.created_at >= start_of_month,
            )
        )
        monthly_result = await db.execute(monthly_query)
        monthly_tokens, monthly_cost = monthly_result.one()
        monthly_tokens = monthly_tokens or 0
        monthly_cost = monthly_cost or 0.0

        # Check limits
        can_proceed = True
        reasons = []

        if self.daily_token_limit and daily_tokens >= self.daily_token_limit:
            can_proceed = False
            reasons.append("Daily token limit exceeded")

        if self.monthly_token_limit and monthly_tokens >= self.monthly_token_limit:
            can_proceed = False
            reasons.append("Monthly token limit exceeded")

        if self.daily_cost_limit and daily_cost >= self.daily_cost_limit:
            can_proceed = False
            reasons.append("Daily cost limit exceeded")

        if self.monthly_cost_limit and monthly_cost >= self.monthly_cost_limit:
            can_proceed = False
            reasons.append("Monthly cost limit exceeded")

        return {
            "can_proceed": can_proceed,
            "reasons": reasons,
            "usage": {
                "daily": {
                    "tokens": daily_tokens,
                    "cost_usd": daily_cost,
                    "token_limit": self.daily_token_limit,
                    "cost_limit": self.daily_cost_limit,
                },
                "monthly": {
                    "tokens": monthly_tokens,
                    "cost_usd": monthly_cost,
                    "token_limit": self.monthly_token_limit,
                    "cost_limit": self.monthly_cost_limit,
                },
            },
        }

    async def get_usage_summary(
        self,
        db: AsyncSession,
        provider: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get usage summary.

        Args:
            db: Database session
            provider: Provider name (None for all)
            days: Number of days to summarize

        Returns:
            Usage summary dictionary
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)

        query = select(
            UsageLog.provider,
            func.sum(UsageLog.total_tokens),
            func.sum(UsageLog.cost_usd),
            func.count(UsageLog.id),
        ).where(
            and_(
                UsageLog.created_at >= cutoff,
                UsageLog.success,
            )
        )

        if provider:
            query = query.where(UsageLog.provider == provider)

        query = query.group_by(UsageLog.provider)

        result = await db.execute(query)
        rows = result.all()

        summary = {
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "total_requests": 0,
            "providers": {},
        }

        for row in rows:
            provider_name, tokens, cost, count = row
            tokens = tokens or 0
            cost = cost or 0.0
            count = count or 0

            summary["total_tokens"] += tokens  # type: ignore[operator]
            summary["total_cost_usd"] += cost  # type: ignore[operator]
            summary["total_requests"] += count  # type: ignore[operator]

            summary["providers"][provider_name] = {  # type: ignore[index]
                "tokens": tokens,
                "cost_usd": cost,
                "requests": count,
            }

        return summary


class ProviderHealthMonitor:
    """
    Monitors provider health and availability.

    Features:
    - Tracks success/failure rates
    - Circuit breaker pattern
    - Automatic provider disabling on repeated failures
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
    ):
        """
        Initialize health monitor.

        Args:
            failure_threshold: Failures before marking unhealthy
            recovery_timeout: Seconds before retrying unhealthy provider
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        # Track failures per provider
        self._failure_counts: Dict[str, int] = defaultdict(int)
        self._last_failure_time: Dict[str, float] = {}
        self._unhealthy_providers: set = set()

    def record_success(self, provider: str):
        """
        Record successful request.

        Args:
            provider: Provider name
        """
        self._failure_counts[provider] = 0
        if provider in self._unhealthy_providers:
            self._unhealthy_providers.remove(provider)
            logger.info(f"✅ Provider {provider} marked healthy")

    def record_failure(self, provider: str):
        """
        Record failed request.

        Args:
            provider: Provider name
        """
        self._failure_counts[provider] += 1
        self._last_failure_time[provider] = time.time()

        if self._failure_counts[provider] >= self.failure_threshold:
            self._unhealthy_providers.add(provider)
            logger.warning(f"⚠️ Provider {provider} marked unhealthy")

    def is_healthy(self, provider: str) -> bool:
        """
        Check if provider is healthy.

        Args:
            provider: Provider name

        Returns:
            True if provider is healthy
        """
        if provider not in self._unhealthy_providers:
            return True

        # Check if recovery timeout has passed
        last_failure = self._last_failure_time.get(provider, 0)
        if time.time() - last_failure > self.recovery_timeout:
            # Allow retry
            logger.info(f"🔄 Allowing retry for unhealthy provider {provider}")
            return True

        return False

    def get_status(self, provider: str) -> Dict[str, Any]:
        """
        Get provider health status.

        Args:
            provider: Provider name

        Returns:
            Health status dictionary
        """
        return {
            "healthy": self.is_healthy(provider),
            "failure_count": self._failure_counts.get(provider, 0),
            "last_failure": self._last_failure_time.get(provider),
            "unhealthy": provider in self._unhealthy_providers,
        }

    def reset(self, provider: Optional[str] = None):
        """
        Reset health monitor.

        Args:
            provider: Provider to reset (None for all)
        """
        if provider:
            self._failure_counts[provider] = 0
            self._unhealthy_providers.discard(provider)
            self._last_failure_time.pop(provider, None)
        else:
            self._failure_counts.clear()
            self._last_failure_time.clear()
            self._unhealthy_providers.clear()


# Singleton instances
rate_limiter = RateLimiter()
quota_manager = QuotaManager()
health_monitor = ProviderHealthMonitor()
