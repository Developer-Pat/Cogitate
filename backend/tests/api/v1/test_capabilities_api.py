"""The capabilities sub-area — the read path that answers "what does each part of the app use?".

The user's ruling (2026-09-30): the locator is exposed as a SUB-AREA inside the providers API, so
`/providers/capabilities` answers per capability with the service, its backups and **the rung that
decided**. These tests pin the contract the surfaces (and, later, the failure statements) read:

* every row carries a `reason` — a resolution that cannot say WHY it chose is the thing this arc
  replaces, so its absence is a failure here rather than a cosmetic gap;
* the resolved chain is served IN ORDER — `primary` is the first attempt and `backups` the ordered
  rest — whatever the rows' STORED ordinals are: a capability's chain may legitimately begin above 0
  (the live `chat` row is stored at ordinal 1). That contract is pinned on rows of the test's own by
  `test_a_chain_stored_above_zero_still_reads_back_in_order`, not asserted over the copied
  installation;
* an unknown key is a 404 — 'not configured' and 'configured to nothing' are different facts;
* a capability created in the store reads back through the API with the service it names;
* `?agent_id=` resolves the agent rung — but ONLY for the capabilities a live consumer passes an
  agent for, so the page can answer "what will this agent use" without misreporting the rest (the
  agent view, phase 6's G2-F2).

**Every test provisions what it reads.** The suite's `auto_clean_tables` fixture truncates all ORM
tables after each test, so the provider row, the agent and the `chat` capability the agent-view test
needs are created (or REUSED, by their natural key) by that test rather than assumed from the copy.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.providers.capabilities import KIND_LLM, KIND_SPEECH, KINDS
from app.infrastructure.database.models import Agent, Capability, CapabilityService, Provider


@pytest.mark.anyio
async def test_the_read_out_serves_every_capability_with_the_rung_that_answered(
    client: AsyncClient,
) -> None:
    """The whole read-out: a reason and a chain per row, and the kinds this revision understands."""
    response = await client.get("/api/v1/providers/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == len(body["capabilities"])
    assert set(body["kinds"]) == set(KINDS)
    for row in body["capabilities"]:
        assert row["reason"], f"{row['key']} resolved without saying which rung answered"
        assert isinstance(row["chain"], str)
        assert row["kind"] in KINDS
        # The primary's ORDINAL is deliberately NOT asserted here. It is the row's STORED position,
        # not the attempt's place in the chain — the live `chat` row is stored at ordinal 1 and
        # resolves as the primary — and this loop also runs over the copied installation, which is
        # empty by the time most tests reach it, so an order assertion written here would be both
        # wrong on that data and vacuous on the rest. The ORDER contract is pinned on rows the test
        # owns, by `test_a_chain_stored_above_zero_still_reads_back_in_order`.


@pytest.mark.anyio
async def test_a_created_capability_reads_back_with_the_engine_it_names(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """A speech capability's candidate is an ENGINE, not a provider row — and the API says so."""
    key = f"zz-api-{uuid.uuid4().hex[:8]}"
    capability = Capability(key=key, label="API test capability", kind=KIND_SPEECH, enabled=True)
    test_session.add(capability)
    await test_session.flush()
    test_session.add(
        CapabilityService(capability_id=capability.id, ordinal=0, service_name="zz-engine")
    )
    await test_session.commit()

    try:
        response = await client.get(f"/api/v1/providers/capabilities/{key}")

        assert response.status_code == 200
        row = response.json()
        assert row["key"] == key
        assert row["kind"] == KIND_SPEECH
        assert row["reason"] == "capability config"
        assert row["chain"] == "zz-engine"
        assert row["primary"]["service_name"] == "zz-engine"
        assert row["primary"]["provider"] is None
        assert row["backups"] == []
    finally:
        await test_session.delete(capability)
        await test_session.commit()


@pytest.mark.anyio
async def test_an_unknown_capability_is_a_404_not_an_empty_answer(client: AsyncClient) -> None:
    """'not configured' is not 'configured to nothing' — the resolver distinguishes, so the API does."""
    response = await client.get("/api/v1/providers/capabilities/zz-not-a-capability")

    assert response.status_code == 404
    assert "zz-not-a-capability" in response.json()["detail"]


# ── The agent view (phase 6, G2-F2) ──────────────────────────────────────────────────────────────
#
# `?agent_id=` resolves through the ladder's agent rung — but only for the capabilities a live
# consumer passes an agent for. Each test below provisions the rows it reads.


async def _provider(session: AsyncSession) -> Provider:
    """A provider row of this test's own — the service the agent's declaration names."""
    row = Provider(
        name=f"zz-agent-view-prov-{uuid.uuid4().hex[:8]}",
        display_name="Agent-view test provider",
        provider_type="openai",
        base_url="https://example.invalid/v1",
        is_active=True,
        priority=98,
        is_default=False,
        config={"default_model": "zz-provider-model"},
    )
    session.add(row)
    await session.commit()
    return row


async def _agent(session: AsyncSession, provider: Provider) -> Agent:
    """An agent whose declaration names `provider` — rung 2's input."""
    row = Agent(
        name=f"zz-agent-view-{uuid.uuid4().hex[:8]}",
        description="Agent-view test agent",
        provider=provider.name,
        model="zz-agent-model",
        # Explicit: the column defaults to ["ollama"], which would add a backup this test does not
        # mean to assert about.
        preferred_providers=[],
        is_active=True,
    )
    session.add(row)
    await session.commit()
    return row


async def _capability_with_candidate(
    session: AsyncSession, key: str, provider: Provider
) -> tuple[Capability, bool]:
    """The capability `key` — REUSED when the installation still has it, provisioned when truncated.

    Returns the row and whether this test created it (so cleanup removes only its own).
    """
    row = (
        await session.execute(select(Capability).where(Capability.key == key))
    ).scalar_one_or_none()
    if row is not None:
        return row, False
    row = Capability(key=key, label=f"agent-view test {key}", kind=KIND_LLM, enabled=True)
    session.add(row)
    await session.flush()
    session.add(CapabilityService(capability_id=row.id, ordinal=0, provider_id=provider.id))
    await session.commit()
    return row, True


@pytest.mark.anyio
async def test_an_agent_selection_changes_only_the_capabilities_that_agent_drives(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """Per-capability truth: the agent rung applies only where a consumer passes one.

    `AGENT_INFLUENCED_CAPABILITIES` is `{chat}` — the two call sites that pass an agent both name
    `CHAT_CAPABILITY_KEY` (`chat_chain`, `domain/chat/services`), and nothing else does. So a
    read-out for an agent must change the `chat` card WITHOUT touching a capability the agent never
    drives: the title service resolves with no agent at all, and a page that showed the agent's LLM
    there would misreport the very capability the phase's exit criterion names.
    """
    provider = await _provider(test_session)
    other, other_created = await _capability_with_candidate(
        test_session, f"zz-agent-view-{uuid.uuid4().hex[:8]}", provider
    )
    chat, chat_created = await _capability_with_candidate(test_session, "chat", provider)
    agent = await _agent(test_session, provider)

    try:
        plain = await client.get("/api/v1/providers/capabilities")
        with_agent = await client.get(f"/api/v1/providers/capabilities?agent_id={agent.id}")
        assert plain.status_code == 200, plain.text
        assert with_agent.status_code == 200, with_agent.text

        def card(body: dict, key: str) -> dict:
            return next(row for row in body["capabilities"] if row["key"] == key)

        # the agent drives chat: its declaration IS the primary, and the rung says so
        driven = card(with_agent.json(), "chat")
        assert driven["reason"] == "agent profile"
        assert driven["primary"]["source"] == "agent"
        assert driven["primary"]["provider"] == provider.name
        assert driven["primary"]["model"] == "zz-agent-model"

        # ...and a read with NO agent does not invoke rung 2: the agent is the CALLER's to pass
        assert card(plain.json(), "chat")["reason"] != "agent profile"

        # a capability the agent never drives reads IDENTICALLY either way
        assert card(plain.json(), other.key) == card(with_agent.json(), other.key)
    finally:
        await test_session.delete(agent)
        if other_created:
            await test_session.delete(other)
        if chat_created:
            await test_session.delete(chat)
        await test_session.delete(provider)
        await test_session.commit()


@pytest.mark.anyio
async def test_an_unknown_agent_is_a_404_not_a_sessionless_answer(client: AsyncClient) -> None:
    """'no such agent' is not 'no agent asked for' — a silent fallback would show the wrong chain."""
    response = await client.get("/api/v1/providers/capabilities?agent_id=999999")

    assert response.status_code == 404
    assert "999999" in response.json()["detail"]


@pytest.mark.anyio
async def test_a_chain_stored_above_zero_still_reads_back_in_order(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """What the payload owes a reader is the resolved ORDER — never a particular STORED ordinal.

    The live `chat` row is exactly this shape: its chain is the BACKUP layer, so its only candidate
    is STORED at ordinal 1 while being the first attempt whenever no agent is on the ladder. Asserting
    that the primary's ordinal IS 0 encodes the superseded assumption and goes red on that data.

    The rows here start at ordinal 1 and run to 3, so neither an "ordinal 0" assumption nor a chain
    served backwards can pass by accident — a read-out that re-sorted or reversed the chain would
    show `[1, 3, 2]` and a chain text that names the engines in the wrong order.
    """
    provider = await _provider(test_session)
    key = f"zz-ordinal-{uuid.uuid4().hex[:8]}"
    capability = Capability(key=key, label="Read-out order test", kind=KIND_LLM, enabled=True)
    test_session.add(capability)
    await test_session.flush()
    test_session.add(
        CapabilityService(capability_id=capability.id, ordinal=1, provider_id=provider.id)
    )
    test_session.add(
        CapabilityService(capability_id=capability.id, ordinal=2, service_name="zz-engine-2")
    )
    test_session.add(
        CapabilityService(capability_id=capability.id, ordinal=3, service_name="zz-engine-3")
    )
    await test_session.commit()

    try:
        response = await client.get(f"/api/v1/providers/capabilities/{key}")

        assert response.status_code == 200, response.text
        row = response.json()
        assert row["reason"] == "capability config"

        # ...served top to bottom, as stored: the ordinals never go BACKWARDS down the chain
        ordinals = [row["primary"]["ordinal"], *(b["ordinal"] for b in row["backups"])]
        assert ordinals == [1, 2, 3], f"the chain's stored order was lost — {ordinals}"
        assert row["chain"] == f"{provider.name}/zz-provider-model -> zz-engine-2 -> zz-engine-3"
    finally:
        await test_session.delete(capability)
        await test_session.delete(provider)
        await test_session.commit()


# ── The availability stamp (phase 6, group 5) ────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_the_read_out_stamps_what_is_up_on_the_resolved_candidates(
    client: AsyncClient, test_session: AsyncSession, monkeypatch
) -> None:
    """THE WIRING: the read-out carries availability — the state, the reason, and WHEN it was checked.

    Proved DISCRIMINATING by unwiring: drop `_availability_for` from `get_capabilities` and every
    candidate comes back `unknown` with no `checked_at`, which is what these assertions catch.
    """
    from app.domain.providers import availability as av

    async def fake_probe(base_url: str, path: str, headers=None):
        return {"data": [{"id": "zz-served-model"}]}

    monkeypatch.setattr(av, "probe_json", fake_probe)
    av.clear_cache()

    provider = Provider(
        name=f"zz-avail-prov-{uuid.uuid4().hex[:8]}",
        display_name="Availability read-out test provider",
        provider_type="openai",
        # Loopback → LOCAL by the class seam, so the local probe path is the one exercised.
        base_url="http://127.0.0.1:8080/v1",
        is_active=True,
        priority=97,
        is_default=False,
        config={"default_model": "zz-avail-model"},
    )
    test_session.add(provider)
    await test_session.flush()

    key = f"zz-avail-{uuid.uuid4().hex[:8]}"
    capability = Capability(key=key, label="Availability read-out test", kind=KIND_LLM, enabled=True)
    test_session.add(capability)
    await test_session.flush()
    test_session.add(
        CapabilityService(capability_id=capability.id, ordinal=0, provider_id=provider.id)
    )
    await test_session.commit()

    try:
        response = await client.get(f"/api/v1/providers/capabilities/{key}")

        assert response.status_code == 200, response.text
        primary = response.json()["primary"]
        assert primary["availability_state"] == "available"
        assert primary["available"] is True
        assert primary["checked_at"], "the copy needs WHEN it was checked"
        assert primary["availability_reason"], "and a reason a reader can act on"
    finally:
        await test_session.delete(capability)
        await test_session.delete(provider)
        await test_session.commit()


@pytest.mark.anyio
async def test_a_candidate_nothing_was_read_for_is_unknown_never_false(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """`available=None` for an unread candidate — NOT False, which would read as broken.

    A named engine (a speech engine, the external process) is a different question this read does
    not answer, and the page must be able to say "not checked here" rather than "down".
    """
    key = f"zz-unknown-{uuid.uuid4().hex[:8]}"
    capability = Capability(key=key, label="Unknown availability test", kind=KIND_SPEECH, enabled=True)
    test_session.add(capability)
    await test_session.flush()
    test_session.add(
        CapabilityService(capability_id=capability.id, ordinal=0, service_name="zz-engine")
    )
    await test_session.commit()

    try:
        response = await client.get(f"/api/v1/providers/capabilities/{key}")

        assert response.status_code == 200, response.text
        primary = response.json()["primary"]
        assert primary["availability_state"] == "unknown"
        assert primary["available"] is None
        assert primary["checked_at"] is None
    finally:
        await test_session.delete(capability)
        await test_session.commit()
