"""D.4 — the hard plug, armed: the turn stops, the work is kept, the user is told.

The failure mode this file exists to prevent is the one the arc was opened for —
a stopped turn that says nothing, or an aborted turn that throws away an answer
the user already paid for. Driven through the REAL `generate_stream`, so the
frame, the saved row and the absence of a further provider call are pinned
end to end.

The definitions themselves — the two ceilings, the copy, the criterion — are
pinned in `test_hard_limits.py`.
"""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.services.cognitive_pipeline.limits import (
    CONTINUE_SENTENCE,
    HARD,
    STOP_ABORT,
    STOP_FINISH,
    TURN,
    hard_turn_limits,
)
from app.services.cognitive_pipeline.turn_state import TurnState


class TestTheCheckAtTheBoundary:
    """`_check_turn_limits` now RETURNS the hard verdict (D.3's return value)."""

    def _context(self, provider_calls: int = 0):
        context = SimpleNamespace(
            turn_state=TurnState(), tool_call_tracker=None,
            session_id=1, model="m", provider="p",
        )
        for _ in range(provider_calls):
            context.turn_state.observe_provider_call("pass1")
        return context

    def test_a_turn_below_the_hard_lines_returns_nothing(self, monkeypatch):
        from app.api.v1.chat import router as mod

        monkeypatch.setattr(mod, "publish_warning", lambda *a, **k: None)
        assert mod._check_turn_limits(self._context(3), stage="call") is None

    def test_a_breached_hard_line_comes_back_to_the_caller(self, monkeypatch, caplog):
        from app.api.v1.chat import router as mod

        monkeypatch.setattr(mod, "publish_warning", lambda *a, **k: None)

        with caplog.at_level(logging.ERROR):
            stop = mod._check_turn_limits(self._context(12), stage="call")

        assert stop is not None and stop.stopped
        assert stop.limit.key == "provider_calls"
        # the judge wrote the line that says WHICH limit fired
        assert any("LIMIT HARD STOP" in r.getMessage() for r in caplog.records)

    def test_a_stopped_turn_is_not_judged_again(self, monkeypatch):
        """The first stop is the one the turn acted on — no second crossing."""
        from app.api.v1.chat import router as mod

        monkeypatch.setattr(mod, "publish_warning", lambda *a, **k: None)
        context = self._context(12)

        assert mod._check_turn_limits(context, stage="call") is not None
        context.turn_state.record_stop(
            SimpleNamespace(limit=hard_turn_limits()[0], value=12), STOP_ABORT
        )

        assert mod._check_turn_limits(context, stage="final") is None
        # the hard crossing is recorded ONCE — the soft crossings of the same key
        # are D.2's and are expected (they are a different line on the same number)
        hard_crossings = [c for c in context.turn_state.crossings if "mode" in c]
        assert len(hard_crossings) == 1


class TestTheStopAtTheBoundaries:
    """D7 (a)/(b) as the router decides it — abort, or let it finish."""

    def _verdict(self):
        limit = hard_turn_limits()[0]
        return SimpleNamespace(limit=limit, value=12, reason=limit.reason)

    def test_no_further_work_means_the_turn_was_ending_anyway(self):
        from app.api.v1.chat import router as mod

        mode = mod._stop_outcome(
            self._verdict(), pending_work=False,
            result=SimpleNamespace(finish_reason="stop", completion_tokens=10),
            call_budget=4096,
        )
        assert mode == STOP_FINISH

    def test_pending_work_with_a_nearly_complete_answer_is_kept(self):
        from app.api.v1.chat import router as mod

        mode = mod._stop_outcome(
            self._verdict(), pending_work=True,
            result=SimpleNamespace(finish_reason="stop", completion_tokens=4000),
            call_budget=4096,
        )
        assert mode == STOP_FINISH

    def test_pending_work_with_a_cut_answer_aborts(self):
        from app.api.v1.chat import router as mod

        mode = mod._stop_outcome(
            self._verdict(), pending_work=True,
            result=SimpleNamespace(finish_reason="tool_calls", completion_tokens=900),
            call_budget=4096,
        )
        assert mode == STOP_ABORT


# ---------------------------------------------------------------------------
# THE STOP THROUGH THE REAL STREAM
# ---------------------------------------------------------------------------

class _StubChunk:
    """A stream chunk in the shape `_stream_llm_response` reads."""

    def __init__(self, content="", finish_reason=None, tool_calls=None, usage=None):
        self.choices = [
            SimpleNamespace(
                delta=SimpleNamespace(
                    content=content, tool_calls=tool_calls,
                    reasoning="", reasoning_content="",
                ),
                finish_reason=finish_reason,
            )
        ]
        self.usage = usage


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


def _tool_call(name="file_info", args='{"path": "a.txt"}'):
    return [SimpleNamespace(
        index=0, id="call_1",
        function=SimpleNamespace(name=name, arguments=args),
    )]


def _one_call_ceiling():
    """The real hard set with the provider ceiling at 1 — a test profile."""
    return (
        type(hard_turn_limits()[0])(
            key="provider_calls", kind=HARD, scope=TURN, threshold=1,
            reason=(
                "This turn reached 1 calls to the provider — the ceiling for a "
                "single answer, so the turn stops here."
            ),
        ),
    )


async def _make_agent(test_session, name="Hard Limit Agent"):
    from app.infrastructure.database.models import Agent

    agent = Agent(
        name=name, provider="deepseek", model="deepseek-v4-flash",
        system_prompt="You are a test agent.", is_active=True,
    )
    test_session.add(agent)
    await test_session.commit()
    await test_session.refresh(agent)
    return agent


def _done_payload(frames):
    """The last done frame's payload, or None — the frame the bubble reads."""
    done = [f for f in frames if '"done": true' in f]
    if not done:
        return None
    payload = done[-1]
    body = (
        payload[6:] if payload.startswith("data: ")
        else payload.split("data: ", 1)[1].strip()
    )
    return json.loads(body)


def _done_metadata(frames):
    """The metadata of the finished turn — where the note on the message lives."""
    payload = _done_payload(frames)
    return None if payload is None else payload.get("metadata", {})


def _error_frames(frames):
    return [f for f in frames if f.startswith("event: error")]


@pytest.mark.anyio
async def test_a_runaway_turn_is_stopped_and_keeps_its_partial_answer(
    test_session, monkeypatch, caplog,
):
    """D7 (a): a breached hard line aborts the turn — and NOTHING is lost.

    The turn keeps calling tools; the ceiling is 1 provider call. What must be
    true afterwards: the user is told (the `limit_stop` frame), the partial answer
    is SAVED and readable, the plug is in the log, and the turn makes no further
    provider call — not even the deep pass the (forced) conduit asked for.
    """
    from app.api.v1.chat import llm_utils
    from app.api.v1.chat import router as mod
    from app.domain.chat.services import ChatService
    from app.infrastructure.database.models import ChatMessage
    from app.services.cognitive_pipeline.conduit import ConduitDecision, Route

    agent = await _make_agent(test_session, "Runaway Agent")

    partial = "Reading the file and now I will "
    calls: list = []

    async def fake_completion(**kwargs):
        calls.append(kwargs)
        return _StubStream([
            _StubChunk(content="Reading the file "),
            _StubChunk(content="and now I will "),
            _StubChunk(finish_reason="tool_calls", tool_calls=_tool_call()),
        ])

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)
    monkeypatch.setattr(mod, "hard_turn_limits", _one_call_ceiling)
    # The conduit is FORCED to want the deep pass: without the guard, a stopped
    # turn would make a second provider call (the assertion below then fails).
    monkeypatch.setattr(
        "app.services.cognitive_pipeline.conduit.conduit_route",
        lambda **kwargs: ConduitDecision(route=Route.HYBRID, reason="forced for the test"),
    )

    request = SimpleNamespace(
        agent_id=agent.id, message="read every file", session_id=None,
        attachment_ids=None, generate_title=False,
    )

    with caplog.at_level(logging.ERROR):
        frames = [chunk async for chunk in mod.generate_stream(request, ChatService(test_session))]

    # 1. the turn was stopped, in the tool guard's tone, with the way back in
    errors = _error_frames(frames)
    assert errors, f"the turn was not stopped: {frames[-3:]}"
    error = json.loads(errors[0].split("data: ", 1)[1].strip())["error"]
    assert error["type"] == "limit_stop"
    assert "stops here" in error["message"]
    assert "What had already arrived is kept." in error["message"]
    assert CONTINUE_SENTENCE in error["message"]

    # 2. the partial answer arrived BEFORE the stop and was KEPT
    assert any('"content": "Reading the file "' in f for f in frames)
    rows = (await test_session.execute(
        select(ChatMessage).where(ChatMessage.role == "assistant")
    )).scalars().all()
    assert rows, "the partial answer was not saved"
    assert rows[-1].content == partial
    hard = [
        c for c in (rows[-1].meta or {}).get("limits", [])
        if c.get("mode") == STOP_ABORT
    ]
    assert hard and hard[0]["key"] == "provider_calls", rows[-1].meta
    assert "What had already arrived is kept." in (rows[-1].meta or {}).get("limit_notice", "")

    # 3. no further provider call — the loop stopped and the deep pass was skipped
    assert len(calls) == 1, f"the stopped turn kept calling the provider: {len(calls)}"

    # 4. the log says so, in one line that names the plug and what was kept
    stopped_lines = [r.getMessage() for r in caplog.records if "TURN STOPPED" in r.getMessage()]
    assert stopped_lines, [r.getMessage() for r in caplog.records]
    assert "key=provider_calls" in stopped_lines[0]
    assert "mode=abort" in stopped_lines[0]
    assert f"partial={len(partial)}" in stopped_lines[0]


@pytest.mark.anyio
async def test_a_nearly_complete_answer_finishes_instead_of_being_cut(
    test_session, monkeypatch,
):
    """D7 (b)/F1: the plug fires BETWEEN iterations on a nearly-complete answer.

    The answer was one cost away from done, so the turn ends with it — no error
    frame, no further work started — and the note on the message says the plug
    fired, which is the only place the user would otherwise never learn it.
    """
    from app.api.v1.chat import llm_utils
    from app.api.v1.chat import router as mod
    from app.domain.chat.services import ChatService
    from app.infrastructure.database.models import ChatMessage

    agent = await _make_agent(test_session, "Nearly Done Agent")

    calls: list = []

    async def fake_completion(**kwargs):
        calls.append(kwargs)
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=20000)
        return _StubStream([
            _StubChunk(content="Here is the complete answer you asked for."),
            _StubChunk(
                finish_reason="stop", tool_calls=_tool_call(), usage=usage,
            ),
        ])

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)
    monkeypatch.setattr(mod, "hard_turn_limits", _one_call_ceiling)

    async def _no_tools(*args, **kwargs):
        raise AssertionError("a stopped turn executed a tool")

    monkeypatch.setattr(mod, "_execute_tools", _no_tools)

    request = SimpleNamespace(
        agent_id=agent.id, message="answer fully", session_id=None,
        attachment_ids=None, generate_title=False,
    )

    frames = [chunk async for chunk in mod.generate_stream(request, ChatService(test_session))]

    # the turn COMPLETED: no error frame, and the answer is the answer
    assert not _error_frames(frames), "a nearly-complete answer was aborted"
    metadata = _done_metadata(frames)
    assert metadata is not None, f"the turn never finished: {frames[-3:]}"
    assert "kept whole" in metadata.get("limit_notice", ""), metadata

    # ...and nothing further was started: the pending tool call was dropped (the
    # executor above would have raised), and no second provider call was made
    assert len(calls) == 1, f"the stopped turn kept calling the provider: {len(calls)}"

    rows = (await test_session.execute(
        select(ChatMessage).where(ChatMessage.role == "assistant")
    )).scalars().all()
    assert rows[-1].content == "Here is the complete answer you asked for."
    hard = [
        c for c in (rows[-1].meta or {}).get("limits", [])
        if c.get("mode") == STOP_FINISH
    ]
    assert hard and hard[0]["key"] == "provider_calls", rows[-1].meta


@pytest.mark.anyio
async def test_the_deep_pass_stops_at_its_own_boundary(
    test_session, monkeypatch, caplog,
):
    """Site 2: the deep pass's boundary stops the turn and keeps ITS answer.

    The deep pass REPLACES the first pass's content, so a stop there must keep the
    deep answer — not the pass before it — and make no further call.
    """
    from app.api.v1.chat import llm_utils
    from app.api.v1.chat import router as mod
    from app.domain.chat.services import ChatService
    from app.infrastructure.database.models import ChatMessage
    from app.services.cognitive_pipeline.conduit import ConduitDecision, Route

    agent = await _make_agent(test_session, "Deep Pass Agent")

    calls: list = []

    async def fake_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _StubStream([
                _StubChunk(content="A first pass sketch."),
                _StubChunk(finish_reason="stop"),
            ])
        return _StubStream([
            _StubChunk(content="The deep pass answer, longer. "),
            _StubChunk(finish_reason="tool_calls", tool_calls=_tool_call()),
        ])

    # The ceiling is 2: pass 1 is fine, the deep pass's call is the one that stops.
    def _two_call_ceiling():
        limit = hard_turn_limits()[0]
        return (
            type(limit)(
                key="provider_calls", kind=HARD, scope=TURN, threshold=2,
                reason=(
                    "This turn reached 2 calls to the provider — the ceiling for a "
                    "single answer, so the turn stops here."
                ),
            ),
        )

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)
    monkeypatch.setattr(mod, "hard_turn_limits", _two_call_ceiling)
    monkeypatch.setattr(
        "app.services.cognitive_pipeline.conduit.conduit_route",
        lambda **kwargs: ConduitDecision(route=Route.HYBRID, reason="forced for the test"),
    )

    request = SimpleNamespace(
        agent_id=agent.id, message="analyze this deeply", session_id=None,
        attachment_ids=None, generate_title=False,
    )

    with caplog.at_level(logging.ERROR):
        frames = [chunk async for chunk in mod.generate_stream(request, ChatService(test_session))]

    errors = _error_frames(frames)
    assert errors, f"the deep pass was not stopped: {frames[-3:]}"
    assert json.loads(errors[0].split("data: ", 1)[1].strip())["error"]["type"] == "limit_stop"
    assert len(calls) == 2, f"the stopped turn kept calling the provider: {len(calls)}"

    rows = (await test_session.execute(
        select(ChatMessage).where(ChatMessage.role == "assistant")
    )).scalars().all()
    assert rows[-1].content == "The deep pass answer, longer. "
    assert any(
        "stage=deep" in r.getMessage() and "mode=abort" in r.getMessage()
        for r in caplog.records if "TURN STOPPED" in r.getMessage()
    ), [r.getMessage() for r in caplog.records if "TURN STOPPED" in r.getMessage()]


# ---------------------------------------------------------------------------
# A TURN THAT PRODUCED NOTHING MUST SAY SO (2026-09-23)
# ---------------------------------------------------------------------------
# The live verification found two ways this turn ends with no answer, and both
# left the transcript EMPTY: session 125 (the tool loop used its five rounds,
# tokens_out=0) and session 127 (a plug fired at a provider call, before any text
# existed). The toast said something; the conversation did not, and a reload
# showed no turn at all. These pin the sentence that fixes it — in the tool
# guard's tone, on the row, and in the done frame.


class TestTheSentenceForATurnThatProducedNothing:
    """`_nothing_to_show_sentence` — why the turn is empty, or None."""

    def test_a_turn_with_content_needs_no_sentence(self):
        from app.api.v1.chat import router as mod

        assert mod._nothing_to_show_sentence(SimpleNamespace(), "an answer", 3) is None

    def test_a_fired_plug_speaks_with_its_own_sentence(self):
        from app.api.v1.chat import router as mod
        from app.services.cognitive_pipeline.limits import STOP_ABORT
        from app.services.cognitive_pipeline.turn_state import TurnState

        state = TurnState()
        limit = hard_turn_limits()[0]
        state.record_stop(
            SimpleNamespace(limit=limit, value=1, reason=limit.reason),
            STOP_ABORT, kept_chars=0,
        )
        sentence = mod._nothing_to_show_sentence(
            SimpleNamespace(turn_state=state), "", 0
        )

        assert sentence is not None
        assert "Nothing had arrived yet, so there was nothing to keep." in sentence
        assert CONTINUE_SENTENCE in sentence

    def test_a_loop_that_used_its_rounds_names_them(self):
        from app.api.v1.chat import router as mod

        sentence = mod._nothing_to_show_sentence(SimpleNamespace(), "", 5)

        assert sentence is not None
        assert "5 tool calls" in sentence
        assert CONTINUE_SENTENCE in sentence

    def test_an_unexplained_empty_turn_stays_with_the_guard(self):
        from app.api.v1.chat import router as mod

        # no plug, no tool rounds — nothing to attribute, so finalize's
        # empty-message guard keeps the case (and its own notice)
        assert mod._nothing_to_show_sentence(SimpleNamespace(), "", 0) is None


@pytest.mark.anyio
async def test_a_plug_that_fires_before_any_text_SAYS_SO_instead_of_vanishing(
    test_session, monkeypatch, caplog,
):
    """The empty-partial abort is not silence: the turn persists its reason.

    Session 127 in the live run: the ceiling was breached at a provider call, so
    nothing of an answer existed. The row was refused (an empty one would replay
    as a phantom bubble) and the turn left NOTHING on the transcript. Now the
    reason IS the message, flagged as the system's sentence rather than model
    output, and the note no longer claims a partial that never arrived.
    """
    from app.api.v1.chat import llm_utils
    from app.api.v1.chat import router as mod
    from app.domain.chat.services import ChatService
    from app.infrastructure.database.models import ChatMessage

    agent = await _make_agent(test_session, "Silent Stop Agent")

    async def fake_completion(**kwargs):
        # A tool call and NO text: the plug fires at the boundary with the
        # answer still empty, exactly as session 127 did.
        return _StubStream([
            _StubChunk(finish_reason="tool_calls", tool_calls=_tool_call()),
        ])

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)
    monkeypatch.setattr(mod, "hard_turn_limits", _one_call_ceiling)

    request = SimpleNamespace(
        agent_id=agent.id, message="write the file", session_id=None,
        attachment_ids=None, generate_title=False,
    )

    with caplog.at_level(logging.ERROR):
        frames = [chunk async for chunk in mod.generate_stream(request, ChatService(test_session))]

    # 1. the frame tells the truth about what was (not) kept
    errors = _error_frames(frames)
    assert errors, f"the turn was not stopped: {frames[-3:]}"
    error = json.loads(errors[0].split("data: ", 1)[1].strip())["error"]
    assert error["type"] == "limit_stop"
    assert "Nothing had arrived yet, so there was nothing to keep." in error["message"]
    assert CONTINUE_SENTENCE in error["message"]

    # 2. the turn is ON the transcript — the reason is the message, marked as
    #    the system's sentence rather than the model's answer
    rows = (await test_session.execute(
        select(ChatMessage).where(ChatMessage.role == "assistant")
    )).scalars().all()
    assert rows, "the stopped turn left the transcript empty"
    assert rows[-1].content == error["message"]
    assert (rows[-1].meta or {}).get("stopped_without_answer") is True
    assert "Nothing had arrived yet" in (rows[-1].meta or {}).get("limit_notice", "")

    # 3. it is no longer an EMPTY completion: the guard must not fire, and the
    #    done frame carries the same flag the row does
    assert not any("empty_completion" in f for f in _error_frames(frames))
    done = _done_metadata(frames)
    assert done is not None and done.get("stopped_without_answer") is True

    # 4. the sentence is IN THE STREAM, and it arrives BEFORE the error frame:
    #    the frontend stops reading at that frame, so the ORDER is the guarantee
    #    (streamed after it, the sentence never reaches the bubble)
    say_frames = [
        f for f in frames
        if '"content":' in f and "Nothing had arrived yet" in f
    ]
    assert say_frames, "the reason was never streamed"
    # ... and in the ONLY shape the frontend renders: `choices[0].delta.content`.
    # A live run proved `{'content': …}` renders nothing at all.
    assert '"delta"' in say_frames[0] and '"choices"' in say_frames[0], (
        f"the sentence did not use the frontend's content shape: {say_frames[0][:120]}"
    )
    say_idx = frames.index(say_frames[0])
    err_idx = next(i for i, f in enumerate(frames) if f.startswith("event: error"))
    assert say_idx < err_idx, (
        "the reason was streamed after the frame that ends the stream — "
        "the bubble would stay empty"
    )
