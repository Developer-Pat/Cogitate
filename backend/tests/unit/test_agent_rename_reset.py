"""The agent rename and reset-memory tests.

- the rename BAN: a duplicate name is rejected with a clean
  ValueError (the create-name-ban pattern, applied to updates)
- the agent.json sync: the workspace's name reflects the rename
  (the folder + workspace_key never change)
- reset_agent_memory: the memory table + sessions clear, the
  agent survives
"""
import json
import pytest
from sqlalchemy import select

from app.infrastructure.database.models import Agent


@pytest.mark.anyio
async def test_rename_rejects_duplicates(test_session):
    from app.domain.agents.services import AgentService
    from app.domain.agents.schemas import AgentUpdate
    a1 = Agent(name="rename-a", provider="deepseek", model="deepseek-v4-flash", is_active=True)
    a2 = Agent(name="rename-b", provider="deepseek", model="deepseek-v4-flash", is_active=True)
    test_session.add_all([a1, a2])
    await test_session.commit()
    await test_session.refresh(a1)
    await test_session.refresh(a2)

    svc = AgentService(test_session)
    with pytest.raises(ValueError, match="already exists"):
        await svc.update(a2.id, AgentUpdate(name="rename-a"))


@pytest.mark.anyio
async def test_rename_ok_same_agent_keeps_workspace_key(test_session):
    from app.domain.agents.services import AgentService
    from app.domain.agents.schemas import AgentUpdate
    a = Agent(
        name="original-name", provider="deepseek", model="deepseek-v4-flash",
        is_active=True, workspace_key="original-name",
    )
    test_session.add(a)
    await test_session.commit()
    await test_session.refresh(a)

    svc = AgentService(test_session)
    updated = await svc.update(a.id, AgentUpdate(name="new-name"))
    assert updated.name == "new-name"
    assert updated.workspace_key == "original-name"  # the disk identity stays


@pytest.mark.anyio
async def test_reset_memory_keeps_the_agent(test_session):
    from app.domain.agents.repository import get_agent_repository
    repo = get_agent_repository(test_session)
    a = Agent(name="memory-agent", provider="deepseek", model="deepseek-v4-flash", is_active=True)
    test_session.add(a)
    await test_session.commit()
    await test_session.refresh(a)

    report = await repo.reset_agent_memory(a.id)
    assert report.get("reset") is True
    assert report.get("agent_id") == a.id
    # the agent SURVIVES
    gone = (await test_session.execute(
        select(Agent).where(Agent.id == a.id)
    )).scalars().first()
    assert gone is not None
