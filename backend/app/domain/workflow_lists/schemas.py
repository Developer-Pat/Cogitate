"""
Workflow List domain schemas.

Pydantic schemas for workflow list request/response validation.
"""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class WorkflowListBase(BaseModel):
    """Base workflow list schema with common fields."""

    name: str = Field(..., min_length=1, max_length=100, description="Workflow list name")
    description: Optional[str] = Field(
        default=None, max_length=500, description="Workflow list description"
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
    tags: Optional[List[str]] = Field(
        default=None,
        description="Tags for categorization and filtering"
    )


class WorkflowListCreate(WorkflowListBase):
    """Schema for creating a new workflow list."""

    workflow_ids: List[str] = Field(
        default_factory=list,
        description="Ordered list of workflow template IDs in this list"
    )


class WorkflowListUpdate(BaseModel):
    """Schema for updating an existing workflow list."""

    name: Optional[str] = Field(
        default=None, min_length=1, max_length=100, description="Workflow list name"
    )
    description: Optional[str] = Field(
        default=None, max_length=500, description="Workflow list description"
    )
    workflow_ids: Optional[List[str]] = Field(
        default=None, description="Ordered list of workflow template IDs"
    )
    is_default: Optional[bool] = Field(
        default=None, description="Whether this is the default list"
    )
    tags: Optional[List[str]] = Field(
        default=None, description="Tags for categorization"
    )


class WorkflowListResponse(WorkflowListBase):
    """Schema for workflow list response."""

    model_config = {"from_attributes": True}

    id: str
    workflow_ids: List[str]
    workflow_count: int
    created_at: datetime
    updated_at: datetime


class WorkflowListWithWorkflowsResponse(WorkflowListResponse):
    """Schema for workflow list with full workflow details."""

    workflows: List[dict] = Field(
        default_factory=list,
        description="Full workflow objects in this list"
    )


class WorkflowListListResponse(BaseModel):
    """Schema for listing workflow lists."""

    workflow_lists: List[WorkflowListResponse]
    total: int


class WorkflowInListResponse(BaseModel):
    """Schema for a workflow within a list context."""

    template_id: str
    name: str
    description: Optional[str]
    version: str
    tags: Optional[List[str]]


class WorkflowListWorkflowsResponse(BaseModel):
    """Schema for response with workflows in a list."""

    workflows: List[WorkflowInListResponse]
    total: int
