"""
Parallel multi-agent execution — the config, the groups, and the validation.

The topology is a DAG: parallel groups are declared and validated, not inferred.
"""

import pytest

from app.domain.workflows.schemas.multi_agent_config import MultiAgentConfig, AgentStep
from app.workflows.graphs.multi_agent_graph import (
    build_multi_agent_graph,
    create_multi_agent_workflow,
)


class TestParallelExecutionSchema:
    """Test parallel execution schema extensions."""

    def test_multi_agent_config_with_execution_mode_sequential(self):
        """Test MultiAgentConfig with sequential execution mode (default)."""
        config = MultiAgentConfig(
            agents=[
                AgentStep(step=1, agent_id=21, input_key="input", output_key="out1"),
                AgentStep(step=2, agent_id=25, input_key="out1", output_key="out2"),
            ]
        )
        
        assert config.execution_mode == "sequential"  # Default
        assert config.parallel_groups == []

    def test_multi_agent_config_with_execution_mode_parallel(self):
        """Test MultiAgentConfig with parallel execution mode."""
        config = MultiAgentConfig(
            agents=[
                AgentStep(step=1, agent_id=21, input_key="input", output_key="research"),
                AgentStep(step=2, agent_id=25, input_key="input", output_key="analysis"),
                AgentStep(step=3, agent_id=16, input_key="combined", output_key="final"),
            ],
            execution_mode="parallel",
            parallel_groups=[[1, 2], [3]]
        )
        
        assert config.execution_mode == "parallel"
        assert config.parallel_groups == [[1, 2], [3]]

    def test_parallel_groups_validation_valid(self):
        """Test that valid parallel groups pass validation."""
        config = MultiAgentConfig(
            agents=[
                AgentStep(step=1, agent_id=21, input_key="input", output_key="out1"),
                AgentStep(step=2, agent_id=25, input_key="input", output_key="out2"),
                AgentStep(step=3, agent_id=16, input_key="combined", output_key="final"),
            ],
            execution_mode="parallel",
            parallel_groups=[[1, 2], [3]]
        )
        
        assert len(config.agents) == 3
        assert config.parallel_groups == [[1, 2], [3]]

    def test_parallel_groups_validation_invalid_step(self):
        """Test that parallel groups with invalid step numbers fail validation."""
        with pytest.raises(ValueError) as exc_info:
            MultiAgentConfig(
                agents=[
                    AgentStep(step=1, agent_id=21, input_key="input", output_key="out1"),
                    AgentStep(step=2, agent_id=25, input_key="input", output_key="out2"),
                ],
                execution_mode="parallel",
                parallel_groups=[[1, 3]]  # Step 3 doesn't exist
            )
        
        assert "invalid step 3" in str(exc_info.value)

    def test_parallel_groups_validation_empty_group(self):
        """Test that empty parallel groups fail validation."""
        with pytest.raises(ValueError) as exc_info:
            MultiAgentConfig(
                agents=[
                    AgentStep(step=1, agent_id=21, input_key="input", output_key="out1"),
                    AgentStep(step=2, agent_id=25, input_key="input", output_key="out2"),
                ],
                execution_mode="parallel",
                parallel_groups=[[]]  # Empty group
            )
        
        assert "empty" in str(exc_info.value)

    def test_parallel_config_with_tools_enabled(self):
        """Test parallel config with tools enabled for some agents."""
        config = MultiAgentConfig(
            agents=[
                AgentStep(
                    step=1,
                    agent_id=25,
                    input_key="input",
                    output_key="research",
                    tools=["tool-1"],
                    enable_tools=True
                ),
                AgentStep(
                    step=2,
                    agent_id=21,
                    input_key="input",
                    output_key="analysis",
                    tools=[],
                    enable_tools=False
                ),
                AgentStep(
                    step=3,
                    agent_id=16,
                    input_key="combined",
                    output_key="final",
                    tools=[],
                    enable_tools=False
                ),
            ],
            execution_mode="parallel",
            parallel_groups=[[1, 2], [3]]
        )
        
        assert config.agents[0].enable_tools is True
        assert len(config.agents[0].tools) == 1
        assert config.agents[1].enable_tools is False


class TestParallelGraphConstruction:
    """Test parallel graph construction."""

    def test_build_parallel_graph_basic(self):
        """Test building a basic parallel execution graph."""
        config = MultiAgentConfig(
            agents=[
                AgentStep(step=1, agent_id=21, input_key="input", output_key="out1"),
                AgentStep(step=2, agent_id=25, input_key="input", output_key="out2"),
            ],
            execution_mode="parallel",
            parallel_groups=[[1, 2]]
        )
        
        graph = build_multi_agent_graph(config)
        assert graph is not None

    def test_build_parallel_graph_multiple_groups(self):
        """Test building parallel graph with multiple groups."""
        config = MultiAgentConfig(
            agents=[
                AgentStep(step=1, agent_id=21, input_key="input", output_key="research"),
                AgentStep(step=2, agent_id=25, input_key="input", output_key="analysis"),
                AgentStep(step=3, agent_id=16, input_key="combined", output_key="final"),
            ],
            execution_mode="parallel",
            parallel_groups=[[1, 2], [3]]
        )
        
        graph = build_multi_agent_graph(config)
        assert graph is not None

    def test_build_parallel_graph_with_tool_enabled_agents(self):
        """Test building parallel graph with tool-enabled agents."""
        config = MultiAgentConfig(
            agents=[
                AgentStep(
                    step=1,
                    agent_id=25,
                    input_key="input",
                    output_key="research",
                    tools=["tool-1"],
                    enable_tools=True
                ),
                AgentStep(
                    step=2,
                    agent_id=21,
                    input_key="input",
                    output_key="analysis",
                    tools=[],
                    enable_tools=False
                ),
            ],
            execution_mode="parallel",
            parallel_groups=[[1, 2]]
        )
        
        graph = build_multi_agent_graph(config)
        assert graph is not None

    def test_build_mixed_sequential_parallel_graph(self):
        """Test building graph with mixed sequential and parallel execution."""
        config = MultiAgentConfig(
            agents=[
                AgentStep(step=1, agent_id=21, input_key="input", output_key="out1"),
                AgentStep(step=2, agent_id=25, input_key="out1", output_key="out2a"),
                AgentStep(step=3, agent_id=16, input_key="out1", output_key="out2b"),
                AgentStep(step=4, agent_id=19, input_key="combined", output_key="final"),
            ],
            execution_mode="parallel",
            parallel_groups=[[1], [2, 3], [4]]
        )
        
        graph = build_multi_agent_graph(config)
        assert graph is not None


class TestSequentialGraphConstruction:
    """Test sequential graph construction (baseline)."""

    def test_build_sequential_graph_default(self):
        """Test building sequential graph with default execution mode."""
        config = MultiAgentConfig(
            agents=[
                AgentStep(step=1, agent_id=21, input_key="input", output_key="out1"),
                AgentStep(step=2, agent_id=25, input_key="out1", output_key="out2"),
            ]
        )
        
        graph = build_multi_agent_graph(config)
        assert graph is not None

    def test_build_sequential_graph_explicit(self):
        """Test building sequential graph with explicit execution mode."""
        config = MultiAgentConfig(
            agents=[
                AgentStep(step=1, agent_id=21, input_key="input", output_key="out1"),
                AgentStep(step=2, agent_id=25, input_key="out1", output_key="out2"),
            ],
            execution_mode="sequential"
        )
        
        graph = build_multi_agent_graph(config)
        assert graph is not None

    def test_build_sequential_graph_three_agents(self):
        """Test building sequential graph with three agents."""
        config = MultiAgentConfig(
            agents=[
                AgentStep(step=1, agent_id=21, input_key="input", output_key="draft"),
                AgentStep(step=2, agent_id=25, input_key="draft", output_key="researched"),
                AgentStep(step=3, agent_id=16, input_key="researched", output_key="final"),
            ]
        )
        
        graph = build_multi_agent_graph(config)
        assert graph is not None


class TestCreateMultiAgentWorkflow:
    """Test create_multi_agent_workflow function with parallel support."""

    def test_create_workflow_parallel_config(self):
        """Test creating workflow with parallel configuration."""
        config = MultiAgentConfig(
            agents=[
                AgentStep(step=1, agent_id=21, input_key="input", output_key="out1"),
                AgentStep(step=2, agent_id=25, input_key="input", output_key="out2"),
            ],
            execution_mode="parallel",
            parallel_groups=[[1, 2]]
        )
        
        graph = create_multi_agent_workflow(config)
        assert graph is not None

    def test_create_workflow_dict_config_parallel(self):
        """Test creating workflow from dict config with parallel mode."""
        config_dict = {
            "agents": [
                {"step": 1, "agent_id": 21, "input_key": "input", "output_key": "out1"},
                {"step": 2, "agent_id": 25, "input_key": "input", "output_key": "out2"},
            ],
            "execution_mode": "parallel",
            "parallel_groups": [[1, 2]]
        }
        
        graph = create_multi_agent_workflow(config_dict)
        assert graph is not None


class TestIntegration:
    """Integration tests for parallel multi-agent workflows."""

    def test_parallel_config_validates_from_database_template(self):
        """Test that parallel config can be loaded from database template."""
        # This test verifies the schema is compatible with database storage
        config_dict = {
            "agents": [
                {"step": 1, "agent_id": 21, "input_key": "user_input", "output_key": "research"},
                {"step": 2, "agent_id": 25, "input_key": "user_input", "output_key": "analysis"},
                {"step": 3, "agent_id": 16, "input_key": "combined", "output_key": "final_story"},
            ],
            "context_mode": "cumulative",
            "execution_mode": "parallel",
            "parallel_groups": [[1, 2], [3]],
            "final_output_key": "final_story"
        }
        
        # Should validate without errors
        config = MultiAgentConfig.model_validate(config_dict)
        assert config.execution_mode == "parallel"
        assert config.parallel_groups == [[1, 2], [3]]
        
        # Should build graph successfully
        graph = build_multi_agent_graph(config)
        assert graph is not None

    def test_sequential_config_still_works(self):
        """Test that sequential configs still work (backward compatibility)."""
        config_dict = {
            "agents": [
                {"step": 1, "agent_id": 21, "input_key": "user_input", "output_key": "draft"},
                {"step": 2, "agent_id": 25, "input_key": "draft", "output_key": "researched"},
                {"step": 3, "agent_id": 16, "input_key": "researched", "output_key": "final"},
            ],
            "context_mode": "cumulative"
        }
        
        # Should validate without errors (defaults to sequential)
        config = MultiAgentConfig.model_validate(config_dict)
        assert config.execution_mode == "sequential"
        
        # Should build graph successfully
        graph = build_multi_agent_graph(config)
        assert graph is not None
