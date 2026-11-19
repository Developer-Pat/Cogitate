"""
Context Indexer Workflow Graph.

Sequential pipeline for building a searchable file index:
  scan → summarize → classify → store

Output: SQLite database (context_index.db) in the target folder.
"""

import logging
from langgraph.graph import StateGraph, END

from ..state.workflow_state import WorkflowState
from ..nodes.context_indexer_nodes import (
    indexer_scan_node,
    indexer_summarize_node,
    indexer_classify_node,
    indexer_store_node,
)

logger = logging.getLogger(__name__)


def create_context_indexer_graph() -> StateGraph:
    """
    Create the Context Indexer workflow graph.

    Linear pipeline:
        scan → summarize → classify → store → END

    Each node stores results in outputs dict for downstream nodes.

    Returns:
        StateGraph ready for compilation with checkpointer
    """
    graph = StateGraph(WorkflowState)

    # Add nodes
    graph.add_node("scan", indexer_scan_node)
    graph.add_node("summarize", indexer_summarize_node)
    graph.add_node("classify", indexer_classify_node)
    graph.add_node("store", indexer_store_node)

    # Entry point
    graph.set_entry_point("scan")

    # Linear edges
    graph.add_edge("scan", "summarize")
    graph.add_edge("summarize", "classify")
    graph.add_edge("classify", "store")
    graph.add_edge("store", END)

    return graph
