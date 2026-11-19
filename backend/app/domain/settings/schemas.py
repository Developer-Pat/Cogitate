"""
Settings domain schemas.

Pydantic schemas for user settings request/response validation.
"""

from datetime import datetime
from typing import Dict, Any

from pydantic import BaseModel, Field


class UserSettingsSchema(BaseModel):
    """Schema for user settings."""

    model_config = {"from_attributes": True}

    id: int
    user_key: str
    settings: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class UserSettingsRequest(BaseModel):
    """Schema for updating user settings."""

    settings: Dict[str, Any] = Field(..., description="Settings object to persist")


class UserSettingsResponse(BaseModel):
    """Schema for user settings response."""

    user_key: str
    settings: Dict[str, Any]
    updated_at: datetime
