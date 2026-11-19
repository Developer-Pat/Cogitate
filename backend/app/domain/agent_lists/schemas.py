"""
Agent List domain schemas.

Pydantic schemas for agent list request/response validation.
"""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class AgentListBase(BaseModel):
    """Base agent list schema with common fields."""

    name: str = Field(..., min_length=1, max_length=100, description="Agent list name")
    description: Optional[str] = Field(
        default=None, max_length=500, description="Agent list description"
    )
    user_key: str = Field(
        default="default",
        max_length=100,
        description="User key for multi-user support"
    )
    is_default: bool = Field(
        default=False,
        description="Whether this is the default list for the user"
    )


class AgentListCreate(AgentListBase):
    """Schema for creating a new agent list."""

    agent_ids: List[int] = Field(
        default_factory=list,
        description="Ordered list of agent IDs in this list"
    )


class AgentListUpdate(BaseModel):
    """Schema for updating an existing agent list."""

    name: Optional[str] = Field(
        default=None, min_length=1, max_length=100, description="Agent list name"
    )
    description: Optional[str] = Field(
        default=None, max_length=500, description="Agent list description"
    )
    agent_ids: Optional[List[int]] = Field(
        default=None, description="Ordered list of agent IDs"
    )
    is_default: Optional[bool] = Field(
        default=None, description="Whether this is the default list"
    )


class AgentListResponse(AgentListBase):
    """Schema for agent list response."""

    model_config = {"from_attributes": True}

    id: str
    agent_ids: List[int]
    agent_count: int
    created_at: datetime
    updated_at: datetime


class AgentListWithAgentsResponse(AgentListResponse):
    """Schema for agent list with full agent details."""

    agents: List[dict] = Field(
        default_factory=list,
        description="Full agent objects in this list"
    )


class AgentListListResponse(BaseModel):
    """Schema for listing agent lists."""

    agent_lists: List[AgentListResponse]
    total: int


class AgentInListResponse(BaseModel):
    """Schema for an agent within a list context."""

    id: int
    name: str
    description: Optional[str]
    provider: str
    model: str
    profile_image_url: Optional[str]
    is_active: bool


class AgentListAgentsResponse(BaseModel):
    """Schema for response with agents in a list."""

    agents: List[AgentInListResponse]
    total: int
