"""Kit listing, attach and detach, with 404s for unknown agents and non-tool collections.

The kits endpoints: GET/POST/DELETE /agents/{id}/kits + the
agent-owners read on the collections router — through the real
routers (the client fixture overrides the db).
"""

import pytest

from app.domain.agent_kits.model import AgentKit
from app.domain.collections.models import Collection
from app.infrastructure.database.models import Agent


def _make_agent(db, aid: int, name: str) -> Agent:
    agent = Agent(
        id=aid, name=name, description="test agent",
        provider="test", model="test-model", system_prompt="",
    )
    db.add(agent)
    return agent


def _make_kit(db, name: str, kind: str = "tool") -> Collection:
    coll = Collection(
        id="kit-" + name.lower().replace(" ", "-") + "-" + name[:2].lower(),
        user_key="default", name=name, entity_type=kind,
        is_active=True,
    )
    db.add(coll)
    return coll


@pytest.mark.asyncio
async def test_list_agent_kits_returns_the_join(test_session, client):
    bob = _make_agent(test_session, 19, "Bob")
    search = _make_kit(test_session, "Search Kit")
    workspace = _make_kit(test_session, "Workspace Kit")
    test_session.add_all([bob, search, workspace])
    await test_session.flush()
    test_session.add_all([
        AgentKit(agent_id=19, kit_id=search.id),
        AgentKit(agent_id=19, kit_id=workspace.id),
    ])
    await test_session.commit()

    resp = await client.get("/api/v1/agents/19/kits")
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_id"] == 19
    names = {k["name"] for k in data["kits"]}
    assert names == {"Search Kit", "Workspace Kit"}


@pytest.mark.asyncio
async def test_attach_kit_endpoint(test_session, client):
    bob = _make_agent(test_session, 19, "Bob")
    search = _make_kit(test_session, "Search Kit")
    test_session.add_all([bob, search])
    await test_session.commit()

    resp = await client.post("/api/v1/agents/19/kits", json={"kit_id": search.id})
    assert resp.status_code == 201
    names = {k["name"] for k in resp.json()["kits"]}
    assert names == {"Search Kit"}

    # idempotent repeat -> the kit still listed once
    resp2 = await client.post("/api/v1/agents/19/kits", json={"kit_id": search.id})
    assert resp2.status_code == 201
    assert len(resp2.json()["kits"]) == 1


@pytest.mark.asyncio
async def test_attach_unknown_agent_404(test_session, client):
    search = _make_kit(test_session, "Search Kit")
    test_session.add(search)
    await test_session.commit()

    resp = await client.post("/api/v1/agents/999/kits", json={"kit_id": search.id})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_attach_rejects_non_tool_collection(test_session, client):
    bob = _make_agent(test_session, 19, "Bob")
    team = _make_kit(test_session, "QA Team", kind="agent")
    test_session.add_all([bob, team])
    await test_session.commit()

    resp = await client.post("/api/v1/agents/19/kits", json={"kit_id": team.id})
    # the service refuses silently (no row) — the endpoint returns the
    # unchanged kit list (the kit never appears)
    assert resp.status_code == 201
    assert resp.json()["kits"] == []


@pytest.mark.asyncio
async def test_detach_kit_endpoint(test_session, client):
    bob = _make_agent(test_session, 19, "Bob")
    search = _make_kit(test_session, "Search Kit")
    test_session.add_all([bob, search])
    await test_session.flush()
    test_session.add(AgentKit(agent_id=19, kit_id=search.id))
    await test_session.commit()

    resp = await client.delete(f"/api/v1/agents/19/kits/{search.id}")
    assert resp.status_code == 204
    listing = await client.get("/api/v1/agents/19/kits")
    assert listing.json()["kits"] == []


@pytest.mark.asyncio
async def test_agent_owners_endpoint(test_session, client):
    bob = _make_agent(test_session, 19, "Bob")
    ada = _make_agent(test_session, 21, "Ada")
    search = _make_kit(test_session, "Search Kit")
    test_session.add_all([bob, ada, search])
    await test_session.flush()
    test_session.add_all([
        AgentKit(agent_id=19, kit_id=search.id),
        AgentKit(agent_id=21, kit_id=search.id),
    ])
    await test_session.commit()

    resp = await client.get(f"/api/v1/collections/{search.id}/agent-owners")
    assert resp.status_code == 200
    data = resp.json()
    assert data["kit_id"] == search.id
    assert {a["name"] for a in data["agents"]} == {"Bob", "Ada"}


@pytest.mark.asyncio
async def test_agent_owners_rejects_non_tool(test_session, client):
    team = _make_kit(test_session, "QA Team", kind="agent")
    test_session.add(team)
    await test_session.commit()

    resp = await client.get(f"/api/v1/collections/{team.id}/agent-owners")
    assert resp.status_code == 400
