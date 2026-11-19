"""
Title service API endpoints.

Provides REST API for session title generation and metrics.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.domain.providers.capabilities import resolve
from app.domain.title.services import TITLE_CAPABILITY_KEY, get_title_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["title-service"])


class TitleGenerationRequest(BaseModel):
    """Request model for title generation."""
    assistant_message: str = Field(..., description="The assistant message to generate title from")
    model: str | None = Field(default=None, description="Optional model override (uses backend config if not provided)")
    user_enabled: bool = Field(default=True, description="Whether user has enabled auto-title in settings")


class TitleGenerationResponse(BaseModel):
    """Response model for title generation."""
    title: str
    success: bool = True
    model_used: str | None = None


@router.post("/generate-title", response_model=TitleGenerationResponse)
async def generate_session_title(
    request: TitleGenerationRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Generate a session title from an assistant message.

    Uses the dedicated TitleService with configured LLM (ollama/llama3.2 by default).
    This endpoint is designed for frontend-initiated title generation (e.g., Rename button).

    Args:
        request: TitleGenerationRequest with assistant_message and optional model override
        db: Database session for default provider configuration

    Returns:
        Generated title and metadata

    Raises:
        HTTPException: If title generation fails
    """
    try:
        title_service = get_title_service()

        # Prepare messages for title generation (using assistant message)
        title_messages = [
            {"role": "assistant", "content": request.assistant_message}
        ]

        # Generate title using dedicated TitleService
        # Pass database session for default provider configuration
        # If model is provided in request, temporarily override config
        generated_title = await title_service.generate_title(
            messages=title_messages,
            user_enabled=request.user_enabled,
            db=db,
            model_override=request.model
        )

        if generated_title:
            logger.info(f"Generated session title via API: '{generated_title}'")
            model_used = request.model or title_service.model
            return TitleGenerationResponse(
                title=generated_title,
                success=True,
                model_used=model_used
            )
        else:
            logger.warning("Title generation returned None via API")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Title generation returned empty result"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Title generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Title generation failed: {str(e)}"
        )


@router.get("/title/metrics")
async def get_title_metrics():
    """
    Get title generation metrics.

    Returns metrics including:
    - Total attempts
    - Success/failure counts
    - Success rate percentage
    - Average generation time
    - Last error details
    """
    try:
        title_service = get_title_service()
        metrics = title_service.get_metrics()
        config = title_service.get_config()

        return {
            "success": True,
            "metrics": metrics,
            "config": config,
        }
    except Exception as e:
        logger.error(f"Failed to get title metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/title-service/status")
async def get_title_service_status(db: AsyncSession = Depends(get_db_session)):
    """
    Get title service configuration and health status.

    Two different facts, and the payload says which is which:

    - ``resolved_*`` is the pair the SERVICE last loaded (null until it configures itself);
    - ``default_provider_ready`` / ``default_provider`` report the **`title` capability's
      resolution**, read live — the capability's own chain, or the global default row when it
      configures nothing of its own. That is the same answer the Capabilities page shows, so the two
      surfaces cannot disagree.

    The last two keep their historical KEYS (existing readers depend on them); what they describe is
    the capability, not a "default provider" of the title's own.

    Returns configuration, resolution, readiness issues and usage metrics.
    """
    try:
        title_service = get_title_service()
        config = title_service.get_config()
        metrics = title_service.get_metrics()

        # THE CAPABILITY'S ANSWER, read live (phase 6, G2-F5). These two fields used to describe the
        # GLOBAL DEFAULT ROW — a row the title only uses when its own capability resolves to nothing —
        # so this endpoint and the Capabilities page could report two different answers to one question.
        resolved = await resolve(db, TITLE_CAPABILITY_KEY)
        primary = resolved.primary
        issues: list[str] = []
        if primary is None:
            issues.append(
                f"the '{TITLE_CAPABILITY_KEY}' capability resolves to nothing "
                f"(reason={resolved.reason})"
            )
        elif primary.provider_id is None:
            issues.append(
                f"the '{TITLE_CAPABILITY_KEY}' capability resolves to '{primary.describe()}', "
                "which names no provider row"
            )

        return {
            "enabled": config["enabled"],
            "resolved_provider": title_service.provider,
            "resolved_model": title_service.model,
            "resolved_base_url": title_service.base_url,
            "reasoning_effort": getattr(title_service, "reasoning_effort", None),
            "config_loaded": title_service._config_is_fresh(),
            # NO fallback_config — the capability resolves ONLY via the
            # provider row or an explicit override (2026-09-03); a failed
            # resolution is a loud TITLE-GEN CONFIG FAILED log, never a
            # silent second-best provider.
            "default_provider_ready": primary is not None and primary.provider_id is not None,
            "default_provider": {
                "id": primary.provider_id,
                "name": primary.provider or primary.service_name,
                "type": primary.provider_type,
                "model": primary.model,
            } if primary is not None else None,
            "default_provider_issues": issues,
            "metrics": metrics,
        }
    except Exception as e:
        logger.error(f"Failed to get title service status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
