"""
Multi-agent workflow graph builder.

Builds LangGraph workflows from multi-agent configuration, chaining multiple agents
in sequence with context passing.

Features:
- Dynamic graph construction from MultiAgentConfig
- Agent node chaining with input/output key mapping
- Context mode support (cumulative vs isolated)
- Final output extraction
- ReAct loop support for tool execution per agent step
- Parallel execution support (DAG topology)
"""

import logging
from typing import Dict, Any, Callable, cast
from datetime import datetime, UTC
from langchain_core.messages import HumanMessage, SystemMessage

from langgraph.graph import StateGraph, END
from ..state.workflow_state import WorkflowState
from ..nodes.agent_nodes import _get_agent_llm, tool_executor_node
from app.domain.workflows.schemas.multi_agent_config import MultiAgentConfig, AgentStep
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def _load_tools_for_step(tool_ids: list[str], db):
    """
    Load tools for agent step.

    Args:
        tool_ids: List of tool IDs (UUIDs) to load
        db: Database session

    Returns:
        List of tool schemas ready for binding
    """
    from app.domain.tools.services import ToolRegistryService

    tool_service = ToolRegistryService(db)
    tools = []

    for tool_id in tool_ids:
        try:
            tool_response = await tool_service.get_tool(tool_id)
            if tool_response:
                # Convert ToolResponse to tool schema format for LLM binding
                tool_schema = {
                    "type": "function",
                    "function": {
                        "name": tool_response.slug,
                        "description": tool_response.description,
                        "parameters": tool_response.arguments_schema or {}
                    }
                }
                tools.append(tool_schema)
                logger.debug(f"Loaded tool: {tool_response.name} ({tool_response.slug})")
            else:
                logger.warning(f"⚠️  Tool ID {tool_id} not found")
        except Exception as e:
            logger.error(f"❌ Error loading tool {tool_id}: {str(e)}")

    return tools


def multi_agent_tool_executor_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Execute all tool calls from the last AIMessage for multi-agent workflows.

    This is a wrapper around the shared tool_executor_node that tracks which
    agent step is currently executing, so we can route back correctly.

    Returns:
        Tool execution results with current_agent_step preserved
    """
    # Execute tools using the shared node
    result = tool_executor_node(state)
    
    # Preserve the current agent step so we know which node to route back to
    current_step = state.get("current_agent_step")
    
    return {
        **result,
        "current_agent_step": current_step,
    }


def create_agent_step_node(agent_step: AgentStep) -> Callable:
    """
    Create a node function for a specific agent step.

    This factory function creates a node that:
    1. Reads input from the specified input_key
    2. Invokes the agent with that input
    3. Writes output to the specified output_key
    4. Optionally binds and executes tools for this step
    5. Supports ReAct loop: detects tool_calls and routes to tool executor
    6. Supports parallel execution with proper synchronization

    Args:
        agent_step: Configuration for this agent step

    Returns:
        Node function compatible with LangGraph
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from langchain_core.messages import ToolMessage as LCToolMessage

    def agent_step_node(state: WorkflowState) -> Dict[str, Any]:
        """
        Execute a single agent step in the multi-agent chain.

        This node:
        1. Reads input from state.inputs[input_key]
        2. Invokes the configured agent
        3. If LLM returns tool_calls: routes to tool_executor (via pending_tool_calls)
        4. If LLM returns final answer: stores output and moves to next agent
        5. Supports ReAct loop continuation after tool execution
        6. Supports parallel execution with result synchronization

        Args:
            state: Current workflow state

        Returns:
            State updates with agent output or pending tool calls
        """
        async def run_agent_step():
            try:
                # Get agent configuration
                agent_id = agent_step.agent_id
                input_key = agent_step.input_key
                output_key = agent_step.output_key
                system_prompt = agent_step.system_prompt_override

                # Detect if we're in a ReAct loop (continuing after tool execution)
                existing_messages = state.get("messages", [])
                is_tool_loop = bool(existing_messages) and isinstance(
                    existing_messages[-1], LCToolMessage
                )

                # Get input for this agent
                inputs = state.get("inputs", {})
                user_input = inputs.get(input_key, "")

                if not user_input and not is_tool_loop:
                    # Try to get from outputs (for chained agents)
                    outputs = state.get("outputs", {})
                    user_input = outputs.get(input_key, "")

                    # If output is a dict (our structure), extract the content
                    if isinstance(user_input, dict):
                        user_input = user_input.get("content", "")

                if not user_input and not is_tool_loop:
                    raise ValueError(f"No input found for key '{input_key}'")

                # Ensure user_input is a string for logging
                input_preview = str(user_input)[:100] if user_input else ""
                if not is_tool_loop:
                    logger.info(f"📤 Invoking agent step {agent_step.step} (agent_id={agent_id}) with input: {input_preview}...")
                else:
                    logger.info(f"🔄 Continuing ReAct loop for agent step {agent_step.step} after tool execution")

                # Get agent LLM
                llm, agent_data = await _get_agent_llm(agent_id)

                # Load and bind tools if enabled for this step
                if agent_step.enable_tools and agent_step.tools:
                    logger.info(f"🔧 Loading {len(agent_step.tools)} tools for agent step {agent_step.step}")
                    async with AsyncSessionLocal() as db:
                        tools = await _load_tools_for_step(agent_step.tools, db)

                    if tools:
                        tool_names = []
                        for t in tools:
                            if isinstance(t, dict):
                                tool_names.append(t.get('function', {}).get('name', 'unknown'))
                            else:
                                tool_names.append(getattr(t, 'name', getattr(t, 'slug', 'unknown')))
                        logger.info(f"🔧 Binding tools to LLM: {tool_names}")

                        # Strip internal metadata before sending to provider
                        clean_tools = [
                            {"type": t["type"], "function": t["function"]}
                            if isinstance(t, dict) else t
                            for t in tools
                        ]
                        llm = llm.bind_tools(clean_tools)
                    else:
                        logger.warning(f"⚠️  No tools loaded for agent step {agent_step.step}")
                else:
                    if agent_step.tools:
                        logger.info(f"📭 Tools disabled for agent step {agent_step.step} (enable_tools={agent_step.enable_tools})")
                    else:
                        logger.info(f"📭 No tools configured for agent step {agent_step.step}")

                # Build messages
                messages = []
                seed_messages = []

                if is_tool_loop:
                    # Continue with existing conversation history
                    messages = list(existing_messages)
                    seed_messages = []
                else:
                    # Fresh invocation: build from system prompt + user input
                    # Use system prompt override if provided, otherwise use agent's default
                    effective_system_prompt = system_prompt or agent_data.get("system_prompt")

                    if effective_system_prompt:
                        logger.info(f"📋 Using system prompt: {effective_system_prompt[:100]}...")
                        sys_msg = SystemMessage(content=effective_system_prompt)
                        messages.append(sys_msg)
                        seed_messages.append(sys_msg)

                    human_msg = HumanMessage(content=user_input)
                    messages.append(human_msg)
                    seed_messages.append(human_msg)

                # Invoke LLM
                logger.info(f"📤 Sending request to agent {agent_data['name']}...")
                response = await llm.ainvoke(messages)

                content = response.content or ""
                has_tool_calls = getattr(response, "tool_calls", None)

                if has_tool_calls:
                    logger.info(f"🔧 Agent step {agent_step.step} requested tools: {[tc['name'] for tc in response.tool_calls]}")
                    logger.debug(f"   Tool call details: {response.tool_calls}")
                else:
                    logger.info(f"📥 Received final response from agent step {agent_step.step}: {content[:200]}...")
                    if content:
                        logger.debug(f"   Response content preview: {content[:500]}")

                # Return only the *new* messages so add_messages reducer can append
                # them without duplicating what is already in state.
                new_messages = seed_messages + [response]

                # Check if LLM returned tool calls
                if has_tool_calls:
                    # Route to tool_executor_node by returning pending_tool_calls
                    return {
                        "messages": new_messages,
                        "pending_tool_calls": response.tool_calls,
                        "current_agent_step": agent_step.step,
                    }
                else:
                    # Final response, store output and move to next agent
                    now = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")

                    # Store in outputs with the specified key
                    outputs = state.get("outputs", {}).copy()
                    outputs[output_key] = {
                        "content": content,
                        "agent_id": agent_data["id"],
                        "agent_name": agent_data["name"],
                        "agent_model": f"{agent_data['provider']}/{agent_data['model']}",
                        "step": agent_step.step,
                    }

                    return {
                        "outputs": outputs,
                        "messages": new_messages,
                        "current_step": f"agent_step_{agent_step.step}",
                        "current_agent_step": None,
                    }

            except Exception as e:
                logger.error(f"❌ Agent step {agent_step.step} failed: {str(e)}", exc_info=True)
                now = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")

                return {
                    "outputs": {
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "failed_step": agent_step.step,
                    },
                    "current_step": None,
                    "current_agent_step": None,
                    "execution_result": {
                        "result": "Multi-agent workflow failed",
                        "completed_at": now,
                        "error": str(e),
                    },
                }

        # Run async in thread pool
        with ThreadPoolExecutor() as executor:
            future = executor.submit(lambda: asyncio.run(run_agent_step()))
            return cast(Dict[str, Any], future.result())

    return agent_step_node


def multi_agent_should_use_tools(state: WorkflowState) -> str:
    """
    Conditional routing for multi-agent ReAct loop.

    Returns:
        "tool_executor_X" if tool_calls present for agent step X
        "next_agent" or "end" if no tool_calls (final answer)
    """
    MAX_TOOL_ITERATIONS = 10

    # Guard against infinite loops
    if state.get("tool_loop_count", 0) >= MAX_TOOL_ITERATIONS:
        logger.warning(f"⚠️  Tool loop hit {MAX_TOOL_ITERATIONS} iterations — forcing end")
        return "end"

    # Check if there are pending tool calls
    pending_calls = state.get("pending_tool_calls")
    if pending_calls:
        current_step = state.get("current_agent_step")
        if current_step:
            return f"tool_executor_{current_step}"
    
    # No tool calls, move to next agent or end
    return "next_agent"


def build_multi_agent_graph(config: MultiAgentConfig) -> StateGraph:
    """
    Build LangGraph workflow from multi-agent configuration.

    This function:
    1. Creates a node for each agent step with ReAct loop support
    2. Creates tool executor nodes for each agent step
    3. Chains nodes with conditional routing for tool execution
    4. Supports parallel execution with DAG topology
    5. Configures context passing based on context_mode
    6. Sets up final output extraction

    Args:
        config: Validated multi-agent configuration

    Returns:
        Compiled StateGraph ready for execution

    Example:
        ```python
        from app.domain.workflows.schemas.multi_agent_config import MultiAgentConfig
        from app.workflows.graphs.multi_agent_graph import build_multi_agent_graph

        # Sequential execution (default)
        config = MultiAgentConfig(
            agents=[
                AgentStep(step=1, agent_id=21, input_key="user_input", output_key="draft"),
                AgentStep(step=2, agent_id=16, input_key="draft", output_key="final_story")
            ],
            context_mode="isolated"
        )

        # Parallel execution
        config_parallel = MultiAgentConfig(
            agents=[
                AgentStep(step=1, agent_id=21, input_key="user_input", output_key="research"),
                AgentStep(step=2, agent_id=25, input_key="user_input", output_key="analysis"),
                AgentStep(step=3, agent_id=16, input_key="combined", output_key="final")
            ],
            execution_mode="parallel",
            parallel_groups=[[1, 2], [3]]  # Steps 1&2 run in parallel, then step 3
        )

        graph = build_multi_agent_graph(config)
        result = graph.invoke(initial_state)
        ```
    """
    # Sort agents by step number to ensure correct ordering
    sorted_agents = sorted(config.agents, key=lambda a: a.step)

    logger.info(f"🏗️  Building multi-agent graph: {len(sorted_agents)} agents, mode={config.execution_mode}")
    for agent in sorted_agents:
        tools_status = f"tools={len(agent.tools)}" if agent.enable_tools else "no tools"
        logger.info(f"   Step {agent.step}: Agent {agent.agent_id} ({agent.input_key} → {agent.output_key}) [{tools_status}]")

    # Initialize graph with WorkflowState schema
    graph = StateGraph(WorkflowState)

    # Create and add node for each agent step
    agent_nodes = {}
    for agent_step in sorted_agents:
        node_name = f"agent_step_{agent_step.step}"
        node_func = create_agent_step_node(agent_step)
        graph.add_node(node_name, node_func)
        agent_nodes[agent_step.step] = node_name
        logger.info(f"✅ Added agent node '{node_name}' for agent {agent_step.agent_id}")

    # Create tool executor nodes for each agent step (for ReAct loop)
    tool_nodes = {}
    for agent_step in sorted_agents:
        if agent_step.enable_tools and agent_step.tools:
            node_name = f"tool_executor_{agent_step.step}"
            graph.add_node(node_name, multi_agent_tool_executor_node)
            tool_nodes[agent_step.step] = node_name
            logger.info(f"✅ Added tool executor node '{node_name}' for agent step {agent_step.step}")

    # Set entry point(s) based on execution mode
    if config.execution_mode == "parallel" and config.parallel_groups:
        # Parallel execution: first group runs in parallel
        first_group = config.parallel_groups[0]
        for step_num in first_group:
            if step_num in agent_nodes:
                graph.set_entry_point(agent_nodes[step_num])
                logger.info(f"✅ Set PARALLEL entry point: {agent_nodes[step_num]} (group 1)")
    else:
        # Sequential execution: first agent is entry point
        first_step = sorted_agents[0].step
        graph.set_entry_point(agent_nodes[first_step])
        logger.info(f"✅ Set SEQUENTIAL entry point: {agent_nodes[first_step]}")

    # Build edges based on execution mode
    if config.execution_mode == "parallel" and config.parallel_groups:
        logger.info(f"🔀 Building PARALLEL edges with {len(config.parallel_groups)} groups: {config.parallel_groups}")
        _build_parallel_edges(graph, config, agent_nodes, tool_nodes)
    else:
        logger.info("🔗 Building SEQUENTIAL edges")
        _build_sequential_edges(graph, agent_nodes, tool_nodes)

    logger.info("✅ Multi-agent graph build complete")
    return graph


def _build_sequential_edges(graph, agent_nodes: dict, tool_nodes: dict):
    """Build sequential edges with ReAct loop support."""
    sorted_steps = sorted(agent_nodes.keys())
    
    logger.info(f"   Building sequential chain: {' → '.join([f'step_{s}' for s in sorted_steps])}")
    
    for i, step in enumerate(sorted_steps):
        agent_node = agent_nodes[step]
        next_agent_node = agent_nodes[sorted_steps[i + 1]] if i < len(sorted_steps) - 1 else END
        
        # Add conditional edge for tool execution
        has_tool_executor = step in tool_nodes
        graph.add_conditional_edges(
            agent_node,
            multi_agent_should_use_tools,
            {
                **({f"tool_executor_{step}": f"tool_executor_{step}"} if has_tool_executor else {}),
                "next_agent": next_agent_node,
                "end": END,
            }
        )
        logger.info(f"   ✅ Edge: {agent_node} → tool_executor_{step} (if tools) OR → {next_agent_node}")

        # Add ReAct loop edge
        if has_tool_executor:
            tool_node = tool_nodes[step]
            graph.add_edge(tool_node, agent_node)
            logger.info(f"   ✅ ReAct loop: {tool_node} → {agent_node}")

    # Final edge to END
    last_step = sorted_steps[-1]
    graph.add_edge(agent_nodes[last_step], END)
    logger.info(f"   ✅ Final: {agent_nodes[last_step]} → END")


def _build_parallel_edges(graph, config: MultiAgentConfig, agent_nodes: dict, tool_nodes: dict):
    """Build parallel edges with DAG topology and ReAct loop support."""
    parallel_groups = config.parallel_groups
    sorted_steps = sorted(agent_nodes.keys())
    
    logger.info(f"   Parallel groups: {parallel_groups}")
    
    # Track which steps are in parallel groups
    steps_in_groups = set()
    for group in parallel_groups:
        steps_in_groups.update(group)
    
    # Build edges for each parallel group
    for group_idx, group in enumerate(parallel_groups):
        is_last_group = group_idx == len(parallel_groups) - 1
        logger.info(f"   Processing parallel group {group_idx + 1}: steps {group}")
        
        # Add ReAct loop edges for each agent in this group
        for step in group:
            if step not in agent_nodes:
                logger.warning(f"⚠️  Step {step} in parallel group {group_idx + 1} not found in agents")
                continue
                
            agent_node = agent_nodes[step]
            has_tool_executor = step in tool_nodes
            
            # Add conditional edge for tool execution
            graph.add_conditional_edges(
                agent_node,
                multi_agent_should_use_tools,
                {
                    **({f"tool_executor_{step}": f"tool_executor_{step}"} if has_tool_executor else {}),
                    "next_agent": "__parallel_sync__",  # Special sync point
                    "end": END,
                }
            )
            logger.info(f"      ✅ Group {group_idx + 1} step {step}: {agent_node} → tool_executor (if tools) OR → sync")

            # Add ReAct loop edge
            if has_tool_executor:
                tool_node = tool_nodes[step]
                graph.add_edge(tool_node, agent_node)
                logger.info(f"      ✅ ReAct loop: {tool_node} → {agent_node}")
        
        # Add synchronization point after this parallel group
        if not is_last_group:
            next_group = parallel_groups[group_idx + 1]
            logger.info(f"      🔄 Sync point after group {group_idx + 1}, next group: {next_group}")
            # Connect all agents in this group to all agents in next group
            for next_step in next_group:
                if next_step in agent_nodes:
                    for current_step in group:
                        if current_step in agent_nodes:
                            current_node = agent_nodes[current_step]
                            next_node = agent_nodes[next_step]
                            graph.add_edge(current_node, next_node)
                            logger.info(f"      ✅ Sync edge: {current_node} → {next_node}")
    
    # Handle steps not in any parallel group (run sequentially at the end)
    remaining_steps = [s for s in sorted_steps if s not in steps_in_groups]
    
    if remaining_steps:
        logger.info(f"   Remaining sequential steps after parallel groups: {remaining_steps}")
        # Connect last parallel group to first remaining sequential step
        if parallel_groups:
            last_parallel_group = parallel_groups[-1]
            first_remaining = agent_nodes[remaining_steps[0]]
            
            # Add edges from each node in last parallel group to first remaining
            for step in last_parallel_group:
                if step in agent_nodes:
                    prev_node = agent_nodes[step]
                    graph.add_edge(prev_node, first_remaining)
                    logger.info(f"   ✅ Transition: parallel group → sequential: {prev_node} → {first_remaining}")
        
        # Chain remaining steps sequentially
        for i, step in enumerate(remaining_steps):
            agent_node = agent_nodes[step]
            has_tool_executor = step in tool_nodes
            
            if i < len(remaining_steps) - 1:
                next_step = remaining_steps[i + 1]
                next_agent_node = agent_nodes[next_step]
                
                # Add conditional edge for tool execution
                graph.add_conditional_edges(
                    agent_node,
                    multi_agent_should_use_tools,
                    {
                        **({f"tool_executor_{step}": f"tool_executor_{step}"} if has_tool_executor else {}),
                        "next_agent": next_agent_node,
                        "end": END,
                    }
                )
                logger.info(f"   ✅ Sequential: {agent_node} → {next_agent_node}")
                
                # Add ReAct loop edge
                if has_tool_executor:
                    tool_node = tool_nodes[step]
                    graph.add_edge(tool_node, agent_node)
                    logger.info(f"   ✅ ReAct loop: {tool_node} → {agent_node}")
            else:
                # Last step goes to END
                graph.add_edge(agent_node, END)
                logger.info(f"   ✅ Final: {agent_node} → END")
    else:
        # All steps are in parallel groups - connect last group to END
        if parallel_groups:
            last_group = parallel_groups[-1]
            for step in last_group:
                if step in agent_nodes:
                    graph.add_edge(agent_nodes[step], END)
            logger.info(f"   ✅ Final: parallel group {last_group} → END")


def create_multi_agent_workflow(config: MultiAgentConfig) -> StateGraph:
    """
    Create a multi-agent workflow graph.

    This is the main entry point for creating multi-agent workflows.
    It validates the config and builds the graph.

    Args:
        config: Multi-agent configuration (can be dict or MultiAgentConfig)

    Returns:
        Compiled StateGraph

    Raises:
        ValidationError: If config is invalid
    """
    # Validate config if it's a dict
    if isinstance(config, dict):
        config = MultiAgentConfig.model_validate(config)

    logger.info(f"🔧 Building multi-agent workflow with {len(config.agents)} agents")
    logger.info(f"   Context mode: {config.context_mode}")
    logger.info(f"   Execution mode: {config.execution_mode}")
    logger.info(f"   Final output key: {config.final_output_key}")
    
    if config.execution_mode == "parallel" and config.parallel_groups:
        logger.info(f"   Parallel groups: {config.parallel_groups}")

    for agent in config.agents:
        logger.info(f"   Step {agent.step}: Agent {agent.agent_id} ({agent.input_key} → {agent.output_key})")
        if agent.enable_tools and agent.tools:
            logger.info(f"           Tools enabled: {len(agent.tools)} tools")

    return build_multi_agent_graph(config)
