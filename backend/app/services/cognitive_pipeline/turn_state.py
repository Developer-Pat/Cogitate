"""A turn's spending, in ONE account (the token-limit arc, Phase D.1).

`limits.py` judges quantities; this module is where the quantities come from.
Before it a turn's cost was nowhere: the done frame's `tokenCount` was the LAST
stream's completion tokens (so a turn that made three provider calls reported one
of them), the tool calls were counted only for the guard, and the provider calls
were not counted at all — a loop that retried four times read exactly like a loop
that ran once.

`TurnState` is the accumulator `limits.py` anticipates ("the turn-accumulator
Phase D builds"): it carries the roadmap §1 keys as attributes — `input_tokens`,
`output_tokens`, `provider_calls`, `tool_calls`, `wall_clock_s`, `cost_usd` —
which is what `limits.measure()` reads, so D.2's limits judge this object with no
new plumbing.

Three rules, each learned from the arc so far:

1. **One owner per number.** Tool calls are the `ToolCallTracker`'s count; this
   object MIRRORS it (`observe_tool_calls(tracker)`) rather than keeping a second
   tally — and the guard's refusals and the failed calls ride that same single
   reading (the tool-reliability arc). `tools_offered` is the one number the
   tracker cannot own: only the TURN knows which calls carried a tools array, so
   that one is observed where the request is sent. Elapsed is measured from the
   turn's start, never summed from durations.
2. **Say where the tokens came from.** A provider that reports usage is a
   measurement; a provider that does not (whitespace or `0` on every chunk,
   which several local servers do) gets the app's existing estimate — and the
   line distinguishes them (`tokens=reported`, `estimated`, `mixed`). An invented
   number that reads as measured is the failure this arc exists to remove.
3. **Never silent, never fatal.** The account is logged at the end of the turn,
   including a turn that died or was closed mid-stream (the report is
   best-effort and cannot raise into the stream).

**The scope of the count is the turn's own loops** — the main tool loop and the
conduit's deep pass, plus the fallbacks that answer inside the same turn. The
auxiliary calls the turn also makes (conversation compaction in
`conversation_compactor.py`, the memory manager in `memory_manager.py`, both of
which call `litellm.acompletion` directly) are NOT counted: the roadmap's
thresholds (8 soft / 12 hard provider calls) are derived from the loops (5 + 5,
plus retries), so a number carrying something else would make them wrong. The
line says `scope=loop+deep` so no reader has to guess.

**D.3 adds one field to this same object: `hard_stop`** — the plug that stopped
the turn and HOW (aborted, with the partial answer kept; or let to finish because
the answer was already there). It rides the account because it is a fact about
this turn, and the note on the message reads it through `crossings`, exactly like
a soft crossing.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from app.services.cognitive_pipeline.limits import STOP_ABORT, stop_notice

logger = logging.getLogger(__name__)

# The keys — the roadmap §1 names, and the ones `limits.check_limits()` judges.
INPUT_TOKENS = "input_tokens"
OUTPUT_TOKENS = "output_tokens"
PROVIDER_CALLS = "provider_calls"
TOOL_CALLS = "tool_calls"
WALL_CLOCK = "wall_clock_s"
COST = "cost_usd"
KEYS = (INPUT_TOKENS, OUTPUT_TOKENS, PROVIDER_CALLS, TOOL_CALLS, WALL_CLOCK, COST)

# What the provider-call count covers (the module docstring's third rule).
SCOPE = "loop+deep"

# The path labels the accounting adds beside the budget paths (`fast`, `pass1`,
# `deep`, `default`): a RETRY (the wrapper's second and later attempts — counted,
# because the thresholds are about how often the turn reached a provider) and the
# in-turn FALLBACK that answers after a failed stream or a blocked tool loop.
RETRY_PATH = "retry"
FALLBACK_PATH = "fallback"

# Where the token numbers came from.
REPORTED = "reported"
ESTIMATED = "estimated"
MIXED = "mixed"
UNMEASURED = "none"


def tracker_tool_calls(tracker: Any) -> int:
    """How many tool calls the turn made, read from the ONE count that owns it.

    `ToolCallTracker.total_calls` is the tracker's own tally (its defaults are
    the policy, C.4). A turn without a tracker — the delegate and stub paths —
    has made none this object can see, which is 0, not an error.
    """
    return tracker_tool_counts(tracker)[CALLS]


# The keys of `tracker_tool_counts()` — the tracker's own numbers, as read.
CALLS = "calls"
BLOCKED = "blocked"
FAILURES = "failures"


def tracker_tool_counts(tracker: Any) -> Dict[str, int]:
    """The tracker's tool numbers as one dict — the ONE place they are read from it.

    Three quantities, each answering a different question (the tool-reliability arc):

    * `calls` — the calls that HAPPENED (the tracker's total; a call the guard
      refused is not among them);
    * `blocked` — the calls the GUARD REFUSED (emitted by the model, never run);
    * `failures` — the calls that ran and did not succeed.

    Read through the tracker's own summary rather than its attributes, so the
    numbers here and the ones a saved row carries can never be two readings of
    different fields. A tracker without the summary half (an older stub, a fake in
    a test) reports what it does have: the calls, with the rest at 0 — the honest
    answer for a thing that has no such counter.
    """
    if tracker is None:
        return {CALLS: 0, BLOCKED: 0, FAILURES: 0}
    summary = getattr(tracker, "get_summary", None)
    if not callable(summary):
        calls = tracker_tool_calls_legacy(tracker)
        return {CALLS: calls, BLOCKED: 0, FAILURES: 0}
    try:
        data = summary()
    except Exception:  # pragma: no cover — the account must not break a turn
        logger.exception("turn accounting: the tracker's summary raised")
        return {CALLS: 0, BLOCKED: 0, FAILURES: 0}
    if not isinstance(data, Mapping):
        data = {}
    return {
        CALLS: int(data.get("total_calls") or 0),
        BLOCKED: int(data.get("blocked") or 0),
        FAILURES: int(data.get("failures") or 0),
    }


def tracker_tool_calls_legacy(tracker: Any) -> int:
    """`total_calls` read straight off a tracker with no summary (the old shape)."""
    totals = getattr(tracker, "total_calls", None)
    if not isinstance(totals, Mapping):
        logger.debug(
            "turn accounting: tracker %r has no total_calls mapping — tool "
            "calls reported as 0", type(tracker).__name__,
        )
        return 0
    return sum(int(count) for count in totals.values())


def response_usage(response: Any) -> Optional[Tuple[int, int]]:
    """``(prompt_tokens, completion_tokens)`` from a NON-streamed response.

    Returns None when the response carries no usable usage — several servers do
    not report it at all — so the caller records the app's estimate and marks it
    as one, instead of filing a zero as a measurement.
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return None

    def field(name: str) -> Any:
        if isinstance(usage, Mapping):
            return usage.get(name)
        return getattr(usage, name, None)

    prompt, completion = field("prompt_tokens"), field("completion_tokens")
    if not prompt and not completion:
        return None
    try:
        return int(prompt or 0), int(completion or 0)
    except (TypeError, ValueError):
        logger.debug("turn accounting: unusable usage %r — treated as unreported", usage)
        return None


@dataclass
class TurnState:
    """One turn's spending — attach it to the chat context, observe as you go.

    Every field a limit can judge is a NAME from `KEYS`; `wall_clock_s` is a
    property (measured on read), and `tool_calls` is written only by
    `observe_tool_calls()`. `cost_usd` is present and stays 0.0 until D.5 arms
    the cost limit against real pricing — an inactive limit that reads a real
    zero is honest; one that reads an invented number is not.
    """

    scope: str = SCOPE
    started_at: float = field(default_factory=time.monotonic)
    input_tokens: int = 0
    output_tokens: int = 0
    provider_calls: int = 0
    tool_calls: int = 0
    cost_usd: float = 0.0
    # THE DENOMINATOR (the tool-reliability arc, F1): how many of this turn's
    # provider calls actually SENT a tools array. The one fact that separates "the
    # model was offered a tool and called none" from "there was nothing to call" —
    # both of which read as `tool_calls=0` before it. Counted at the send site,
    # because that is where the offered list exists; the answer pass deliberately
    # sends none and so contributes nothing.
    tools_offered: int = 0
    # The tracker's other two numbers, mirrored the same way `tool_calls` is
    # (rule 1): refusals the guard made, and calls that ran and failed. They are
    # READINGS, not judged quantities — deliberately NOT members of `KEYS`, so no
    # limit can be armed against a counter that exists to be reported.
    tool_calls_blocked: int = 0
    tool_failures: int = 0
    # Which path made each call (`pass1`, `deep`, `fallback`, `retry` …) — the
    # breakdown the observation rows (G.4) read, kept beside the total.
    calls_by_path: Dict[str, int] = field(default_factory=dict)
    # The provenance of the token numbers (rule 2).
    reported_calls: int = 0
    estimated_calls: int = 0
    # THE SOFT LINES THIS TURN HAS CROSSED (D.2). `warned_keys` is the toast's
    # guard — the user hears about a threshold ONCE per turn, not once per
    # iteration (the tool guard's own shape) — and `crossings` is the record the
    # note on the message carries, newest value per limit.
    warned_keys: set = field(default_factory=set)
    crossings: List[Dict[str, Any]] = field(default_factory=list)
    # THE HARD PLUG THAT STOPPED THIS TURN (D.3), or None. The crossing's shape
    # plus `mode` (abort/finish) — the first plug to fire is the one recorded,
    # because it is the one the turn acted on.
    hard_stop: Optional[Dict[str, Any]] = None
    # THE NUMBER THE WIRE ACTUALLY CARRIED (G-A ii) — {sent, declared, reason, path} of
    # the LAST request the resolver decided, or None when this turn made no call. The
    # declaration says what an agent WOULD send; this says what a turn DID. It is the
    # half that had no home: the effective-budget line lived only in the log, and the
    # log rotates — so a turn could not answer "what did you send?" after the fact.
    # Deliberately NOT a `KEYS` member: nothing is limited by a reading.
    budget: Optional[Dict[str, Any]] = None

    def observe_budget(
        self, sent: Any, declared: Any, reason: str, path: str
    ) -> Optional[Dict[str, Any]]:
        """Record the budget one request went out with — the LAST write wins.

        A turn can send several (a hybrid turn sends pass 1 and then the deep pass),
        and the number that matters to a reader is the one behind the answer they are
        looking at: the last. Each request's own line is in the log; this is the
        turn's summary, in the shape the row and the done frame carry.
        """
        if sent is None:
            return self.budget
        self.budget = {
            "sent": int(sent),
            "declared": int(declared) if declared is not None else None,
            "reason": reason or "",
            "path": path or "",
        }
        return self.budget

    @property
    def wall_clock_s(self) -> float:
        """Seconds since the turn started — measured, never accumulated."""
        return max(time.monotonic() - self.started_at, 0.0)

    def observe_provider_call(self, path: str = "") -> int:
        """One provider call has been made (or attempted) — count it.

        Called BEFORE the await, so an attempt that fails or times out is still
        a provider call: the roadmap's thresholds are about how often the turn
        reached a provider, and a retry storm is exactly what they exist for.
        """
        self.provider_calls += 1
        if path:
            self.calls_by_path[path] = self.calls_by_path.get(path, 0) + 1
        return self.provider_calls

    def observe_usage(
        self,
        prompt_tokens: Any = 0,
        completion_tokens: Any = 0,
        *,
        reported: bool = True,
    ) -> None:
        """Add one call's tokens, and record whether they were measured.

        ``reported=False`` is the caller saying "the provider gave me nothing;
        these numbers are the app's estimate" — the flag is what keeps the line
        from claiming a measurement it does not have.
        """
        self.input_tokens += max(int(prompt_tokens or 0), 0)
        self.output_tokens += max(int(completion_tokens or 0), 0)
        if reported:
            self.reported_calls += 1
        else:
            self.estimated_calls += 1

    def observe_tool_calls(self, tracker: Any) -> int:
        """Mirror the tracker's counts — the ONE tool account (rule 1).

        All three numbers come from the same reading, so the line's `tool_calls`
        and `tool_failures` can never disagree with the row's summary: they are the
        same fields, read once.
        """
        counts = tracker_tool_counts(tracker)
        self.tool_calls = counts[CALLS]
        self.tool_calls_blocked = counts[BLOCKED]
        self.tool_failures = counts[FAILURES]
        return self.tool_calls

    def observe_tools_offered(self, tools_sent: Any) -> int:
        """Count one provider call that was given a NON-EMPTY tools array (F1).

        Called at the send site with what the request actually carries, so the
        count describes the wire rather than an intention. An empty or absent list
        is a call where no tool was offered — the answer pass's withheld-tools
        call is exactly that, and it must NOT count here.
        """
        if tools_sent:
            self.tools_offered += 1
        return self.tools_offered

    def record_soft(self, verdict: Any) -> bool:
        """Record a fired soft limit; True when the user has not been told yet.

        The judge has already written the line (that is `check_limits`' job); this
        decides whether the turn ALSO tells the user, and keeps the crossing for
        the message's note. Nothing here stops the turn — the hard plug is D.3's.
        """
        limit = getattr(verdict, "limit", None)
        if limit is None:
            return False
        self.crossings.append({
            "key": limit.key,
            "value": getattr(verdict, "value", None),
            "threshold": limit.threshold,
            "reason": getattr(verdict, "reason", ""),
        })
        key = f"{limit.key}@{limit.threshold}"
        if key in self.warned_keys:
            return False
        self.warned_keys.add(key)
        return True

    def record_stop(
        self, verdict: Any, mode: str = STOP_ABORT, kept_chars: int = 1
    ) -> Optional[Dict[str, Any]]:
        """Record a fired HARD plug; the FIRST one is the one the turn acted on.

        Returns the record, or None when the verdict carries no limit (nothing to
        record). The crossing carries the outcome sentence (`stop_notice`), so the
        note on the message says what was crossed AND what happened to the turn —
        and no reader has to guess whether the answer was cut or kept whole.

        ``kept_chars`` is what the turn had when the plug fired, so an abort that
        kept NOTHING says that rather than claiming a partial it never had.
        """
        limit = getattr(verdict, "limit", None)
        if limit is None:
            return None
        record = {
            "key": limit.key,
            "value": getattr(verdict, "value", None),
            "threshold": limit.threshold,
            "mode": mode,
            "reason": stop_notice(limit, mode, kept_chars),
        }
        self.crossings.append(record)
        if self.hard_stop is None:
            self.hard_stop = record
        return record

    @property
    def stopped_by_limit(self) -> bool:
        """Whether a hard plug has stopped this turn (D.3).

        The turn is over as far as the pipeline is concerned: nothing further is
        started for it — no deep pass, no more tool rounds.
        """
        return self.hard_stop is not None

    def notice_text(self) -> str:
        """The crossings as ONE sentence — what the message's note shows (D.2)."""
        return notice_text(self.crossings)

    @property
    def token_source(self) -> str:
        """Whether the token numbers are measured, estimated or both."""
        if self.reported_calls and self.estimated_calls:
            return MIXED
        if self.reported_calls:
            return REPORTED
        if self.estimated_calls:
            return ESTIMATED
        return UNMEASURED

    def snapshot(self) -> Dict[str, Any]:
        """The state in the shape `limits.check_limits()` judges (roadmap §1).

        One call per check site: D.2's limits read this and nothing else, so a
        limit and the report can never be looking at two different numbers.
        """
        return {
            INPUT_TOKENS: self.input_tokens,
            OUTPUT_TOKENS: self.output_tokens,
            PROVIDER_CALLS: self.provider_calls,
            TOOL_CALLS: self.tool_calls,
            WALL_CLOCK: self.wall_clock_s,
            COST: self.cost_usd,
        }

    def paths_text(self) -> str:
        """The per-path breakdown, or `-` when no call named its path."""
        if not self.calls_by_path:
            return "-"
        return ",".join(
            f"{path}:{count}" for path, count in sorted(self.calls_by_path.items())
        )

    def account_line(
        self,
        session_id: Optional[Any] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> str:
        """The turn's totals as one greppable line (`TURN ACCOUNT`).

        THE TOOL STORY reads in one place (the tool-reliability arc): the
        DENOMINATOR first (`tools_offered`), then the calls that happened, the
        guard's refusals and the failures — so "was this model offered a tool, and
        what did it do with it" is answered from a single line.
        """
        return (
            f"TURN ACCOUNT session={session_id} model={model} provider={provider} "
            f"provider_calls={self.provider_calls} paths={self.paths_text()} "
            f"tools_offered={self.tools_offered} tool_calls={self.tool_calls} "
            f"tool_calls_blocked={self.tool_calls_blocked} "
            f"tool_failures={self.tool_failures} "
            f"tokens_in={self.input_tokens} "
            f"tokens_out={self.output_tokens} tokens={self.token_source} "
            f"elapsed_s={self.wall_clock_s:.1f} scope={self.scope}"
        )


def notice_text(crossings: Optional[Any]) -> str:
    """The unique crossing reasons joined — the note on the message (D.2).

    A turn can cross more than one line; the note says all of them once each, in
    the order they were crossed (each reason already says what happened and that
    nothing was blocked).
    """
    seen: List[str] = []
    for crossing in crossings or []:
        if not isinstance(crossing, Mapping):
            continue
        reason = str(crossing.get("reason") or "")
        if reason and reason not in seen:
            seen.append(reason)
    return " ".join(seen)


def report_turn_account(
    state: Optional[TurnState],
    *,
    session_id: Optional[Any] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None,
) -> str:
    """Log one turn's account — best-effort, and it never raises into the turn.

    A turn that dies mid-stream still reports what it spent (the caller reaches
    this from a `finally`), which is the only way a runaway becomes visible from
    the log rather than from a bill.
    """
    if state is None:
        return ""
    try:
        line = state.account_line(session_id=session_id, model=model, provider=provider)
    except Exception:  # pragma: no cover — the report must not break a turn
        logger.exception("turn accounting: could not build the account line")
        return ""
    logger.info("🧮 %s", line)
    return line
