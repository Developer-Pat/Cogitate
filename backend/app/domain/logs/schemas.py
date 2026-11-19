"""
Log schemas for request/response validation.

Defines Pydantic models for log-related API endpoints.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, ConfigDict, Field


class FrontendLogEntry(BaseModel):
    """
    Frontend log entry schema.
    
    Represents a log entry sent from the frontend application.
    """
    
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    level: str = Field(..., description="Log level (debug, info, warning, error, critical)")
    source: str = Field(..., description="Component/hook name")
    message: str = Field(..., description="Log message")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context data")
    user_agent: Optional[str] = Field(None, description="Browser user agent")
    url: Optional[str] = Field(None, description="Page URL where event occurred")
    session_id: Optional[str] = Field(None, description="Session identifier")
    trace_id: Optional[str] = Field(None, description="Trace identifier for correlation")
    
    model_config = ConfigDict(json_schema_extra={ "example": { "timestamp": "2026-02-26T10:30:00.000Z", "level": "error", "source": "ChatPage", "message": "Failed to send message", "context": { "sessionId": "abc123", "errorMessage": "Connection timeout" }, "user_agent": "Mozilla/5.0...", "url": "http://localhost:5173/chat/123", "session_id": "user-session-456" } })


class LogEntryResponse(BaseModel):
    """
    Log entry response schema.
    
    Represents a log entry returned from the API.
    """
    
    id: int
    timestamp: str
    level: str
    source: str
    message: str
    context: Optional[Dict[str, Any]] = None
    user_agent: Optional[str] = None
    url: Optional[str] = None
    session_id: Optional[str] = None
    trace_id: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class LogStatsResponse(BaseModel):
    """
    Log statistics response schema.
    """
    
    total: int
    by_level: Dict[str, int]
    by_source: Dict[str, int]
    recent_activity: int
    frontend_logs: int
    backend_logs: int
    
    model_config = ConfigDict(json_schema_extra={ "example": { "total": 1908, "by_level": { "DEBUG": 100, "INFO": 1200, "WARNING": 400, "ERROR": 180, "CRITICAL": 28 }, "by_source": { "frontend": 850, "backend": 1058 }, "recent_activity": 45, "frontend_logs": 850, "backend_logs": 1058 } })


class LogFilterParams(BaseModel):
    """
    Log filter query parameters.
    """
    
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(50, ge=1, le=100, description="Items per page")
    level: Optional[str] = Field(None, description="Filter by log level")
    source: Optional[str] = Field(None, description="Filter by source")
    from_time: Optional[str] = Field(None, alias="from", description="Start time (ISO 8601)")
    to_time: Optional[str] = Field(None, alias="to", description="End time (ISO 8601)")
    search: Optional[str] = Field(None, description="Full-text search in message")
    session_id: Optional[str] = Field(None, description="Filter by session ID")
    
    model_config = ConfigDict(populate_by_name=True)


class PaginatedLogsResponse(BaseModel):
    """
    Paginated logs response schema.
    """
    
    items: List[LogEntryResponse]
    total: int
    page: int
    page_size: int
    has_more: bool
    
    model_config = ConfigDict(json_schema_extra={ "example": { "items": [], "total": 1908, "page": 1, "page_size": 50, "has_more": True } })
