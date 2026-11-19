"""
LangGraph workflow orchestration for cogitate.

This module provides workflow execution capabilities using LangGraph,
with support for:
- Checkpoint-based persistence (survives restarts)
- Human-in-the-loop interrupts
- Collections integration
- Real-time progress tracking
- FastAPI REST API

Example:
    ```python
    from app.workflows import execute_workflow
    
    result = execute_workflow(
        template_id="tpl-123",
        workflow_id="wf-456"
    )
    ```

API Endpoints:
    POST   /api/v1/workflows/execute       - Start workflow
    GET    /api/v1/workflows/{id}/status  - Get status
    POST   /api/v1/workflows/{id}/approve - Approve/reject
    GET    /api/v1/workflows/{id}/history - Get history
    DELETE /api/v1/workflows/{id}         - Delete workflow
"""

from .graphs.simple_workflow import create_simple_workflow
from .graphs.advanced_workflow import create_advanced_workflow
from .checkpointing.config import CheckpointerConfig
from .api.workflow_router import router as workflows_router

__all__ = [
    "create_simple_workflow",
    "create_advanced_workflow",
    "CheckpointerConfig",
    "workflows_router",
]
