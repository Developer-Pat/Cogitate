"""Workflow graph resolution — every template resolves to a graph.

The get_workflow_graph if-chain became a data table + the kind
registry. These tests pin the resolution contract:

- legacy per-template graphs resolve identically (node-for-node)
- kind-based resolution (simple-with-approval → advanced via chain
  kind; simple-hello/test-basic → simple kind)
- the default fallback is the simple workflow
- the kind registry's KIND_GRAPH_FACTORIES resolves for the kinds
  with generic graphs
"""

import shutil
from pathlib import Path

import pytest

from app.workflows.api.workflow_router import get_workflow_graph
from app.workflows.graphs.monitor_graph import (
    create_rss_monitor_graph, create_market_watch_graph,
    create_readiness_check_graph,
)
from app.workflows.graphs.file_clerk_graph import create_file_clerk_graph
from app.workflows.graphs.boss_agent_graph import create_boss_agent_graph
from app.workflows.graphs.context_indexer_graph import create_context_indexer_graph
from app.workflows.graphs.agent_workflows import (
    create_hello_agent_graph, create_math_assistant_graph,
    create_code_review_graph, create_summary_agent_graph,
    create_agent_workflow_graph,
)
from app.workflows.graphs.default_provider_test_graphs import (
    create_llm_connection_graph, create_llm_chain_graph,
    create_llm_summary_graph, create_llm_comparison_graph,
)
from app.workflows.graphs.advanced_workflow import create_advanced_workflow
from app.workflows.graphs.simple_workflow import create_simple_workflow
from app.workflows.nodes.agent_nodes import agent_invoke_node
from app.domain.workflows.kinds.registry import resolve_kind_graph_factory


def _nodes(g):
    return sorted(getattr(g, "nodes", {}).keys())


# THE SUITE'S DB-ISOLATION (2026-08-26, the sweep): the earlier
# tests MUTATE the live db's workflow_templates.kind_id — the
# kind-registry resolution reads it, so the suite's run resolved
# templates to the wrong factories. The autouse copy + from_settings
# patch pins the resolution contract against a CLEAN db.
@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch, live_db_path):
    from app.core.config import Paths as CorePaths
    db_copy = tmp_path / "cogitate.db"
    shutil.copy(live_db_path, db_copy)
    # Resolved BEFORE the patch — `rooted_at` derives through `from_settings`.
    sandbox = CorePaths.rooted_at(db_copy)
    monkeypatch.setattr(
        CorePaths, "from_settings",
        classmethod(lambda cls, settings: sandbox),
    )


class TestLegacyResolution:
    """The old if-chain cases resolve node-for-node identically."""

    def test_monitor_family(self):
        cases = [
            ("rss-monitor", create_rss_monitor_graph()),
            ("market-watch", create_market_watch_graph()),
            ("readiness-check", create_readiness_check_graph()),
        ]
        for tid, expected in cases:
            assert _nodes(get_workflow_graph(tid)) == _nodes(expected), tid

    def test_provider_test_fixtures(self):
        cases = [
            ("test-llm-connection", create_llm_connection_graph()),
            ("test-llm-chain", create_llm_chain_graph()),
            ("test-llm-summary", create_llm_summary_graph()),
            ("test-llm-comparison", create_llm_comparison_graph()),
        ]
        for tid, expected in cases:
            assert _nodes(get_workflow_graph(tid)) == _nodes(expected), tid

    def test_agent_demos(self):
        cases = [
            ("agent-hello", create_hello_agent_graph()),
            ("agent-math", create_math_assistant_graph()),
            ("agent-code-review", create_code_review_graph()),
            ("agent-summary", create_summary_agent_graph()),
        ]
        for tid, expected in cases:
            assert _nodes(get_workflow_graph(tid)) == _nodes(expected), tid

    def test_tool_test_fixtures(self):
        expected = create_agent_workflow_graph(agent_invoke_node)
        for tid in ("test-calculator", "test-datetime", "test-file-info",
                    "test-text-tools", "test-todo-list"):
            assert _nodes(get_workflow_graph(tid)) == _nodes(expected), tid

    def test_office_workflows(self):
        cases = [
            ("file-clerk", create_file_clerk_graph()),
            ("boss-agent", create_boss_agent_graph()),
            ("context-indexer", create_context_indexer_graph()),
        ]
        for tid, expected in cases:
            assert _nodes(get_workflow_graph(tid)) == _nodes(expected), tid


class TestKindResolution:
    """Templates without a legacy entry resolve via their kind."""

    def test_approval_template_resolves_via_chain_kind(self):
        # simple-with-approval is chain kind → the advanced graph
        assert _nodes(get_workflow_graph("simple-with-approval")) == _nodes(create_advanced_workflow())

    def test_simple_kind_templates(self):
        for tid in ("simple-hello", "test-basic", "test-long-running"):
            assert _nodes(get_workflow_graph(tid)) == _nodes(create_simple_workflow()), tid

    def test_kind_graph_factories_resolve(self):
        # the kinds with generic graphs resolve to a StateGraph
        for kind in ("file-processing", "batch-orchestration",
                     "context-indexing", "chain", "simple"):
            factory = resolve_kind_graph_factory(kind)
            assert factory is not None, kind
            assert _nodes(factory())  # non-empty node set

    def test_kind_without_generic_graph_returns_none(self):
        # agent-task gained a generic factory (the deep-agent job) —
        # a kind with NO factory at all is the honest probe
        from app.domain.workflows.kinds.registry import (
            KIND_GRAPH_FACTORIES, get_kind,
        )
        for kind in ("monitor", "multi-agent"):
            assert get_kind(kind) is not None
            assert kind not in KIND_GRAPH_FACTORIES


class TestDefaults:
    def test_unknown_template_falls_back_to_simple(self):
        assert _nodes(get_workflow_graph("nonexistent")) == _nodes(create_simple_workflow())

    def test_empty_template_falls_back_to_simple(self):
        assert _nodes(get_workflow_graph("")) == _nodes(create_simple_workflow())
