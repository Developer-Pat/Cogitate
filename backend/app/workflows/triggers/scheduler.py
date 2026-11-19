"""
Scheduler for workflow triggers.

Uses APScheduler to schedule workflow executions based on cron expressions.

Features:
- Cron-based scheduling
- Dynamic job management (add/remove/update)
- Timezone support
- Job persistence
- Execution tracking

Usage:
    scheduler = TriggerScheduler()
    scheduler.start()
    
    # Add scheduled trigger
    scheduler.add_job(
        trigger_id="daily-briefing",
        workflow_id="daily-briefing-workflow",
        cron_expression="0 9 * * *",
        timezone="UTC"
    )
    
    # Remove job
    scheduler.remove_job("daily-briefing")
"""

import logging
from typing import Dict, Any, Optional, List, Callable, TYPE_CHECKING
from datetime import datetime, UTC
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]
from apscheduler.jobstores.memory import MemoryJobStore  # type: ignore[import-untyped]
from apscheduler.executors.asyncio import AsyncIOExecutor  # type: ignore[import-untyped]
import asyncio

from app.domain.workflows.services.trigger_service import TriggerService
from app.workflows.triggers.event_router import EventRouter

if TYPE_CHECKING:  # the annotation on `_build_trigger_state` only
    from app.workflows.state.workflow_state import WorkflowState


def _build_trigger_state(
    execution_id: str,
    template_id: str,
    trigger_id: str,
    template_config: Optional[Dict[str, Any]] = None,
) -> "WorkflowState":
    """The state a SCHEDULED run starts with — the scheduler's own door into a workflow.

    **Extracted so the seam that broke stays testable.** This is the shape whose ``config`` channel
    used to be hardcoded ``None``, which made every scheduled monitor run resolve zero feeds and
    report a clean cycle. A sealed dict inside an async method could not be asserted on; this can.

    ``template_config`` is the template's own config, read by the ONE reader both doors now share
    (``app.workflows.template_config.load_template_config``). It is copied, never aliased: the graph
    mutates state, and the caller's dict is the template's.
    """
    from langchain_core.messages import HumanMessage

    from ..state.workflow_state import RunMetadata, WorkflowState

    state: WorkflowState = {
        "workflow_id": execution_id,
        "template_id": template_id,
        "messages": [HumanMessage(content=f"Scheduled run: {trigger_id}")],
        "inputs": {"trigger_id": trigger_id},
        "config": dict(template_config or {}),
        "current_step": None,
        "execution_result": None,
        "outputs": {},
        "approval_required": False,
        "approval_status": None,
        "metadata": RunMetadata(workflow_id=execution_id, template_id=template_id),
        "tool_calls_history": [],
        "tool_loop_count": 0,
        "pending_tool_calls": [],
        "current_agent_step": None,
    }
    return state

logger = logging.getLogger(__name__)


# Global scheduler instance
_scheduler_instance: Optional["TriggerScheduler"] = None


def get_scheduler() -> "TriggerScheduler":
    """
    Get or create the global scheduler instance.
    
    Returns:
        TriggerScheduler instance
    """
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = TriggerScheduler()
    return _scheduler_instance


class TriggerScheduler:
    """
    Scheduler for workflow triggers.
    
    This class handles:
    1. APScheduler initialization and configuration
    2. Adding/removing scheduled jobs
    3. Cron expression parsing
    4. Job execution callbacks
    5. Scheduler lifecycle management
    """
    
    def __init__(self) -> None:
        """Initialize trigger scheduler."""
        self.trigger_service = TriggerService()
        self.event_router = EventRouter()
        
        # Configure APScheduler
        jobstores = {
            'default': MemoryJobStore()
        }
        
        executors = {
            'default': AsyncIOExecutor()
        }
        
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            timezone='UTC'
        )
        
        self._job_callbacks: Dict[str, Callable] = {}
        
        logger.info("✅ TriggerScheduler initialized")
    
    def start(self):
        """
        Start the scheduler.
        
        This should be called during application startup.
        """
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("✅ TriggerScheduler started")

    def schedule_once(
        self,
        job_id: str,
        callback: Callable,
        delay_seconds: int = 300,
    ) -> None:
        """Schedule a ONE-SHOT job after a relative delay.

        THE STARTUP-CLEAN SCHEDULE (2026-08-24, the user's call):
        cron expressions are ABSOLUTE times; '5 minutes after
        startup' is RELATIVE — the APScheduler DateTrigger (one
        shot at now+delay) is the fit. The startup path only
        REGISTERS the job; the deep work runs later, keeping the
        boot uncluttered.
        """
        from datetime import datetime, timedelta, timezone
        run_date = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        self.scheduler.add_job(
            callback,
            trigger="date",
            run_date=run_date,
            id=job_id,
            replace_existing=True,
        )
        logger.info(
            "✅ Scheduled one-shot '%s' in %ss (run at %s)",
            job_id, delay_seconds, run_date.isoformat(timespec="seconds"),
        )
    
    def shutdown(self, wait: bool = True):
        """
        Shutdown the scheduler.
        
        This should be called during application shutdown.
        
        Args:
            wait: Wait for running jobs to complete
        """
        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            logger.info("✅ TriggerScheduler shutdown complete")
    
    def add_job(
        self,
        trigger_id: str,
        workflow_id: str,
        cron_expression: str,
        timezone: str = "UTC",
        enabled: bool = True,
        callback: Optional[Callable] = None
    ):
        """
        Add a scheduled job.
        
        Args:
            trigger_id: Unique trigger ID (used as job ID)
            workflow_id: Workflow ID to execute
            cron_expression: Cron expression (5 parts: minute hour day month weekday)
            timezone: Timezone for cron execution
            enabled: Whether job is enabled
            callback: Optional callback function for execution
        
        Returns:
            True if job added successfully
        """
        try:
            # Parse cron expression
            cron_parts = cron_expression.strip().split()
            
            if len(cron_parts) != 5:
                logger.error(f"❌ Invalid cron expression: {cron_expression}")
                return False
            
            minute, hour, day, month, day_of_week = cron_parts
            
            # Create cron trigger
            trigger = CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
                timezone=timezone
            )
            
            # Create or use callback
            if callback is None:
                callback = self._create_default_callback(trigger_id, workflow_id)
            
            # Store callback
            self._job_callbacks[trigger_id] = callback
            
            # Add job to scheduler
            self.scheduler.add_job(
                callback,
                trigger=trigger,
                id=trigger_id,
                name=f"Scheduled workflow: {workflow_id}",
                replace_existing=True,
                misfire_grace_time=60  # 1 minute grace time
            )
            
            if enabled:
                logger.info(
                    f"✅ Added scheduled job: {trigger_id} -> {workflow_id} "
                    f"(cron: {cron_expression} {timezone})"
                )
            else:
                # Pause if not enabled
                self.pause_job(trigger_id)
                logger.info(
                    f"✅ Added paused job: {trigger_id} -> {workflow_id}"
                )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to add scheduled job {trigger_id}: {e}")
            return False
    
    def add_maintenance_job(
        self, job_id: str, cron_expression: str, callback: Callable, description: str = ""
    ) -> bool:
        """Add a NON-workflow job — the maintenance kind (retention and its siblings).

        Same trigger machinery as a workflow trigger, deliberately without the workflow
        bookkeeping: a maintenance job has no workflow to resolve, no trigger row, and nothing to
        record in the execution history. It must never fire a workflow.
        """
        try:
            parts = cron_expression.strip().split()
            if len(parts) != 5:
                logger.error(f"❌ Invalid cron expression for maintenance job {job_id}: {cron_expression}")
                return False
            minute, hour, day, month, day_of_week = parts
            self.scheduler.add_job(
                callback,
                trigger=CronTrigger(
                    minute=minute, hour=hour, day=day, month=month,
                    day_of_week=day_of_week, timezone="UTC",
                ),
                id=job_id,
                name=description or f"Maintenance: {job_id}",
                replace_existing=True,
                misfire_grace_time=600,
            )
            logger.info(f"✅ Maintenance job scheduled: {job_id} ({cron_expression} UTC)")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to add maintenance job {job_id}: {e}")
            return False

    def _create_default_callback(
        self,
        trigger_id: str,
        workflow_id: str
    ) -> Callable:
        """
        Create default callback for scheduled execution.
        
        Args:
            trigger_id: Trigger ID
            workflow_id: Workflow ID
        
        Returns:
            Callback function
        """
        # Return async function
        def callback():
            """Wrapper to run the async execution (APScheduler sync API)."""
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            loop.run_until_complete(self.execute_scheduled_workflow(
                trigger_id, workflow_id
            ))

        return callback

    async def execute_scheduled_workflow(
        self, trigger_id: str, workflow_id: str
    ) -> None:
        """Execute a scheduled workflow (event + match + invoke)."""
        logger.info(f"⏰ Scheduled trigger fired: {trigger_id} -> {workflow_id}")

        # Create schedule event
        self.event_router.create_schedule_event(
            trigger_id=trigger_id,
            scheduled_time=datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        )

        # Get matching triggers
        triggers = self.trigger_service.get_active_triggers_by_type("schedule")
        matching_triggers = [
            t for t in triggers
            if t.id == trigger_id and t.workflow_id == workflow_id
        ]

        if matching_triggers:
            logger.info(
                f"✅ Scheduled trigger matched: {trigger_id} -> {workflow_id}"
            )
            await self._execute_triggered_workflow(trigger_id, workflow_id)
        else:
            logger.warning(
                f"⚠️ Scheduled trigger {trigger_id} not found or inactive"
            )

    async def _execute_triggered_workflow(
        self, trigger_id: str, workflow_id: str
    ) -> None:
        """Actually run the workflow a scheduled trigger fires.

        Previously the scheduler only logged "matched" — the event
        was created and discarded, and the graph was never invoked
        (wired-but-idle, found 2026-08-10 during live testing).
        This mirrors the API path: compile the graph, invoke it,
        and record execution identity.
        """
        import uuid
        from ..api.workflow_router import compile_workflow
        from ..state.workflow_state import WorkflowState
        from ..template_config import load_template_config
        from ..execution_history import (
            record_execution_start,
            record_execution_complete,
        )

        execution_id = f"wf-{uuid.uuid4().hex[:12]}"
        thread_id = execution_id

        record_execution_start(
            execution_id=execution_id,
            template_id=workflow_id,
            input_data={"trigger_id": trigger_id},
            agent_id=None,
        )

        # THE TEMPLATE'S CONFIG, READ HERE (2026-10-13). This path used to seed `"config": None`,
        # and the monitor family reads its FEEDS from that channel — so every scheduled run
        # resolved zero feeds, fetched nothing and reported a clean cycle (`Items: 0 · Errors: 0`)
        # for weeks. It stayed invisible because a monitor's failures are declared TOLERANT and
        # never mark a run. The API path had the same channel and did load it; one reader now
        # serves both (`app/workflows/template_config.py`), because the config a run is seeded with
        # must not depend on which door it came through.
        template_config, _template_tags = load_template_config(workflow_id)

        try:
            compiled_graph = compile_workflow(workflow_id)
            initial_state: WorkflowState = _build_trigger_state(
                execution_id=execution_id,
                template_id=workflow_id,
                trigger_id=trigger_id,
                template_config=template_config,
            )
            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": "",
                }
            }
            result = compiled_graph.invoke(initial_state, config)
            record_execution_complete(
                execution_id,
                status="completed",
                output_data=result if isinstance(result, dict) else None,
            )
            logger.info(
                f"✅ Scheduled workflow executed: {trigger_id} -> "
                f"{workflow_id} ({execution_id})"
            )
        except Exception as e:
            record_execution_complete(
                execution_id,
                status="failed",
                error_message=str(e),
            )
            logger.error(
                f"❌ Scheduled workflow {trigger_id} failed: {e}",
                exc_info=True,
            )

    def remove_job(self, trigger_id: str) -> bool:
        """
        Remove a scheduled job.
        
        Args:
            trigger_id: Trigger ID (job ID)
        
        Returns:
            True if removed successfully
        """
        try:
            self.scheduler.remove_job(trigger_id)
            
            # Remove callback
            if trigger_id in self._job_callbacks:
                del self._job_callbacks[trigger_id]
            
            logger.info(f"✅ Removed scheduled job: {trigger_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to remove job {trigger_id}: {e}")
            return False
    
    def pause_job(self, trigger_id: str) -> bool:
        """
        Pause a scheduled job.
        
        Args:
            trigger_id: Trigger ID
        
        Returns:
            True if paused successfully
        """
        try:
            self.scheduler.pause_job(trigger_id)
            logger.info(f"⏸️ Paused scheduled job: {trigger_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to pause job {trigger_id}: {e}")
            return False
    
    def resume_job(self, trigger_id: str) -> bool:
        """
        Resume a paused job.
        
        Args:
            trigger_id: Trigger ID
        
        Returns:
            True if resumed successfully
        """
        try:
            self.scheduler.resume_job(trigger_id)
            logger.info(f"▶️ Resumed scheduled job: {trigger_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to resume job {trigger_id}: {e}")
            return False
    
    def get_job_info(self, trigger_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a scheduled job.

        Args:
            trigger_id: Trigger ID

        Returns:
            Job information or None
        """
        try:
            job = self.scheduler.get_job(trigger_id)

            if not job:
                return None

            # Check if job is paused by looking at scheduler state
            is_paused = job.next_run_time is None and job.trigger is not None

            return {
                "trigger_id": trigger_id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
                "paused": is_paused,
            }
        except Exception as e:
            logger.error(f"❌ Failed to get job info for {trigger_id}: {e}")
            return None

    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """
        Get information about all scheduled jobs.

        Returns:
            List of job information
        """
        jobs = []

        for job in self.scheduler.get_jobs():
            # Check if job is paused
            is_paused = job.next_run_time is None and job.trigger is not None

            jobs.append({
                "trigger_id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
                "paused": is_paused,
            })

        return jobs
    
    def load_triggers_from_database(self):
        """
        Load all active schedule triggers from database and add them to scheduler.
        
        This should be called during application startup.
        """
        triggers = self.trigger_service.get_active_triggers_by_type("schedule")
        
        loaded = 0
        for trigger in triggers:
            config = trigger.config
            
            cron_expression = config.get("cron", "")
            timezone = config.get("timezone", "UTC")
            enabled = config.get("enabled", True)
            
            if not cron_expression:
                logger.warning(f"⚠️ Schedule trigger {trigger.id} missing cron expression")
                continue
            
            success = self.add_job(
                trigger_id=trigger.id,
                workflow_id=trigger.workflow_id,
                cron_expression=cron_expression,
                timezone=timezone,
                enabled=enabled
            )
            
            if success:
                loaded += 1
        
        logger.info(f"✅ Loaded {loaded}/{len(triggers)} schedule triggers from database")
    
    def execute_scheduled_triggers(self):
        """
        Manually execute all scheduled triggers.
        
        This is useful for testing or manual trigger execution.
        
        Returns:
            List of executed trigger IDs
        """
        triggers = self.trigger_service.get_active_triggers_by_type("schedule")
        executed = []
        
        for trigger in triggers:
            logger.info(f"⏰ Manually executing scheduled trigger: {trigger.id}")
            
            # Create and route event
            self.event_router.create_schedule_event(
                trigger_id=trigger.id,
                scheduled_time=datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            )
            
            executed.append(trigger.id)
        
        logger.info(f"✅ Manually executed {len(executed)} scheduled triggers")
        return executed
