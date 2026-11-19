"""
Session domain schemas.

Pydantic schemas for session management.
"""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field

from app.domain.chat.schemas import ChatMessageSchema


class SessionCreate(BaseModel):
    """Schema for creating a new session."""

    agent_id: Optional[int] = Field(
        default=None,
        description="Agent ID — null for the external surface "
        "(Exa chats: source='exa', 2026-08-21).",
    )
    title: Optional[str] = Field(default=None, max_length=200, description="Session title")
    source: str = Field(default="agent", max_length=20, description="Session source: 'agent' | 'exa' (2026-08-21)")


class MessageCreate(BaseModel):
    """A message to append to a session (2026-08-21).

    The Exa chat bridge's persistence path — the external surface
    has no pipeline handler (the normal chat saves messages inside
    send_message); this endpoint is the explicit save.
    """

    role: str = Field(..., max_length=20, description="'user' | 'assistant'")
    content: str = Field(..., description="The message body")


class SessionUpdate(BaseModel):
    """Schema for updating a session."""

    title: Optional[str] = Field(default=None, max_length=200, description="Session title")
    is_active: Optional[bool] = Field(default=None, description="Active status")


class SessionResponse(BaseModel):
    """Schema for session response."""

    model_config = {"from_attributes": True}

    id: int
    title: Optional[str] = None
    agent_id: Optional[int] = None
    # THE AGENT'S MODEL (2026-09-06): the sessions payload never carried
    # it — the frontend fell back to 'llama3.2' + warned per session
    # ('Session model missing'). The router attaches it from the agents
    # table (chat_sessions.agent_id -> agents.model).
    model: Optional[str] = None
    source: str = "agent"
    is_active: bool
    created_at: datetime
    updated_at: datetime
    messages: Optional[List[ChatMessageSchema]] = None
    # THE MESSAGE COUNT (2026-09-15): the list endpoint is titles-only and sends
    # `messages: []`, so anything wanting a count had to read the lazily-loaded
    # `messages` array — wrong (0) for unopened sessions and stale for the open
    # one. The router fills this from a single COUNT query. None means "not
    # asked for" (the include_messages path), not zero.
    message_count: Optional[int] = None


class SessionListResponse(BaseModel):
    """Schema for listing sessions."""

    sessions: List[SessionResponse]
    total: int
    page: int = 1
    page_size: int = 10
