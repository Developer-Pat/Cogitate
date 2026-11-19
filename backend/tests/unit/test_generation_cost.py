"""The generation carries the app's own cost — or nothing at all.

Langfuse prices a generation at ingestion, and it can only price what it can identify. Rather than
seed a second copy of every price into the tracing project (and then keep that copy in step with a
catalog that refreshes), the app hands Langfuse the number it already knows: `cost_details`, from
the same resolver and the same per-1K arithmetic as the usage row.

The rule that matters as much as the figure is the ABSENCE. `ollama_cloud` and the local servers
publish no price, so they send none: a `0.0` on the trace would read as "this call was free", which
is a claim the app cannot make.

WHY THE REAL `update` RUNS HERE (and why this file is shaped this way). The first version of these
tests faked `LangfuseManager.update(**fields)`, which accepts ANY keyword — so when
`_finish_generation` handed it `cost_details`, the tests stayed green while a real turn died on the
wire ("LangfuseManager.update() got an unexpected keyword argument 'cost_details'" — a TypeError
raised AT THE CALL, before the wrapper's own `except` could see it). Only `generation` is faked now:
the observation records what the REAL manager passes through, so every field a path can emit is
checked against the real signature by being sent through it. For the same reason the error path has
its own test — `level` and `status_message` are fields too.
"""

from types import SimpleNamespace

import pytest

from app.api.v1.chat import llm_utils
from app.workflows.observability import langfuse_config

# A price in the cost site's unit: PER 1K TOKENS.
PRICING = {"prompt": 2.0, "completion": 8.0}


class _Chunk:
    def __init__(self, content="", usage=None):
        self.choices = [
            SimpleNamespace(
                delta=SimpleNamespace(
                    content=content, tool_calls=None, reasoning="", reasoning_content=""
                ),
                finish_reason=None,
            )
        ]
        self.usage = usage


class _Stream:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def __aiter__(self):
        self._it = iter(self._chunks)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


class _FailingStream:
    """A provider that dies mid-iteration — the path that marks the generation errored."""

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise RuntimeError("provider died")


def _usage(prompt: int, completion: int):
    return SimpleNamespace(
        prompt_tokens=prompt, completion_tokens=completion, total_tokens=prompt + completion
    )


class _Observation:
    """What `generation` yields: a context manager that records what the manager tells it."""

    def __init__(self, seen):
        self.seen = seen

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def update(self, **fields):
        self.seen["updates"].append(fields)


def _capture(monkeypatch):
    """Fake `generation` only — `LangfuseManager.update` stays REAL (see the module docstring)."""
    seen: dict = {"updates": []}

    def fake_generation(cls, name=None, **fields):
        seen["name"] = name
        seen["opened"] = fields
        return _Observation(seen)

    monkeypatch.setattr(
        langfuse_config.LangfuseManager, "generation", classmethod(fake_generation)
    )
    return seen


async def _drain(agen):
    return [chunk async for chunk in agen]


async def _drive(monkeypatch, chunks, stream=None, **call_kwargs):
    """One streamed call through the funnel; returns what the generation was told."""
    seen = _capture(monkeypatch)
    stream = stream if stream is not None else _Stream(chunks)

    async def fake_acompletion(**kwargs):
        seen["kwargs"] = kwargs
        return stream

    monkeypatch.setattr(llm_utils, "acompletion", fake_acompletion)
    await _drain(await llm_utils.acompletion_with_retry(stream=True, **call_kwargs))
    return seen


@pytest.mark.anyio
async def test_a_priced_streamed_call_reports_the_cost_the_app_computed(monkeypatch):
    seen = await _drive(
        monkeypatch,
        [_Chunk("hi", usage=_usage(1000, 250))],
        model="openrouter/inclusionai/ling-3.0-flash",
        messages=[],
        pricing=PRICING,
    )

    update = seen["updates"][-1]
    assert update["usage_details"] == {"input": 1000, "output": 250}
    # 1000/1000 * 2.0 = 2.0  ·  250/1000 * 8.0 = 2.0
    assert update["cost_details"] == {"input": 2.0, "output": 2.0}


@pytest.mark.anyio
async def test_an_unpriced_call_sends_no_cost_at_all(monkeypatch):
    seen = await _drive(
        monkeypatch,
        [_Chunk("hi", usage=_usage(1000, 250))],
        model="ollama_chat/nemotron-3-super",
        messages=[],
        # No `pricing`: the provider publishes no price, and a 0.0 would assert one.
    )

    update = seen["updates"][-1]
    assert update["usage_details"] == {"input": 1000, "output": 250}
    assert "cost_details" not in update, "an unpriced call must not claim to be free"


@pytest.mark.anyio
async def test_a_call_with_no_reported_tokens_gets_no_cost(monkeypatch):
    """Cost is derived from tokens: with nothing to multiply, there is nothing to say."""
    seen = await _drive(
        monkeypatch,
        [_Chunk("hi")],
        model="openrouter/inclusionai/ling-3.0-flash",
        messages=[],
        pricing=PRICING,
    )

    update = seen["updates"][-1]
    assert "usage_details" not in update
    assert "cost_details" not in update


@pytest.mark.anyio
async def test_a_failed_call_is_recorded_as_an_error(monkeypatch):
    """`level` and `status_message` are fields like any other — sent through the real signature."""
    seen = _capture(monkeypatch)

    async def fake_acompletion(**kwargs):
        return _FailingStream()

    monkeypatch.setattr(llm_utils, "acompletion", fake_acompletion)
    with pytest.raises(RuntimeError):
        await _drain(
            await llm_utils.acompletion_with_retry(
                stream=True, model="openrouter/x", messages=[], pricing=PRICING
            )
        )

    update = seen["updates"][-1]
    assert update["level"] == "ERROR"
    assert "provider died" in update["status_message"]


@pytest.mark.anyio
async def test_the_price_never_reaches_the_provider(monkeypatch):
    """`pricing` is the WRAPPER's parameter. litellm forwards unknown kwargs to the provider,
    which is how a convenience argument becomes a 400."""
    seen = await _drive(
        monkeypatch,
        [_Chunk("hi", usage=_usage(10, 5))],
        model="openrouter/inclusionai/ling-3.0-flash",
        messages=[],
        pricing=PRICING,
    )

    assert "pricing" not in seen["kwargs"]
    assert seen["kwargs"]["stream_options"] == {"include_usage": True}


@pytest.mark.anyio
async def test_the_non_streamed_path_carries_the_same_cost(monkeypatch):
    """A turn's calls are not all streams — `delegate` and the title pass are plain completions."""
    seen = _capture(monkeypatch)
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="hi", tool_calls=None), finish_reason="stop"
            )
        ],
        usage=_usage(2000, 500),
    )

    async def fake_acompletion(**kwargs):
        return response

    monkeypatch.setattr(llm_utils, "acompletion", fake_acompletion)
    await llm_utils.acompletion_with_retry(
        model="openrouter/inclusionai/ling-3.0-flash", messages=[], pricing=PRICING
    )

    update = seen["updates"][-1]
    # 2000/1000 * 2.0 = 4.0  ·  500/1000 * 8.0 = 4.0
    assert update["cost_details"] == {"input": 4.0, "output": 4.0}
