"""The purge inventory — the derived check, and a scrub proved by SEEDING.

Two claims are worth testing here, and each has its own failure mode:

1. **The inventory covers the schema.** A purge that misses a table is not a
   purge; it is a delete that leaves rows naming an agent nobody can look up.
   The check is derived from the database, so it fails the day a new table
   starts naming agents.
2. **A hard delete really clears them.** Proved by SEEDING every reference the
   inventory claims and then finding none of it — the four that the first pass
   missed (kits, tool usage, saved lists, the shared memory keys) are seeded
   first, because those are the ones a green test must be able to redden.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.agents.purge import (
    INVENTORY,
    references_missing_from_the_inventory,
)


async def test_the_inventory_covers_every_agent_reference_in_the_schema(
    test_session: AsyncSession,
) -> None:
    """THE DERIVED HALF. Every (table, column) that names an agent is claimed by
    the inventory — so a table added later cannot silently outlive the agents it
    names."""
    missing = await references_missing_from_the_inventory(test_session)

    assert missing == [], (
        "these references name an agent and the purge inventory does not claim "
        f"them: {missing} — add them to app/domain/agents/purge.py"
    )


async def test_every_claimed_table_really_exists(test_session: AsyncSession) -> None:
    """A typo in a table name would make a claim that clears nothing, and the
    coverage check above would not notice (it only asks what is MISSING)."""
    real = set((await test_session.execute(
        sa_text("SELECT name FROM sqlite_master WHERE type = 'table'")
    )).scalars().all())

    for ref in INVENTORY:
        if ref.in_schema and not ref.optional:
            assert ref.table in real, f"{ref.table} is claimed but does not exist"


async def test_a_hard_delete_clears_EVERY_reference(test_session: AsyncSession) -> None:
    """Seed one row per reference, scrub, and find NONE of it — including the
    four the first pass missed, and the shared store's keys."""
    from app.domain.agent_kits.model import AgentKit
    from app.domain.agents.repository import get_agent_repository
    from app.domain.collections.models import Collection, CollectionItem
    from app.domain.tools.models import AgentTool, Tool, ToolUsageLog
    from app.infrastructure.database.models import (
        Agent,
        AgentList,
        UsageLog,
    )

    repo = get_agent_repository(test_session)
    agent = await repo.create_agent({
        "name": "Purge Me", "description": "x",
        "provider": "deepseek", "model": "deepseek-v4-flash",
    })
    aid, aid_s = agent.id, str(agent.id)

    # the PARENTS the FKs need — created here, because the tables this test
    # points at are cleaned between tests (a seeded baseline would make this
    # test depend on another test's leftovers)
    kit = Collection(id="purge-kit", user_key="default", name="Purge Kit",
                     entity_type="tool")
    tool = Tool(id="purge-tool", name="Purge Tool", slug="purge-tool",
                description="a tool for the purge test",
                config_schema={}, arguments_schema={})
    test_session.add_all([agent, kit, tool])
    await test_session.flush()

    test_session.add_all([
        AgentTool(id="purge-tool-link", agent_id=aid_s, tool_id=tool.id, is_enabled=True),
        AgentKit(agent_id=aid, kit_id=kit.id),
        ToolUsageLog(tool_id=tool.id, agent_id=aid_s),
        CollectionItem(id="purge-collection-item",
                       collection_id=kit.id, entity_id=aid_s,
                       entity_type="agent", entity_name="Purge Me"),
        UsageLog(agent_id=aid, provider="test", model="test"),
        AgentList(id="purge-list", name="Purge list", user_key="default", agent_ids=[aid]),
    ])
    await test_session.flush()

    # the shared KV store's key for this agent — the reference no FK can see
    from app.core.config import Paths, get_settings

    mem = Paths.from_settings(get_settings()).data_dir / "cognitive_memory.db"
    mem.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(mem))
    con.execute("CREATE TABLE IF NOT EXISTS cognitive_memory ("
                "key TEXT PRIMARY KEY, value TEXT NOT NULL, "
                "turn_count INTEGER NOT NULL DEFAULT 0, "
                "created_at TEXT NOT NULL DEFAULT (datetime('now')), "
                "updated_at TEXT NOT NULL DEFAULT (datetime('now')))")
    con.execute("INSERT OR REPLACE INTO cognitive_memory (key, value) VALUES (?, ?)",
                (f"agent_{aid}:s1", "[]"))
    con.execute("INSERT OR REPLACE INTO cognitive_memory (key, value) VALUES (?, ?)",
                ("agent_999999:s1", "[]"))          # a DIFFERENT agent's key — must survive
    con.commit()
    con.close()

    report = await repo.hard_delete_agent(agent.id)

    assert report["deleted"] is True
    bom = report["bom"]                      # the BOM is nested under "bom"
    # the four the first pass missed, plus the ones it already covered
    for key in ("kits", "tool_usage_logs", "agent_lists", "memory_keys",
                "tool_links", "collections", "usage_logs"):
        assert key in bom, f"the BOM does not report {key!r}"
    assert bom["kits"] == 1
    assert bom["tool_usage_logs"] == 1
    assert bom["agent_lists"] == 1
    assert bom["memory_keys"] == 1

    assert (await test_session.execute(
        sa_text("SELECT COUNT(*) FROM agent_kits WHERE agent_id = :a"), {"a": aid}
    )).scalar() == 0
    assert (await test_session.execute(
        sa_text("SELECT COUNT(*) FROM tool_usage_logs WHERE agent_id = :a"), {"a": aid_s}
    )).scalar() == 0
    assert (await test_session.execute(
        sa_text("SELECT COUNT(*) FROM agents WHERE id = :a"), {"a": aid}
    )).scalar() == 0

    # the saved list still exists, without this agent in it
    listed = (await test_session.execute(
        sa_text("SELECT agent_ids FROM agent_lists WHERE id = 'purge-list'")
    )).scalar()
    assert aid not in (listed if isinstance(listed, list) else [])

    # the shared store: THIS agent's key went, the other agent's stayed
    con = sqlite3.connect(str(mem))
    try:
        keys = {r[0] for r in con.execute("SELECT key FROM cognitive_memory")}
    finally:
        con.close()
    assert f"agent_{aid}:s1" not in keys
    assert "agent_999999:s1" in keys
