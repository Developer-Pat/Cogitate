"""
Tool-enabled multi-agent steps — the enabled, disabled and default paths.
"""

import pytest

from app.domain.workflows.schemas.multi_agent_config import MultiAgentConfig, AgentStep
from app.workflows.graphs.multi_agent_graph import _load_tools_for_step, create_agent_step_node
from app.core.database import AsyncSessionLocal
from tests import conftest as cf


@pytest.fixture(autouse=True)
def _tool_registry_rows():
    """The registry ids these tests name come from the fixture rows, re-loaded per test.

    `auto_clean_tables` truncates every ORM table after each test and `tools` is
    not one of the seeded exceptions, so in every worker that has already run a
    test these ids resolve to nothing — three reds that moved with xdist's
    distribution and looked like flakiness. The loader is missing-rows-only, so a
    copied database's own registry is left alone.
    """
    cf.reload_reference_rows()


class TestAgentStepWithTools:
    """Test AgentStep schema with tool configuration."""

    def test_agent_step_with_tools_enabled(self):
        """Test AgentStep with tools and enable_tools=True."""
        step = AgentStep(
            step=1,
            agent_id=25,
            tools=["tool-1", "tool-2"],
            enable_tools=True
        )
        assert step.tools == ["tool-1", "tool-2"]
        assert step.enable_tools is True

    def test_agent_step_with_tools_disabled(self):
        """Test AgentStep with tools but enable_tools=False."""
        step = AgentStep(
            step=1,
            agent_id=25,
            tools=["tool-1", "tool-2"],
            enable_tools=False
        )
        assert step.tools == ["tool-1", "tool-2"]
        assert step.enable_tools is False

    def test_agent_step_no_tools_default(self):
        """Test AgentStep default values for tools."""
        step = AgentStep(
            step=1,
            agent_id=25
        )
        assert step.tools == []
        assert step.enable_tools is True

    def test_agent_step_with_uuid_tool_ids(self):
        """Test AgentStep with UUID-format tool IDs."""
        step = AgentStep(
            step=1,
            agent_id=25,
            tools=[
                "81ff193c8f3342cda2360360eb6fd3f9",
                "35adf4ad469f43a5b631368615ef762a"
            ],
            enable_tools=True
        )
        assert len(step.tools) == 2
        assert step.tools[0] == "81ff193c8f3342cda2360360eb6fd3f9"

    def test_multi_agent_config_with_tool_enhanced_step(self):
        """Test MultiAgentConfig with tool-enhanced agent step."""
        config = MultiAgentConfig(
            agents=[
                AgentStep(step=1, agent_id=21, tools=[], enable_tools=False),
                AgentStep(
                    step=2,
                    agent_id=25,
                    tools=["81ff193c8f3342cda2360360eb6fd3f9"],
                    enable_tools=True
                ),
                AgentStep(step=3, agent_id=16, tools=[], enable_tools=False)
            ]
        )
        assert len(config.agents) == 3
        assert config.agents[1].enable_tools is True
        assert len(config.agents[1].tools) == 1


class TestToolLoading:
    """Test tool loading for multi-agent workflows."""

    @pytest.mark.asyncio
    async def test_load_tools_for_step(self):
        """Test loading tools by ID list."""
        tool_ids = [
            "0fcbe3731a414e6e95723930cbecb618",  # web-search (duckduckgo)
            "33d7ddbbe30e460d9bb01d0602238063",  # compute (run-python)
        ]

        async with AsyncSessionLocal() as db:
            tools = await _load_tools_for_step(tool_ids, db)

        assert len(tools) == 2
        assert tools[0]["type"] == "function"
        assert tools[0]["function"]["name"] == "duckduckgo"
        assert tools[1]["function"]["name"] == "run-python"

    @pytest.mark.asyncio
    async def test_load_tools_empty_list(self):
        """Test loading tools with empty ID list."""
        async with AsyncSessionLocal() as db:
            tools = await _load_tools_for_step([], db)

        assert len(tools) == 0

    @pytest.mark.asyncio
    async def test_load_tools_invalid_id(self):
        """Test loading tools with invalid ID."""
        tool_ids = ["invalid-tool-id"]

        async with AsyncSessionLocal() as db:
            tools = await _load_tools_for_step(tool_ids, db)

        assert len(tools) == 0

    @pytest.mark.asyncio
    async def test_load_tools_mixed_valid_invalid(self):
        """Test loading tools with mix of valid and invalid IDs."""
        tool_ids = [
            "0fcbe3731a414e6e95723930cbecb618",  # valid: web-search (duckduckgo)
            "invalid-tool-id",  # invalid
        ]

        async with AsyncSessionLocal() as db:
            tools = await _load_tools_for_step(tool_ids, db)

        assert len(tools) == 1
        assert tools[0]["function"]["name"] == "duckduckgo"

    @pytest.mark.asyncio
    async def test_load_tools_schema_format(self):
        """Test that loaded tools have correct schema format for LLM binding."""
        tool_ids = ["62267a65ab924f43896b89b53b183cbc"]  # datetime

        async with AsyncSessionLocal() as db:
            tools = await _load_tools_for_step(tool_ids, db)

        assert len(tools) == 1
        tool = tools[0]

        # Verify schema structure for LangChain tool binding
        assert "type" in tool
        assert tool["type"] == "function"
        assert "function" in tool
        assert "name" in tool["function"]
        assert "description" in tool["function"]
        assert "parameters" in tool["function"]


class TestToolEnhancedTemplate:
    """Test tool-enhanced multi-agent workflow template."""

    def test_research_enhanced_writer_template_exists(self):
        """Test that research-enhanced-writer template exists in database."""
        import sqlite3
        from app.core.config import Paths, get_settings

        DB_PATH = str(Paths.from_settings(get_settings()).shared_db)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            'SELECT id, name, config FROM workflow_templates WHERE id = ?',
            ('research-enhanced-writer',)
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == "research-enhanced-writer"
        assert "Research-Enhanced Writing" in result[1]

    def test_research_enhanced_writer_has_tool_enhanced_step(self):
        """Test that template has tool-enhanced agent step."""
        import sqlite3
        import json
        from app.core.config import Paths, get_settings

        DB_PATH = str(Paths.from_settings(get_settings()).shared_db)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            'SELECT config FROM workflow_templates WHERE id = ?',
            ('research-enhanced-writer',)
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        config = json.loads(result[0])

        # Should have 3 agents
        assert len(config["agents"]) == 3

        # Step 2 should have tools enabled
        step2 = config["agents"][1]
        assert step2["step"] == 2
        assert step2["agent_id"] == 25  # Tooled Up
        assert step2["enable_tools"] is True
        assert len(step2["tools"]) > 0

    def test_research_enhanced_writer_validates(self):
        """Test that research-enhanced-writer template validates correctly."""
        import sqlite3
        import json
        from app.core.config import Paths, get_settings

        DB_PATH = str(Paths.from_settings(get_settings()).shared_db)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            'SELECT config FROM workflow_templates WHERE id = ?',
            ('research-enhanced-writer',)
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        config_dict = json.loads(result[0])

        # Should validate without errors
        config = MultiAgentConfig.model_validate(config_dict)
        assert len(config.agents) == 3
        assert config.agents[1].enable_tools is True


class TestCreateAgentStepNodeWithTools:
    """Test agent step node creation with tool configuration."""

    def test_create_node_with_tools_enabled(self):
        """Test creating node with tools enabled."""
        step = AgentStep(
            step=1,
            agent_id=25,
            tools=["tool-1"],
            enable_tools=True
        )

        node_func = create_agent_step_node(step)
        assert callable(node_func)

    def test_create_node_with_tools_disabled(self):
        """Test creating node with tools disabled."""
        step = AgentStep(
            step=1,
            agent_id=25,
            tools=["tool-1"],
            enable_tools=False
        )

        node_func = create_agent_step_node(step)
        assert callable(node_func)

    def test_create_node_no_tools(self):
        """Test creating node with no tools configured."""
        step = AgentStep(
            step=1,
            agent_id=25,
            tools=[],
            enable_tools=False
        )

        node_func = create_agent_step_node(step)
        assert callable(node_func)


class TestIntegration:
    """Integration tests for tool-enhanced multi-agent workflows."""

    def test_full_tool_enhanced_config(self):
        """Test complete tool-enhanced multi-agent configuration."""
        config = MultiAgentConfig(
            agents=[
                AgentStep(
                    step=1,
                    agent_id=21,
                    input_key="user_input",
                    output_key="draft",
                    tools=[],
                    enable_tools=False
                ),
                AgentStep(
                    step=2,
                    agent_id=25,
                    input_key="draft",
                    output_key="researched",
                    tools=[
                        "0fcbe3731a414e6e95723930cbecb618",  # web-search (duckduckgo)
                        "33d7ddbbe30e460d9bb01d0602238063",  # compute (run-python)
                        "62267a65ab924f43896b89b53b183cbc"   # datetime
                    ],
                    enable_tools=True,
                    system_prompt_override="You are a research assistant. Use your tools."
                ),
                AgentStep(
                    step=3,
                    agent_id=16,
                    input_key="researched",
                    output_key="final",
                    tools=[],
                    enable_tools=False
                )
            ],
            context_mode="cumulative",
            final_output_key="final"
        )

        # Validate entire config
        assert len(config.agents) == 3
        assert config.context_mode == "cumulative"

        # Verify tool configuration
        assert config.agents[0].enable_tools is False
        assert config.agents[1].enable_tools is True
        assert len(config.agents[1].tools) == 3
        assert config.agents[2].enable_tools is False
