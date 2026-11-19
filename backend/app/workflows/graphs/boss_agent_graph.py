"""
BossAgent Workflow Graph.

Multi-batch orchestrator for large-scale file classification:
  list_files → boss_dispatch → batch_workers → boss_merge → create_folders → move_files

The BossAgent:
- Uses list_files from File Clerk (reused)
- boss_dispatch decides batch strategy (single vs multi-batch)
- batch_workers runs File Clerk nodes per batch (summarize + classify)
- boss_merge merges overlapping categories across batches
- create_folders + move_files from File Clerk (reused)

For small file sets (< 15), it falls through to single-pass mode.
"""

import logging
from langgraph.graph import StateGraph, END

from ..state.workflow_state import WorkflowState
from ..nodes.file_clerk_nodes import (
    list_files_node,
    create_folders_node,
    move_files_node,
)
from ..nodes.boss_agent_nodes import (
    boss_dispatch_node,
    batch_workers_node,
    boss_merge_node,
)

logger = logging.getLogger(__name__)


def create_boss_agent_graph() -> StateGraph:
    """
    Create the BossAgent workflow graph.

    Pipeline:
        list_files → boss_dispatch → batch_workers → boss_merge → create_folders → move_files → END

    - boss_dispatch: decides single vs batched strategy
    - batch_workers: runs File Clerk summarize + classify per batch
    - boss_merge: LLM merges categories from all batches
    - create_folders, move_files: reused from File Clerk

    Returns:
        StateGraph ready for compilation with checkpointer
    """
    graph = StateGraph(WorkflowState)

    # Add nodes
    graph.add_node("list_files", list_files_node)
    graph.add_node("boss_dispatch", boss_dispatch_node)
    graph.add_node("batch_workers", batch_workers_node)
    graph.add_node("boss_merge", boss_merge_node)
    graph.add_node("create_folders", create_folders_node)
    graph.add_node("move_files", move_files_node)

    # Entry point
    graph.set_entry_point("list_files")

    # Linear edges
    graph.add_edge("list_files", "boss_dispatch")
    graph.add_edge("boss_dispatch", "batch_workers")
    graph.add_edge("batch_workers", "boss_merge")
    graph.add_edge("boss_merge", "create_folders")
    graph.add_edge("create_folders", "move_files")
    graph.add_edge("move_files", END)

    return graph
