"""
File Clerk Workflow Graph.

Sequential pipeline for organizing markdown files:
  list_files → summarize_all → classify_subjects → create_folders → move_files

Each step stores its output in the workflow state, enabling checkpoint-based
resume if the workflow is interrupted.
"""

import logging
from langgraph.graph import StateGraph, END

from ..state.workflow_state import WorkflowState
from ..nodes.file_clerk_nodes import (
    list_files_node,
    summarize_all_node,
    classify_subjects_node,
    create_folders_node,
    move_files_node,
)

logger = logging.getLogger(__name__)


def create_file_clerk_graph() -> StateGraph:
    """
    Create the File Clerk workflow graph.

    Linear pipeline:
        list_files → summarize_all → classify_subjects → create_folders → move_files → END

    Each node stores results in outputs dict for downstream nodes to consume.

    Returns:
        StateGraph ready for compilation with checkpointer
    """
    graph = StateGraph(WorkflowState)

    # Add nodes
    graph.add_node("list_files", list_files_node)
    graph.add_node("summarize_all", summarize_all_node)
    graph.add_node("classify_subjects", classify_subjects_node)
    graph.add_node("create_folders", create_folders_node)
    graph.add_node("move_files", move_files_node)

    # Entry point
    graph.set_entry_point("list_files")

    # Linear edges
    graph.add_edge("list_files", "summarize_all")
    graph.add_edge("summarize_all", "classify_subjects")
    graph.add_edge("classify_subjects", "create_folders")
    graph.add_edge("create_folders", "move_files")
    graph.add_edge("move_files", END)

    return graph
