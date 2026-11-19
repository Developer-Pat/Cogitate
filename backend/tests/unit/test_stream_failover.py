"""The chat STREAM's failover — the turn's own request open walks the resolved chain (R3).

`_stream_llm_response` opens its OWN LLM request rather than going through the pipeline executor, so
the service-capability arc's phase 3 extended the chain to that open: a provider that REFUSES while
the attempt is opening (a dead endpoint, a model it does not serve, a rejected key) is failed over to
the next candidate. Once a chunk has arrived there is nothing to fail over — the user has read text —
which is why the walk covers the open and nothing else.

What these tests hold still:

* the answer arrives from the BACKUP, and the backup's request is built for THAT provider: the model
  string through the router's one mapping and the CANDIDATE's own `endpoint` (never the primary's
  endpoint or credentials);
* `fallback_enabled` keeps its meaning — OFF = the primary only, fail visibly;
* with no resolver reading on the context, the turn's request is the single attempt, exactly as
  before the arc (the pre-R3 behaviour every other caller still relies on).

Discriminators: each test fails when its behaviour is reverted.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.domain.providers.capabilities import SOURCE_AGENT, ServiceCandidate


def _chunk(content: str = ""):
    """One stream chunk, shaped like litellm's (`choices[0].delta`)."""
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(
                    content=content, tool_calls=None, reasoning="", reasoning_content=""
                )
            )
        ],
        usage=None,
    )


class _Stream:
    """A minimal async stream: yields the chunks it was handed."""

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


class _Logger:
    """Every `log_*` method is inert."""

    def __getattr__(self, name):
        return lambda *a, **k: None


class _Service:
    def _estimate_tokens(self, s):
        return len(s or "") // 4

    async def _log_usage(self, **k):
        pass


def _context(*, candidates=None, fallback_enabled: bool = False):
    """A chat context with the fields the streamer touches."""
    return SimpleNamespace(
        session_id=195,
        session=SimpleNamespace(id=195, title="t"),
        agent=SimpleNamespace(
            name="Lois", description="", workspace_key="lois", fallback_enabled=fallback_enabled
        ),
        agent_id=56,
        agent_name="Lois",
        model="openrouter/zz-refused-model",
        provider="openrouter",
        messages=[{"role": "user", "content": "hi"}],
        messages_count=1,
        messages_preview="hi",
        tools=[],
        tools_count=0,
        parameters={},
        request_params={},
        llm_tools=None,
        api_base=None,
        api_key=None,
        candidates=candidates,
        tool_call_tracker=None,
        turn_state=None,
    )


def _chain(*specs, endpoints=None):
    """The chain a resolution would hand over. `endpoints` mirrors what the resolver fills from the
    rows it read (2026-10-12, stage 2) — a candidate carries its own address."""
    return tuple(
        ServiceCandidate(
            ordinal=index,
            provider=provider,
            model=model,
            endpoint=(endpoints or {}).get(provider),
            source=SOURCE_AGENT,
        )
        for index, (provider, model) in enumerate(specs)
    )


@pytest.mark.anyio
async def test_the_stream_open_fails_over_to_the_backup(monkeypatch):
    """The primary REFUSES at the open → the backup answers, with ITS model string and endpoint."""
    from app.api.v1.chat import llm_utils, router as mod

    calls: list[dict] = []

    async def fake_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise RuntimeError("zz-refused-model is not a valid model ID")
        return _Stream([_chunk("hello from the local backup")])

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)

    context = _context(
        fallback_enabled=True,
        candidates=_chain(
            ("openrouter", "zz-refused-model"),
            ("llama", "local-model"),
            endpoints={"llama": "http://127.0.0.1:8080/v1"},
        ),
    )
    holder: dict = {"result": None}

    chunks = [
        c
        async for c in mod._stream_llm_response(
            {"messages": [], "model": "openrouter/zz-refused-model"},
            context,
            _Logger(),
            0.0,
            _Service(),
            holder,
        )
    ]

    assert len(calls) == 2, "one attempt per candidate"
    # the backup's request is built for the BACKUP: alias-mapped model + its own api_base + the
    # keyless placeholder the openai adapter needs
    assert calls[1]["model"] == "openai/local-model"
    assert calls[1]["api_base"] == "http://127.0.0.1:8080/v1"
    assert calls[1]["api_key"] == "local-llama"
    # the answer the user sees came from the backup
    assert chunks, "the backup's content was streamed to the user"
    assert holder["result"] is not None
    assert "hello from the local backup" in holder["result"].accumulated_content


@pytest.mark.anyio
async def test_the_failed_over_request_never_keeps_the_primarys_credentials(monkeypatch):
    """A backup on another provider must not be handed the primary's api_base / key / headers."""
    from app.api.v1.chat import llm_utils, router as mod

    calls: list[dict] = []

    async def fake_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise RuntimeError("refused")
        return _Stream([_chunk("ok")])

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)

    context = _context(
        fallback_enabled=True,
        candidates=_chain(("openrouter", "zz-refused-model"), ("deepseek", "zz-backup")),
    )
    request = {
        "messages": [],
        "model": "openrouter/zz-refused-model",
        "api_base": "https://openrouter.ai/api/v1",
        "api_key": "PRIMARY-KEY",
        "extra_headers": {"Authorization": "Bearer PRIMARY-KEY"},
    }

    await mod._open_stream_with_failover(request, context, path="default")

    backup = calls[1]
    assert backup["model"] == "deepseek/zz-backup"
    assert "api_base" not in backup, "the primary's endpoint must not ride along"
    assert backup.get("api_key") != "PRIMARY-KEY"
    assert "extra_headers" not in backup, "the primary's auth header must not ride along"


@pytest.mark.anyio
async def test_the_open_does_not_fail_over_without_the_flag(monkeypatch):
    """`fallback_enabled=False` → the primary's error surfaces, and nothing else is attempted."""
    from app.api.v1.chat import llm_utils, router as mod

    calls: list[dict] = []

    async def fake_completion(**kwargs):
        calls.append(kwargs)
        raise RuntimeError("refused")

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)

    context = _context(
        fallback_enabled=False,
        candidates=_chain(("openrouter", "zz-refused-model"), ("llama", "local-model")),
    )

    with pytest.raises(RuntimeError, match="refused"):
        await mod._open_stream_with_failover(
            {"messages": [], "model": "openrouter/zz-refused-model"}, context, path="default"
        )

    assert len(calls) == 1, "the chain is not walked when the agent has not opted in"


@pytest.mark.anyio
async def test_no_resolver_reading_means_the_request_is_the_single_attempt(monkeypatch):
    """No chain on the context → one attempt, riding the request the turn already built."""
    from app.api.v1.chat import llm_utils, router as mod

    calls: list[dict] = []

    async def fake_completion(**kwargs):
        calls.append(kwargs)
        return _Stream([_chunk("ok")])

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)

    context = _context(candidates=None)
    request = {"messages": [], "model": "openrouter/zz-refused-model", "api_key": "its-own-key"}

    await mod._open_stream_with_failover(request, context, path="default")

    assert len(calls) == 1
    assert calls[0]["model"] == "openrouter/zz-refused-model"
    assert calls[0]["api_key"] == "its-own-key"


@pytest.mark.anyio
async def test_the_open_names_the_ROW_each_attempt_is_made_against(monkeypatch):
    """THE BRIDGE'S CARRIER (the availability bridge's third seam): the walk knows which candidate it
    is opening, and the bridge needs that row to name the service a failed call belongs to.

    Pinned because a call site that stops passing it leaves the provider half of the bridge complete,
    tested and INERT — the failure mode the wiring exists to avoid. Note the SECOND half: the request
    the turn already built carries no row of its own, so the walk must supply it per attempt.
    """
    from app.api.v1.chat import llm_utils, router as mod

    calls: list[dict] = []

    async def fake_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise RuntimeError("refused")
        return _Stream([_chunk("ok")])

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)

    context = _context(
        fallback_enabled=True,
        candidates=_chain(("openrouter", "zz-refused-model"), ("llama", "local-model")),
    )

    await mod._open_stream_with_failover(
        {"messages": [], "model": "openrouter/zz-refused-model"}, context, path="default"
    )

    assert [call["provider"] for call in calls] == ["openrouter", "llama"], "each attempt names ITS row"
