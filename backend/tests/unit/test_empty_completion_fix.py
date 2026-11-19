"""The empty-completion fix tests — the empty assistant bubble.

Bob's session (Current Weather Forecast Omaha) showed FOUR empty
assistant bubbles (messages 40/42/48/50) — the model streamed for
15-42s and produced ZERO tokens (usage: pt~2800 ct=0). The wrapper
stored the empty result BEFORE validating, so the main loop treated
it as "conversation complete" and finalize PERSISTED an empty
message. The fix: the wrapper flags empty completions (never stores
them as usable results), the main loop retries ONCE, and finalize
refuses to persist an empty message.

THE TESTS are discriminating: each fails when its fix is reverted.
"""

import json
import time
from types import SimpleNamespace

import pytest


# ---------------------------------------------------------------------------
# 1. THE WRAPPER: an empty completion is flagged, never stored as usable
# ---------------------------------------------------------------------------

class _FakeChunk:
    """A stream chunk with choices[0].delta — empty (no content, no tools)."""

    def __init__(self, content: str = "", tool_calls=None, usage=None):
        self.choices = [SimpleNamespace(delta=SimpleNamespace(
            content=content, tool_calls=tool_calls, reasoning="", reasoning_content="",
        ))]
        self.usage = usage


def _make_context():
    return SimpleNamespace(
        session_id=99,
        session=SimpleNamespace(id=99, title="t"),
        agent=SimpleNamespace(name="Bob", description="", workspace_key="bob"),
        agent_id=19,
        agent_name="Bob",
        model="deepseek-v4-flash",
        provider="deepseek",
        messages=[{"role": "user", "content": "hi"}],
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


@pytest.mark.anyio
async def test_wrapper_flags_empty_completion(monkeypatch):
    """THE EMPTY-COMPLETION FLAG: a stream with chunks but NO content
    and NO tool calls must NOT be stored as a usable result — the
    holder carries empty_completion=True so the main loop retries."""
    from app.api.v1.chat import router as mod

    class _FakeStream:
        def __init__(self):
            self._chunks = [_FakeChunk(content="")]  # streamed but empty
        def __aiter__(self):
            self._it = iter(self._chunks)
            return self
        async def __anext__(self):
            try:
                return next(self._it)
            except StopIteration:
                raise StopAsyncIteration

    async def fake_completion(**kwargs):
        return _FakeStream()

    from app.api.v1.chat import llm_utils
    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)

    holder = {"result": None}
    gen = mod._stream_llm_response(
        {"messages": []}, _make_context(), _FakeLogger(), 0.0, _FakeService(), holder
    )
    chunks = [c async for c in gen]

    # the flag is set; no usable result was stored
    assert holder["empty_completion"] is True
    assert holder["result"] is None
    # nothing user-visible was yielded (the retry is transparent)
    assert chunks == []


@pytest.mark.anyio
async def test_wrapper_stores_real_content_normally(monkeypatch):
    """A normal completion (content present) stores the result and
    clears the flag — unchanged behavior for healthy streams."""
    from app.api.v1.chat import router as mod

    class _FakeStream:
        def __init__(self):
            self._chunks = [
                _FakeChunk(content="The current conditions in Omaha: 74F, partly cloudy."),
                _FakeChunk(content=""),
            ]
        def __aiter__(self):
            self._it = iter(self._chunks)
            return self
        async def __anext__(self):
            try:
                return next(self._it)
            except StopIteration:
                raise StopAsyncIteration

    async def fake_completion(**kwargs):
        return _FakeStream()

    from app.api.v1.chat import llm_utils
    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)

    holder = {"result": None}
    gen = mod._stream_llm_response(
        {"messages": []}, _make_context(), _FakeLogger(), 0.0, _FakeService(), holder
    )
    chunks = [c async for c in gen]

    assert holder["empty_completion"] is False
    assert holder["result"] is not None
    assert "Omaha" in holder["result"].accumulated_content
    # the content chunks were yielded (the normal SSE stream)
    assert len(chunks) == 1


# ---------------------------------------------------------------------------
# 2. THE FINALIZE GUARD: an empty message is never persisted
# ---------------------------------------------------------------------------

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


@pytest.mark.anyio
async def test_finalize_refuses_empty_message(monkeypatch):
    """THE EMPTY-MESSAGE GUARD: finalize with empty final_content must
    NOT add a ChatMessage row — the metadata carries empty_guard=True
    (the failure is trackable, the bubble never persists)."""
    from app.api.v1.chat.finalization import finalize_response
    from app.api.v1.chat.schemas import StreamResult

    db = _FakeDB()
    ctx = _make_context()
    result = StreamResult(
        chunk_count=3, accumulated_content="", tool_calls=[], has_content=False,
    )

    meta = await finalize_response(
        context=ctx,
        result=result,
        tool_results=[],
        request=SimpleNamespace(generate_title=False),
        service=_FakeService(),
        db=db,
        logger_service=_FakeLogger(),
        start_time=time.time(),
        final_content="   ",  # whitespace-only — still empty
    )

    assert db.added == []  # NOTHING persisted
    assert meta.get("metadata", {}).get("empty_guard") is True


@pytest.mark.anyio
async def test_finalize_persists_real_message(monkeypatch):
    """A real non-empty response still saves normally (the guard only
    refuses the EMPTY case — never blocks healthy turns)."""
    from app.api.v1.chat.finalization import finalize_response
    from app.api.v1.chat.schemas import StreamResult

    db = _FakeDB()
    ctx = _make_context()
    result = StreamResult(
        chunk_count=3, accumulated_content="A real answer", tool_calls=[], has_content=True,
    )

    meta = await finalize_response(
        context=ctx,
        result=result,
        tool_results=[],
        request=SimpleNamespace(generate_title=False),
        service=_FakeService(),
        db=db,
        logger_service=_FakeLogger(),
        start_time=time.time(),
        final_content="A real answer",
    )

    assert len(db.added) == 1  # persisted normally
    assert db.added[0].content == "A real answer"
    assert "empty_guard" not in meta.get("metadata", {})
    # and made durable here, rather than left for the response teardown
    assert db.commits == 1


# ---------------------------------------------------------------------------
# 3. THE MAIN-LOOP RETRY PIN (the loop must actually retry once on the flag)
# ---------------------------------------------------------------------------

def test_main_loop_retries_on_empty_flag():
    """THE RETRY WIRING: the tool loop reads the empty_completion flag
    and retries the SAME request once (tools intact) before falling
    through to the visible fallback. Reverting the retry would send
    empty completions straight to the fallback/empty-save path."""
    import inspect
    # the retry lives in the stream function that holds the tool loop —
    # pin via the module source (the function is huge; the markers are
    # unambiguous)
    import app.api.v1.chat.router as mod
    src = inspect.getsource(mod)
    assert '_empty_retried = False' in src
    assert 'if result_holder.get("empty_completion") and not _empty_retried:' in src
    assert '_empty_retried = True' in src
    assert 'EMPTY COMPLETION RETRY' in src


# ---------------------------------------------------------------------------
# 4. THE EMPTY-GUARD NOTICE (the guard must not be SILENT)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_finalize_empty_guard_carries_the_notice():
    """THE VISIBILITY FIX (2026-09-10, the user's "she died again, no
    warning or messages"): the guard still refuses the empty row, but
    the payload now carries the machine-readable signal (`empty_guard`)
    + the minimal copy (`notice`) the router turns into the user-visible
    `event: error` frame. Reverting the notice re-silences the failure.
    """
    from app.api.v1.chat.finalization import finalize_response
    from app.api.v1.chat.error_handling import EMPTY_COMPLETION_NOTICE
    from app.api.v1.chat.schemas import StreamResult

    db = _FakeDB()
    meta = await finalize_response(
        context=_make_context(),
        result=StreamResult(chunk_count=1, accumulated_content="", tool_calls=[], has_content=False),
        tool_results=[],
        request=SimpleNamespace(generate_title=False),
        service=_FakeService(),
        db=db,
        logger_service=_FakeLogger(),
        start_time=time.time(),
        final_content="",
    )

    assert db.added == []                      # guard unchanged — still refuses
    assert meta.get("empty_guard") is True      # top-level machine-readable signal
    assert meta.get("notice") == EMPTY_COMPLETION_NOTICE
    assert meta["metadata"].get("notice") == EMPTY_COMPLETION_NOTICE
    # the copy is MINIMAL and factual (what happened + the usual fix)
    assert "No answer was produced" in EMPTY_COMPLETION_NOTICE
    assert "new session" in EMPTY_COMPLETION_NOTICE


def test_empty_completion_event_is_the_frontend_error_convention():
    """THE SSE FRAME: the notice rides the EXISTING error convention —
    `event: error` + `data: {"error": {type, message, provider, model,
    session_id}}` — which StreamingService.processSSELine already
    routes to a toast + onStreamError (F1, 2026-08-03). Inventing a new
    frame would need a frontend change; this one does not.
    """
    from app.api.v1.chat.error_handling import (
        build_empty_completion_event,
        EMPTY_COMPLETION_NOTICE,
    )

    ctx = _make_context()
    frame = build_empty_completion_event(ctx)

    assert frame.startswith("event: error\ndata: ")
    assert frame.endswith("\n\n")
    payload = json.loads(frame.split("data: ", 1)[1].strip())
    assert payload["error"]["type"] == "empty_completion"
    assert payload["error"]["message"] == EMPTY_COMPLETION_NOTICE
    assert payload["error"]["provider"] == ctx.provider
    assert payload["error"]["model"] == ctx.model
    assert payload["error"]["session_id"] == ctx.session_id


def test_router_emits_the_notice_before_the_done_frame():
    """THE WIRING PIN: generate_stream emits the error frame when (and
    only when) finalize flagged the guard — and BEFORE the final done
    frame, because the frontend stops reading the stream at the error.
    Reverting the emission re-silences the failure."""
    import inspect
    import app.api.v1.chat.router as mod

    src = inspect.getsource(mod)
    assert 'if metadata.get("empty_guard"):' in src
    assert "yield build_empty_completion_event(context)" in src
    # the emission must precede the final done frame
    assert src.index("yield build_empty_completion_event(context)") < src.index(
        'yield f"data: {json.dumps(metadata)}\\n\\n"'
    )
