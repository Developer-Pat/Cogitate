"""The truncation-signal tests — a cut answer must SAY it was cut.

Bob's forecast/beat sessions were cut mid-sentence (issues/
forecast-truncation-2026-09-22.md, reports/issues/output-truncation-
2026-09-17.md) and NOTHING in the app knew: the streamer read only
content/tool_calls, so `choices[0].finish_reason` — the provider's
"I hit max_tokens and stopped" — was dropped on the floor. The saved
row, the done frame and the bubble all presented a cut answer as a
finished one; the only thing that ever noticed was the frontend's
token ESTIMATE (StreamingService, "Response truncated (token count
fallback)"), which fires only when the local count reaches the cap.

THE TESTS are discriminating: each fails when its fix is reverted —
the wrapper stops capturing the stop reason, or finalize stops
reporting it.
"""

import inspect
import json
import time
from types import SimpleNamespace

import pytest


class _FakeChunk:
    """A stream chunk carrying a stop reason (finish_reason)."""

    def __init__(self, content: str = "", finish_reason=None, tool_calls=None):
        self.choices = [
            SimpleNamespace(
                delta=SimpleNamespace(
                    content=content, tool_calls=tool_calls,
                    reasoning="", reasoning_content="",
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


def _make_context():
    return SimpleNamespace(
        session_id=115,
        session=SimpleNamespace(id=115, title="Local Weather 10-Day Forecast"),
        agent=SimpleNamespace(name="Bob", description="", workspace_key="bob"),
        agent_id=19,
        agent_name="Bob",
        model="openrouter/inclusionai/ling-3.0-flash",
        provider="openrouter",
        messages=[{"role": "user", "content": "Check the 10 day forecast."}],
        messages_count=1,
    )


class _FakeLogger:
    def log_stream_started(self, *a, **k): pass
    def log_first_chunk(self, *a, **k): pass
    def log_stream_completed(self, *a, **k): pass
    def log_stream_open_failed(self, *a, **k): pass
    def log_final_response(self, *a, **k): pass
    def log_usage(self, *a, **k): pass


class _FakeService:
    def _estimate_tokens(self, s): return len(s or "") // 4
    async def _log_usage(self, **k): pass


class _FakeDB:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass

    async def commit(self):
        """The turn's phase boundary — the real session commits its writes here
        rather than leaving them for the response teardown."""
        self.commits += 1


async def _run_wrapper(monkeypatch, chunks):
    """Drive the real streaming wrapper over a fake stream."""
    from app.api.v1.chat import router as mod
    from app.api.v1.chat import llm_utils

    async def fake_completion(**kwargs):
        return _FakeStream(chunks)

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)

    holder = {"result": None}
    gen = mod._stream_llm_response(
        {"messages": [], "max_tokens": 2000}, _make_context(), _FakeLogger(),
        0.0, _FakeService(), holder,
    )
    [c async for c in gen]
    return holder


# ---------------------------------------------------------------------------
# 1. THE WRAPPER: the provider's stop reason is captured, not dropped
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_wrapper_captures_a_budget_cut(monkeypatch):
    """A stream that ends with finish_reason='length' must be recorded
    as truncated — the field the whole signal chain hangs off."""
    holder = await _run_wrapper(monkeypatch, [
        _FakeChunk(content="## 10-Day Forecast — Omaha, NE\n\n| Day |"),
        _FakeChunk(content=""),          # the final chunk: no content
        _FakeChunk(finish_reason="length"),
    ])

    result = holder["result"]
    assert result is not None
    assert result.finish_reason == "length"
    assert result.is_truncated is True
    # the content that DID arrive is kept (nothing is discarded)
    assert "10-Day Forecast" in result.accumulated_content


@pytest.mark.anyio
async def test_wrapper_clean_stop_is_not_truncation(monkeypatch):
    """finish_reason='stop' is a FINISHED answer — never flagged (the
    false-positive guard: every healthy turn would otherwise warn)."""
    holder = await _run_wrapper(monkeypatch, [
        _FakeChunk(content="Omaha: 71F, cloudy. Full forecast below."),
        _FakeChunk(finish_reason="stop"),
    ])

    result = holder["result"]
    assert result.finish_reason == "stop"
    assert result.is_truncated is False


@pytest.mark.anyio
async def test_wrapper_keeps_the_last_stop_reason(monkeypatch):
    """Streaming deltas carry finish_reason=None; the LAST non-empty
    value is the stream's verdict and must win."""
    holder = await _run_wrapper(monkeypatch, [
        _FakeChunk(content="The wet stretch "),
        _FakeChunk(content="before conditions", finish_reason=None),
        _FakeChunk(finish_reason="length"),
    ])

    assert holder["result"].finish_reason == "length"
    assert holder["result"].is_truncated is True


@pytest.mark.anyio
async def test_wrapper_without_a_stop_reason_is_silent(monkeypatch):
    """A provider that never sends finish_reason (some local servers)
    leaves the flag empty — no truncation is CLAIMED without evidence."""
    holder = await _run_wrapper(monkeypatch, [_FakeChunk(content="short answer")])

    assert holder["result"].finish_reason == ""
    assert holder["result"].is_truncated is False


# ---------------------------------------------------------------------------
# 2. FINALIZE: the flag rides the done frame AND the saved row
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_finalize_reports_truncation():
    """finish_reason='length' at finalize -> metadata.truncated on the
    done frame (what the frontend's truncation notice reads) and on the
    persisted row (so a reloaded turn still says it was cut)."""
    from app.api.v1.chat.finalization import finalize_response
    from app.api.v1.chat.schemas import StreamResult

    db = _FakeDB()
    meta = await finalize_response(
        context=_make_context(),
        result=StreamResult(
            chunk_count=357, accumulated_content="| Sun 9", tool_calls=[],
            has_content=True, finish_reason="length",
        ),
        tool_results=[],
        request=SimpleNamespace(generate_title=False),
        service=_FakeService(),
        db=db,
        logger_service=_FakeLogger(),
        start_time=time.time(),
        final_content="| Sun 9",
    )

    frame_meta = meta["metadata"]
    assert frame_meta["truncated"] is True
    assert frame_meta["truncationReason"] == "max_tokens"
    # the cut answer is still saved (truncation is reported, not thrown away)
    assert len(db.added) == 1
    assert db.added[0].meta["truncated"] is True
    # and that row was COMMITTED here: the turn's writes end at their phase
    # boundary, not at the response's teardown
    assert db.commits == 1


@pytest.mark.anyio
async def test_finalize_healthy_turn_carries_no_truncation():
    """A finished answer must not carry the flag — the notice never
    fires on a complete response."""
    from app.api.v1.chat.finalization import finalize_response
    from app.api.v1.chat.schemas import StreamResult

    db = _FakeDB()
    meta = await finalize_response(
        context=_make_context(),
        result=StreamResult(
            chunk_count=10, accumulated_content="A complete answer.",
            tool_calls=[], has_content=True, finish_reason="stop",
        ),
        tool_results=[],
        request=SimpleNamespace(generate_title=False),
        service=_FakeService(),
        db=db,
        logger_service=_FakeLogger(),
        start_time=time.time(),
        final_content="A complete answer.",
    )

    assert "truncated" not in meta["metadata"]
    assert "truncated" not in db.added[0].meta
    # the healthy turn's row is committed at the same boundary as the cut one's
    assert db.commits == 1


# ---------------------------------------------------------------------------
# 3. THE WIRING PIN: the router hands the LAST stream's stop reason over
# ---------------------------------------------------------------------------

def test_router_propagates_the_stop_reason_into_finalize():
    """The wrapper can capture the reason and finalize can report it —
    and the turn still reads as complete if the router never passes it
    between them. Pin the handover (main loop AND conduit deep pass
    assign `stream_result`; it is the last stream that ended the turn).
    """
    import app.api.v1.chat.router as mod

    src = inspect.getsource(mod)
    assert '_finish = getattr(chunk.choices[0], \'finish_reason\', None)' in src
    assert "finish_reason=_last_finish_reason," in src
    assert '_last_finish_reason = getattr(_last_result, "finish_reason", "")' in src
    assert "OUTPUT TRUNCATED (finish_reason=length)" in src


# ---------------------------------------------------------------------------
# 4. END-TO-END: the done frame the browser reads carries the flag
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_generate_stream_done_frame_reports_truncation(test_session, monkeypatch):
    """Drive the REAL generate_stream with a budget-cut stream and read
    the frame the frontend parses: `done` + `metadata.truncated`.

    This is the user-visible half of the fix — the frontend's truncation
    notice hangs off exactly this field (StreamingService.processSSELine
    -> showTruncationNotification), so a cut answer now says it was cut
    instead of passing for a complete one.
    """
    from app.api.v1.chat import router as mod
    from app.api.v1.chat.schemas import StreamResult
    from app.domain.chat.services import ChatService
    from app.infrastructure.database.models import Agent

    agent = Agent(
        name="Truncated Agent",
        provider="deepseek",
        model="deepseek-v4-flash",
        system_prompt="You are a test agent.",
        is_active=True,
    )
    test_session.add(agent)
    await test_session.commit()
    await test_session.refresh(agent)

    async def fake_stream(request_kwargs, context, logger_service, start_time, service,
                     result_holder, path=""):
        result_holder["result"] = StreamResult(
            chunk_count=357, accumulated_content="## 10-Day Forecast\n\n| Sun 9",
            tool_calls=[], has_content=True, finish_reason="length",
        )
        result_holder["empty_completion"] = False
        return
        yield  # pragma: no cover — makes this an async generator

    monkeypatch.setattr(mod, "_stream_llm_response", fake_stream)

    request = SimpleNamespace(
        agent_id=agent.id,
        message="Check the 10 day forecast.",
        session_id=None,
        attachment_ids=None,
        generate_title=False,
    )
    service = ChatService(test_session)
    frames = [chunk async for chunk in mod.generate_stream(request, service)]

    done_frames = [f for f in frames if '"done": true' in f]
    assert done_frames, f"no done frame in the stream: {frames[-5:]}"
    payload = json.loads(done_frames[-1].split("data: ", 1)[1].strip())

    assert payload["metadata"]["truncated"] is True
    assert payload["metadata"]["truncationReason"] == "max_tokens"


# ---------------------------------------------------------------------------
# 5. THE LOG RECORD: every stream says why it ended
# ---------------------------------------------------------------------------

def test_stream_completed_log_carries_the_stop_reason():
    """The structured STREAM COMPLETED line records the stop reason, so a
    cut answer and a finished one no longer log identically (the gap that
    made Bob's truncation unattributable from the log)."""
    from app.api.v1.chat.logging_service import ChatLoggingService
    from app.api.v1.chat.schemas import StreamResult

    class _Capture:
        def __init__(self):
            self.records = []

        def info(self, msg, extra=None):
            self.records.append((msg, extra))

    ctx = {"session_id": 115, "agent_id": 19, "model": "m", "provider": "p"}

    svc = ChatLoggingService()
    svc.logger = _Capture()
    svc.log_stream_completed(
        ctx,
        StreamResult(
            chunk_count=357, accumulated_content="| Sun 9",
            has_content=True, finish_reason="length",
        ),
    )
    extra = svc.logger.records[0][1]
    assert extra["finish_reason"] == "length"
    assert extra["truncated"] is True

    # a finished answer reads as normal, not as a truncation
    svc_ok = ChatLoggingService()
    svc_ok.logger = _Capture()
    svc_ok.log_stream_completed(
        ctx,
        StreamResult(
            chunk_count=10, accumulated_content="A complete answer.",
            has_content=True, finish_reason="stop",
        ),
    )
    assert svc_ok.logger.records[0][1]["finish_reason"] == "stop"
    assert svc_ok.logger.records[0][1]["truncated"] is False

    # a stream with no verdict logs as None (not as a silent 'stop')
    svc_none = ChatLoggingService()
    svc_none.logger = _Capture()
    svc_none.log_stream_completed(
        ctx,
        StreamResult(chunk_count=5, accumulated_content="cut mid-word", has_content=True),
    )
    assert svc_none.logger.records[0][1]["finish_reason"] is None
    assert svc_none.logger.records[0][1]["truncated"] is False
