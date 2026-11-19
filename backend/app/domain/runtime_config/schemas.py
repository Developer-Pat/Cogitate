"""
Runtime configuration domain schemas.

Pydantic schemas for runtime configuration request/response validation.
"""

from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel, ConfigDict, Field

from app.services.cognitive_pipeline.output_budget import BUDGET_CEILING


class RuntimeConfigBase(BaseModel):
    """Base runtime config schema with common fields."""

    temperature: Optional[float] = Field(
        default=None, ge=0, le=2, description="Temperature override (0-2)"
    )
    max_tokens: Optional[int] = Field(
        default=None,
        ge=1,
        le=BUDGET_CEILING,
        description=(
            "Max tokens override (1 … the derived budget ceiling, "
            "output_budget.BUDGET_CEILING)"
        ),
    )
    top_p: Optional[float] = Field(
        default=None, ge=0, le=1, description="Top P override (0-1)"
    )
    system_prompt_override: Optional[str] = Field(
        default=None, max_length=5000, description="System prompt override"
    )
    model_override: Optional[str] = Field(
        default=None, description="Model override"
    )
    additional_params: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional parameters"
    )


class RuntimeConfigCreate(RuntimeConfigBase):
    """Schema for creating runtime config."""

    session_id: int = Field(..., description="Chat session ID")
    agent_id: int = Field(..., description="Agent ID")


class RuntimeConfigUpdate(RuntimeConfigBase):
    """Schema for updating runtime config."""

    pass


class RuntimeConfigResponse(RuntimeConfigBase):
    """Schema for runtime config response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    agent_id: int
    created_at: datetime
    updated_at: datetime


class RuntimeConfigApplyRequest(BaseModel):
    """Schema for applying runtime config to a chat request."""

    session_id: int = Field(..., description="Chat session ID")
    message: str = Field(..., description="User message")
    agent_id: int = Field(..., description="Agent ID")
