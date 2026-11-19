"""
FastAPI router for workflow trigger management.

Provides REST API endpoints for:
- Creating and managing workflow triggers
- Listing triggers
- Activating/deactivating triggers
- Viewing scheduled triggers

Features:
- Trigger CRUD operations
- Trigger type filtering
- Schedule management
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Literal, TYPE_CHECKING, cast
from datetime import datetime, UTC
import logging

if TYPE_CHECKING:
    from app.domain.workflows.services.trigger_service import TriggerService
    from app.workflows.triggers.scheduler import TriggerScheduler

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/triggers", tags=["workflow-triggers"])


# ============== Request/Response Models ==============

class TriggerCreateRequest(BaseModel):
    """Request to create a workflow trigger."""
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
    trigger_type: str = Field(
        ...,
        description="Type of trigger",
        examples=["webhook", "schedule", "database"]
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


class TriggerUpdateRequest(BaseModel):
    """Request to update a workflow trigger."""
    workflow_id: Optional[str] = Field(
        None,
        description="ID of workflow template to execute"
    )
    trigger_type: Optional[str] = Field(
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


class TriggerInfo(BaseModel):
    """Information about a trigger."""
    id: str
    workflow_id: str
    trigger_type: str
    config: Dict[str, Any]
    is_active: bool
    name: Optional[str]
    description: str
    created_at: datetime
    updated_at: datetime


class ScheduleTriggerConfig(BaseModel):
    """Configuration for schedule trigger."""
    cron: str = Field(
        ...,
        description="Cron expression",
        examples=["0 9 * * *", "*/5 * * * *"]
    )
    timezone: str = Field(
        default="UTC",
        description="Timezone for cron execution"
    )
    enabled: bool = Field(
        default=True,
        description="Whether the schedule is enabled"
    )


class WebhookTriggerConfig(BaseModel):
    """Configuration for webhook trigger."""
    endpoint: str = Field(
        ...,
        description="Webhook endpoint path",
        examples=["/github", "/custom"]
    )
    secret: Optional[str] = Field(
        None,
        description="Secret for HMAC signature verification"
    )
    allowed_events: List[str] = Field(
        default_factory=list,
        description="List of allowed event types"
    )
    headers: Dict[str, str] = Field(
        default_factory=dict,
        description="Expected headers for validation"
    )


class ScheduleInfo(BaseModel):
    """Information about a scheduled trigger."""
    trigger_id: str
    workflow_id: str
    cron: str
    timezone: str
    next_run_time: Optional[str]
    paused: bool


# ============== Service Instance ==============

def get_service() -> "TriggerService":
    """Get trigger service instance."""
    from app.domain.workflows.services.trigger_service import TriggerService
    return TriggerService()


def get_scheduler() -> "TriggerScheduler":
    """Get scheduler instance."""
    from app.workflows.triggers.scheduler import get_scheduler
    return get_scheduler()


# ============== API Endpoints ==============

@router.post("", response_model=TriggerInfo)
async def create_trigger(request: TriggerCreateRequest):
    """
    Create a new workflow trigger.

    Creates a trigger that can automatically execute workflows based on:
    - Webhook events
    - Schedule (cron)
    - Database changes
    """
    service = get_service()

    # Validate config based on trigger type
    if request.trigger_type == "schedule":
        try:
            ScheduleTriggerConfig(**request.config)
        except Exception as e:
            logger.error(f"❌ Invalid schedule config: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid schedule config: {str(e)}"
            )

    elif request.trigger_type == "webhook":
        try:
            WebhookTriggerConfig(**request.config)
        except Exception as e:
            logger.error(f"❌ Invalid webhook config: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid webhook config: {str(e)}"
            )

    # Create trigger using service
    from app.domain.workflows.schemas.trigger_config import WorkflowTriggerCreate

    config = WorkflowTriggerCreate(
        id=request.id,
        workflow_id=request.workflow_id,
        trigger_type=cast(Literal["webhook", "schedule", "database"], request.trigger_type),
        config=request.config,
        is_active=request.is_active,
        name=request.name,
        description=request.description,
    )

    try:
        trigger = service.create_trigger(config)
    except Exception as e:
        logger.error(f"❌ Failed to create trigger: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to create trigger: {str(e)}"
        )

    # If schedule trigger, add to scheduler
    if request.trigger_type == "schedule":
        scheduler = get_scheduler()
        scheduler.add_job(
            trigger_id=request.id,
            workflow_id=request.workflow_id,
            cron_expression=request.config.get("cron", ""),
            timezone=request.config.get("timezone", "UTC"),
            enabled=request.config.get("enabled", True)
        )

    logger.info(f"✅ Created trigger: {request.id}")

    return TriggerInfo(
        id=trigger.id,
        workflow_id=trigger.workflow_id,
        trigger_type=trigger.trigger_type,
        config=trigger.config,
        is_active=trigger.is_active,
        name=trigger.name,
        description=trigger.description or "",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@router.get("", response_model=List[TriggerInfo])
async def list_triggers(
    include_inactive: bool = False,
    trigger_type: Optional[str] = None,
    workflow_id: Optional[str] = None
):
    """
    List all workflow triggers.

    Query parameters:
    - include_inactive: Include inactive triggers (default: false)
    - trigger_type: Filter by trigger type (webhook, schedule, database)
    - workflow_id: Filter by workflow ID
    """
    service = get_service()

    triggers = service.get_all_triggers(
        include_inactive=include_inactive,
        trigger_type=trigger_type,
        workflow_id=workflow_id
    )

    return [
        TriggerInfo(
            id=t.id,
            workflow_id=t.workflow_id,
            trigger_type=t.trigger_type,
            config=t.config,
            is_active=t.is_active,
            name=t.name,
            description=t.description or "",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        for t in triggers
    ]


@router.get("/{trigger_id}", response_model=TriggerInfo)
async def get_trigger(trigger_id: str):
    """
    Get a specific trigger by ID.
    """
    service = get_service()

    trigger = service.get_trigger(trigger_id)

    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    return TriggerInfo(
        id=trigger.id,
        workflow_id=trigger.workflow_id,
        trigger_type=trigger.trigger_type,
        config=trigger.config,
        is_active=trigger.is_active,
        name=trigger.name,
        description=trigger.description or "",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@router.put("/{trigger_id}", response_model=TriggerInfo)
async def update_trigger(trigger_id: str, request: TriggerUpdateRequest):
    """
    Update a workflow trigger.
    """
    service = get_service()

    from app.domain.workflows.schemas.trigger_config import WorkflowTriggerUpdate

    update = WorkflowTriggerUpdate(
        workflow_id=request.workflow_id,
        trigger_type=cast(Literal["webhook", "schedule", "database"], request.trigger_type) if request.trigger_type else None,
        config=request.config,
        is_active=request.is_active,
        name=request.name,
        description=request.description,
    )

    trigger = service.update_trigger(trigger_id, update)

    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    return TriggerInfo(
        id=trigger.id,
        workflow_id=trigger.workflow_id,
        trigger_type=trigger.trigger_type,
        config=trigger.config,
        is_active=trigger.is_active,
        name=trigger.name,
        description=trigger.description or "",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@router.delete("/{trigger_id}")
async def delete_trigger(trigger_id: str):
    """
    Delete a workflow trigger.
    """
    service = get_service()

    # If schedule trigger, remove from scheduler first
    trigger = service.get_trigger(trigger_id)
    if trigger and trigger.trigger_type == "schedule":
        scheduler = get_scheduler()
        scheduler.remove_job(trigger_id)

    success = service.delete_trigger(trigger_id)

    if not success:
        raise HTTPException(status_code=404, detail="Trigger not found")

    logger.info(f"✅ Deleted trigger: {trigger_id}")
    return {"message": f"Trigger {trigger_id} deleted"}


@router.post("/{trigger_id}/activate")
async def activate_trigger(trigger_id: str):
    """
    Activate a workflow trigger.
    """
    service = get_service()

    success = service.activate_trigger(trigger_id)

    if not success:
        raise HTTPException(status_code=404, detail="Trigger not found")

    # If schedule trigger, add (if never loaded) or resume in scheduler
    trigger = service.get_trigger(trigger_id)
    if trigger and trigger.trigger_type == "schedule":
        scheduler = get_scheduler()
        job_info = scheduler.get_job_info(trigger_id)
        if job_info is None:
            # Job was never added (e.g. trigger was inactive at startup)
            config = trigger.config
            scheduler.add_job(
                trigger_id=trigger.id,
                workflow_id=trigger.workflow_id,
                cron_expression=config.get("cron", ""),
                timezone=config.get("timezone", "UTC"),
                enabled=config.get("enabled", True),
            )
        else:
            scheduler.resume_job(trigger_id)

    logger.info(f"✅ Activated trigger: {trigger_id}")
    return {"message": f"Trigger {trigger_id} activated"}


@router.post("/{trigger_id}/deactivate")
async def deactivate_trigger(trigger_id: str):
    """
    Deactivate a workflow trigger.
    """
    service = get_service()

    success = service.deactivate_trigger(trigger_id)

    if not success:
        raise HTTPException(status_code=404, detail="Trigger not found")

    # If schedule trigger, pause in scheduler
    trigger = service.get_trigger(trigger_id)
    if trigger and trigger.trigger_type == "schedule":
        scheduler = get_scheduler()
        scheduler.pause_job(trigger_id)

    logger.info(f"✅ Deactivated trigger: {trigger_id}")
    return {"message": f"Trigger {trigger_id} deactivated"}


@router.get("/schedules/list", response_model=List[ScheduleInfo])
async def list_schedules():
    """
    List all scheduled triggers with their next run times.
    """
    scheduler = get_scheduler()
    service = get_service()

    jobs = scheduler.get_all_jobs()
    triggers = service.get_active_triggers_by_type("schedule")

    schedules = []
    for job in jobs:
        # Find matching trigger
        trigger = next(
            (t for t in triggers if t.id == job["trigger_id"]),
            None
        )

        if trigger:
            schedules.append(ScheduleInfo(
                trigger_id=job["trigger_id"],
                workflow_id=trigger.workflow_id,
                cron=trigger.config.get("cron", ""),
                timezone=trigger.config.get("timezone", "UTC"),
                next_run_time=job["next_run_time"],
                paused=job["paused"],
            ))

    return schedules


@router.get("/webhooks/endpoints", response_model=List[Dict[str, Any]])
async def list_webhook_endpoints():
    """
    List all webhook endpoints.

    Returns information about configured webhook endpoints including:
    - Endpoint path
    - Associated workflow
    - Allowed events
    - Signature requirements
    """
    from app.workflows.triggers.webhook_handler import WebhookHandler
    from app.workflows.triggers.event_router import EventRouter

    event_router = EventRouter()
    handler = WebhookHandler(event_router)

    return handler.list_webhook_endpoints()
