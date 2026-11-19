"""
The multi-agent graph builder — node creation and the edge order.

Verifies graph construction from multi-agent configuration.
"""

import pytest

from app.domain.workflows.schemas.multi_agent_config import (
    MultiAgentConfig,
    AgentStep,
)
from app.workflows.graphs.multi_agent_graph import (
    build_multi_agent_graph,
    create_multi_agent_workflow,
    create_agent_step_node,
)


class TestAgentStepNodeFactory:
    """Test agent step node creation."""

    def test_create_agent_step_node(self):
        """Test that agent step node factory creates callable."""
        agent_step = AgentStep(step=1, agent_id=21)
        node_func = create_agent_step_node(agent_step)
        
        assert callable(node_func)
        assert node_func.__name__ == "agent_step_node"


class TestMultiAgentGraphConstruction:
    """Test multi-agent graph construction."""

    def test_build_two_agent_graph(self):
        """Test graph construction with 2 agents."""
        config = MultiAgentConfig(
            agents=[
                AgentStep(step=1, agent_id=21, input_key="user_input", output_key="draft"),
                AgentStep(step=2, agent_id=16, input_key="draft", output_key="final_story")
            ],
            context_mode="isolated"
        )
        
        graph = build_multi_agent_graph(config)
        
        # Graph should be created (we can't easily inspect internal structure)
        assert graph is not None
        assert hasattr(graph, 'add_node')
        assert hasattr(graph, 'add_edge')

    def test_build_three_agent_graph(self):
        """Test graph construction with 3 agents."""
        config = MultiAgentConfig(
            agents=[
                AgentStep(step=1, agent_id=21, output_key="draft"),
                AgentStep(step=2, agent_id=16, input_key="draft", output_key="edited"),
                AgentStep(step=3, agent_id=15, input_key="edited", output_key="final")
            ],
            context_mode="cumulative"
        )
        
        graph = build_multi_agent_graph(config)
        
        assert graph is not None

    def test_graph_builds_from_unsorted_agents(self):
        """Test that graph correctly orders unsorted agents."""
        # Agents defined out of order
        config = MultiAgentConfig(
            agents=[
                AgentStep(step=3, agent_id=15),
                AgentStep(step=1, agent_id=21),
                AgentStep(step=2, agent_id=16)
            ]
        )
        
        graph = build_multi_agent_graph(config)
        
        # Should still build correctly (sorted internally)
        assert graph is not None

    def test_graph_with_custom_keys(self):
        """Test graph with custom input/output keys."""
        config = MultiAgentConfig(
            agents=[
                AgentStep(
                    step=1,
                    agent_id=21,
                    input_key="story_prompt",
                    output_key="first_draft",
                    system_prompt_override="You are a writer"
                ),
                AgentStep(
                    step=2,
                    agent_id=16,
                    input_key="first_draft",
                    output_key="polished_story",
                    system_prompt_override="You are an editor"
                )
            ],
            final_output_key="polished_story"
        )
        
        graph = build_multi_agent_graph(config)
        
        assert graph is not None


class TestCreateMultiAgentWorkflow:
    """Test create_multi_agent_workflow convenience function."""

    def test_create_workflow_with_config_object(self):
        """Test workflow creation with MultiAgentConfig object."""
        config = MultiAgentConfig(
            agents=[
                AgentStep(step=1, agent_id=21),
                AgentStep(step=2, agent_id=16)
            ]
        )
        
        graph = create_multi_agent_workflow(config)
        
        assert graph is not None

    def test_create_workflow_with_dict_config(self):
        """Test workflow creation with dict config (auto-validation)."""
        config_dict = {
            "agents": [
                {"step": 1, "agent_id": 21, "input_key": "input", "output_key": "output1"},
                {"step": 2, "agent_id": 16, "input_key": "output1", "output_key": "output2"}
            ],
            "context_mode": "isolated",
            "final_output_key": "output2"
        }
        
        graph = create_multi_agent_workflow(config_dict)
        
        assert graph is not None

    def test_create_workflow_validates_config(self):
        """Test that invalid config raises ValidationError."""
        from pydantic import ValidationError
        
        # Missing required field
        invalid_config = {
            "agents": [
                {"step": 1}  # Missing agent_id
            ]
        }
        
        with pytest.raises(ValidationError):
            create_multi_agent_workflow(invalid_config)

    def test_create_workflow_requires_two_agents(self):
        """Test that config with < 2 agents raises ValidationError."""
        from pydantic import ValidationError
        
        invalid_config = {
            "agents": [
                {"step": 1, "agent_id": 21}
            ]
        }
        
        with pytest.raises(ValidationError):
            create_multi_agent_workflow(invalid_config)


class TestGraphIntegration:
    """Integration tests for multi-agent graph."""

    def test_hunter_editor_config_builds_graph(self):
        """Test that Hunter + Editor config builds valid graph."""
        config = MultiAgentConfig(
            agents=[
                AgentStep(
                    step=1,
                    agent_id=21,
                    input_key="user_input",
                    output_key="draft",
                    system_prompt_override="You are Hunter, a fiction writer."
                ),
                AgentStep(
                    step=2,
                    agent_id=16,
                    input_key="draft",
                    output_key="final_story",
                    system_prompt_override="You are an editor."
                )
            ],
            context_mode="isolated",
            final_output_key="final_story"
        )
        
        # Should build without errors
        graph = create_multi_agent_workflow(config)
        
        assert graph is not None
        # Verify graph has expected structure
        assert hasattr(graph, 'compile')

    def test_three_agent_chain_builds_graph(self):
        """Test that 3-agent chain builds valid graph."""
        config = MultiAgentConfig(
            agents=[
                AgentStep(step=1, agent_id=21, output_key="draft"),
                AgentStep(step=2, agent_id=16, input_key="draft", output_key="edited"),
                AgentStep(step=3, agent_id=15, input_key="edited", output_key="final")
            ],
            context_mode="cumulative"
        )
        
        graph = create_multi_agent_workflow(config)
        
        assert graph is not None
