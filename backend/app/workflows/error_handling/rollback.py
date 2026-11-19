"""
Rollback mechanisms for workflow checkpoints.

Provides:
- RollbackManager: Manages checkpoint restoration
- RollbackResult: Result of rollback operation

Supports:
- Rollback to specific checkpoint
- Rollback to last known good state
- State restoration with validation
"""

from typing import Any, Dict, Optional, List
from datetime import datetime, UTC
from dataclasses import dataclass


@dataclass
class RollbackResult:
    """
    Result of rollback operation.

    Attributes:
        success: Whether rollback succeeded
        workflow_id: Workflow identifier
        from_checkpoint: Checkpoint rolled back from
        to_checkpoint: Checkpoint rolled back to
        error: Error message (if failed)
        timestamp: When rollback occurred
    """
    success: bool
    workflow_id: str
    from_checkpoint: Optional[str] = None
    to_checkpoint: Optional[str] = None
    error: Optional[str] = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "success": self.success,
            "workflow_id": self.workflow_id,
            "from_checkpoint": self.from_checkpoint,
            "to_checkpoint": self.to_checkpoint,
            "error": self.error,
            "timestamp": self.timestamp,
        }


class RollbackManager:
    """
    Manages checkpoint rollback operations.

    Provides:
    - Rollback to specific checkpoint
    - Rollback to last known good state
    - Checkpoint history navigation

    Usage:
        ```python
        # Rollback to specific checkpoint
        result = RollbackManager.rollback_to_checkpoint(
            workflow_id="wf-123",
            checkpoint_id="chk-456",
            config=config
        )

        # Rollback to last good state
        result = RollbackManager.rollback_to_last_good(
            workflow_id="wf-123",
            config=config
        )
        ```
    """

    @classmethod
    def rollback_to_checkpoint(
        cls,
        workflow_id: str,
        checkpoint_id: str,
        compiled_graph,
        config: dict,
    ) -> RollbackResult:
        """
        Rollback workflow to specific checkpoint.

        Args:
            workflow_id: Workflow identifier
            checkpoint_id: Target checkpoint ID
            compiled_graph: Compiled LangGraph workflow
            config: Workflow configuration

        Returns:
            RollbackResult with success/failure information
        """
        try:
            # Get current state to know where we're rolling back from
            current_state = compiled_graph.get_state(config)
            current_checkpoint_id = current_state.config.get("checkpoint_id") if current_state.config else None

            # Get target checkpoint
            history = list(compiled_graph.get_state_history(config))

            target_state = None
            for state in history:
                if state.config and state.config.get("checkpoint_id") == checkpoint_id:
                    target_state = state
                    break

            if target_state is None:
                return RollbackResult(
                    success=False,
                    workflow_id=workflow_id,
                    error=f"Checkpoint {checkpoint_id} not found",
                )

            # Restore state
            # In LangGraph, we can't directly restore, but we can update state
            # to match the target checkpoint
            compiled_graph.update_state(config, target_state.values)

            return RollbackResult(
                success=True,
                workflow_id=workflow_id,
                from_checkpoint=current_checkpoint_id,
                to_checkpoint=checkpoint_id,
            )

        except Exception as e:
            return RollbackResult(
                success=False,
                workflow_id=workflow_id,
                error=str(e),
            )

    @classmethod
    def rollback_to_last_good(
        cls,
        workflow_id: str,
        compiled_graph,
        config: dict,
        error_status: str = "error",
    ) -> RollbackResult:
        """
        Rollback workflow to last known good state.

        Finds the most recent checkpoint that doesn't have error status
        and rolls back to it.

        Args:
            workflow_id: Workflow identifier
            compiled_graph: Compiled LangGraph workflow
            config: Workflow configuration
            error_status: Status value that indicates error (default: "error")

        Returns:
            RollbackResult with success/failure information
        """
        try:
            # Get current state
            current_state = compiled_graph.get_state(config)
            current_checkpoint_id = current_state.config.get("checkpoint_id") if current_state.config else None

            # Get history
            history = list(compiled_graph.get_state_history(config))

            # Find last good state
            last_good_state = None
            for state in history:
                metadata = state.values.get("metadata", {}) if state.values else {}
                status = metadata.status if hasattr(metadata, 'status') else state.values.get("metadata", {}).get("status") if state.values else None

                if status != error_status:
                    last_good_state = state
                    break

            if last_good_state is None:
                return RollbackResult(
                    success=False,
                    workflow_id=workflow_id,
                    error="No good checkpoint found",
                )

            target_checkpoint_id = last_good_state.config.get("checkpoint_id") if last_good_state.config else None

            # Restore state
            compiled_graph.update_state(config, last_good_state.values)

            return RollbackResult(
                success=True,
                workflow_id=workflow_id,
                from_checkpoint=current_checkpoint_id,
                to_checkpoint=target_checkpoint_id,
            )

        except Exception as e:
            return RollbackResult(
                success=False,
                workflow_id=workflow_id,
                error=str(e),
            )

    @classmethod
    def get_checkpoint_history(
        cls,
        workflow_id: str,
        compiled_graph,
        config: dict,
    ) -> List[Dict[str, Any]]:
        """
        Get workflow checkpoint history.

        Args:
            workflow_id: Workflow identifier
            compiled_graph: Compiled LangGraph workflow
            config: Workflow configuration

        Returns:
            List of checkpoint metadata
        """
        try:
            history = list(compiled_graph.get_state_history(config))

            checkpoints = []
            for state in history:
                checkpoint_id = state.config.get("checkpoint_id") if state.config else None
                metadata = state.values.get("metadata", {}) if state.values else {}

                checkpoints.append({
                    "checkpoint_id": checkpoint_id,
                    "status": metadata.status if hasattr(metadata, 'status') else state.values.get("metadata", {}).get("status") if state.values else None,
                    "current_step": state.values.get("current_step") if state.values else None,
                    "next_nodes": list(state.next) if state.next else [],
                    "created_at": metadata.started_at if hasattr(metadata, 'started_at') else state.values.get("metadata", {}).get("started_at") if state.values else None,
                })

            return checkpoints

        except Exception:
            return []
