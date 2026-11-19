"""
Workflow trigger configuration schemas.

Pydantic schemas for defining and validating workflow triggers,
enabling event-driven execution via webhooks, schedules, or database events.
"""

import logging
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal, List, Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class WebhookConfig(BaseModel):
    """
    Configuration for webhook triggers.

    Attributes:
        endpoint: Webhook endpoint path (e.g., '/github', '/custom')
        secret: Optional secret for HMAC signature verification
        allowed_events: List of allowed event types
        headers: Expected headers for validation
    """
    endpoint: str = Field(
        ...,
        description="Webhook endpoint path",
        examples=["/github", "/custom", "/deploy"]
    )
    secret: Optional[str] = Field(
        None,
        description="Secret for HMAC signature verification"
    )
    allowed_events: List[str] = Field(
        default_factory=list,
        description="List of allowed event types",
        examples=[["push", "pull_request"]]
    )
    headers: Dict[str, str] = Field(
        default_factory=dict,
        description="Expected headers for validation"
    )

    model_config = ConfigDict(json_schema_extra={ "example": { "endpoint": "/github", "secret": "your-webhook-secret", "allowed_events": ["push", "pull_request"], "headers": {"X-GitHub-Event": "push"} } })


class ScheduleConfig(BaseModel):
    """
    Configuration for scheduled triggers.

    Attributes:
        cron: Cron expression (e.g., '0 9 * * *' for daily at 9 AM)
        timezone: Timezone for cron execution (default: UTC)
        enabled: Whether the schedule is enabled
    """
    cron: str = Field(
        ...,
        description="Cron expression",
        examples=["0 9 * * *", "*/5 * * * *", "0 0 1 1 *"]
    )
    timezone: str = Field(
        default="UTC",
        description="Timezone for cron execution"
    )
    enabled: bool = Field(
        default=True,
        description="Whether the schedule is enabled"
    )

    @field_validator('cron')
    @classmethod
    def validate_cron(cls, v):
        """Validate cron expression has 5 parts."""
        parts = v.strip().split()
        if len(parts) != 5:
            raise ValueError("Cron expression must have 5 parts: minute hour day month weekday")
        return v

    model_config = ConfigDict(json_schema_extra={ "example": { "cron": "0 9 * * *", "timezone": "UTC", "enabled": True } })


class DatabaseTriggerConfig(BaseModel):
    """
    Configuration for database event triggers.

    Attributes:
        table: Table to monitor
        event: Event type (insert, update, delete)
        condition: Optional SQL condition for filtering
    """
    table: str = Field(
        ...,
        description="Table to monitor",
        examples=["chat_sessions", "agents"]
    )
    event: Literal["insert", "update", "delete"] = Field(
        ...,
        description="Event type to trigger on"
    )
    condition: Optional[str] = Field(
        None,
        description="Optional SQL condition for filtering"
    )

    model_config = ConfigDict(json_schema_extra={ "example": { "table": "chat_sessions", "event": "insert", "condition": "status = 'pending'" } })


class WorkflowTrigger(BaseModel):
    """
    Workflow trigger configuration.

    Enables automatic workflow execution based on events:
    - Webhook: HTTP POST to trigger endpoint
    - Schedule: Cron-based scheduled execution
    - Database: Monitor database changes

    Attributes:
        id: Unique identifier for this trigger
        workflow_id: ID of workflow template to execute
        trigger_type: Type of trigger (webhook, schedule, database)
        config: Trigger-specific configuration
        is_active: Whether the trigger is active
        name: Human-readable name
        description: Detailed description
    """
    id: str = Field(
        ...,
        description="Unique identifier for this trigger",
        examples=["daily-briefing-trigger", "code-review-webhook"]
    )
    workflow_id: str = Field(
        ...,
        description="ID of workflow template to execute",
        examples=["daily-briefing", "code-review-pipeline"]
    )
    trigger_type: Literal["webhook", "schedule", "database"] = Field(
        ...,
        description="Type of trigger"
    )
    config: Dict[str, Any] = Field(
        ...,
        description="Trigger-specific configuration"
    )
    is_active: bool = Field(
        default=True,
        description="Whether the trigger is active"
    )
    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
        description="Human-readable name"
    )
    description: Optional[str] = Field(
        default="",
        description="Detailed description"
    )

    @field_validator('config')
    @classmethod
    def validate_config(cls, v, info):
        """Validate config based on trigger type."""
        # This validation happens at runtime when we know trigger_type
        # For schema validation, we just check it's a dict
        if not isinstance(v, dict):
            raise ValueError("Config must be a dictionary")
        return v

    model_config = ConfigDict(json_schema_extra={ "example": { "id": "daily-briefing-trigger", "workflow_id": "daily-briefing", "trigger_type": "schedule", "config": { "cron": "0 9 * * *", "timezone": "UTC" }, "is_active": True, "name": "Daily Briefing at 9 AM", "description": "Automated daily briefing generation" } })


class WorkflowTriggerCreate(BaseModel):
    """
    Request to create a workflow trigger.

    Same as WorkflowTrigger but without optional fields defaults.
    """
    id: str = Field(
        ...,
        description="Unique identifier for this trigger"
    )
    workflow_id: str = Field(
        ...,
        description="ID of workflow template to execute"
    )
    trigger_type: Literal["webhook", "schedule", "database"] = Field(
        ...,
        description="Type of trigger"
    )
    config: Dict[str, Any] = Field(
        ...,
        description="Trigger-specific configuration"
    )
    is_active: bool = Field(
        default=True,
        description="Whether the trigger is active"
    )
    name: Optional[str] = Field(
        None,
        description="Human-readable name"
    )
    description: str = Field(
        default="",
        description="Detailed description"
    )


class WorkflowTriggerUpdate(BaseModel):
    """
    Request to update a workflow trigger.

    All fields are optional for partial updates.
    """
    workflow_id: Optional[str] = Field(
        None,
        description="ID of workflow template to execute"
    )
    trigger_type: Optional[Literal["webhook", "schedule", "database"]] = Field(
        None,
        description="Type of trigger"
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Trigger-specific configuration"
    )
    is_active: Optional[bool] = Field(
        None,
        description="Whether the trigger is active"
    )
    name: Optional[str] = Field(
        None,
        description="Human-readable name"
    )
    description: Optional[str] = Field(
        None,
        description="Detailed description"
    )


class WorkflowTriggerResponse(BaseModel):
    """
    Response containing workflow trigger information.
    """
    id: str
    workflow_id: str
    trigger_type: str
    config: Dict[str, Any]
    is_active: bool
    name: Optional[str]
    description: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TriggerExecutionResult(BaseModel):
    """
    Result of executing a trigger.

    Attributes:
        trigger_id: ID of the executed trigger
        workflow_id: ID of workflow that was triggered
        execution_id: ID of the workflow execution
        status: Execution status
        triggered_at: When the trigger was executed
        error: Error message if execution failed
    """
    trigger_id: str = Field(..., description="ID of executed trigger")
    workflow_id: str = Field(..., description="ID of triggered workflow")
    execution_id: Optional[str] = Field(None, description="ID of workflow execution")
    status: Literal["success", "error", "skipped"] = Field(..., description="Execution status")
    triggered_at: str = Field(..., description="When trigger was executed")
    error: Optional[str] = Field(None, description="Error message if failed")

    model_config = ConfigDict(json_schema_extra={ "example": { "trigger_id": "daily-briefing-trigger", "workflow_id": "daily-briefing", "execution_id": "exec-123", "status": "success", "triggered_at": "2026-03-30T09:00:00Z" } })
