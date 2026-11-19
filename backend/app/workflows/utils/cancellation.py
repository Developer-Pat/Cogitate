"""
Workflow cancellation utility functions.

Provides utilities for checking and handling workflow cancellation requests.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def is_workflow_cancelled(thread_id: str) -> bool:
    """
    Check if a workflow has been cancelled.

    This function checks the workflow checkpoint to determine if a cancellation
    request has been made by examining the metadata status.

    Args:
        thread_id: The workflow/thread ID to check

    Returns:
        True if workflow has been cancelled, False otherwise
    """
    try:
        from ..checkpointing.config import CheckpointerManager

        checkpointer = CheckpointerManager.get_checkpointer()
        config = {"configurable": {"thread_id": thread_id}}
        
        # Force a fresh read from the checkpoint
        state = checkpointer.get(config)
        
        logger.debug(f"🔍 Cancellation check | thread_id={thread_id} | state_exists={state is not None}")

        if not state:
            logger.debug(f"⚠️ No checkpoint found for workflow | thread_id={thread_id}")
            return False

        channel_values = state.get("channel_values", {})
        metadata = channel_values.get("metadata", "")

        # Parse metadata string to check status
        metadata_str = str(metadata)
        logger.debug(f"🔍 Checking cancellation | thread_id={thread_id} | metadata={metadata_str[:150] if len(metadata_str) > 150 else metadata_str}")
        
        if "status='cancelled'" in metadata_str:
            logger.warning(f"✅ Workflow cancellation detected | thread_id={thread_id}")
            return True

        return False

    except Exception as e:
        logger.warning(f"Failed to check cancellation status | thread_id={thread_id} | error={str(e)}")
        return False


def get_workflow_status(thread_id: str) -> Optional[str]:
    """
    Get the current status of a workflow.

    Args:
        thread_id: The workflow/thread ID to check

    Returns:
        Status string ('running', 'completed', 'cancelled', 'failed') or None if not found
    """
    try:
        from ..checkpointing.config import CheckpointerManager

        checkpointer = CheckpointerManager.get_checkpointer()
        config = {"configurable": {"thread_id": thread_id}}
        state = checkpointer.get(config)

        if not state:
            return None

        channel_values = state.get("channel_values", {})
        metadata = channel_values.get("metadata", "")

        # Parse metadata string to extract status
        metadata_str = str(metadata)
        if "status='running'" in metadata_str:
            return "running"
        elif "status='completed'" in metadata_str:
            return "completed"
        elif "status='cancelled'" in metadata_str:
            return "cancelled"
        elif "status='failed'" in metadata_str:
            return "failed"

        return "unknown"

    except Exception as e:
        logger.warning(f"Failed to get workflow status | thread_id={thread_id} | error={str(e)}")
        return None
