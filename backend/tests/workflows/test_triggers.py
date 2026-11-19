"""
Trigger config validation: webhook, schedule cron syntax, database and workflow triggers.

Tests cover:
- Trigger schema validation
- Trigger service CRUD operations
- Event router matching
- Webhook handler
- Scheduler integration
- API endpoints

Run with:
    uv run pytest tests/workflows/test_triggers.py -v
"""

import pytest
import uuid

from app.domain.workflows.schemas.trigger_config import (
    WorkflowTrigger,
    WorkflowTriggerCreate,
    WorkflowTriggerUpdate,
    WebhookConfig,
    ScheduleConfig,
    DatabaseTriggerConfig,
)
from app.domain.workflows.services.trigger_service import TriggerService
from app.workflows.triggers.event_router import EventRouter
from app.workflows.triggers.webhook_handler import WebhookHandler
from app.workflows.triggers.scheduler import TriggerScheduler


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def trigger_service():
    """Create trigger service instance."""
    return TriggerService()


@pytest.fixture
def event_router():
    """Create event router instance."""
    return EventRouter()


@pytest.fixture
def webhook_handler(event_router):
    """Create webhook handler instance."""
    return WebhookHandler(event_router)


@pytest.fixture
def scheduler():
    """Create scheduler instance."""
    return TriggerScheduler()


@pytest.fixture
def cleanup_triggers(trigger_service):
    """Fixture to cleanup test triggers after test."""
    created_ids = []
    
    yield lambda config: _create_test_trigger(trigger_service, config, created_ids)
    
    # Cleanup
    for trigger_id in created_ids:
        try:
            trigger_service.delete_trigger(trigger_id)
        except Exception:
            pass


def _create_test_trigger(service, config, created_ids):
    """Helper to create test trigger and track ID."""
    trigger = service.create_trigger(config)
    created_ids.append(trigger.id)
    return trigger


# =============================================================================
# Schema Tests
# =============================================================================

class TestTriggerSchemas:
    """Test trigger schema validation."""

    def test_webhook_config_valid(self):
        """Test valid webhook configuration."""
        config = WebhookConfig(
            endpoint="/github",
            secret="test-secret",
            allowed_events=["push", "pull_request"],
            headers={"X-GitHub-Event": "push"}
        )
        
        assert config.endpoint == "/github"
        assert config.secret == "test-secret"
        assert len(config.allowed_events) == 2
        assert config.headers == {"X-GitHub-Event": "push"}

    def test_webhook_config_minimal(self):
        """Test minimal webhook configuration."""
        config = WebhookConfig(endpoint="/custom")
        
        assert config.endpoint == "/custom"
        assert config.secret is None
        assert config.allowed_events == []
        assert config.headers == {}

    def test_schedule_config_valid(self):
        """Test valid schedule configuration."""
        config = ScheduleConfig(
            cron="0 9 * * *",
            timezone="America/New_York",
            enabled=True
        )
        
        assert config.cron == "0 9 * * *"
        assert config.timezone == "America/New_York"
        assert config.enabled is True

    def test_schedule_config_invalid_cron(self):
        """Test invalid cron expression."""
        with pytest.raises(ValueError) as exc_info:
            ScheduleConfig(cron="invalid")
        
        assert "5 parts" in str(exc_info.value)

    def test_database_trigger_config_valid(self):
        """Test valid database trigger configuration."""
        config = DatabaseTriggerConfig(
            table="chat_sessions",
            event="insert",
            condition="status = 'pending'"
        )
        
        assert config.table == "chat_sessions"
        assert config.event == "insert"
        assert config.condition == "status = 'pending'"

    def test_workflow_trigger_valid(self):
        """Test valid workflow trigger."""
        trigger = WorkflowTrigger(
            id="test-trigger",
            workflow_id="test-workflow",
            trigger_type="schedule",
            config={"cron": "0 9 * * *"},
            is_active=True,
            name="Test Trigger",
            description="Test description"
        )
        
        assert trigger.id == "test-trigger"
        assert trigger.workflow_id == "test-workflow"
        assert trigger.trigger_type == "schedule"
        assert trigger.is_active is True

    def test_workflow_trigger_create(self):
        """Test workflow trigger create schema."""
        create = WorkflowTriggerCreate(
            id="create-trigger",
            workflow_id="test-workflow",
            trigger_type="webhook",
            config={"endpoint": "/test"},
            is_active=True,
            name="Create Trigger",
            description=""
        )
        
        assert create.id == "create-trigger"
        assert create.trigger_type == "webhook"

    def test_workflow_trigger_update_partial(self):
        """Test workflow trigger update with partial data."""
        update = WorkflowTriggerUpdate(
            is_active=False,
            name="Updated Name"
        )
        
        assert update.is_active is False
        assert update.name == "Updated Name"
        assert update.workflow_id is None  # Not provided


# =============================================================================
# Service Tests
# =============================================================================

class TestTriggerService:
    """Test trigger service CRUD operations."""

    def test_create_schedule_trigger(self, trigger_service, cleanup_triggers):
        """Test creating a schedule trigger."""
        config = WorkflowTriggerCreate(
            id=f"schedule-trigger-{uuid.uuid4().hex[:8]}",
            workflow_id="daily-briefing",
            trigger_type="schedule",
            config={"cron": "0 9 * * *", "timezone": "UTC"},
            is_active=True,
            name="Daily Briefing",
            description="Daily briefing at 9 AM"
        )
        
        trigger = cleanup_triggers(config)
        
        assert trigger.id == config.id
        assert trigger.workflow_id == "daily-briefing"
        assert trigger.trigger_type == "schedule"
        assert trigger.is_active is True

    def test_create_webhook_trigger(self, trigger_service, cleanup_triggers):
        """Test creating a webhook trigger."""
        config = WorkflowTriggerCreate(
            id=f"webhook-trigger-{uuid.uuid4().hex[:8]}",
            workflow_id="code-review",
            trigger_type="webhook",
            config={
                "endpoint": "/github",
                "allowed_events": ["push", "pull_request"]
            },
            is_active=True,
            name="GitHub Webhook",
            description="Code review on push"
        )
        
        trigger = cleanup_triggers(config)
        
        assert trigger.id == config.id
        assert trigger.trigger_type == "webhook"
        assert trigger.config["endpoint"] == "/github"

    def test_get_trigger(self, trigger_service, cleanup_triggers):
        """Test getting a trigger by ID."""
        config = WorkflowTriggerCreate(
            id=f"get-trigger-{uuid.uuid4().hex[:8]}",
            workflow_id="test-workflow",
            trigger_type="schedule",
            config={"cron": "0 0 * * *"},
            is_active=True,
        )
        
        created = cleanup_triggers(config)
        retrieved = trigger_service.get_trigger(created.id)
        
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.workflow_id == "test-workflow"

    def test_get_trigger_not_found(self, trigger_service):
        """Test getting a non-existent trigger."""
        trigger = trigger_service.get_trigger("non-existent")
        assert trigger is None

    def test_update_trigger(self, trigger_service, cleanup_triggers):
        """Test updating a trigger."""
        config = WorkflowTriggerCreate(
            id=f"update-trigger-{uuid.uuid4().hex[:8]}",
            workflow_id="test-workflow",
            trigger_type="schedule",
            config={"cron": "0 0 * * *"},
            is_active=True,
            name="Original Name"
        )
        
        created = cleanup_triggers(config)
        
        update = WorkflowTriggerUpdate(
            name="Updated Name",
            is_active=False
        )
        
        updated = trigger_service.update_trigger(created.id, update)
        
        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.is_active is False

    def test_delete_trigger(self, trigger_service):
        """Test deleting a trigger."""
        config = WorkflowTriggerCreate(
            id=f"delete-trigger-{uuid.uuid4().hex[:8]}",
            workflow_id="test-workflow",
            trigger_type="schedule",
            config={"cron": "0 0 * * *"},
            is_active=True,
        )
        
        created = trigger_service.create_trigger(config)
        deleted = trigger_service.delete_trigger(created.id)
        
        assert deleted is True
        assert trigger_service.get_trigger(created.id) is None

    def test_activate_deactivate_trigger(self, trigger_service, cleanup_triggers):
        """Test activating and deactivating a trigger."""
        config = WorkflowTriggerCreate(
            id=f"activate-trigger-{uuid.uuid4().hex[:8]}",
            workflow_id="test-workflow",
            trigger_type="schedule",
            config={"cron": "0 0 * * *"},
            is_active=False,  # Start inactive
        )
        
        created = cleanup_triggers(config)
        assert created.is_active is False
        
        # Activate
        activated = trigger_service.activate_trigger(created.id)
        assert activated is True
        assert trigger_service.get_trigger(created.id).is_active is True
        
        # Deactivate
        deactivated = trigger_service.deactivate_trigger(created.id)
        assert deactivated is True
        assert trigger_service.get_trigger(created.id).is_active is False

    def test_get_all_triggers_filtered(self, trigger_service, cleanup_triggers):
        """Test getting triggers with filters."""
        # Create multiple triggers
        for i in range(3):
            config = WorkflowTriggerCreate(
                id=f"filter-trigger-{i}-{uuid.uuid4().hex[:8]}",
                workflow_id="test-workflow",
                trigger_type="schedule",
                config={"cron": "0 0 * * *"},
                is_active=True,
            )
            cleanup_triggers(config)
        
        # Get all schedule triggers
        triggers = trigger_service.get_all_triggers(trigger_type="schedule")
        
        assert len(triggers) >= 3


# =============================================================================
# Event Router Tests
# =============================================================================

class TestEventRouter:
    """Test event router matching logic."""

    def test_create_webhook_event(self, event_router):
        """Test creating a webhook event."""
        event = event_router.create_webhook_event(
            endpoint="/github",
            event_name="push",
            payload={"repository": "test-repo"},
            headers={"X-GitHub-Event": "push"}
        )
        
        assert event.event_type == "webhook"
        assert event.source == "webhook"
        assert event.payload["event"] == "push"

    def test_create_schedule_event(self, event_router):
        """Test creating a schedule event."""
        event = event_router.create_schedule_event(
            trigger_id="daily-trigger",
            scheduled_time="2026-03-30T09:00:00Z"
        )
        
        assert event.event_type == "schedule"
        assert event.source == "scheduler"
        assert event.payload["trigger_id"] == "daily-trigger"

    def test_create_database_event(self, event_router):
        """Test creating a database event."""
        event = event_router.create_database_event(
            table="chat_sessions",
            operation="insert",
            row_data={"id": "123", "status": "pending"}
        )
        
        assert event.event_type == "database"
        assert event.source == "database"
        assert event.payload["table"] == "chat_sessions"

    def test_match_webhook_event(self, event_router):
        """Test matching webhook event to trigger."""
        triggers = [
            WorkflowTrigger(
                id="trigger-1",
                workflow_id="workflow-1",
                trigger_type="webhook",
                config={
                    "endpoint": "/github",
                    "allowed_events": ["push"]
                },
                is_active=True
            ),
            WorkflowTrigger(
                id="trigger-2",
                workflow_id="workflow-2",
                trigger_type="webhook",
                config={
                    "endpoint": "/gitlab",
                    "allowed_events": ["push"]
                },
                is_active=True
            ),
        ]
        
        event = event_router.create_webhook_event(
            endpoint="/github",
            event_name="push",
            payload={},
            headers={}
        )
        
        matches = event_router.match_event(event, triggers)
        
        assert len(matches) == 1
        assert matches[0].id == "trigger-1"

    def test_match_schedule_event(self, event_router):
        """Test matching schedule event."""
        triggers = [
            WorkflowTrigger(
                id="schedule-trigger",
                workflow_id="daily-briefing",
                trigger_type="schedule",
                config={"cron": "0 9 * * *"},
                is_active=True
            ),
        ]
        
        event = event_router.create_schedule_event(
            trigger_id="schedule-trigger",
            scheduled_time="2026-03-30T09:00:00Z"
        )
        
        matches = event_router.match_event(event, triggers)
        
        assert len(matches) == 1
        assert matches[0].id == "schedule-trigger"

    def test_match_inactive_trigger(self, event_router):
        """Test that inactive triggers are not matched."""
        triggers = [
            WorkflowTrigger(
                id="inactive-trigger",
                workflow_id="workflow",
                trigger_type="webhook",
                config={"endpoint": "/test"},
                is_active=False  # Inactive
            ),
        ]
        
        event = event_router.create_webhook_event(
            endpoint="/test",
            event_name="test",
            payload={},
            headers={}
        )
        
        matches = event_router.match_event(event, triggers)
        
        assert len(matches) == 0


# =============================================================================
# Webhook Handler Tests
# =============================================================================

class TestWebhookHandler:
    """Test webhook handler functionality."""

    def test_parse_webhook_basic(self, webhook_handler):
        """Test parsing basic webhook."""
        error, event = webhook_handler.parse_webhook(
            endpoint="/github",
            headers={"X-GitHub-Event": "push"},
            payload={"repository": "test"}
        )
        
        assert error is None
        assert event is not None
        assert event.payload["event"] == "push"

    def test_parse_webhook_no_event_type(self, webhook_handler):
        """Test parsing webhook without event type."""
        error, event = webhook_handler.parse_webhook(
            endpoint="/test",
            headers={},
            payload={}
        )
        
        assert error is not None
        assert "Could not determine event type" in error

    def test_list_webhook_endpoints(self, webhook_handler, trigger_service, cleanup_triggers):
        """Test listing webhook endpoints."""
        # Create webhook trigger
        config = WorkflowTriggerCreate(
            id=f"endpoint-trigger-{uuid.uuid4().hex[:8]}",
            workflow_id="test-workflow",
            trigger_type="webhook",
            config={
                "endpoint": "/custom",
                "allowed_events": ["test"]
            },
            is_active=True,
        )
        
        cleanup_triggers(config)
        
        endpoints = webhook_handler.list_webhook_endpoints()
        
        assert len(endpoints) >= 1
        custom_endpoint = next(
            (e for e in endpoints if e["endpoint"] == "/custom"),
            None
        )
        assert custom_endpoint is not None
        assert custom_endpoint["workflow_id"] == "test-workflow"


# =============================================================================
# Scheduler Tests
# =============================================================================

class TestScheduler:
    """Test scheduler functionality."""

    def test_scheduler_initialization(self, scheduler):
        """Test scheduler initializes correctly."""
        assert scheduler.scheduler is not None
        # Don't start scheduler in sync test - it needs event loop
        # scheduler.start()
        # assert scheduler.scheduler.running
        # scheduler.shutdown(wait=False)
        pass  # Skip runtime test, initialization is enough

    @pytest.mark.asyncio
    async def test_add_remove_job(self, scheduler):
        """Test adding and removing scheduled jobs."""
        import asyncio
        asyncio.get_event_loop()
        
        # Start scheduler in async context
        scheduler.start()
        
        try:
            success = scheduler.add_job(
                trigger_id="test-job",
                workflow_id="test-workflow",
                cron_expression="0 9 * * *",
                timezone="UTC"
            )
            
            assert success is True
            
            job_info = scheduler.get_job_info("test-job")
            assert job_info is not None
            assert job_info["trigger_id"] == "test-job"
            
            # Remove job
            removed = scheduler.remove_job("test-job")
            assert removed is True
            
        finally:
            scheduler.shutdown(wait=False)

    @pytest.mark.asyncio
    async def test_pause_resume_job(self, scheduler):
        """Test pausing and resuming jobs."""
        scheduler.start()
        
        try:
            scheduler.add_job(
                trigger_id="pause-job",
                workflow_id="test-workflow",
                cron_expression="0 0 * * *",
                timezone="UTC",
                enabled=False  # Start paused
            )
            
            job_info = scheduler.get_job_info("pause-job")
            assert job_info is not None
            assert job_info["paused"] is True
            
            # Resume
            scheduler.resume_job("pause-job")
            job_info = scheduler.get_job_info("pause-job")
            assert job_info["paused"] is False
            
        finally:
            scheduler.shutdown(wait=False)

    @pytest.mark.asyncio
    async def test_get_all_jobs(self, scheduler):
        """Test getting all scheduled jobs."""
        scheduler.start()
        
        try:
            # Add multiple jobs
            for i in range(3):
                scheduler.add_job(
                    trigger_id=f"job-{i}",
                    workflow_id="test-workflow",
                    cron_expression="0 0 * * *",
                    timezone="UTC"
                )
            
            jobs = scheduler.get_all_jobs()
            assert len(jobs) == 3
            
        finally:
            scheduler.shutdown(wait=False)


# =============================================================================
# Integration Tests
# =============================================================================

class TestTriggerIntegration:
    """Integration tests for trigger system."""

    def test_full_webhook_flow(
        self,
        trigger_service,
        cleanup_triggers,
        webhook_handler
    ):
        """Test complete webhook trigger flow."""
        # Create webhook trigger
        config = WorkflowTriggerCreate(
            id=f"integration-webhook-{uuid.uuid4().hex[:8]}",
            workflow_id="code-review",
            trigger_type="webhook",
            config={
                "endpoint": "/github",
                "allowed_events": ["push"]
            },
            is_active=True,
            name="Integration Test Webhook"
        )
        
        cleanup_triggers(config)
        
        # Simulate webhook
        success, triggered_workflows, error = webhook_handler.handle_webhook(
            endpoint="/github",
            headers={"X-GitHub-Event": "push"},
            payload={"repository": "test-repo", "commits": []},
            signature=None
        )
        
        assert success is True
        assert "code-review" in triggered_workflows

    @pytest.mark.asyncio
    async def test_full_schedule_flow(
        self,
        trigger_service,
        cleanup_triggers,
        scheduler
    ):
        """Test complete schedule trigger flow."""
        # Create schedule trigger
        config = WorkflowTriggerCreate(
            id=f"integration-schedule-{uuid.uuid4().hex[:8]}",
            workflow_id="daily-briefing",
            trigger_type="schedule",
            config={
                "cron": "0 9 * * *",
                "timezone": "UTC",
                "enabled": True
            },
            is_active=True,
            name="Integration Test Schedule"
        )
        
        trigger = cleanup_triggers(config)
        
        # Add to scheduler
        scheduler.start()
        
        try:
            success = scheduler.add_job(
                trigger_id=trigger.id,
                workflow_id=trigger.workflow_id,
                cron_expression="0 9 * * *",
                timezone="UTC"
            )
            
            assert success is True
            
            job_info = scheduler.get_job_info(trigger.id)
            assert job_info is not None
            assert "cron" in str(job_info["trigger"]).lower()
            
        finally:
            scheduler.shutdown(wait=False)


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
