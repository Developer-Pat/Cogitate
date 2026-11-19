"""Registry addressing — name resolution, uniqueness, and strict lookup.

- the unique-name BAN: create rejects exact-name duplicates (the
  addressing precondition); the DB constraint enforces it
- resolve_agent(name): STRICT — resolves a unique name, raises on
  missing (dead-letter, don't hang)
- the by-name endpoint surface
"""

import sys
sys.path.insert(0, "backend")

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# resolve the model graph
from app.domain.collections import models as _cm  # noqa: F401
from app.domain.tools import team_tools  # noqa: F401


class TestNameBan:
    async def test_create_rejects_duplicate_name(self, test_session: AsyncSession):
        from app.domain.agents.services import AgentService
        from app.domain.agents.schemas import AgentCreate

        svc = AgentService(test_session)
        await svc.create(AgentCreate(
            name="Dup Test", description="first",
            provider="deepseek", model="deepseek-v4-flash",
        ))
        with pytest.raises(ValueError, match="already exists"):
            await svc.create(AgentCreate(
                name="Dup Test", description="second",
                provider="deepseek", model="deepseek-v4-flash",
            ))

    async def test_unique_constraint_enforced(self, test_session: AsyncSession):
        """The DB itself rejects duplicates (belt + suspenders)."""
        from app.domain.agents.services import AgentService
        from app.domain.agents.schemas import AgentCreate

        svc = AgentService(test_session)
        a = await svc.create(AgentCreate(
            name="Constraint Test", description="x",
            provider="deepseek", model="deepseek-v4-flash",
        ))
        # bypass the service check — insert directly
        from app.infrastructure.database.models import Agent as AgentModel
        dup = AgentModel(
            id=999999, name="Constraint Test",
            description="dup", provider="deepseek",
            model="deepseek-v4-flash", is_active=True,
        )
        test_session.add(dup)
        import sqlalchemy.exc
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            await test_session.flush()
        await test_session.rollback()


class TestResolveAgent:
    async def test_resolves_by_name(self, test_session: AsyncSession):
        from app.domain.agents.services import AgentService
        from app.domain.agents.schemas import AgentCreate

        svc = AgentService(test_session)
        created = await svc.create(AgentCreate(
            name="Resolve Me", description="x",
            provider="deepseek", model="deepseek-v4-flash",
        ))
        resolved = await svc.resolve_agent("Resolve Me")
        assert resolved.id == created.id

    async def test_strict_raises_on_missing(self, test_session: AsyncSession):
        from app.domain.agents.services import AgentService
        svc = AgentService(test_session)
        with pytest.raises(ValueError, match="No agent named"):
            await svc.resolve_agent("Does Not Exist")
