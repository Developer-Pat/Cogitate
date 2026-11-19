"""
Tools domain schemas.

Pydantic schemas for tool management request/response validation.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# Tool Category Schemas
# =============================================================================


class ToolCategoryBase(BaseModel):
    """Base schema for tool categories."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Category name", max_length=200)
    slug: str = Field(..., description="URL-friendly identifier", max_length=200)
    description: Optional[str] = Field(None, description="Category description")
    icon: Optional[str] = Field(None, description="Icon name", max_length=50)
    sort_order: int = Field(0, description="Sort order for display")


class ToolCategoryCreate(ToolCategoryBase):
    """Schema for creating a tool category."""

    parent_id: Optional[str] = Field(None, description="Parent category ID (UUID)")


class ToolCategoryUpdate(BaseModel):
    """Schema for updating a tool category."""

    name: Optional[str] = Field(None, description="Category name", max_length=200)
    slug: Optional[str] = Field(None, description="URL-friendly identifier", max_length=200)
    description: Optional[str] = Field(None, description="Category description")
    icon: Optional[str] = Field(None, description="Icon name", max_length=50)
    sort_order: Optional[int] = Field(None, description="Sort order for display")


class ToolCategoryResponse(ToolCategoryBase):
    """Schema for tool category response."""

    id: str
    parent_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ToolCategoryListResponse(BaseModel):
    """Schema for listing tool categories."""

    categories: List[ToolCategoryResponse]
    total: int


# =============================================================================
# Tool Schemas
# =============================================================================


class ToolBase(BaseModel):
    """Base schema for tools."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Tool name", max_length=200)
    slug: str = Field(..., description="URL-friendly identifier", max_length=200)
    description: str = Field(..., description="Tool description")
    capability: Optional[str] = Field(
        None, description="Canonical capability slug (the ARM vocabulary, Phase A)",
        max_length=64,
    )
    version: str = Field("1.0.0", description="Tool version", max_length=20)
    provider: Optional[str] = Field(None, description="Tool provider", max_length=100)
    type: Optional[str] = Field(None, description="Tool type", max_length=50)
    config_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema for tool configuration",
    )
    arguments_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema for tool arguments (what LLM provides)",
    )
    endpoint: Optional[str] = Field(None, description="Tool endpoint URL", max_length=500)
    timeout_ms: int = Field(30000, description="Timeout in milliseconds")
    requires_auth: bool = Field(False, description="Whether tool requires authentication")
    icon: Optional[str] = Field(None, description="Icon name", max_length=50)
    color: Optional[str] = Field(None, description="Color for UI", max_length=20)
    tags: Optional[List[str]] = Field(
        default_factory=list,
        description="Tool tags for filtering and organization (e.g., ['op:read', 'purpose:productivity', 'safe'])",
        examples=[["op:read", "purpose:productivity", "safe"], ["op:write", "source:local-file", "side-effects"]],
    )
    is_active: bool = Field(True, description="Whether tool is active")
    is_builtin: bool = Field(False, description="Whether tool is built-in")


class ToolCreate(ToolBase):
    """Schema for creating a tool."""

    category_id: Optional[str] = Field(None, description="Category ID (UUID)")


class ToolUpdate(BaseModel):
    """Schema for updating a tool."""

    name: Optional[str] = Field(None, description="Tool name", max_length=200)
    slug: Optional[str] = Field(None, description="URL-friendly identifier", max_length=200)
    description: Optional[str] = Field(None, description="Tool description")
    version: Optional[str] = Field(None, description="Tool version", max_length=20)
    category_id: Optional[str] = Field(None, description="Category ID (UUID)")
    provider: Optional[str] = Field(None, description="Tool provider", max_length=100)
    type: Optional[str] = Field(None, description="Tool type", max_length=50)
    config_schema: Optional[Dict[str, Any]] = Field(
        None, description="JSON Schema for tool configuration"
    )
    endpoint: Optional[str] = Field(None, description="Tool endpoint URL", max_length=500)
    timeout_ms: Optional[int] = Field(None, description="Timeout in milliseconds")
    requires_auth: Optional[bool] = Field(None, description="Whether tool requires authentication")
    icon: Optional[str] = Field(None, description="Icon name", max_length=50)
    color: Optional[str] = Field(None, description="Color for UI", max_length=20)
    tags: Optional[List[str]] = Field(
        None,
        description="Tool tags for filtering and organization (e.g., ['op:read', 'purpose:productivity', 'safe'])",
    )
    is_active: Optional[bool] = Field(None, description="Whether tool is active")
    is_builtin: Optional[bool] = Field(None, description="Whether tool is built-in")


class CategorySummary(BaseModel):
    """Summary of a tool category."""

    id: str
    name: str
    slug: str
    icon: Optional[str] = None


class ToolResponse(ToolBase):
    """Schema for tool response."""

    id: str
    category_id: Optional[str] = None
    category: Optional[CategorySummary] = None
    usage_count: int
    access_tier: Optional[str] = Field(
        default=None, description="gras | keyed override; NULL = derive from capability"
    )
    created_at: datetime
    updated_at: datetime


class ToolListResponse(BaseModel):
    """Schema for listing tools."""

    tools: List[ToolResponse]
    total: int


class ToolSearchResponse(ToolListResponse):
    """Schema for tool search results."""

    query: str
    filters: Optional[Dict[str, Any]] = None


# =============================================================================
# Agent-Tool Association Schemas
# =============================================================================


class AgentToolBase(BaseModel):
    """Base schema for agent-tool associations."""

    model_config = ConfigDict(from_attributes=True)

    is_enabled: bool = Field(True, description="Whether tool is enabled for agent")
    priority: int = Field(0, description="Tool priority (higher = more important)")
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Tool-specific configuration",
    )


class AgentToolCreate(AgentToolBase):
    """Schema for creating an agent-tool association."""

    tool_id: str = Field(..., description="Tool ID (UUID)")


class AgentToolUpdate(BaseModel):
    """Schema for updating an agent-tool association."""

    is_enabled: Optional[bool] = Field(None, description="Whether tool is enabled")
    priority: Optional[int] = Field(None, description="Tool priority")
    config: Optional[Dict[str, Any]] = Field(None, description="Tool-specific configuration")


class ToolSummary(BaseModel):
    """Summary of a tool."""

    id: str
    name: str
    slug: str
    description: str
    icon: Optional[str] = None
    color: Optional[str] = None
    category: Optional[CategorySummary] = None
    config_schema: Dict[str, Any] = Field(default_factory=dict)
    arguments_schema: Dict[str, Any] = Field(default_factory=dict)


class AgentToolResponse(AgentToolBase):
    """Schema for agent-tool response."""

    id: str
    agent_id: str
    tool_id: str
    tool: Optional[ToolSummary] = None
    created_at: datetime
    updated_at: datetime


class AgentToolListResponse(BaseModel):
    """Schema for listing agent tools."""

    tools: List[AgentToolResponse]
    total: int


class AgentToolEnableRequest(BaseModel):
    """Schema for enabling a tool for an agent."""

    tool_id: str = Field(..., description="Tool ID (UUID)")
    priority: int = Field(0, description="Tool priority")
    config: Dict[str, Any] = Field(default_factory=dict, description="Tool configuration")


# =============================================================================
# Tool Usage Log Schemas
# =============================================================================


class ToolUsageLogBase(BaseModel):
    """Base schema for tool usage logs."""

    model_config = ConfigDict(from_attributes=True)

    agent_id: str = Field(..., description="Agent ID (UUID)")
    session_id: Optional[str] = Field(None, description="Session ID (UUID)")
    success: bool = Field(True, description="Whether tool execution was successful")
    execution_time_ms: Optional[int] = Field(None, description="Execution time in milliseconds")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ToolUsageLogCreate(ToolUsageLogBase):
    """Schema for creating a tool usage log."""

    tool_id: str = Field(..., description="Tool ID (UUID)")


class ToolUsageLogResponse(ToolUsageLogBase):
    """Schema for tool usage log response."""

    id: str
    tool_id: str
    tool_name: Optional[str] = None
    created_at: datetime


class ToolUsageLogListResponse(BaseModel):
    """Schema for listing tool usage logs."""

    logs: List[ToolUsageLogResponse]
    total: int


# =============================================================================
# Analytics Schemas
# =============================================================================


class ToolUsageStats(BaseModel):
    """Schema for tool usage statistics."""

    tool_id: str
    tool_name: str
    total_usage: int
    success_rate: float
    avg_execution_time_ms: Optional[float] = None


class ToolUsageStatsResponse(BaseModel):
    """Schema for tool usage stats response."""

    stats: List[ToolUsageStats]
    period_start: datetime
    period_end: datetime


# =============================================================================
# Tool Execution Schemas
# =============================================================================


class ToolExecutionRequest(BaseModel):
    """Schema for tool execution request."""

    agent_id: str = Field(..., description="Agent ID")
    tool_slug: str = Field(..., description="Tool slug to execute")
    arguments: Dict[str, Any] = Field(
        default_factory=dict, description="Tool arguments"
    )
    session_id: Optional[str] = Field(
        None, description="Optional session ID for logging"
    )


class ToolExecutionResponse(BaseModel):
    """Schema for tool execution response."""

    success: bool = Field(..., description="Whether the execution was successful")
    tool_slug: str = Field(..., description="Tool slug")
    tool_name: str = Field(..., description="Tool name")
    result: Optional[Any] = Field(None, description="Execution result (if successful)")
    error: Optional[str] = Field(None, description="Error message (if failed)")
    error_type: Optional[str] = Field(None, description="Error type (if failed)")
    execution_time_ms: int = Field(..., description="Execution time in milliseconds")
    tokens_used: int = Field(0, description="Number of tokens consumed")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional execution metadata"
    )

    model_config = ConfigDict(from_attributes=True)
