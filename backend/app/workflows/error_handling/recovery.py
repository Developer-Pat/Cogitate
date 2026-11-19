"""
Recovery workflows for error scenarios.

Provides:
- RecoveryStrategy: Strategies for handling failures
- RecoveryWorkflow: Predefined recovery workflows

Supports:
- Retry with exponential backoff
- Fallback to alternative agent
- Graceful degradation
- Error notification
"""

from typing import Any, Dict, Optional
from datetime import datetime, UTC
from enum import Enum


class RecoveryStrategy(Enum):
    """
    Strategies for workflow recovery.

    Members:
        RETRY: Retry failed operation with backoff
        FALLBACK: Use fallback agent/configuration
        DEGRADE: Continue with reduced functionality
        NOTIFY: Notify and pause for human intervention
        ABORT: Abort workflow gracefully
    """
    RETRY = "retry"
    FALLBACK = "fallback"
    DEGRADE = "degrade"
    NOTIFY = "notify"
    ABORT = "abort"


class RecoveryWorkflow:
    """
    Predefined recovery workflows for error scenarios.

    Provides:
    - Error handling templates
    - Recovery execution logic
    - State management during recovery

    Usage:
        ```python
        # Execute recovery
        result = RecoveryWorkflow.execute_recovery(
            strategy=RecoveryStrategy.RETRY,
            error=exception,
            state=current_state,
            context={"max_retries": 3}
        )
        ```
    """

    @classmethod
    def execute_recovery(
        cls,
        strategy: RecoveryStrategy,
        error: Exception,
        state: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute recovery strategy.

        Args:
            strategy: Recovery strategy to use
            error: Exception that triggered recovery
            state: Current workflow state
            context: Additional context for recovery

        Returns:
            Updated state after recovery attempt
        """
        context = context or {}

        if strategy == RecoveryStrategy.RETRY:
            return cls._retry_recovery(error, state, context)
        elif strategy == RecoveryStrategy.FALLBACK:
            return cls._fallback_recovery(error, state, context)
        elif strategy == RecoveryStrategy.DEGRADE:
            return cls._degraded_recovery(error, state, context)
        elif strategy == RecoveryStrategy.NOTIFY:
            return cls._notify_recovery(error, state, context)
        elif strategy == RecoveryStrategy.ABORT:
            return cls._abort_recovery(error, state, context)
        else:
            raise ValueError(f"Unknown recovery strategy: {strategy}")

    @classmethod
    def _retry_recovery(
        cls,
        error: Exception,
        state: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Retry recovery - prepare state for retry.

        Context:
            - retry_count: Number of retries attempted
            - max_retries: Maximum retries allowed
        """
        retry_count = context.get("retry_count", 0)
        max_retries = context.get("max_retries", 3)

        if retry_count >= max_retries:
            # Max retries exceeded - abort
            return cls._abort_recovery(error, state, {
                **context,
                "reason": f"Max retries ({max_retries}) exceeded"
            })

        # Prepare for retry
        updated_state = state.copy()
        metadata = updated_state.get("metadata", {})

        # Update metadata
        if hasattr(metadata, 'status'):
            metadata.status = "retrying"
            metadata.error = str(error)
        else:
            if isinstance(metadata, dict):
                metadata["status"] = "retrying"
                metadata["error"] = str(error)

        updated_state["metadata"] = metadata
        updated_state["recovery_attempt"] = retry_count + 1

        return updated_state

    @classmethod
    def _fallback_recovery(
        cls,
        error: Exception,
        state: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Fallback recovery - switch to fallback agent/config.

        Context:
            - fallback_agent_id: ID of fallback agent
            - fallback_config: Alternative configuration
        """
        fallback_agent_id = context.get("fallback_agent_id")
        fallback_config = context.get("fallback_config")

        updated_state = state.copy()
        metadata = updated_state.get("metadata", {})

        # Update metadata
        if hasattr(metadata, 'status'):
            metadata.status = "using_fallback"
            metadata.error = str(error)
            metadata.fallback_used = True
        else:
            if isinstance(metadata, dict):
                metadata["status"] = "using_fallback"
                metadata["error"] = str(error)
                metadata["fallback_used"] = True

        # Update agent configuration if provided
        if fallback_agent_id:
            updated_state["fallback_agent_id"] = fallback_agent_id

        if fallback_config:
            updated_state["agent_config"] = fallback_config

        updated_state["metadata"] = metadata

        return updated_state

    @classmethod
    def _degraded_recovery(
        cls,
        error: Exception,
        state: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Degraded recovery - continue with reduced functionality.

        Context:
            - degraded_mode: Description of degraded state
            - skipped_steps: Steps to skip in degraded mode
        """
        degraded_mode = context.get("degraded_mode", "limited")
        skipped_steps = context.get("skipped_steps", [])

        updated_state = state.copy()
        metadata = updated_state.get("metadata", {})

        # Update metadata
        if hasattr(metadata, 'status'):
            metadata.status = "degraded"
            metadata.error = str(error)
            metadata.degraded_mode = degraded_mode
        else:
            if isinstance(metadata, dict):
                metadata["status"] = "degraded"
                metadata["error"] = str(error)
                metadata["degraded_mode"] = degraded_mode

        updated_state["metadata"] = metadata
        updated_state["degraded_mode"] = True
        updated_state["skipped_steps"] = skipped_steps

        return updated_state

    @classmethod
    def _notify_recovery(
        cls,
        error: Exception,
        state: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Notify recovery - pause for human intervention.

        Context:
            - notification_channel: Where to send notification
            - notification_recipients: Who to notify
        """
        notification_channel = context.get("notification_channel", "log")
        recipients = context.get("notification_recipients", [])

        updated_state = state.copy()
        metadata = updated_state.get("metadata", {})

        # Update metadata
        if hasattr(metadata, 'status'):
            metadata.status = "awaiting_intervention"
            metadata.error = str(error)
        else:
            if isinstance(metadata, dict):
                metadata["status"] = "awaiting_intervention"
                metadata["error"] = str(error)

        # Create notification payload
        notification = {
            "workflow_id": state.get("workflow_id"),
            "error": str(error),
            "timestamp": datetime.now(UTC).isoformat(),
            "channel": notification_channel,
            "recipients": recipients,
        }

        updated_state["metadata"] = metadata
        updated_state["pending_notification"] = notification

        # Log notification (in production, send to actual channel)
        print(f"🚨 WORKFLOW REQUIRES INTERVENTION: {notification}")

        return updated_state

    @classmethod
    def _abort_recovery(
        cls,
        error: Exception,
        state: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Abort recovery - gracefully terminate workflow.

        Context:
            - reason: Reason for abort
            - cleanup_action: Optional cleanup action
        """
        reason = context.get("reason", "Unrecoverable error")
        cleanup_action = context.get("cleanup_action")

        updated_state = state.copy()
        metadata = updated_state.get("metadata", {})

        # Update metadata
        if hasattr(metadata, 'status'):
            metadata.status = "aborted"
            metadata.error = str(error)
            metadata.abort_reason = reason
        else:
            if isinstance(metadata, dict):
                metadata["status"] = "aborted"
                metadata["error"] = str(error)
                metadata["abort_reason"] = reason

        updated_state["metadata"] = metadata
        updated_state["abort_reason"] = reason

        # Execute cleanup if provided
        if cleanup_action:
            try:
                cleanup_action(state)
            except Exception as cleanup_error:
                print(f"⚠️  Cleanup failed: {cleanup_error}")

        return updated_state

    @classmethod
    def create_error_recovery_state(
        cls,
        workflow_id: str,
        template_id: str,
        error: Exception,
        recovery_strategy: RecoveryStrategy,
    ) -> Dict[str, Any]:
        """
        Create error recovery state for new workflow.

        Args:
            workflow_id: Workflow identifier
            template_id: Template identifier
            error: Exception that occurred
            recovery_strategy: Strategy being used

        Returns:
            State dictionary for error recovery
        """
        from ..state.workflow_state import RunMetadata

        return {
            "workflow_id": workflow_id,
            "template_id": template_id,
            "messages": [],
            "current_step": None,
            "execution_result": {
                "error": str(error),
                "recovery_strategy": recovery_strategy.value,
            },
            "approval_required": False,
            "approval_status": None,
            "metadata": RunMetadata(
                workflow_id=workflow_id,
                template_id=template_id,
                status="error",
                error=str(error),
            )
        }
