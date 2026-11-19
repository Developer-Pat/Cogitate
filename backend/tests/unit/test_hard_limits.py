"""D.3 — the hard plugs DEFINED: the two ceilings, and what a stopped turn says.

This is the half of D.3 that changes no behaviour: the two hard lines exist, they
carry the sentences the user will read, and the criterion that decides whether a
nearly-complete answer is kept (D.4 (b)) is named and testable. Nothing calls
them yet — arming them is the second half of the landing, in the router.

The companion file, `test_hard_limit_stop.py`, pins what the turn DOES with them:
the check returns the verdict, the stop aborts or finishes, and the partial
answer survives both.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.services.cognitive_pipeline.limits import (
    CONTINUE_SENTENCE,
    HARD,
    HARD_PROVIDER_CALLS,
    HARD_WALL_CLOCK_S,
    NEARLY_COMPLETE_FRACTION,
    STOP_ABORT,
    STOP_FINISH,
    TURN,
    hard_turn_limits,
    limits_in_force,
    nearly_complete,
    stop_message,
    stop_notice,
    turn_soft_limits,
    turn_stopped_line,
)
from app.services.cognitive_pipeline.turn_state import TurnState


class TestTheNumbers:
    """The armed HARD set — the ceilings the turn owns, and nothing else's."""

    def test_the_turn_arms_exactly_two_hard_lines(self):
        armed = hard_turn_limits()

        assert [(limit.key, limit.kind, limit.scope) for limit in armed] == [
            ("provider_calls", HARD, TURN),
            ("wall_clock_s", HARD, TURN),
        ]

    def test_the_numbers_are_the_roadmaps(self):
        armed = {limit.key: limit.threshold for limit in hard_turn_limits()}

        assert armed == {"provider_calls": 12, "wall_clock_s": 600}
        assert armed["provider_calls"] == HARD_PROVIDER_CALLS
        assert armed["wall_clock_s"] == HARD_WALL_CLOCK_S

    def test_every_reason_says_the_turn_stops(self):
        """The hard half of D7's tone rule: what happened AND its consequence.

        A soft reason says "nothing is blocked"; a hard reason must not — it has
        to say the turn is stopping, or the user cannot tell a stopped turn from
        a slow one.
        """
        for limit in hard_turn_limits():
            assert "stops here" in limit.reason, limit.key
            assert "Nothing is blocked" not in limit.reason, limit.key

    def test_a_hard_line_never_fires_before_its_own_warning(self):
        """Soft warns first, hard acts after — a plug below its warning is a bug."""
        soft = {limit.key: limit.threshold for limit in turn_soft_limits()}
        for limit in hard_turn_limits():
            if limit.key in soft:
                assert soft[limit.key] < limit.threshold, limit.key

    def test_the_guard_and_the_providers_cut_are_not_duplicated_here(self):
        """The tool guard's numbers and the output cut are already hard, elsewhere."""
        keys = {limit.key for limit in hard_turn_limits()}
        assert "consecutive_tool_calls" not in keys
        assert "output_tokens" not in keys
        assert "tool_calls" not in keys

    def test_the_armed_set_reads_as_one_line_for_the_log(self):
        described = limits_in_force(turn_soft_limits() + hard_turn_limits())

        assert "provider_calls(soft turn 8), " in described
        assert "provider_calls(hard turn 12)" in described
        assert "wall_clock_s(hard turn 600)" in described


class TestNearlyComplete:
    """D.4 (b)'s criterion (F1) — the difference between keeping and cutting."""

    def test_a_clean_stream_that_used_most_of_its_budget_is_kept(self):
        assert nearly_complete("stop", 3686, 4096) is True
        assert nearly_complete("stop", int(4096 * NEARLY_COMPLETE_FRACTION), 4096) is True
        assert nearly_complete("stop", 4096, 4096) is True

    def test_a_cut_stream_is_never_kept(self):
        """`length` means the provider cut the answer — that is not completion."""
        assert nearly_complete("length", 4096, 4096) is False

    def test_a_short_answer_is_not_nearly_complete(self):
        assert nearly_complete("stop", 1000, 4096) is False
        assert nearly_complete("stop", 0, 4096) is False

    def test_no_measurement_is_not_a_qualification(self):
        """A criterion is not met by a number we do not have (B.1's rule)."""
        not_a_number: Any = "not a number"

        assert nearly_complete("stop", 4000, None) is False
        assert nearly_complete("stop", None, 4096) is False
        assert nearly_complete(None, 4000, 4096) is False
        assert nearly_complete("stop", not_a_number, 4096) is False

    def test_it_is_its_own_number_not_the_output_softs(self):
        """The soft warns the user; this keeps or cuts an answer. One may move."""
        from app.core.config import Paths
        from app.services.cognitive_pipeline import limits as mod

        source = (
            Path(str(Paths.root)) / "backend/app/services/cognitive_pipeline/limits.py"
        ).read_text()

        assert mod.NEARLY_COMPLETE_FRACTION == 0.9
        # Its OWN literal, not an alias of the soft's fraction: a move in what
        # warns the user must not silently move what keeps an answer.
        assert "NEARLY_COMPLETE_FRACTION = 0.9" in source
        assert "NEARLY_COMPLETE_FRACTION = OUTPUT_SOFT_FRACTION" not in source


class TestWhatAStoppedTurnSays:
    """The two sentences (F2/F3) — the note, the frame's message, the log line."""

    def _limit(self):
        return hard_turn_limits()[0]

    def test_an_abort_says_what_was_kept_and_the_way_back_in(self):
        limit = self._limit()
        message = stop_message(limit, STOP_ABORT)

        assert limit.reason in message
        assert "What had already arrived is kept." in message
        assert CONTINUE_SENTENCE in message
        assert message.index("What had already arrived") < message.index(CONTINUE_SENTENCE)

    def test_a_finish_says_the_answer_was_kept_whole(self):
        notice = stop_notice(self._limit(), STOP_FINISH)

        assert "The answer was kept whole — nothing further was started." in notice
        # a finished turn has nothing to continue from — no "say continue"
        assert CONTINUE_SENTENCE not in notice

    def test_an_abort_that_kept_NOTHING_does_not_claim_a_partial(self):
        """A plug can fire before the first token — the note must not lie.

        The live verification hit exactly this (session 127: `partial=0`,
        mode=abort) and the note said "What had already arrived is kept" about an
        answer that did not exist. Zero kept is a third outcome, and it says so.
        """
        limit = self._limit()

        nothing_kept = stop_message(limit, STOP_ABORT, kept_chars=0)
        assert "Nothing had arrived yet, so there was nothing to keep." in nothing_kept
        assert "What had already arrived is kept." not in nothing_kept
        assert CONTINUE_SENTENCE in nothing_kept

        # the ordinary abort (something WAS kept) is unchanged
        assert "What had already arrived is kept." in stop_notice(limit, STOP_ABORT, 320)
        # and a FINISH never claims a partial either way
        assert "kept whole" in stop_notice(limit, STOP_FINISH, 0)

    def test_the_note_and_the_frame_carry_the_same_reason(self):
        limit = self._limit()
        assert stop_notice(limit, STOP_ABORT).startswith(limit.reason)
        assert stop_message(limit, STOP_ABORT).startswith(stop_notice(limit, STOP_ABORT))

    def test_the_log_line_names_the_plug_and_what_became_of_the_turn(self):
        line = turn_stopped_line(
            self._limit(), 12, partial_chars=431, stage="call", mode=STOP_ABORT
        )

        assert line.startswith("🚫 TURN STOPPED ")
        assert "key=provider_calls" in line
        assert "value=12" in line and "threshold=12" in line
        assert "partial=431" in line and "stage=call" in line and "mode=abort" in line


class TestTheAccountRecordsTheStop:
    """`TurnState` is where the note comes from — the stop rides it like a soft."""

    def _stopped(self, mode=STOP_ABORT):
        state = TurnState()
        verdict = SimpleNamespace(
            limit=hard_turn_limits()[0], value=12, reason=hard_turn_limits()[0].reason,
        )
        state.record_stop(verdict, mode)
        return state

    def test_the_first_plug_is_the_one_the_turn_acted_on(self):
        state = self._stopped()
        assert state.stopped_by_limit is True
        assert state.hard_stop is not None
        assert state.hard_stop["key"] == "provider_calls"
        assert state.hard_stop["mode"] == STOP_ABORT

    @pytest.mark.parametrize("mode", [STOP_ABORT, STOP_FINISH])
    def test_the_note_on_the_message_carries_the_plug(self, mode):
        state = self._stopped(mode)

        notice = state.notice_text()
        assert state.hard_stop["reason"] in notice
        assert notice in state.notice_text()  # stable, one sentence

    def test_a_verdict_with_no_limit_records_nothing(self):
        state = TurnState()
        assert state.record_stop(SimpleNamespace(limit=None), STOP_ABORT) is None
        assert state.stopped_by_limit is False
        assert state.crossings == []
