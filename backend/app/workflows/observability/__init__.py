"""
Observability module for LangGraph workflows.

Provides integration with observability platforms:
- Langfuse: Open source tracing and monitoring
- Future: LangSmith, Prometheus, etc.

Usage:
    ```python
    from app.workflows.observability import LangfuseManager

    # One trace per unit of work, its id derived from the unit's own id
    trace_id = LangfuseManager.create_trace_id(f"chat:{session_id}:{turn}")
    with LangfuseManager.create_trace("agent-chat", session_id=session_id, trace_id=trace_id) as span:
        ...
    ```
"""

from .langfuse_config import LangfuseManager

__all__ = ["LangfuseManager"]
