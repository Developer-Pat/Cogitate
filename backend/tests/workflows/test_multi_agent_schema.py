"""
The multi-agent step schema — required fields and the step-number validation.

Validates AgentStep and MultiAgentConfig schema behavior.
"""

import pytest
from pydantic import ValidationError

from app.domain.workflows.schemas.multi_agent_config import (
    AgentStep,
    MultiAgentConfig,
)


class TestAgentStep:
    """Test AgentStep schema validation."""

    def test_agent_step_minimal(self):
        """Test AgentStep with minimal required fields."""
        step = AgentStep(step=1, agent_id=21)
        
        assert step.step == 1
        assert step.agent_id == 21
        assert step.input_key == "user_input"
        assert step.output_key == "agent_output"
        assert step.system_prompt_override is None

    def test_agent_step_with_custom_keys(self):
        """Test AgentStep with custom input/output keys."""
        step = AgentStep(
            step=2,
            agent_id=16,
            input_key="draft",
            output_key="final_story"
        )
        
        assert step.step == 2
        assert step.agent_id == 16
        assert step.input_key == "draft"
        assert step.output_key == "final_story"

    def test_agent_step_with_system_prompt(self):
        """Test AgentStep with system prompt override."""
        prompt = "You are Hunter, a fiction writer. Write the first draft."
        step = AgentStep(
            step=1,
            agent_id=21,
            system_prompt_override=prompt
        )
        
        assert step.system_prompt_override == prompt

    def test_agent_step_invalid_step_number(self):
        """Test that step number must be >= 1."""
        with pytest.raises(ValidationError) as exc_info:
            AgentStep(step=0, agent_id=21)
        
        assert "greater than or equal to 1" in str(exc_info.value)

    def test_agent_step_missing_agent_id(self):
        """Test that agent_id is required."""
        with pytest.raises(ValidationError) as exc_info:
            AgentStep(step=1)
        
        assert "agent_id" in str(exc_info.value)


class TestMultiAgentConfig:
    """Test MultiAgentConfig schema validation."""

    def test_multi_agent_config_minimal(self):
        """Test MultiAgentConfig with minimal required fields."""
        config = MultiAgentConfig(
            agents=[
                AgentStep(step=1, agent_id=21),
                AgentStep(step=2, agent_id=16)
            ]
        )
        
        assert len(config.agents) == 2
        assert config.agents[0].agent_id == 21
        assert config.agents[1].agent_id == 16
        assert config.context_mode == "cumulative"
        assert config.final_output_key == "final_output"

    def test_multi_agent_config_hunter_editor(self):
        """Test Hunter + Editor collaboration config."""
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
                    system_prompt_override="You are an editor. Refine the story."
                )
            ],
            context_mode="isolated"
        )
        
        assert len(config.agents) == 2
        assert config.context_mode == "isolated"
        assert config.agents[0].output_key == "draft"
        assert config.agents[1].input_key == "draft"
        assert config.agents[1].output_key == "final_story"

    def test_multi_agent_config_cumulative_context(self):
        """Test cumulative context mode."""
        config = MultiAgentConfig(
            agents=[
                AgentStep(step=1, agent_id=21, output_key="draft"),
                AgentStep(step=2, agent_id=16, input_key="draft"),
                AgentStep(step=3, agent_id=15, input_key="draft")
            ],
            context_mode="cumulative"
        )
        
        assert config.context_mode == "cumulative"
        assert len(config.agents) == 3

    def test_multi_agent_config_custom_final_output(self):
        """Test custom final output key."""
        config = MultiAgentConfig(
            agents=[
                AgentStep(step=1, agent_id=21),
                AgentStep(step=2, agent_id=16)
            ],
            final_output_key="story_result"
        )
        
        assert config.final_output_key == "story_result"

    def test_multi_agent_config_requires_minimum_two_agents(self):
        """Test that at least 2 agents are required."""
        with pytest.raises(ValidationError) as exc_info:
            MultiAgentConfig(
                agents=[AgentStep(step=1, agent_id=21)]
            )
        
        assert "at least 2" in str(exc_info.value).lower() or "min_length" in str(exc_info.value)

    def test_multi_agent_config_invalid_context_mode(self):
        """Test that context_mode must be valid literal."""
        with pytest.raises(ValidationError) as exc_info:
            MultiAgentConfig(
                agents=[
                    AgentStep(step=1, agent_id=21),
                    AgentStep(step=2, agent_id=16)
                ],
                context_mode="invalid_mode"
            )
        
        assert "cumulative" in str(exc_info.value)
        assert "isolated" in str(exc_info.value)

    def test_multi_agent_config_agent_steps_must_be_ordered(self):
        """Test that agent steps should be logically ordered."""
        # Schema doesn't enforce ordering, but we can validate it works
        config = MultiAgentConfig(
            agents=[
                AgentStep(step=2, agent_id=16),
                AgentStep(step=1, agent_id=21)
            ]
        )
        
        # Schema accepts this, but graph builder should handle ordering
        assert len(config.agents) == 2
        # Sort by step number for actual execution
        sorted_agents = sorted(config.agents, key=lambda a: a.step)
        assert sorted_agents[0].step == 1
        assert sorted_agents[1].step == 2


class TestIntegration:
    """Integration tests for multi-agent schemas."""

    def test_hunter_editor_template_validation(self):
        """Test that Hunter + Editor template config validates correctly."""
        template_config = {
            "agents": [
                {
                    "step": 1,
                    "agent_id": 21,
                    "input_key": "user_input",
                    "output_key": "draft",
                    "system_prompt_override": "You are Hunter, a fiction writer. Write the first draft of a story based on the user's prompt."
                },
                {
                    "step": 2,
                    "agent_id": 16,
                    "input_key": "draft",
                    "output_key": "final_story",
                    "system_prompt_override": "You are a skilled editor. Refine the provided story draft. Improve pacing, dialogue, and prose."
                }
            ],
            "context_mode": "isolated",
            "final_output_key": "final_story"
        }
        
        # Validate using schema
        config = MultiAgentConfig.model_validate(template_config)
        
        assert len(config.agents) == 2
        assert config.agents[0].agent_id == 21
        assert config.agents[1].agent_id == 16
        assert config.context_mode == "isolated"
        assert config.final_output_key == "final_story"
        assert config.agents[0].system_prompt_override is not None
        assert "Hunter" in config.agents[0].system_prompt_override
        assert "editor" in config.agents[1].system_prompt_override.lower()
