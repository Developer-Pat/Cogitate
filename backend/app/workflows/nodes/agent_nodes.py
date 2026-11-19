"""
Agent Workflow Nodes

Nodes that invoke agents with their configured system prompts and parameters.
"""

import logging
from typing import Dict, Any, cast
from datetime import datetime, UTC
from langchain_core.messages import HumanMessage, SystemMessage

from app.workflows.state.workflow_state import WorkflowState, RunMetadata
from ..error_handling.grades import absorb, node_grade
from app.core.database import AsyncSessionLocal
from app.domain.agents.services import AgentService
from app.domain.providers.llm_factory import get_llm_from_config
from app.domain.providers.config_service import ProviderConfig
from app.services.cognitive_pipeline.output_budget import (
    PATH_DEFAULT,
    resolve_output_budget,
)

logger = logging.getLogger(__name__)


async def _get_agent_llm(agent_id: int):
    """
    Get LLM client configured for a specific agent.

    Args:
        agent_id: ID of the agent to load

    Returns:
        Tuple of (llm_client, agent_data)
    """
    async with AsyncSessionLocal() as db:
        agent_service = AgentService(db)
        agent = await agent_service.get_by_id(agent_id)

        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        if not agent.is_active:
            raise ValueError(f"Agent {agent_id} is not active")

        # Load provider config from database to get decrypted API key
        from app.domain.providers.config_service import ProviderConfigService
        provider_service = ProviderConfigService()
        
        # Get provider by name (agent.provider should match provider.name)
        provider_config = await provider_service.get_provider_by_name(db, agent.provider)
        
        # Get decrypted API key if provider has one
        api_key = None
        has_api_key = False
        if provider_config and provider_config.id is not None:
            has_api_key = await provider_service.has_api_key(db, provider_config.id)
            if has_api_key:
                api_key = await provider_service.get_api_key(db, provider_config.id)
        
        # Create provider config from agent settings
        config = ProviderConfig(
            id=agent.id,
            name=f"agent-{agent.name}",  # Use agent name as provider identifier
            provider_type=agent.provider,
            base_url=provider_config.base_url if provider_config else None,
            has_api_key=has_api_key,
            config={"default_model": agent.model}
        )

        # Get agent parameters
        params = agent.parameters or {}
        temperature = params.get("temperature", 0.7)
        top_p = params.get("top_p", 0.9)
        # THE OUTPUT BUDGET (the token-limit arc, C.1): a workflow node is not a
        # chat turn, but it is one of the writers of `max_tokens`. The resolver
        # decides it — the agent's declaration, then the reasoning floor — so a
        # node whose agent declares nothing runs on the resolver's fallback
        # rather than on a fourth copy of the same magic number, and a thinking
        # model's node gets its floor instead of an empty answer.
        max_tokens, _budget_reason = resolve_output_budget(
            agent, agent.model or "", path=PATH_DEFAULT,
        )
        logger.info(
            "💰 OUTPUT BUDGET (workflow node) max_tokens=%s reason=%s model=%s agent=%s",
            max_tokens, _budget_reason, agent.model, agent.id,
        )

        logger.info(f"✅ Loading agent: {agent.name} (id={agent_id}, provider={agent.provider}, model={agent.model}, has_api_key={has_api_key})")

        llm = get_llm_from_config(
            config,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            api_key=api_key,
        )

        return llm, {
            "id": agent.id,
            "name": agent.name,
            "system_prompt": agent.system_prompt,
            "provider": agent.provider,
            "model": agent.model,
        }


def _check_cancellation(state: WorkflowState) -> bool:
    """Check if workflow has been cancelled."""
    try:
        from ..utils.cancellation import is_workflow_cancelled
        return is_workflow_cancelled(state["workflow_id"])
    except Exception as e:
        logger.warning(f"Failed to check cancellation | workflow_id={state['workflow_id']} | error={str(e)}")
        return False


def _create_cancelled_response(state: WorkflowState, elapsed: int = 0) -> dict:
    """Create response for cancelled workflow."""
    now = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return {
        "execution_result": {
            "result": "Cancelled",
            "elapsed_seconds": elapsed,
            "completed_at": now
        },
        "current_step": None,
        "metadata": RunMetadata(
            workflow_id=state["workflow_id"],
            template_id=state["template_id"],
            started_at=getattr(state["metadata"], "started_at", None),
            completed_at=now,
            status="cancelled",
            error="Cancelled by user",
            config=state["metadata"].config if state["metadata"] and hasattr(state["metadata"], "config") else None,
            tags=state["metadata"].tags if state["metadata"] and hasattr(state["metadata"], "tags") else None
        )
    }


@node_grade("fatal")
def agent_invoke_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Invoke an agent with its system prompt and user input.

    This node:
    1. Loads the agent configuration from database
    2. Creates LLM client with agent's parameters
    3. Invokes with system prompt + user message
    4. Returns agent response

    Required config in metadata:
        - agent_id: ID of agent to use
        - user_input_key: Key in inputs dict containing user message (default: "user_input")
        - output_key: Key for output (default: "agent_response")

    Args:
        state: Current workflow state

    Returns:
        State updates with agent response
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    async def run_agent_invoke() -> Dict[str, Any]:
        """Run the async agent invocation in a new event loop."""
        try:
            # Get agent_id from config
            metadata = state.get("metadata")
            config: Dict[str, Any] = metadata.config if metadata and hasattr(metadata, "config") and metadata.config is not None else {}

            # Recipient contract (ARM Phase D): the step addresses the
            # agent BY NAME (registry identity — the white pages), or
            # by id for backward compatibility. Names resolve STRICT:
            # an unknown name fails loudly (dead-letter, not a hang).
            agent_name = config.get("agent_name")
            agent_id = config.get("agent_id")
            if agent_name:
                async with AsyncSessionLocal() as db:
                    from app.domain.agents.services import AgentService
                    resolved = await AgentService(db).resolve_agent(agent_name)
                agent_id = resolved.id
                logger.info(f"🔍 Registry: '{agent_name}' -> agent {agent_id}")
            if not agent_id:
                raise ValueError(
                    "Workflow step needs an agent — set 'agent_name' "
                    "(registry identity) or 'agent_id' in the config"
                )

            user_input_key = config.get("user_input_key", "user_input")
            output_key = config.get("output_key", "agent_response")

            # Get user input
            inputs = state.get("inputs", {})
            user_input = inputs.get(user_input_key, "Hello")

            logger.info(f"📤 Invoking agent {agent_id} with input: {user_input[:100]}...")

            # Get agent LLM
            llm, agent_data = await _get_agent_llm(agent_id)

            # Load agent's tools and bind to LLM
            from app.domain.tools.execution_service import ToolExecutionService
            async with AsyncSessionLocal() as db:
                tool_service = ToolExecutionService(db)
                # Pass agent_id as string since database stores it as text
                tools = await tool_service.get_enabled_tools_for_agent(str(agent_id))
            
            if tools:
                tool_names = []
                for t in tools:
                    if isinstance(t, dict):
                        tool_names.append(t.get('function', {}).get('name', 'unknown'))
                    else:
                        tool_names.append(getattr(t, 'name', getattr(t, 'slug', 'unknown')))
                logger.info(f"🔧 Binding {len(tools)} tools to LLM: {tool_names}")
                
                # Strip internal metadata before sending to provider
                # x-cogitate-tool is for internal routing only and should not be
                # sent to the LLM provider (leaks implementation details, may fail
                # strict-mode validation)
                clean_tools = [
                    {"type": t["type"], "function": t["function"]}
                    if isinstance(t, dict) else t
                    for t in tools
                ]
                llm_with_tools = llm.bind_tools(clean_tools)
            else:
                logger.info(f"📭 No tools configured for agent {agent_id}")
                llm_with_tools = llm

            # Detect if we are looping back after tool_executor_node.
            # When the last message in state is a ToolMessage, the full
            # conversation history is already accumulated in state["messages"]
            # and we must NOT re-add the system/human seed messages.
            from langchain_core.messages import ToolMessage as LCToolMessage
            existing_messages = state.get("messages", [])
            is_tool_loop = bool(existing_messages) and isinstance(
                existing_messages[-1], LCToolMessage
            )

            if is_tool_loop:
                # All context (System, Human, AIMessage w/ tool_calls, ToolMessages)
                # is accumulated in state — use it directly as LLM input.
                messages = list(existing_messages)
                seed_messages: list = []
            else:
                # Fresh invocation: build from system prompt + user input.
                messages = []
                seed_messages = []
                if agent_data["system_prompt"]:
                    logger.info(f"📋 Using system prompt: {agent_data['system_prompt'][:100]}...")
                    sys_msg = SystemMessage(content=agent_data["system_prompt"])
                    messages.append(sys_msg)
                    seed_messages.append(sys_msg)
                human_msg = HumanMessage(content=user_input)
                messages.append(human_msg)
                seed_messages.append(human_msg)

            # Single LLM call — the graph's conditional edge + tool_executor_node
            # handle the ReAct iteration; this node is responsible for one turn only.
            logger.info("📤 Sending request to agent...")
            response = await llm_with_tools.ainvoke(messages)

            content = response.content or ""
            logger.info(f"📥 Received agent response: {content[:200]}...")

            # Return only the *new* messages so add_messages reducer can append
            # them without duplicating what is already in state.
            new_messages = seed_messages + [response]

            outputs = {
                output_key: content,
                "agent_id": agent_data["id"],
                "agent_name": agent_data["name"],
                "agent_model": f"{agent_data['provider']}/{agent_data['model']}",
            }

            now = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            is_done = not getattr(response, "tool_calls", None)

            result: Dict[str, Any] = {
                "messages": new_messages,
                "outputs": outputs,
                "current_step": None,
            }

            if is_done:
                # Final answer reached — mark the workflow as completed.
                result["execution_result"] = {
                    "result": f"Agent {agent_data['name']} responded successfully",
                    "completed_at": now,
                    "agent_id": agent_data["id"],
                    "agent_name": agent_data["name"],
                }
                result["metadata"] = RunMetadata(
                    workflow_id=state["workflow_id"],
                    template_id=state["template_id"],
                    started_at=getattr(state["metadata"], "started_at", None),
                    completed_at=now,
                    status="completed",
                    config=metadata.config if metadata and hasattr(metadata, "config") else None,
                    tags=metadata.tags if metadata and hasattr(metadata, "tags") else None,
                )
            else:
                logger.info(
                    f"🔧 Agent requested tools: "
                    f"{[tc['name'] for tc in response.tool_calls]} "
                    f"— routing to tool_executor_node"
                )

            return result
            
        except Exception as e:
            # FATAL (the @node_grade above): the agent's answer IS the run's product, so an
            # LLM failure here is the run's failure, not a per-item detail. absorb()
            # re-raises; the frame records it and names the offender.
            absorb(agent_invoke_node, state, e)
            logger.error(f"❌ Agent invocation failed: {str(e)}", exc_info=True)
            now = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            return {
                "outputs": {
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                "current_step": None,
                "execution_result": {
                    "result": "Agent invocation failed",
                    "completed_at": now,
                    "error": str(e),
                },
                "metadata": RunMetadata(
                    workflow_id=state["workflow_id"],
                    template_id=state["template_id"],
                    started_at=getattr(state["metadata"], "started_at", None),
                    completed_at=now,
                    status="error",
                    error=str(e),
                    config=metadata.config if metadata and hasattr(metadata, "config") else None,
                    tags=metadata.tags if metadata and hasattr(metadata, "tags") else None
                )
            }

    # Run async in thread pool to avoid event loop issues
    with ThreadPoolExecutor() as executor:
        future = executor.submit(lambda: asyncio.run(run_agent_invoke()))
        return future.result()


def tool_executor_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Execute all tool calls from the last AIMessage in the workflow state.

    This node is reached via a conditional edge from ``agent_invoke_node`` when
    the LLM response contains ``tool_calls``.  It:

    1. Finds the most-recent AIMessage that has pending tool calls.
    2. Executes each tool via ``ToolExecutionService.execute_tool_for_agent()``.
    3. Returns a list of ``ToolMessage`` objects which the ``add_messages``
       reducer appends to ``state["messages"]``.
    4. Records tool call history for observability.

    After this node the graph loops back to ``agent_invoke_node``, which picks
    up the full conversation history (including the new ToolMessages) and sends
    another request to the LLM so it can continue its reasoning.
    """
    import asyncio
    import time
    from concurrent.futures import ThreadPoolExecutor as _TPE
    from datetime import datetime

    async def run_tools():
        from langchain_core.messages import ToolMessage as LCToolMessage
        from app.domain.tools.execution_service import ToolExecutionService

        existing_messages = state.get("messages", [])
        # Find last AI message that has unresolved tool calls
        last_ai = next(
            (m for m in reversed(existing_messages)
             if hasattr(m, "tool_calls") and m.tool_calls),
            None,
        )
        if not last_ai:
            logger.warning("⚠️  tool_executor_node called but no tool_calls found in state")
            return {"messages": [], "tool_calls_history": [], "tool_loop_count": state.get("tool_loop_count", 0)}

        metadata = state.get("metadata")
        config = metadata.config if metadata and hasattr(metadata, "config") else {}
        agent_id = config.get("agent_id")

        tool_messages = []
        history_entries = []
        current_iteration = state.get("tool_loop_count", 0) + 1
        
        async with AsyncSessionLocal() as db:
            svc = ToolExecutionService(db)
            for tc in last_ai.tool_calls:
                start_ms = time.time() * 1000
                logger.info(f"🔧 Executing tool '{tc['name']}' for agent {agent_id}")
                exec_result = await svc.execute_tool_for_agent(
                    agent_id=agent_id,
                    tool_slug=tc["name"],
                    arguments=tc["args"],
                    session_id=str(state.get("workflow_id", "")),
                )
                end_ms = time.time() * 1000
                
                msg_content = (
                    str(exec_result.result)
                    if exec_result.success
                    else f"Error: {exec_result.error}"
                )
                tool_messages.append(
                    LCToolMessage(content=msg_content, tool_call_id=tc["id"])
                )
                
                # Record history entry for observability
                history_entries.append({
                    "iteration": current_iteration,
                    "name": tc["name"],
                    "args": tc["args"],
                    "call_id": tc["id"],
                    "result": str(exec_result.result) if exec_result.success else f"Error: {exec_result.error}",
                    "success": exec_result.success,
                    "execution_time_ms": int(end_ms - start_ms),
                    "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
                })
                
                # THE LOUD TOOL-VERDICT LOG (2026-08-23, the base_path
                # bug): the wrapper logged success=True while the tool
                # PAYLOAD said success=False — the '✅ file-manager'
                # masked a 'base_path is required' failure. Log the
                # payload's verdict too: a tool that failed must be
                # visible as failed (the user's doctrine).
                _payload = getattr(exec_result, "result", None)
                _payload_failed = (
                    isinstance(_payload, dict) and _payload.get("success") is False
                )
                if _payload_failed or not exec_result.success:
                    logger.error(
                        f"  ❌ {tc['name']} FAILED: wrapper_success={exec_result.success} "
                        f"payload={str(_payload)[:200]}"
                    )
                else:
                    logger.info(
                        f"  ✅ {tc['name']}: success={exec_result.success} "
                        f"({exec_result.execution_time_ms}ms)"
                    )

        return {
            "messages": tool_messages,
            "tool_calls_history": history_entries,
            "tool_loop_count": current_iteration,
        }

    with _TPE() as executor:
        future = executor.submit(lambda: asyncio.run(run_tools()))
        return cast(dict[str, Any], future.result())


def should_use_tools(state: WorkflowState) -> str:
    """
    Conditional routing function for the agent graph.

    Returns ``"tool_executor"`` when the last message in state contains
    ``tool_calls`` (i.e. the LLM wants to invoke one or more tools).
    Returns ``END`` when the LLM has produced a final text answer.
    
    Includes a guard against infinite loops (max 10 iterations).
    """
    from langgraph.graph import END

    # THE DEEP-AGENT RAISE (2026-08-23, the sweep run): the hard
    # 10-iteration cap killed the sweep — a 486-file survey needs
    # 50+ tool calls. The cap is now CONFIGURABLE per workflow (the
    # template config declares max_tool_iterations; the default
    # stays 10 for the chat-era guards). The deep-agent-job sets 200.
    metadata = state.get("metadata")
    wf_config = metadata.config if metadata and hasattr(metadata, "config") and metadata.config else {}
    MAX_TOOL_ITERATIONS = int(wf_config.get("max_tool_iterations", 10))

    # Guard against infinite loops
    if state.get("tool_loop_count", 0) >= MAX_TOOL_ITERATIONS:
        logger.warning(f"⚠️  Tool loop hit {MAX_TOOL_ITERATIONS} iterations — forcing END")
        return END

    messages = state.get("messages", [])
    if not messages:
        return END
    last = messages[-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tool_executor"
    return END


def hello_agent_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Simple hello agent workflow node.

    Uses agent ID from config, sends a greeting request.

    Required config:
        - agent_id: ID of agent to use

    Returns:
        greeting: Agent's greeting response
    """
    return agent_invoke_node(state)


def math_assistant_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Math assistant agent node.

    Expects user_input to contain a math question.
    Returns answer with explanation.
    """
    return agent_invoke_node(state)


def code_review_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Code review agent node.

    Expects user_input to contain code snippet.
    Returns review with suggestions.
    """
    return agent_invoke_node(state)


def summary_agent_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Summary agent node.

    Expects user_input to contain text to summarize.
    Returns concise summary.
    """
    return agent_invoke_node(state)
