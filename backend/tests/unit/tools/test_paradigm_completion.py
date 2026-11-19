"""The tooling-paradigm completion tests.

The unfinished half of the tooling rewrite, now done:
- GRAS tools default-on for every agent (the REGISTRY is the
  surface — no assignment row needed)
- an explicit is_enabled=0 row EXCLUDES a GRAS tool
- keyed tools need the enabled link (the grant enforces at exec)
- the chat context uses the SAME selection (no divergence)
"""
import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from app.domain.tools.capabilities import tier_for
from app.domain.tools.execution_service import ToolExecutionService
from app.domain.tools.models import AgentTool, Tool, ToolCategory, ToolUsageLog
from app.domain.tools.registry import ToolRegistry


async def _mock_calculator_handler(config, expression="0", **kwargs):
    return {"success": True, "result": 42}


@pytest_asyncio.fixture
async def clean_db(test_session):
    """Clear all tools tables before each test (the house pattern)."""
    await test_session.execute(delete(ToolUsageLog))
    await test_session.execute(delete(AgentTool))
    await test_session.execute(delete(Tool))
    await test_session.execute(delete(ToolCategory))
    await test_session.commit()
    return test_session


@pytest_asyncio.fixture
async def tools_in_registry(clean_db):
    """Register the canonical tools in the singleton AND the DB rows
    (the execution path reads the DB for the definition; the tier
    gate reads the registry)."""
    from datetime import datetime, timezone
    reg = ToolRegistry.get_instance()
    now = datetime.now(timezone.utc)
    defs = [
        ("Calculator", "calculator", "math", _mock_calculator_handler, "calculator", None),
        ("Graph Query", "graph-query", "topology", lambda c, **k: {"success": True}, "db-query", None),
        ("Restart Backend", "restart-backend", "admin", lambda c, **k: {"success": True}, "system-diag", "keyed"),
    ]
    for name, slug, desc, handler, capability, tier in defs:
        reg.register(
            name=name, slug=slug, description=desc, handler=handler,
            capability=capability, access_tier=tier, is_builtin=True,
        )
        # the DB row (what the execution path resolves) — the id is a UUID
        import uuid as _uuid
        clean_db.add(Tool(
            id=_uuid.uuid4().hex, name=name, slug=slug, description=desc,
            capability=capability,
            access_tier=tier,
            is_builtin=True,
            created_at=now, updated_at=now,
        ))
    await clean_db.commit()
    return clean_db


def test_tier_vocabulary():
    # the declared access_tier is used DIRECTLY (gras/keyed); the
    # capability derives its tier from the vocabulary
    assert tier_for("system-diag") == "gras"
    assert tier_for("agent-admin") == "keyed"


@pytest.mark.anyio
async def test_gras_defaults_on_for_unlinked_agent(tools_in_registry):
    svc = ToolExecutionService(tools_in_registry)
    tools = await svc.get_enabled_tools_for_agent("no-links-agent")
    slugs = {t["function"]["name"] for t in tools}
    assert "calculator" in slugs      # GRAS default-on
    assert "graph-query" in slugs


@pytest.mark.anyio
async def test_keyed_tools_not_default(tools_in_registry):
    svc = ToolExecutionService(tools_in_registry)
    tools = await svc.get_enabled_tools_for_agent("no-links-agent")
    slugs = {t["function"]["name"] for t in tools}
    assert "restart-backend" not in slugs  # keyed needs the link


@pytest.mark.anyio
async def test_exclusion_blocks_a_gras_tool(tools_in_registry):
    db = tools_in_registry
    tool = (await db.execute(select(Tool).where(Tool.slug == "calculator"))).scalars().first()
    # the exclusion row: agent_tools with is_enabled=0
    db.add(AgentTool(agent_id="excl-agent", tool_id=tool.id, is_enabled=False))
    await db.commit()
    svc = ToolExecutionService(db)
    tools = await svc.get_enabled_tools_for_agent("excl-agent")
    slugs = {t["function"]["name"] for t in tools}
    assert "calculator" not in slugs


@pytest.mark.anyio
async def test_execute_gras_for_unlinked_agent(tools_in_registry):
    svc = ToolExecutionService(tools_in_registry)
    r = await svc.execute_tool_for_agent(999999, "calculator", {"expression": "2+2"})
    assert r.success is True


@pytest.mark.anyio
async def test_execute_keyed_without_link_denied(tools_in_registry):
    svc = ToolExecutionService(tools_in_registry)
    r = await svc.execute_tool_for_agent(999999, "restart-backend", {})
    assert r.success is False
    assert r.error_type in ("ToolNotEnabled", "ToolKeyRequired")


@pytest.mark.asyncio
async def test_delete_agent_registered_and_gated(monkeypatch):
    from app.domain.tools.registry import ToolRegistry, init_default_registry
    import app.domain.tools.registry as reg_mod
    # the singleton may hold only a previous test's tools (the
    # full-suite order) — build the default registry fresh. The
    # reset must ALSO clear the idempotency flag (init_default
    # guards on it — a stale flag skips registration).
    ToolRegistry.reset()
    reg_mod._DEFAULT_REGISTRY_INITIALIZED = False
    init_default_registry()
    reg = ToolRegistry.get_instance()
    assert "delete-agent" in reg.get_all_slugs()
    # the keyed tier is declared on the definition
    tool = reg.get("delete-agent")
    assert tool is not None
    assert tool.metadata.get("access_tier") == "keyed"
    # without the grant (patched): admin_denied — the gate fires
    # BEFORE any delete attempt
    monkeypatch.setattr(reg_mod, "_fix_mode_granted", lambda: False)
    r = await reg.execute_tool("delete-agent", {}, {"agent_id": 999999})
    assert r.get("success") is False
    assert r.get("error_type") == "admin_denied"
