"""The turn's tweak points — ONE place they are declared and read (gap L, Stage 1).

What belongs here, and what does not
------------------------------------
This is the home for the numbers that shape a turn's WORK and are **judged by nothing**:

* the tool loop's rounds (both loops),
* and, as the later stages land, the timeouts a turn waits under, the retry policy of a
  provider call, and the tool guard's own ceilings.

Three neighbours already own their kind of number, and nothing here replaces them:

* a **budget** (what a call may spend) lives in ``output_budget.py`` — declared per class,
  per agent, overridable per session, resolved in one place;
* a **limit** (a quantity that is JUDGED, with the sentence it tells the user) lives in
  ``limits.py`` — a limit with no reason cannot even be constructed;
* a **path** lives in ``Paths`` (``app/core/config.py``).

The loop's cap is deliberately NOT a limit: nothing is judged against it and nothing stops —
it ends a tool-heavy turn normally. That distinction is the reason this module exists instead
of a fourth row in ``limits.py``.

Why these are reached through FUNCTION CALLS, not bare constants
---------------------------------------------------------------
So the SOURCE behind a number can change without a single call site moving. Today every
accessor returns a code default; the banked successor (config service — the census is
``local/tool-loop/limits-and-tweak-points.md``) makes them read Settings, a per-agent row or
a session override, and the loops, the guard and the call sites stay exactly as they are.
This is the shape ``Paths`` already has for paths: one place resolves, everybody imports it,
and the argument for it is the failure of the opposite — a number typed twice drifts, and the
drift is silent because both copies read as authoritative. The same module is also what makes
the moved numbers documentable: the numbers table in
``wiki/dev-notes/agents/agent-design-guidelines.md`` names a constant's home and
``tests/unit/test_budget_docs_table.py`` pins the table to the code.
"""

from __future__ import annotations

# THE TOOL LOOP'S ROUNDS. One number for BOTH loops — the main tool loop and the conduit's deep
# pass. They ran as two separate bare literals (``max_iterations = 5`` and ``range(5)``) in one
# function, which is how one policy became two knobs nobody owned: a reader could not tell whether
# they were meant to match, and a change to one silently left the other behind.
#
# What the number is NOT: a limit. No line is judged against it and nothing is stopped — the loop
# ends, and the turn says what it did with what it collected (the stand-in sentence, or the answer
# pass that exists so a turn is not stopped one call short of its deliverable).
LOOP_ROUNDS = 5


def loop_rounds() -> int:
    """How many rounds a turn's tool loop runs — the main loop and the deep pass alike.

    Read as a call so the source can change behind it (see the module docstring). If the two loops
    ever genuinely need different numbers, that is a SECOND function here with its reason — never a
    second literal at a call site.
    """
    return LOOP_ROUNDS


# THE TIMEOUTS a turn waits under. They are NOT limits: nothing is judged against them, nothing
# stops and nobody is told — each bounds ONE wait so a turn cannot hang forever. They live here
# because they are the other half of "how long may this take": the wall-clock LIMIT (`limits.py`)
# says when a turn is too long, these say when a single call has waited too long.
STREAM_TIMEOUT_S = 300.0
#   The chat turn's streamed provider call. 300 s because a reasoning driver can think for
#   20-140 s+ before its first token; 60 s killed every mid-plan run.
ANSWER_TIMEOUT_S = 30.0
#   The direct, non-streamed answer the turn falls back to when the tool path failed or every tool
#   call was blocked. Short on purpose: it is a recovery, and a recovery that hangs is worse than
#   no answer.
DELEGATE_TIMEOUT_S = 120.0
#   The HTTP call the conduit makes to this app's own delegate endpoint.
DELEGATE_CALL_TIMEOUT_S = 120.0
#   The delegate endpoint's OWN provider call (non-streamed, tools intact).

# THE RETRY POLICY of one provider call: the attempts a rate-limited call gets, and the base delay
# of its linear back-off (`delay × attempt`). It is what makes the turn's HARD `provider_calls` line
# reachable at all — one call can be three attempts — and until now it was a pair of constants in
# `llm_utils.py` that no doc named.
RETRY_ATTEMPTS = 3
RETRY_DELAY_S = 2


def stream_timeout_s() -> float:
    """How long the chat turn's streamed provider call may wait (seconds)."""
    return STREAM_TIMEOUT_S


def answer_timeout_s() -> float:
    """How long the direct, non-streamed answer may wait (seconds)."""
    return ANSWER_TIMEOUT_S


def delegate_timeout_s() -> float:
    """How long the conduit's HTTP call to the delegate endpoint may wait (seconds)."""
    return DELEGATE_TIMEOUT_S


def delegate_call_timeout_s() -> float:
    """How long the delegate endpoint's own provider call may wait (seconds)."""
    return DELEGATE_CALL_TIMEOUT_S


def retry_attempts() -> int:
    """How many attempts one rate-limited provider call gets (the first one included)."""
    return RETRY_ATTEMPTS


def retry_delay_s() -> int:
    """The base delay between those attempts — the back-off is `delay × attempt`."""
    return RETRY_DELAY_S
