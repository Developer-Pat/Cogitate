"""The turn's soft lines: where they are defined, and what the judge does with them.

Soft means the log writes the line, the user is told, and NOTHING stops. These
tests pin the two halves that make that safe: the numbers and the copy every
reason carries (what happened, and that the turn carries on), and the SCOPES —
a turn-scoped limit is judged against the account, a call-scoped one against the
single call, and confusing the two fires on the second call of every multi-call
turn (a false alarm, not a limit).
"""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import pytest

from app.services.cognitive_pipeline.limits import (
    CALL,
    HARD,
    SOFT,
    TURN,
    Limit,
    check_limits,
    inactive_limits_note,
    limits_in_force,
    turn_soft_limits,
    call_soft_limits,
)
from app.services.cognitive_pipeline.turn_state import TurnState
from sqlalchemy import select

# The budgets a path can run under (the resolver's paths: fast 512, pass 1 the
# declaration, the deep pass max(declared, 4096)).
PATH_BUDGETS = {
    "fast": (512, 460),
    "pass1": (2000, 1800),
    "deep": (4096, 3686),
}


class TestTheNumbers:
    """The armed set — what the table's second half will have to admit to."""

    def test_the_turn_arms_three_soft_lines_and_no_hard_one(self):
        armed = turn_soft_limits()

        assert [(limit.key, limit.kind, limit.scope) for limit in armed] == [
            ("provider_calls", SOFT, TURN),
            ("tool_calls", SOFT, TURN),
            ("wall_clock_s", SOFT, TURN),
        ]
        assert [limit for limit in armed if limit.kind == HARD] == []

    def test_the_numbers_are_the_roadmaps(self):
        armed = {limit.key: limit.threshold for limit in turn_soft_limits()}

        assert armed == {"provider_calls": 8, "tool_calls": 20, "wall_clock_s": 300}

    def test_every_reason_says_nothing_was_blocked(self):
        """D7's tone rule: a warning the user cannot act on is the failure here."""
        for limit in turn_soft_limits() + call_soft_limits(2000):
            assert "Nothing is blocked" in limit.reason, limit.key
            assert "carries on" in limit.reason, limit.key

    def test_the_iterations_row_is_not_armed_it_is_named_redundant(self):
        """Both loops already end at 5 and `provider_calls` covers the same events."""
        keys = {limit.key for limit in turn_soft_limits()}
        assert "iterations" not in keys
        assert "turns" not in keys


class TestTheOutputSoft:
    """A fraction of the call's own budget — so it varies by run path."""

    def test_it_scales_with_the_budget_each_path_runs_under(self):
        for path, (budget, expected) in PATH_BUDGETS.items():
            limits = call_soft_limits(budget)
            assert len(limits) == 1, path
            assert limits[0].key == "output_tokens"
            assert limits[0].scope == CALL, path
            assert limits[0].threshold == expected, path
            assert f"{budget}-token" in limits[0].reason, path

    def test_no_budget_means_no_limit(self):
        """A threshold that cannot be named is not a limit (B.1) — it is skipped."""
        assert call_soft_limits(None) == ()
        assert call_soft_limits(0) == ()

    def test_the_window_is_accepted_and_unused_by_design(self):
        """The number the app trims against is the BUDGET, not the window (E.6).

        80 % of a 262144 window would never speak; 80 % of the 16000-token assembly
        ceiling is a line a real prompt can reach. The argument stays in the
        signature so the shape did not move when the input soft was armed.
        """
        assert call_soft_limits(2000, window=8192) == call_soft_limits(2000)


class TestTheInputSoft:
    """E.6, F4's ruling: 80 % of the INPUT BUDGET, judged per call."""

    def test_it_is_a_fraction_of_the_budget_in_force(self):
        limits = call_soft_limits(2000, input_budget=16000)

        assert [limit.key for limit in limits] == ["output_tokens", "input_tokens"]
        input_limit = limits[1]
        assert input_limit.scope == CALL
        assert input_limit.threshold == 12800          # 80 % of 16000
        assert "16000-token input budget" in input_limit.reason
        assert "Nothing is blocked" in input_limit.reason

    def test_it_follows_a_window_lowered_budget(self):
        """A driver too small to hold the constant gets a lower line, not 12800."""
        assert call_soft_limits(None, input_budget=6192)[0].threshold == 4953

    def test_no_input_budget_means_no_input_limit(self):
        assert [limit.key for limit in call_soft_limits(2000)] == ["output_tokens"]
        assert call_soft_limits(input_budget=0) == ()

    def test_a_call_that_reported_no_prompt_is_skipped_not_breached(self):
        """An unmeasured quantity is not a limit (B.1) — the caller omits the key."""
        limits = call_soft_limits(2000, input_budget=16000)

        assert check_limits({"output_tokens": 10}, limits).ok          # no input_tokens
        assert check_limits({"input_tokens": 12800}, limits).warned    # the line itself
        assert check_limits({"input_tokens": 12799}, limits).ok


class TestTheInactiveCensus:
    """An inactive limit must SAY it is inactive (D8), never pass silently."""

    def test_the_one_left_that_cannot_be_judged_is_declared(self):
        """`input_tokens` was the other row until E.1 derived the window (E.6)."""
        note = inactive_limits_note()

        assert note.startswith("limits inactive: ")
        assert "cost_usd" in note
        assert "D8" in note
        assert "input_tokens" not in note

    def test_an_empty_census_still_says_something(self):
        assert inactive_limits_note({}) == "limits inactive: none"


class TestTheJudgement:
    """The judge's behaviour on both scopes — warn, never stop."""

    def test_the_turn_soft_lines_fire_at_their_thresholds(self):
        state = TurnState()
        for _ in range(7):
            state.observe_provider_call("pass1")

        assert check_limits(state, turn_soft_limits()).ok

        state.observe_provider_call("pass1")  # the 8th
        verdict = check_limits(state, turn_soft_limits())

        assert verdict.warned and not verdict.stopped
        assert verdict.limit is not None and verdict.limit.key == "provider_calls"
        assert "provider_calls" in verdict.log_line

    def test_the_output_soft_is_judged_against_one_call(self):
        """The call's own tokens — never the turn's accumulated total."""
        limits = call_soft_limits(2000)

        assert check_limits({"output_tokens": 1799}, limits).ok
        assert check_limits({"output_tokens": 1800}, limits).warned
        # the same limit against the TURN's tokens would fire on the second call
        # of every multi-call turn — which is why the scopes are kept apart and
        # the account is never handed to `call_soft_limits`' thresholds.
        assert [limit.scope for limit in limits] == [CALL]

    def test_the_armed_set_reads_as_one_line_for_the_log(self):
        described = limits_in_force(turn_soft_limits())

        assert described.startswith("limits: ")
        assert "provider_calls(soft turn 8)" in described
        assert "wall_clock_s(soft turn 300)" in described


# ---------------------------------------------------------------------------
# THE CHECK AT THE BOUNDARY (the router's half)
# ---------------------------------------------------------------------------

class _StubChunk:
    """A stream chunk in the shape the router's streamer reads."""

    def __init__(self, content: str = "", finish_reason=None):
        self.choices = [
            SimpleNamespace(
                delta=SimpleNamespace(
                    content=content, tool_calls=None, reasoning="", reasoning_content="",
                ),
                finish_reason=finish_reason,
            )
        ]
        self.usage = None


class _StubStream:
    def __init__(self, chunks):
        self._chunks = chunks

    def __aiter__(self):
        self._it = iter(self._chunks)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


def _one_provider_call_crosses():
    """The turn's lines, with the provider threshold dropped to 1 (a test profile)."""
    return (
        Limit(
            key="provider_calls", kind=SOFT, scope=TURN, threshold=1,
            reason="This turn has called the provider 1 times — a test profile. "
                   "Nothing is blocked; the turn carries on.",
        ),
    )


class TestTheCheckAtTheBoundary:
    """Tell the user ONCE per threshold, record EVERY crossing, never stop."""

    def _context(self, provider_calls: int = 0) -> SimpleNamespace:
        context = SimpleNamespace(
            turn_state=TurnState(), tool_call_tracker=None,
            session_id=1, model="m", provider="p",
        )
        for _ in range(provider_calls):
            context.turn_state.observe_provider_call("pass1")
        return context

    def test_a_crossing_is_told_once_and_recorded_every_time(self, monkeypatch):
        from app.api.v1.chat import router as mod

        told = []
        monkeypatch.setattr(
            mod, "publish_warning",
            lambda title, message, kind=None: told.append((title, message, kind)),
        )

        context = self._context(provider_calls=8)
        mod._check_turn_limits(context, stage="call")
        mod._check_turn_limits(context, stage="call")

        # the toast is once per threshold per turn (F2)...
        assert len(told) == 1
        assert told[0][2] == "turn-soft-limit"
        assert "provider 8 times" in told[0][1]
        # ...while the record keeps both crossings, newest last
        assert len(context.turn_state.crossings) == 2
        assert context.turn_state.notice_text() == told[0][1]

    def test_the_input_soft_is_judged_from_the_CALLS_prompt(self, monkeypatch):
        """E.6: THIS call's prompt against the budget in force — never the turn's total."""
        from app.api.v1.chat import router as mod

        told = []
        monkeypatch.setattr(
            mod, "publish_warning",
            lambda title, message, kind=None: told.append(message),
        )

        context = self._context()
        context.input_budget = 16000          # the assembly ceiling in force

        # an ordinary prompt says nothing
        mod._check_turn_limits(context, stage="call", call_tokens=10, call_budget=2000)
        assert told == []

        # a prompt near the budget is told once, by name
        mod._check_turn_limits(
            context, stage="call", call_tokens=10, call_budget=2000,
            call_prompt_tokens=13000,
        )
        assert len(told) == 1 and "16000-token input budget" in told[0]

        # and it is NOT a turn line: the account's accumulated input does not fire it
        context.turn_state.input_tokens = 999_999
        mod._check_turn_limits(
            context, stage="call", call_tokens=10, call_budget=2000,
            call_prompt_tokens=10,
        )
        assert len(told) == 1

    def test_a_turn_below_every_line_is_told_nothing(self, monkeypatch):
        from app.api.v1.chat import router as mod

        told = []
        monkeypatch.setattr(
            mod, "publish_warning",
            lambda title, message, kind=None: told.append(title),
        )

        context = self._context(provider_calls=3)
        mod._check_turn_limits(context, stage="call")

        assert told == []
        assert context.turn_state.crossings == []

    def test_the_check_mirrors_the_tool_count_before_it_judges(self, monkeypatch):
        """The tool soft reads the TRACKER's count (one owner per number)."""
        from app.api.v1.chat import router as mod
        from app.api.v1.chat.tool_call_tracker import ToolCallTracker

        monkeypatch.setattr(mod, "publish_warning", lambda *a, **k: None)
        tracker = ToolCallTracker()
        for i in range(21):
            tracker.record_call("file-info", {"path": str(i)}, iteration=0)

        context = SimpleNamespace(
            turn_state=TurnState(), tool_call_tracker=tracker,
            session_id=1, model="m", provider="p",
        )
        mod._check_turn_limits(context, stage="final")

        assert context.turn_state.tool_calls == 21
        assert [c["key"] for c in context.turn_state.crossings] == ["tool_calls"]


@pytest.mark.anyio
async def test_a_crossing_reaches_the_frame_and_the_saved_row(
    test_session, monkeypatch, caplog,
):
    """The note on the message — on the done frame AND on the saved row.

    Driven through the REAL `generate_stream` over a fake provider stream: this
    pins the whole path (the boundary check → the toast → the note), and the
    turn COMPLETING is half the point — a soft limit tells, it does not stop.
    """
    from app.api.v1.chat import llm_utils
    from app.api.v1.chat import router as mod
    from app.domain.chat.services import ChatService
    from app.infrastructure.database.models import Agent, ChatMessage

    agent = Agent(
        name="Soft Limit Agent", provider="deepseek", model="deepseek-v4-flash",
        system_prompt="You are a test agent.", is_active=True,
    )
    test_session.add(agent)
    await test_session.commit()
    await test_session.refresh(agent)

    async def fake_completion(**kwargs):
        return _StubStream([
            _StubChunk(content="A complete answer."),
            _StubChunk(finish_reason="stop"),
        ])

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)
    monkeypatch.setattr(mod, "turn_soft_limits", _one_provider_call_crosses)

    request = SimpleNamespace(
        agent_id=agent.id, message="answer plainly", session_id=None,
        attachment_ids=None, generate_title=False,
    )
    service = ChatService(test_session)

    with caplog.at_level(logging.WARNING):
        frames = [chunk async for chunk in mod.generate_stream(request, service)]

    done = [f for f in frames if '"done": true' in f]
    assert done, f"the turn did not finish: {frames[-3:]}"
    assert not [f for f in frames if f.startswith("event: error")], "a soft limit STOPPED the turn"

    payload = json.loads(done[-1][6:]) if done[-1].startswith("data: ") else json.loads(
        done[-1].split("data: ", 1)[1].strip()
    )
    note = payload["metadata"].get("limit_notice")
    assert note and "Nothing is blocked" in note, payload["metadata"]
    assert payload["metadata"]["limits"][0]["key"] == "provider_calls"

    # ...and on the row the reload reads
    rows = (await test_session.execute(
        select(ChatMessage).where(ChatMessage.role == "assistant")
    )).scalars().all()
    assert rows and rows[-1].meta.get("limit_notice") == note, [r.meta for r in rows]

    # the log carries the fired line (the judge's own line)
    assert any("LIMIT SOFT" in record.getMessage() for record in caplog.records)
