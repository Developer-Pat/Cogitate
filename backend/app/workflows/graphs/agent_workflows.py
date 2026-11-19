"""
Agent Workflow Graphs

Pre-built agent-based workflow definitions.
"""

import logging

from langgraph.graph import StateGraph, END

from app.workflows.state.workflow_state import WorkflowState
from app.workflows.nodes.agent_nodes import (
    tool_executor_node,
    should_use_tools,
    hello_agent_node,
    math_assistant_node,
    code_review_node,
    summary_agent_node,
    agent_invoke_node,
)

logger = logging.getLogger(__name__)


def create_agent_workflow_graph(agent_node_func) -> StateGraph:
    """
    Create an agent workflow graph with a ReAct tool-use loop.

    Graph topology:
        agent_invoke  ──(no tool calls)──►  END
             ▲                 │
             │       (tool calls present)
             │                 ▼
             └────  tool_executor  ◄────────┘

    Args:
        agent_node_func: The agent node function to use

    Returns:
        StateGraph builder (not compiled)
    """
    workflow = StateGraph(WorkflowState)

    # Add nodes
    workflow.add_node("agent_invoke", agent_node_func)
    workflow.add_node("tool_executor", tool_executor_node)

    # Set entry point
    workflow.set_entry_point("agent_invoke")

    # Conditional edge: if LLM returned tool_calls → tool_executor, else → END
    workflow.add_conditional_edges(
        "agent_invoke",
        should_use_tools,
        {"tool_executor": "tool_executor", END: END},
    )

    # After tools are executed, loop back to agent for the next LLM turn
    workflow.add_edge("tool_executor", "agent_invoke")

    return workflow


def create_hello_agent_graph() -> StateGraph:
    """Create hello agent workflow graph."""
    return create_agent_workflow_graph(hello_agent_node)


def create_math_assistant_graph() -> StateGraph:
    """Create math assistant workflow graph."""
    return create_agent_workflow_graph(math_assistant_node)


def create_code_review_graph() -> StateGraph:
    """Create code review workflow graph."""
    return create_agent_workflow_graph(code_review_node)


def create_summary_agent_graph() -> StateGraph:
    """Create summary agent workflow graph."""
    return create_agent_workflow_graph(summary_agent_node)


def create_agent_task_graph() -> StateGraph:
    """Create the GENERIC agent-task graph (the canonical kind entry).

    THE DEEP-AGENT JOB (2026-08-23, the user's 'no legacy' call):
    the agent-task kind's generic graph — the agent_invoke_node
    reads agent_id + the task from the template config, so ANY
    agent can run ANY task through the ReAct loop. Registered in
    KIND_GRAPH_FACTORIES (the canonical path), NOT the legacy
    per-template table — building on legacy entrench removal.
    """
    return create_agent_workflow_graph(agent_invoke_node)


# Pre-compiled agent workflow graphs (for backward compatibility)
hello_agent_graph = create_hello_agent_graph()
math_assistant_graph = create_math_assistant_graph()
code_review_graph = create_code_review_graph()
summary_agent_graph = create_summary_agent_graph()
