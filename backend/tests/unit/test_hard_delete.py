"""Hard delete scrubs the agent row, its references, workspace and memory; restore stays gated.

The IRREVERSIBLE scrub: the row + every reference + the workspace
+ memory all go. The API endpoint's hard flag + the tool's hard
mode.
"""
import pytest
from sqlalchemy import select

from app.infrastructure.database.models import Agent


@pytest.mark.anyio
async def test_hard_delete_scrubs_the_row(test_session):
    """The hard delete removes the row entirely (not soft-deleted)."""
    from app.domain.agents.repository import get_agent_repository
    repo = get_agent_repository(test_session)
    # create a throwaway
    agent = Agent(
        name="scrub-me", provider="deepseek", model="deepseek-v4-flash",
        is_active=True,
    )
    test_session.add(agent)
    await test_session.commit()
    await test_session.refresh(agent)

    report = await repo.hard_delete_agent(agent.id)
    assert report.get("deleted") is True
    assert report.get("irreversible") is True
    # the row is GONE
    gone = (await test_session.execute(
        select(Agent).where(Agent.id == agent.id)
    )).scalars().first()
    assert gone is None


@pytest.mark.anyio
async def test_hard_delete_unknown_agent(test_session):
    from app.domain.agents.repository import get_agent_repository
    repo = get_agent_repository(test_session)
    report = await repo.hard_delete_agent(999999)
    assert report.get("deleted") is False
    assert report.get("reason") == "not found"


# ── The lifecycle-tool surface (2026-08-19) ────────────────────────

@pytest.mark.asyncio
async def test_lifecycle_tools_registered(monkeypatch):
    from app.domain.tools.registry import ToolRegistry, init_default_registry
    import app.domain.tools.registry as reg_mod
    ToolRegistry.reset()
    reg_mod._DEFAULT_REGISTRY_INITIALIZED = False
    init_default_registry()
    reg = ToolRegistry.get_instance()
    slugs = reg.get_all_slugs()
    assert "list-archived-agents" in slugs
    assert "restore-agent" in slugs
    # the restore tool is keyed; the list tool is read-only (gras)
    assert reg.get("restore-agent").metadata.get("access_tier") == "keyed"


@pytest.mark.asyncio
async def test_list_archived_agents_read_only(monkeypatch):
    # no grant needed — the read tool works without the gate
    from app.domain.tools.registry import ToolRegistry, init_default_registry
    import app.domain.tools.registry as reg_mod
    ToolRegistry.reset()
    reg_mod._DEFAULT_REGISTRY_INITIALIZED = False
    init_default_registry()
    reg = ToolRegistry.get_instance()
    r = await reg.execute_tool("list-archived-agents", {}, {})
    assert r.get("success") is True
    assert "archived" in r
    assert isinstance(r.get("archived"), list)


@pytest.mark.asyncio
async def test_restore_agent_gated(monkeypatch):
    # the restore tool is KEYED — without the grant: admin_denied
    from app.domain.tools.registry import ToolRegistry, init_default_registry
    import app.domain.tools.registry as reg_mod
    ToolRegistry.reset()
    reg_mod._DEFAULT_REGISTRY_INITIALIZED = False
    init_default_registry()
    reg = ToolRegistry.get_instance()
    monkeypatch.setattr(reg_mod, "_fix_mode_granted", lambda: False)
    r = await reg.execute_tool("restore-agent", {}, {"agent_id": 999999})
    assert r.get("success") is False
    assert r.get("error_type") == "admin_denied"
