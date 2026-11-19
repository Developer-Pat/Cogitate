"""The INPUT side's first tests — the assembly ceiling and the model's window (E.1).

The arc characterized the OUTPUT side from Phase B onward
(`tests/unit/test_output_budget_table.py`) and never touched the input side:
`grep -rl build_context_with_token_budget backend/tests/` returned **nothing**
before this file. Three properties are what matter, and all three are about the
ceiling not quietly becoming a different thing:

1. an unknown window changes nothing (roadmap §2.4 — never clamp blindly);
2. a LARGE window changes nothing (the window is a ceiling over the constant, not
   a new basis for it — the phase's F2 ruling, and why this phase cannot raise a
   prompt's size or cost on a driver that can hold the constant);
3. a window too SMALL lowers the ceiling, and can lower it to zero when the
   driver's own output budget consumes the whole window.

The fourth property is the trim itself: history is dropped to fit the ceiling, and
one pair always survives so the model still has something to work from.
"""

from __future__ import annotations

from app.domain.chat.token_budget import (
    DEFAULT_INPUT_BUDGET,
    DEFAULT_MAX_CONTEXT_TOKENS,
    build_context_with_token_budget,
    input_budget_for,
)


# ── the ceiling ───────────────────────────────────────────────────────────────

def test_an_unknown_window_leaves_the_constant_alone():
    """§2.4: a driver nobody has recorded must not be clamped blindly."""
    assert input_budget_for(None, 8192) == DEFAULT_INPUT_BUDGET
    assert input_budget_for(None, None) == DEFAULT_INPUT_BUDGET


def test_a_large_window_does_not_raise_the_ceiling():
    """The window is a CEILING, never a new basis (F2).

    The working driver's cached window is 262144; the assembly stays at 16000, so
    this phase changes no prompt size, no input cost and no compaction trigger on
    a driver that can hold the constant.
    """
    assert input_budget_for(262144, 8192) == DEFAULT_INPUT_BUDGET
    assert input_budget_for(DEFAULT_INPUT_BUDGET, 0) == DEFAULT_INPUT_BUDGET


def test_a_small_window_lowers_the_ceiling():
    """A driver too small for the constant pulls it down to what it can hold."""
    assert input_budget_for(8192, 2000) == 6192
    assert input_budget_for(16384, 4096) == 12288


def test_a_window_consumed_by_the_output_budget_is_zero():
    """Zero is a statement, not a crash: this driver has no room for history.

    (The caller still sends the system prompt and the user's message; the trim only
    selects history, and it always keeps one pair.)
    """
    assert input_budget_for(8192, 8192) == 0
    assert input_budget_for(4096, 8192) == 0


def test_a_junk_window_falls_back_to_the_constant():
    """A window that is not a number is no window at all."""
    # Deliberately the wrong type: the guard exists because a value can arrive from
    # a database column that is not what its declaration claims.
    assert input_budget_for("not-a-number", 2000) == DEFAULT_INPUT_BUDGET  # type: ignore[arg-type]


def test_the_deprecated_alias_is_the_same_number():
    """The old name read as "the model's context window" — it never was one."""
    assert DEFAULT_MAX_CONTEXT_TOKENS == DEFAULT_INPUT_BUDGET


# ── the trim ──────────────────────────────────────────────────────────────────

def _history(pairs: int, chars: int = 4000) -> list[dict]:
    """`pairs` user/assistant turns, each big enough to matter (~1000 tokens)."""
    out: list[dict] = []
    for i in range(pairs):
        out.append({"role": "user", "content": f"question {i} " + "x" * chars})
        out.append({"role": "assistant", "content": f"answer {i} " + "y" * chars})
    return out


def test_a_small_ceiling_trims_more_history_than_a_large_one():
    history = _history(3)

    small, small_tokens = build_context_with_token_budget(history, "system", input_budget=2000)
    large, large_tokens = build_context_with_token_budget(history, "system", input_budget=60000)

    assert len(large) == len(history)          # room for everything
    assert len(small) < len(large)             # the small driver keeps less
    assert small_tokens < large_tokens


def test_the_trim_always_keeps_one_pair():
    """Even a zero ceiling leaves the model one pair — the trim's own floor."""
    selected, _ = build_context_with_token_budget(_history(3), "system", input_budget=0)

    assert len(selected) == 2
    assert selected[0]["role"] == "user" and selected[1]["role"] == "assistant"


def test_an_absent_budget_is_the_constant():
    """`None` keeps today's behaviour — the caller had no window to report."""
    history = _history(2)

    absent = build_context_with_token_budget(history, "system")
    explicit = build_context_with_token_budget(
        history, "system", input_budget=DEFAULT_INPUT_BUDGET
    )

    assert absent == explicit


def test_the_trim_says_what_it_dropped(caplog):
    """E.1b — never a silent cut: the line names what was kept and what was not.

    The old line reported only what SURVIVED ("N messages"), so a turn that lost
    most of its history looked exactly like one that lost none.
    """
    import logging

    with caplog.at_level(logging.INFO, logger="app.domain.chat.token_budget"):
        build_context_with_token_budget(_history(3), "system", input_budget=2000)

    assert "2/6 messages" in caplog.text
    assert "dropped: 4" in caplog.text
    assert "input budget: 2000" in caplog.text
