"""G.3 — the numbers table in the dev note comes from the CODE, not from memory.

`wiki/dev-notes/agents/agent-design-guidelines.md` states the budget and limit numbers
a designer reads before sizing an agent. Numbers copied into prose drift silently —
every constant below has moved at least once — so the table is pinned to the constants
it describes: move a threshold and this test names the row the note still gets wrong,
instead of leaving a confident page behind.

It reads the SOURCE tree (the wiki is a source artifact, not an installation one), the
same way `test_page_map_sync.py` reads the generated page map — through the locator,
never by counting `..` climbs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.api.v1.chat.tool_call_tracker import ToolCallTracker
from app.core.config import Paths
from app.services.cognitive_pipeline import limits, output_budget, reasoning_support

NOTE = (
    Path(str(Paths.root)) / "wiki" / "dev-notes" / "agents" / "agent-design-guidelines.md"
)


def _rows(text: str) -> dict[str, str]:
    """The note's number table as {label: row}, header and separator skipped."""
    rows: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or cells[0] in ("What", "") or set(cells[0]) <= {"-"}:
            continue
        rows[cells[0]] = line
    return rows


@pytest.fixture(scope="module")
def table() -> dict[str, str]:
    assert NOTE.exists(), f"the design note moved — this test reads it by path: {NOTE}"
    rows = _rows(NOTE.read_text(encoding="utf-8"))
    assert rows, "the note has no numbers table"
    return rows


def _assert_row(table: dict[str, str], label: str, *values: str) -> None:
    assert label in table, (
        f"the note's numbers table has no `{label}` row — the reader loses that number"
    )
    for value in values:
        assert value in table[label], (
            f"`{label}`: the note says {table[label]!r}, the code says {value!r}"
        )


@pytest.mark.parametrize(
    "label,value",
    (
        ("The fast profile's budget", output_budget.FAST_POLICY_BUDGET),
        ("The deep pass's minimum", output_budget.DEEP_MIN_BUDGET),
        ("Undeclared fallback", output_budget.FALLBACK_BUDGET),
        ("Thinking floor", reasoning_support.REASONING_MAX_TOKENS_FLOOR),
    ),
    ids=("fast", "deep_min", "fallback", "thinking_floor"),
)
def test_the_resolver_numbers_are_the_ones_the_code_holds(table, label, value):
    _assert_row(table, label, str(value))


def test_the_turn_limits_are_the_ones_the_code_holds(table):
    _assert_row(
        table, "Provider calls",
        str(limits.SOFT_PROVIDER_CALLS), str(limits.HARD_PROVIDER_CALLS),
    )
    _assert_row(table, "Tool calls", str(limits.SOFT_TOOL_CALLS))
    _assert_row(
        table, "Wall clock",
        str(limits.SOFT_WALL_CLOCK_S), str(limits.HARD_WALL_CLOCK_S),
    )


def test_the_output_soft_is_stated_as_the_fraction_it_is(table):
    fraction = limits.OUTPUT_SOFT_FRACTION
    assert f"{fraction:.0%}" in "".join(table.values()) or "90%" in table["Output soft (a fraction of the call's budget)"], (
        f"the output soft is {fraction} of the call's budget and the note does not say so"
    )


def test_the_input_soft_is_stated_as_the_fraction_it_is(table):
    """E.6: 80 % of the input budget in force — a fraction, so it must read as one."""
    fraction = limits.INPUT_SOFT_FRACTION
    assert f"{fraction:.0%}" in table["Input soft (a fraction of the input budget)"], (
        f"the input soft is {fraction} of the input budget and the note does not say so"
    )


def test_the_input_budget_is_the_constant_the_code_holds(table):
    """E.1: the assembly ceiling — the number that is NOT the model's window."""
    from app.domain.chat.token_budget import DEFAULT_INPUT_BUDGET

    _assert_row(table, "The input budget", str(DEFAULT_INPUT_BUDGET))


@pytest.mark.parametrize(
    "label,value",
    (
        ("The lesser class — trivial agents, pseudo-agents, workflow nodes",
         output_budget.TYPE_BUDGETS[output_budget.TYPE_LESSER]),
        ("The shallow class — a row and a workspace, no memory (the base)",
         output_budget.TYPE_BUDGETS[output_budget.TYPE_SHALLOW]),
        ("The deep class — a workspace and memory",
         output_budget.TYPE_BUDGETS[output_budget.TYPE_DEEP]),
        ("The deep class — a workspace and memory",
         output_budget.TYPE_BUDGETS[output_budget.TYPE_DEEP_LONG]),
        ("A thinking driver's class DEFAULT (never a declared number)",
         output_budget.THINKING_MULTIPLIER),
        ("The budget ceiling — DERIVED from the table, never typed",
         output_budget.BUDGET_CEILING),
    ),
    ids=("lesser", "shallow", "deep", "deep_long", "thinking_multiplier", "ceiling"),
)
def test_the_ladder_and_its_derived_ceiling_are_the_ones_the_code_holds(table, label, value):
    """F.2: the classes are new numbers in the note, and the ceiling is derived.

    The ceiling has no literal to drift from — it is `max(table) × multiplier` — so
    this row is the check that the note states the number the code computes.
    """
    _assert_row(table, label, str(value))


def test_the_timeouts_and_the_retry_policy_are_the_config_services(table):
    """The turn's waits and its retry policy have ONE home (gap L, stage 3).

    These were bare literals at their call sites — a 300 s stream timeout, a 30 s direct answer, a
    120 s delegate (twice) and a retry pair in `llm_utils` that no page named. The retry policy is
    what makes the `provider_calls` line reachable at all: one call can be three attempts.
    """
    from app.services.cognitive_pipeline import turn_config

    _assert_row(table, "The stream call's timeout", str(int(turn_config.STREAM_TIMEOUT_S)))
    _assert_row(table, "The direct answer's timeout", str(int(turn_config.ANSWER_TIMEOUT_S)))
    _assert_row(table, "The delegate's HTTP timeout", str(int(turn_config.DELEGATE_TIMEOUT_S)))
    _assert_row(
        table, "The delegate's own call timeout", str(int(turn_config.DELEGATE_CALL_TIMEOUT_S))
    )
    _assert_row(
        table, "A rate-limited call's retries",
        str(turn_config.RETRY_ATTEMPTS), str(turn_config.RETRY_DELAY_S),
    )


def test_the_guard_numbers_are_the_tracker_s_own_defaults(table):
    """The tracker's thresholds ARE the policy — the note must not carry its own copy."""
    tracker = ToolCallTracker()
    _assert_row(
        table,
        "One tool, same arguments, in a row",
        str(tracker.max_consecutive_calls - 1),  # the warning one below the block
        str(tracker.max_consecutive_calls),
    )
    _assert_row(table, "One tool, in total", str(tracker.max_total_calls))
    _assert_row(
        table, "The guard's dedup window", str(int(tracker.dedup_window.total_seconds()))
    )


def test_the_tool_loops_rounds_are_the_config_services(table):
    """The loop's cap has ONE home, so the note names it rather than a literal.

    It used to be two bare literals in the router (`max_iterations = 5` and the deep pass's
    `range(5)`): a reader could not tell whether they were meant to match, and nothing pinned
    either one.
    """
    from app.services.cognitive_pipeline import turn_config

    _assert_row(table, "The tool loop's rounds", str(turn_config.LOOP_ROUNDS))
    assert turn_config.loop_rounds() == turn_config.LOOP_ROUNDS, (
        "the accessor and the constant disagree — call sites read the accessor"
    )


def test_the_inactive_limits_are_named_as_inactive(table):
    assert "Declared inactive" in table, "the note does not say which limits are not watching"
    for key in limits.TURN_LIMITS_INACTIVE:
        assert key in table["Declared inactive"], (
            f"`{key}` is declared inactive in {limits.__name__} and the note omits it"
        )
