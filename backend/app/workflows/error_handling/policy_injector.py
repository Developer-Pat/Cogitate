"""Apply a kind's error contract to a graph at compile time (Phase F).

LangGraph attaches retry_policy at add_node time; graphs built by
the individual builders don't pass it. This module post-fixes a
built StateGraph's node specs before compilation — the single
seam that wires the KIND's declared error contract (the taxonomy)
into EVERY node of the graph, without rewriting the builders.

The canonical try/catch (study 07 §2): LangGraph's native
error_handler + destinations are available per-node; this phase
wires the retry policy (the retryable leg). The dead-letter
(error product) leg rides the execution status — a run that
exhausts retries fails with the taxonomy's decision recorded.
"""

from __future__ import annotations

from typing import Any

from app.workflows.error_handling.taxonomy import contract_for


def apply_kind_retry_policy(graph: Any, kind_name: str) -> Any:
    """Attach the kind's native RetryPolicy to every node.

    Mutates the StateGraph's node specs in place (LangGraph stores
    retry_policy on StateNodeSpec). START/END pseudo-nodes and
    error-handler nodes are skipped.
    """
    contract = contract_for(kind_name)
    policy = contract.to_retry_policy()

    nodes: dict[str, Any] = getattr(graph, "nodes", {})
    applied = 0
    for name, spec in nodes.items():
        if name in ("__start__", "__end__", START, END):
            continue
        if getattr(spec, "is_error_handler", False):
            continue
        try:
            spec.retry_policy = policy
            applied += 1
        except Exception:
            continue
    return graph


# LangGraph's pseudo-node names (imported defensively so this
# module imports even if the internals shift)
try:
    from langgraph.graph import START, END
except Exception:  # pragma: no cover
    START, END = "__start__", "__end__"
