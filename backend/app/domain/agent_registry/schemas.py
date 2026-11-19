"""
Agent Registry schemas.

Pydantic models for the Agent Registry API.
"""

from datetime import datetime
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field


# ── Lifecycle Status ──────────────────────────────────────────────────────

AGENT_LIFECYCLE_STATUSES = {"active", "experimental", "archived", "deprecated"}


# ── Request Schemas ───────────────────────────────────────────────────────


class AgentPackageCreate(BaseModel):
    """Schema for creating a new agent package."""

    name: str = Field(..., min_length=1, max_length=200, description="Unique package name")
    role: str = Field("generic", max_length=100, description="Agent role/type")
    version: str = Field("1.0.0", max_length=50, description="Semantic version string")
    status: str = Field("experimental", max_length=20, description="Lifecycle status")
    system_prompt: Optional[str] = Field(None, description="System prompt for the agent")
    code: Optional[str] = Field(None, description="Python code string executed by Nucleus")
    tools_schema: Optional[Dict[str, Any]] = Field(None, description="JSON schema for tools")
    parent_version_id: Optional[int] = Field(None, description="ID of parent version for lineage")
    package_metadata: Optional[Dict[str, Any]] = Field(None, description="Flexible metadata JSON")


class AgentPackageUpdate(BaseModel):
    """Schema for updating an existing agent package."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    role: Optional[str] = Field(None, max_length=100)
    version: Optional[str] = Field(None, max_length=50)
    status: Optional[str] = Field(None, max_length=20)
    system_prompt: Optional[str] = Field(None)
    code: Optional[str] = Field(None)
    tools_schema: Optional[Dict[str, Any]] = Field(None)
    parent_version_id: Optional[int] = Field(None)
    package_metadata: Optional[Dict[str, Any]] = Field(None)


# ── Response Schemas ──────────────────────────────────────────────────────


class AgentPackageResponse(BaseModel):
    """Schema for agent package responses."""

    id: int
    name: str
    role: str
    version: str
    status: str
    system_prompt: Optional[str] = None
    code: Optional[str] = None
    tools_schema: Optional[Dict[str, Any]] = None
    parent_version_id: Optional[int] = None
    package_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    archived_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AgentPackageListResponse(BaseModel):
    """Schema for paginated list responses."""

    items: List[AgentPackageResponse]
    total: int
    skip: int = 0
    limit: int = 100


class AgentPackageVersionResponse(BaseModel):
    """Schema for a version in the lineage tree."""

    id: int
    name: str
    version: str
    status: str
    parent_version_id: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentPackageLineageResponse(BaseModel):
    """Schema for the full lineage tree of a package."""

    package: AgentPackageResponse
    ancestors: List[AgentPackageVersionResponse]
    descendants: List[AgentPackageVersionResponse]
