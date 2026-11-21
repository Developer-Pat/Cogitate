"""ONE TURN, TWO ANSWERS — the replace frame, and brevity stops earning a second call.

The failure this file pins (measured on a live install, 2026-11-20): a turn answered `Ready.`, the
conduit routed HYBRID because the answer was under 500 characters, a second 6,086-token prompt
answered `Ready.` again, and the client — which can only append — showed `Ready.Ready.` while the
saved row held `Ready.`.

Two halves, ruled together (A + B):

* **A — the wire.** The server replaces the answer at several sites (a deep round, the deep answer
  pass, the main loop's answer pass). It now emits a REPLACE frame immediately before the superseding
  pass's first content chunk, and the client drops what it holds. Lazy, so a pass that comes back
  EMPTY replaces nothing — the answer on screen survives, which is the server's own rule.
* **B — the trigger.** A short answer that answers is a COMPLETE answer. The deep pass now needs
  intent (a deep keyword) or a measured shortfall (the provider cut the answer at the output budget).

These drive the REAL `generate_stream`, so the frame order, the saved row and the provider-call count
are all pinned end to end. The provider is stubbed; nothing else is.
"""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import pytest
from sqlalchemy import select

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
    return [SimpleNamespace(
        index=0, id="call_1",
        function=SimpleNamespace(name="file_info", arguments=json.dumps({"path": path})),
    )]


def _deltas(frames):
    """Every delta the client would parse, in order. Non-frame lines are skipped."""
    out = []
    for frame in frames:
        if not frame.startswith("data: "):
            continue
        try:
            payload = json.loads(frame[6:])
        except json.JSONDecodeError:
            continue
        choices = payload.get("choices") or []
        if not choices:
            continue
        out.append(choices[0].get("delta") or {})
    return out


def _client_bubble(frames) -> str:
    """The bubble's text, built the way `StreamingService` builds it.

    THE RULE UNDER TEST: `content` is appended, and a `replace` delta RESETS the accumulator. If the
    two halves ever disagree again, this replay is where the disagreement shows up.
    """
    text = ""
    for delta in _deltas(frames):
        if delta.get("replace"):
            text = ""
            continue
        chunk = delta.get("content")
        if chunk:
            text += chunk
    return text


def _replace_frames(frames):
    return [i for i, d in enumerate(_deltas(frames)) if d.get("replace")]


def _done_payload(frames):
    done = [f for f in frames if '"done": true' in f]
    if not done:
        return None
    body = done[-1][6:] if done[-1].startswith("data: ") else done[-1].split("data: ", 1)[1].strip()
    return json.loads(body)


async def _make_agent(test_session, name="Replace Frame Agent"):
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


def _force_executor(monkeypatch, mod, executor: str):
    """The turn's strategy is a PROFILE fact; these tests are about the wire and the trigger."""
    from app.services.cognitive_pipeline.models import PipelineConfig

    async def fake_config(db, context):
        return PipelineConfig(executor=executor)

    monkeypatch.setattr(mod, "_resolve_pipeline_config", fake_config)


def _force_route(monkeypatch, route_name: str):
    from app.services.cognitive_pipeline.conduit import ConduitDecision, Route

    route = getattr(Route, route_name)
    monkeypatch.setattr(
        "app.services.cognitive_pipeline.conduit.conduit_route",
        lambda **kwargs: ConduitDecision(route=route, reason="forced for the test"),
    )


async def _saved_answer(test_session) -> str:
    from app.infrastructure.database.models import ChatMessage

    rows = (await test_session.execute(
        select(ChatMessage).where(ChatMessage.role == "assistant")
    )).scalars().all()
    assert rows, "the turn saved nothing"
    return rows[-1].content


def _request(agent, message):
    return SimpleNamespace(
        agent_id=agent.id, message=message, session_id=None,
        attachment_ids=None, generate_title=False,
    )


@pytest.mark.anyio
async def test_a_short_answer_on_a_hybrid_profile_is_asked_once(test_session, monkeypatch, caplog):
    """THE REPORTED BUG, pinned. `Ready.` used to buy a second 6,086-token prompt.

    One call. One answer. The bubble and the row agree, and no replace frame is needed because
    nothing was superseded — there is nothing to supersede.
    """
    from app.api.v1.chat import llm_utils
    from app.api.v1.chat import router as mod
    from app.domain.chat.services import ChatService

    agent = await _make_agent(test_session, "Brief Answer Agent")
    calls: list = []

    async def fake_completion(**kwargs):
        calls.append(kwargs)
        return _StubStream([_StubChunk(content="Ready."), _StubChunk(finish_reason="stop")])

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)
    _force_executor(monkeypatch, mod, "hybrid")

    with caplog.at_level(logging.INFO):
        frames = [
            chunk async for chunk in
            mod.generate_stream(_request(agent, "Bob, one word: ready?"), ChatService(test_session))
        ]

    assert len(calls) == 1, f"brevity still buys a second call: {len(calls)} provider calls"
    assert _client_bubble(frames) == "Ready."
    assert _replace_frames(frames) == [], "a turn that answered once replaced its answer"
    assert await _saved_answer(test_session) == "Ready."
    account = [r.getMessage() for r in caplog.records if "TURN ACCOUNT" in r.getMessage()]
    assert account and "provider_calls=1" in account[-1], account[-1]
    decision = [r.getMessage() for r in caplog.records if "Conduit decision" in r.getMessage()]
    assert decision and "route=shallow" in decision[-1], decision[-1]


@pytest.mark.anyio
async def test_an_intent_word_still_earns_the_deep_pass(test_session, monkeypatch, caplog):
    """B removes brevity, not depth: a question that ASKS for depth still gets its second pass."""
    from app.api.v1.chat import llm_utils
    from app.api.v1.chat import router as mod
    from app.domain.chat.services import ChatService

    agent = await _make_agent(test_session, "Intent Agent")
    calls: list = []

    async def fake_completion(**kwargs):
        calls.append(kwargs)
        return _StubStream([_StubChunk(content="Blue."), _StubChunk(finish_reason="stop")])

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)
    _force_executor(monkeypatch, mod, "hybrid")

    with caplog.at_level(logging.INFO):
        frames = [
            chunk async for chunk in
            mod.generate_stream(_request(agent, "Explain why the sky is blue"), ChatService(test_session))
        ]

    assert len(calls) == 2, calls
    decision = [r.getMessage() for r in caplog.records if "Conduit decision" in r.getMessage()]
    assert decision and "deep_keywords=True" in decision[-1], decision[-1]
    assert "short=" not in decision[-1], "the ruled-out brevity reason is still on the wire"
    # the second pass answered the same text here, so the bubble is ONE copy of it
    assert _client_bubble(frames) == "Blue."


@pytest.mark.anyio
async def test_the_deep_pass_supersedes_the_first_in_the_bubble(test_session, monkeypatch, caplog):
    """A's whole job: the second answer REPLACES the first on screen, as it already did in the row."""
    from app.api.v1.chat import llm_utils
    from app.api.v1.chat import router as mod
    from app.domain.chat.services import ChatService

    agent = await _make_agent(test_session, "Superseded Agent")
    calls: list = []
    deep_answer = "Because Rayleigh scattering prefers short wavelengths."

    async def fake_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _StubStream([_StubChunk(content="Blue."), _StubChunk(finish_reason="stop")])
        return _StubStream([
            _StubChunk(content="Because Rayleigh scattering "),
            _StubChunk(content="prefers short wavelengths."),
            _StubChunk(finish_reason="stop"),
        ])

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)
    _force_executor(monkeypatch, mod, "hybrid")

    frames = [
        chunk async for chunk in
        mod.generate_stream(_request(agent, "Explain why the sky is blue"), ChatService(test_session))
    ]

    # ONE replace, emitted lazily — right before the deep pass's first content chunk
    replaces = _replace_frames(frames)
    assert len(replaces) == 1, f"{len(replaces)} replace frames: {_deltas(frames)}"
    deltas = _deltas(frames)
    first_deep = next(
        i for i, d in enumerate(deltas)
        if d.get("content") == "Because Rayleigh scattering "
    )
    assert replaces[0] < first_deep, "the replace arrived after the text it should have cleared"

    # the bubble is the deep answer ALONE — that is the defect this frame removes
    assert _client_bubble(frames) == deep_answer
    assert _client_bubble(frames) != "Blue." + deep_answer
    assert await _saved_answer(test_session) == deep_answer


@pytest.mark.anyio
async def test_a_deep_pass_that_comes_back_empty_replaces_nothing(test_session, monkeypatch, caplog):
    """The lazy half: no content from the superseding pass means NO reset.

    The server keeps the first pass when the deep pass is empty, so a reset here would leave a blank
    bubble beside a correct row — a worse defect than the duplication it fixed.
    """
    from app.api.v1.chat import llm_utils
    from app.api.v1.chat import router as mod
    from app.domain.chat.services import ChatService

    agent = await _make_agent(test_session, "Empty Deep Agent")
    calls: list = []

    async def fake_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _StubStream([_StubChunk(content="Blue."), _StubChunk(finish_reason="stop")])
        return _StubStream([_StubChunk(finish_reason="stop")])

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)
    _force_executor(monkeypatch, mod, "hybrid")

    with caplog.at_level(logging.INFO):
        frames = [
            chunk async for chunk in
            mod.generate_stream(_request(agent, "Explain why the sky is blue"), ChatService(test_session))
        ]

    assert len(calls) == 2, calls
    assert _replace_frames(frames) == [], "an empty deep pass cleared the answer on screen"
    assert _client_bubble(frames) == "Blue."
    assert await _saved_answer(test_session) == "Blue."
    assert any("deep pass empty" in r.getMessage() for r in caplog.records), (
        [r.getMessage() for r in caplog.records if "HYBRID" in r.getMessage()]
    )


@pytest.mark.anyio
async def test_the_answer_pass_supersedes_the_loops_narration(test_session, monkeypatch, caplog):
    """The same class in the MAIN loop: a narration round must not survive beside the answer.

    Round 1 says what it is about to do and calls a tool; every later round calls tools too, so the
    loop exhausts and gap L's answer pass writes the deliverable. The row keeps the deliverable, and
    now so does the bubble.
    """
    from app.api.v1.chat import llm_utils
    from app.api.v1.chat import router as mod
    from app.domain.chat.services import ChatService

    rounds = turn_config.loop_rounds()
    agent = await _make_agent(test_session, "Narrating Agent")
    calls: list = []
    answer = "The file is twelve bytes."

    async def fake_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) > rounds:
            return _StubStream([_StubChunk(content=answer), _StubChunk(finish_reason="stop")])
        if len(calls) == 1:
            return _StubStream([
                _StubChunk(content="Let me read that file first."),
                _StubChunk(finish_reason="tool_calls", tool_calls=_tool_call("a.txt")),
            ])
        return _StubStream([
            _StubChunk(finish_reason="tool_calls", tool_calls=_tool_call(f"f{len(calls)}.txt")),
        ])

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)
    _stub_tool_runner(monkeypatch, mod)
    _force_executor(monkeypatch, mod, "hybrid")
    _force_route(monkeypatch, "SHALLOW")

    frames = [
        chunk async for chunk in
        mod.generate_stream(_request(agent, "how big is a.txt"), ChatService(test_session))
    ]

    assert len(calls) == rounds + 1, calls
    assert _client_bubble(frames) == answer, "the narration survived beside the answer"
    assert len(_replace_frames(frames)) == 1, _deltas(frames)
    assert await _saved_answer(test_session) == answer


@pytest.mark.anyio
async def test_the_replace_frame_is_a_delta_the_client_can_parse():
    """The frame's SHAPE is the contract: `choices[0].delta.replace`, nothing else.

    A frame in any other shape renders nothing at all (measured once already — see `_content_frame`),
    so the shape is asserted rather than assumed.
    """
    from app.api.v1.chat.router import _replace_frame

    frame = _replace_frame()
    assert frame.startswith("data: ") and frame.endswith("\n\n")
    payload = json.loads(frame[6:])
    assert payload == {"choices": [{"delta": {"replace": True}}]}
