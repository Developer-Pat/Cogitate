"""The trigger scheduler — a fired schedule invokes the graph, and a failure records it.

Regression: the scheduler used to log "matched" and never invoke
the workflow graph (wired-but-idle, found 2026-08-10 during live
testing). These tests pin the execution path so it can't silently
regress again.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[4]  # path-ok: locates the SOURCE tree to import app code; only DATA follows the installation root
sys.path.insert(0, str(ROOT / "backend"))

from app.workflows.triggers.scheduler import TriggerScheduler


@pytest.fixture
def scheduler():
    s = TriggerScheduler()
    s.event_router = MagicMock()
    s.trigger_service = MagicMock()
    return s


class TestScheduledExecution:
    @pytest.mark.anyio
    async def test_trigger_fires_invokes_workflow(self, scheduler):
        """A matched schedule trigger actually runs the workflow graph."""
        # The trigger exists + matches
        scheduler.trigger_service.get_active_triggers_by_type.return_value = [
            MagicMock(id="monitor-market-5min", workflow_id="market-watch")
        ]

        with patch(
            "app.workflows.api.workflow_router.compile_workflow"
        ) as mock_compile, patch(
            "app.workflows.execution_history.record_execution_start"
        ) as mock_start, patch(
            "app.workflows.execution_history.record_execution_complete"
        ) as mock_complete:
            # A compiled graph that returns a result
            mock_graph = MagicMock()
            mock_graph.invoke.return_value = {"last_price": 64914.0}
            mock_compile.return_value = mock_graph

            # Fire the extracted async method directly (the APScheduler
            # callback is a thin sync wrapper around this).
            await scheduler.execute_scheduled_workflow(
                "monitor-market-5min", "market-watch"
            )

            mock_start.assert_called_once()
            mock_complete.assert_called_once()
            assert mock_complete.call_args.kwargs["status"] == "completed"

    @pytest.mark.anyio
    async def test_trigger_failure_records_error(self, scheduler):
        """A graph exception records a failed execution, not silence."""
        scheduler.trigger_service.get_active_triggers_by_type.return_value = [
            MagicMock(id="monitor-market-5min", workflow_id="market-watch")
        ]

        with patch(
            "app.workflows.api.workflow_router.compile_workflow"
        ) as mock_compile, patch(
            "app.workflows.execution_history.record_execution_start"
        ), patch(
            "app.workflows.execution_history.record_execution_complete"
        ) as mock_complete:
            mock_graph = MagicMock()
            mock_graph.invoke.side_effect = RuntimeError("boom")
            mock_compile.return_value = mock_graph

            await scheduler.execute_scheduled_workflow(
                "monitor-market-5min", "market-watch"
            )

            mock_complete.assert_called_once()
            assert mock_complete.call_args.kwargs["status"] == "failed"
            assert "boom" in mock_complete.call_args.kwargs["error_message"]
