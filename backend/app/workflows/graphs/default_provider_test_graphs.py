"""
Default Provider Test Workflow Graphs

Creates executable workflow graphs that use the real LLM test nodes.
These graphs integrate the test nodes from default_provider_test_nodes.py
into runnable workflows.
"""

from langgraph.graph import StateGraph, END
import logging

from app.workflows.state.workflow_state import WorkflowState
from app.workflows.nodes.default_provider_test_nodes import (
    test_llm_connection_node,
    test_llm_chain_node,
    test_llm_summary_node,
    test_llm_comparison_node,
)

logger = logging.getLogger(__name__)


def create_llm_connection_graph() -> StateGraph:
    """
    Create workflow graph for LLM connection test.
    
    Graph structure:
    [START] -> [test_llm_connection_node] -> [END]
    """
    builder = StateGraph(WorkflowState)
    
    # Add the test node
    builder.add_node("test_connection", test_llm_connection_node)
    
    # Set entry point
    builder.set_entry_point("test_connection")
    
    # Set finish point
    builder.add_edge("test_connection", END)
    
    return builder


def create_llm_chain_graph() -> StateGraph:
    """
    Create workflow graph for LLM chaining test.
    
    Graph structure:
    [START] -> [test_llm_chain_node] -> [END]
    
    The chain node internally handles all 3 steps.
    """
    builder = StateGraph(WorkflowState)
    
    # Add the chain test node (handles all steps internally)
    builder.add_node("test_chain", test_llm_chain_node)
    
    # Set entry point
    builder.set_entry_point("test_chain")
    
    # Set finish point
    builder.add_edge("test_chain", END)
    
    return builder


def create_llm_summary_graph() -> StateGraph:
    """
    Create workflow graph for LLM summarization test.
    
    Graph structure:
    [START] -> [test_llm_summary_node] -> [END]
    """
    builder = StateGraph(WorkflowState)
    
    # Add the summary test node
    builder.add_node("test_summary", test_llm_summary_node)
    
    # Set entry point
    builder.set_entry_point("test_summary")
    
    # Set finish point
    builder.add_edge("test_summary", END)
    
    return builder


def create_llm_comparison_graph() -> StateGraph:
    """
    Create workflow graph for LLM comparison test.
    
    Graph structure:
    [START] -> [test_llm_comparison_node] -> [END]
    
    The comparison node internally handles all 3 prompts.
    """
    builder = StateGraph(WorkflowState)
    
    # Add the comparison test node
    builder.add_node("test_comparison", test_llm_comparison_node)
    
    # Set entry point
    builder.set_entry_point("test_comparison")
    
    # Set finish point
    builder.add_edge("test_comparison", END)
    
    return builder


def get_all_test_graphs() -> dict[str, StateGraph]:
    """
    Get all test workflow graphs.
    
    Returns:
        Dictionary mapping workflow ID to graph builder
    """
    return {
        "test-llm-connection": create_llm_connection_graph(),
        "test-llm-chain": create_llm_chain_graph(),
        "test-llm-summary": create_llm_summary_graph(),
        "test-llm-comparison": create_llm_comparison_graph(),
    }


if __name__ == "__main__":
    # Test graph creation
    graphs = get_all_test_graphs()
    print(f"Created {len(graphs)} workflow graphs:")
    for wf_id, graph in graphs.items():
        print(f"  - {wf_id}: {graph}")
