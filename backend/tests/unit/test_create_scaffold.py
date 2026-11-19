"""Agent scaffolding — the folder, the derived agent.json, and rollback on failure.

- create makes the workspace folder + derived agent.json + skills/
- agent.json is DERIVED (a snapshot: db_id + workspace_key +
  _derived: true) — never a second source of truth
- a folder-write failure ROLLS BACK the row (no half-created agents)
- workspace_key is stable/unique (slugified, deduped)
"""

import sys
sys.path.insert(0, "backend")

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.collections import models as _cm  # noqa: F401
from app.domain.tools import team_tools  # noqa: F401


class TestCreateScaffolds:
    async def test_create_makes_folder_and_agent_json(
        self, test_session: AsyncSession,
    ):
        from app.domain.agents.repository import get_agent_repository
        from app.domain.agents.workspace import AGENTS_ROOT
        repo = get_agent_repository(test_session)
        a = await repo.create_agent({
            "name": "Scaffold Born", "description": "b",
            "provider": "deepseek", "model": "deepseek-v4-flash",
        })
        assert a.workspace_key == "scaffold-born"
        ws = AGENTS_ROOT / a.workspace_key
        assert ws.is_dir()
        assert (ws / "skills").is_dir()
        assert (ws / "agent.json").exists()

    async def test_agent_json_is_derived(
        self, test_session: AsyncSession,
    ):
        import json
        from app.domain.agents.repository import get_agent_repository
        from app.domain.agents.workspace import AGENTS_ROOT
        repo = get_agent_repository(test_session)
        a = await repo.create_agent({
            "name": "Derived Agent", "description": "d",
            "provider": "deepseek", "model": "deepseek-v4-flash",
        })
        meta = json.loads(
            (AGENTS_ROOT / a.workspace_key / "agent.json").read_text()
        )
        assert meta["db_id"] == a.id
        assert meta["workspace_key"] == a.workspace_key
        assert meta["_derived"] is True
        assert meta["name"] == "Derived Agent"

    async def test_folder_failure_rolls_back_row(
        self, test_session: AsyncSession,
    ):
        """A folder-write failure removes the row — no half-created
        agents."""
        from app.domain.agents.repository import get_agent_repository
        from app.domain.agents import workspace as ws_mod
        repo = get_agent_repository(test_session)

        def boom(agent):
            raise OSError("disk full (test)")

        orig = ws_mod.scaffold
        ws_mod.scaffold = boom
        try:
            with pytest.raises(OSError):
                await repo.create_agent({
                    "name": "Rollback Agent", "description": "r",
                    "provider": "deepseek",
                    "model": "deepseek-v4-flash",
                })
        finally:
            ws_mod.scaffold = orig

        # the row must be gone
        from app.infrastructure.database.models import Agent
        from sqlalchemy import select
        rows = (await test_session.execute(
            select(Agent).where(Agent.name == "Rollback Agent")
        )).scalars().all()
        assert len(rows) == 0

    async def test_workspace_key_unique_on_slug_collision(
        self, test_session: AsyncSession,
    ):
        """Names that differ but slug to the same key still get
        distinct workspaces (the name ban forbids exact duplicates,
        so the collision is at the SLUG level: 'Collision Agent'
        vs 'collision agent')."""
        from app.domain.agents.repository import get_agent_repository
        repo = get_agent_repository(test_session)
        a1 = await repo.create_agent({
            "name": "Collision Agent", "description": "1",
            "provider": "deepseek", "model": "deepseek-v4-flash",
        })
        a2 = await repo.create_agent({
            "name": "collision agent", "description": "2",
            "provider": "deepseek", "model": "deepseek-v4-flash",
        })
        assert a1.workspace_key != a2.workspace_key
        assert a2.workspace_key.startswith("collision-agent")
