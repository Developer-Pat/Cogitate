"""
Provider Abstraction API endpoints.

Provides unified completion interface with fallback support.
"""

import logging
import time
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.domain.providers.completion_service import (
    provider_completion_service,
    CompletionRequest,
)
from app.domain.providers.rate_limiter import (
    rate_limiter,
    quota_manager,
    health_monitor,
)
from app.domain.providers.factory import provider_factory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/providers", tags=["provider-abstraction"])


class CompletionRequestSchema:
    """Pydantic-like schema for completion request."""
    def __init__(
        self,
        messages: List[Dict[str, str]],
        model: str,
        provider: str,
        temperature: Optional[float] = 0.7,
        max_tokens: Optional[int] = 2000,
        top_p: Optional[float] = 0.9,
        stream: bool = False,
        fallback_enabled: bool = True,
        **kwargs
    ):
        self.messages = messages
        self.model = model
        self.provider = provider
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.stream = stream
        self.fallback_enabled = fallback_enabled
        self.extra_params = kwargs


@router.post("/complete")
async def complete(
    request_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db_session),
):
    """
    Send completion request with automatic fallback.

    Request body:
    - messages: List of message dictionaries
    - model: Model name
    - provider: Primary provider
    - temperature: Sampling temperature (optional)
    - max_tokens: Maximum tokens (optional)
    - top_p: Nucleus sampling (optional)
    - stream: Whether to stream (optional)
    - fallback_enabled: Enable fallback chain (optional, default True)

    Returns:
        Completion response with content and usage statistics
    """
    try:
        # Parse request
        messages = request_data.get("messages", [])
        model = request_data.get("model")
        # NO default service. This used to read `request_data.get("provider", "ollama")` — a service
        # NAME written in code, and one aimed at a local engine that need not be running (the
        # service-capability arc's phase-8 audit). The caller NAMES the service here; that is this
        # endpoint's contract (its own schema declares `provider: str`, and the external agent it
        # exists for always names one), so an omission is a bad request, not a licence to invent a
        # provider — and the fallback chain below is built from the caller's name as an `override`.
        provider = request_data.get("provider")
        temperature = request_data.get("temperature", 0.7)
        max_tokens = request_data.get("max_tokens", 2000)
        top_p = request_data.get("top_p", 0.9)
        stream = request_data.get("stream", False)
        fallback_enabled = request_data.get("fallback_enabled", True)

        if not messages or not model or not provider:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="messages, model and provider are required",
            )

        # Check rate limit
        if not rate_limiter.can_proceed(provider):
            wait_time = rate_limiter.get_wait_time(provider)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {wait_time:.1f}s",
            )

        # Check quota
        quota_status = await quota_manager.check_quota(db, provider)
        if not quota_status["can_proceed"]:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Quota exceeded: {', '.join(quota_status['reasons'])}",
            )

        # Build the fallback chain — the RESOLUTION's, never a literal (R3). The caller NAMED the
        # primary (`provider`/`model`), which is the ladder's override rung; what to try after it is
        # CONFIGURATION (the capability's chain). A literal list here also published a "fell back"
        # warning to the user BEFORE anything had been attempted — a false alarm on every request.
        fallback_chain = None
        # THE ADDRESSES the chain will need — resolved HERE, where the candidates are (2026-10-12,
        # stage 2): the service's per-name loop holds no session and must not carry a copy.
        endpoints: dict = {}
        if fallback_enabled:
            from app.domain.providers.capabilities import CHAT_CAPABILITY_KEY, resolve

            resolved = await resolve(db, CHAT_CAPABILITY_KEY, override=f"{provider}/{model}")
            fallback_chain = [c.provider for c in resolved.backups if c.provider] or None
            for candidate in resolved.candidates:
                if candidate.provider and candidate.endpoint:
                    endpoints.setdefault(candidate.provider, candidate.endpoint)

        # Record rate limit request
        rate_limiter.record_request(provider)

        # Create completion request
        completion_request = CompletionRequest(
            messages=messages,
            model=model,
            provider=provider,
            endpoint=endpoints.get(provider),
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            stream=stream,
        )

        # Execute completion
        response = await provider_completion_service.complete(
            completion_request,
            fallback_chain=fallback_chain,
            max_retries=2,
            endpoints=endpoints,
        )

        # Record health status
        if response.success:
            health_monitor.record_success(provider)
        else:
            health_monitor.record_failure(provider)

        return response.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Completion error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Completion failed: {str(e)}",
        )


@router.get("/health")
async def get_provider_health():
    """
    Get health status for all providers.

    Returns health metrics for each configured provider.
    """
    providers = list(provider_factory.SUPPORTED_PROVIDERS.keys())

    health_status = {}
    for provider in providers:
        status = health_monitor.get_status(provider)
        rate_limit_status = {
            "can_proceed": rate_limiter.can_proceed(provider),
            "wait_time": rate_limiter.get_wait_time(provider),
        }
        health_status[provider] = {
            **status,
            "rate_limit": rate_limit_status,
        }

    return {
        "providers": health_status,
        "timestamp": time.time(),
    }


@router.get("/quota")
async def get_quota_status(
    provider: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get quota status for providers.

    Args:
        provider: Provider name (optional, returns all if not specified)
    """
    if provider:
        status = await quota_manager.check_quota(db, provider)
        return {
            "provider": provider,
            **status,
        }
    else:
        # Get status for all providers
        providers = list(provider_factory.SUPPORTED_PROVIDERS.keys())
        statuses = {}
        for prov in providers:
            statuses[prov] = await quota_manager.check_quota(db, prov)

        return {
            "providers": statuses,
        }


@router.get("/usage")
async def get_usage_summary(
    provider: Optional[str] = None,
    days: int = 30,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get usage summary.

    Args:
        provider: Provider name (optional)
        days: Number of days to summarize (default: 30)
    """
    summary = await quota_manager.get_usage_summary(db, provider, days)
    return {
        "period_days": days,
        **summary,
    }


@router.post("/rate-limit/reset")
async def reset_rate_limit(provider: Optional[str] = None):
    """
    Reset rate limiter.

    Args:
        provider: Provider name (optional, resets all if not specified)
    """
    rate_limiter.reset(provider)
    return {
        "status": "success",
        "message": f"Rate limiter reset for {provider or 'all providers'}",
    }


@router.post("/health/reset")
async def reset_health(provider: Optional[str] = None):
    """
    Reset health monitor.

    Args:
        provider: Provider name (optional, resets all if not specified)
    """
    health_monitor.reset(provider)
    return {
        "status": "success",
        "message": f"Health monitor reset for {provider or 'all providers'}",
    }
