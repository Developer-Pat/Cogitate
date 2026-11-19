"""The resource card — provider locality and collective membership.

The selection surface Exa/the resource manager will read:
- the provider spec classifier (local/cloud + size, derived)
- the ARM card block on the agent card (depth, competence, spec,
  capability — the two-audience principle)
- skills declared at agent creation flow through to the card
"""

import sys
sys.path.insert(0, "backend")

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.tools.provider_spec import (
    spec_for, location_for, LOCAL, CLOUD, SMALL, MEDIUM, BIG,
)

# resolve the model graph
from app.domain.collections import models as _cm  # noqa: F401
from app.domain.tools import team_tools  # noqa: F401


class TestProviderSpec:
    def test_local_providers(self):
        assert spec_for("ollama", "mistral:7b") == (LOCAL, SMALL)
        assert spec_for("ollama", "llama3.2:latest") == (LOCAL, MEDIUM)
        assert location_for("ollama") == LOCAL

    def test_cloud_providers(self):
        assert spec_for("openrouter", "nvidia/nemotron-3-super-120b-a12b:free") == (CLOUD, BIG)
        assert spec_for("deepseek", "deepseek-v4-flash") == (CLOUD, SMALL)
        assert spec_for("openrouter", "nvidia/nemotron-nano-12b-v2-vl:free") == (CLOUD, SMALL)

    def test_localhost_base_url(self):
        assert location_for("anything", base_url="http://localhost:11434") == LOCAL
        assert location_for("anything", base_url="http://127.0.0.1:8000") == LOCAL

    def test_unknown_defaults(self):
        assert spec_for(None, None) == (CLOUD, MEDIUM)
        assert spec_for("mystery", "weird-model") == (CLOUD, MEDIUM)


class TestCollectiveAxis:
    """ARM Phase C — collectives on the card + the picker criterion."""

    async def test_card_lists_collectives(self, test_session: AsyncSession):
        """The card carries the agent's collectives (Phase C step 3)."""
        from app.domain.agents.selection_service import select_agents
        from app.domain.collections.models import Collection, CollectionItem
        from sqlalchemy import select

        from app.domain.agents.services import AgentService
        from app.domain.agents.schemas import AgentCreate
        svc = AgentService(test_session)
        a = await svc.create(AgentCreate(
            name="Collective Card", description="c", provider="deepseek",
            model="deepseek-v4-flash",
        ))
        import uuid
        coll = Collection(id=str(uuid.uuid4()), user_key="default",
                          name="The Writers", entity_type="agent")
        test_session.add(coll)
        await test_session.flush()
        test_session.add(CollectionItem(
            id=str(uuid.uuid4()), collection_id=coll.id,
            entity_id=str(a.id), entity_type="agent", entity_name=a.name,
        ))
        await test_session.commit()

        results = await select_agents(test_session, {})
        card = next(r for r in results if r["name"] == "Collective Card")
        assert "The Writers" in card["collectives"]

    async def test_collective_criterion_filters(self, test_session: AsyncSession):
        """The collective criterion narrows the pool (never routes)."""
        from app.domain.agents.selection_service import select_agents
        from app.domain.collections.models import Collection, CollectionItem

        from app.domain.agents.services import AgentService
        from app.domain.agents.schemas import AgentCreate
        svc = AgentService(test_session)
        a1 = await svc.create(AgentCreate(
            name="In Writers", description="c", provider="deepseek",
            model="deepseek-v4-flash",
        ))
        a2 = await svc.create(AgentCreate(
            name="Not In Writers", description="c", provider="deepseek",
            model="deepseek-v4-flash",
        ))
        import uuid
        coll = Collection(id=str(uuid.uuid4()), user_key="default",
                          name="The Writers", entity_type="agent")
        test_session.add(coll)
        await test_session.flush()
        test_session.add(CollectionItem(
            id=str(uuid.uuid4()), collection_id=coll.id,
            entity_id=str(a1.id), entity_type="agent", entity_name=a1.name,
        ))
        await test_session.commit()

        results = await select_agents(test_session, {"collective": "The Writers"})
        names = [r["name"] for r in results]
        assert "In Writers" in names
        assert "Not In Writers" not in names


class TestArmCard:
    async def test_card_has_arm_block(self, test_session: AsyncSession):
        from app.domain.agents.services import AgentService
        from app.domain.agents.schemas import AgentCreate

        agent = await AgentService(test_session).create(AgentCreate(
            name="arm-test", description="ARM test",
            provider="ollama", model="mistral:7b",
            skills=["web-research"],
        ))
        card = await AgentService(test_session).get_agent_card(agent.id)
        assert card is not None
        assert card.arm is not None
        assert card.arm.spec == {"location": "local", "size": "small"}
        assert "web-research" in card.arm.competence
        assert isinstance(card.arm.capability, list)

    async def test_depth_from_cognitive_profile(self, test_session: AsyncSession):
        from app.domain.agents.services import AgentService
        from app.domain.agents.schemas import AgentCreate
        from app.infrastructure.database.models import CognitiveProfile

        # seed the profile (the test DB starts empty)
        prof = CognitiveProfile(id=6, name="research-pro")
        test_session.add(prof)
        await test_session.commit()

        agent = await AgentService(test_session).create(AgentCreate(
            name="arm-depth", description="depth test",
            provider="deepseek", model="deepseek-v4-flash",
            cognitive_profile_id=6,  # research-pro
        ))
        card = await AgentService(test_session).get_agent_card(agent.id)
        assert card.arm.depth == "research-pro"

    async def test_skills_flow_through_create(self, test_session: AsyncSession):
        from app.domain.agents.services import AgentService
        from app.domain.agents.schemas import AgentCreate

        agent = await AgentService(test_session).create(AgentCreate(
            name="arm-skills", description="skills test",
            provider="deepseek", model="deepseek-v4-flash",
            skills=["fiction-craft", "prompt-design"],
        ))
        assert sorted(agent.skills or []) == sorted(["fiction-craft", "prompt-design"])
        card = await AgentService(test_session).get_agent_card(agent.id)
        assert sorted(card.arm.competence) == sorted(["fiction-craft", "prompt-design"])
