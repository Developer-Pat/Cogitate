"""The first-chunk wait belongs to the CALL, not to the turn.

A turn makes several streamed calls (the tool loop, the answer pass). The wait for the first chunk
was measured against the TURN's start, so a turn's second call reported the whole elapsed turn as
its own "time to first chunk" — a number that grows call over call and describes none of them. It
read as a slow provider when the provider was answering in about a second.

The test makes the difference VISIBLE rather than asserting a duration: the wrapper is handed a
turn that began ten seconds ago, and the wait it reports must be the call's (a handful of
milliseconds), not the turn's (ten thousand and climbing).

`StreamTiming` derives the same figure from the same origin, so the value on the `STREAM COMPLETED`
line and the value on the `FIRST CHUNK` line can no longer disagree — which is the second half of
the same bug.
"""

import time
from types import SimpleNamespace

import pytest

from app.api.v1.chat import llm_utils


class _Chunk:
    def __init__(self, content=""):
        self.choices = [
            SimpleNamespace(
                delta=SimpleNamespace(
                    content=content, tool_calls=None, reasoning="", reasoning_content=""
                ),
                finish_reason=None,
            )
        ]
        self.usage = None


class _Stream:
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


class _RecordingLogger:
    """Keeps what the FIRST CHUNK line reported, which is the value under test."""

    def __init__(self):
        self.first_chunk_ms = None

    def log_first_chunk(self, session_id, time_to_first_chunk_ms, model, provider):
        self.first_chunk_ms = time_to_first_chunk_ms

    def log_stream_started(self, *a, **k): pass
    def log_stream_completed(self, *a, **k): pass
    def log_stream_open_failed(self, *a, **k): pass
    def log_final_response(self, *a, **k): pass
    def log_usage(self, *a, **k): pass


class _Service:
    def _estimate_tokens(self, s): return len(s or "") // 4
    async def _log_usage(self, **k): pass


def _context():
    return SimpleNamespace(
        session_id=1,
        session=SimpleNamespace(id=1, title="t"),
        agent=SimpleNamespace(name="A", description="", workspace_key="a"),
        agent_id=1,
        agent_name="A",
        model="m",
        provider="p",
        messages=[{"role": "user", "content": "hi"}],
        messages_count=1,
    )


async def _run(monkeypatch, chunks, turn_started_at):
    from app.api.v1.chat import router as mod

    logger = _RecordingLogger()

    async def fake_with_retry(**kwargs):
        return _Stream(chunks)

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_with_retry)

    holder = {"result": None}
    gen = mod._stream_llm_response(
        {"messages": [], "max_tokens": 64}, _context(), logger, turn_started_at, _Service(), holder
    )
    [c async for c in gen]
    return logger, holder["result"]


@pytest.mark.anyio
async def test_the_first_chunk_wait_is_the_calls_own_not_the_turns(monkeypatch):
    logger, result = await _run(monkeypatch, [_Chunk("hi")], turn_started_at=time.time() - 10.0)

    assert logger.first_chunk_ms is not None
    # The turn began ten seconds ago. A wait measured from the TURN would read ~10,000ms and up.
    assert logger.first_chunk_ms < 1000, logger.first_chunk_ms

    # The completed line's figure comes off the same origin, so the two lines agree.
    assert result.timing.time_to_first_chunk_ms == pytest.approx(logger.first_chunk_ms, abs=50)


@pytest.mark.anyio
async def test_a_later_call_in_the_same_turn_does_not_inherit_the_elapsed_turn(monkeypatch):
    """The bug's shape: call N reported the turn's whole elapsed time. Two calls, one clock each."""
    turn_start = time.time() - 30.0

    first_logger, _ = await _run(monkeypatch, [_Chunk("one")], turn_started_at=turn_start)
    second_logger, _ = await _run(monkeypatch, [_Chunk("two")], turn_started_at=turn_start)

    assert first_logger.first_chunk_ms < 1000, first_logger.first_chunk_ms
    assert second_logger.first_chunk_ms < 1000, second_logger.first_chunk_ms
