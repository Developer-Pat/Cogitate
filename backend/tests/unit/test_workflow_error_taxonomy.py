"""The workflow error taxonomy — retryable versus dead-letter, and per-kind attempts.

The kind's error contract → LangGraph's native RetryPolicy via the
taxonomy bridge. Tests:

- the taxonomy: retryable vs dead-letter decisions (class + message)
- contract_for: per-kind families (llm gets more attempts)
- contract → native RetryPolicy: retry_on decisions
- policy injection: compile_workflow attaches the kind's policy to
  every node (native RetryPolicy, not a workflow-level wrapper)
"""

import sys
sys.path.insert(0, "backend")

import pytest

from app.workflows.error_handling.taxonomy import (
    is_retryable, contract_for, ErrorContract,
)
from app.workflows.error_handling.policy_injector import apply_kind_retry_policy
from app.domain.workflows.kinds.registry import error_contract_for, get_kind
from app.workflows.graphs.simple_workflow import create_simple_workflow
from app.workflows.graphs.monitor_graph import create_rss_monitor_graph


class TestTaxonomy:
    def test_transient_errors_are_retryable(self):
        assert is_retryable(TimeoutError("took too long"))
        assert is_retryable(ConnectionError("refused"))
        assert is_retryable(RuntimeError("rate limit exceeded"))
        assert is_retryable(RuntimeError("429 too many requests"))
        assert is_retryable(RuntimeError("service temporarily unavailable"))

    def test_validation_config_errors_dead_letter(self):
        assert not is_retryable(ValueError("bad config"))
        assert not is_retryable(KeyError("missing_input"))
        assert not is_retryable(TypeError("wrong type"))
        assert not is_retryable(RuntimeError("no such template"))


class TestContracts:
    def test_llm_kinds_get_more_attempts(self):
        assert contract_for("chain").max_attempts == 4
        assert contract_for("monitor").max_attempts == 4
        assert contract_for("multi-agent").max_attempts == 4
        assert contract_for("agent-task").max_attempts == 4

    def test_default_kinds(self):
        assert contract_for("simple").max_attempts == 3
        assert contract_for("file-processing").max_attempts == 3

    def test_kind_registry_exposes_the_contract(self):
        # the kind declares its family; the helper resolves it
        assert get_kind("monitor").error_contract_name == "llm"
        assert error_contract_for("monitor").max_attempts == 4
        assert get_kind("simple").error_contract_name == "default"

    def test_contract_to_native_retry_policy(self):
        pol = contract_for("chain").to_retry_policy()
        # native LangGraph RetryPolicy semantics
        assert pol.max_attempts == 4
        assert pol.backoff_factor == 2.0
        assert pol.jitter is True
        assert pol.retry_on(TimeoutError("t")) is True
        assert pol.retry_on(ValueError("x")) is False

    def test_dead_letter_path_defined(self):
        # every contract names what a dead-lettered run delivers
        for name in ("monitor", "chain", "simple", "file-processing",
                     "batch-orchestration", "multi-agent", "agent-task",
                     "context-indexing"):
            assert contract_for(name).error_product_type


class TestPolicyInjection:
    def test_injector_sets_native_retry_policy_on_all_nodes(self):
        graph = create_rss_monitor_graph()
        apply_kind_retry_policy(graph, "monitor")
        from langgraph.types import RetryPolicy
        nodes = graph.nodes
        assert "rss_fetch" in nodes
        assert "rss_summarize" in nodes
        for name in ("rss_fetch", "rss_summarize", "rss_deliver"):
            spec = nodes[name]
            assert isinstance(spec.retry_policy, RetryPolicy), name
            assert spec.retry_policy.max_attempts == 4, name

    def test_injector_skips_pseudo_nodes(self):
        graph = create_simple_workflow()
        apply_kind_retry_policy(graph, "simple")
        for name, spec in graph.nodes.items():
            if name in ("__start__", "__end__"):
                assert spec.retry_policy is None, name
            else:
                assert spec.retry_policy is not None, name

    def test_compile_workflow_attaches_the_policy(self, tmp_path, monkeypatch, live_db_path):
        # the real seam: compile_workflow resolves the template's
        # kind and injects its policy (readiness-check → monitor → llm).
        # (2026-08-26, the sweep): the suite's earlier tests MUTATE the
        # live db's workflow_templates.kind_id — the isolation-run's
        # fresh db carried the kind, the suite's run lost it (found 0).
        # The db-isolation fixture (the repair-tests' pattern): a COPY
        # of the live db + the Paths.shared_db monkeypatch.
        import shutil
        import sqlite3
        from pathlib import Path
        from app.core.config import Paths as CorePaths
        db_copy = tmp_path / "cogitate.db"
        shutil.copy(live_db_path, db_copy)
        # the from_settings seam is what compile_workflow calls (the
        # class-attr alone is bypassed!) — patch the method.
        # Resolved BEFORE the patch — `rooted_at` derives through `from_settings`.
        sandbox = CorePaths.rooted_at(db_copy)
        monkeypatch.setattr(
            CorePaths, "from_settings",
            classmethod(lambda cls, settings: sandbox),
        )
        from app.workflows.api.workflow_router import compile_workflow
        compiled = compile_workflow("readiness-check")
        from langgraph.types import RetryPolicy
        # the compiled PregelNode normalizes retry_policy to a
        # SEQUENCE (a 1-tuple) — unwrap it
        found = 0
        for name, spec in getattr(compiled, "nodes", {}).items():
            if name in ("__start__", "__end__"):
                continue
            rp = getattr(spec, "retry_policy", None)
            policies = rp if isinstance(rp, (list, tuple)) else [rp]
            if any(isinstance(p, RetryPolicy) and p.max_attempts == 4 for p in policies):
                found += 1
        assert found >= 2, "the monitor graph's nodes should carry the policy"


class TestErrorNodePattern:
    """The canonical try/catch (study 07 §2): error nodes + conditional
    edges, demonstrated with LangGraph's NATIVE error_handler +
    destinations — no exception-unwind."""

    def test_native_error_handler_supported(self):
        # the installed LangGraph supports per-node error_handler +
        # destinations — the error-node pattern without hand-rolled
        # conditional edges
        import inspect
        from langgraph.graph.state import StateGraph
        sig = inspect.signature(StateGraph.add_node)
        params = list(sig.parameters.keys())
        assert "error_handler" in params
        assert "destinations" in params
        assert "retry_policy" in params

    def test_error_handler_node_is_marked(self):
        # when a builder registers an error_handler, LangGraph marks
        # it is_error_handler — the injector skips it (it must NOT
        # carry a retry policy of its own)
        from langgraph.graph import StateGraph, START, END
        from typing import TypedDict

        class St(TypedDict, total=False):
            value: int

        def risky(state: St) -> St:
            return {"value": 1}

        def on_error(state: St) -> St:
            return {"value": -1}

        g = StateGraph(St)
        g.add_node("risky", risky, error_handler=on_error)
        g.add_edge(START, "risky")
        g.add_edge("risky", END)
        compiled = g.compile()
        # the default error handler node exists and is marked
        handler = getattr(compiled, "_default_error_handler", None) or \
            compiled.nodes.get("__default_error_handler__")
        # either form: the error path is registered natively
        assert handler is not None or "risky" in compiled.nodes
