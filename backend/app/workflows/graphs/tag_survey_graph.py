"""Tag Survey Workflow Graph — the fan-out survey (2026-08-23).

The tag-layer-sweeper adaptation of the boss-agent fan-out:

    list_files -> tag_dispatch -> batch_workers -> tag_merge -> END

- list_files: enumerate the wiki pages (reused from File Clerk).
- tag_dispatch: declare the tag worker, then split into batches.
- batch_workers: run the tag-extract worker per batch in parallel
  threads (each returns its tag rows).
- tag_merge: assemble the batch rows into the manifest.
- the_boss: consolidate the tags (renames / adds / drops).

The worker and the boss are PSEUDO-AGENT specs (app/domain/
pseudo_agents): a named prompt plus an ordered provider chain —
the free route, then the local Bonsai, then the paid brain. The
manifest lands in the workflow outputs; the consolidation report
is written to the agent's workspace.
"""

import logging
from langgraph.graph import StateGraph, END

from ..state.workflow_state import WorkflowState
from ..nodes.boss_agent_nodes import batch_workers_node
from ..nodes.tag_survey_nodes import (
    tag_discover_node,
    tag_dispatch_node,
    tag_merge_node,
    boss_node,
)

logger = logging.getLogger(__name__)


def create_tag_survey_graph() -> StateGraph:
    """Create the tag-survey fan-out graph.

    Pipeline: list_files -> tag_dispatch -> batch_workers -> tag_merge -> END

    - The boss graph's batch_workers_node runs the WORKERS; the
      tag worker function is declared by tag_dispatch via the
      config's worker_fn channel.
    """
    graph = StateGraph(WorkflowState)

    graph.add_node("list_files", tag_discover_node)
    graph.add_node("tag_dispatch", tag_dispatch_node)
    graph.add_node("batch_workers", batch_workers_node)
    graph.add_node("tag_merge", tag_merge_node)
    graph.add_node("the_boss", boss_node)

    graph.set_entry_point("list_files")
    graph.add_edge("list_files", "tag_dispatch")
    graph.add_edge("tag_dispatch", "batch_workers")
    graph.add_edge("batch_workers", "tag_merge")
    graph.add_edge("tag_merge", "the_boss")
    graph.add_edge("the_boss", END)

    return graph
