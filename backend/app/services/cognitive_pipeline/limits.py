"""The limit model — ONE place that judges a limit (the token-limit arc, Phase B).

Before this module the app had exactly one guard (the tool-call tracker) and
one implicit stop (the provider cutting a stream at `max_tokens`). The arc's
review found what that costs: a limit that lives in its own subsystem cannot
say *why* it fired, so a fired limit is indistinguishable from a bug, and
the next limit gets written as a third mechanism beside the first two.

`Limit` is the shape every quantity now shares (output tokens, provider calls,
tool calls, wall clock, cost, input tokens — `roadmap.md` §1), and
`check_limits()` is the only judge:

* **soft** — the user is told and nothing stops (`log + message`),
* **hard** — the turn is aborted and the user is told (`log + message + abort`).

Two rules are enforced here rather than left to review, because both were
broken in the code this replaces:

1. **Every limit names its reason.** The reason is the policy sentence that
   reaches the log line AND the user verbatim — a limit whose reason is empty
   cannot be constructed (`LimitDefinitionError`). A limit without a name is a
   silent clamp with extra steps.
2. **Never silent.** A verdict that is not `ok` carries the log line it wrote,
   and `check_limits()` writes it: `⚠️ LIMIT SOFT key=… value=… threshold=…
   reason=…` / `🚫 LIMIT HARD STOP key=… value=… reason=…`. The log is the
   instrument (D5: the running app corrects a wrong limit; a limit that does
   not report itself cannot be corrected).

The judgement is `value >= threshold` for both classes — the shape the tool
guard already had (`consecutive >= max` blocks, one below warns). An
unmeasurable quantity (the key is absent from the state) is skipped, logged at
DEBUG, and never treated as a breach: a missing measurement is not a limit.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# The kinds. SOFT is heard and survived; HARD stops the turn.
SOFT = "soft"
HARD = "hard"
KINDS = (SOFT, HARD)

# The scopes. CALL is judged per LLM call; TURN accumulates across a turn
# (both executor passes included).
CALL = "call"
TURN = "turn"
SCOPES = (CALL, TURN)

# The verdicts, worst first — the escalation ladder.
OK = "ok"
WARN = "warn"
STOP = "stop"


class LimitDefinitionError(ValueError):
    """A limit that cannot be judged — an unknown kind/scope, or no reason."""


@dataclass(frozen=True)
class Limit:
    """One policy number, with the sentence that explains it.

    ``key`` is the quantity measured (it must be the key the state carries —
    see `measure`); ``kind`` and ``scope`` are from the tuples above;
    ``threshold`` is the number the measurement is compared against;
    ``reason`` is the policy sentence, verbatim into the log and the user
    message.
    """

    key: str
    kind: str
    scope: str
    threshold: float
    reason: str

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise LimitDefinitionError(
                f"limit key={self.key!r}: unknown kind {self.kind!r} "
                f"(expected one of {KINDS})"
            )
        if self.scope not in SCOPES:
            raise LimitDefinitionError(
                f"limit key={self.key!r}: unknown scope {self.scope!r} "
                f"(expected one of {SCOPES})"
            )
        if self.threshold is None:
            raise LimitDefinitionError(
                f"limit key={self.key!r}: no threshold — a limit that judges "
                f"nothing is not a limit"
            )
        if not str(self.reason or "").strip():
            raise LimitDefinitionError(
                f"limit key={self.key!r}: no reason — every limit names why it "
                f"exists (the reason lands in the log line and the user message)"
            )

    @property
    def is_soft(self) -> bool:
        return self.kind == SOFT

    @property
    def is_hard(self) -> bool:
        return self.kind == HARD


@dataclass(frozen=True)
class LimitVerdict:
    """The judgement: ``ok``, or the one limit that fired.

    ``reason`` is the fired limit's reason (the user-facing sentence) and
    ``log_line`` is the line the judge wrote — both empty on ``ok``.
    """

    status: str = OK
    limit: Optional[Limit] = None
    value: Optional[float] = None
    reason: str = ""
    log_line: str = ""

    @property
    def ok(self) -> bool:
        return self.status == OK

    @property
    def warned(self) -> bool:
        return self.status == WARN

    @property
    def stopped(self) -> bool:
        return self.status == STOP


def number(value: Any) -> str:
    """A number as the log should print it — integers without a `.0`."""
    try:
        as_float = float(value)
    except (TypeError, ValueError):
        return str(value)
    return str(int(as_float)) if as_float == int(as_float) else str(as_float)


def measure(state: Any, key: str) -> Optional[float]:
    """The current value of ``key`` in ``state``, or None when unmeasurable.

    ``state`` is a mapping (``{"output_tokens": 1024}``) or any object
    carrying the quantity as an attribute — so the turn-accumulator Phase D
    builds and a plain dict-shaped per-call state both work.
    """
    if state is None:
        return None
    if isinstance(state, Mapping):
        value = state.get(key)
    else:
        value = getattr(state, key, None)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def limit_line(limit: Limit, value: Optional[float]) -> str:
    """The log line for a fired limit — the exact shape in `roadmap.md` §1."""
    if limit.kind == HARD:
        return (
            f"🚫 LIMIT HARD STOP key={limit.key} value={number(value)} "
            f"reason={limit.reason}"
        )
    return (
        f"⚠️ LIMIT SOFT key={limit.key} value={number(value)} "
        f"threshold={number(limit.threshold)} reason={limit.reason}"
    )


def check_limits(state: Any, limits: Sequence[Limit]) -> LimitVerdict:
    """Judge ``state`` against ``limits`` — the one place a limit is decided.

    A hard breach outranks a soft one (the plug protects the system, the
    warning protects the user's attention); within a class the FIRST limit in
    the given order that is breached wins, so the caller's ordering is the
    priority. The fired line is logged here (WARNING for soft, ERROR for hard)
    because a limit that fires silently is the failure this module exists to
    prevent.
    """
    hard_hit: Optional[tuple[Limit, float]] = None
    soft_hit: Optional[tuple[Limit, float]] = None

    for limit in limits:
        value = measure(state, limit.key)
        if value is None:
            logger.debug(
                "limit key=%s not in the state — not judged (no measurement)",
                limit.key,
            )
            continue
        if value < limit.threshold:
            continue
        if limit.is_hard:
            hard_hit = hard_hit or (limit, value)
        else:
            soft_hit = soft_hit or (limit, value)

    fired = hard_hit or soft_hit
    if fired is None:
        return LimitVerdict()

    limit, value = fired
    line = limit_line(limit, value)
    if limit.is_hard:
        logger.error(line)
        status = STOP
    else:
        logger.warning(line)
        status = WARN

    return LimitVerdict(
        status=status,
        limit=limit,
        value=value,
        reason=limit.reason,
        log_line=line,
    )


def limits_in_force(limits: Sequence[Limit]) -> str:
    """A one-line census of a limit set — for the log and the docs table (G.3)."""
    if not limits:
        return "limits: none"
    described = ", ".join(
        f"{limit.key}({limit.kind} {limit.scope} {number(limit.threshold)})"
        for limit in limits
    )
    return f"limits: {described}"

# ===========================================================================
# THE TURN'S SOFT LINES (the token-limit arc, Phase D.2)
# ===========================================================================
# `roadmap.md` §1's table, in the ONE place limits are defined — the guard's
# numbers live with the guard (`ToolCallTracker.limits_for()`), the turn's live
# here. SOFT means: the judge writes the line, the user is told, and NOTHING
# stops. The hard plugs are D.3's; the only hard stop armed today is the
# provider's own output cut (reported as `truncated=True`, never enforced here).
#
# **The `iterations` row is deliberately NOT armed.** §1 lists it (soft 5), but
# both loops already end at 5 and `provider_calls` counts the same events with a
# soft at 8 — an iterations soft would fire at the last iteration of a loop that
# is already finishing, i.e. a warning that arrives after the fact. Named
# redundant rather than armed (see the phase file's F3).
SOFT_PROVIDER_CALLS = 8
SOFT_TOOL_CALLS = 20
SOFT_WALL_CLOCK_S = 300
# The output soft is a FRACTION of the call's own budget: the budget IS the
# provider's hard stop, so the user should hear about the cut before it lands.
OUTPUT_SOFT_FRACTION = 0.9
# THE INPUT SOFT IS A FRACTION OF THE INPUT BUDGET (E.6, F4's ruling). It is judged
# against ONE CALL's prompt — the same trap D.2 found on the output side: the turn's
# accumulated `input_tokens` would fire on the second call of every multi-call turn.
# **The INPUT BUDGET, not the window**: the window can be 262144, and 80 % of a
# number the app never fills would never speak. The budget in force is what the
# assembly trims against, so a prompt that reaches it is a prompt whose fixed part
# (persona, tool schemas, the message) is eating the room history needs.
INPUT_SOFT_FRACTION = 0.8

# The limits the turn's policy DECLARES but that cannot be judged yet, each with
# why. D8's shape — an inactive limit SAYS it is inactive rather than passing
# silently — and the census is printed beside the armed set, so a reader of the
# log can tell "nothing is near a line" from "nothing is watching".
#
# `input_tokens` was the other row here until E: "the model's window is not derived
# yet". E.1 derives the window, so the input budget is a number and the soft is
# ARMED (`call_soft_limits(..., input_budget=…)`) — one inactive row is left.
TURN_LIMITS_INACTIVE: dict[str, str] = {
    "cost_usd": "pricing is unverified (D8)",
}


def turn_soft_limits() -> Tuple[Limit, ...]:
    """The TURN-scoped soft lines in force (they are judged against the account).

    Every reason says what happened AND that nothing stopped (D7's tone rule): a
    limit the user cannot act on because they cannot tell whether the turn was cut
    is the failure the arc exists to remove.
    """
    return (
        Limit(
            key="provider_calls",
            kind=SOFT,
            scope=TURN,
            threshold=SOFT_PROVIDER_CALLS,
            reason=(
                f"This turn has called the provider {SOFT_PROVIDER_CALLS} times — "
                f"unusual for a single answer. Nothing is blocked; the turn carries on."
            ),
        ),
        Limit(
            key="tool_calls",
            kind=SOFT,
            scope=TURN,
            threshold=SOFT_TOOL_CALLS,
            reason=(
                f"This turn has made {SOFT_TOOL_CALLS} tool calls — a lot for a "
                f"single answer. Nothing is blocked; the turn carries on."
            ),
        ),
        Limit(
            key="wall_clock_s",
            kind=SOFT,
            scope=TURN,
            threshold=SOFT_WALL_CLOCK_S,
            reason=(
                f"This answer has been running for {SOFT_WALL_CLOCK_S // 60} minutes — "
                f"longer than usual. Nothing is blocked; the turn carries on."
            ),
        ),
    )


def call_soft_limits(
    call_budget: Optional[int] = None,
    window: Optional[int] = None,
    input_budget: Optional[int] = None,
    composition: Optional[str] = None,
) -> Tuple[Limit, ...]:
    """The CALL-scoped soft lines: their state is ONE call, not the turn.

    Kept apart from `turn_soft_limits()` on purpose — judging a call's threshold
    against the turn's accumulated tokens would fire on the second call of every
    multi-call turn, which is a false alarm, not a limit.

    ``composition`` (D4) is the MEASURED composition of the prompt this call carried — the phrase
    ``prompt_accounting.describe_account()`` renders — and it goes into the input soft's sentence,
    so the note the user reads names the parts instead of only the crossing. ``None`` means the
    caller could not measure it (the declaration sites, a path with no messages in hand): the
    sentence then states what the budget counts and names no numbers, because a sentence that
    cannot measure must not assert (the defect this arc opened on).

    ``call_budget`` is the budget the call actually ran under
    (``request_kwargs["max_tokens"]``, written by the resolver), so the output
    soft varies by path — 460 on `fast` (512), 1800 on pass 1 (2000), 3686 on the
    deep pass (4096). **No budget, no limit**: a limit whose threshold cannot be
    named is not constructed at all (B.1's rule), and the caller logs that it was
    skipped.

    ``input_budget`` is the assembly ceiling in force for that call
    (`token_budget.input_budget_for()`, E.1) and arms the INPUT soft at
    `INPUT_SOFT_FRACTION` of it (E.6, F4). The judgement is against ONE call's
    prompt — the caller passes that call's `prompt_tokens`, and omits the key when
    the provider reported none (an unmeasured quantity is skipped, not treated as a
    breach). ``window`` is accepted and unused ON PURPOSE: the number the app trims
    against is the budget, and 80 % of a 262144 window would never speak.
    """
    limits: list[Limit] = []
    if call_budget:
        threshold = int(call_budget * OUTPUT_SOFT_FRACTION)
        limits.append(
            Limit(
                key="output_tokens",
                kind=SOFT,
                scope=CALL,
                threshold=threshold,
                reason=(
                    f"This answer is near its {int(call_budget)}-token output budget "
                    f"— it may be cut short. Nothing is blocked; the turn carries on."
                ),
            )
        )
    if input_budget:
        threshold = int(input_budget * INPUT_SOFT_FRACTION)
        limits.append(
            Limit(
                key="input_tokens",
                kind=SOFT,
                scope=CALL,
                threshold=threshold,
                reason=(
                    f"This prompt is near the {int(input_budget)}-token input budget in "
                    f"force, so history is being dropped to fit."
                    # THE MEASURED PARTS (D4). Present only when the caller measured them: the
                    # sentence reports, it does not estimate. This is the half of the arc's first
                    # complaint that could not be fixed by wording alone — the warning used to name
                    # a cause nobody had measured.
                    + (f" This call's prompt measured: {composition}." if composition else "")
                    + f" The count covers the system prompt, the tool schemas, the replayed "
                    f"thinking and the history it keeps; the tool results the turn adds after "
                    f"assembly are not re-judged. Nothing is blocked; the turn carries on."
                ),
            )
        )
    return tuple(limits)


def inactive_limits_note(
    inactive: Optional[Mapping[str, str]] = None,
) -> str:
    """The one-line census of the limits DECLARED but not armed, with their why."""
    declared = TURN_LIMITS_INACTIVE if inactive is None else inactive
    if not declared:
        return "limits inactive: none"
    return "limits inactive: " + ", ".join(
        f"{key} ({why})" for key, why in declared.items()
    )


# ===========================================================================
# THE TURN'S HARD PLUGS (the token-limit arc, Phase D.3)
# ===========================================================================
# `roadmap.md` §1's hard column — the two ceilings the TURN owns. A breach stops
# the turn: the judge writes `🚫 LIMIT HARD STOP …` (above), the turn logs
# `🚫 TURN STOPPED …`, the stream carries `event: error` (`limit_stop`) and the
# partial answer is finalised and saved (D7 (a), F2). **Never silence, never a
# lost turn** — a stopped turn is still a turn the user can read.
#
# Two hard rows are deliberately NOT armed here:
#   * the tool guard's own numbers (30/tool, 4 consecutive) are already hard, in
#     the guard — a copy here would fire a second plug on the same event;
#   * the provider's own output cut is already hard (the budget IS the cut) and
#     is reported as `truncated=True` on the frame and the row.
# The other two §1 rows are not plugs here: `cost_usd` (D8/D.5) and
# `input_tokens`. The input row is ARMED as a soft now (E.6) and deliberately has no
# hard: the trim and the window are what stop a prompt that cannot fit (a prompt
# that does not fit is CUT, not sent), so a plug here would be a second mechanism
# for one event. `cost_usd` stays declared in `TURN_LIMITS_INACTIVE` above, so the
# log says it is not watching.
HARD_PROVIDER_CALLS = 12
HARD_WALL_CLOCK_S = 600

# The way back in — the tool guard's own words, so a stopped turn reads the same
# however it was stopped.
CONTINUE_SENTENCE = "Say 'continue' and I'll carry on from what I have."

# How a fired plug was handled: ABORT cut the turn and kept what had already
# arrived (D7 (a)); FINISH let the turn end with the answer it had (D7 (b), F1)
# — a nearly-complete answer, or one whose turn had no further work to do, is
# worth keeping whole.
STOP_ABORT = "abort"
STOP_FINISH = "finish"

# What counts as "nearly complete" (F1): the last stream ended CLEANLY
# (`finish_reason=stop`) having used most of the budget it ran under. Its own
# number, deliberately NOT `OUTPUT_SOFT_FRACTION`: the soft warns the user, this
# throws away or keeps a paid-for answer, and one moving must not move the other.
NEARLY_COMPLETE_FRACTION = 0.9


def hard_turn_limits() -> Tuple[Limit, ...]:
    """The TURN-scoped HARD plugs — a breach stops the turn (D.3).

    Ordered as the tie-break runs: the first breached limit in this order is the
    one that stops the turn. Every reason says what happened AND its consequence
    (the hard half of D7's tone rule) — the user must be able to tell a stopped
    turn from a slow one without reading the log.
    """
    return (
        Limit(
            key="provider_calls",
            kind=HARD,
            scope=TURN,
            threshold=HARD_PROVIDER_CALLS,
            reason=(
                f"This turn reached {HARD_PROVIDER_CALLS} calls to the provider — "
                f"the ceiling for a single answer, so the turn stops here."
            ),
        ),
        Limit(
            key="wall_clock_s",
            kind=HARD,
            scope=TURN,
            threshold=HARD_WALL_CLOCK_S,
            reason=(
                f"This answer ran for {HARD_WALL_CLOCK_S // 60} minutes — the "
                f"ceiling for a single turn, so the turn stops here."
            ),
        ),
    )


def nearly_complete(
    finish_reason: Optional[str] = None,
    call_tokens: Optional[int] = None,
    call_budget: Optional[int] = None,
) -> bool:
    """Whether the last call left an answer worth keeping whole (D.4 (b), F1).

    True only when the stream ENDED CLEANLY — the provider said `stop`, not
    `length` (a cut answer) — and it used at least `NEARLY_COMPLETE_FRACTION` of
    the budget it ran under. A call with no budget, or with no numbers at all,
    is answered False: the criterion is not met by a measurement we do not have.
    """
    if str(finish_reason or "") != "stop":
        return False
    if not call_budget:
        return False
    try:
        return int(call_tokens or 0) >= int(call_budget * NEARLY_COMPLETE_FRACTION)
    except (TypeError, ValueError):
        return False


def stop_notice(limit: Limit, mode: str = STOP_ABORT, kept_chars: int = 1) -> str:
    """What a fired plug SAYS in the note on the message: the reason + the outcome.

    Both halves are load-bearing: the reason is the policy sentence (what was
    crossed), the outcome says what happened to the turn — the same note shape
    D.2 gave the soft lines, so a reader never has to guess which one fired.

    ``kept_chars`` is the abort's honesty: a plug can fire BEFORE any text
    arrived (a tool round is a provider call, and nothing of the answer existed
    yet), and "What had already arrived is kept" would then claim a partial that
    does not exist. Zero means exactly that, so the note says it.
    """
    if mode == STOP_FINISH:
        return (
            f"{limit.reason} The answer was kept whole — nothing further was started."
        )
    if kept_chars <= 0:
        return (
            f"{limit.reason} Nothing had arrived yet, so there was nothing to keep."
        )
    return f"{limit.reason} What had already arrived is kept."


def stop_message(limit: Limit, mode: str = STOP_ABORT, kept_chars: int = 1) -> str:
    """The user-facing message of a stopped turn (the SSE frame's ``message``, F2)."""
    return f"{stop_notice(limit, mode, kept_chars)} {CONTINUE_SENTENCE}"


def turn_stopped_line(
    limit: Limit,
    value: Any,
    *,
    partial_chars: int = 0,
    stage: str = "",
    mode: str = STOP_ABORT,
) -> str:
    """The line a stopped turn writes (F3) — the plug AND what became of the turn.

    The judge's own `🚫 LIMIT HARD STOP …` says WHICH limit fired; this says what
    the turn did about it (`partial` is what was kept, `mode` is abort/finish), so
    a runaway is legible from the log alone (D5).
    """
    return (
        f"🚫 TURN STOPPED key={limit.key} value={number(value)} "
        f"threshold={number(limit.threshold)} reason={limit.reason} "
        f"partial={int(partial_chars)} stage={stage} mode={mode}"
    )
