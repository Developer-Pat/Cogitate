"""D.1 — one turn's spending, counted in one place.

Phase D.1 adds accounting and decides no budget: its own acceptance test is a
turn's totals in the log. What can be pinned in a unit test is the arithmetic and
the two rules the module states — one owner per number, and the token numbers say
whether they were measured.

The limit-model half matters as much as the arithmetic: `snapshot()` and the
attributes are what D.2's limits judge, so a test that a `Limit` fires against
this state is the proof that D.2 needs no new plumbing to be written.
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.api.v1.chat.tool_call_tracker import ToolCallTracker
from app.core.config import Paths
from app.services.cognitive_pipeline.limits import (
    HARD,
    SOFT,
    TURN,
    Limit,
    check_limits,
    measure,
)
from app.services.cognitive_pipeline.turn_state import (
    COST,
    ESTIMATED,
    INPUT_TOKENS,
    KEYS,
    MIXED,
    OUTPUT_TOKENS,
    PROVIDER_CALLS,
    REPORTED,
    SCOPE,
    TOOL_CALLS,
    UNMEASURED,
    WALL_CLOCK,
    TurnState,
    report_turn_account,
    tracker_tool_calls,
)


class TestTheAccumulation:
    """A turn's numbers, as the loops make them."""

    def test_provider_calls_accumulate_and_remember_their_path(self):
        state = TurnState()
        state.observe_provider_call("pass1")
        state.observe_provider_call("deep")
        # A retry is an attempt at the same path — the roadmap's thresholds are
        # about how often the turn reached a provider.
        state.observe_provider_call("deep")
        state.observe_provider_call("fallback")

        assert state.provider_calls == 4
        assert state.calls_by_path == {"pass1": 1, "deep": 2, "fallback": 1}
        assert state.paths_text() == "deep:2,fallback:1,pass1:1"

    def test_tokens_accumulate_across_the_loops_and_the_deep_pass(self):
        state = TurnState()
        state.observe_usage(prompt_tokens=1500, completion_tokens=200)
        state.observe_usage(prompt_tokens=1700, completion_tokens=900)
        state.observe_usage(prompt_tokens=1900, completion_tokens=800)

        assert (state.input_tokens, state.output_tokens) == (5100, 1900)
        assert state.token_source == REPORTED

    def test_a_provider_that_reports_nothing_is_an_estimate_and_says_so(self):
        state = TurnState()
        state.observe_usage(prompt_tokens=1200, completion_tokens=300)
        state.observe_usage(
            prompt_tokens=1400, completion_tokens=250, reported=False,
        )

        assert (state.input_tokens, state.output_tokens) == (2600, 550)
        assert state.token_source == MIXED

        estimated_only = TurnState()
        estimated_only.observe_usage(prompt_tokens=10, reported=False)
        assert estimated_only.token_source == ESTIMATED

        assert TurnState().token_source == UNMEASURED

    def test_usage_that_arrives_as_nothing_or_garbage_never_goes_negative(self):
        state = TurnState()
        state.observe_usage(prompt_tokens=None, completion_tokens="")
        state.observe_usage(prompt_tokens=-5, completion_tokens=-1)

        assert (state.input_tokens, state.output_tokens) == (0, 0)

    def test_elapsed_is_measured_not_summed(self):
        state = TurnState(started_at=time.monotonic() - 12.5)
        first = state.wall_clock_s
        assert first >= 12.5
        assert state.wall_clock_s >= first

    def test_tool_calls_mirror_the_tracker_rather_than_counting_again(self):
        state = TurnState()
        tracker = ToolCallTracker()
        tracker.record_call("file-info", {"path": "a"}, iteration=0)
        tracker.record_call("file-info", {"path": "b"}, iteration=1)

        assert state.observe_tool_calls(tracker) == 2
        # THE MIRROR: the tracker keeps counting and the mirror follows it, so
        # there is no second tally that could disagree with the guard's.
        tracker.record_call("datetime", {"operation": "now"}, iteration=2)
        assert state.observe_tool_calls(tracker) == 3
        assert state.tool_calls == tracker_tool_calls(tracker) == 3

    def test_a_turn_without_a_tracker_has_made_no_tool_calls(self):
        state = TurnState()
        assert state.observe_tool_calls(None) == 0
        assert state.observe_tool_calls(SimpleNamespace(total_calls=None)) == 0


class TestTheLimitInterface:
    """The shape D.2's limits judge — no new plumbing needed to write them."""

    def test_the_state_carries_every_key_the_limit_model_names(self):
        state = TurnState()
        assert set(KEYS) == {
            INPUT_TOKENS, OUTPUT_TOKENS, PROVIDER_CALLS, TOOL_CALLS, WALL_CLOCK, COST,
        }
        assert set(state.snapshot()) == set(KEYS)

    def test_measure_reads_every_key_off_the_object(self):
        state = TurnState(started_at=time.monotonic() - 1.0)
        state.observe_provider_call()
        state.observe_usage(prompt_tokens=100, completion_tokens=50)
        state.observe_tool_calls(None)

        for key in KEYS:
            value = measure(state, key)
            assert value is not None, key
        assert measure(state, PROVIDER_CALLS) == 1
        elapsed = measure(state, WALL_CLOCK)
        assert elapsed is not None and elapsed >= 1.0

    def test_a_soft_limit_warns_against_a_real_turn(self):
        state = TurnState()
        for _ in range(8):
            state.observe_provider_call("pass1")
        verdict = check_limits(
            state,
            [Limit(
                key=PROVIDER_CALLS, kind=SOFT, scope=TURN, threshold=8,
                reason="This turn has called the provider 8 times.",
            )],
        )

        assert verdict.warned and not verdict.stopped
        assert "provider_calls" in verdict.log_line

    def test_a_hard_limit_stops_against_a_real_turn(self):
        state = TurnState()
        for _ in range(12):
            state.observe_provider_call()
        verdict = check_limits(
            state,
            [Limit(
                key=PROVIDER_CALLS, kind=HARD, scope=TURN, threshold=12,
                reason="This turn has called the provider 12 times — stopping.",
            )],
        )

        assert verdict.stopped
        assert verdict.reason.endswith("stopping.")

    def test_cost_sits_at_zero_until_the_pricing_is_real(self):
        # D8: an inactive cost limit must read a real zero, not an invention.
        assert TurnState().cost_usd == 0.0


class TestTheAccountLine:
    """The line a live turn is read from."""

    def test_the_line_names_the_totals_the_paths_and_the_source(self):
        state = TurnState(started_at=time.monotonic() - 42.0)
        state.observe_provider_call("pass1")
        state.observe_provider_call("deep")
        state.observe_usage(prompt_tokens=8123, completion_tokens=1204)

        line = state.account_line(session_id=117, model="openrouter/x", provider="openrouter")

        assert line.startswith("TURN ACCOUNT ")
        assert "session=117" in line
        assert "model=openrouter/x" in line
        assert "provider_calls=2" in line
        assert "paths=deep:1,pass1:1" in line
        # THE TOOL STORY (the tool-reliability arc): the denominator and the counts
        # ride the same line, so one grep answers "was a tool offered, and what
        # happened to the calls".
        assert "tools_offered=0" in line
        assert "tool_calls=0" in line
        assert "tool_calls_blocked=0" in line
        assert "tool_failures=0" in line
        assert "tokens_in=8123" in line
        assert "tokens_out=1204" in line
        assert "tokens=reported" in line
        assert "elapsed_s=42." in line
        assert line.endswith(f"scope={SCOPE}")

    def test_the_line_says_when_there_is_no_measurement_at_all(self):
        line = TurnState().account_line()
        assert "tokens=none" in line
        assert "provider_calls=0" in line
        assert "paths=-" in line

    def test_the_report_is_logged(self, caplog):
        state = TurnState()
        state.observe_provider_call("pass1")

        with caplog.at_level(logging.INFO, logger="app.services.cognitive_pipeline.turn_state"):
            returned = report_turn_account(state, session_id=117, model="m")

        assert returned
        assert any("🧮 TURN ACCOUNT" in record.getMessage() for record in caplog.records)

    def test_the_report_never_raises_into_the_turn(self, caplog):
        class Exploding(TurnState):
            def account_line(self, **kwargs):  # type: ignore[override]
                raise RuntimeError("boom")

        with caplog.at_level(logging.ERROR):
            assert report_turn_account(Exploding(), session_id=1) == ""
        assert report_turn_account(None, session_id=1) == ""


# ---------------------------------------------------------------------------
# THE WIRING: read as SOURCE, so a new provider call cannot slip in uncounted
# ---------------------------------------------------------------------------

CHAT_DIR = Path(str(Paths.root)) / "backend/app/api/v1/chat"

# The chat module's provider-call shape, and the ONE place a provider is really
# reached (inside the retry wrapper — `acompletion(` itself).
CHAT_CALL = re.compile(r"acompletion_with_retry\(")
DIRECT_CALL = re.compile(r"await acompletion\(")
ACCOUNTED = "_account_provider_call("
# How far around a call site its accounting may sit: the calls are written
# multi-line, with their comment above them.
WINDOW = 10

# THE PARKED SITES (ruled "park both, named"): provider calls that are NOT this
# turn's, each carrying the reason it stays out of D.1's accounting. An excuse
# with no reason is what turns an allowlist into a hole.
PARKED = {
    "chat_delegate": (
        "a separate READ-ONLY turn on its own endpoint — its own 5-iteration "
        "loop, no tracker, no finalize (D.1 is the chat turn's account)"
    ),
    "chat_completion": (
        "a separate non-streaming endpoint — LiteLLM's own usage already rides "
        "its response body"
    ),
}


def _enclosing_function(lines, index):
    """``(name, def line index)`` of the module-level function at ``index``."""
    for i in range(index, -1, -1):
        match = re.match(r"(?:async )?def (\w+)", lines[i])
        if match:
            return match.group(1), i
    return "", 0


def _unaccounted_sites(lines, parked=None):
    """Line numbers (1-based) of provider calls neither accounted nor parked."""
    parked = PARKED if parked is None else parked
    offenders = []
    for index, line in enumerate(lines):
        if not CHAT_CALL.search(line):
            continue
        function, start = _enclosing_function(lines, index)
        if function in parked:
            continue
        # The accounting may sit anywhere between this function's `def` and just
        # after the call (the calls are written multi-line) — but never in a
        # PRECEDING function, which a plain lookback window would let it count.
        window = "\n".join(lines[start:index + WINDOW])
        if ACCOUNTED not in window:
            offenders.append(index + 1)
    return offenders


class TestEveryProviderCallIsAccounted:
    """A provider call in the turn is counted, or parked with its reason."""

    def test_every_call_in_the_chat_turn_is_accounted_or_parked(self):
        lines = (CHAT_DIR / "router.py").read_text().splitlines()
        offenders = _unaccounted_sites(lines)

        assert not offenders, (
            "router.py: these provider calls are neither accounted nor parked by "
            f"name, so the turn's account would under-report them — lines {offenders}"
        )

    def test_the_detector_flags_a_planted_uncounted_call(self):
        """Prove the guard can fail (the planted-instance recipe)."""
        planted = [
            "async def a_counted_turn():",
            "    _account_provider_call(context, 'pass1')",
            "    await acompletion_with_retry(**kwargs)",
            "",
            "async def a_second_call():",
            "    await acompletion_with_retry(**kwargs)",
        ]
        assert _unaccounted_sites(planted) == [6]
        # a parked site is excused ...
        assert _unaccounted_sites(planted, parked={"a_counted_turn", "a_second_call"}) == []

    def test_every_parked_site_names_a_reason(self):
        for function, reason in PARKED.items():
            assert reason.strip(), f"{function} is excused with no reason"

    def test_the_parked_sites_are_live(self):
        """An excuse with no call site behind it is a stale hole in the guard."""
        lines = (CHAT_DIR / "router.py").read_text().splitlines()
        for function in PARKED:
            sites = [
                i for i, line in enumerate(lines)
                if CHAT_CALL.search(line)
                and _enclosing_function(lines, i)[0] == function
            ]
            assert sites, f"{function} no longer calls a provider — drop its parked entry"

    def test_the_retry_wrapper_reports_its_attempts(self):
        """F2: the retries are visible to the turn, or the count misses the storm.

        The roadmap's provider-call thresholds (8 soft / 12 hard) are the loops'
        calls PLUS retries; a wrapper that retried silently would make the hard
        limit fire late on exactly the failure it exists for.
        """
        src = (CHAT_DIR / "llm_utils.py").read_text()

        assert DIRECT_CALL.search(src), "the wrapper no longer calls acompletion directly"
        assert "on_attempt(attempt)" in src
        assert src.index("on_attempt(attempt)") < src.index("await acompletion(**kwargs)")


# ---------------------------------------------------------------------------
# A SCRIPTED TURN: the real generate_stream over a fake provider stream
# ---------------------------------------------------------------------------

class _FakeChunk:
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


class _FakeStream:
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


@pytest.mark.anyio
async def test_a_scripted_turn_reports_its_totals(test_session, monkeypatch, caplog):
    """One real turn over a fake provider, and its totals reach the log.

    The whole wiring in one pass: the wrapper COUNTS the call, the call's tokens
    are ESTIMATED because this fake provider reports no usage (and marked as an
    estimate rather than passed off as a measurement), the tool count is mirrored
    from the tracker, and the report is written from the turn's `finally`.
    """
    from app.api.v1.chat import llm_utils
    from app.api.v1.chat import router as mod
    from app.domain.chat.services import ChatService
    from app.infrastructure.database.models import Agent

    agent = Agent(
        name="Accounting Agent",
        provider="deepseek",
        model="deepseek-v4-flash",
        system_prompt="You are a test agent.",
        is_active=True,
    )
    test_session.add(agent)
    await test_session.commit()
    await test_session.refresh(agent)

    async def fake_completion(**kwargs):
        return _FakeStream([
            _FakeChunk(content="A complete answer."),
            _FakeChunk(finish_reason="stop"),
        ])

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)

    request = SimpleNamespace(
        agent_id=agent.id, message="just answer plainly, no tools", session_id=None,
        attachment_ids=None, generate_title=False,
    )
    service = ChatService(test_session)

    with caplog.at_level(
        logging.INFO, logger="app.services.cognitive_pipeline.turn_state",
    ):
        frames = [chunk async for chunk in mod.generate_stream(request, service)]

    lines = [r.getMessage() for r in caplog.records if "TURN ACCOUNT" in r.getMessage()]
    assert lines, f"no account line was written; frames={frames[-3:]}"
    line = lines[-1]

    assert re.search(r"session=\d+", line), line
    assert re.search(r"provider_calls=[1-9]", line), line
    assert "tool_calls=0" in line
    assert "tokens=estimated" in line, line
    assert line.endswith("scope=loop+deep"), line

    # D.1 is accounting, not a behaviour change: the turn still finishes.
    assert any('"done": true' in frame for frame in frames)
