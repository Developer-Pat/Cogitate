"""
Pydantic schemas for the Agent Chat (JSON Adapter) API.

Defines request/response models for agent-to-agent and script-to-agent
communication with structured JSON responses and full cognitive trace data.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class CreateSessionRequest(BaseModel):
    """Request to create a new agent chat session."""

    agent_id: int = Field(..., description="ID of the agent to chat with")
    title: Optional[str] = Field(None, description="Optional session title")
    cognitive_config: Optional[Dict[str, str]] = Field(
        None,
        description=(
            "Per-component strategy overrides. "
            "Keys: context_builder, executor, memory_manager, response_formatter"
        ),
    )


class SendMessageRequest(BaseModel):
    """Request to send a message and get a JSON response."""

    session_id: int = Field(..., description="ID of the session")
    message: str = Field(..., description="The message text", min_length=1)
    cognitive_config: Optional[Dict[str, str]] = Field(
        None,
        description=(
            "Optional per-call strategy overrides. "
            "Keys: context_builder, executor, memory_manager, response_formatter"
        ),
    )


class UpdateStatusRequest(BaseModel):
    """Request to toggle external access status."""

    enabled: bool = Field(..., description="Whether external access is enabled")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ComponentTraceSchema(BaseModel):
    """Serializable trace for a single pipeline component."""

    strategy: str = "unknown"
    duration_ms: int = 0
    tokens_used: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class CognitiveTraceSchema(BaseModel):
    """Serializable trace across all pipeline components."""

    context_builder: ComponentTraceSchema = Field(
        default_factory=ComponentTraceSchema
    )
    executor: ComponentTraceSchema = Field(default_factory=ComponentTraceSchema)
    memory_manager: ComponentTraceSchema = Field(
        default_factory=ComponentTraceSchema
    )
    response_formatter: ComponentTraceSchema = Field(
        default_factory=ComponentTraceSchema
    )
    total_duration_ms: int = 0
    total_tokens: int = 0


class CognitiveMetricsSchema(BaseModel):
    """Aggregate performance metrics for a pipeline run."""

    total_duration_ms: int = 0
    total_tokens: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    cache_hits: int = 0


class MemoryDeltaSchema(BaseModel):
    """What changed in memory as a result of this pipeline run."""

    stored_keys: List[str] = Field(default_factory=list)
    evicted_keys: List[str] = Field(default_factory=list)
    compaction_triggered: bool = False
    summary: Optional[str] = None


class MessageResponse(BaseModel):
    """A single message in the session history."""

    id: int
    role: str
    content: str
    token_count: Optional[int] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    total_time_ms: Optional[float] = None
    metadata: Optional[dict] = None  # THE THINKING FOLD (2026-08-24): the reasoning
    created_at: datetime


class SessionResponse(BaseModel):
    """Response for session creation / retrieval."""

    id: int
    agent_id: int
    title: Optional[str] = None
    is_active: bool = True
    cognitive_config: Optional[Dict[str, str]] = None
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = Field(default_factory=list)


class SendMessageResponse(BaseModel):
    """Response after sending a message."""

    session_id: int
    message_id: int
    response: str
    trace: CognitiveTraceSchema
    metrics: CognitiveMetricsSchema
    memory_delta: Optional[MemoryDeltaSchema] = None
    error: Optional[str] = None


class TraceResponse(BaseModel):
    """Full cognitive trace for a session."""

    session_id: int
    trace: CognitiveTraceSchema
    metrics: CognitiveMetricsSchema
    memory_delta: Optional[MemoryDeltaSchema] = None


class PresetCreateRequest(BaseModel):
    """Request to create a new cognitive configuration preset."""

    name: str = Field(
        ..., description="Unique name for the preset", min_length=1, max_length=100
    )
    description: Optional[str] = Field(
        None, description="Optional description of the preset"
    )
    context_builder: str = Field(
        "default", description="Context builder strategy"
    )
    executor: str = Field("default", description="Executor strategy")
    memory_manager: str = Field(
        "default", description="Memory manager strategy"
    )
    response_formatter: str = Field(
        "default", description="Response formatter strategy"
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Extended configuration (temperature, memory settings, etc.). "
            "Arbitrary JSON object for future-proof extensibility."
        ),
    )


class PresetUpdateRequest(BaseModel):
    """Request to update an existing cognitive configuration preset."""

    name: Optional[str] = Field(
        None, description="New unique name", max_length=100
    )
    description: Optional[str] = Field(
        None, description="New description"
    )
    context_builder: Optional[str] = Field(
        None, description="Context builder strategy"
    )
    executor: Optional[str] = Field(None, description="Executor strategy")
    memory_manager: Optional[str] = Field(
        None, description="Memory manager strategy"
    )
    response_formatter: Optional[str] = Field(
        None, description="Response formatter strategy"
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Extended configuration (replaces existing if provided)",
    )


class PresetResponse(BaseModel):
    """Response model for a cognitive configuration preset."""

    id: int
    name: str
    description: Optional[str] = None
    context_builder: str = "default"
    executor: str = "default"
    memory_manager: str = "default"
    response_formatter: str = "default"
    config: Optional[Dict[str, Any]] = None
    is_builtin: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PresetExportData(BaseModel):
    """Schema for exporting/importing presets as JSON."""

    format_version: str = Field("1", description="Export format version")
    presets: List[PresetResponse] = Field(
        ..., description="List of presets to export"
    )


class StatusResponse(BaseModel):
    """External access status."""

    enabled: bool


# ---------------------------------------------------------------------------
# WebSocket Bridge schemas
# ---------------------------------------------------------------------------


class UIStateUpdateRequest(BaseModel):
    """Request body for ``POST /api/v1/agent-chat/ui-state``.

    All fields are optional so the frontend can send partial updates.
    """

    current_route: Optional[str] = Field(
        None, description="Current frontend route path"
    )
    sidebar_collapsed: Optional[bool] = Field(
        None, description="Whether the sidebar is collapsed"
    )
    theater_mode_active: Optional[bool] = Field(
        None, description="Whether theater mode is active"
    )
    active_agent_id: Optional[str] = Field(
        None, description="ID of the currently selected agent (string, may be client-generated)"
    )
    active_agent_name: Optional[str] = Field(
        None, description="Name of the currently selected agent"
    )
    active_session_id: Optional[str] = Field(
        None, description="ID of the currently active chat session (string, may be client-generated)"
    )
    active_session_title: Optional[str] = Field(
        None, description="Title of the currently active chat session"
    )
    theme: Optional[str] = Field(
        None, description="Current theme (light/dark/auto)"
    )


class UIStateResponse(BaseModel):
    """Snapshot of the current frontend UI state.

    Returned by ``GET /api/v1/agent-chat/ui-state`` and pushed via WebSocket
    when the state changes.
    """

    current_route: str = Field(
        "/", description="Current frontend route path"
    )
    sidebar_collapsed: bool = Field(
        False, description="Whether the sidebar is collapsed"
    )
    theater_mode_active: bool = Field(
        False, description="Whether theater mode is active"
    )
    active_agent_id: Optional[str] = Field(
        None, description="ID of the currently selected agent (string, may be client-generated)"
    )
    active_agent_name: Optional[str] = Field(
        None, description="Name of the currently selected agent"
    )
    active_session_id: Optional[str] = Field(
        None, description="ID of the currently active chat session (string, may be client-generated)"
    )
    active_session_title: Optional[str] = Field(
        None, description="Title of the currently active chat session"
    )
    theme: str = Field(
        "light", description="Current theme (light/dark/auto)"
    )
    timestamp: str = Field(
        ..., description="ISO 8601 timestamp of the state snapshot"
    )


class UINavigateRequest(BaseModel):
    """Request to programmatically navigate the frontend to a route."""

    route: str = Field(
        ..., description="Target frontend route path to navigate to"
    )
    replace: bool = Field(
        False,
        description="If true, replace the current history entry instead of pushing",
    )


class UINavigateResponse(BaseModel):
    """Response confirming the navigation request."""

    success: bool = Field(..., description="Whether the navigation was accepted")
    route: str = Field(..., description="The route that was navigated to")
    message: str = Field(
        "Navigation request accepted", description="Human-readable status message"
    )


class WSMessage(BaseModel):
    """WebSocket message envelope for UI state push."""

    type: str = Field(
        ...,
        description="Message type: ui_state_update, navigation_request, ping, pong",
    )
    payload: Optional[Dict[str, Any]] = Field(
        None, description="Message payload (varies by type)"
    )
    timestamp: str = Field(
        ..., description="ISO 8601 timestamp of the message"
    )
