"""Tool access tiers — every capability's tier, the grant lifecycle, and enforcement.

The two-tier model: every capability declares a tier (gras =
read-only/enabled-enough; keyed = needs an explicit grant). The
slug stays identity; the grant is a separate object.

- tier declarations: the vocabulary's map is complete + sane
- grant lifecycle: issue / has_grant / revoke / expiry
- enforcement: the execution path returns ToolKeyRequired for a
  keyed tool without a grant, executes with one, never gates gras
"""
import pytest

import sys
sys.path.insert(0, "backend")

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.tools.capabilities import (
    CAPABILITIES, GRAS, KEYED, CAPABILITY_TIERS, tier_for, is_keyed,
)
from app.domain.tools.grant_service import (
    AgentToolGrantService, _norm_uuid,
)

# resolve the model graph (circular: Tool -> TeamTool -> Collection)
from app.domain.collections import models as _cm  # noqa: F401
from app.domain.tools import team_tools  # noqa: F401


class TestTierDeclarations:
    def test_every_capability_declares_a_tier(self):
        assert set(CAPABILITY_TIERS.keys()) == set(CAPABILITIES)
        for cap, tier in CAPABILITY_TIERS.items():
            assert tier in (GRAS, KEYED), f"{cap}: {tier}"

    def test_tier_pattern(self):
        # the study's pattern: read = gras, admin = keyed.
        # file-write is deliberately GRAS (2026-09-10): every file tool carries
        # needs_workspace, so the execution service injects the agent's own
        # folder as base_path and the sandbox IS the scope. Requiring a grant
        # made a fresh agent able to read everything and write nothing, silently.
        assert not is_keyed("file-write")
        assert is_keyed("doc-admin")
        assert is_keyed("agent-admin")
        assert is_keyed("workflow-admin")
        assert not is_keyed("file-read")
        assert not is_keyed("web-search")
        assert not is_keyed("datetime")
        assert not is_keyed("db-query")

    def test_unknown_defaults_to_gras(self):
        assert tier_for(None) == GRAS
        assert tier_for("nonsense") == GRAS
        assert not is_keyed(None)


class TestUUIDNormalization:
    def test_hyphenless_becomes_hyphenated(self):
        assert _norm_uuid("08ab832c2124459f99245e1bec3cd0b0") == \
            "08ab832c-2124-459f-9924-5e1bec3cd0b0"

    def test_already_hyphenated_unchanged(self):
        assert _norm_uuid("08ab832c-2124-459f-9924-5e1bec3cd0b0") == \
            "08ab832c-2124-459f-9924-5e1bec3cd0b0"


class TestGrantLifecycle:
    async def test_grant_has_revoke(self, test_session: AsyncSession):
        svc = AgentToolGrantService(test_session)
        tool_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        assert not await svc.has_grant("42", tool_id)
        g = await svc.grant("42", tool_id, granted_by="exa", scope="run:wf1")
        assert g.agent_id == "42"
        assert g.tool_id == tool_id
        assert g.scope == "run:wf1"
        assert await svc.has_grant("42", tool_id)
        # idempotent re-issue
        g2 = await svc.grant("42", tool_id, granted_by="user", scope="run:wf1")
        assert g2.id == g.id
        # revoke
        n = await svc.revoke("42", tool_id)
        assert n >= 1
        assert not await svc.has_grant("42", tool_id)

    async def test_expired_grant_is_not_live(self, test_session: AsyncSession):
        svc = AgentToolGrantService(test_session)
        tool_id = "ffffffff-1111-2222-3333-444444444444"
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        await svc.grant("42", tool_id, scope="session", expires_at=past)
        assert not await svc.has_grant("42", tool_id)

    async def test_scope_filter(self, test_session: AsyncSession):
        svc = AgentToolGrantService(test_session)
        tool_id = "cccccccc-9999-8888-7777-666666666666"
        await svc.grant("42", tool_id, scope="permanent")
        assert await svc.has_grant("42", tool_id)
        assert await svc.has_grant("42", tool_id, scopes=["permanent"])
        assert not await svc.has_grant("42", tool_id, scopes=["session"])


class TestEnforcement:
    """The keyed gate through the real execution path (test DB).

    Builds a minimal tool + agent-tool link in the test session,
    then exercises ToolExecutionService: keyed without grant →
    ToolKeyRequired; with grant → executes; gras → never gated.
    """

    async def _seed_keyed_tool(self, session: AsyncSession):
        from app.domain.tools.models import Tool
        from app.domain.tools.models import AgentTool
        import uuid

        tool = Tool(
            id=str(uuid.uuid4()),
            name="Probe Keyed", slug="probe-keyed",
            description="test keyed tool",
            # A GENUINELY keyed capability. This was "file-write", which left the
            # keyed tier on 2026-09-10 (needs_workspace confines file tools to the
            # agent's own folder) -- so tier_for() returned GRAS, the keyed gate
            # never fired, execution proceeded, and the test saw KeyError instead
            # of ToolKeyRequired. The fixture, not the registry.
            capability="agent-admin",
        )
        session.add(tool)
        await session.flush()
        agent_tool = AgentTool(
            agent_id="999", tool_id=tool.id, is_enabled=True,
        )
        session.add(agent_tool)
        await session.commit()
        return tool

    async def test_keyed_without_grant_denied(self, test_session: AsyncSession):
        """A keyed capability without a grant is denied, before execution.

        THE KEYED GATE RUNS FIRST — ahead of the registry lookup. So a tool needs
        no registered handler for this test to be meaningful: it only needs a
        capability that is genuinely KEYED.

        The earlier failure was the FIXTURE, not the registry. It seeded
        `capability="file-write"`, which left the keyed tier on 2026-09-10, so
        `tier_for()` returned GRAS, no gate fired, execution proceeded, and the
        tool's absence from the registry surfaced as `KeyError` — which read like
        a registry problem and was actually a stale fixture.

        The gate is not loosened to make this pass; nor should the registry be. A
        tool row is still not an executable tool — that is what the declarative
        tier (app/domain/tools/declarative.py) addresses, by giving a row an
        `endpoint` and a `type` instead of a handler.
        """
        from app.domain.tools.execution_service import ToolExecutionService
        tool = await self._seed_keyed_tool(test_session)
        svc = ToolExecutionService(test_session)
        result = await svc.execute_tool_for_agent(999, "probe-keyed", {})
        assert result.success is False
        assert result.error_type == "ToolKeyRequired"

    async def test_keyed_with_grant_executes(self, test_session: AsyncSession):
        from app.domain.tools.execution_service import ToolExecutionService
        tool = await self._seed_keyed_tool(test_session)
        await AgentToolGrantService(test_session).grant("999", tool.id, scope="permanent")
        svc = ToolExecutionService(test_session)
        result = await svc.execute_tool_for_agent(999, "probe-keyed", {})
        # the grant opened the gate; the handler itself is a stub
        # (no real handler registered) so it errors AFTER the gate —
        # the point is it must NOT be ToolKeyRequired
        assert result.error_type != "ToolKeyRequired"

    async def test_gras_tool_never_gated(self, test_session: AsyncSession):
        from app.domain.tools.models import Tool
        from app.domain.tools.models import AgentTool
        from app.domain.tools.execution_service import ToolExecutionService
        import uuid

        tool = Tool(
            id=str(uuid.uuid4()), name="Probe Read", slug="probe-read",
            description="test gras tool", capability="file-read",
        )
        test_session.add(tool)
        await test_session.flush()
        test_session.add(AgentTool(agent_id="999", tool_id=tool.id, is_enabled=True))
        await test_session.commit()
        svc = ToolExecutionService(test_session)
        result = await svc.execute_tool_for_agent(999, "probe-read", {})
        assert result.error_type != "ToolKeyRequired"
