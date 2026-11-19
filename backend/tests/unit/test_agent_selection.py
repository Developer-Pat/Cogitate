"""Agent selection by capability criteria — the filtered, ranked pool.

- the selection service filters by capability (the CANONICAL
  vocabulary, not provider slugs), depth, collective, spec
- criteria are AND-ed; capability is OR-within-field; empty =
  the whole pool
- ranking is deterministic (criteria-match count, tool count,
  name)
- the per-tool access_tier override: a read-only tool in a keyed
  family (agent-select: capability agent-admin, tier gras)
"""

import sys
sys.path.insert(0, "backend")

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.collections import models as _cm  # noqa: F401
from app.domain.tools import team_tools  # noqa: F401


async def _seed(db: AsyncSession, name: str, provider: str = "deepseek",
                model: str = "deepseek-v4-flash", tags=None, tools=None,
                profile_id: int | None = None):
    # ensure the referenced tool rows exist (the test DB starts empty)
    if tools:
        from app.domain.tools.models import Tool
        from sqlalchemy import select
        for slug in tools:
            t = (await db.execute(select(Tool).where(Tool.slug == slug))).scalar_one_or_none()
            if t is None:
                import uuid
                db.add(Tool(id=str(uuid.uuid4()), name=slug, slug=slug,
                            description=slug, capability="web-search",
                            is_builtin=True, is_active=True, provider="System",
                            type="builtin", version="1.0.0"))
        await db.flush()
    # ensure the cognitive profile exists
    if profile_id is not None:
        from app.infrastructure.database.models import CognitiveProfile
        from sqlalchemy import select
        p = (await db.execute(select(CognitiveProfile).where(CognitiveProfile.id == profile_id))).scalar_one_or_none()
        if p is None:
            db.add(CognitiveProfile(id=profile_id, name="research-pro",
                                    description="deep research profile"))
        await db.flush()
    # autoflush=False — commit the fixtures so the create service's
    # validation sees them (the teardown rolls back, so it's safe)
    await db.commit()
    from app.domain.agents.services import AgentService
    from app.domain.agents.schemas import AgentCreate
    svc = AgentService(db)
    a = await svc.create(AgentCreate(
        name=name, description="sel test", provider=provider, model=model,
        tags=tags, skills=[], cognitive_profile_id=profile_id,
    ))
    # link tools (enabled) so the capability axis has data
    if tools:
        from app.domain.tools.models import AgentTool, Tool
        from sqlalchemy import select
        for slug in tools:
            t = (await db.execute(select(Tool).where(Tool.slug == slug))).scalar_one_or_none()
            if t:
                db.add(AgentTool(agent_id=str(a.id), tool_id=str(t.id), is_enabled=True))
        await db.flush()
    return a


class TestSelectionFilters:
    async def test_empty_criteria_lists_pool(self, test_session: AsyncSession):
        from app.domain.agents.selection_service import select_agents
        await _seed(test_session, "Sel A")
        await _seed(test_session, "Sel B")
        results = await select_agents(test_session, {})
        assert len(results) == 2

    async def test_capability_matches_vocabulary_not_slug(self, test_session: AsyncSession):
        """web-search matches duckduckgo/tavily (the capability, not
        the provider slug) — the canonical vocabulary is the axis."""
        from app.domain.agents.selection_service import select_agents
        from app.domain.tools.models import Tool, AgentTool
        from sqlalchemy import select
        await _seed(test_session, "Searchy", tools=["web-search"])
        results = await select_agents(test_session, {"capability": ["web-search"]})
        assert any(r["name"] == "Searchy" for r in results)

    async def test_depth_filter(self, test_session: AsyncSession):
        from app.domain.agents.selection_service import select_agents
        from sqlalchemy import select as sa_select
        from app.infrastructure.database.models import CognitiveProfile, Agent
        # profile 6 = research-pro (deep family) — seeded by _seed
        await _seed(test_session, "Deepy", profile_id=6)
        results = await select_agents(test_session, {"depth": "deep"})
        assert any(r["name"] == "Deepy" for r in results)

    async def test_anded_criteria(self, test_session: AsyncSession):
        from app.domain.agents.selection_service import select_agents
        await _seed(test_session, "Only Cloud", provider="deepseek")
        await _seed(test_session, "Local One", provider="ollama", model="mistral:7b")
        results = await select_agents(test_session, {"spec": "local"})
        assert [r["name"] for r in results] == ["Local One"]

    async def test_ranking_deterministic(self, test_session: AsyncSession):
        from app.domain.agents.selection_service import select_agents
        await _seed(test_session, "Zed", tools=["calculator"])
        await _seed(test_session, "Al", tools=["calculator"])
        results = await select_agents(test_session, {})
        # equal matches → alphabetical by name
        assert results[0]["name"] == "Al"
        assert results[-1]["name"] == "Zed"


class TestAccessTierOverride:
    async def test_agent_select_is_gras(self, test_session: AsyncSession):
        """agent-select: capability agent-admin (keyed family) but
        access_tier=gras — the read-only override."""
        from app.domain.tools.registry import init_default_registry
        reg = init_default_registry()
        t = reg._tools["agent-select"]
        assert t.capability == "agent-admin"
        assert t.metadata.get("access_tier") == "gras"

    async def test_keyed_tool_still_requires_grant(self, test_session: AsyncSession):
        """The override is per-tool, not a family-wide downgrade."""
        from app.domain.tools.registry import init_default_registry
        reg = init_default_registry()
        t = reg._tools.get("agent-manager")
        # agent-manager has no override → derives from capability
        assert t.metadata.get("access_tier") is None
