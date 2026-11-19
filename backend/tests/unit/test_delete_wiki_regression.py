"""The agent-delete and wiki-root-page regression tests.

Two silent breakages:
1. DELETE /agents/{id} was unregistered (the export/import commit
   consumed the decorator — the route ran the EXPORT handler).
2. /wiki defaulted to 'index' which no longer exists (renamed to
   'Site Index' in the Obsidian-graph rename).
"""

import sys
sys.path.insert(0, "backend")

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.collections import models as _cm  # noqa: F401
from app.domain.tools import team_tools  # noqa: F401


class TestAgentDeleteRoute:
    """The DELETE /agents/{id} route is registered and deletes."""

    async def test_delete_route_registered(self, client):
        """DELETE on a missing agent → 404 (the route EXISTS and
        resolves; the pre-fix state ran export_agent instead)."""
        resp = await client.delete("/api/v1/agents/999999")
        assert resp.status_code == 404

    async def test_delete_removes_agent(self, client, test_session: AsyncSession):
        from app.domain.agents.services import AgentService
        from app.domain.agents.schemas import AgentCreate
        svc = AgentService(test_session)
        a = await svc.create(AgentCreate(
            name="Delete Me Route", description="d", provider="deepseek",
            model="deepseek-v4-flash",
        ))
        await test_session.commit()
        aid = a.id
        resp = await client.delete(f"/api/v1/agents/{aid}")
        # the recoverable delete: 200 with the report (not 204) —
        # the row is SOFT-deleted (deleted_at set). This agent was
        # created via the SERVICE directly (no workspace_key), so
        # there is no workspace to archive — archived_path is None
        # (correct: a shallow agent has no disk footprint).
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] is True
        # the test_session may hold a stale cached copy — expire it
        test_session.expire_all()
        row = await svc.get_by_id(aid)
        assert row is not None
        assert row.deleted_at is not None


class TestWikiRoot:
    """/wiki renders the Site Index page, not 'index'."""

    async def test_site_index_exists(self, client):
        resp = await client.get("/api/v1/wiki/Site%20Index")
        assert resp.status_code == 200

    async def test_legacy_index_is_gone(self, client):
        """The old default ('index') is 404 — the viewer must not
        default to it."""
        resp = await client.get("/api/v1/wiki/index")
        assert resp.status_code == 404
