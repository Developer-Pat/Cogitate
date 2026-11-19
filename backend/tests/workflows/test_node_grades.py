"""Node grades — what a node's failure means for its RUN.

The gap this closes: every node catches its own LLM failure and returns error state, so the
graph ended normally and the run was recorded `completed` — for a genuine provider failure,
named by nobody, with no toast. The grade is the declaration that was missing, and these
tests pin the three behaviours plus the DECLARATIONS themselves (a grade that is inferred
from a docstring is not declared).

The graph-level tests run the real `WorkflowState` through real two-node graphs, so what is
asserted is what the record layer will read.
"""

from __future__ import annotations

from typing import Any

import pytest
from langgraph.graph import END, START, StateGraph

from app.workflows.error_handling.grades import (
    DEFAULT_GRADE,
    absorb,
    grade_for_kind,
    grade_of,
    node_grade,
)
from app.workflows.state.workflow_state import LLMResolution, RunMetadata, WorkflowState
from app.workflows.utils.run_failure import run_failure_statement

RESOLUTION = LLMResolution(provider="ollama", model="phi4-mini:latest", rung="primary")
RUN_ID = "wf-grade-probe"
TEMPLATE_ID = "tpl-grade-probe"


class ProviderError(RuntimeError):
    """litellm-shaped: `llm_provider` is the attribute `is_provider_failure` reads, so this
    stands in for a real provider failure without importing litellm."""

    llm_provider = "ollama"


def _state() -> dict[str, Any]:
    """A run as the frame starts it — the resolved service carried on the run's metadata."""
    return {
        "workflow_id": RUN_ID,
        "template_id": TEMPLATE_ID,
        "metadata": RunMetadata(
            workflow_id=RUN_ID,
            template_id=TEMPLATE_ID,
            status="running",
            llm_resolution=RESOLUTION,
        ),
    }


def _run(nodes: dict[str, Any]) -> dict[str, Any]:
    names = list(nodes)
    graph = StateGraph(WorkflowState)
    for name, fn in nodes.items():
        graph.add_node(name, fn)
    graph.add_edge(START, names[0])
    for source, target in zip(names, names[1:]):
        graph.add_edge(source, target)
    graph.add_edge(names[-1], END)
    return graph.compile().invoke(_state())


# ── the vocabulary ───────────────────────────────────────────────────────────────────────


def test_the_kind_supplies_the_default_the_node_declares_the_rest():
    assert DEFAULT_GRADE == "recoverable"
    # the monitor family is tolerant BY CONSTRUCTION; every other kind defaults to recoverable
    assert grade_for_kind("monitor") == "tolerant"
    assert grade_for_kind("chain") == "recoverable"
    assert grade_for_kind(None) == "recoverable"


def test_a_declaration_is_read_off_the_node_and_beats_the_kind_default():
    @node_grade("fatal")
    def declared(state):  # noqa: ANN001, ANN202
        return {}

    def undeclared(state):  # noqa: ANN001, ANN202
        return {}

    assert grade_of(declared) == "fatal"
    assert grade_of(undeclared) == "recoverable"
    # a declared node keeps its declaration even under a kind whose default is the opposite
    assert grade_of(declared, kind="monitor") == "fatal"
    assert grade_of(undeclared, kind="monitor") == "tolerant"


def test_the_decorator_returns_the_same_function():
    """Graph wiring hands these callables to LangGraph — a decorator that returned a new
    object would silently change node identity."""

    def original(state):  # noqa: ANN001, ANN202
        return {}

    assert node_grade("fatal")(original) is original


def test_an_unknown_grade_is_refused_at_import_time():
    with pytest.raises(ValueError):
        node_grade("whatever")  # type: ignore[arg-type]


# ── the three behaviours ─────────────────────────────────────────────────────────────────


def test_a_tolerant_node_writes_no_verdict_on_the_run():
    @node_grade("tolerant")
    def tolerant(state):  # noqa: ANN001, ANN202
        return {}

    assert absorb(tolerant, _state(), ProviderError("feed is down")) == {}


def test_a_recoverable_node_marks_the_run_and_names_the_offender():
    def recoverable(state):  # noqa: ANN001, ANN202
        return {}

    verdict = absorb(recoverable, _state(), ProviderError("boom"))

    assert verdict["status"] == "error"
    assert "boom" in verdict["error"]
    statement = verdict["failure_statement"]
    assert statement is not None, "a recoverable failure with a carried resolution named nobody"
    assert "phi4" in statement.casefold() and "ollama" in statement.casefold(), statement


def test_a_recoverable_node_marks_the_run_even_when_it_cannot_name_anybody():
    """The run is marked either way; naming is the gate's extra, never a precondition."""
    def recoverable(state):  # noqa: ANN001, ANN202
        return {}

    state = _state()
    state["metadata"] = RunMetadata(workflow_id=RUN_ID, template_id=TEMPLATE_ID)  # nothing carried

    verdict = absorb(recoverable, state, ProviderError("boom"))

    assert verdict["status"] == "error"
    assert verdict["failure_statement"] is None


def test_a_recoverable_node_keeps_the_message_it_shows_its_reader():
    def recoverable(state):  # noqa: ANN001, ANN202
        return {}

    verdict = absorb(recoverable, _state(), ProviderError("boom"), error_text="the call failed: boom")

    assert verdict["error"] == "the call failed: boom"
    assert verdict["failure_statement"] is not None  # the statement is still the gate's own


def test_a_fatal_node_re_raises_so_the_run_fails_and_the_offender_is_still_nameable():
    @node_grade("fatal")
    def fatal(state):  # noqa: ANN001, ANN202
        return {}

    error = ProviderError("boom")

    with pytest.raises(ProviderError) as caught:
        absorb(fatal, _state(), error)

    # the SAME exception object: its traceback is what the frame's failure path sees
    assert caught.value is error

    # and naming comes free — the frame still holds initial_state.metadata, untouched by nodes
    statement = run_failure_statement(_state()["metadata"], caught.value)
    assert statement is not None and "phi4" in statement.casefold(), statement


# ── the graph level: what the run's own record will read ────────────────────────────────


def test_a_tolerant_nodes_failure_leaves_the_run_clean():
    @node_grade("tolerant")
    def fetch(state):  # noqa: ANN001, ANN202
        return {"execution_result": {"error": "the feed is down", "errors": ["the feed is down"]}}

    result = _run({"fetch": fetch})
    metadata = result["metadata"]

    assert metadata.status == "running", "a tolerated failure named the run's status"
    assert metadata.error is None
    assert metadata.failure_statement is None
    # the detail is not lost — it is the node's own report, which is DATA rather than a verdict
    assert result["execution_result"]["errors"] == ["the feed is down"]


def test_a_recoverable_nodes_failure_reaches_the_final_state():
    @node_grade("recoverable")
    def summarize(state):  # noqa: ANN001, ANN202
        return {"metadata": RunMetadata(workflow_id=RUN_ID, template_id=TEMPLATE_ID,
                                        **absorb(summarize, state, ProviderError("boom")))}

    metadata = _run({"summarize": summarize})["metadata"]

    assert metadata.status == "error"
    assert metadata.failure_statement is not None
    assert metadata.llm_resolution == RESOLUTION, "the verdict cost the carried identity"


def test_a_fatal_nodes_failure_fails_the_graph():
    @node_grade("fatal")
    def verify(state):  # noqa: ANN001, ANN202
        absorb(verify, state, ProviderError("no credentials"))
        return {}  # unreachable

    with pytest.raises(ProviderError):
        _run({"verify": verify})


# ── the declarations, read off the real modules ──────────────────────────────────────────


def test_the_ruling_is_declared_where_it_says_it_is():
    """A grade that lives only in prose is not declared. These are the module-level
    declarations the ruling of 2026-10-07 put in place."""
    from app.workflows.nodes.agent_nodes import agent_invoke_node
    from app.workflows.nodes.default_provider_test_nodes import (
        test_llm_chain_node,
        test_llm_comparison_node,
        test_llm_connection_node,
        test_llm_summary_node,
    )
    from app.workflows.nodes.enhanced_nodes import plan_node
    from app.workflows.nodes import monitor_nodes

    # the calls that ARE the node's purpose
    for node in (test_llm_connection_node, test_llm_chain_node, test_llm_summary_node,
                 test_llm_comparison_node, plan_node, agent_invoke_node):
        assert grade_of(node) == "fatal", f"{node.__name__} is not declared fatal"

    # the family whose resilience IS the purpose
    monitor_family = (
        monitor_nodes.rss_fetch_node, monitor_nodes.rss_summarize_node,
        monitor_nodes.rss_format_node, monitor_nodes.rss_deliver_node,
        monitor_nodes.market_fetch_node, monitor_nodes.market_deliver_node,
        monitor_nodes.readiness_probe_node, monitor_nodes.readiness_deliver_node,
    )
    for node in monitor_family:
        assert grade_of(node) == "tolerant", f"{node.__name__} is not declared tolerant"
