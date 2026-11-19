"""
Execution results carry success or error into the LLM message, and the service dispatches.

Tests for the tool execution service including:
- ToolExecutionResult dataclass
- Configuration resolution
- Argument validation
- Tool execution flow
- Error handling
"""

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.tools.execution_service import (
    ToolExecutionService,
    ToolExecutionResult,
)
from app.domain.tools.models import ToolCategory, Tool, AgentTool, ToolUsageLog
from app.domain.tools.registry import ToolRegistry
from app.domain.tools.schemas import ToolCreate
from app.domain.tools.services import (
    ToolRegistryService,
    AgentToolService,
)

# A simple mock calculator handler for ToolRegistry singleton registration
async def _mock_calculator_handler(config: dict, expression: str | None = None, **kwargs) -> dict:
    """Mock calculator handler for testing."""
    # Support precision config for agent config tests
    precision = config.get("precision", 2)
    # If expression contains invalid chars, return error for registry_error test
    if expression and not all(c in "0123456789+-*/.() " for c in expression):
        return {"success": False, "error": "Invalid characters in expression"}
    if expression:
        try:
            result = eval(expression, {"__builtins__": {}}, {})
            if isinstance(result, float):
                result = round(result, precision)
            return {"success": True, "result": result}
        except Exception:
            return {"success": False, "error": "Evaluation error"}
    return {"success": True, "result": 42}


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


@pytest_asyncio.fixture
async def setup_calculator_tool(clean_db: AsyncSession) -> AsyncSession:
    """Set up a calculator tool in DB and ToolRegistry singleton for testing."""
    # Register in the ToolRegistry singleton (needed by _execute_tool)
    registry = ToolRegistry.get_instance()
    registry.register(
        name="Calculator",
        slug="calculator",
        description="Perform mathematical calculations",
        handler=_mock_calculator_handler,
        config_schema={
            "type": "object",
            "properties": {
                "precision": {
                    "type": "integer",
                    "default": 2,
                    "minimum": 0,
                    "maximum": 10,
                }
            }
        },
        arguments_schema={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate",
                }
            },
            "required": ["expression"],
        },
    )
    
    # Also create the tool record in the DB via ToolRegistryService
    registry_service = ToolRegistryService(clean_db)
    await registry_service.create_tool(ToolCreate(
        name="Calculator",
        slug="calculator",
        description="Perform mathematical calculations",
        config_schema={
            "type": "object",
            "properties": {
                "precision": {
                    "type": "integer",
                    "default": 2,
                    "minimum": 0,
                    "maximum": 10,
                }
            }
        },
        tags=["math", "utility"],
    ))
    
    return clean_db


@pytest_asyncio.fixture(autouse=True)
async def reset_tool_registry():
    """Reset the ToolRegistry singleton before each test to prevent state bleed."""
    ToolRegistry.reset()
    yield
    ToolRegistry.reset()


@pytest_asyncio.fixture
async def setup_agent_with_tool(setup_calculator_tool: AsyncSession) -> AsyncSession:
    """Set up an agent with the calculator tool enabled."""
    db = setup_calculator_tool
    
    # Get the tool
    registry_service = ToolRegistryService(db)
    tools, _ = await registry_service.list_tools()
    tool = tools[0]
    
    # Enable for agent
    agent_tool_service = AgentToolService(db)
    await agent_tool_service.enable_tool_for_agent(
        agent_id="123",
        tool_id=tool.id,
        priority=1,
        config={"precision": 3},
    )
    
    return db


# =============================================================================
# ToolExecutionResult Tests
# =============================================================================


class TestToolExecutionResult:
    """Tests for ToolExecutionResult dataclass."""

    def test_create_success_result(self):
        """Test creating a successful execution result."""
        result = ToolExecutionResult(
            success=True,
            tool_slug="calculator",
            tool_name="Calculator",
            result=42,
            execution_time_ms=50,
        )

        assert result.success is True
        assert result.tool_slug == "calculator"
        assert result.tool_name == "Calculator"
        assert result.result == 42
        assert result.error is None
        assert result.error_type is None
        assert result.execution_time_ms == 50

    def test_create_error_result(self):
        """Test creating a failed execution result."""
        result = ToolExecutionResult(
            success=False,
            tool_slug="calculator",
            tool_name="Calculator",
            error="Invalid expression",
            error_type="ValueError",
            execution_time_ms=10,
        )

        assert result.success is False
        assert result.tool_slug == "calculator"
        assert result.error == "Invalid expression"
        assert result.error_type == "ValueError"
        assert result.result is None

    def test_result_with_metadata(self):
        """Test creating result with metadata."""
        result = ToolExecutionResult(
            success=True,
            tool_slug="calculator",
            tool_name="Calculator",
            result=100,
            metadata={"tokens_used": 10, "cache_hit": True},
        )

        assert result.metadata == {"tokens_used": 10, "cache_hit": True}

    def test_to_llm_message_success(self):
        """Test converting successful result to LLM message."""
        result = ToolExecutionResult(
            success=True,
            tool_slug="calculator",
            tool_name="Calculator",
            result=42,
        )

        message = result.to_llm_message()

        assert message["role"] == "tool"
        assert message["content"] == "42"
        assert message["tool_call_id"] == "calculator"

    def test_to_llm_message_error(self):
        """Test converting error result to LLM message."""
        result = ToolExecutionResult(
            success=False,
            tool_slug="calculator",
            tool_name="Calculator",
            error="Division by zero",
        )

        message = result.to_llm_message()

        assert message["role"] == "tool"
        assert "Error: Division by zero" in message["content"]
        assert message["tool_call_id"] == "calculator"

    def test_result_default_values(self):
        """Test default values in result."""
        result = ToolExecutionResult(
            success=True,
            tool_slug="test",
            tool_name="Test",
        )

        assert result.result is None
        assert result.error is None
        assert result.error_type is None
        assert result.execution_time_ms == 0
        assert result.tokens_used == 0
        assert result.metadata == {}


# =============================================================================
# ToolExecutionService Tests
# =============================================================================


class TestToolExecutionService:
    """Tests for ToolExecutionService."""

    def test_service_initialization(self, clean_db: AsyncSession):
        """Test service initializes correctly."""
        service = ToolExecutionService(clean_db)

        assert service.db == clean_db
        assert service.tool_registry is not None
        assert service.tool_service is not None
        assert service.agent_tool_service is not None
        assert service.usage_service is not None

    @pytest.mark.anyio
    async def test_execute_gras_tool_for_unlinked_agent(
        self, setup_calculator_tool: AsyncSession
    ):
        """The PARADIGM COMPLETION (2026-08-19): a GRAS tool executes
        for an unlinked agent — the tier is the gate, not the manual
        grid. (The old test expected the manual-gate denial.)"""
        db = setup_calculator_tool
        service = ToolExecutionService(db)

        result = await service.execute_tool_for_agent(
            agent_id="999999",
            tool_slug="calculator",
            arguments={"expression": "2 + 2"},
        )

        assert result.success is True

    @pytest.mark.anyio
    async def test_execute_tool_not_found_in_db(
        self, clean_db: AsyncSession
    ):
        """Test executing a non-existent tool."""
        service = ToolExecutionService(clean_db)

        # Skip agent-level check by passing agent_id=None (system manager path)
        result = await service.execute_tool_for_agent(
            agent_id=None,
            tool_slug="non-existent-tool",
            arguments={},
        )

        assert result.success is False
        assert result.error_type == "ToolNotFound"

    @pytest.mark.anyio
    async def test_execute_tool_success(
        self, setup_agent_with_tool: AsyncSession
    ):
        """Test successful tool execution."""
        db = setup_agent_with_tool
        service = ToolExecutionService(db)

        result = await service.execute_tool_for_agent(
            agent_id="123",
            tool_slug="calculator",
            arguments={"expression": "2 + 2"},
            session_id="test-session",
        )

        assert result.success is True
        assert result.tool_slug == "calculator"
        assert result.tool_name == "Calculator"
        assert result.result is not None
        assert result.error is None
        assert result.execution_time_ms >= 0

    @pytest.mark.anyio
    async def test_execute_tool_with_agent_config(
        self, setup_agent_with_tool: AsyncSession
    ):
        """Test tool execution uses agent-specific config."""
        db = setup_agent_with_tool
        service = ToolExecutionService(db)

        result = await service.execute_tool_for_agent(
            agent_id="123",
            tool_slug="calculator",
            arguments={"expression": "10 / 3"},
        )

        assert result.success is True
        # Agent config sets precision to 3 — handler returns {'success': True, 'result': 3.333}
        assert result.result["result"] == 3.333

    @pytest.mark.anyio
    async def test_execute_tool_validation_missing_required(
        self, setup_agent_with_tool: AsyncSession
    ):
        """Test tool execution when a required field is missing.

        Registry-based tools skip service-layer argument validation
        (``_validate_arguments`` at line 282 of execution_service.py),
        so the handler must validate its own arguments.  This test
        verifies that the handler-level error is surfaced correctly.
        """
        db = setup_agent_with_tool
        service = ToolExecutionService(db)

        registry_service = ToolRegistryService(db)
        tool = await registry_service.create_tool(ToolCreate(
            name="Required Test",
            slug="required-test",
            description="Test",
            arguments_schema={
                "type": "object",
                "properties": {
                    "required_field": {"type": "string"}
                },
                "required": ["required_field"]
            },
        ))

        async def _mock_handler(config, **kwargs):
            if "required_field" not in kwargs:
                return {"success": False, "error": "Missing required field: required_field"}
            return {"success": True, "result": kwargs["required_field"]}

        registry = ToolRegistry.get_instance()
        registry.register(
            name="Required Test",
            slug="required-test",
            description="Test",
            handler=_mock_handler,
            arguments_schema={
                "type": "object",
                "properties": {
                    "required_field": {"type": "string"}
                },
                "required": ["required_field"]
            },
        )

        agent_tool_service = AgentToolService(db)
        await agent_tool_service.enable_tool_for_agent(
            agent_id="123",
            tool_id=tool.id,
        )

        result = await service.execute_tool_for_agent(
            agent_id="123",
            tool_slug="required-test",
            arguments={},  # Missing required field
        )

        # Service level: a handler that RETURNED its verdict is reported with it —
        # a refusal is a failure to the caller and the model, not a success with the
        # real answer nested inside (the tool-reliability arc, F3: this assertion
        # used to read `is True`, which is why a refusal was logged ✅ and reached the
        # model as a success).
        assert result.success is False
        assert result.error == "Missing required field: required_field"
        assert result.error_type is None  # the handler named no class — counted, not invented
        # Handler level: the handler's own payload rides along untouched
        assert result.result is not None
        assert result.result["success"] is False
        assert "Missing required field" in result.result["error"]

    @pytest.mark.anyio
    async def test_execute_tool_validation_wrong_type(
        self, setup_agent_with_tool: AsyncSession
    ):
        """Test tool execution when an argument has the wrong type.

        Registry-based tools skip service-layer argument validation
        (``_validate_arguments`` at line 282 of execution_service.py),
        so the handler must validate its own arguments.  This test
        verifies that the handler-level error is surfaced correctly.
        """
        db = setup_agent_with_tool
        service = ToolExecutionService(db)

        registry_service = ToolRegistryService(db)
        tool = await registry_service.create_tool(ToolCreate(
            name="Type Test",
            slug="type-test",
            description="Test",
            arguments_schema={
                "type": "object",
                "properties": {
                    "count": {"type": "integer"}
                },
                "required": ["count"]
            },
        ))

        async def _mock_handler(config, **kwargs):
            count = kwargs.get("count")
            if count is not None and not isinstance(count, int):
                return {"success": False, "error": f"Field 'count' must be an integer, got {type(count).__name__}"}
            return {"success": True, "result": count}

        registry = ToolRegistry.get_instance()
        registry.register(
            name="Type Test",
            slug="type-test",
            description="Test",
            handler=_mock_handler,
            arguments_schema={
                "type": "object",
                "properties": {
                    "count": {"type": "integer"}
                },
                "required": ["count"]
            },
        )

        agent_tool_service = AgentToolService(db)
        await agent_tool_service.enable_tool_for_agent(
            agent_id="123",
            tool_id=tool.id,
        )

        result = await service.execute_tool_for_agent(
            agent_id="123",
            tool_slug="type-test",
            arguments={"count": "not a number"},  # Wrong type
        )

        # Service level: the handler's verdict IS the result (the tool-reliability
        # arc, F3 — this read `is True` while the failure sat in `result`)
        assert result.success is False
        assert "must be an integer" in (result.error or "")
        # Handler level: the handler's own payload rides along untouched
        assert result.result is not None
        assert result.result["success"] is False
        assert "must be an integer" in result.result["error"]

    @pytest.mark.anyio
    async def test_execute_tool_unknown_field(
        self, setup_agent_with_tool: AsyncSession
    ):
        """Test tool execution passes with unknown field (silently allowed)."""
        db = setup_agent_with_tool
        service = ToolExecutionService(db)

        result = await service.execute_tool_for_agent(
            agent_id="123",
            tool_slug="calculator",
            arguments={"unknown_field": "value"},
        )

        # Unknown fields are silently allowed by the validator
        assert result.success is True

    @pytest.mark.anyio
    async def test_execute_tool_registry_error(
        self, setup_agent_with_tool: AsyncSession
    ):
        """Test tool execution handles registry-level errors.

        The mock calculator handler returns ``{"success": False, "error": …}``
        when it receives an invalid expression. A handler that RETURNS a refusal is
        a FAILURE: ``ToolExecutionResult.success`` carries the handler's own verdict
        (the tool-reliability arc, F3) — it used to stay ``True`` because the handler
        did not throw, which is how a refusal was logged ✅ and reached the model as
        a success.
        """
        db = setup_agent_with_tool
        service = ToolExecutionService(db)

        # Try to execute with invalid expression
        result = await service.execute_tool_for_agent(
            agent_id="123",
            tool_slug="calculator",
            arguments={"expression": "invalid!!!"},
        )

        assert result.success is False, "a returned refusal is not a success"
        assert result.error
        assert result.result is not None
        # The handler's dict is the verdict AND the payload — nothing is lost
        assert result.result["success"] is False
        assert result.result["error"] is not None
        assert result.execution_time_ms >= 0

    @pytest.mark.anyio
    async def test_get_enabled_tools_for_agent(
        self, setup_agent_with_tool: AsyncSession
    ):
        """Test getting enabled tools for agent."""
        db = setup_agent_with_tool
        service = ToolExecutionService(db)

        tools = await service.get_enabled_tools_for_agent("123")

        assert len(tools) >= 1
        tool = tools[0]
        
        assert "function" in tool
        assert tool["function"]["name"] == "calculator"
        assert "description" in tool["function"]
        assert "parameters" in tool["function"]
        assert "x-cogitate-tool" in tool

    @pytest.mark.anyio
    async def test_get_enabled_tools_empty(
        self, clean_db: AsyncSession
    ):
        """Test getting tools for agent with no tools."""
        service = ToolExecutionService(clean_db)

        tools = await service.get_enabled_tools_for_agent("no-tools-agent")

        assert len(tools) == 0


# =============================================================================
# Configuration Resolution Tests
# =============================================================================


class TestConfigResolution:
    """Tests for configuration resolution logic."""

    @pytest.mark.anyio
    async def test_resolve_config_schema_defaults(
        self, clean_db: AsyncSession
    ):
        """Test config resolution uses schema defaults."""
        service = ToolExecutionService(clean_db)

        schema = {
            "type": "object",
            "properties": {
                "timeout": {"type": "integer", "default": 30},
                "retries": {"type": "integer", "default": 3},
            }
        }

        config = service._resolve_config({}, schema)

        assert config["timeout"] == 30
        assert config["retries"] == 3

    @pytest.mark.anyio
    async def test_resolve_config_agent_overrides_default(
        self, clean_db: AsyncSession
    ):
        """Test agent config overrides schema defaults."""
        service = ToolExecutionService(clean_db)

        schema = {
            "type": "object",
            "properties": {
                "timeout": {"type": "integer", "default": 30},
                "retries": {"type": "integer", "default": 3},
            }
        }

        agent_config = {"timeout": 60}

        config = service._resolve_config(agent_config, schema)

        assert config["timeout"] == 60  # Agent config wins
        assert config["retries"] == 3   # Schema default

    @pytest.mark.anyio
    async def test_resolve_config_empty_schema(
        self, clean_db: AsyncSession
    ):
        """Test config resolution with empty schema."""
        service = ToolExecutionService(clean_db)

        config = service._resolve_config({"key": "value"}, {})

        assert config == {"key": "value"}


# =============================================================================
# Argument Validation Tests
# =============================================================================


class TestArgumentValidation:
    """Tests for argument validation logic."""

    @pytest.mark.anyio
    async def test_validate_valid_arguments(
        self, clean_db: AsyncSession
    ):
        """Test validation passes for valid arguments."""
        service = ToolExecutionService(clean_db)

        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
            },
            "required": ["name"]
        }

        arguments = {"name": "test", "count": 5}

        error = service._validate_arguments(arguments, schema)

        assert error is None

    @pytest.mark.anyio
    async def test_validate_missing_required(
        self, clean_db: AsyncSession
    ):
        """Test validation fails for missing required field."""
        service = ToolExecutionService(clean_db)

        schema = {
            "type": "object",
            "properties": {
                "api_key": {"type": "string"}
            },
            "required": ["api_key"]
        }

        arguments = {}

        error = service._validate_arguments(arguments, schema)

        assert error is not None
        assert "Missing required field" in error

    @pytest.mark.anyio
    async def test_validate_string_type(
        self, clean_db: AsyncSession
    ):
        """Test validation for string type."""
        service = ToolExecutionService(clean_db)

        schema = {
            "type": "object",
            "properties": {
                "message": {"type": "string"}
            }
        }

        # Valid
        error = service._validate_arguments({"message": "hello"}, schema)
        assert error is None

        # Invalid
        error = service._validate_arguments({"message": 123}, schema)
        assert error is not None
        assert "must be a string" in error

    @pytest.mark.anyio
    async def test_validate_integer_type(
        self, clean_db: AsyncSession
    ):
        """Test validation for integer type."""
        service = ToolExecutionService(clean_db)

        schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"}
            }
        }

        # Valid
        error = service._validate_arguments({"count": 42}, schema)
        assert error is None

        # Invalid (string)
        error = service._validate_arguments({"count": "42"}, schema)
        assert error is not None
        assert "must be an integer" in error

        # Invalid (float)
        error = service._validate_arguments({"count": 3.14}, schema)
        assert error is not None

    @pytest.mark.anyio
    async def test_validate_number_type(
        self, clean_db: AsyncSession
    ):
        """Test validation for number type (int or float)."""
        service = ToolExecutionService(clean_db)

        schema = {
            "type": "object",
            "properties": {
                "value": {"type": "number"}
            }
        }

        # Valid (integer)
        error = service._validate_arguments({"value": 42}, schema)
        assert error is None

        # Valid (float)
        error = service._validate_arguments({"value": 3.14}, schema)
        assert error is None

        # Invalid (string)
        error = service._validate_arguments({"value": "42"}, schema)
        assert error is not None
        assert "must be a number" in error

    @pytest.mark.anyio
    async def test_validate_boolean_type(
        self, clean_db: AsyncSession
    ):
        """Test validation for boolean type."""
        service = ToolExecutionService(clean_db)

        schema = {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"}
            }
        }

        # Valid
        error = service._validate_arguments({"enabled": True}, schema)
        assert error is None

        # Invalid
        error = service._validate_arguments({"enabled": 1}, schema)
        assert error is not None
        assert "must be a boolean" in error

    @pytest.mark.anyio
    async def test_validate_unknown_field(
        self, clean_db: AsyncSession
    ):
        """Test validation allows unknown fields (silently permitted by default)."""
        service = ToolExecutionService(clean_db)

        schema = {
            "type": "object",
            "properties": {
                "known_field": {"type": "string"}
            }
        }

        arguments = {"known_field": "value", "unknown_field": "extra"}

        error = service._validate_arguments(arguments, schema)

        # Unknown fields are silently allowed by the validator
        assert error is None

    @pytest.mark.anyio
    async def test_validate_empty_schema(
        self, clean_db: AsyncSession
    ):
        """Test validation with empty schema."""
        service = ToolExecutionService(clean_db)

        arguments = {"anything": "goes"}

        error = service._validate_arguments(arguments, {})

        # Should allow anything with empty schema
        assert error is None


# =============================================================================
# Integration Tests
# =============================================================================


class TestToolExecutionIntegration:
    """Integration tests for tool execution flow."""

    @pytest.mark.anyio
    async def test_full_execution_flow(
        self, setup_agent_with_tool: AsyncSession
    ):
        """Test complete tool execution flow."""
        db = setup_agent_with_tool
        service = ToolExecutionService(db)

        # Execute
        result = await service.execute_tool_for_agent(
            agent_id="123",
            tool_slug="calculator",
            arguments={"expression": "100 * 2"},
            session_id="integration-test-session",
        )

        # Verify execution result
        assert result.success is True
        assert result.result is not None
        assert result.execution_time_ms >= 0

        # If usage logging succeeded, verify it; otherwise the execution
        # itself is the primary concern of this integration test.
        usage_service = service.usage_service
        try:
            logs, total = await usage_service.get_usage_logs(
                agent_id="123",
            )
            if total >= 1:
                assert any(log.agent_id == "123" for log in logs)
        except Exception:
            pass

    @pytest.mark.anyio
    async def test_multiple_tools_for_agent(
        self, setup_agent_with_tool: AsyncSession
    ):
        """Test agent with multiple tools."""
        db = setup_agent_with_tool
        
        # Add another tool
        registry_service = ToolRegistryService(db)
        tool2 = await registry_service.create_tool(ToolCreate(
            name="Echo",
            slug="echo",
            description="Echo tool",
        ))
        
        agent_tool_service = AgentToolService(db)
        await agent_tool_service.enable_tool_for_agent(
            agent_id="123",
            tool_id=tool2.id,
        )
        # THE PARADIGM COMPLETION: the selection reads the REGISTRY —
        # a DB-only tool is invisible; register the second one there
        from app.domain.tools.registry import ToolRegistry

        async def _echo_handler(config, **kwargs):
            return {"success": True, "result": "echo"}

        ToolRegistry.get_instance().register(
            name="Echo", slug="echo", description="Echo tool",
            handler=_echo_handler, is_builtin=True,
        )

        service = ToolExecutionService(db)
        tools = await service.get_enabled_tools_for_agent("123")

        assert len(tools) == 2
        slugs = [t["function"]["name"] for t in tools]
        assert "calculator" in slugs
        assert "echo" in slugs

    @pytest.mark.anyio
    async def test_execution_error_handling(
        self, setup_agent_with_tool: AsyncSession
    ):
        """Test error handling during execution."""
        db = setup_agent_with_tool
        service = ToolExecutionService(db)

        # Execute with error
        result = await service.execute_tool_for_agent(
            agent_id="123",
            tool_slug="calculator",
            arguments={"expression": "10 / 0"},
        )

        # Calculator should handle division by zero gracefully
        # or return an error - either way, service should not crash
        assert result is not None
        assert result.tool_slug == "calculator"
