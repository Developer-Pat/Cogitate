"""Kit attach and detach maintain the join row idempotently, and the slot migration backfills it.

The agent_kits join CRUD + the SLOT MIGRATION discriminator (the
singular agents.kit_id -> the join rows, idempotent).
"""

import pytest

from app.domain.agent_kits.model import AgentKit
from app.domain.agent_kits.service import AgentKitService
from app.domain.collections.models import Collection
from app.infrastructure.database.models import Agent


def _make_agent(name: str = "bob") -> Agent:
    return Agent(
        name=name,
        description="test agent",
        provider="test",
        model="test-model",
        system_prompt="",
    )


def _make_kit(name: str = "Search Kit", kind: str = "tool") -> Collection:
    return Collection(
        id="kit-" + name.lower().replace(" ", "-"),
        user_key="default",
        name=name,
        entity_type=kind,
    )


@pytest.mark.asyncio
async def test_attach_creates_the_join_row(test_session):
    agent = _make_agent()
    kit = _make_kit()
    test_session.add_all([agent, kit])
    await test_session.flush()

    svc = AgentKitService(test_session)
    created = await svc.attach(agent.id, kit.id)

    assert created is True
    row = await test_session.get(AgentKit, {"agent_id": agent.id, "kit_id": kit.id})
    assert row is not None


@pytest.mark.asyncio
async def test_attach_is_idempotent(test_session):
    agent = _make_agent()
    kit = _make_kit()
    test_session.add_all([agent, kit])
    await test_session.flush()

    svc = AgentKitService(test_session)
    assert await svc.attach(agent.id, kit.id) is True
    assert await svc.attach(agent.id, kit.id) is False  # already owned
    rows = await svc.kits_for_agent(agent.id)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_attach_rejects_non_tool_collections(test_session):
    agent = _make_agent()
    not_a_kit = _make_kit(name="A Team", kind="agent")
    test_session.add_all([agent, not_a_kit])
    await test_session.flush()

    svc = AgentKitService(test_session)
    assert await svc.attach(agent.id, not_a_kit.id) is False
    assert await svc.kits_for_agent(agent.id) == []


@pytest.mark.asyncio
async def test_detach_removes_the_row(test_session):
    agent = _make_agent()
    kit = _make_kit()
    test_session.add_all([agent, kit])
    await test_session.flush()
    svc = AgentKitService(test_session)
    await svc.attach(agent.id, kit.id)

    assert await svc.detach(agent.id, kit.id) is True
    assert await svc.detach(agent.id, kit.id) is False  # already gone
    assert await svc.kits_for_agent(agent.id) == []


@pytest.mark.asyncio
async def test_both_directions_answerable(test_session):
    bob = _make_agent("bob")
    ada = _make_agent("ada")
    search = _make_kit("Search Kit")
    workspace = _make_kit("Workspace Kit")
    test_session.add_all([bob, ada, search, workspace])
    await test_session.flush()

    svc = AgentKitService(test_session)
    await svc.attach(bob.id, search.id)
    await svc.attach(bob.id, workspace.id)
    await svc.attach(ada.id, search.id)

    bob_kits = {k.id for k in await svc.kits_for_agent(bob.id)}
    assert bob_kits == {search.id, workspace.id}
    search_agents = await svc.agents_for_kit(search.id)
    assert set(search_agents) == {bob.id, ada.id}


@pytest.mark.asyncio
async def test_slot_migration_creates_rows_idempotently(test_session):
    """THE MIGRATION DISCRIMINATOR: an agent with the singular
    kit_id set gains a JOIN row; a second sync creates nothing."""
    bob = _make_agent("bob")
    search = _make_kit("Search Kit")
    test_session.add_all([bob, search])
    await test_session.flush()
    bob.kit_id = search.id  # the old singular slot
    await test_session.flush()

    svc = AgentKitService(test_session)
    assert await svc.sync_from_agent_slots() == 1
    rows = await svc.kits_for_agent(bob.id)
    assert [k.id for k in rows] == [search.id]

    # idempotent — the second sync creates nothing
    assert await svc.sync_from_agent_slots() == 0
    assert len(await svc.kits_for_agent(bob.id)) == 1


@pytest.mark.asyncio
async def test_slot_migration_skips_dangling_and_non_tool(test_session):
    bob = _make_agent("bob")
    not_a_kit = _make_kit(name="A Team", kind="agent")
    test_session.add_all([bob, not_a_kit])
    await test_session.flush()
    bob.kit_id = "dangling-id"  # no such collection
    await test_session.flush()

    svc = AgentKitService(test_session)
    assert await svc.sync_from_agent_slots() == 0
    bob.kit_id = not_a_kit.id  # a non-tool collection
    await test_session.flush()
    assert await svc.sync_from_agent_slots() == 0
    assert await svc.kits_for_agent(bob.id) == []
