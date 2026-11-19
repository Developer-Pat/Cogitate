"""The capability resolver's LADDER, and the three ways a candidate names a service.

Phase 1 of the service-capability arc exists to make ONE answer to "which service answers this?"
where there were four (the default row, an agent's own declaration, the title service's own rule,
and eighteen direct constructions). These tests pin the parts that only a test can hold still:

* **the rungs, in order** — override beats the agent, the agent beats the capability's own config
  (and only when the CALLER passes an agent: the chat path does, the title service must not),
  the capability beats the global default, and nothing-resolvable is REPORTED rather than raised;
* **the three naming forms** — `provider_id` (the LLM case), `require_location` (how "prefer local"
  becomes configuration instead of the hardcoded `DEFAULT_FALLBACK_CHAIN` list), and `service_name`
  (the families that are not provider rows at all: piper, edge, whisper, exa — without it this
  revision could not reproduce what `stt` and `tts` do today);
* **the loud half** — a candidate that names nothing is SKIPPED AND LOGGED, because a chain that
  silently loses a backup is the defect class this arc is removing.

Every row is built inside the test database and rolled back by the fixture, so nothing here depends
on the live capability rows (which arrive from the migration's seed, not from this file).
"""

from __future__ import annotations

import logging
import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.providers import capabilities as cap
from app.domain.providers.config_service import DefaultProviderService, ProviderConfig
from app.infrastructure.database.models import Capability, CapabilityService, Provider


async def _provider(
    session: AsyncSession,
    name: str,
    provider_type: str = "openai",
    base_url: str | None = None,
    priority: int = 99,
    default_model: str | None = "zz-model",
) -> Provider:
    """A provider row of the class the test needs (loopback + openai = local)."""
    row = Provider(
        name=name,
        display_name=name,
        provider_type=provider_type,
        base_url=base_url,
        is_active=True,
        priority=priority,
        config={"default_model": default_model} if default_model else {},
    )
    session.add(row)
    await session.flush()
    return row


async def _capability(
    session: AsyncSession,
    candidates: list[tuple[int, dict[str, Any]]] | None = None,
    kind: str = cap.KIND_LLM,
) -> Capability:
    """A capability with an ordered candidate list; the key is unique per call."""
    row = Capability(key=f"zz-test-{uuid.uuid4().hex[:8]}", label="Test", kind=kind, enabled=True)
    session.add(row)
    await session.flush()
    for ordinal, fields in candidates or []:
        session.add(CapabilityService(capability_id=row.id, ordinal=ordinal, enabled=True, **fields))
    await session.flush()
    await session.refresh(row, ["services"])
    return row


@pytest.mark.anyio
async def test_a_provider_row_candidate_names_the_row_it_resolved(test_session: AsyncSession) -> None:
    """The LLM case: the candidate is a row, and the resolution names it (not its type).

    The location comes from `provider_location` — here the LOOPBACK tiebreaker, which is how a
    self-hosted server registered as `openai` (the llama.cpp case) reads as local rather than cloud.
    """
    provider = await _provider(test_session, "zz-row-provider", base_url="http://127.0.0.1:9995",
                               priority=7)
    capability = await _capability(test_session, [(0, {"provider_id": provider.id})])

    resolved = await cap.resolve(test_session, capability.key)

    assert resolved.reason == cap.REASON_CAPABILITY
    assert resolved.resolved is True
    assert resolved.primary is not None
    assert resolved.primary.provider == "zz-row-provider"
    assert resolved.primary.provider_id == provider.id
    assert resolved.primary.model == "zz-model"  # the row's own default_model
    assert resolved.primary.location == "local"  # openai type + a loopback base_url


@pytest.mark.anyio
async def test_an_explicit_model_on_the_candidate_beats_the_rows_default(
    test_session: AsyncSession,
) -> None:
    """A capability may pin a model; the row's `default_model` is the fallback, not the winner."""
    provider = await _provider(test_session, "zz-model-provider")
    capability = await _capability(
        test_session, [(0, {"provider_id": provider.id, "model": "zz-pinned"})]
    )

    resolved = await cap.resolve(test_session, capability.key)

    assert resolved.primary is not None
    assert resolved.primary.model == "zz-pinned"


@pytest.mark.anyio
async def test_a_class_candidate_contributes_the_matching_rows_in_priority_order(
    test_session: AsyncSession,
) -> None:
    """`require_location='local'` = "prefer the local ones", best-first — configuration, not a list.

    The test database already holds local and cloud rows, so the assertions are RELATIVE: my two
    local rows must appear in priority order, a cloud row must not appear at all, and every
    candidate in the chain must be local.
    """
    slow_local = await _provider(
        test_session, "zz-local-slow", base_url="http://127.0.0.1:9998", priority=80
    )
    fast_local = await _provider(
        test_session, "zz-local-fast", base_url="http://127.0.0.1:9999", priority=10
    )
    cloud = await _provider(
        test_session, "zz-cloud", provider_type="openrouter", base_url=None, priority=1
    )
    capability = await _capability(test_session, [(0, {"require_location": "local"})])

    resolved = await cap.resolve(test_session, capability.key)

    names = [c.provider for c in resolved.candidates]
    assert fast_local.name in names and slow_local.name in names
    assert names.index(fast_local.name) < names.index(slow_local.name), "priority must order a class"
    assert cloud.name not in names
    assert {c.location for c in resolved.candidates} == {"local"}
    assert {c.source for c in resolved.candidates} == {cap.SOURCE_CLASS}


@pytest.mark.anyio
async def test_a_named_service_candidate_carries_no_provider(test_session: AsyncSession) -> None:
    """The speech/process families are not provider rows — the candidate names the ENGINE."""
    capability = await _capability(
        test_session, [(0, {"service_name": "whisper"})], kind=cap.KIND_SPEECH
    )

    resolved = await cap.resolve(test_session, capability.key)

    assert resolved.kind == cap.KIND_SPEECH
    assert resolved.primary is not None
    assert resolved.primary.service_name == "whisper"
    assert resolved.primary.provider is None
    assert cap.describe_chain(resolved) == "whisper"


@pytest.mark.anyio
async def test_the_backups_are_everything_after_the_primary(test_session: AsyncSession) -> None:
    """The chain's meaning: ordinal 0 is the primary, and the rest is what a failure path can try."""
    first = await _provider(test_session, "zz-first", base_url="http://127.0.0.1:9997")
    second = await _provider(test_session, "zz-second", base_url="http://127.0.0.1:9996")
    capability = await _capability(
        test_session,
        [(1, {"provider_id": second.id}), (0, {"provider_id": first.id})],
    )

    resolved = await cap.resolve(test_session, capability.key)

    assert resolved.primary is not None and resolved.primary.provider == "zz-first"
    assert [c.provider for c in resolved.backups] == ["zz-second"]
    assert cap.describe_chain(resolved) == "zz-first/zz-model -> zz-second/zz-model"


@pytest.mark.anyio
async def test_an_override_beats_the_capability_config(test_session: AsyncSession) -> None:
    """Rung 1: an explicit `provider/model` wins, and says so."""
    provider = await _provider(test_session, "zz-ignored")
    capability = await _capability(test_session, [(0, {"provider_id": provider.id})])

    resolved = await cap.resolve(test_session, capability.key, override="openrouter/zz-choice")

    assert resolved.reason == cap.REASON_OVERRIDE
    assert resolved.primary is not None
    assert resolved.primary.provider == "openrouter"
    assert resolved.primary.model == "zz-choice"
    assert resolved.primary.source == cap.SOURCE_OVERRIDE


@pytest.mark.anyio
async def test_an_agent_beats_the_capability_config_only_when_the_caller_passes_one(
    test_session: AsyncSession,
) -> None:
    """Rung 2 is OPT-IN — which is what keeps the title service's behaviour unchanged.

    The chat path passes an agent (its behaviour today IS "the agent's model first"); the title
    service does not, and must keep resolving to its own config.
    """
    provider = await _provider(test_session, "zz-capability-row")
    capability = await _capability(test_session, [(0, {"provider_id": provider.id})])
    agent = SimpleNamespace(provider="llama", model="zz-agent-model")

    with_agent = await cap.resolve(test_session, capability.key, agent=agent)
    without_agent = await cap.resolve(test_session, capability.key)

    assert with_agent.reason == cap.REASON_AGENT
    assert with_agent.primary is not None and with_agent.primary.model == "zz-agent-model"
    assert without_agent.reason == cap.REASON_CAPABILITY
    assert without_agent.primary is not None and without_agent.primary.provider == "zz-capability-row"


@pytest.mark.anyio
async def test_an_unconfigured_capability_falls_to_the_global_default(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rung 4: the row every consumer sits on today, named — this is the behaviour being replaced."""

    async def _fake_default(self: DefaultProviderService, db: AsyncSession) -> ProviderConfig:
        return ProviderConfig(
            id=4242,
            name="zz-default",
            provider_type="openrouter",
            is_default=True,
            config={"default_model": "zz-default-model"},
        )

    monkeypatch.setattr(DefaultProviderService, "get_default_provider", _fake_default)

    resolved = await cap.resolve(test_session, "zz-no-such-capability")

    assert resolved.reason == cap.REASON_GLOBAL_DEFAULT
    assert resolved.primary is not None
    assert resolved.primary.provider == "zz-default"
    assert resolved.primary.model == "zz-default-model"
    assert resolved.primary.source == cap.SOURCE_DEFAULT


@pytest.mark.anyio
async def test_nothing_resolvable_is_REPORTED_and_never_raised(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rung 5 hands the caller an honest empty answer: the caller names the failure, not the resolver."""

    async def _no_default(self: DefaultProviderService, db: AsyncSession) -> None:
        return None

    monkeypatch.setattr(DefaultProviderService, "get_default_provider", _no_default)

    resolved = await cap.resolve(test_session, "zz-no-such-capability")

    assert resolved.reason == cap.REASON_NONE
    assert resolved.candidates == ()
    assert resolved.resolved is False
    assert resolved.primary is None


@pytest.mark.anyio
async def test_a_candidate_that_names_nothing_is_skipped_and_LOGGED(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A candidate with no service is a configuration error, and it must not pass silently.

    A chain that quietly drops an entry reads as a backup that exists — the same defect class as an
    inert FK. So the entry is skipped AND the log says which one.
    """
    monkeypatch.setattr(
        DefaultProviderService,
        "get_default_provider",
        lambda self, db: _no_default(),
    )
    capability = await _capability(test_session, [(0, {})])

    with caplog.at_level(logging.ERROR):
        resolved = await cap.resolve(test_session, capability.key)

    assert resolved.resolved is False
    assert any("names NO service" in record.message for record in caplog.records), caplog.text


async def _no_default() -> None:
    """Awaitable `None` for the monkeypatched default lookup."""
    return None


@pytest.mark.anyio
async def test_the_agents_preferred_providers_are_its_backups(test_session: AsyncSession) -> None:
    """Rung 2 declares an ORDER — its own provider first, its preferred list after it (R3).

    The agent's declaration is not a single answer: it is the primary AND the backups, so the
    order lives here rather than in whichever consumer used to walk it. The primary is never its
    own backup, a repeat adds nothing, and every backup carries the AGENT'S model — which is what
    the executor's failover sends today.
    """
    provider = await _provider(test_session, "zz-capability-row")
    capability = await _capability(test_session, [(0, {"provider_id": provider.id})])
    agent = SimpleNamespace(
        provider="openrouter",
        model="zz-agent-model",
        preferred_providers=["llama", "openrouter", "deepseek"],
    )

    resolved = await cap.resolve(test_session, capability.key, agent=agent)

    assert resolved.reason == cap.REASON_AGENT
    assert [(c.provider, c.ordinal) for c in resolved.candidates] == [
        ("openrouter", 0),
        ("llama", 1),
        ("deepseek", 2),
    ]
    assert {c.model for c in resolved.backups} == {"zz-agent-model"}
    assert {c.source for c in resolved.candidates} == {cap.SOURCE_AGENT}
    assert cap.describe_chain(resolved) == (
        "openrouter/zz-agent-model -> llama/zz-agent-model -> deepseek/zz-agent-model"
    )


def test_the_agents_preferred_providers_default_names_no_service() -> None:
    """The column's DEFAULT is EMPTY — it used to be `["ollama"]`, a service named in code.

    That default landed as the backup list of every new agent, so a failover walked a provider nobody
    had chosen for it (`ollama`, down on a box with no daemon). An agent that declares nothing must
    declare nothing: the ladder then falls to the capability's own configured chain, which is the one
    answer this arc exists to give.
    """
    from app.infrastructure.database.models import Agent

    default = Agent.__table__.c.preferred_providers.default
    assert default is not None
    assert default.arg(None) == []  # SQLAlchemy wraps it as `lambda ctx: []`
