"""The ONE place a call's output budget is decided (the token-limit arc, Phase B).

The study (`local/token-limits/study.md` §3) found **seven writers** of one
turn's `max_tokens`: the client's belief, the declared value, the reasoning
floor, the two executor caps, the deep pass's forced 4096, and a dead copy of
it. Nothing said which one was authoritative, and the logged number was not
the sent number — so every budget question asked from the log started from a
false premise.

This module is the resolver the rest of the arc hangs off. **In Phase B it
returns exactly today's values, path by path**, and Phase C is what makes
every writer call it: that ordering is deliberate, because a resolver landing
at the same moment as the behaviour change proves nothing. The characterization
table (`backend/tests/unit/test_output_budget_table.py`) pins the rows, so C's
diff can only be the rows someone meant to change.

Today's ladder (`path` names the run path, not the agent's type):

===========================  ===========================================
``PATH_DEFAULT``             the declared value (runtime override first),
                             then the reasoning floor.
``PATH_FAST``                the fast profile's policy constant — 512,
                             named and logged (C.2) — then the floor.
``PATH_PASS1``               the declared value: a first pass is not a
                             cheaper pass, and it was silently run on a
                             quarter budget until C.2 (D1).
``PATH_DEEP``                ``max(declared, 4096)`` — the conduit's deep
                             pass keeps a named minimum of its own and lets a
                             larger declaration through (C.3) — then the floor.
===========================  ===========================================

The ladder is now the one the arc ruled: the fast profile's policy constant, the
declared value for pass 1 and the ordinary turn, and the deep pass's minimum.
None of them can put a thinking driver below its floor — the deep pass used to
FORCE 4096 over both the declaration and the floor, which is what C.3 deleted.

**Where the number comes from (G-I's one slot):** the runtime override, else the agent's
declared ``llm_spec.max_output``, else ``FALLBACK_BUDGET``. The override is a session's
choice and the declaration is the agent's; the fallback is a default, and the log's
``reason`` names all three.

**The floor's trigger is the thinking CHAIN (F.3), and the name pattern is its last
resort.** `thinking_in_force()` takes the signal a caller resolved from the driver's own
record (the provider's claim, else the curated label —
`domain.providers.model_window.resolve_model_thinking`), then the agent's OWN
declaration (`llm_spec.thinking`), then `reasoning_support.is_reasoning_model`'s name
list for a driver nobody has recorded. Any one of them saying "this thinks" is enough:
a driver that reasons cannot be talked out of it by a row we hand-labelled — the live
case this phase answers (`inclusionai/ling-3.0-flash` catalogued `thinking: none` while
the provider publishes `default_enabled: true`).

``window`` and ``prompt_tokens`` together are **E.2's clamp**: the window is the
one limit allowed to LOWER a budget we chose (`roadmap.md` §2 — physics, not
policy), so when ``prompt + budget > window`` the budget is lowered to fit and the
reason is ``window_clamp``. It is applied LAST, after the path's policy and after
the reasoning floor: a thinking driver whose window cannot hold the floor is a
driver to replace, not a licence to exceed the window, and the clamp says so
loudly. With no window, or with no prompt estimate, **nothing is clamped** — a
missing measurement is not a limit (B.1's rule), which is what keeps an unrecorded
driver behaving exactly as it does today.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Mapping, MutableMapping, Optional, Sequence, Tuple

from app.domain.chat.token_budget import (
    TOKENS_PER_MESSAGE_OVERHEAD,
    estimate_tokens,
)
from app.services.cognitive_pipeline.reasoning_support import (
    REASONING_MAX_TOKENS_FLOOR,
    SOURCE_DECLARATION,
    SOURCE_NAME_PATTERN,
    ThinkingSignal,
    as_signal,
    is_reasoning_model,
    signal_from_level,
)

logger = logging.getLogger(__name__)

# The paths a budget is resolved for. The names are the run paths: the
# executor strategy for the first two, the pass number for the third, and the
# conduit's deep pass for the fourth.
PATH_DEFAULT = "default"
PATH_FAST = "fast"
PATH_PASS1 = "pass1"
PATH_DEEP = "deep"
PATHS = (PATH_DEFAULT, PATH_FAST, PATH_PASS1, PATH_DEEP)

# THE FAST PATH'S POLICY CONSTANT (C.2). `fast` answering briefly is a
# legitimate profile choice (D1), so its budget is a declared, named, logged
# constant instead of a silent `min(declared, 512)` that made the agent's own
# number advisory. The reasoning floor still applies after it.
FAST_POLICY_BUDGET = 512
# THE DEEP PASS'S MINIMUM (C.3). The conduit's deep pass is the better attempt,
# so it keeps a floor of its own — named and logged like the fast constant — and
# a declaration ABOVE it flows straight through (F.4's 8192 reaches the pass).
DEEP_MIN_BUDGET = 4096

# The number the router substitutes when NOTHING declares a budget
# (`request_kwargs.get("max_tokens", 4096)` at the cap and the floor).
FALLBACK_BUDGET = 4096

# THE EXECUTOR PATH'S OWN PASS-1 CAP (F-B). The chat path's 1024 cap died at C.2
# (D1); this copy survives because `/agent-chat` runs the executor rather than the
# resolver. It is NAMED here, not left as a literal in `executor.py`: it is the one
# remaining place a path decides a budget for itself — a declared exception with a
# test, not an accident.
EXECUTOR_PASS1_CAP = 1024

# The reasons — the sentence fragment that lands in the log line verbatim
# (`max_tokens_sent=… reason=…`). One per writer, so the log names who spoke.
REASON_DECLARED = "declared"
# RETIRED (G-I, 2026-09-25): `REASON_TYPE_DEFAULT` named the layer that read the
# agent's spec as a "type default" while `parameters.max_tokens` outranked it. With
# one declaration slot there is nothing for it to name: the spec IS the declaration.
REASON_OVERRIDE = "runtime_override"
REASON_NO_DECLARATION = "no_declared_budget"
REASON_THINKING_FLOOR = "thinking_floor"
# THE FLOOR'S SECOND REASON (F.3): the driver's reasoning is MANDATORY — the provider
# says it cannot be told not to think, so the floor is a FACT about the driver rather
# than a policy applied to a choice. Distinct from `thinking_floor` because the user's
# options differ: there is no effort to lower, only a driver to replace.
REASON_THINKING_MANDATORY = "thinking_mandatory"
REASON_FAST_POLICY = "fast_policy"
REASON_DEEP_MIN = "deep_min"
# THE WINDOW'S REASON (E.2) — the only lowering that is not a policy choice:
# `prompt + budget > window` and the driver cannot hold it. It is logged with the
# numbers it was clamped between, so the sent value stays explainable.
REASON_WINDOW_CLAMP = "window_clamp"

# The smallest output budget a clamp will send. A provider rejects `max_tokens=0`,
# and a prompt that alone exceeds the window is a driver to replace (E.3 warns at
# match time) — not a reason to send a number no API accepts.
WINDOW_CLAMP_FLOOR = 1

# ── THE LADDER (F.2, D3) — the per-class defaults, as code constants ────────────
# The seeded ladder (`roadmap.md` §1): the CLASS an agent belongs to, not the PATH a
# turn runs on. These are the numbers a package declares as its type default (F.1),
# the numbers F.4's bespoke row raises to, and the source the ceiling is derived
# from. Deliberately generous and deliberately unmeasured (D5): the running app, its
# log lines and its chat messages are what correct them.
TYPE_LESSER = "lesser"          # trivial agents, pseudo-agents, workflow nodes
TYPE_SHALLOW = "shallow"        # a row + a workspace, no memory pipeline (Bob's class — the BASE)
TYPE_DEEP = "deep"              # a workspace AND memory: the research class
TYPE_DEEP_LONG = "deep_long"    # the deep class's long-form top

TYPE_BUDGETS: Mapping[str, int] = {
    TYPE_LESSER: 4096,
    TYPE_SHALLOW: 8192,
    TYPE_DEEP: 16384,
    TYPE_DEEP_LONG: 24576,
}

# A driver that THINKS spends budget on reasoning before it writes a word (the
# ox-alpha incident), so the class DEFAULT is doubled for it. **It is a statement
# about a default, not a multiplier on a number someone declared** (F-A): a declared
# budget is floored at `REASONING_MAX_TOKENS_FLOOR` and is never silently doubled —
# raising a number the user typed is a surprise that needs its own reason string.
THINKING_MULTIPLIER = 2

# THE CEILING (D3) — DERIVED from the table, never typed a second time. It is what
# the table can actually PRODUCE, so it carries the thinking multiplier: a bound the
# system can legitimately exceed is not a bound. It bounds the budgets that can be
# STORED (the API's validation and the UI's input range); it is POLICY and not
# physics — a model's window is what clamps a call (E.2), and a provider's own cap
# can sit far above this (`space-bunny-alpha` publishes 524288).
BUDGET_CEILING = max(TYPE_BUDGETS.values()) * THINKING_MULTIPLIER


def type_default_budget(agent_type: str, thinking: bool = False) -> int:
    """The class default for an agent of this type.

    ``thinking`` doubles it (F-A): a driver that reasons spends budget before it
    answers, so its DEFAULT has to cover thinking plus answer. Callers that hold a
    DECLARED number must not come here — the declaration is the authority (D2).
    """
    try:
        budget = TYPE_BUDGETS[agent_type]
    except KeyError:
        raise ValueError(
            f"unknown agent type {agent_type!r} (expected one of {tuple(TYPE_BUDGETS)})"
        ) from None
    return budget * THINKING_MULTIPLIER if thinking else budget


def estimate_prompt_tokens(
    messages: Optional[Sequence[Any]] = None,
    tools: Optional[Sequence[Any]] = None,
) -> Optional[int]:
    """The size of the prompt about to go on the wire — what the window clamps against.

    Best-effort by design, and honest about being nothing at all: an empty/absent
    message list returns ``None``, which means **no clamp** (a missing measurement
    is not a limit). The tool schemas count, because they are the part of a prompt
    that grows without the conversation growing — a page of tool definitions is
    thousands of tokens on every call.

    Measured with the app's own estimator (`token_budget.estimate_tokens`:
    tiktoken when available, ``len // 4`` otherwise), so the clamp and the input
    trim disagree only by rounding.
    """
    if not messages:
        return None

    total = 0
    for message in messages:
        if isinstance(message, Mapping):
            content = message.get("content")
        else:
            content = getattr(message, "content", None)
        total += estimate_tokens(str(content or "")) + TOKENS_PER_MESSAGE_OVERHEAD

    if tools:
        try:
            total += estimate_tokens(json.dumps(list(tools), default=str))
        except (TypeError, ValueError):
            pass
    return total


def _as_budget(raw: Any) -> Optional[int]:
    """A stored budget as an int, or None when it is not a number at all."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    try:
        return int(raw)
    except (TypeError, ValueError):
        logger.warning(
            "output budget %r is not a number — treated as undeclared", raw
        )
        return None


def declared_output_budget(agent: Any) -> Optional[int]:
    """The agent's OWN declaration — `llm_spec.max_output`, the one declaration slot (G-I).

    The arc's original defect was a budget living in the wrong place and nobody
    able to see both numbers. The fix's last step (G-I) is that there is ONE place:
    the agent's own `llm_spec` — the contract it OWNS, copied from its package at
    adoption, editable through the API, and the only thing the resolver reads.

    Reads the agent row (or a plain `llm_spec` dict) and returns None when nothing
    declares a budget: "undeclared" is a real state, and the fallback default is the
    caller's business, not this function's.

    DEPRECATED(2026-09-25): the readers of `parameters.max_tokens` (a JSON blob the
    profile form used to edit) and of a bare `max_tokens` attribute were removed here.
    A request still carrying `parameters.max_tokens` is REFUSED — by the typed
    `AgentParameters` shape, which is permanent and is not what this note is about.

    THIS NOTE'S removal condition, measured 2026-09-25 and checkable in two commands:
    (1) `select count(*) from agents where parameters like '%max_tokens%'` and the same
    for `agent_templates` — both 0 of 4; (2) the grep for `parameters.max_tokens` /
    `maxTokens` across `backend/app` and `frontend/src` returns only COMMENTS that name
    the key as retired (this note, `domain/agents/schemas.py` ×2,
    `domain/runtime_config/services.py`, and three client comments). Remove the note when
    (2) comes back empty of even those — i.e. when nobody needs to be told.
    """
    if agent is None:
        return None

    spec: Any = getattr(agent, "llm_spec", None)
    if spec is None and isinstance(agent, Mapping):
        spec = agent.get("llm_spec")
    if isinstance(spec, Mapping):
        return _as_budget(spec.get("max_output"))
    return None


def declared_thinking(agent: Any) -> Optional[ThinkingSignal]:
    """The agent's OWN declaration — `llm_spec.thinking` (F.3).

    Read from the agent's spec rather than the package's live row for the same reason
    the type default is: adoption COPIES the contract, so a later package edit does not
    mutate an agent that already exists. A spec saying `none` (or saying nothing at
    all) returns ``None``, so the next source in the chain still speaks.
    """
    spec: Any = getattr(agent, "llm_spec", None)
    if spec is None and isinstance(agent, Mapping):
        spec = agent.get("llm_spec")
    if isinstance(spec, Mapping):
        return signal_from_level(spec.get("thinking"), SOURCE_DECLARATION)
    return None


def thinking_in_force(
    model: str, thinking: Any = None, agent: Any = None,
) -> ThinkingSignal:
    """The signal that APPLIES to this call, and where it came from (F.3).

    Three sources, strongest evidence first: what the caller resolved about the DRIVER
    (the provider's claim, else our curated label), the agent's OWN declaration, then
    the name-pattern list for a driver nobody has recorded. Any one of them saying
    "this thinks" is enough — a driver that reasons cannot be talked out of it by a
    silent row — and the MANDATORY fact is carried through from whichever source
    stated it, because it changes what the user can do (nothing).
    """
    given = as_signal(thinking)
    declared = declared_thinking(agent)
    by_pattern = is_reasoning_model(str(model or ""))
    if not (given.thinking or (declared is not None and declared.thinking) or by_pattern):
        return ThinkingSignal()
    if given.thinking:
        source = given.source
    elif declared is not None and declared.thinking:
        source = declared.source
    else:
        source = SOURCE_NAME_PATTERN
    return ThinkingSignal(thinking=True, mandatory=given.mandatory, source=source)


def floors_for(model: str, thinking: Any = None) -> bool:
    """Whether the reasoning floor applies to this call.

    F.3: the NAME PATTERN is the fallback now, not the trigger — the verified provider
    claim and the agent's own declaration speak first (`thinking_in_force`). Kept as
    the two-argument predicate because that is the question most callers are asking.
    """
    return thinking_in_force(model, thinking).thinking


def floor_budget(
    model: str, budget: int, thinking: Any = None, *, agent: Any = None,
) -> int:
    """The thinking floor applied to a number — the ONE application of the rule.

    ``resolve_output_budget`` applies the same rule and names the reason
    (`thinking_floor` / `thinking_mandatory`); a caller that already holds a budget and
    only needs the number — the executors, on the registry path `/agent-chat` runs —
    calls this one, so the floor cannot drift between the two surfaces (F-B).
    """
    if thinking_in_force(model, thinking, agent=agent).thinking and budget < REASONING_MAX_TOKENS_FLOOR:
        return REASONING_MAX_TOKENS_FLOOR
    return budget


def resolve_output_budget(
    agent: Any,
    model: str,
    thinking: Any = None,
    path: str = PATH_DEFAULT,
    window: Optional[int] = None,
    *,
    override: Optional[int] = None,
    prompt_tokens: Optional[int] = None,
) -> Tuple[int, str]:
    """The output budget for this call, and the reason it is that number.

    ``override`` is the per-session ``runtime_configs.max_tokens`` — writer #4,
    which D2 keeps ("the override stays, but routes through the resolver —
    never a bypass"). It is keyword-only and optional so the call shape stays
    the five settled arguments.

    ``thinking`` is what a caller resolved about the DRIVER — a
    `reasoning_support.ThinkingSignal` from the provider's claim, else the curated
    label (`domain.providers.model_window.resolve_model_thinking`), or a plain bool as
    before. ``None`` is the honest state for a caller with no database read: the
    agent's own declaration and then the name pattern speak instead (F.3).

    ``window`` and ``prompt_tokens`` are E.2's clamp (keyword-only for the same
    reason): physics, applied after every policy, and only when both numbers are
    known.

    Returns ``(budget, reason)``; ``reason`` is one of the REASON_* constants.
    """
    if path not in PATHS:
        raise ValueError(f"unknown output-budget path {path!r} (expected one of {PATHS})")

    declared = _as_budget(override)
    reason = REASON_OVERRIDE if declared is not None else ""
    if declared is None:
        # THE ONE DECLARATION SLOT (G-I): the agent's own `llm_spec.max_output`.
        # There is no second source to consult — the agent's class default arrives
        # by COPIES at adoption, and a package edit never mutates an agent that
        # already exists. A row that declares nothing gets the fallback, named as
        # one, rather than a class default guessed from a role field.
        declared = declared_output_budget(agent)
        reason = REASON_DECLARED
    if declared is None:
        # Nothing declared anywhere: the router's own fallback is the number that runs.
        declared = FALLBACK_BUDGET
        reason = REASON_NO_DECLARATION

    # THE DEEP PASS RAISES (C.3). It used to FORCE 4096 over BOTH the declaration
    # and the floor — which put a thinking driver below its own floor, the exact
    # failure the floor exists to prevent. Now it takes the larger of the
    # declaration and its own named minimum, and the floor below still has the
    # last word. A declaration above the minimum flows straight through.
    if path == PATH_DEEP and declared < DEEP_MIN_BUDGET:
        budget, reason = DEEP_MIN_BUDGET, REASON_DEEP_MIN
    # THE FAST PATH'S POLICY (C.2) — the constant IS the profile's promise, and
    # the log names it (`reason=fast_policy`). Pass 1 carries no policy of its
    # own: a first pass meant to lead somewhere must not run on a quarter of the
    # agent's declared budget (D1).
    elif path == PATH_FAST:
        budget, reason = FAST_POLICY_BUDGET, REASON_FAST_POLICY
    else:
        budget = declared

    # THE FLOOR, APPLIED AFTER THE PATH'S POLICY — which is why a thinking
    # driver on the fast path gets 16000 and not 512, and why the constant
    # alone never describes a reasoning turn.
    signal = thinking_in_force(model, thinking, agent=agent)
    if signal.thinking and budget < REASONING_MAX_TOKENS_FLOOR:
        budget = REASONING_MAX_TOKENS_FLOOR
        reason = (
            REASON_THINKING_MANDATORY if signal.mandatory else REASON_THINKING_FLOOR
        )

    # THE WINDOW, LAST (E.2). Physics outranks every policy above: a budget that
    # cannot fit beside the prompt is lowered to fit, whatever chose it — including
    # the floor, because a driver whose window cannot hold the floor is a driver to
    # replace (E.3 warns at match time) and NOT a licence to send more than the
    # window holds. `roadmap.md` §2: the window is the only limit allowed to lower a
    # declared budget, and the lowering is never silent.
    if window is not None and prompt_tokens is not None:
        allowance = int(window) - int(prompt_tokens)
        if budget > allowance:
            clamped = max(WINDOW_CLAMP_FLOOR, allowance)
            logger.warning(
                "🪟 WINDOW CLAMP model=%s window=%s prompt_tokens=%s "
                "budget=%s clamped=%s (reason=window_clamp) — the driver cannot "
                "hold the prompt beside this output budget; the budget is lowered "
                "to fit. A driver this small is what E.3 warns about at match time.",
                model, int(window), int(prompt_tokens), budget, clamped,
            )
            return int(clamped), REASON_WINDOW_CLAMP

    return int(budget), reason


def apply_output_budget(
    request_kwargs: MutableMapping[str, Any],
    agent: Any,
    model: str,
    path: str = PATH_DEFAULT,
    *,
    override: Optional[int] = None,
    thinking: Any = None,
    window: Optional[int] = None,
    prompt_tokens: Optional[int] = None,
    session_id: Optional[int] = None,
) -> Tuple[int, str]:
    """Decide this call's budget, WRITE it into the request, and log the line.

    The call every path makes (C.1): resolve → write `request_kwargs["max_tokens"]`
    → write the effective-budget line. One function, so a path cannot decide a
    number that is not the number the log reports — the mismatch that started
    the whole arc.

    On the DEFAULT path the number may only ever be the resolver's, so a request
    that already carries a different one means a second writer has reappeared:
    that is the one case worth shouting about, and it is shouted here. **A window
    clamp is not that case** — it is the resolver deciding, so it passes without
    the shout (the `window_clamp` warning above already said what happened).
    """
    previous = request_kwargs.get("max_tokens")
    budget, reason = resolve_output_budget(
        agent, model, thinking, path, window,
        override=override,
        prompt_tokens=prompt_tokens,
    )
    request_kwargs["max_tokens"] = budget

    if path == PATH_DEFAULT and previous is not None and reason != REASON_WINDOW_CLAMP:
        try:
            previous_number: Optional[int] = int(previous)
        except (TypeError, ValueError):
            previous_number = None
        if previous_number is not None and previous_number != budget:
            logger.warning(
                "⚠️  BUDGET OVERWRITTEN on the default path — the request "
                "carried %s and the resolver says %s (reason=%s). Nothing "
                "decides a default-path budget but the resolver: a second "
                "writer is back.",
                previous_number, budget, reason,
            )

    log_effective_budget(
        request_kwargs.get("max_tokens"),
        budget,
        declared_output_budget(agent),
        reason,
        path=path,
        model=model,
        session_id=session_id,
    )
    return budget, reason


def effective_budget_line(
    sent: Any,
    declared: Any,
    reason: str,
    path: str,
) -> str:
    """The log line B.4 replaces the misleading `parameters={'max_tokens': …}` with."""
    sent_text = "none" if sent is None else str(sent)
    declared_text = "none" if declared is None else str(declared)
    return (
        f"max_tokens_sent={sent_text} reason={reason or 'unknown'} "
        f"declared={declared_text} path={path}"
    )


def log_effective_budget(
    sent: Any,
    resolved: int,
    declared: Any,
    reason: str,
    *,
    path: str,
    model: Optional[str] = None,
    session_id: Optional[int] = None,
) -> str:
    """Write the effective-budget line, and SHOUT when the sent value differs.

    Phase B's acceptance test is "if a sent value differs after B, B is wrong",
    and a test can only prove it for the paths it exercises. Logging the
    comparison makes the same check run on every real turn.
    """
    line = effective_budget_line(sent, declared, reason, path)
    logger.info(
        "💰 EFFECTIVE OUTPUT BUDGET %s model=%s session=%s",
        line, model, session_id,
    )
    try:
        sent_number: Optional[int] = None if sent is None else int(sent)
    except (TypeError, ValueError):
        sent_number = None
    if sent_number is not None and sent_number != resolved:
        logger.warning(
            "⚠️  BUDGET MISMATCH — the resolver says %s but %s was sent "
            "(reason=%s path=%s). Phase B must not move a sent value: one of "
            "the two is wrong, and the characterization table is where to look.",
            resolved, sent_number, reason, path,
        )
    return line
