"""Regression tests for the tool_calls metric wiring.

The cognitive pipeline's executors never set metrics.tool_calls
(they call acompletion without tools=). The chat/stream path DOES
execute tools — the ToolCallTracker counts them. These tests prove
the save-site helper lifts the REAL number into the persisted
metric, and the fallback path works without a tracker.
"""

import pytest

from app.api.v1.chat.router import _populate_tool_calls_metric
from app.api.v1.chat.tool_call_tracker import ToolCallTracker
from app.services.cognitive_pipeline.models import (
    CognitiveMetrics,
    CognitiveResult,
    ComponentTrace,
    CognitiveTrace,
)


def _result() -> CognitiveResult:
    return CognitiveResult(response="ok", metrics=CognitiveMetrics())


class TestPopulateToolCallsMetric:
    def test_tracker_total_calls_is_lifted(self):
        tracker = ToolCallTracker()
        tracker.record_call("datetime", {"operation": "now"}, iteration=1, success=True)
        tracker.record_call("web_search", {"query": "x"}, iteration=2, success=True)
        tracker.record_call("datetime", {"operation": "now"}, iteration=3, success=True)

        result = _result()
        _populate_tool_calls_metric(result, tracker)

        assert result.metrics.tool_calls == 3

    def test_no_tracker_falls_back_to_tool_iterations(self):
        result = _result()
        trace = ComponentTrace(metadata={"tool_iterations": 5})
        _populate_tool_calls_metric(result, None, trace)
        assert result.metrics.tool_calls == 5

    def test_no_tracker_no_trace_leaves_zero(self):
        result = _result()
        _populate_tool_calls_metric(result, None, None)
        assert result.metrics.tool_calls == 0

    def test_empty_tracker_leaves_zero(self):
        tracker = ToolCallTracker()  # no calls recorded
        result = _result()
        _populate_tool_calls_metric(result, tracker)
        assert result.metrics.tool_calls == 0

    def test_does_not_touch_trace_or_response(self):
        tracker = ToolCallTracker()
        tracker.record_call("datetime", {"operation": "now"}, iteration=1, success=True)
        result = CognitiveResult(
            response="hello",
            trace=CognitiveTrace(),
            metrics=CognitiveMetrics(total_tokens=10),
        )
        _populate_tool_calls_metric(result, tracker)
        assert result.response == "hello"
        assert result.metrics.total_tokens == 10  # untouched
        assert result.metrics.tool_calls == 1
