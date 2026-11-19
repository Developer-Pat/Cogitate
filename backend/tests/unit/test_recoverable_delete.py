"""The recoverable delete — the move to the trash, and the builtin guard.

- deleting an agent MOVES the workspace onto the trash's agents
  shelf (`trash/agents/`, never hard-deleted) + reports the path
- the row is SOFT-deleted (deleted_at + archived_path) — NOT
  hard-deleted; history keeps its reference, and the row is what
  makes the shelf entry restorable
- relational rows (tool links, grants, collections, chat
  sessions) are removed
- built-in agents stay protected (ValueError → 403)
- the delete returns the BOM + where the workspace landed
"""

import sys
sys.path.insert(0, "backend")

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.collections import models as _cm  # noqa: F401
from app.domain.tools import team_tools  # noqa: F401


class TestRecoverableDelete:
    async def test_delete_archives_and_soft_deletes(
        self, test_session: AsyncSession,
    ):
        from app.domain.agents.repository import get_agent_repository
        from app.domain.agents.workspace import AGENTS_ROOT
        from sqlalchemy import select
        from app.infrastructure.database.models import Agent

        repo = get_agent_repository(test_session)
        a = await repo.create_agent({
            "name": "Delete Me C", "description": "c",
            "provider": "deepseek", "model": "deepseek-v4-flash",
        })
        ws = AGENTS_ROOT / a.workspace_key
        assert ws.is_dir()

        report = await repo.delete_agent(a.id)
        assert report["deleted"] is True
        assert report["archived_path"] is not None
        # the workspace moved to .archived — the original is gone
        assert not ws.exists()
        import pathlib
        assert pathlib.Path(report["archived_path"]).exists()
        # the row SURVIVES, soft-deleted
        row = (await test_session.execute(
            select(Agent).where(Agent.id == a.id)
        )).scalar_one()
        assert row.deleted_at is not None
        assert row.archived_path == report["archived_path"]
        assert row.is_active is False

    async def test_delete_removes_relational_rows(
        self, test_session: AsyncSession,
    ):
        from app.domain.agents.repository import get_agent_repository
        from sqlalchemy import select
        from app.domain.tools.models import AgentTool, AgentToolGrant
        from app.domain.collections.models import CollectionItem
        from app.infrastructure.database.models import Agent

        repo = get_agent_repository(test_session)
        a = await repo.create_agent({
            "name": "Relational C", "description": "c",
            "provider": "deepseek", "model": "deepseek-v4-flash",
        })
        aid = str(a.id)
        # seed relational rows
        test_session.add(AgentTool(id="tool-link-c", agent_id=aid,
                                   tool_id="00000000000000000000000000000001",
                                   is_enabled=True))
        test_session.add(CollectionItem(id="col-item-c",
                                        collection_id="00000000000000000000000000000002",
                                        entity_id=aid, entity_type="agent",
                                        entity_name="Relational C"))
        await test_session.flush()

        await repo.delete_agent(a.id)
        assert (await test_session.execute(
            select(AgentTool).where(AgentTool.agent_id == aid)
        )).scalars().all() == []
        assert (await test_session.execute(
            select(CollectionItem).where(CollectionItem.entity_id == aid)
        )).scalars().all() == []
        assert (await test_session.execute(
            select(AgentToolGrant).where(AgentToolGrant.agent_id == aid)
        )).scalars().all() == []

    async def test_builtin_protected(
        self, test_session: AsyncSession,
    ):
        from app.domain.agents.repository import get_agent_repository
        from app.infrastructure.database.models import Agent
        a = Agent(id=999901, name="Builtin C", description="b",
                  provider="deepseek", model="deepseek-v4-flash",
                  is_builtin=True)
        test_session.add(a)
        await test_session.flush()
        repo = get_agent_repository(test_session)
        with pytest.raises(ValueError):
            await repo.delete_agent(a.id)
