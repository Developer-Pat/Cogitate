"""
Error handling and recovery for LangGraph workflows.

Provides:
- Retry logic for failed nodes
- Rollback mechanisms
- Recovery workflows
- Error state management

Usage:
    ```python
    from app.workflows.error_handling import RetryConfig, WorkflowRecoveryManager
    
    # Configure retry
    retry_config = RetryConfig(max_retries=3, delay=1.0)
    
    # Execute with retry
    result = WorkflowRecoveryManager.execute_with_retry(node_func, state, retry_config)
    
    # Rollback to checkpoint
    WorkflowRecoveryManager.rollback_to_checkpoint(workflow_id, checkpoint_id)
    ```
"""

from .retry import RetryConfig, RetryResult, execute_with_retry
from .rollback import RollbackManager, RollbackResult
from .recovery import RecoveryWorkflow, RecoveryStrategy

__all__ = [
    "RetryConfig",
    "RetryResult",
    "execute_with_retry",
    "RollbackManager",
    "RollbackResult",
    "RecoveryWorkflow",
    "RecoveryStrategy",
]
