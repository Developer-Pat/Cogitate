"""
Team Tools domain schemas.

Pydantic schemas for team-tool assignment request/response validation.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# Team Tool Schemas
# =============================================================================


class TeamToolBase(BaseModel):
    """Base schema for team-tool assignments."""

    model_config = ConfigDict(from_attributes=True)

    priority: int = Field(
        0,
        description="Priority for conflict resolution (higher = more important)",
    )
    is_active: bool = Field(True, description="Whether this assignment is active")
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Tool-specific configuration for this team",
    )


class TeamToolCreate(TeamToolBase):
    """Schema for creating a team-tool assignment."""

    tool_id: str = Field(..., description="Tool ID (UUID)")
    source_type: str = Field(
        ...,
        description="Source type: 'direct'",
        pattern="^(direct)$",
    )
    source_id: Optional[str] = Field(
        None,
        description="Source ID (the collection the tool came from)",
    )


class TeamToolUpdate(BaseModel):
    """Schema for updating a team-tool assignment."""

    priority: Optional[int] = Field(None, description="Priority for conflict resolution")
    is_active: Optional[bool] = Field(None, description="Whether assignment is active")
    config: Optional[Dict[str, Any]] = Field(
        None, description="Tool-specific configuration"
    )


class ToolSummary(BaseModel):
    """Summary of a tool for team-tool responses."""

    id: str
    name: str
    slug: str
    description: str
    icon: Optional[str] = None
    color: Optional[str] = None
    is_active: bool


class TeamToolResponse(TeamToolBase):
    """Schema for team-tool response."""

    id: str
    team_id: str
    tool_id: str
    source_type: str
    source_id: Optional[str] = None
    tool: Optional[ToolSummary] = None
    created_at: datetime
    updated_at: datetime


class TeamToolListResponse(BaseModel):
    """Schema for listing team tools."""

    tools: List[TeamToolResponse]
    total: int


# =============================================================================
# Team Sync Schemas
# =============================================================================


class TeamSyncRequest(BaseModel):
    """Schema for team sync request."""

    agent_ids: Optional[List[str]] = Field(
        None,
        description="Specific agent IDs to sync. If None, sync all team members.",
    )


class TeamSyncResult(BaseModel):
    """Schema for team sync result."""

    synced_agents: List[str] = Field(
        default_factory=list,
        description="List of agent IDs that were synced",
    )
    tools_assigned: int = Field(0, description="Number of tools assigned")
    tools_removed: int = Field(0, description="Number of tools removed")
    conflicts_detected: int = Field(0, description="Number of conflicts detected")


class ConflictInfo(BaseModel):
    """Schema for conflict information."""

    agent_id: str
    tool_id: str
    tool_name: str
    conflicting_teams: List[Dict[str, str]]
    resolution: str  # "last_team_wins"
    winning_team_id: str


class TeamSyncWithConflicts(TeamSyncResult):
    """Schema for team sync result with conflict information."""

    conflicts: List[ConflictInfo] = Field(
        default_factory=list,
        description="List of detected conflicts",
    )
