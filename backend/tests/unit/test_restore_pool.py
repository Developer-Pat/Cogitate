"""The restore path — bringing an agent back, and excluding the deleted.

- list_deleted returns soft-deleted agents + their archive paths
- restore_agent moves the workspace back + clears the markers
  (ADDITIVE — explicit, never automatic)
- soft-deleted agents are EXCLUDED from the live pool (list,
  resolve, select — the registry contract)
"""

import sys
sys.path.insert(0, "backend")

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.collections import models as _cm  # noqa: F401
from app.domain.tools import team_tools  # noqa: F401


class TestRestoreAndPool:
    async def test_restore_brings_agent_back(
        self, test_session: AsyncSession,
    ):
        from app.domain.agents.repository import get_agent_repository
        from sqlalchemy import select
        from app.infrastructure.database.models import Agent

        repo = get_agent_repository(test_session)
        a = await repo.create_agent({
            "name": "Restore Me", "description": "r",
            "provider": "deepseek", "model": "deepseek-v4-flash",
        })
        await repo.delete_agent(a.id)
        # deleted — in the deleted list, out of the live pool
        deleted = await repo.list_deleted()
        assert any(x["id"] == a.id for x in deleted)
        resolved = None
        try:
            await repo.resolve_agent("Restore Me")
        except ValueError:
            resolved = "dead-letter"
        assert resolved == "dead-letter"

        # restore — additive, explicit
        restored = await repo.restore_agent(a.id)
        assert restored.deleted_at is None
        assert restored.archived_path is None
        assert restored.is_active is True
        row = (await test_session.execute(
            select(Agent).where(Agent.id == a.id)
        )).scalar_one()
        assert row.deleted_at is None
        # back in the live pool
        live = await repo.resolve_agent("Restore Me")
        assert live.id == a.id

    async def test_restore_not_deleted_raises(
        self, test_session: AsyncSession,
    ):
        from app.domain.agents.repository import get_agent_repository
        repo = get_agent_repository(test_session)
        a = await repo.create_agent({
            "name": "Never Deleted", "description": "n",
            "provider": "deepseek", "model": "deepseek-v4-flash",
        })
        with pytest.raises(ValueError):
            await repo.restore_agent(a.id)

    async def test_deleted_excluded_from_list(
        self, test_session: AsyncSession,
    ):
        from app.domain.agents.repository import get_agent_repository
        from app.domain.agents.services import AgentService
        from app.domain.agents.schemas import AgentCreate

        repo = get_agent_repository(test_session)
        a = await repo.create_agent({
            "name": "Pool Exclusion", "description": "p",
            "provider": "deepseek", "model": "deepseek-v4-flash",
        })
        await repo.delete_agent(a.id)
        # the service's list (used by the UI) excludes it
        svc = AgentService(test_session)
        agents, total = await svc.list_all_agents()
        names = [x.name for x in agents]
        assert "Pool Exclusion" not in names
        assert total == len(agents)
