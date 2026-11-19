"""NODE GRADES — what a node's failure means for its RUN (ruled 2026-10-07).

Every node in this codebase catches its own failures and returns error state, because a
monitor must not die on a dead feed. The cost was that NOTHING reached the run: the node said
"error" inside the state, the graph ended normally, and the run was recorded `completed` — for
a genuine provider failure, with no name and no toast. Measured against the recorded history,
the run-level failure surface has never once fired for an LLM failure.

The grade is the missing declaration. It belongs to the NODE and answers one question: when
THIS node fails, is the failure the RUN's?

    tolerant     resilience IS the purpose (the monitor family). The failure is absorbed and
                 the run is left clean — no verdict is written onto the run's metadata at all.
    recoverable  the failure is absorbed but the run is MARKED: `status="error"` plus the one
                 statement. The record layer turns that into a completed-but-degraded run.
                 The default, for anything whose purpose is not the call itself.
    fatal        the call IS the node's purpose (a "verify this connection" node). The node
                 re-raises, so the run takes the EXISTING failure path — which names the
                 offender for free, because the frame still holds `initial_state.metadata`
                 with the resolution intact.

Two ways a node honours its grade:

- **`absorb(node, state, error)`** — the one call for the absorbING grades and the raise.
  Returns the metadata fields to write (`{}` for a tolerant node), or re-raises for a fatal
  one. In a catch:

      except Exception as e:
          verdict = absorb(plan_node, state, e)
          return {..., "metadata": RunMetadata(..., **verdict)}

- **Not marking the run at all** — the tolerant family's shape. A monitor keeps its per-item
  error handling in `execution_result` (that is data, not a verdict) and never touches
  `metadata.status`, which is why it needs no `absorb` call to stay clean. The declaration is
  still required, because the grade is what a reader and the tests read.

The per-item families that already build their own error state (`_error_state` in
file_clerk_nodes / context_indexer_nodes / boss_agent_nodes) mark the run `status="error"`
there — that IS the recoverable behaviour, so they keep their own builder and need no call.

The KIND supplies the default where a whole family shares one (`grade_for_kind`): the monitor
family is tolerant by construction, every other kind is `recoverable` with `fatal` declared
node by node. Grade the NODE, never infer it — a misclassification is a behaviour change: a
dead feed starts failing runs (a monitor graded fatal) or a failed run is recorded clean (a
fatal node graded tolerant).
"""

from __future__ import annotations

from typing import Any, Callable, Literal, Optional, TypeVar, cast

NodeGrade = Literal["tolerant", "recoverable", "fatal"]

#: What a node is when nobody says otherwise. Deliberately NOT `tolerant`: an undeclared node
#: that swallows an LLM failure should surface it as a degraded run, not hide it. The
#: tolerant families declare themselves.
DEFAULT_GRADE: NodeGrade = "recoverable"

_GRADES: tuple[NodeGrade, ...] = ("tolerant", "recoverable", "fatal")

#: Kinds whose nodes are tolerant BY CONSTRUCTION — a monitor exists to keep going when a
#: feed, an API or the summariser is down, so its failures are never the run's.
_TOLERANT_KINDS: frozenset[str] = frozenset({"monitor"})

_DECLARED_ATTR = "__node_grade__"

F = TypeVar("F", bound=Callable[..., Any])


def grade_for_kind(kind_name: Optional[str]) -> NodeGrade:
    """The grade a node of this kind gets when it declares none."""
    if kind_name is not None and kind_name in _TOLERANT_KINDS:
        return "tolerant"
    return DEFAULT_GRADE


def node_grade(grade: NodeGrade) -> Callable[[F], F]:
    """Declare a node's grade, on the node.

    A decorator rather than an entry elsewhere: the declaration sits beside the catch that
    honours it, and it survives the function being handed to a graph (the decorator returns
    the same object).

        @node_grade("fatal")
        def test_llm_connection_node(state): ...
    """
    if grade not in _GRADES:
        raise ValueError(f"unknown node grade {grade!r}; expected one of {_GRADES}")

    def decorate(fn: F) -> F:
        setattr(fn, _DECLARED_ATTR, grade)
        return fn

    return decorate


def grade_of(node: Any, *, kind: Optional[str] = None) -> NodeGrade:
    """This node's grade: what it declares, else its kind's default, else the default."""
    declared = getattr(node, _DECLARED_ATTR, None)
    if declared in _GRADES:
        return cast(NodeGrade, declared)
    return grade_for_kind(kind)


def _metadata_of(state: Any) -> Any:
    """The run's metadata from a state dict, defensively (a hand-built state may carry none)."""
    if isinstance(state, dict):
        return state.get("metadata")
    return getattr(state, "metadata", None)


def absorb(
    node: Any,
    state: Any,
    error: BaseException,
    *,
    error_text: Optional[str] = None,
    kind: Optional[str] = None,
) -> dict[str, Any]:
    """What an absorbing node writes onto the run for this failure — or RAISE for a fatal node.

    Returns the metadata verdict fields to splat into the node's error-state builder:

        fatal         never returns — re-raises `error` so the run's failure path fires
        tolerant      `{}` — the run is not marked (the node's own `execution_result` carries
                      the detail, which is data rather than a verdict)
        recoverable   `{"status": "error", "error": ..., "failure_statement": ...}`, where the
                      statement is the ONE wording from the run's carried resolution. It is
                      `None` when the failure never reached the provider layer, which is the
                      honest answer — the run is marked, nobody is fingered.

    `error_text` lets a node keep the message it already shows its reader (`"LLM connection
    test failed: …"`) while the verdict carries it; without it the exception's own text is used.
    """
    grade = grade_of(node, kind=kind)

    if grade == "fatal":
        # The RUN's failure, not the node's: re-raise. The exception object travels with its
        # traceback, so the frame sees the real failure and `run_failure_statement` can still
        # recognise the provider layer — a synthesized error could not.
        raise error

    if grade == "tolerant":
        return {}

    from ..utils.run_failure import run_failure_statement

    return {
        "status": "error",
        "error": error_text if error_text is not None else str(error),
        "failure_statement": run_failure_statement(_metadata_of(state), error),
    }
