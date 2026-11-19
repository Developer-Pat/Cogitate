"""An owned kit is the tool surface: kits union and dedupe, an empty kit means no tools.

THE POLICY: if an agent OWNS any TOOL-typed collection (a kit),
the kits ARE the surface — the GRAS default is suppressed. The
surface = the UNION of all owned kits' granted tools (deduped).
States:
1. no kit -> the current default surface (unchanged)
2. one kit with granted tools -> ONLY the kit's tools
3. N kits -> the UNION of their tools (the _35 plural rule)
4. an EMPTY kit (or all-empty kits) -> NO tools (the shallow-bot)
5. the JOIN row alone (no slot) -> the surface (the migration
   path — the agent_kits row is the truth)
"""

import pytest
import pytest_asyncio
from typing import AsyncGenerator

from sqlalchemy import delete, select
from app.domain.tools.execution_service import ToolExecutionService
from app.domain.tools.registry import ToolRegistry
from app.domain.collections.models import Collection, CollectionItem
from app.domain.agent_kits.model import AgentKit
from app.domain.tools.tool_permission_models import ToolCollectionPermission
from app.domain.tools.models import Tool
from app.domain.tools.services import ToolRegistryService
from app.domain.tools.schemas import ToolCreate
from app.domain.tools.services import AgentToolService


@pytest_asyncio.fixture(autouse=True)
async def reset_tool_registry():
    """Reset the ToolRegistry singleton before each test."""
    ToolRegistry.reset()
    yield
    ToolRegistry.reset()


@pytest_asyncio.fixture
async def clean_db(test_session) -> AsyncSession:
    """Clear the tool tables before each test."""
    from app.domain.tools.models import ToolUsageLog, ToolCategory
    await test_session.execute(delete(ToolUsageLog))
    await test_session.execute(delete(ToolCollectionPermission))
    await test_session.execute(delete(CollectionItem))
    await test_session.execute(delete(Collection))
    await test_session.execute(delete(Tool))
    await test_session.execute(delete(ToolCategory))
    await test_session.commit()
    return test_session


@pytest_asyncio.fixture
async def setup_calculator_tool(clean_db) -> AsyncSession:
    """Set up a calculator tool in the DB + the registry."""
    registry = ToolRegistry.get_instance()
    registry.register(
        name="Calculator", slug="calculator",
        description="Perform mathematical calculations",
        handler=lambda args: {"result": 0},
        config_schema={"type": "object", "properties": {"precision": {"type": "integer"}}},
        arguments_schema={"type": "object", "properties": {"expression": {"type": "string"}}},
    )
    registry_service = ToolRegistryService(clean_db)
    await registry_service.create_tool(ToolCreate(
        name="Calculator", slug="calculator",
        description="Perform mathematical calculations",
        config_schema={"type": "object", "properties": {"precision": {"type": "integer"}}},
        tags=["math", "utility"],
    ))
    return clean_db


@pytest_asyncio.fixture
async def setup_agent_with_tool(setup_calculator_tool) -> AsyncSession:
    """The base: an agent (test-agent-123) with calculator enabled."""
    db = setup_calculator_tool
    from app.infrastructure.database.models import Agent
    agent = Agent(
        id=123, name="Test Agent 123", provider="ollama", model="test",
    )
    db.add(agent)
    await db.flush()
    tool_row = (await db.execute(
        select(Tool).where(Tool.slug == "calculator")
    )).scalar_one()
    service = AgentToolService(db)
    await service.enable_tool_for_agent(
        agent_id="123", tool_id=tool_row.id,
        priority=1, config={"precision": 3},
    )
    return db


@pytest_asyncio.fixture
async def setup_toolkit_db(setup_agent_with_tool) -> AsyncSession:
    """The base: an agent (test-agent-123) with calculator enabled."""
    db = setup_agent_with_tool
    tool_row = (await db.execute(
        select(Tool).where(Tool.slug == "calculator")
    )).scalar_one_or_none()
    if not tool_row:
        tool_row = (await db.execute(select(Tool).limit(1))).scalar_one()
    db._test_tool = tool_row  # type: ignore[attr-defined]
    return db


async def _make_kit(db, name: str) -> str:
    """Create a tool-typed collection (a kit). The id is a
    client-assigned string (UUID) — the model has no default."""
    import uuid
    coll = Collection(
        id=str(uuid.uuid4()),
        user_key="test", name=name, entity_type="tool",
        is_active=True,
    )
    db.add(coll)
    await db.flush()
    return coll.id


async def _assign_agent_to_kit(db, agent_id: str, collection_id: str) -> None:
    """THE OWNERSHIP MODEL (2026-08-24, the user's correction): the
    agent OWNS the kit — set agents.kit_id directly. NOT a
    collection membership (that is the team framing)."""
    from app.infrastructure.database.models import Agent
    agent = (await db.execute(
        select(Agent).where(Agent.id == int(agent_id))
    )).scalar_one()
    agent.kit_id = collection_id
    await db.flush()


async def _assign_kit_via_join(db, agent_id: str, collection_id: str) -> None:
    """THE PLURAL OWNERSHIP (2026-09-04, the _35 build): the
    agent_kits JOIN row — the truth going forward."""
    db.add(AgentKit(agent_id=int(agent_id), kit_id=collection_id))
    await db.flush()


async def _grant_tool_to_kit(db, collection_id: str, tool_id: str) -> None:
    import uuid
    db.add(ToolCollectionPermission(
        id=str(uuid.uuid4()),
        collection_id=collection_id, tool_id=tool_id,
        permission_level="read",
    ))
    await db.flush()


class TestToolkitPolicy:
    @pytest.mark.anyio
    async def test_no_kit_keeps_the_default(self, setup_toolkit_db):
        """No kit -> the default surface (GRAS + the enabled link)."""
        service = ToolExecutionService(setup_toolkit_db)
        tools = await service.get_enabled_tools_for_agent("123")
        assert len(tools) >= 1
        names = {t["function"]["name"] for t in tools}
        assert "calculator" in names

    @pytest.mark.anyio
    async def test_kit_with_tools_is_the_surface(self, setup_toolkit_db):
        """A kit with granted tools -> ONLY the kit's tools."""
        db = setup_toolkit_db
        tool = db._test_tool  # type: ignore[attr-defined]
        kit_id = await _make_kit(db, "Bob's Kit")
        await _assign_agent_to_kit(db, "123", kit_id)
        await _grant_tool_to_kit(db, kit_id, tool.id)
        await db.commit()

        service = ToolExecutionService(db)
        tools = await service.get_enabled_tools_for_agent("123")
        names = {t["function"]["name"] for t in tools}
        assert names == {"calculator"}  # ONLY the kit's tool — no GRAS flood

    @pytest.mark.anyio
    async def test_empty_kit_means_no_tools(self, setup_toolkit_db):
        """An EMPTY kit -> NO tools (the shallow-bot fix: Bob's surface
        drops from 27 to 0 — nothing left to hallucinate)."""
        db = setup_toolkit_db
        kit_id = await _make_kit(db, "Bob's Empty Kit")
        await _assign_agent_to_kit(db, "123", kit_id)
        await db.commit()

        service = ToolExecutionService(db)
        tools = await service.get_enabled_tools_for_agent("123")
        assert tools == []

    @pytest.mark.anyio
    async def test_team_membership_is_not_a_kit(self, setup_toolkit_db):
        """Being a MEMBER of an agent-typed collection (a team) is
        NOT owning a kit — kit_id is unset, the default surface
        stays (the chat selector's team collections). The agent
        OWNS a kit only via its direct kit_id reference."""
        db = setup_toolkit_db
        import uuid
        coll = Collection(
            id=str(uuid.uuid4()),
            user_key="test", name="QA Team", entity_type="agent",
            is_active=True,
        )
        db.add(coll)
        await db.flush()
        # membership (the team framing) — NOT ownership
        db.add(CollectionItem(
            id=str(uuid.uuid4()),
            collection_id=coll.id, entity_id="123",
            entity_type="agent", entity_name="Test Agent",
        ))
        await db.flush()
        await db.commit()

        service = ToolExecutionService(db)
        tools = await service.get_enabled_tools_for_agent("123")
        assert len(tools) >= 1
        names = {t["function"]["name"] for t in tools}
        assert "calculator" in names

    # ===== THE UNION (2026-09-04, the _35 build P2) =====

    @pytest.mark.anyio
    async def test_join_row_alone_is_the_surface(self, setup_toolkit_db):
        """THE MIGRATION-PATH DISCRIMINATOR: the agent_kits JOIN row
        (no slot set) IS the surface — the policy reads the join.
        A link-only keyed tool (no kit grant) must be SUPPRESSED —
        the kits are the surface, no agent_tools links."""
        db = setup_toolkit_db
        calculator = db._test_tool  # type: ignore[attr-defined]
        # a link-only keyed tool — enabled for the agent but NOT
        # granted to the kit: the kit surface must exclude it
        from app.domain.tools.registry import ToolRegistry
        from app.domain.tools.services import ToolRegistryService, AgentToolService
        from app.domain.tools.schemas import ToolCreate
        registry = ToolRegistry.get_instance()
        registry.register(
            name="Datetime", slug="datetime",
            description="The current date and time",
            handler=lambda args: {"now": "2026-09-04"},
        )
        svc = ToolRegistryService(db)
        await svc.create_tool(ToolCreate(
            name="Datetime", slug="datetime",
            description="The current date and time",
            tags=["utility"],
        ))
        datetime_row = (await db.execute(
            select(Tool).where(Tool.slug == "datetime")
        )).scalar_one()
        await AgentToolService(db).enable_tool_for_agent(
            agent_id="123", tool_id=datetime_row.id, priority=2,
        )

        kit_id = await _make_kit(db, "Bob's Joined Kit")
        await _assign_kit_via_join(db, "123", kit_id)
        await _grant_tool_to_kit(db, kit_id, calculator.id)
        await db.commit()

        service = ToolExecutionService(db)
        tools = await service.get_enabled_tools_for_agent("123")
        names = {t["function"]["name"] for t in tools}
        assert names == {"calculator"}  # the joined kit's grant ONLY

    @pytest.mark.anyio
    async def test_two_kits_union(self, setup_toolkit_db):
        """N kits -> the UNION of their granted tools, deduped (the
        plural rule — the functional split: search + workspace)."""
        db = setup_toolkit_db
        calculator = db._test_tool  # type: ignore[attr-defined]
        # a second tool (datetime)
        from app.domain.tools.registry import ToolRegistry
        from app.domain.tools.services import ToolRegistryService
        from app.domain.tools.schemas import ToolCreate
        registry = ToolRegistry.get_instance()
        registry.register(
            name="Datetime", slug="datetime",
            description="The current date and time",
            handler=lambda args: {"now": "2026-09-04"},
        )
        svc = ToolRegistryService(db)
        await svc.create_tool(ToolCreate(
            name="Datetime", slug="datetime",
            description="The current date and time",
            tags=["utility"],
        ))
        datetime_row = (await db.execute(
            select(Tool).where(Tool.slug == "datetime")
        )).scalar_one()

        search_kit = await _make_kit(db, "Search Kit")
        workspace_kit = await _make_kit(db, "Workspace Kit")
        # one kit via the join + one via the slot (both sources union)
        await _assign_kit_via_join(db, "123", search_kit)
        await _assign_agent_to_kit(db, "123", workspace_kit)
        await _grant_tool_to_kit(db, search_kit, calculator.id)
        await _grant_tool_to_kit(db, workspace_kit, datetime_row.id)
        await db.commit()

        service = ToolExecutionService(db)
        tools = await service.get_enabled_tools_for_agent("123")
        names = {t["function"]["name"] for t in tools}
        assert names == {"calculator", "datetime"}  # the union, no GRAS flood

    @pytest.mark.anyio
    async def test_union_dedupes_shared_tools(self, setup_toolkit_db):
        """A tool granted by TWO kits appears once (the dedupe) AND
        a link-only tool (enabled for the agent, granted to NO kit)
        stays SUPPRESSED — the kits are the whole surface."""
        db = setup_toolkit_db
        calculator = db._test_tool  # type: ignore[attr-defined]
        from app.domain.tools.registry import ToolRegistry
        from app.domain.tools.services import ToolRegistryService, AgentToolService
        from app.domain.tools.schemas import ToolCreate
        registry = ToolRegistry.get_instance()
        registry.register(
            name="Datetime", slug="datetime",
            description="The current date and time",
            handler=lambda args: {"now": "2026-09-04"},
        )
        svc = ToolRegistryService(db)
        await svc.create_tool(ToolCreate(
            name="Datetime", slug="datetime",
            description="The current date and time",
            tags=["utility"],
        ))
        datetime_row = (await db.execute(
            select(Tool).where(Tool.slug == "datetime")
        )).scalar_one()
        # the link-only tool: enabled for the agent, granted to NO kit
        await AgentToolService(db).enable_tool_for_agent(
            agent_id="123", tool_id=datetime_row.id, priority=2,
        )

        kit_a = await _make_kit(db, "Kit A")
        kit_b = await _make_kit(db, "Kit B")
        await _assign_kit_via_join(db, "123", kit_a)
        await _assign_kit_via_join(db, "123", kit_b)
        await _grant_tool_to_kit(db, kit_a, calculator.id)
        await _grant_tool_to_kit(db, kit_b, calculator.id)  # shared
        await db.commit()

        service = ToolExecutionService(db)
        tools = await service.get_enabled_tools_for_agent("123")
        names = {t["function"]["name"] for t in tools}
        assert names == {"calculator"}  # deduped; the link-only datetime is OUT

    @pytest.mark.anyio
    async def test_empty_joined_kits_mean_no_tools(self, setup_toolkit_db):
        """All-owned kits empty -> NO tools (the shallow-bot rule
        holds with the plural join: any kits suppress the GRAS)."""
        db = setup_toolkit_db
        kit_a = await _make_kit(db, "Empty Kit A")
        kit_b = await _make_kit(db, "Empty Kit B")
        await _assign_kit_via_join(db, "123", kit_a)
        await _assign_kit_via_join(db, "123", kit_b)
        await db.commit()

        service = ToolExecutionService(db)
        tools = await service.get_enabled_tools_for_agent("123")
        assert tools == []
