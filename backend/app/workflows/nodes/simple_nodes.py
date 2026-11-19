"""
Simple workflow nodes for basic workflow execution.

These nodes demonstrate the basic pattern of stateless state transformation
in LangGraph workflows.
"""

import time
import logging
from datetime import datetime, UTC
from ..state.workflow_state import WorkflowState, RunMetadata

logger = logging.getLogger(__name__)


def _check_cancellation(state: WorkflowState) -> bool:
    """
    Check if workflow has been cancelled.

    Args:
        state: Current workflow state

    Returns:
        True if cancelled, False otherwise
    """
    try:
        from ..utils.cancellation import is_workflow_cancelled
        return is_workflow_cancelled(state["workflow_id"])
    except Exception as e:
        logger.warning(f"Failed to check cancellation | workflow_id={state['workflow_id']} | error={str(e)}")
        return False


def _create_cancelled_response(state: WorkflowState, elapsed: int = 0) -> dict:
    """
    Create response for cancelled workflow.

    Args:
        state: Current workflow state
        elapsed: Elapsed time in seconds

    Returns:
        State updates with cancelled status
    """
    now = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return {
        "execution_result": {
            "result": "Cancelled",
            "elapsed_seconds": elapsed,
            "completed_at": now
        },
        "current_step": None,
        "metadata": RunMetadata(
            workflow_id=state["workflow_id"],
            template_id=state["template_id"],
            started_at=getattr(state["metadata"], "started_at", None),
            completed_at=now,
            status="cancelled",
            error="Cancelled by user",
            config=state["metadata"].config if state["metadata"] and hasattr(state["metadata"], "config") else None,
            tags=state["metadata"].tags if state["metadata"] and hasattr(state["metadata"], "tags") else None
        )
    }


def plan_node(state: WorkflowState) -> dict:
    """
    Simple planner node that prepares workflow execution.

    This node:
    1. Logs the workflow start
    2. Sets the current step to 'executor'
    3. Updates metadata status to 'running'

    Args:
        state: Current workflow state

    Returns:
        State updates with new step and metadata
    """
    now = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    # Preserve config and tags from incoming metadata
    incoming_metadata = state.get("metadata")
    config = incoming_metadata.config if incoming_metadata and hasattr(incoming_metadata, "config") else None
    tags = incoming_metadata.tags if incoming_metadata and hasattr(incoming_metadata, "tags") else None

    return {
        "messages": state["messages"],
        "current_step": "executor",
        "execution_result": {"plan": "Execute workflow"},
        "metadata": RunMetadata(
            workflow_id=state["workflow_id"],
            template_id=state["template_id"],
            started_at=now,
            status="running",
            config=config,
            tags=tags
        )
    }


def execute_node(state: WorkflowState) -> dict:
    """
    Simple executor node that completes the workflow.

    This node:
    1. Executes the workflow (placeholder for real logic)
    2. Marks workflow as completed
    3. Sets completion timestamp

    If config has 'delay_seconds', it will sleep for testing purposes.
    Checks for cancellation during long-running operations.

    Args:
        state: Current workflow state

    Returns:
        State updates with completion status
    """
    # Check if we should add a delay (for testing stop button)
    # Access config from metadata
    metadata = state.get("metadata")
    delay = 0
    if metadata and hasattr(metadata, "config") and metadata.config:
        delay = metadata.config.get("delay_seconds", 0)

    if delay:
        logger.info(f"⏳ Long-running test workflow: sleeping for {delay} seconds...")
        # Sleep in 1-second increments, checking for cancellation each time
        for elapsed in range(delay):
            # Check for cancellation before each sleep interval
            cancelled = _check_cancellation(state)
            logger.debug(f"🔍 Cancellation check at {elapsed}s | cancelled={cancelled}")
            if cancelled:
                logger.warning(f"⏹️ Workflow cancelled during execution (at {elapsed}s)")
                return _create_cancelled_response(state, elapsed)
            time.sleep(1)
        
        # Final cancellation check after sleep completes
        logger.debug(f"🔍 Final cancellation check after {delay}s sleep")
        if _check_cancellation(state):
            logger.warning(f"⏹️ Workflow cancelled during execution (at {delay}s)")
            return _create_cancelled_response(state, delay)

    now = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    # Create output based on workflow type
    outputs = {}
    
    # Check workflow type from template_id to provide appropriate output
    template_id = state.get("template_id", "unknown")

    if "hello" in template_id.lower():
        outputs["greeting"] = "Hello, World!"
        outputs["message"] = "This is a simple test workflow that confirms the system is working."
        outputs["status"] = "success"
    elif "approval" in template_id.lower():
        outputs["message"] = "This workflow requires human approval before proceeding."
        outputs["approval_status"] = "pending"
        outputs["next_step"] = "Waiting for user approval"
    else:
        # Default test output
        outputs["result"] = "Workflow executed successfully"
        outputs["template_id"] = template_id
        outputs["test_status"] = "passed"

    return {
        "execution_result": {
            "result": "Workflow executed successfully",
            "completed_at": now,
            "delay_seconds": delay if delay else None
        },
        "outputs": outputs,  # Add outputs for display in UI
        "current_step": None,
        "metadata": RunMetadata(
            workflow_id=state["workflow_id"],
            template_id=state["template_id"],
            started_at=getattr(state["metadata"], "started_at", None),
            completed_at=now,
            status="completed",
            config=metadata.config if metadata and hasattr(metadata, "config") else None,
            tags=metadata.tags if metadata and hasattr(metadata, "tags") else None
        )
    }
