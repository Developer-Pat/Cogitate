"""THE SEAM: `generate_stream` refuses a turn BEFORE the pipeline starts (phase 6, G5-F3/F4).

The plan's own "check first" — *the exact seam in `generate_stream` and whether the resolution
available there is the one the refusal needs* — answered by driving the REAL generator:

* a turn whose capability is OFF, or whose primary is cached-**down** with no fallback the walk may
  use, is refused at the seam: the LLM is never asked, the statement rides a CONTENT frame (the
  bubble) and the `event: error` frame the frontend already renders (`capability_unavailable`), and
  the refusal is persisted so a reload still shows it;
* **a COLD memo refuses nothing** — the same turn goes on to the provider, which is the ruling's
  discriminator (`unknown`/stale never refuses; the at-turn walk is the arbiter) and the reason the
  refusal can afford to read the cache only.

Everything is provisioned by the test: `auto_clean_tables` truncates the ORM tables after each
test, and a copied installation's rows are visible only to a session's FIRST test.
"""

from __future__ import annotations

import json
import time
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.domain.chat.services import ChatService
from app.domain.providers import availability as av
from app.infrastructure.database.models import Agent, Capability, ChatMessage


async def _reset_chat_capability(session, *, enabled=None) -> None:
    """Make the `chat` capability row deterministic, then optionally re-create it."""
    existing = (
        await session.execute(select(Capability).where(Capability.key == "chat"))
    ).scalar_one_or_none()
    if existing is not None:
        await session.delete(existing)
        await session.flush()
    if enabled is not None:
        session.add(Capability(key="chat", label="Chat", kind="llm", enabled=enabled))
    await session.commit()


async def _make_agent(session, *, provider: str, fallback_enabled: bool) -> Agent:
    agent = Agent(
        name="Refusal Test Agent",
        provider=provider,
        model="Bonsai-27B-Q1_0.gguf",
        system_prompt="You are a test agent.",
        is_active=True,
        # The column's own default is ["ollama"]; the tests want the DECLARATION alone, so the
        # chain is exactly the agent's provider plus whatever the capability configures.
        preferred_providers=[],
        fallback_enabled=fallback_enabled,
    )
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    return agent


def _seed_llama_down() -> None:
    """The memo, the way a real read would have left it: llama is DOWN, checked just now."""
    av._CACHE[6] = (
        time.monotonic() + av.DEFAULT_TTL_SECONDS,
        av.Availability(
            provider_id=6,
            name="llama",
            state=av.STATE_DOWN,
            reason="the local server is not running and no local server answers",
            checked_at="2026-10-05T00:00:00Z",
        ),
    )


def _request(agent: Agent) -> SimpleNamespace:
    return SimpleNamespace(
        agent_id=agent.id,
        message="are you there?",
        session_id=None,
        attachment_ids=None,
        generate_title=False,
    )


def _frames(frames: list[str]) -> list[dict]:
    """Every frame that carries an `error` payload, parsed."""
    out = []
    for frame in frames:
        if frame.startswith("event: error"):
            out.append(json.loads(frame.split("data: ", 1)[1].strip())["error"])
    return out


@pytest.fixture(autouse=True)
def _cold_cache():
    av.clear_cache()
    yield
    av.clear_cache()


@pytest.mark.anyio
async def test_a_down_primary_with_no_fallback_is_refused_before_the_pipeline(test_session, monkeypatch):
    from app.api.v1.chat import router as mod

    await _reset_chat_capability(test_session)          # no chat row: the AGENT's declaration answers
    agent = await _make_agent(test_session, provider="llama", fallback_enabled=False)
    _seed_llama_down()

    called = {"llm": False}

    async def fake_stream(*args, **kwargs):
        called["llm"] = True
        result_holder = args[5] if len(args) > 5 else kwargs.get("result_holder")
        if result_holder is not None:
            result_holder["result"] = None
        return
        yield  # pragma: no cover

    monkeypatch.setattr(mod, "_stream_llm_response", fake_stream)

    frames = [c async for c in mod.generate_stream(_request(agent), ChatService(test_session))]

    errors = _frames(frames)
    assert errors, f"no error frame — frames={frames[-4:]}"
    assert errors[0]["type"] == "capability_unavailable"
    assert "Bonsai 27b Q1 0.gguf (llama) is unavailable" in errors[0]["message"]
    assert "No fallback is configured for this agent." in errors[0]["message"]

    # THE POINT: the provider was never asked.
    assert called["llm"] is False, "the refusal must precede the pipeline and the LLM call"

    # The sentence reaches the BUBBLE (a content frame), not only the toast.
    content = [
        json.loads(f.split("data: ", 1)[1].strip())["choices"][0]["delta"]["content"]
        for f in frames if f.startswith("data: ") and '"choices"' in f
    ]
    assert any("is unavailable" in c for c in content), content

    # …and it is on the transcript, so a reload still shows it.
    rows = (
        await test_session.execute(select(ChatMessage).where(ChatMessage.role == "assistant"))
    ).scalars().all()
    assert len(rows) == 1
    assert "Bonsai 27b Q1 0.gguf (llama) is unavailable" in rows[0].content
    assert (rows[0].meta or {}).get("refusal") is True


@pytest.mark.anyio
async def test_a_capability_switched_off_is_refused_at_the_seam(test_session, monkeypatch):
    from app.api.v1.chat import router as mod

    await _reset_chat_capability(test_session, enabled=False)
    agent = await _make_agent(test_session, provider="llama", fallback_enabled=False)

    called = {"llm": False}

    async def fake_stream(*args, **kwargs):
        called["llm"] = True
        return
        yield  # pragma: no cover

    monkeypatch.setattr(mod, "_stream_llm_response", fake_stream)

    frames = [c async for c in mod.generate_stream(_request(agent), ChatService(test_session))]

    errors = _frames(frames)
    assert errors[0]["type"] == "capability_unavailable"
    assert "'chat' capability is switched off" in errors[0]["message"]
    assert called["llm"] is False


@pytest.mark.anyio
async def test_chat_readiness_reads_the_agents_declared_service(test_session, monkeypatch):
    """The agent surface's read: the SAME predicate, over the SAME memo, for a page (G5-F2).

    A page can afford the probe; the run below proves the verdict lands on the agent whose own
    declaration names the dead service.
    """
    from app.domain.providers import availability as av
    from app.domain.providers.refusal import chat_readiness
    from app.infrastructure.database.models import Provider

    await _reset_chat_capability(test_session)
    existing = (
        await test_session.execute(select(Provider).where(Provider.name == "llama"))
    ).scalar_one_or_none()
    if existing is None:
        test_session.add(
            Provider(
                name="llama",
                provider_type="openai",
                base_url="http://127.0.0.1:18080/v1",
                is_active=True,
            )
        )
        await test_session.commit()
    agent = await _make_agent(test_session, provider="llama", fallback_enabled=False)

    async def nothing(*args, **kwargs):
        return None

    monkeypatch.setattr(av, "probe_json", nothing)
    monkeypatch.setattr(av, "env_key", lambda provider_type: None)
    av.clear_cache()

    verdict = (await chat_readiness(test_session, [agent]))[agent.id]

    assert verdict.available is False, "a down declared service is the 'cannot run' state"
    assert verdict.state == "down"
    assert verdict.provider == "llama"
    assert verdict.checked_at, "the badge's copy owns the staleness window"


@pytest.mark.anyio
async def test_a_cold_memo_refuses_nothing_and_the_turn_reaches_the_provider(test_session, monkeypatch):
    """THE DISCRIMINATOR: `unknown`/cold is not a refusal — the turn proceeds to the walk."""
    from app.api.v1.chat import router as mod
    from app.api.v1.chat import llm_utils
    from app.api.v1.chat.error_handling import EMPTY_COMPLETION_NOTICE

    await _reset_chat_capability(test_session)
    agent = await _make_agent(test_session, provider="llama", fallback_enabled=False)
    av.clear_cache()  # nothing was ever checked

    seen = {"llm": False}

    async def fake_stream(request_kwargs, context, logger_service, start_time, service,
                          result_holder, path=""):
        seen["llm"] = True
        result_holder["result"] = None
        result_holder["empty_completion"] = True
        result_holder["empty_chunk_count"] = 1
        result_holder["empty_invalid_chunks"] = 0
        return
        yield  # pragma: no cover

    async def fake_completion(**kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=""))])

    monkeypatch.setattr(mod, "_stream_llm_response", fake_stream)
    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)

    frames = [c async for c in mod.generate_stream(_request(agent), ChatService(test_session))]

    assert seen["llm"] is True, "a cold memo must NOT refuse — the walk is the arbiter"
    types = [e["type"] for e in _frames(frames)]
    assert "capability_unavailable" not in types, types
    # The turn ran to its own (empty) end rather than being refused.
    assert EMPTY_COMPLETION_NOTICE in "".join(frames)
