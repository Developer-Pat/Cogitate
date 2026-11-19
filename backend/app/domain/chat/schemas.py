"""
Chat domain schemas.

Pydantic schemas for chat request/response validation.
"""

from datetime import datetime
from typing import Any, Dict, Optional, List

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Schema for chat request."""

    agent_id: int = Field(..., description="Agent ID to chat with")
    message: str = Field(..., min_length=1, max_length=10000, description="User message")
    session_id: Optional[int] = Field(default=None, description="Existing session ID (optional)")
    stream: bool = Field(default=False, description="Whether to stream response")
    generate_title: bool = Field(default=True, description="Auto-generate session title from first message")


class ChatResponse(BaseModel):
    """Schema for chat response."""

    message: str = Field(..., description="Assistant response")
    session_id: int = Field(..., description="Session ID")
    model: Optional[str] = Field(default=None, description="Model used")
    token_count: Optional[int] = Field(default=None, description="Token count")


class ChatMessageSchema(BaseModel):
    """Schema for a single chat message."""

    model_config = {"from_attributes": True}

    id: int
    role: str
    content: str
    token_count: Optional[int] = None
    model: Optional[str] = None
    provider: Optional[str] = None  # NEW: Provider name
    total_time_ms: Optional[float] = None  # NEW: Generation time
    tokens_per_second: Optional[float] = None  # NEW: Generation speed
    created_at: datetime
    # THE ROW'S META (2026-09-23): the message's `meta` JSON carries what the
    # turn CROSSED (`limits` + `limit_notice`, Phases D.2/D.3), whether the
    # provider CUT the answer (`truncated`) and the chain-of-thought fold
    # (`reasoning`). This schema listed only the flat metric columns, so every
    # one of those was dropped on the way out of the API — a limit note lived in
    # the saved row and vanished at the next reload. The note is the RECORD; the
    # toast is only the moment.
    #
    # `validation_alias` because the ORM attribute is `meta` (SQLAlchemy reserves
    # `metadata` for its own MetaData) while the API's shape — and every consumer
    # of it — calls the object `metadata`.
    metadata: Optional[Dict[str, Any]] = Field(default=None, validation_alias="meta")


class ChatSessionSchema(BaseModel):
    """Schema for chat session."""

    model_config = {"from_attributes": True}

    id: int
    title: Optional[str] = None
    agent_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    messages: Optional[List[ChatMessageSchema]] = None


class ChatSessionListResponse(BaseModel):
    """Schema for listing chat sessions."""

    sessions: List[ChatSessionSchema]
    total: int
    page: int = 1
    page_size: int = 10


class StreamChunk(BaseModel):
    """Schema for streaming response chunk."""

    chunk: str = Field(..., description="Text chunk")
    done: bool = Field(default=False, description="Whether this is the last chunk")
    session_id: Optional[int] = Field(default=None, description="Session ID")
