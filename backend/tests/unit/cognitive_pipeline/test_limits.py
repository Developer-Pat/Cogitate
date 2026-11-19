"""B.1 — the limit model: ok | warn | stop, and it is never silent.

The arc's rule is that a limit must be LOUD (roadmap §1, D5): the running app
is the instrument that corrects a wrong limit, and an instrument that does not
report itself cannot be corrected. So these tests pin three things besides the
arithmetic: the exact log lines, that a fired limit carries its reason into the
user-facing sentence, and that a limit with no reason cannot exist at all.
"""

from __future__ import annotations

import logging

import pytest

from app.services.cognitive_pipeline.limits import (
    CALL,
    HARD,
    SOFT,
    TURN,
    Limit,
    LimitDefinitionError,
    check_limits,
    limit_line,
    limits_in_force,
    measure,
    number,
)


def _limit(
    key: str = "output_tokens",
    kind: str = SOFT,
    scope: str = CALL,
    threshold: float = 2000,
    reason: str = "the call's budget",
) -> Limit:
    return Limit(key=key, kind=kind, scope=scope, threshold=threshold, reason=reason)


class TestTheLimitIsAWellFormedPolicy:
    def test_a_limit_carries_its_reason(self):
        limit = _limit(reason="output budget for this call is 2000 — soft line at 90%")
        assert limit.reason.startswith("output budget for this call")

    def test_a_limit_with_no_reason_cannot_be_built(self):
        with pytest.raises(LimitDefinitionError):
            _limit(reason="")

    def test_a_blank_reason_is_not_a_reason(self):
        with pytest.raises(LimitDefinitionError):
            _limit(reason="   ")

    def test_unknown_kind_and_scope_are_refused(self):
        with pytest.raises(LimitDefinitionError):
            _limit(kind="medium")
        with pytest.raises(LimitDefinitionError):
            _limit(scope="forever")

    def test_no_threshold_is_not_a_limit(self):
        with pytest.raises(LimitDefinitionError):
            _limit(threshold=None)  # type: ignore[arg-type]

    def test_soft_and_hard_are_the_two_kinds(self):
        assert _limit(kind=SOFT).is_soft and not _limit(kind=SOFT).is_hard
        assert _limit(kind=HARD).is_hard and not _limit(kind=HARD).is_soft


class TestTheVerdicts:
    def test_under_both_thresholds_is_ok(self):
        limits = [_limit(kind=SOFT, threshold=1800), _limit(kind=HARD, threshold=2000)]
        verdict = check_limits({"output_tokens": 1024}, limits)
        assert verdict.ok and verdict.status == "ok"
        assert verdict.reason == "" and verdict.log_line == ""

    def test_the_soft_line_warns_and_carries_on(self):
        limits = [_limit(kind=SOFT, threshold=1800, reason="the answer is near its budget")]
        verdict = check_limits({"output_tokens": 1800}, limits)
        assert verdict.warned and not verdict.stopped
        assert verdict.value == 1800
        assert verdict.reason == "the answer is near its budget"
        assert verdict.limit is not None and verdict.limit.kind == SOFT

    def test_the_hard_line_stops(self):
        limits = [_limit(kind=HARD, threshold=2000, reason="the turn hit its ceiling")]
        verdict = check_limits({"output_tokens": 2001}, limits)
        assert verdict.stopped and not verdict.warned
        assert verdict.reason == "the turn hit its ceiling"

    def test_the_threshold_itself_fires(self):
        """`value >= threshold`, the tool guard's own shape — one below warns."""
        assert check_limits({"output_tokens": 1999}, [_limit(threshold=2000)]).ok
        assert check_limits({"output_tokens": 2000}, [_limit(threshold=2000)]).warned

    def test_a_hard_breach_outranks_a_soft_one(self):
        limits = [
            _limit(kind=SOFT, threshold=100, reason="soft"),
            _limit(kind=HARD, threshold=200, reason="hard"),
        ]
        verdict = check_limits({"output_tokens": 5000}, limits)
        assert verdict.stopped and verdict.reason == "hard"

    def test_the_first_limit_of_a_class_wins(self):
        limits = [
            _limit(key="provider_calls", kind=HARD, threshold=12, reason="calls"),
            _limit(key="wall_clock_s", kind=HARD, threshold=600, reason="clock"),
        ]
        verdict = check_limits({"provider_calls": 12, "wall_clock_s": 900}, limits)
        assert verdict.reason == "calls"

    def test_an_unmeasurable_quantity_is_not_a_breach(self):
        """A missing measurement is not a limit — the state simply has no number."""
        limits = [_limit(key="cost_usd", kind=HARD, threshold=0.25, reason="spend")]
        assert check_limits({"output_tokens": 99999}, limits).ok
        assert check_limits({}, limits).ok
        assert check_limits(None, limits).ok

    def test_state_may_be_an_object(self):
        class TurnState:
            output_tokens = 3000

        verdict = check_limits(TurnState(), [_limit(threshold=2000)])
        assert verdict.warned and verdict.value == 3000

    def test_no_limits_at_all_is_ok(self):
        assert check_limits({"output_tokens": 10}, []).ok


class TestItIsNeverSilent:
    def test_the_soft_line_is_the_exact_log_shape(self):
        limits = [_limit(kind=SOFT, threshold=2000, reason="the answer is near its budget")]
        verdict = check_limits({"output_tokens": 2048}, limits)
        assert verdict.log_line == (
            "⚠️ LIMIT SOFT key=output_tokens value=2048 threshold=2000 "
            "reason=the answer is near its budget"
        )

    def test_the_hard_line_is_the_exact_log_shape(self):
        limits = [_limit(key="provider_calls", kind=HARD, scope=TURN, threshold=12, reason="runaway")]
        verdict = check_limits({"provider_calls": 13}, limits)
        assert verdict.log_line == (
            "🚫 LIMIT HARD STOP key=provider_calls value=13 reason=runaway"
        )

    def test_a_soft_breach_is_written_to_the_log(self, caplog):
        limits = [_limit(kind=SOFT, threshold=2000, reason="near its budget")]
        with caplog.at_level(logging.WARNING, logger="app.services.cognitive_pipeline.limits"):
            check_limits({"output_tokens": 2048}, limits)
        assert any("⚠️ LIMIT SOFT key=output_tokens" in r.message for r in caplog.records)

    def test_a_hard_breach_is_written_to_the_log_at_error(self, caplog):
        limits = [_limit(kind=HARD, threshold=2000, reason="ceiling")]
        with caplog.at_level(logging.ERROR, logger="app.services.cognitive_pipeline.limits"):
            check_limits({"output_tokens": 2048}, limits)
        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert any("🚫 LIMIT HARD STOP key=output_tokens" in r.message for r in errors)

    def test_an_ok_verdict_writes_nothing(self, caplog):
        with caplog.at_level(logging.DEBUG, logger="app.services.cognitive_pipeline.limits"):
            check_limits({"output_tokens": 1}, [_limit(threshold=2000)])
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


class TestTheSmallHelpers:
    def test_numbers_print_without_a_trailing_zero(self):
        assert number(2048.0) == "2048"
        assert number(0.25) == "0.25"
        assert number(None) == "None"
        assert number("nonsense") == "nonsense"

    def test_measure_reads_a_mapping_and_an_object(self):
        class State:
            output_tokens = 7

        assert measure({"output_tokens": 7}, "output_tokens") == 7.0
        assert measure(State(), "output_tokens") == 7.0
        assert measure({"output_tokens": 7}, "cost_usd") is None
        assert measure({}, "output_tokens") is None
        assert measure(None, "output_tokens") is None
        assert measure({"output_tokens": "not a number"}, "output_tokens") is None

    def test_the_line_helper_matches_the_verdict(self):
        limit = _limit(kind=HARD, threshold=12)
        assert limit_line(limit, 12) == check_limits({"output_tokens": 12}, [limit]).log_line

    def test_the_limit_set_can_describe_itself(self):
        census = limits_in_force(
            [
                _limit(key="output_tokens", kind=SOFT, scope=CALL, threshold=1800),
                _limit(key="provider_calls", kind=HARD, scope=TURN, threshold=12),
            ]
        )
        assert census == "limits: output_tokens(soft call 1800), provider_calls(hard turn 12)"
        assert limits_in_force([]) == "limits: none"
