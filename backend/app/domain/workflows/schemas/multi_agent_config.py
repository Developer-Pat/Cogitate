"""
Multi-agent workflow configuration schemas.

Pydantic schemas for defining and validating multi-agent workflow chains.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Literal, List, Optional


class AgentStep(BaseModel):
    """
    Single agent step in a multi-agent workflow.

    Attributes:
        step: Step order in the chain (1, 2, 3...)
        agent_id: ID of the agent to invoke
        input_key: State key for input (default: "user_input")
        output_key: State key for output (default: "agent_output")
        system_prompt_override: Optional system prompt override for this step
        tools: List of tool IDs to enable for this agent step
        enable_tools: Whether to enable tools for this step (default: True)
    """
    step: int = Field(..., ge=1, description="Step order (1, 2, 3...)")
    agent_id: int = Field(..., description="Agent ID to invoke")
    input_key: str = Field(
        default="user_input",
        description="State key for input"
    )
    output_key: str = Field(
        default="agent_output",
        description="State key for output"
    )
    system_prompt_override: Optional[str] = Field(
        default=None,
        description="Optional system prompt override for this agent step"
    )
    # Tool support
    tools: List[str] = Field(
        default_factory=list,
        description="List of tool IDs (UUIDs) to enable for this agent step"
    )
    enable_tools: bool = Field(
        default=True,
        description="Whether to enable tools for this step"
    )


class MultiAgentConfig(BaseModel):
    """
    Multi-agent workflow configuration.

    Attributes:
        agents: Ordered list of agent steps (minimum 2)
        context_mode: How context is passed between agents
            - "cumulative": Each agent sees all previous outputs
            - "isolated": Each agent sees only immediate predecessor's output
        execution_mode: How agents are executed
            - "sequential": Agents execute one after another (default)
            - "parallel": Agents in parallel groups execute concurrently
        parallel_groups: List of step numbers to execute in parallel
            - Only used when execution_mode="parallel"
            - Each group is a list of step numbers that run concurrently
            - Groups execute sequentially
            - Example: [[1, 2], [3]] means steps 1&2 run in parallel, then step 3
        final_output_key: State key for final output (default: "final_output")
    """
    agents: List[AgentStep] = Field(
        ...,
        min_length=2,
        description="Ordered list of agent steps (minimum 2 agents)"
    )
    context_mode: Literal["cumulative", "isolated"] = Field(
        default="cumulative",
        description="cumulative=each agent sees all previous output, isolated=only immediate predecessor"
    )
    execution_mode: Literal["sequential", "parallel"] = Field(
        default="sequential",
        description="sequential=agents run one after another, parallel=agents in groups run concurrently"
    )
    parallel_groups: List[List[int]] = Field(
        default_factory=list,
        description="Groups of step numbers to execute in parallel (only used when execution_mode='parallel')"
    )
    final_output_key: str = Field(
        default="final_output",
        description="State key for final output"
    )

    @field_validator('parallel_groups')
    @classmethod
    def validate_parallel_groups(cls, v, info):
        """Validate that parallel groups reference valid step numbers."""
        if not v:
            return v
        
        # Get all step numbers from agents
        data = info.data if hasattr(info, 'data') else {}
        agents = data.get('agents', [])
        if not agents:
            return v  # Can't validate without agents
        
        valid_steps = {agent.step for agent in agents}
        
        # Check each group
        for i, group in enumerate(v):
            if not group:
                raise ValueError(f"Parallel group {i} is empty")
            for step in group:
                if step not in valid_steps:
                    raise ValueError(f"Parallel group {i} references invalid step {step}")
        
        return v
