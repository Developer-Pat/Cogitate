"""B.5 — the tool guard is a LIMIT, with the numbers it always had.

The guard used to be its own subsystem: it warned and it blocked, and the only
record of a fired guard was a private log line in `should_execute`. It is now
one more set of `Limit` objects judged by `check_limits()`, which means a
blocked call reports itself as `🚫 LIMIT HARD STOP key=tool_calls value=30
reason=…` — the same line shape the token limits use.

**No behaviour change.** The ceilings, the order they are judged in, the
warning one call before a block, the sentences the turn is told with, and the
rule that a blocked call leaves the counters untouched are all exactly what
`should_execute` did before; C.4's rule (the tracker's default IS the policy,
one source) still holds.
"""

from __future__ import annotations

import logging

from app.api.v1.chat.tool_call_tracker import (
    CONSECUTIVE_KEY,
    TOOL_CALLS_KEY,
    ToolCallTracker,
)
from app.services.cognitive_pipeline.limits import HARD, SOFT, TURN

LIMITS_LOGGER = "app.services.cognitive_pipeline.limits"


def _call(tracker: ToolCallTracker, tool_name: str, arguments: dict, iteration: int = 1):
    """One call through the guard, recorded exactly as the router records it."""
    verdict = tracker.should_execute(
        tool_name=tool_name, arguments=arguments, iteration=iteration
    )
    should_execute, _warning, error = verdict
    if should_execute:
        tracker.record_call(
            tool_name=tool_name, arguments=arguments, iteration=iteration, success=True
        )
    return verdict


def _repeat(tracker: ToolCallTracker, times: int, tool_name: str = "datetime"):
    """Call the SAME tool with the SAME arguments `times` times; return the verdicts."""
    verdicts = []
    for _ in range(times):
        verdicts.append(_call(tracker, tool_name, {"operation": "now"}))
    return verdicts


class TestTheLimitSetIsTheGuardsOwnNumbers:
    def test_the_guard_declares_its_three_limits(self):
        limits = ToolCallTracker().limits_for("file_info", consecutive=0)
        assert [(limit.key, limit.kind, limit.scope, limit.threshold) for limit in limits] == [
            (TOOL_CALLS_KEY, HARD, TURN, 30),
            (CONSECUTIVE_KEY, SOFT, TURN, 3),
            (CONSECUTIVE_KEY, HARD, TURN, 4),
        ]

    def test_the_numbers_track_the_constructor(self):
        tracker = ToolCallTracker(max_consecutive_calls=10, max_total_calls_per_tool=99)
        assert [limit.threshold for limit in tracker.limits_for("file_info", 0)] == [99, 9, 10]

    def test_the_total_ceiling_is_judged_before_the_repeat_one(self):
        """The guard's own order: the per-tool total, then the loop detector."""
        keys = [limit.key for limit in ToolCallTracker().limits_for("file_info", 0)]
        assert keys[0] == TOOL_CALLS_KEY

    def test_every_limit_names_a_reason(self):
        for limit in ToolCallTracker().limits_for("file_info", consecutive=2):
            assert limit.reason.strip()


class TestTheVerdictsAreLimitVerdicts:
    def test_the_warning_one_call_before_the_block_still_fires(self):
        tracker = ToolCallTracker()
        verdicts = _repeat(tracker, 3)
        assert [v[0] for v in verdicts] == [True, True, True]
        warning = verdicts[2][1]
        assert warning and "One more call will block" in warning
        assert verdicts[2][2] is None

    def test_the_block_still_fires_at_the_ceiling(self):
        tracker = ToolCallTracker()
        verdicts = _repeat(tracker, 4)
        should_execute, warning, error = verdicts[3]
        assert should_execute is False and warning is None
        assert error is not None and "Breaking loop to prevent spam" in error

    def test_the_warning_is_a_soft_limit_verdict_in_the_log(self, caplog):
        tracker = ToolCallTracker()
        with caplog.at_level(logging.WARNING, logger=LIMITS_LOGGER):
            _repeat(tracker, 3)
        assert any(
            "⚠️ LIMIT SOFT key=consecutive_tool_calls value=3 threshold=3" in r.getMessage()
            for r in caplog.records
        )

    def test_the_block_is_a_hard_limit_verdict_in_the_log(self, caplog):
        tracker = ToolCallTracker()
        with caplog.at_level(logging.ERROR, logger=LIMITS_LOGGER):
            _repeat(tracker, 4)
        assert any(
            "🚫 LIMIT HARD STOP key=consecutive_tool_calls value=4" in r.getMessage()
            for r in caplog.records
        )

    def test_the_total_ceiling_reports_as_the_total_key(self, caplog):
        tracker = ToolCallTracker()
        with caplog.at_level(logging.ERROR, logger=LIMITS_LOGGER):
            for i in range(31):
                _call(tracker, "file_info", {"path": f"agents/bob/n-{i}.md"})
        assert any(
            "🚫 LIMIT HARD STOP key=tool_calls value=30" in r.getMessage()
            for r in caplog.records
        )

    def test_a_twelve_call_inventory_still_passes_and_logs_no_limit(self, caplog):
        """C.4's regression, re-read through the limit model."""
        tracker = ToolCallTracker()
        with caplog.at_level(logging.WARNING, logger=LIMITS_LOGGER):
            for i in range(12):
                should_execute, warning, error = _call(
                    tracker, "file_info", {"path": f"agents/bob/n-{i}.md"}
                )
                assert should_execute and error is None and warning is None
        assert not [r for r in caplog.records if "LIMIT" in r.getMessage()]


class TestNothingMoved:
    def test_a_blocked_call_leaves_the_counters_untouched(self):
        """The guard's own rule, kept: a BLOCKED call is not a call.

        Four identical calls: three pass and are recorded, the fourth is
        blocked and recorded nowhere. (The counter is why the guard's message
        reads "called 4 consecutive times" — the number includes the call being
        judged — and a further attempt is blocked on the same count.)
        """
        tracker = ToolCallTracker()
        _repeat(tracker, 4)
        assert tracker.total_calls["datetime"] == 3
        assert tracker.consecutive_counts["datetime"] == 3
        should_execute, _warning, error = _repeat(tracker, 1)[0]
        assert should_execute is False and error is not None
        assert tracker.total_calls["datetime"] == 3
        assert tracker.consecutive_counts["datetime"] == 3

    def test_the_message_names_the_repeat_including_this_call(self):
        tracker = ToolCallTracker()
        verdicts = _repeat(tracker, 4)
        assert "called 4 consecutive times" in (verdicts[3][2] or "")

    def test_a_blocked_total_call_does_not_count_either(self):
        """The total ceiling is judged first, and it does not mutate state."""
        tracker = ToolCallTracker(max_total_calls_per_tool=2)
        for i in range(3):
            _call(tracker, "file_info", {"path": f"agents/bob/n-{i}.md"})
        assert tracker.total_calls["file_info"] == 2
        assert tracker.consecutive_counts["file_info"] == 1

    def test_a_different_argument_is_not_a_repeat(self):
        tracker = ToolCallTracker()
        verdicts = [
            _call(tracker, "file_info", {"path": f"agents/bob/n-{i}.md"}) for i in range(5)
        ]
        assert all(v[0] and v[1] is None for v in verdicts)
        assert tracker.consecutive_counts["file_info"] == 1

    def test_the_caller_passed_number_is_still_the_policy(self):
        """C.4: no limit is imposed from outside the tracker."""
        tracker = ToolCallTracker(max_total_calls_per_tool=2)
        verdicts = [
            _call(tracker, "file_info", {"path": f"agents/bob/n-{i}.md"}) for i in range(3)
        ]
        assert verdicts[1][0] is True and verdicts[2][0] is False
