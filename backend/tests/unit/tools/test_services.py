"""
Tool category CRUD: hierarchy, listing the roots, and a missing category reported.

Tests for ToolCategoryService, ToolRegistryService, AgentToolService, and ToolUsageService.
"""

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.tools.models import ToolCategory, Tool, AgentTool, ToolUsageLog
from app.domain.tools.services import (
    ToolCategoryService,
    ToolRegistryService,
    AgentToolService,
    ToolUsageService,
)
from app.domain.tools.schemas import (
    ToolCategoryCreate,
    ToolCreate,
)
from app.domain.tools.validators import (
    validate_config_schema,
    validate_tool_config,
    ConfigValidationError,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def clean_db(test_session: AsyncSession) -> AsyncSession:
    """Clear all tools tables before each test."""
    # Clear in reverse dependency order
    await test_session.execute(delete(ToolUsageLog))
    await test_session.execute(delete(AgentTool))
    await test_session.execute(delete(Tool))
    await test_session.execute(delete(ToolCategory))
    await test_session.commit()
    return test_session


# =============================================================================
# ToolCategoryService Tests
# =============================================================================


class TestToolCategoryService:
    """Tests for ToolCategoryService."""

    @pytest.mark.anyio
    async def test_create_category(self, clean_db: AsyncSession):
        """Test creating a tool category."""
        service = ToolCategoryService(clean_db)

        category_data = ToolCategoryCreate(
            name="Search Tools",
            slug="search-tools",
            description="Tools for searching",
            icon="search",
        )
        result = await service.create_category(category_data)

        assert result.name == "Search Tools"
        assert result.slug == "search-tools"
        assert result.icon == "search"
        assert result.id is not None

    @pytest.mark.anyio
    async def test_get_category(self, clean_db: AsyncSession):
        """Test getting a category by ID."""
        service = ToolCategoryService(clean_db)

        # Create category
        category_data = ToolCategoryCreate(
            name="Test Category",
            slug="test-category",
        )
        created = await service.create_category(category_data)

        # Get category
        result = await service.get_category(created.id)

        assert result is not None
        assert result.id == created.id
        assert result.name == "Test Category"

    @pytest.mark.anyio
    async def test_get_category_not_found(self, clean_db: AsyncSession):
        """Test getting a non-existent category."""
        service = ToolCategoryService(clean_db)

        result = await service.get_category("non-existent-id")

        assert result is None

    @pytest.mark.anyio
    async def test_list_root_categories(self, clean_db: AsyncSession):
        """Test listing root categories."""
        service = ToolCategoryService(clean_db)

        # Create parent category
        parent_data = ToolCategoryCreate(
            name="Parent",
            slug="parent",
        )
        parent = await service.create_category(parent_data)

        # Create child category
        child_data = ToolCategoryCreate(
            name="Child",
            slug="child",
            parent_id=parent.id,
        )
        await service.create_category(child_data)

        # List root categories (should only return parent)
        result = await service.list_categories()

        assert len(result) == 1
        assert result[0].slug == "parent"

    @pytest.mark.anyio
    async def test_create_hierarchical_categories(self, clean_db: AsyncSession):
        """Test creating parent-child category hierarchy."""
        service = ToolCategoryService(clean_db)

        # Create parent
        parent_data = ToolCategoryCreate(
            name="Parent",
            slug="parent",
        )
        parent = await service.create_category(parent_data)

        # Create child
        child_data = ToolCategoryCreate(
            name="Child",
            slug="child",
            parent_id=parent.id,
        )
        child = await service.create_category(child_data)

        assert child.parent_id == parent.id

    @pytest.mark.anyio
    async def test_update_category(self, clean_db: AsyncSession):
        """Test updating a category."""
        service = ToolCategoryService(clean_db)

        # Create category
        category_data = ToolCategoryCreate(
            name="Original",
            slug="original",
        )
        created = await service.create_category(category_data)

        # Update
        from app.domain.tools.schemas import ToolCategoryUpdate
        update_data = ToolCategoryUpdate(
            name="Updated",
            description="New description",
        )
        result = await service.update_category(created.id, update_data)

        assert result is not None
        assert result.name == "Updated"
        assert result.description == "New description"

    @pytest.mark.anyio
    async def test_delete_category(self, clean_db: AsyncSession):
        """Test deleting a category."""
        service = ToolCategoryService(clean_db)

        # Create category
        category_data = ToolCategoryCreate(
            name="To Delete",
            slug="to-delete",
        )
        created = await service.create_category(category_data)

        # Delete
        result = await service.delete_category(created.id)

        assert result is True

        # Verify deleted
        get_result = await service.get_category(created.id)
        assert get_result is None


# =============================================================================
# ToolRegistryService Tests
# =============================================================================


class TestToolRegistryService:
    """Tests for ToolRegistryService."""

    @pytest.mark.anyio
    async def test_create_tool(self, clean_db: AsyncSession):
        """Test creating a tool."""
        service = ToolRegistryService(clean_db)

        tool_data = ToolCreate(
            name="Test Tool",
            slug="test-tool",
            description="A test tool",
            provider="TestProvider",
            config_schema={
                "type": "object",
                "properties": {
                    "api_key": {"type": "string"}
                }
            },
            tags=["test", "utility"],
        )
        result = await service.create_tool(tool_data)

        assert result.name == "Test Tool"
        assert result.slug == "test-tool"
        assert result.provider == "TestProvider"
        assert result.tags == ["test", "utility"]

    @pytest.mark.anyio
    async def test_get_tool(self, clean_db: AsyncSession):
        """Test getting a tool by ID."""
        service = ToolRegistryService(clean_db)

        # Create tool
        tool_data = ToolCreate(
            name="Get Test",
            slug="get-test",
            description="Test",
        )
        created = await service.create_tool(tool_data)

        # Get tool
        result = await service.get_tool(created.id)

        assert result is not None
        assert result.id == created.id
        assert result.name == "Get Test"

    @pytest.mark.anyio
    async def test_list_tools(self, clean_db: AsyncSession):
        """Test listing tools with filters."""
        service = ToolRegistryService(clean_db)

        # Create multiple tools
        for i in range(3):
            tool_data = ToolCreate(
                name=f"Tool {i}",
                slug=f"tool-{i}",
                description=f"Test tool {i}",
                is_active=True,
            )
            await service.create_tool(tool_data)

        # List all
        tools, total = await service.list_tools()

        assert total == 3
        assert len(tools) == 3

    @pytest.mark.anyio
    async def test_search_tools(self, clean_db: AsyncSession):
        """Test searching tools."""
        service = ToolRegistryService(clean_db)

        # Create tools
        await service.create_tool(ToolCreate(
            name="Web Search",
            slug="web-search",
            description="Search the web",
            tags=["search", "web"],
        ))
        await service.create_tool(ToolCreate(
            name="Calculator",
            slug="calculator",
            description="Calculate things",
            tags=["math"],
        ))

        # Search
        results = await service.search_tools("search")

        assert len(results) >= 1
        assert any("search" in t.name.lower() or "search" in t.description.lower() for t in results)

    @pytest.mark.anyio
    async def test_update_tool(self, clean_db: AsyncSession):
        """Test updating a tool."""
        service = ToolRegistryService(clean_db)

        # Create tool
        tool_data = ToolCreate(
            name="Original",
            slug="original-tool",
            description="Original description",
        )
        created = await service.create_tool(tool_data)

        # Update
        from app.domain.tools.schemas import ToolUpdate
        update_data = ToolUpdate(
            name="Updated",
            description="New description",
        )
        result = await service.update_tool(created.id, update_data)

        assert result is not None
        assert result.name == "Updated"
        assert result.description == "New description"

    @pytest.mark.anyio
    async def test_delete_tool(self, clean_db: AsyncSession):
        """Test deleting a tool."""
        service = ToolRegistryService(clean_db)

        # Create tool
        tool_data = ToolCreate(
            name="To Delete",
            slug="delete-me",
            description="Will be deleted",
        )
        created = await service.create_tool(tool_data)

        # Delete
        result = await service.delete_tool(created.id)

        assert result is True


# =============================================================================
# AgentToolService Tests
# =============================================================================


class TestAgentToolService:
    """Tests for AgentToolService."""

    @pytest.mark.anyio
    async def test_enable_tool_for_agent(self, clean_db: AsyncSession):
        """Test enabling a tool for an agent."""
        # Create tool first
        registry_service = ToolRegistryService(clean_db)
        tool_data = ToolCreate(
            name="Test Tool",
            slug="test-tool",
            description="Test",
        )
        tool = await registry_service.create_tool(tool_data)

        # Enable for agent
        agent_service = AgentToolService(clean_db)
        result = await agent_service.enable_tool_for_agent(
            agent_id="test-agent-id",
            tool_id=tool.id,
            priority=1,
            config={"key": "value"},
        )

        assert result.agent_id == "test-agent-id"
        assert result.tool_id == tool.id
        assert result.is_enabled is True
        assert result.priority == 1

    @pytest.mark.anyio
    async def test_list_agent_tools(self, clean_db: AsyncSession):
        """Test listing tools for an agent."""
        # Create tools
        registry_service = ToolRegistryService(clean_db)
        tool1 = await registry_service.create_tool(ToolCreate(
            name="Tool 1",
            slug="tool-1",
            description="Test",
        ))
        tool2 = await registry_service.create_tool(ToolCreate(
            name="Tool 2",
            slug="tool-2",
            description="Test",
        ))

        # Enable for agent
        agent_service = AgentToolService(clean_db)
        await agent_service.enable_tool_for_agent("agent-1", tool1.id)
        await agent_service.enable_tool_for_agent("agent-1", tool2.id)

        # List
        result = await agent_service.list_agent_tools("agent-1")

        assert len(result) == 2

    @pytest.mark.anyio
    async def test_disable_tool_for_agent(self, clean_db: AsyncSession):
        """Test disabling a tool for an agent."""
        # Create and enable tool
        registry_service = ToolRegistryService(clean_db)
        tool = await registry_service.create_tool(ToolCreate(
            name="Test",
            slug="test",
            description="Test",
        ))
        agent_service = AgentToolService(clean_db)
        await agent_service.enable_tool_for_agent("agent-1", tool.id)

        # Disable
        result = await agent_service.disable_tool_for_agent("agent-1", tool.id)

        assert result is not None
        assert result.is_enabled is False

    @pytest.mark.anyio
    async def test_remove_tool_from_agent(self, clean_db: AsyncSession):
        """Test removing a tool from an agent."""
        # Create and enable tool
        registry_service = ToolRegistryService(clean_db)
        tool = await registry_service.create_tool(ToolCreate(
            name="Test",
            slug="test",
            description="Test",
        ))
        agent_service = AgentToolService(clean_db)
        await agent_service.enable_tool_for_agent("agent-1", tool.id)

        # Remove
        result = await agent_service.remove_tool_from_agent("agent-1", tool.id)

        assert result is True

        # Verify removed
        tools = await agent_service.list_agent_tools("agent-1")
        assert len(tools) == 0


# =============================================================================
# ToolUsageService Tests
# =============================================================================


class TestToolUsageService:
    """Tests for ToolUsageService."""

    @pytest.mark.anyio
    async def test_log_usage(self, clean_db: AsyncSession):
        """Test logging tool usage."""
        # Create tool
        registry_service = ToolRegistryService(clean_db)
        tool = await registry_service.create_tool(ToolCreate(
            name="Test",
            slug="test",
            description="Test",
        ))

        # Log usage — use valid UUIDs since _is_valid_uuid() validates agent_id and session_id
        usage_service = ToolUsageService(clean_db)
        result = await usage_service.log_usage(
            tool_id=tool.id,
            agent_id="00000000-0000-0000-0000-000000000001",
            success=True,
            session_id="00000000-0000-0000-0000-000000000002",
            execution_time_ms=100,
            metadata={"query": "test query"},
        )

        assert result.tool_id == tool.id
        assert result.agent_id == "00000000-0000-0000-0000-000000000001"
        assert result.success is True
        assert result.execution_time_ms == 100

    @pytest.mark.anyio
    async def test_get_usage_logs(self, clean_db: AsyncSession):
        """Test getting usage logs."""
        # Create tool
        registry_service = ToolRegistryService(clean_db)
        tool = await registry_service.create_tool(ToolCreate(
            name="Test",
            slug="test",
            description="Test",
        ))

        # Log multiple usages — use valid UUIDs since _is_valid_uuid() validates agent_id
        usage_service = ToolUsageService(clean_db)
        for i in range(3):
            await usage_service.log_usage(
                tool_id=tool.id,
                agent_id="00000000-0000-0000-0000-000000000001",
                success=i % 2 == 0,  # Alternate success/failure
            )

        # Get logs
        logs, total = await usage_service.get_usage_logs(tool_id=tool.id)

        assert total == 3
        assert len(logs) == 3

    @pytest.mark.anyio
    async def test_usage_stats(self, clean_db: AsyncSession):
        """Test getting usage statistics."""
        # Create tool
        registry_service = ToolRegistryService(clean_db)
        tool = await registry_service.create_tool(ToolCreate(
            name="Test",
            slug="test",
            description="Test",
        ))

        # Log usages — use valid UUIDs since _is_valid_uuid() validates agent_id
        usage_service = ToolUsageService(clean_db)
        for _ in range(5):
            await usage_service.log_usage(
                tool_id=tool.id,
                agent_id="00000000-0000-0000-0000-000000000001",
                success=True,
                execution_time_ms=100,
            )
        for _ in range(2):
            await usage_service.log_usage(
                tool_id=tool.id,
                agent_id="00000000-0000-0000-0000-000000000001",
                success=False,
            )

        # Get stats
        stats = await usage_service.get_usage_stats(tool_id=tool.id)

        assert "stats" in stats
        assert len(stats["stats"]) >= 1
        tool_stats = stats["stats"][0]
        assert tool_stats["total_usage"] == 7
        assert tool_stats["successes"] == 5
        assert tool_stats["failures"] == 2


# =============================================================================
# Validator Tests
# =============================================================================


class TestValidators:
    """Tests for JSON Schema validators."""

    def test_validate_valid_schema(self):
        """Test validating a valid JSON Schema."""
        schema = {
            "type": "object",
            "properties": {
                "api_key": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 100}
            },
            "required": ["api_key"]
        }

        # Should not raise
        validate_config_schema(schema)

    def test_validate_invalid_schema_type(self):
        """Test validating schema with wrong type."""
        schema = {
            "type": "array",  # Should be "object"
            "items": {"type": "string"}
        }

        with pytest.raises(ConfigValidationError):
            validate_config_schema(schema)

    def test_validate_required_properties_defined(self):
        """Test that required properties are defined."""
        schema = {
            "type": "object",
            "properties": {
                "api_key": {"type": "string"}
            },
            "required": ["api_key", "undefined_field"]  # undefined_field not defined
        }

        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config_schema(schema)

        # Check the errors list — str(exception) returns only the message, not the detail
        assert any("undefined_field" in e for e in exc_info.value.errors)

    def test_validate_tool_config_valid(self):
        """Test validating tool configuration."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "count": {"type": "integer", "minimum": 1, "maximum": 10}
            },
            "required": ["name"]
        }

        config = {
            "name": "Test",
            "count": 5
        }

        is_valid, errors = validate_tool_config(config, schema)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_tool_config_missing_required(self):
        """Test validating config with missing required field."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "required": ["name"]
        }

        config = {}  # Missing 'name'

        is_valid, errors = validate_tool_config(config, schema)

        assert is_valid is False
        assert any("name" in e for e in errors)

    def test_validate_tool_config_type_mismatch(self):
        """Test validating config with wrong type."""
        schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"}
            }
        }

        config = {
            "count": "not a number"  # Should be integer
        }

        is_valid, errors = validate_tool_config(config, schema)

        assert is_valid is False
        assert any("integer" in e.lower() for e in errors)
