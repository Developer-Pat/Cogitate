"""The repository seam — workspace resolution through the factory.

- agent_workspace returns the folder BY COLUMN (no filesystem scan)
- resolve_agent + select_agents pass through the seam unchanged
- the factory returns the disk implementation
- the export path uses the column, not a scan
"""

import sys
sys.path.insert(0, "backend")

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.collections import models as _cm  # noqa: F401
from app.domain.tools import team_tools  # noqa: F401


async def _seed(db: AsyncSession, name: str, workspace: str | None = None):
    from app.domain.agents.services import AgentService
    from app.domain.agents.schemas import AgentCreate
    svc = AgentService(db)
    a = await svc.create(AgentCreate(
        name=name, description="repo test", provider="deepseek",
        model="deepseek-v4-flash",
    ))
    if workspace:
        a.workspace_key = workspace
        await db.flush()
        await db.commit()
    return a


class TestRepositorySeam:
    async def test_factory_returns_disk_repo(self, test_session: AsyncSession):
        from app.domain.agents.repository import get_agent_repository, DiskAgentRepository
        repo = get_agent_repository(test_session)
        assert isinstance(repo, DiskAgentRepository)

    async def test_agent_workspace_by_column(self, test_session: AsyncSession):
        """The workspace comes from workspace_key — NO folder scan."""
        from app.domain.agents.repository import get_agent_repository
        a = await _seed(test_session, "Workspace Agent", workspace="ws-agent")
        repo = get_agent_repository(test_session)
        ws = await repo.agent_workspace(a.id)
        assert ws is not None
        assert ws.endswith("agents/ws-agent")

    async def test_agent_workspace_none_when_no_key(self, test_session: AsyncSession):
        from app.domain.agents.repository import get_agent_repository
        a = await _seed(test_session, "No Workspace Agent")
        repo = get_agent_repository(test_session)
        assert await repo.agent_workspace(a.id) is None

    async def test_resolve_through_seam(self, test_session: AsyncSession):
        from app.domain.agents.repository import get_agent_repository
        a = await _seed(test_session, "Seam Resolve")
        repo = get_agent_repository(test_session)
        resolved = await repo.resolve_agent("Seam Resolve")
        assert resolved.id == a.id

    async def test_select_through_seam(self, test_session: AsyncSession):
        from app.domain.agents.repository import get_agent_repository
        await _seed(test_session, "Seam Select")
        repo = get_agent_repository(test_session)
        cards = await repo.select_agents({})
        assert any(r["name"] == "Seam Select" for r in cards)

    async def test_export_uses_column_not_scan(self, test_session: AsyncSession):
        """export_service._agent_folder_path resolves via the repo —
        the scan heuristic is gone."""
        import inspect
        from app.domain.agents import export_service
        src = inspect.getsource(export_service)
        # no agents-dir scan loop in the folder lookup
        assert "os.listdir(agents_dir)" not in src
