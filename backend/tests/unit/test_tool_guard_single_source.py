"""C.4 — the tool guard's limit has ONE source: the tracker's own default.

The call site in `chat/router.py` used to pass `max_total_calls_per_tool=10`,
silently undoing the tracker's own 10 → 30 raise (recorded in its docstring): a
reporter taking inventory of her workspace — 12 `file_info` calls — was killed
again, mid-job, after the raise was supposed to have fixed exactly that.

These tests pin both halves of the fix: the default really does admit ordinary
work, and the router's construction does not re-impose a lower cap.
"""

from __future__ import annotations

import ast
import inspect

from app.api.v1.chat import router as router_module
from app.api.v1.chat.tool_call_tracker import ToolCallTracker

INVENTORY_CALLS = 12
# The default the router now relies on instead of passing its own number.
TRACKER_DEFAULT_MAX_TOTAL_CALLS = 30


def _call(tracker: ToolCallTracker, index: int, iteration: int = 1):
    """One `file_info` call over a DIFFERENT file — an inventory, not a loop."""
    tool_name = "file_info"
    arguments = {"path": f"agents/bob/notes/note-{index}.md"}
    verdict = tracker.should_execute(
        tool_name=tool_name, arguments=arguments, iteration=iteration
    )
    tracker.record_call(
        tool_name=tool_name, arguments=arguments, iteration=iteration, success=True
    )
    return verdict


class TestTheDefaultIsThePolicy:
    def test_the_default_is_thirty(self):
        assert ToolCallTracker().max_total_calls == TRACKER_DEFAULT_MAX_TOTAL_CALLS

    def test_default_admits_a_twelve_call_inventory(self):
        tracker = ToolCallTracker()
        for i in range(INVENTORY_CALLS):
            should_execute, _warning, error = _call(tracker, i)
            assert should_execute and error is None, f"call {i + 1} was blocked: {error}"
        assert tracker.total_calls["file_info"] == INVENTORY_CALLS

    def test_the_old_call_site_cap_would_have_killed_it(self):
        """The regression itself: with the old 10 passed in, call 11 blocks."""
        tracker = ToolCallTracker(max_total_calls_per_tool=10)
        for i in range(INVENTORY_CALLS):
            should_execute, _warning, error = _call(tracker, i)
            if i < 10:
                assert should_execute, f"call {i + 1} blocked early: {error}"
            else:
                assert not should_execute, "the 10-cap no longer blocks at call 11"

    def test_the_ceiling_still_exists(self):
        """A cap is still a cap — the fix raised it, it did not remove it."""
        tracker = ToolCallTracker()
        for i in range(TRACKER_DEFAULT_MAX_TOTAL_CALLS):
            should_execute, _warning, error = _call(tracker, i)
            assert should_execute, f"call {i + 1} blocked inside the ceiling: {error}"
        should_execute, _warning, error = _call(tracker, TRACKER_DEFAULT_MAX_TOTAL_CALLS)
        assert should_execute is False and error is not None


class TestTheCallSiteDoesNotOverrideIt:
    """The router may pass the shape of the guard, never a lower total cap."""

    @staticmethod
    def _construction_keywords() -> list[list[str | None]]:
        tree = ast.parse(inspect.getsource(router_module))
        found: list[list[str | None]] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name == "ToolCallTracker":
                found.append([keyword.arg for keyword in node.keywords])
        return found

    def test_the_router_constructs_the_tracker(self):
        assert self._construction_keywords(), "chat/router.py must construct the tracker"

    def test_no_total_cap_is_reimposed(self):
        for keywords in self._construction_keywords():
            assert "max_total_calls_per_tool" not in keywords, (
                "the call site must not re-impose a cap — the tracker's default is "
                f"the single source (found keywords: {keywords})"
            )
