"""
Chat with tools on and off, multi-turn tool calls, and session persistence across turns.

Integration tests for chat service with tool execution including:
- Tool-enabled chat requests
- Tool call parsing and execution
- Multi-turn conversations with tools
- Error handling in tool execution
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

# THE EXTERNAL CLASS. Every test here drives ChatService with an
# agent whose fixture PINS the provider — `provider="ollama"`, a Provider row at
# `http://localhost:11434`. So the dependency is THAT daemon, not "some LLM":
# marking it generically would let llama.cpp running satisfy a probe while this
# still failed, which is exactly the wrong-probe failure we already paid for.
#
# Before this marker these five tests failed with
#   litellm.APIConnectionError: OllamaException - Cannot connect to host
# which reads as a defect in our code. It is an absent external service.
pytestmark = pytest.mark.external("ollama")

from app.domain.chat.services import ChatService
from app.domain.chat.schemas import ChatRequest
from app.domain.tools.execution_service import ToolExecutionService
from app.domain.tools.registry import init_default_registry
from app.domain.tools.models import ToolCategory, Tool, AgentTool, ToolUsageLog
from app.domain.tools.schemas import ToolCreate
from app.domain.tools.services import (
    ToolRegistryService,
    AgentToolService,
)
from app.infrastructure.database.models import (
    ChatSession,
    ChatMessage,
    Agent,
    Provider,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="session", autouse=True)
def init_tool_registry():
    """Initialize the tool registry with default tools before all tests."""
    init_default_registry()


@pytest_asyncio.fixture
async def clean_db(test_session: AsyncSession) -> AsyncSession:
    """Clear all relevant tables before each test."""
    from sqlalchemy import delete
    
    # Clear chat tables using async-compatible delete
    await test_session.execute(delete(ChatMessage))
    await test_session.execute(delete(ChatSession))
    await test_session.execute(delete(AgentTool))
    await test_session.execute(delete(ToolUsageLog))
    await test_session.execute(delete(Tool))
    await test_session.execute(delete(ToolCategory))
    await test_session.execute(delete(Agent))
    await test_session.execute(delete(Provider))
    await test_session.commit()
    return test_session


@pytest_asyncio.fixture
async def setup_provider(clean_db: AsyncSession) -> Provider:
    """Set up a test provider."""
    provider = Provider(
        name="Test Provider",
        provider_type="ollama",
        base_url="http://localhost:11434",
        is_active=True,
    )
    clean_db.add(provider)
    await clean_db.commit()
    await clean_db.refresh(provider)
    return provider


@pytest_asyncio.fixture
async def setup_agent(clean_db: AsyncSession, setup_provider: Provider) -> Agent:
    """Set up a test agent."""
    agent = Agent(
        name="Test Agent",
        provider="ollama",  # Uses string provider type, not provider_id
        model="llama3.2",
        system_prompt="You are a helpful assistant with access to tools.",
        is_active=True,
    )
    clean_db.add(agent)
    await clean_db.commit()
    await clean_db.refresh(agent)
    return agent


@pytest_asyncio.fixture
async def setup_calculator_tool(clean_db: AsyncSession) -> Tool:
    """Set up a calculator tool for testing."""
    registry_service = ToolRegistryService(clean_db)

    tool_create = ToolCreate(
        name="Calculator",
        slug="run-python",
        description="Perform mathematical calculations",
        config_schema={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Mathematical code to evaluate",
                },
                "precision": {
                    "type": "integer",
                    "default": 2,
                    "minimum": 0,
                    "maximum": 10,
                }
            },
            "required": ["code"],
        },
        tags=["math", "utility"],
    )

    tool = await registry_service.create_tool(tool_create)
    return tool


@pytest_asyncio.fixture
async def setup_agent_with_tool(
    clean_db: AsyncSession,
    setup_agent: Agent,
    setup_calculator_tool: Tool,
) -> AsyncSession:
    """Enable calculator tool for the test agent."""
    agent_tool_service = AgentToolService(clean_db)
    await agent_tool_service.enable_tool_for_agent(
        agent_id=setup_agent.id,  # Pass integer ID directly
        tool_id=setup_calculator_tool.id,
        priority=1,
        config={"precision": 2},
    )
    return clean_db


@pytest_asyncio.fixture
async def chat_service(clean_db: AsyncSession) -> ChatService:
    """Create chat service instance."""
    return ChatService(clean_db)


# =============================================================================
# ChatService with Tools Tests
# =============================================================================


class TestChatServiceToolIntegration:
    """Integration tests for ChatService with tool execution."""

    @pytest.mark.asyncio
    async def test_send_message_with_tools_enabled(
        self,
        chat_service: ChatService,
        setup_agent: Agent,
        setup_agent_with_tool,
    ):
        """Test sending a message with tools enabled."""
        request = ChatRequest(
            agent_id=str(setup_agent.id),
            message="What is 25 + 17?",
            session_id=None,
        )

        # Should not raise error even if tool execution is mocked
        response = await chat_service.send_message(request, enable_tools=True)

        assert response is not None
        assert response.session_id is not None
        assert response.message is not None

    @pytest.mark.asyncio
    async def test_send_message_without_tools(
        self,
        chat_service: ChatService,
        setup_agent: Agent,
    ):
        """Test sending a message without tools."""
        request = ChatRequest(
            agent_id=str(setup_agent.id),
            message="Hello!",
            session_id=None,
        )

        response = await chat_service.send_message(request, enable_tools=False)

        assert response is not None
        assert response.session_id is not None

    @pytest.mark.asyncio
    async def test_tool_execution_service_integration(
        self,
        clean_db: AsyncSession,
        setup_calculator_tool: Tool,
    ):
        """Test that ToolExecutionService can execute registered tools."""
        # First enable the tool for the test agent
        from app.domain.tools.services import AgentToolService
        agent_tool_service = AgentToolService(clean_db)
        
        # Create a dummy agent for tool enabling
        agent = Agent(
            name="Test Agent for Tool",
            provider="ollama",
            model="llama3.2",
            is_active=True,
        )
        clean_db.add(agent)
        await clean_db.commit()
        await clean_db.refresh(agent)
        
        # Enable tool for agent
        await agent_tool_service.enable_tool_for_agent(
            agent_id=agent.id,
            tool_id=setup_calculator_tool.id,
            priority=1,
        )
        
        # Now test execution
        execution_service = ToolExecutionService(clean_db)

        # Execute calculator tool
        result = await execution_service.execute_tool_for_agent(
            agent_id=agent.id,
            tool_slug="run-python",
            arguments={"code": "10 + 5", "precision": 2},
            session_id="test-session",
        )

        assert result.success is True
        assert result.tool_slug == "run-python"
        assert result.result is not None

    @pytest.mark.asyncio
    async def test_get_agent_with_tools(
        self,
        clean_db: AsyncSession,
        setup_agent: Agent,
        setup_agent_with_tool,
    ):
        """Test retrieving agent with associated tools."""
        # Use AgentService to get agent with tools
        from app.domain.agents.services import AgentService
        agent_service = AgentService(clean_db)
        agent_data = await agent_service.get_by_id(setup_agent.id)

        assert agent_data is not None
        assert agent_data.id == setup_agent.id
        assert agent_data.name == setup_agent.name


# =============================================================================
# Tool Execution Flow Tests
# =============================================================================


class TestToolExecutionFlow:
    """Tests for the complete tool execution flow."""

    @pytest.mark.asyncio
    async def test_tool_discovery_and_execution(
        self,
        clean_db: AsyncSession,
        setup_agent: Agent,
        setup_calculator_tool: Tool,
        setup_agent_with_tool,
    ):
        """Test discovering tools and executing them."""
        # Get agent with tools using AgentService
        from app.domain.agents.services import AgentService
        agent_service = AgentService(clean_db)
        agent_data = await agent_service.get_by_id(setup_agent.id)
        
        # Verify agent is retrieved
        assert agent_data is not None

        # Execute tool directly
        execution_service = ToolExecutionService(clean_db)
        result = await execution_service.execute_tool_for_agent(
            agent_id=setup_agent.id,
            tool_slug="run-python",
            arguments={"code": "100 / 4"},
            session_id="test-session",
        )

        assert result.success is True
        assert result.result is not None

    @pytest.mark.asyncio
    async def test_tool_with_invalid_arguments(
        self,
        clean_db: AsyncSession,
        setup_calculator_tool: Tool,
    ):
        """Test tool execution with invalid arguments."""
        # First enable the tool for a test agent
        from app.domain.tools.services import AgentToolService
        agent_tool_service = AgentToolService(clean_db)
        
        agent = Agent(
            name="Test Agent for Invalid Args",
            provider="ollama",
            model="llama3.2",
            is_active=True,
        )
        clean_db.add(agent)
        await clean_db.commit()
        await clean_db.refresh(agent)
        
        await agent_tool_service.enable_tool_for_agent(
            agent_id=agent.id,
            tool_id=setup_calculator_tool.id,
            priority=1,
        )
        
        execution_service = ToolExecutionService(clean_db)

        # Execute with missing required argument
        result = await execution_service.execute_tool_for_agent(
            agent_id=agent.id,
            tool_slug="run-python",
            arguments={},  # Missing 'code'
            session_id="test-session",
        )

        # Should handle gracefully
        assert result is not None
        assert result.success is True  # Tool execution itself succeeded
        assert result.result.get("success") is False  # Contains error result
        assert "No code provided" in result.result.get("error", "")

    @pytest.mark.asyncio
    async def test_multiple_tools_for_agent(
        self,
        clean_db: AsyncSession,
        setup_agent: Agent,
        setup_calculator_tool: Tool,
    ):
        """Test agent with multiple tools enabled."""
        # Create another tool
        registry_service = ToolRegistryService(clean_db)
        weather_tool = await registry_service.create_tool(ToolCreate(
            name="Weather",
            slug="weather",
            description="Get weather information",
            config_schema={
                "type": "object",
                "properties": {
                    "location": {"type": "string"},
                },
                "required": ["location"],
            },
            tags=["weather", "api"],
        ))

        # Enable both tools for agent
        agent_tool_service = AgentToolService(clean_db)
        await agent_tool_service.enable_tool_for_agent(
            agent_id=setup_agent.id,
            tool_id=setup_calculator_tool.id,
            priority=1,
        )
        await agent_tool_service.enable_tool_for_agent(
            agent_id=setup_agent.id,
            tool_id=weather_tool.id,
            priority=2,
        )

        # Verify tools can be retrieved — THE PARADIGM COMPLETION
        # (2026-08-19): the agent sees its assigned tools PLUS the
        # default-on GRAS surface (the registry's read tools); the
        # count is no longer exactly the assigned count.
        from app.domain.tools.execution_service import ToolExecutionService
        tool_service = ToolExecutionService(clean_db)
        enabled_tools = await tool_service.get_enabled_tools_for_agent(setup_agent.id)

        tool_slugs = [t["function"]["name"] for t in enabled_tools]
        assert "run-python" in tool_slugs  # the assigned GRAS tool
        assert "weather" in tool_slugs     # the assigned tool
        assert len(tool_slugs) >= 2          # the assigned surface + default-on


# =============================================================================
# Conversation Context with Tools Tests
# =============================================================================


class TestConversationContextWithTools:
    """Tests for maintaining conversation context when using tools."""

    @pytest.mark.asyncio
    async def test_multi_turn_conversation(
        self,
        chat_service: ChatService,
        setup_agent: Agent,
    ):
        """Test multi-turn conversation maintains context."""
        # First message
        request1 = ChatRequest(
            agent_id=str(setup_agent.id),
            message="Hello, I need help with math",
            session_id=None,
        )
        response1 = await chat_service.send_message(request1, enable_tools=False)

        # Second message should reference first
        request2 = ChatRequest(
            agent_id=str(setup_agent.id),
            session_id=response1.session_id,
            message="Can you help me add numbers?",
        )
        response2 = await chat_service.send_message(request2, enable_tools=False)

        assert response1.session_id == response2.session_id
        assert response1.message is not None
        assert response2.message is not None

    @pytest.mark.asyncio
    async def test_session_persistence_with_tools(
        self,
        chat_service: ChatService,
        setup_agent: Agent,
        setup_agent_with_tool,
    ):
        """Test that sessions persist messages correctly with tools."""
        request = ChatRequest(
            agent_id=str(setup_agent.id),
            message="Test message",
            session_id=None,
        )

        response = await chat_service.send_message(request, enable_tools=True)

        # Retrieve session and verify messages
        session = await chat_service.get_session(response.session_id)

        assert session is not None
        assert len(session.messages) >= 2  # At least user + assistant messages


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestToolErrorHandling:
    """Tests for error handling in tool execution."""

    @pytest.mark.asyncio
    async def test_tool_not_found(
        self,
        clean_db: AsyncSession,
    ):
        """Test handling of non-existent tool."""
        # Create a test agent
        agent = Agent(
            name="Test Agent for Not Found",
            provider="ollama",
            model="llama3.2",
            is_active=True,
        )
        clean_db.add(agent)
        await clean_db.commit()
        await clean_db.refresh(agent)
        
        execution_service = ToolExecutionService(clean_db)

        result = await execution_service.execute_tool_for_agent(
            agent_id=agent.id,
            tool_slug="nonexistent_tool",  # Non-existent
            arguments={},
            session_id="test-session",
        )

        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_agent_without_tools(
        self,
        chat_service: ChatService,
        setup_agent: Agent,
    ):
        """Test chat with agent that has no tools enabled."""
        # Use AgentService to get agent data (without tools since none enabled)
        from app.domain.agents.services import AgentService
        agent_service = AgentService(chat_service.db)
        agent_data = await agent_service.get_by_id(setup_agent.id)

        # Should return agent data
        assert agent_data is not None

        # Chat should still work (tools will be empty)
        request = ChatRequest(
            agent_id=str(setup_agent.id),
            message="Hello!",
            session_id=None,
        )
        response = await chat_service.send_message(request, enable_tools=True)

        assert response is not None


# =============================================================================
# Performance and Concurrency Tests
# =============================================================================


class TestToolExecutionPerformance:
    """Tests for tool execution performance."""

    @pytest.mark.asyncio
    async def test_tool_execution_time_tracking(
        self,
        clean_db: AsyncSession,
        setup_calculator_tool: Tool,
    ):
        """Test that execution time is tracked."""
        # First enable the tool for a test agent
        from app.domain.tools.services import AgentToolService
        agent_tool_service = AgentToolService(clean_db)
        
        agent = Agent(
            name="Test Agent for Timing",
            provider="ollama",
            model="llama3.2",
            is_active=True,
        )
        clean_db.add(agent)
        await clean_db.commit()
        await clean_db.refresh(agent)
        
        await agent_tool_service.enable_tool_for_agent(
            agent_id=agent.id,
            tool_id=setup_calculator_tool.id,
            priority=1,
        )
        
        execution_service = ToolExecutionService(clean_db)

        result = await execution_service.execute_tool_for_agent(
            agent_id=agent.id,
            tool_slug="run-python",
            arguments={"code": "1 + 1"},
            session_id="test-session",
        )

        assert result.execution_time_ms >= 0
        assert result.execution_time_ms < 10000  # Should complete in < 10s
        assert result.success is True
