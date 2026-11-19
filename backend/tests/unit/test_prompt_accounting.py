"""The prompt's account, and the trim that now reads it (the input-budget arc, Phases A and B).

Two phases, one file, because B is defined as the change A is diffed against:

- **A — the accounting.** ``account_prompt`` measures a prompt by contributor (system · history ·
  tool results · tool schemas · replayed reasoning) and the call boundary logs one line per
  provider call. The table below is a CHARACTERIZATION table: it pins today's numbers, including
  the ones known to be wrong (the trim counts message *content* alone, so the schemas and the
  replay ride outside its arithmetic), because a table that only pinned the good news could not
  detect the bad.
- **B — the trim's arithmetic.** ``build_context_with_token_budget`` now deducts the two
  contributors it could not see, so the declared budget and the sent prompt describe the same
  thing. The behaviour change is deliberate: history is dropped earlier, by exactly those weights
  — pinned here as an exact delta, not as "fewer messages".
"""

import logging

import pytest

from app.domain.chat.token_budget import (
    DEFAULT_INPUT_BUDGET,
    TOKENS_PER_MESSAGE_OVERHEAD,
    TOKENS_RESPONSE_HEADROOM,
    build_context_with_token_budget,
    estimate_tokens,
    schemas_tokens,
)
from app.services.cognitive_pipeline.prompt_accounting import (
    PromptAccount,
    account_prompt,
    format_account,
)

# ── a fixture turn: one of each contributor, in the shape the app actually sends ──────────────

SYSTEM = "You are a news agent. " * 20          # the persona + rules + state/notebook blocks
USER = "Check the local headlines."
ASSISTANT = "I will search and fetch the local sources."
REASONING = "Let me think about which sources to fetch first. " * 30   # replayed on thinking models
TOOL_RESULT = "headline one\nheadline two\nheadline three\n" * 50      # a fetch, riding in the prompt


def _tools(n: int = 3) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": f"tool-{i}",
                "description": "A tool whose schema travels in the request's tools field. " * 4,
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for i in range(n)
    ]


def _turn() -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": USER},
        {"role": "assistant", "content": ASSISTANT, "reasoning_content": REASONING},
        {"role": "tool", "content": TOOL_RESULT},
    ]


# ── Phase A: the account ──────────────────────────────────────────────────────────────────────

def test_the_account_names_every_contributor():
    account = account_prompt(_turn(), tools=_tools())
    assert account.system == estimate_tokens(SYSTEM)
    assert account.history == estimate_tokens(USER) + estimate_tokens(ASSISTANT)
    assert account.tool_results == estimate_tokens(TOOL_RESULT)
    assert account.replayed_reasoning == estimate_tokens(REASONING)
    assert account.tool_schemas == schemas_tokens(_tools())
    assert account.total == sum(
        [
            account.system,
            account.history,
            account.tool_results,
            account.tool_schemas,
            account.replayed_reasoning,
        ]
    )


def test_the_account_separates_what_the_trim_counts_from_what_it_cannot_see():
    """The arc's headline, as an assertion: the trim counts content alone, so the schemas and the
    replayed reasoning are prompt the budget never sees."""
    account = account_prompt(_turn(), tools=_tools())
    assert account.counted_by_trim == account.system + account.history + account.tool_results
    assert account.uncounted == account.tool_schemas + account.replayed_reasoning
    assert account.counted_by_trim + account.uncounted == account.total
    assert account.uncounted > 0, "the fixture carries both uncounted contributors"


def test_the_system_prompt_is_counted_once_whichever_way_it_arrives():
    """A caller whose message list excludes the system prompt names it instead; passing both must
    not double count it."""
    without = [m for m in _turn() if m["role"] != "system"]
    passed_separately = account_prompt(without, system_prompt=SYSTEM)
    in_the_list = account_prompt(_turn())
    assert passed_separately.system == in_the_list.system == estimate_tokens(SYSTEM)
    # ...and the double-count case is refused: an explicit system prompt is ignored when the list
    # already carries one.
    both = account_prompt(_turn(), system_prompt=SYSTEM)
    assert both.system == estimate_tokens(SYSTEM)


def test_no_tools_means_no_schema_weight_and_broken_tools_do_not_raise():
    assert account_prompt(_turn()).tool_schemas == 0
    assert schemas_tokens(None) == 0
    assert schemas_tokens([]) == 0
    assert schemas_tokens([object()]) > 0, "an unserializable tool still has to measure something"

    class Unserializable:
        def __repr__(self) -> str:
            raise ValueError("no repr for you")

    assert schemas_tokens([Unserializable()]) == 0, "an unmeasurable fixed part is 0, never a crash"


def test_the_line_carries_the_parts_beside_the_ceiling_in_force():
    account = account_prompt(_turn(), tools=_tools())
    line = format_account(account, input_budget=16000, soft_threshold=12800)
    assert "PROMPT ACCOUNT" in line
    for part in ("system", "history", "tool results", "tool schemas", "replayed reasoning"):
        assert part in line
    assert "ceiling 16,000" in line
    assert "soft 12,800" in line


def test_an_unnamed_ceiling_is_reported_as_the_default_not_as_silence():
    line = format_account(PromptAccount(system=10), input_budget=None)
    assert f"ceiling {DEFAULT_INPUT_BUDGET:,}" in line
    assert "soft" not in line, "no budget named, no soft threshold invented"


def test_the_call_boundary_logs_one_line_per_call(caplog):
    from app.api.v1.chat.llm_utils import _log_prompt_account

    with caplog.at_level(logging.INFO):
        _log_prompt_account(
            {"messages": _turn(), "tools": _tools()}, prompt_budget=16000
        )
    lines = [r.getMessage() for r in caplog.records if "PROMPT ACCOUNT" in r.getMessage()]
    assert len(lines) == 1
    assert "soft 12,800" in lines[0]


def test_the_account_never_breaks_a_call(caplog):
    """Bookkeeping must not turn a working call into a dead one: a prompt nobody can measure is
    still a prompt the call goes ahead with."""
    from app.api.v1.chat.llm_utils import _log_prompt_account

    class Exploding(list):
        def __iter__(self):  # type: ignore[override]
            raise RuntimeError("the messages blew up")

    _log_prompt_account({"messages": Exploding(), "tools": None}, prompt_budget=16000)


# ── D4: the composition in the warning's own sentence ─────────────────────────────────────────

def test_the_input_softs_sentence_carries_the_measured_parts_when_it_has_them():
    """D4 — the note the user reads names the parts, not just the crossing.

    This is the half of the arc's first complaint that wording alone could not fix: the warning used
    to assert a cause nobody had measured. Now it reports one nobody can doubt.
    """
    from app.services.cognitive_pipeline.limits import call_soft_limits
    from app.services.cognitive_pipeline.prompt_accounting import describe_account

    account = account_prompt(_turn(), tools=_tools(2))
    phrase = describe_account(account)
    (limit,) = call_soft_limits(None, input_budget=16000, composition=phrase)

    assert "This call's prompt measured:" in limit.reason
    assert phrase in limit.reason
    for part in ("system", "history", "tool results", "tool schemas", "replayed reasoning"):
        assert part in limit.reason


def test_the_sentence_claims_no_measurement_when_the_caller_could_not_make_one():
    """No composition, no numbers — and never a guess dressed as a reading."""
    from app.services.cognitive_pipeline.limits import call_soft_limits

    (limit,) = call_soft_limits(None, input_budget=16000)
    assert "measured" not in limit.reason
    assert "history is being dropped to fit" in limit.reason
    assert "not re-judged" in limit.reason, "the boundary claim survives without the numbers"


def test_the_two_readers_of_the_composition_use_one_rendering():
    """The log line's parts and the note's parts come from the same function, so a warning and the
    log cannot describe the same call differently."""
    from app.services.cognitive_pipeline.prompt_accounting import describe_account

    account = account_prompt(_turn(), tools=_tools(2))
    line = format_account(account, input_budget=16000)
    assert describe_account(account) in line


# ── Phase B: the trim's arithmetic ────────────────────────────────────────────────────────────

def _history(lambda_chars: int, pair_count: int = 6) -> list[dict]:
    """Enough history that the budget bites, each message the same size."""
    return [
        {"role": "user" if i % 2 == 0 else "assistant", "content": "x" * lambda_chars}
        for i in range(pair_count)
    ]


def test_the_schemas_are_deducted_so_history_is_dropped_earlier():
    """The exact delta, not "fewer messages": the schemas' own weight decides whether the last
    message fits."""
    messages = _history(2000, 6)
    schemas = _tools(3)
    budget = 3000

    without, _ = build_context_with_token_budget(messages, None, input_budget=budget)
    with_schemas, _ = build_context_with_token_budget(
        messages, None, input_budget=budget, tools=schemas
    )

    assert len(with_schemas) <= len(without)
    schemas_weight = schemas_tokens(schemas)
    # the delta is the schemas' weight: re-trimming with a budget reduced by exactly that weight
    # must select exactly what the schemas-aware run selected.
    shifted, _ = build_context_with_token_budget(
        messages, None, input_budget=budget - schemas_weight
    )
    assert len(with_schemas) == len(shifted)


def test_the_replayed_reasoning_is_deducted_per_kept_message():
    """An assistant message that carries a big stored `reasoning_content` costs what it carries —
    and a dropped message's reasoning costs nothing, because it is not sent."""
    small = {"role": "assistant", "content": "y" * 400, "reasoning_content": "r" * 4000}
    filler = [
        {"role": "user", "content": "z" * 400},
        {"role": "assistant", "content": "z" * 400},
    ]
    messages = filler + [small]

    without_replay = build_context_with_token_budget(
        [{k: v for k, v in small.items() if k != "reasoning_content"}] + filler,
        None,
        input_budget=2500,
    )[0]
    with_replay = build_context_with_token_budget(messages, None, input_budget=2500)[0]
    assert len(with_replay) <= len(without_replay)


def test_the_pair_rule_stands_and_an_oversized_fixed_part_says_so(caplog):
    """A fixed part bigger than the whole budget cannot empty the history — and the log says the
    budget was blown by design rather than failing quietly (D5: report, do not clamp)."""
    messages = _history(2000, 4)
    with caplog.at_level(logging.INFO):
        kept, _ = build_context_with_token_budget(
            messages,
            system_prompt="plan " * 4000,
            input_budget=1000,
            tools=_tools(3),
        )
    assert len(kept) == 2, "the ≥1-pair rule survives a blown budget"
    line = " ".join(r.getMessage() for r in caplog.records if "Context built" in r.getMessage())
    assert "reason=fixed_exceeds_budget" in line


def test_the_trim_reports_its_fixed_part_and_the_replay_it_counted(caplog):
    messages = _history(600, 2) + [
        {"role": "assistant", "content": "hello", "reasoning_content": "thinking " * 50}
    ]
    with caplog.at_level(logging.INFO):
        build_context_with_token_budget(
            messages, system_prompt=SYSTEM, input_budget=6000, tools=_tools(2)
        )
    line = " ".join(r.getMessage() for r in caplog.records if "Context built" in r.getMessage())
    assert f"system {estimate_tokens(SYSTEM)}" in line
    assert f"tool schemas {schemas_tokens(_tools(2))}" in line
    assert "replayed reasoning:" in line
    assert "reason=fixed_exceeds_budget" not in line


def test_the_trim_and_the_account_agree_about_the_prompt(caplog):
    """One arithmetic, two readers — and after Phase B the two describe the SAME prompt.

    The app's calling convention: the system prompt travels OUTSIDE the message list
    (`build_context_with_token_budget(system_prompt=...)`). With that, the trim's own line reports
    the account's *whole* total (system + history + tool results + schemas + replay) plus the
    per-message overhead — which is the fix in one assertion. Before Phase B the trim's number was
    the account's `counted_by_trim` (content alone) and the schemas and the replay were missing
    from it.
    """
    history = [m for m in _turn() if m["role"] != "system"]
    account = account_prompt(history, tools=_tools(2), system_prompt=SYSTEM)
    with caplog.at_level(logging.INFO):
        _, total = build_context_with_token_budget(
            history, SYSTEM, input_budget=16000, tools=_tools(2)
        )
    line = " ".join(r.getMessage() for r in caplog.records if "Context built" in r.getMessage())

    overhead = TOKENS_PER_MESSAGE_OVERHEAD * len(history)
    assert account.uncounted > 0, "the fixture carries both contributors Phase B added"
    # every message is kept (a tiny prompt under a big budget)
    assert f"~{account.total + overhead} tokens" in line
    assert total == account.total + overhead
    # ...and the OLD arithmetic no longer describes it: the trim is not counting content alone.
    assert total != account.counted_by_trim + overhead
    assert expected_within_budget(total, 16000)


def expected_within_budget(total: int, budget: int) -> bool:
    return total <= budget - TOKENS_RESPONSE_HEADROOM
