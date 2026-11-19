"""Asking for the tokens on a stream — and reading them wherever they arrive.

Several providers report usage on a streamed call ONLY when asked (the funnel now sets
`stream_options.include_usage`; measured on llama.cpp and groq, documented by OpenAI and
DeepSeek). Two things have to hold, and each fails silently on its own:

* the flag is actually SENT, and only where it is legal — `stream_options` is a streaming
  parameter, so a non-streamed call must not carry it, and a caller that sets its own keeps it;
* the usage is READ wherever it arrives. A provider that reports on request sends it on a
  FINAL frame with NO choices, so the loop must take the numbers from that frame and must not
  file it as malformed — `invalid_chunks` is a health field, and that frame now ends every
  stream, so a naive count would flag every healthy turn.

The second pair drives the real streaming wrapper over fake chunks, so they fail if the
reading order in the loop is ever put back the way it was.
"""

from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from app.api.v1.chat import llm_utils


class _Chunk:
    """A stream chunk. `usage` may ride a frame that carries no choices at all."""

    def __init__(self, content="", finish_reason=None, usage=None, choices=None):
        self.choices = (
            choices
            if choices is not None
            else [
                SimpleNamespace(
                    delta=SimpleNamespace(
                        content=content, tool_calls=None, reasoning="", reasoning_content=""
                    ),
                    finish_reason=finish_reason,
                )
            ]
        )
        self.usage = usage


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


class TestTheFlagIsAskedFor:
    """`acompletion_with_retry` sets it — the one place every chat call goes through."""

    @pytest.fixture(autouse=True)
    def _capture(self, monkeypatch):
        self.calls = []

        async def fake_acompletion(**kwargs):
            self.calls.append(kwargs)
            return _Stream([])

        monkeypatch.setattr(llm_utils, "acompletion", fake_acompletion)
        # One attempt: the retry ladder is not what this file is about.
        monkeypatch.setattr(llm_utils.turn_config, "retry_attempts", lambda: 1)

        # THE TRACER IS NOT THE SUBJECT, and a unit test must not ship spans to a real
        # project (the keys live in .env, which litellm loads into the process).
        from app.workflows.observability import langfuse_config

        monkeypatch.setattr(
            langfuse_config.LangfuseManager, "generation", staticmethod(lambda **kw: nullcontext(None))
        )
        yield

    @pytest.mark.anyio
    async def test_a_streamed_call_asks_for_usage(self):
        await llm_utils.acompletion_with_retry(model="m", messages=[], stream=True)

        assert self.calls[0]["stream_options"] == {"include_usage": True}

    @pytest.mark.anyio
    async def test_a_non_streamed_call_does_not_ask(self):
        await llm_utils.acompletion_with_retry(model="m", messages=[])

        assert "stream_options" not in self.calls[0]

    @pytest.mark.anyio
    async def test_a_callers_own_stream_options_win(self):
        await llm_utils.acompletion_with_retry(
            model="m", messages=[], stream=True, stream_options={"custom": True}
        )

        assert self.calls[0]["stream_options"] == {"custom": True}


class _Logger:
    def log_stream_started(self, *a, **k): pass
    def log_first_chunk(self, *a, **k): pass
    def log_stream_completed(self, *a, **k): pass
    def log_stream_open_failed(self, *a, **k): pass
    def log_final_response(self, *a, **k): pass
    def log_usage(self, *a, **k): pass


class _Service:
    def _estimate_tokens(self, s): return len(s or "") // 4
    async def _log_usage(self, **k): pass


def _context():
    return SimpleNamespace(
        session_id=115,
        session=SimpleNamespace(id=115, title="t"),
        agent=SimpleNamespace(name="Bob", description="", workspace_key="bob"),
        agent_id=19,
        agent_name="Bob",
        model="openrouter/inclusionai/ling-3.0-flash",
        provider="openrouter",
        messages=[{"role": "user", "content": "hi"}],
        messages_count=1,
    )


async def _drive(monkeypatch, chunks, logger=None):
    """Run the real streaming wrapper over a fake stream and give back its result."""
    from app.api.v1.chat import router as mod

    async def fake_with_retry(**kwargs):
        return _Stream(chunks)

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_with_retry)

    holder = {"result": None}
    gen = mod._stream_llm_response(
        {"messages": [], "max_tokens": 2000}, _context(), logger or _Logger(), 0.0, _Service(), holder,
    )
    [c async for c in gen]
    return holder["result"]


class TestTheLoopReadsUsageWhereverItArrives:
    @pytest.mark.anyio
    async def test_a_usage_only_final_frame_is_read_and_not_called_invalid(self, monkeypatch):
        usage = SimpleNamespace(prompt_tokens=73, completion_tokens=8)

        result = await _drive(
            monkeypatch,
            [_Chunk(content="Ready"), _Chunk(choices=[], usage=usage)],
        )

        assert (result.prompt_tokens, result.completion_tokens) == (73, 8)
        assert result.invalid_chunks == 0
        assert result.accumulated_content == "Ready"

    @pytest.mark.anyio
    async def test_a_choices_less_frame_without_usage_is_still_invalid(self, monkeypatch):
        """The health signal has to survive: only a frame carrying usage is excused."""
        result = await _drive(
            monkeypatch,
            [_Chunk(content="Ready"), _Chunk(choices=[], usage=None)],
        )

        assert result.invalid_chunks == 1
        assert (result.prompt_tokens, result.completion_tokens) == (0, 0)

    @pytest.mark.anyio
    async def test_usage_on_a_normal_chunk_is_still_read(self, monkeypatch):
        """OpenRouter's shape: the numbers ride a final frame that DOES carry a choice."""
        usage = SimpleNamespace(prompt_tokens=11, completion_tokens=3)

        result = await _drive(
            monkeypatch,
            [_Chunk(content="Ready", usage=usage)],
        )

        assert (result.prompt_tokens, result.completion_tokens) == (11, 3)
        assert result.invalid_chunks == 0


class TestTheCallSiteHandsTheUsageToTheLine:
    """A loop that reads usage into a result nobody logs is inert — the WIRE is the call site."""

    @pytest.mark.anyio
    async def test_the_logged_result_carries_the_usage_the_loop_read(self, monkeypatch):
        usage = SimpleNamespace(prompt_tokens=20536, completion_tokens=228)
        seen = []

        class _Capturing(_Logger):
            def log_stream_completed(self, context, result):
                seen.append(result)

        await _drive(monkeypatch, [_Chunk(content="Ready", usage=usage)], logger=_Capturing())

        assert (seen[0].prompt_tokens, seen[0].completion_tokens) == (20536, 228)


class TestTheLineCarriesTheCallTokens:
    """The per-call line prints those two numbers.

    The turn account holds their SUM across the turn's calls, so without this the only per-call
    prompt size available anywhere was an estimate.
    """

    class _Capture:
        def __init__(self):
            self.records = []

        def info(self, msg, extra=None):
            self.records.append((msg, extra))

    def _extra(self, **result_kwargs):
        from app.api.v1.chat.logging_service import ChatLoggingService
        from app.api.v1.chat.schemas import StreamResult

        service = ChatLoggingService()
        service.logger = self._Capture()
        service.log_stream_completed(
            {"session_id": 224, "agent_id": 19, "model": "m", "provider": "p"},
            StreamResult(chunk_count=3, accumulated_content="Ready", **result_kwargs),
        )
        return service.logger.records[0][1]

    def test_the_reported_usage_rides_the_line(self):
        extra = self._extra(prompt_tokens=20536, completion_tokens=228)

        assert extra["prompt_tokens"] == 20536
        assert extra["completion_tokens"] == 228

    def test_an_unreported_usage_reads_as_none_not_as_a_free_call(self):
        """A provider that sends nothing must not read as zero tokens."""
        extra = self._extra()

        assert extra["prompt_tokens"] is None
        assert extra["completion_tokens"] is None
