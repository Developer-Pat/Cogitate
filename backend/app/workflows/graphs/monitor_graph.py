"""Monitor workflow family — graph builders.

Two graphs share the monitor → analyze → report pattern:
- create_rss_monitor_graph: fetch → summarize → deliver (hourly)
- create_market_watch_graph: fetch → deliver (5-min)

Both use a checkpointed StateGraph so cross-run state ("last
seen" / "last price") persists in the checkpoint journal — the
execution-identity + checkpoint-as-memory design.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, TypedDict

from langgraph.graph import END, START, StateGraph

from app.workflows.nodes.monitor_nodes import (
    market_deliver_node,
    market_fetch_node,
    readiness_deliver_node,
    readiness_probe_node,
    rss_deliver_node,
    rss_fetch_node,
    rss_format_node,
    rss_summarize_node,
)

logger = logging.getLogger(__name__)


class MonitorState(TypedDict, total=False):
    """Shared monitor state (all keys optional; checkpoint-persisted).

    ``inputs`` carries the router's request inputs (WorkflowState
    convention) — must be declared or LangGraph filters it out.
    """

    config: Dict[str, Any]
    inputs: Dict[str, Any]
    feeds: List[str]
    symbol: str
    last_seen: Dict[str, List[str]]
    last_price: float
    new_items: List[Dict[str, Any]]
    report_text: str
    digest_path: str
    errors: List[str]
    current_step: str


def create_rss_monitor_graph():
    """RSS digest monitor: fetch → summarize → deliver."""
    builder = StateGraph(MonitorState)

    builder.add_node("rss_fetch", rss_fetch_node)
    builder.add_node("rss_summarize", rss_summarize_node)
    builder.add_node("rss_format", rss_format_node)
    builder.add_node("rss_deliver", rss_deliver_node)

    builder.add_edge(START, "rss_fetch")
    builder.add_edge("rss_fetch", "rss_summarize")
    builder.add_edge("rss_summarize", "rss_format")
    builder.add_edge("rss_format", "rss_deliver")
    builder.add_edge("rss_deliver", END)

    return builder


def create_readiness_check_graph():
    """First-run readiness check: probe → deliver (manual trigger)."""
    builder = StateGraph(MonitorState)

    builder.add_node("readiness_probe", readiness_probe_node)
    builder.add_node("readiness_deliver", readiness_deliver_node)

    builder.add_edge(START, "readiness_probe")
    builder.add_edge("readiness_probe", "readiness_deliver")
    builder.add_edge("readiness_deliver", END)

    return builder


def create_market_watch_graph():
    """Market watch monitor: fetch → deliver (5-min cadence)."""
    builder = StateGraph(MonitorState)

    builder.add_node("market_fetch", market_fetch_node)
    builder.add_node("market_deliver", market_deliver_node)

    builder.add_edge(START, "market_fetch")
    builder.add_edge("market_fetch", "market_deliver")
    builder.add_edge("market_deliver", END)

    return builder


GRAPH_BUILDERS = {
    "rss-monitor": create_rss_monitor_graph,
    "market-watch": create_market_watch_graph,
    "readiness-check": create_readiness_check_graph,
}
