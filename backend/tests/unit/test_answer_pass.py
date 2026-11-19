"""Gap L — a tool loop that uses every round is asked to WRITE THE ANSWER.

The failure mode this file exists to prevent: the loop spends every round on tool calls, the
results land in the history, and the turn ends one call short of its deliverable — four live turns
of one session spent 249,377 input tokens and 77 tool calls and produced no answer at all
(*THE TOOL LOOP ENDS WITHOUT ASKING FOR AN ANSWER*).

The fix is ONE more call with the tools withheld. These drive the REAL `generate_stream`, so the
extra call, its shape (no tools), the answer on the saved row and the ABSENCE of the stand-in
sentence are pinned end to end. The tool RUNNER is stubbed; everything around it — the history
`_execute_tools` builds, the loop, the answer pass, the finalize — is the real thing.
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
    TURN,
    hard_turn_limits,
)
from app.services.cognitive_pipeline import turn_config


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


def _tool_call(path: str):
    """One tool call, with DIFFERENT arguments each round.

    The arguments must differ: the guard blocks the fourth identical call in a row, and a blocked
    round would end the loop for the wrong reason (that path is covered by its own test).
    """
    return [SimpleNamespace(
        index=0, id="call_1",
        function=SimpleNamespace(name="file_info", arguments=json.dumps({"path": path})),
    )]


def _done_payload(frames):
    done = [f for f in frames if '"done": true' in f]
    if not done:
        return None
    body = done[-1][6:] if done[-1].startswith("data: ") else done[-1].split("data: ", 1)[1].strip()
    return json.loads(body)


async def _make_agent(test_session, name="Answer Pass Agent"):
    from app.infrastructure.database.models import Agent

    agent = Agent(
        name=name, provider="deepseek", model="deepseek-v4-flash",
        system_prompt="You are a test agent.", is_active=True,
    )
    test_session.add(agent)
    await test_session.commit()
    await test_session.refresh(agent)
    return agent


def _stub_tool_runner(monkeypatch, mod):
    """Stub the tool RUNNER only, so `_execute_tools` still builds the real history."""
    from app.domain.tools.execution_service import ToolExecutionResult

    async def fake_execute_tool_calls(**kwargs):
        return [
            ToolExecutionResult(
                success=True, tool_slug="file_info", tool_name=tc["name"],
                result=f"{tc.get('parsed_arguments', {}).get('path', '?')}: 12 bytes",
                call_id=tc.get("id") or "call_1",
            )
            for tc in kwargs.get("tool_calls", [])
        ]

    monkeypatch.setattr(mod, "execute_tool_calls", fake_execute_tool_calls)


def _force_route(monkeypatch, route_name: str):
    """Pin the conduit's decision: these tests are about the LOOP, not about the routing.

    Without it a turn with any content is free to be routed into a second (deep) pass, and the
    provider-call counts below would be measuring the conduit instead of the answer pass.
    """
    from app.services.cognitive_pipeline.conduit import ConduitDecision, Route

    route = getattr(Route, route_name)
    monkeypatch.setattr(
        "app.services.cognitive_pipeline.conduit.conduit_route",
        lambda **kwargs: ConduitDecision(route=route, reason="forced for the test"),
    )


@pytest.mark.anyio
async def test_a_loop_that_uses_every_round_is_asked_to_write_the_answer(
    test_session, monkeypatch, caplog,
):
    """The whole point of gap L: the work is converted into a deliverable instead of a sentence."""
    from app.api.v1.chat import llm_utils
    from app.api.v1.chat import router as mod
    from app.domain.chat.services import ChatService
    from app.infrastructure.database.models import ChatMessage

    rounds = turn_config.loop_rounds()
    agent = await _make_agent(test_session, "Exhausted Loop Agent")
    calls: list = []

    async def fake_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) <= rounds:
            return _StubStream([
                _StubChunk(finish_reason="tool_calls", tool_calls=_tool_call(f"f{len(calls)}.txt")),
            ])
        return _StubStream([
            _StubChunk(content="The answer, written from what I read."),
            _StubChunk(finish_reason="stop"),
        ])

    answer = "The answer, written from what I read."
    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)
    _stub_tool_runner(monkeypatch, mod)
    _force_route(monkeypatch, "SHALLOW")

    request = SimpleNamespace(
        agent_id=agent.id, message="read every file and summarise", session_id=None,
        attachment_ids=None, generate_title=False,
    )

    with caplog.at_level(logging.INFO):
        frames = [chunk async for chunk in mod.generate_stream(request, ChatService(test_session))]

    # 1. ONE MORE call than the loop's rounds — and that call offered no tools
    assert len(calls) == rounds + 1, (
        f"the loop never asked for an answer: {len(calls)} provider calls for {rounds} rounds"
    )
    assert not calls[-1].get("tools"), "the answer pass still offered tools"
    assert not calls[-1].get("tool_choice"), "the answer pass still set tool_choice"
    # the withheld-tools instruction rides the request (and only this one)
    assert "no further tool calls are possible" in str(calls[-1]["messages"][-1])

    # 2. the answer is what the user saw AND what the turn saved
    assert any(answer in f for f in frames), "the answer never reached the bubble"
    rows = (await test_session.execute(
        select(ChatMessage).where(ChatMessage.role == "assistant")
    )).scalars().all()
    assert rows, "the turn saved nothing"
    assert rows[-1].content == answer
    assert not (rows[-1].meta or {}).get("stopped_without_answer"), rows[-1].meta

    # 3. the stand-in sentence did NOT fire, and the turn was not reported as empty
    assert not [f for f in frames if f.startswith("event: error")]
    assert "still produced no answer" not in "".join(frames)
    assert (_done_payload(frames) or {}).get("metadata", {}).get("stopped_without_answer") is None

    # 4. the pass names itself in the log, and the turn's account counts its call
    assert any("ANSWER PASS" in r.getMessage() for r in caplog.records), (
        [r.getMessage() for r in caplog.records if "PASS" in r.getMessage()]
    )
    account = [r.getMessage() for r in caplog.records if "TURN ACCOUNT" in r.getMessage()]
    assert account, "the turn wrote no account line"
    assert f"provider_calls={rounds + 1}" in account[-1], account[-1]


@pytest.mark.anyio
async def test_a_turn_that_answers_directly_gets_no_answer_pass(test_session, monkeypatch, caplog):
    """The pass is for an EXHAUSTED loop only — a round that breaks out ends the turn as before."""
    from app.api.v1.chat import llm_utils
    from app.api.v1.chat import router as mod
    from app.domain.chat.services import ChatService

    agent = await _make_agent(test_session, "Direct Answer Agent")
    calls: list = []

    async def fake_completion(**kwargs):
        calls.append(kwargs)
        return _StubStream([
            _StubChunk(content="Answered directly."),
            _StubChunk(finish_reason="stop"),
        ])

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)
    _force_route(monkeypatch, "SHALLOW")

    request = SimpleNamespace(
        agent_id=agent.id, message="hello", session_id=None,
        attachment_ids=None, generate_title=False,
    )

    with caplog.at_level(logging.INFO):
        frames = [chunk async for chunk in mod.generate_stream(request, ChatService(test_session))]

    assert len(calls) == 1, "a turn that answered made an extra call"
    assert not any("ANSWER PASS" in r.getMessage() for r in caplog.records)


@pytest.mark.anyio
async def test_a_stopped_turn_gets_no_answer_pass(test_session, monkeypatch, caplog):
    """A hard plug ends the turn: nothing further is started, the answer pass included (D.3)."""
    from app.api.v1.chat import llm_utils
    from app.api.v1.chat import router as mod
    from app.domain.chat.services import ChatService

    agent = await _make_agent(test_session, "Stopped Loop Agent")
    calls: list = []

    async def fake_completion(**kwargs):
        calls.append(kwargs)
        return _StubStream([
            _StubChunk(finish_reason="tool_calls", tool_calls=_tool_call(f"f{len(calls)}.txt")),
        ])

    def _two_call_ceiling():
        limit = hard_turn_limits()[0]
        return (
            type(limit)(
                key="provider_calls", kind=HARD, scope=TURN, threshold=2,
                reason="This turn reached 2 calls to the provider — the ceiling.",
            ),
        )

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)
    monkeypatch.setattr(mod, "publish_warning", lambda *a, **k: None)
    monkeypatch.setattr(mod, "hard_turn_limits", _two_call_ceiling)
    _stub_tool_runner(monkeypatch, mod)

    request = SimpleNamespace(
        agent_id=agent.id, message="read everything", session_id=None,
        attachment_ids=None, generate_title=False,
    )

    with caplog.at_level(logging.ERROR):
        frames = [chunk async for chunk in mod.generate_stream(request, ChatService(test_session))]

    assert len(calls) == 2, f"the stopped turn kept calling the provider: {len(calls)}"
    assert not any("ANSWER PASS" in r.getMessage() for r in caplog.records)
    assert [f for f in frames if f.startswith("event: error")], "the turn was not stopped"


@pytest.mark.anyio
async def test_an_empty_answer_pass_still_says_why(test_session, monkeypatch, caplog):
    """The withheld-tools call can come back empty too — the turn then says so, on the row and in
    the bubble, instead of going silent."""
    from app.api.v1.chat import llm_utils
    from app.api.v1.chat import router as mod
    from app.domain.chat.services import ChatService
    from app.infrastructure.database.models import ChatMessage

    rounds = turn_config.loop_rounds()
    agent = await _make_agent(test_session, "Empty Answer Pass Agent")
    calls: list = []

    async def fake_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) <= rounds:
            return _StubStream([
                _StubChunk(finish_reason="tool_calls", tool_calls=_tool_call(f"f{len(calls)}.txt")),
            ])
        # chunks, no content, no tool calls, no stop reason — an empty completion
        return _StubStream([_StubChunk()])

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)
    _stub_tool_runner(monkeypatch, mod)
    _force_route(monkeypatch, "SHALLOW")

    request = SimpleNamespace(
        agent_id=agent.id, message="read every file", session_id=None,
        attachment_ids=None, generate_title=False,
    )

    with caplog.at_level(logging.WARNING):
        frames = [chunk async for chunk in mod.generate_stream(request, ChatService(test_session))]

    assert len(calls) == rounds + 1, "the empty answer pass did not happen"
    assert any("ANSWER PASS" in r.getMessage() and "came back empty" in r.getMessage()
               for r in caplog.records), [r.getMessage() for r in caplog.records]

    rows = (await test_session.execute(
        select(ChatMessage).where(ChatMessage.role == "assistant")
    )).scalars().all()
    assert rows, "the turn left the transcript empty"
    assert "still produced no answer" in rows[-1].content, rows[-1].content
    assert CONTINUE_SENTENCE in rows[-1].content
    assert (rows[-1].meta or {}).get("stopped_without_answer") is True
    assert any("still produced no answer" in f for f in frames), "the reason never reached the bubble"


@pytest.mark.anyio
async def test_a_hard_line_crossed_at_the_answer_pass_finishes_the_turn(
    test_session, monkeypatch, caplog,
):
    """The answer pass is the turn's LAST call: a breach there has nothing further to start, so
    the plug FINISHES the turn (D7 (b)) — the answer is kept whole and the note says a plug fired,
    with no error frame (only an ABORT has one)."""
    from app.api.v1.chat import llm_utils
    from app.api.v1.chat import router as mod
    from app.domain.chat.services import ChatService
    from app.infrastructure.database.models import ChatMessage

    rounds = turn_config.loop_rounds()
    agent = await _make_agent(test_session, "Answer Pass Plug Agent")
    calls: list = []

    async def fake_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) <= rounds:
            return _StubStream([
                _StubChunk(finish_reason="tool_calls", tool_calls=_tool_call(f"f{len(calls)}.txt")),
            ])
        return _StubStream([
            _StubChunk(content="The answer the pass wrote."),
            _StubChunk(finish_reason="stop"),
        ])

    def _ceiling_at_the_pass():
        limit = hard_turn_limits()[0]
        return (
            type(limit)(
                key="provider_calls", kind=HARD, scope=TURN, threshold=rounds + 1,
                reason=(
                    f"This turn reached {rounds + 1} calls to the provider — the ceiling "
                    f"for a single answer, so the turn stops here."
                ),
            ),
        )

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)
    monkeypatch.setattr(mod, "publish_warning", lambda *a, **k: None)
    monkeypatch.setattr(mod, "hard_turn_limits", _ceiling_at_the_pass)
    _stub_tool_runner(monkeypatch, mod)
    _force_route(monkeypatch, "SHALLOW")

    request = SimpleNamespace(
        agent_id=agent.id, message="read every file and answer", session_id=None,
        attachment_ids=None, generate_title=False,
    )

    with caplog.at_level(logging.ERROR):
        frames = [chunk async for chunk in mod.generate_stream(request, ChatService(test_session))]

    # the pass ran, and its answer is the turn's
    assert len(calls) == rounds + 1
    rows = (await test_session.execute(
        select(ChatMessage).where(ChatMessage.role == "assistant")
    )).scalars().all()
    assert rows[-1].content == "The answer the pass wrote."

    # the crossing is on the account as a FINISH, and the turn was not aborted
    crossings = [c for c in (rows[-1].meta or {}).get("limits", []) if c.get("mode") == "finish"]
    assert crossings and crossings[0]["key"] == "provider_calls", rows[-1].meta
    assert not [f for f in frames if f.startswith("event: error")], (
        "a breach with nothing left to start must not abort the turn"
    )


@pytest.mark.anyio
async def test_the_deep_pass_gets_the_same_pass_when_its_own_rounds_run_out(
    test_session, monkeypatch, caplog,
):
    """L-3: the deep pass's rounds are collected work too — its own answer replaces pass 1's."""
    from app.api.v1.chat import llm_utils
    from app.api.v1.chat import router as mod
    from app.domain.chat.services import ChatService
    from app.infrastructure.database.models import ChatMessage

    rounds = turn_config.loop_rounds()
    agent = await _make_agent(test_session, "Deep Pass Agent")
    calls: list = []

    async def fake_completion(**kwargs):
        calls.append(kwargs)
        n = len(calls)
        # 1: pass 1 opens with a tool round + prose; 2: pass 1 answers, so its loop breaks.
        if n == 1:
            return _StubStream([
                _StubChunk(content="Looking at the file now. "),
                _StubChunk(finish_reason="tool_calls", tool_calls=_tool_call("f1.txt")),
            ])
        if n == 2:
            return _StubStream([
                _StubChunk(content="A short first-pass sketch."),
                _StubChunk(finish_reason="stop"),
            ])
        # 3..3+rounds-1: the deep pass spends its own rounds on tools.
        if n <= 2 + rounds:
            return _StubStream([
                _StubChunk(finish_reason="tool_calls", tool_calls=_tool_call(f"deep{n}.txt")),
            ])
        return _StubStream([
            _StubChunk(content="The deep pass's answer from its own rounds."),
            _StubChunk(finish_reason="stop"),
        ])

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)
    monkeypatch.setattr(mod, "publish_warning", lambda *a, **k: None)
    _force_route(monkeypatch, "HYBRID")
    _stub_tool_runner(monkeypatch, mod)

    request = SimpleNamespace(
        agent_id=agent.id, message="analyze this deeply", session_id=None,
        attachment_ids=None, generate_title=False,
    )

    with caplog.at_level(logging.INFO):
        frames = [chunk async for chunk in mod.generate_stream(request, ChatService(test_session))]

    # one answer pass at the deep boundary, after the deep pass's own rounds
    assert len(calls) == 2 + rounds + 1, f"the deep pass got no answer pass: {len(calls)} calls"
    assert not calls[-1].get("tools"), "the deep answer pass still offered tools"

    rows = (await test_session.execute(
        select(ChatMessage).where(ChatMessage.role == "assistant")
    )).scalars().all()
    assert rows[-1].content == "The deep pass's answer from its own rounds.", rows[-1].content
    assert not any("deep pass empty" in r.getMessage() for r in caplog.records), (
        "the deep pass was reported empty although its answer pass wrote"
    )
