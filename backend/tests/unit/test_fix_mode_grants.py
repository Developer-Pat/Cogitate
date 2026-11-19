"""Fix-mode grants — issuing, revoking, and run-scope isolation.

The user's fix-mode grant becomes first-class: a deliberate,
session-scoped button. Three layers, honest about which is which:

- the BUTTON (the user's deliberate grant) — flips the config flag
- the GRANTS (the inspectable record) — agent_tool_grants under
  the "external" consultant identity, scope=session
- the ACP strictTools gate (the enforcement — already built, not
  re-tested here)

Plus the run-grant path: workflows DECLARE tool needs; grants are
derived at dispatch (scope=run:<workflow_id>), revoked at run end.
"""

import sys
sys.path.insert(0, "backend")

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.tools.grant_service import AgentToolGrantService
from app.domain.tools.capabilities import is_keyed
from app.domain.external_agent.services import (
    EXTERNAL_AGENT_ID, get_fix_grant_state,
)

# resolve the model graph
from app.domain.collections import models as _cm  # noqa: F401
from app.domain.tools import team_tools  # noqa: F401


class TestSessionGrantBridge:
    """save_config bridges the toggle to session grants."""

    async def test_toggle_on_issues_session_grants(self, test_session: AsyncSession):
        from app.domain.external_agent.services import save_config, get_config
        from app.domain.external_agent.schemas import ExternalAgentConfig
        from app.domain.tools.models import Tool
        import uuid

        # seed keyed tools (the test DB starts empty)
        for i, cap in enumerate(["file-write", "doc-admin", "agent-admin"]):
            test_session.add(Tool(
                id=str(uuid.uuid4()), name=f"Keyed {i}", slug=f"keyed-{i}",
                description="test", capability=cap,
            ))
        await test_session.commit()

        # ensure off first
        cfg = await get_config(test_session)
        await save_config(test_session, ExternalAgentConfig(
            command=cfg.command, cwd=cfg.cwd,
            permission_tier="chat", max_turn_seconds=cfg.max_turn_seconds,
        ))
        # toggle on (the fix tier)
        cfg = await get_config(test_session)
        await save_config(test_session, ExternalAgentConfig(
            command=cfg.command, cwd=cfg.cwd,
            permission_tier="fix", max_turn_seconds=cfg.max_turn_seconds,
        ))
        grants = AgentToolGrantService(test_session)
        rows = await grants.grants_for_agent(EXTERNAL_AGENT_ID)
        session_rows = [g for g in rows if g.scope == "session"]
        # The `fix` tier grants every KEYED tool once. That is 2, not 3:
        # file-write left the keyed tier on 2026-09-10 (needs_workspace confines
        # it to the agent's own folder, so the sandbox is the scope).
        assert len(session_rows) == 2, "each keyed tool granted once"
        # every grant covers a KEYED tool
        from app.domain.tools.models import Tool as ToolModel
        from sqlalchemy import select
        for g in session_rows:
            t = (await test_session.execute(
                select(ToolModel).where(ToolModel.id == g.tool_id)
            )).scalar_one()
            assert is_keyed(t.capability)
        assert await get_fix_grant_state(test_session) is True

    async def test_toggle_off_revokes_session_grants(self, test_session: AsyncSession):
        from app.domain.external_agent.services import save_config, get_config
        from app.domain.external_agent.schemas import ExternalAgentConfig

        cfg = await get_config(test_session)
        await save_config(test_session, ExternalAgentConfig(
            command=cfg.command, cwd=cfg.cwd,
            permission_tier="chat", max_turn_seconds=cfg.max_turn_seconds,
        ))
        grants = AgentToolGrantService(test_session)
        rows = await grants.grants_for_agent(EXTERNAL_AGENT_ID)
        session_rows = [g for g in rows if g.scope == "session"]
        assert session_rows == [], "session grants revoked on OFF"
        assert await get_fix_grant_state(test_session) is False


class TestRunGrants:
    """Workflow-declared tool needs → run-scoped grants."""

    async def test_issue_revoke_roundtrip(self, test_session: AsyncSession):
        from app.domain.tools.models import Tool
        import uuid

        tool = Tool(
            id=str(uuid.uuid4()), name="Probe", slug="probe-run-tool",
            description="test", capability="file-write",
        )
        test_session.add(tool)
        await test_session.commit()

        # simulate the dispatch helpers against the test session
        from app.domain.tools.grant_service import AgentToolGrantService
        svc = AgentToolGrantService(test_session)
        scope = "run:wf-test"
        await svc.grant("19", tool.id, granted_by="exa", scope=scope)
        rows = await svc.grants_for_agent("19")
        run_rows = [g for g in rows if g.scope == scope]
        assert len(run_rows) == 1
        assert run_rows[0].granted_by == "exa"
        # revoke at run end
        await svc.revoke("19", tool.id, scope=scope)
        rows2 = await svc.grants_for_agent("19")
        assert [g for g in rows2 if g.scope == scope] == []

    async def test_run_scope_isolated_from_session(self, test_session: AsyncSession):
        """A run grant and a session grant coexist; revoking one
        leaves the other (the scope is the isolation unit)."""
        from app.domain.tools.models import Tool
        import uuid

        tool = Tool(
            id=str(uuid.uuid4()), name="Probe2", slug="probe-run-tool2",
            description="test", capability="db-write",
        )
        test_session.add(tool)
        await test_session.commit()

        svc = AgentToolGrantService(test_session)
        await svc.grant("19", tool.id, granted_by="exa", scope="run:wf-1")
        await svc.grant("19", tool.id, granted_by="user", scope="session")
        assert await svc.has_grant("19", tool.id)
        # revoke only the run grant
        await svc.revoke("19", tool.id, scope="run:wf-1")
        assert not await svc.has_grant("19", tool.id, scopes=["run:wf-1"])
        assert await svc.has_grant("19", tool.id, scopes=["session"])
