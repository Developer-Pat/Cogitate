"""Tool reliability as a number — the counts, their classes, and the denominator.

The failure this file exists to prevent (the tool-reliability arc): a turn's tool use was ONE number, `tool_calls`, with no
denominator and no failures — so "the model was offered a tool and called none"
and "no tool was ever offered" were the same reading, and a handler's refusal
reached the model as a success.

Three layers are pinned here:
* the tracker's aggregate (`attempts` / `failures_by_type` / `blocked`) and the
  rule that a REFUSAL is counted beside the calls, never inside them;
* the turn's account line carrying the tool story in one place;
* the real `generate_stream`, where the denominator comes from what actually went
  on the wire (the answer pass withholds tools and must not count as an offer).
"""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import pytest

from app.api.v1.chat.tool_call_tracker import ToolCallTracker
from app.services.cognitive_pipeline import turn_config
from app.services.cognitive_pipeline.turn_state import (
    CALLS,
    BLOCKED,
    FAILURES,
    TurnState,
    tracker_tool_counts,
)


class TestTheTrackerAggregate:
    def test_failures_are_grouped_by_class_and_the_tally_can_be_checked(self):
        tracker = ToolCallTracker()
        tracker.record_call(
            "file-manager", {"operation": "move"}, 1,
            success=False, error="Source file does not exist: 'x'", error_type="not_found",
        )
        tracker.record_call("file-info", {"path": "x"}, 1, success=True)
        # a failure nobody classified: counted, so the failure total stays honest
        tracker.record_call("jina-reader", {"url": "u"}, 2, success=False, error="boom")

        summary = tracker.get_summary()

        assert summary["total_calls"] == 3
        assert summary["attempts"] == 3
        assert summary["failures"] == 2
        assert summary["failures_by_type"] == {"not_found": 1}
        assert summary["failures_unnamed"] == 1
        assert (
            sum(summary["failures_by_type"].values()) + summary["failures_unnamed"]
            == summary["failures"]
        ), "the grouped counts and the total disagree — a reader cannot check the tally"

    def test_a_refusal_is_counted_beside_the_calls_and_never_inside_them(self):
        """F4: the guard's refusal gets a number, and `tool_calls` keeps its meaning."""
        tracker = ToolCallTracker()
        arguments = {"path": "agents/bob/notes/note.md"}

        allowed = 0
        for _ in range(3):
            should_exec, _warning, error = tracker.should_execute(
                "file-info", arguments, iteration=1
            )
            assert should_exec and error is None
            tracker.record_call("file-info", arguments, 1, success=True)
            allowed += 1

        should_exec, _warning, error = tracker.should_execute(
            "file-info", arguments, iteration=1
        )
        assert not should_exec, "the 4th identical call in a row is the guard's ceiling"
        assert error, "a refusal must say why"

        summary = tracker.get_summary()
        assert summary["total_calls"] == allowed, "a blocked call is not a call that happened"
        assert summary["blocked"] == 1
        assert summary["attempts"] == allowed + 1, "attempts = what happened + what was refused"
        assert summary["blocked_by_tool"] == {"file-info": 1}
        assert summary["failures"] == 0, "a refusal is not a failure — the call never ran"

    def test_a_tracker_without_the_summary_reports_only_what_it_has(self):
        """The delegate/stub shapes: an old tracker is read honestly, not fatally."""
        class Legacy:
            total_calls = {"datetime": 2, "file-info": 1}
            consecutive_counts: dict = {}
            last_call: dict = {}
            call_history: list = []

        counts = tracker_tool_counts(Legacy())
        assert counts == {CALLS: 3, BLOCKED: 0, FAILURES: 0}
        assert tracker_tool_counts(None) == {CALLS: 0, BLOCKED: 0, FAILURES: 0}


class TestTheAccountLine:
    def test_the_tool_story_reads_in_one_place(self):
        state = TurnState()
        tracker = ToolCallTracker()
        tracker.record_call("file-info", {"path": "a"}, 1, success=True)
        tracker.record_call(
            "file-manager", {"operation": "move"}, 1,
            success=False, error="Source file does not exist: 'x'", error_type="not_found",
        )
        state.observe_tools_offered([{"function": {"name": "file-info"}}])
        state.observe_tools_offered([])  # the answer pass: tools withheld
        state.observe_tool_calls(tracker)

        line = state.account_line(session_id=1, model="m", provider="p")

        assert "tools_offered=1" in line
        assert "tool_calls=2" in line
        assert "tool_calls_blocked=0" in line
        assert "tool_failures=1" in line

    def test_an_absent_offer_is_not_a_zero_the_line_invents(self):
        """`tools_offered=0` means the turn genuinely offered nothing."""
        state = TurnState()
        state.observe_tools_offered(None)
        assert state.tools_offered == 0
        assert "tools_offered=0" in state.account_line()

    def test_the_readings_are_not_judged_quantities(self):
        """A counter that exists to be REPORTED must not be armable as a limit."""
        from app.services.cognitive_pipeline.turn_state import KEYS

        assert "tools_offered" not in KEYS
        assert "tool_calls_blocked" not in KEYS
        assert "tool_failures" not in KEYS
        snapshot = TurnState().snapshot()
        assert "tools_offered" not in snapshot


# ---------------------------------------------------------------------------
# F3: the handler's OWN verdict, and the wrapper that used to stamp over it.
# ---------------------------------------------------------------------------


class TestTheHandlersVerdict:
    def test_a_handler_that_refuses_is_read_as_a_failure(self):
        from app.domain.tools.execution_service import declared_refusal

        assert declared_refusal(
            {"success": False, "error": "Source file does not exist: 'x'", "error_type": "not_found"}
        ) == ("Source file does not exist: 'x'", "not_found")

    def test_an_unclassified_refusal_keeps_no_class(self):
        """No invented class: the tracker counts these as `failures_unnamed`."""
        from app.domain.tools.execution_service import declared_refusal

        assert declared_refusal({"success": False, "error": "Not a file: x"}) == ("Not a file: x", None)
        assert declared_refusal({"success": False}) == ("the tool reported a failure", None)

    def test_a_successful_payload_and_a_plain_dict_are_not_refusals(self):
        from app.domain.tools.execution_service import declared_refusal

        assert declared_refusal({"success": True, "result": "ok"}) is None
        assert declared_refusal({"time": "12:00"}) is None          # no verdict at all
        assert declared_refusal(["not", "a", "dict"]) is None
        assert declared_refusal("done") is None
        assert declared_refusal(None) is None


@pytest.mark.anyio
async def test_the_real_service_reports_a_handlers_refusal_as_a_failure(test_session, monkeypatch):
    """The end-to-end half: no LLM, and none of the DB's seeding to depend on.

    `datetime` with an unsupported `location` returns the house refusal — the same
    shape dozens of registry handlers use — which is deterministic and side-effect
    free. The service's TOOL LOOKUP is faked (the shared test database is not ours to
    assume a row in), and everything past it is the real code: the real registry, the
    real handler, the real verdict mapping. Before F3 this call came back
    `success=True, error=None, error_type=None` — the refusal buried in `result` —
    which is the reading the model received.
    """
    from types import SimpleNamespace

    from app.domain.tools.execution_service import ToolExecutionService
    from app.domain.tools.registry import init_default_registry

    init_default_registry()

    class _FakeToolService:
        async def get_tool_by_slug(self, slug):
            # Only the attributes this path really reads — the shared test database
            # holds no row for this slug, and the test should not depend on one.
            return SimpleNamespace(
                id=1, slug=slug, name="DateTime", capability="datetime",
                access_tier=None, arguments_schema={}, config_schema={}, type="builtin",
            )

    class _FakeAgentTools:
        async def get_agent_tool_by_slug(self, agent_id, slug):
            return None  # no explicit exclusion: the GRAS default applies

    class _FakeUsage:
        async def log_usage(self, **kwargs):
            return None

    service = ToolExecutionService(test_session)
    monkeypatch.setattr(service, "tool_service", _FakeToolService())
    monkeypatch.setattr(service, "agent_tool_service", _FakeAgentTools())
    monkeypatch.setattr(service, "usage_service", _FakeUsage())

    async def _no_kits(agent_id):
        return None

    monkeypatch.setattr(service, "_toolkit_slugs_for_agent", _no_kits)

    result = await service.execute_tool_for_agent(
        agent_id=1,
        tool_slug="datetime",
        arguments={"operation": "now", "location": "moon-base"},
        session_id="f3-check",
    )

    assert result.success is False, (
        f"a handler's refusal was reported as a success: {result}"
    )
    assert result.error == "capability_not_supported"
    assert result.error_type == "CapabilityError"
    # nothing the handler said is thrown away: its own payload still rides along
    assert isinstance(result.result, dict)
    assert result.result.get("success") is False
    assert result.result.get("error_details")

    # ... and the tracker the turn keeps records a FAILURE, once the class is passed
    tracker = ToolCallTracker()
    tracker.record_call(
        "datetime", {"operation": "now"}, 1,
        success=result.success, error=result.error, error_type=result.error_type,
    )
    summary = tracker.get_summary()
    assert summary["failures"] == 1
    assert summary["failures_by_type"] == {"CapabilityError": 1}


# ---------------------------------------------------------------------------
# Through the REAL stream: the denominator is what went on the wire.
# ---------------------------------------------------------------------------


class _StubChunk:
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
    """One tool call with DIFFERENT arguments each round (the guard blocks repeats)."""
    return [SimpleNamespace(
        index=0, id="call_1",
        function=SimpleNamespace(name="file_info", arguments=json.dumps({"path": path})),
    )]


async def _make_agent(test_session, name):
    from app.infrastructure.database.models import Agent

    agent = Agent(
        name=name, provider="deepseek", model="deepseek-v4-flash",
        system_prompt="You are a test agent.", is_active=True,
    )
    test_session.add(agent)
    await test_session.commit()
    await test_session.refresh(agent)
    return agent


def _stub_tool_runner(monkeypatch, mod, *, fail_first: bool = False):
    """Stub the tool RUNNER only — the loop, the tracker and the line stay real."""
    from app.domain.tools.execution_service import ToolExecutionResult

    async def fake_execute_tool_calls(**kwargs):
        results = []
        for index, tc in enumerate(kwargs.get("tool_calls", [])):
            path = tc.get("parsed_arguments", {}).get("path", "?")
            if fail_first and index == 0:
                results.append(ToolExecutionResult(
                    success=False, tool_slug="file_info", tool_name=tc["name"],
                    error=f"Source file does not exist: '{path}'", error_type="not_found",
                    call_id=tc.get("id") or "call_1",
                ))
            else:
                results.append(ToolExecutionResult(
                    success=True, tool_slug="file_info", tool_name=tc["name"],
                    result=f"{path}: 12 bytes", call_id=tc.get("id") or "call_1",
                ))
        return results

    monkeypatch.setattr(mod, "execute_tool_calls", fake_execute_tool_calls)


def _force_route(monkeypatch, route_name: str):
    from app.services.cognitive_pipeline.conduit import ConduitDecision, Route

    route = getattr(Route, route_name)
    monkeypatch.setattr(
        "app.services.cognitive_pipeline.conduit.conduit_route",
        lambda **kwargs: ConduitDecision(route=route, reason="forced for the test"),
    )


async def _run_turn(test_session, monkeypatch, caplog, *, fail_first: bool):
    """One real turn that spends every round on tools, then is asked to answer."""
    from app.api.v1.chat import llm_utils
    from app.api.v1.chat import router as mod
    from app.domain.chat.services import ChatService

    rounds = turn_config.loop_rounds()
    agent = await _make_agent(test_session, f"Tool Numbers Agent {fail_first}")
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

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)
    _stub_tool_runner(monkeypatch, mod, fail_first=fail_first)
    _force_route(monkeypatch, "SHALLOW")

    request = SimpleNamespace(
        agent_id=agent.id, message="read every file and summarise", session_id=None,
        attachment_ids=None, generate_title=False,
    )

    with caplog.at_level(logging.INFO):
        frames = [chunk async for chunk in mod.generate_stream(request, ChatService(test_session))]

    account = [r.getMessage() for r in caplog.records if "TURN ACCOUNT" in r.getMessage()]
    return rounds, calls, frames, account


@pytest.mark.anyio
async def test_the_line_separates_calls_from_offers(
    test_session, monkeypatch, caplog,
):
    """The count is of the WIRE: `tools_offered` equals the calls that carried tools.

    Deliberately NOT pinned to a fixed number: whether this agent is offered tools
    depends on what the shared test database holds by the time the test runs (a tool
    row seeded by another module is enough — the GRAS/toolkit default then offers a
    full surface). What must hold is the RELATION: the line's denominator counts the
    calls that actually carried a tools array, so `tool_calls` above it can be read
    against something. The answer pass withholds tools and must add nothing.
    """
    rounds, calls, _frames, account = await _run_turn(
        test_session, monkeypatch, caplog, fail_first=False
    )

    assert account, "the turn wrote no account line"
    line = account[-1]
    offered = sum(1 for call in calls if call.get("tools"))
    assert f"tools_offered={offered}" in line, (
        f"the denominator does not match the wire: {offered} calls carried tools\n{line}"
    )
    assert f"tool_calls={rounds}" in line, line
    assert "tool_calls_blocked=0" in line, line
    assert "tool_failures=0" in line, line
    # the answer pass must not count as an offer (there was nothing to decline)
    assert not calls[-1].get("tools"), "the answer pass offered tools"


def _done_payload(frames):
    """The done frame's JSON body, parsed (the turn's metadata rides it)."""
    done = [f for f in frames if '"done": true' in f]
    if not done:
        return None
    body = done[-1][6:] if done[-1].startswith("data: ") else done[-1].split("data: ", 1)[1].strip()
    return json.loads(body)


@pytest.mark.anyio
async def test_the_tool_summary_reaches_the_row_and_the_frame(
    test_session, monkeypatch, caplog,
):
    """F5: the numbers survive a reload, and sit where the frontend already reads.

    Before this, the summary was written at the done frame's TOP level as a sibling of
    `metadata` (no reader anywhere: not the frontend, not the tests) and never reached
    the saved row at all — so a reloaded turn knew nothing about its tools. Both halves
    are asserted here, with the failing class included, because a count without its
    class is the half the arc was missing.
    """
    from sqlalchemy import select

    from app.infrastructure.database.models import ChatMessage

    rounds, _calls, frames, _account = await _run_turn(
        test_session, monkeypatch, caplog, fail_first=True
    )

    done = _done_payload(frames)
    assert done, "the turn streamed no done frame"
    summary = (done.get("metadata") or {}).get("tool_call_summary")
    assert summary, f"the frame's metadata carries no tool summary: {done.get('metadata')}"
    assert summary["total_calls"] == rounds
    assert summary["attempts"] == rounds
    assert summary["failures"] == rounds
    assert summary["failures_by_type"] == {"not_found": rounds}
    assert "tool_call_summary" not in done, (
        "the orphan top-level key is back: the summary belongs INSIDE metadata"
    )

    rows = (await test_session.execute(
        select(ChatMessage).where(ChatMessage.role == "assistant")
    )).scalars().all()
    assert rows, "the turn saved nothing"
    row_summary = (rows[-1].meta or {}).get("tool_call_summary")
    assert row_summary, f"the saved row carries no tool summary: {rows[-1].meta}"
    assert row_summary["failures_by_type"] == {"not_found": rounds}
    assert (
        sum(row_summary["failures_by_type"].values()) + row_summary["failures_unnamed"]
        == row_summary["failures"]
    ), "the row's grouped counts do not add up to its own total"


@pytest.mark.anyio
async def test_a_failing_tool_reaches_the_line_with_its_count(
    test_session, monkeypatch, caplog,
):
    """A tool that ran and refused is a FAILURE — and it is visible from the line."""
    rounds, _calls, frames, account = await _run_turn(
        test_session, monkeypatch, caplog, fail_first=True
    )

    line = account[-1]
    assert f"tool_calls={rounds}" in line, line
    assert f"tool_failures={rounds}" in line, (
        f"every round's tool refused and none of them reached the count: {line}"
    )
    # the failure is not only counted: the frame the turn streamed says so too
    assert '"success": false' in "".join(frames), (
        "the failing tool result never reached the bubble's frames"
    )


class TestTheTurnKeepsWhatItSent:
    """G-A ii — the turn's account holds the budget that went on the wire.

    `llm_spec.max_output` is what an agent WOULD send. This is what a turn DID, and
    until now it had no home outside the effective-budget LOG LINE, which rotates.
    """

    def test_the_last_request_wins_and_the_shape_is_the_rows(self):
        state = TurnState()

        assert state.budget is None, "a turn that has made no call has sent nothing"

        state.observe_budget(16000, 8192, "thinking_floor", "pass1")
        assert state.budget == {
            "sent": 16000, "declared": 8192,
            "reason": "thinking_floor", "path": "pass1",
        }

        # a hybrid turn sends twice; the number behind the answer is the last one
        state.observe_budget(16000, 8192, "deep_min", "deep")
        assert state.budget is not None
        assert state.budget["path"] == "deep"
        assert state.budget["reason"] == "deep_min"

    def test_an_undecided_budget_records_nothing(self):
        state = TurnState()
        state.observe_budget(None, None, "", "default")
        assert state.budget is None

    def test_a_none_declaration_is_recorded_as_none_not_invented(self):
        state = TurnState()
        state.observe_budget(4096, None, "no_declared_budget", "default")
        assert state.budget is not None
        assert state.budget["declared"] is None
        assert state.budget["sent"] == 4096


@pytest.mark.anyio
async def test_the_sent_budget_reaches_the_row_and_the_frame(
    test_session, monkeypatch, caplog,
):
    """The observation survives the turn on BOTH surfaces a reload reads.

    The declaration is on the agent row (a read the page already makes); the number
    a turn actually carried has to come from the turn — and the reload whitelist is
    what keeps it (the same lesson `limits` records: the row had it, the endpoint
    dropped it, and the note vanished at the next reload).
    """
    from sqlalchemy import select

    from app.infrastructure.database.models import ChatMessage

    _rounds, _calls, frames, _account = await _run_turn(
        test_session, monkeypatch, caplog, fail_first=False
    )

    done = _done_payload(frames)
    assert done, "the turn streamed no done frame"
    budget = (done.get("metadata") or {}).get("budget")
    assert budget, f"the frame's metadata carries no budget: {done.get('metadata')}"
    assert set(budget) == {"sent", "declared", "reason", "path"}
    assert budget["sent"] > 0 and budget["reason"] and budget["path"], (
        "the number arrived without its why — two numbers with no reason are a bug report"
    )
    assert budget["reason"] in {
        "declared", "runtime_override", "no_declared_budget", "thinking_floor",
        "thinking_mandatory", "fast_policy", "deep_min", "window_clamp",
    }, f"an unnamed reason: {budget['reason']}"
    assert "budget" not in done, (
        "the budget belongs INSIDE metadata — where the frontend reads — not top-level"
    )

    rows = (await test_session.execute(
        select(ChatMessage).where(ChatMessage.role == "assistant")
    )).scalars().all()
    assert rows, "the turn saved nothing"
    assert (rows[-1].meta or {}).get("budget") == budget, (
        "the row and the frame disagree about what the wire carried"
    )
