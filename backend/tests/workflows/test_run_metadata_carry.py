"""The `metadata` channel's MERGE POLICY — the run's identity survives a node's rebuild.

The defect this pins: `WorkflowState.metadata` was declared with no reducer, so LangGraph
REPLACED the channel every time a node returned a fresh `RunMetadata(...)` — which 32 sites
across 9 node modules do. `llm_resolution` (the service the run resolved at its start, G4-F2)
was therefore gone after the FIRST node, and `run_failure_statement` returned None for a
genuine provider failure: the gate built to name the offender could never fire on the node
path. The two failing halves are asserted here together, so the test also fails if the gate
stops gating.

The tests run the REAL `WorkflowState` through a real two-node graph — the probe shape the
study measured the defect with (`local/studies/llm-escalation-gap/01-the-gap-as-it-is.md` §4b).
"""

from __future__ import annotations

from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

from app.workflows.state.workflow_state import (
    LLMResolution,
    RunMetadata,
    WorkflowState,
    merge_run_metadata,
)
from app.workflows.utils.run_failure import run_failure_statement

RESOLUTION = LLMResolution(provider="ollama", model="phi4-mini:latest", rung="primary")

RUN_ID = "wf-carry-probe"
TEMPLATE_ID = "tpl-carry-probe"


class ProviderError(RuntimeError):
    """A provider-shaped exception: `llm_provider` is litellm's own attribute, and it is the
    second signal `is_provider_failure` reads — so this stands in for a real litellm failure
    without importing it."""

    llm_provider = "ollama"


def _initial_state() -> dict[str, Any]:
    """A run as the frame starts it: the resolved service carried on the run's metadata."""
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


def _run(nodes: dict[str, Callable[[dict[str, Any]], dict[str, Any]]]) -> dict[str, Any]:
    """Compile and invoke a chain of the given nodes over the real WorkflowState."""
    names = list(nodes)
    graph = StateGraph(WorkflowState)
    for name, fn in nodes.items():
        graph.add_node(name, fn)
    graph.add_edge(START, names[0])
    for source, target in zip(names, names[1:]):
        graph.add_edge(source, target)
    graph.add_edge(names[-1], END)
    return graph.compile().invoke(_initial_state())


# ── the carry ────────────────────────────────────────────────────────────────────────────


def test_the_carried_resolution_survives_a_nodes_rebuild():
    """What every node does: return a fresh RunMetadata naming a handful of fields."""

    def rebuild(state: dict[str, Any]) -> dict[str, Any]:
        return {
            "metadata": RunMetadata(
                workflow_id=state["workflow_id"],
                template_id=state["template_id"],
                status="running",
            )
        }

    def observe(state: dict[str, Any]) -> dict[str, Any]:
        seen = state["metadata"]
        return {
            "metadata": seen,
            "execution_result": {
                "llm_resolution": seen.llm_resolution,
                "workflow_id": seen.workflow_id,
                "template_id": seen.template_id,
            },
        }

    result = _run({"rebuild": rebuild, "observe": observe})
    observed = result["execution_result"]

    assert observed["llm_resolution"] == RESOLUTION, (
        "the resolution the run started with did not survive a node's fresh RunMetadata — "
        "the failure gate can name nobody without it"
    )
    assert observed["workflow_id"] == RUN_ID
    assert observed["template_id"] == TEMPLATE_ID


def test_the_gate_still_names_the_offender_after_a_nodes_rebuild():
    """Both halves: the sentence after the rebuild, and None when the carry is absent."""

    def rebuild(state: dict[str, Any]) -> dict[str, Any]:
        return {
            "metadata": RunMetadata(
                workflow_id=state["workflow_id"], template_id=state["template_id"]
            )
        }

    def ask_the_gate(state: dict[str, Any]) -> dict[str, Any]:
        return {
            "metadata": state["metadata"],
            "execution_result": {
                "statement": run_failure_statement(state["metadata"], ProviderError("boom"))
            },
        }

    result = _run({"rebuild": rebuild, "ask_the_gate": ask_the_gate})
    statement = result["execution_result"]["statement"]

    assert statement is not None, "the gate named nobody on a genuine provider failure"
    # The offender is named by the ONE renderer (model label + provider), so assert on the
    # identity it carries rather than on its prose: the statement is the sentence, and the
    # sentence must finger both halves of the carried resolution.
    assert "phi4" in statement.casefold() and "ollama" in statement.casefold(), statement
    assert "the provider reported" in statement, statement

    # The other direction, on the same inputs: with the resolution dropped (what replacement
    # semantics produced) the gate must name nobody rather than invent an offender.
    dropped = RunMetadata(workflow_id=RUN_ID, template_id=TEMPLATE_ID)
    assert run_failure_statement(dropped, ProviderError("boom")) is None


# ── the policy: verdicts still replace ───────────────────────────────────────────────────


def test_a_later_node_clears_an_earlier_verdict():
    """Replace semantics for the verdict fields — a stale `error` must not outlive a success.

    A bare merge would fail this: 15 of the 32 node-side builders name `status` and only the
    error paths name `error`, so a merge of everything would leave `error` set on a run whose
    last node succeeded.
    """

    def fail(state: dict[str, Any]) -> dict[str, Any]:
        return {
            "metadata": RunMetadata(
                workflow_id=state["workflow_id"],
                template_id=state["template_id"],
                status="error",
                error="the node failed",
            )
        }

    def succeed(state: dict[str, Any]) -> dict[str, Any]:
        return {
            "metadata": RunMetadata(
                workflow_id=state["workflow_id"],
                template_id=state["template_id"],
                status="running",
            )
        }

    metadata = _run({"fail": fail, "succeed": succeed})["metadata"]

    assert metadata.status == "running"
    assert metadata.error is None, "an earlier node's error outlived a later node's success"
    assert metadata.llm_resolution == RESOLUTION, "the verdict policy must not cost the carry"


def test_a_writer_that_names_a_carried_field_clears_it():
    """An explicit value wins over the carried one — the writer's own statement about the run."""

    def clear(state: dict[str, Any]) -> dict[str, Any]:
        return {
            "metadata": RunMetadata(
                workflow_id=state["workflow_id"],
                template_id=state["template_id"],
                llm_resolution=None,
            )
        }

    assert _run({"clear": clear})["metadata"].llm_resolution is None


# ── the reducer's edges ──────────────────────────────────────────────────────────────────


def test_the_reducer_stands_when_there_is_nothing_to_carry():
    """A non-metadata value on either side leaves the update in place (the pre-reducer path)."""
    update = RunMetadata(workflow_id=RUN_ID, template_id=TEMPLATE_ID)

    assert merge_run_metadata(None, update) is update
    assert merge_run_metadata({"status": "running"}, update) is update
    assert merge_run_metadata(update, {"status": "running"}) == {"status": "running"}


def test_an_identical_update_is_returned_unchanged():
    """No carried field is missing, so the reducer must not copy or invent anything."""
    update = RunMetadata(
        workflow_id=RUN_ID,
        template_id=TEMPLATE_ID,
        started_at="2026-10-07T00:00:00Z",
        config={"feeds": []},
        tags=["monitor"],
        trace_level="debug",
        llm_resolution=RESOLUTION,
    )
    carried = RunMetadata(workflow_id=RUN_ID, template_id=TEMPLATE_ID, llm_resolution=None)

    assert merge_run_metadata(carried, update) is update
