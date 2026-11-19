"""
Tool Call Tracker.

Tracks tool calls to detect loops, prevent spam, and enforce rate limits.
Also tracks delegation chains for auditability across agent-to-agent hops.

**The guard is a LIMIT** (the token-limit arc, B.5): its two ceilings are
judged by `app.services.cognitive_pipeline.limits` — the one model the token
limits use — so a blocked call reports itself as `🚫 LIMIT HARD STOP key=…
value=… reason=…` and the warning one call before it as `⚠️ LIMIT SOFT …`.
The tracker still owns the NUMBERS (its defaults are the policy, C.4); it no
longer owns the judgement. The third check below (deduplication) is a NOTE,
not a limit: it never blocks, so it is not a ceiling.

**One stated nuance** — the only counter difference from the pre-limit code: a
call that is BLOCKED is judged as the repeat it would make (the message says
"called 4 consecutive times"), but it is NOT committed to the counter, so the
counter counts calls that happened. The ceilings, the order they are judged in,
the warning one call before a block and every sentence are unchanged.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.services.cognitive_pipeline.limits import (
    HARD,
    SOFT,
    TURN,
    Limit,
    check_limits,
)

logger = logging.getLogger(__name__)

# The quantities the guard's limits are measured under — the names the
# limit model's state carries (and the roadmap's limit table uses).

# `tool_calls`: how many times THIS tool has been called in the turn.
TOOL_CALLS_KEY = "tool_calls"
# `consecutive_tool_calls`: how many times it has been called in a row with the
# same arguments (the loop detector).
CONSECUTIVE_KEY = "consecutive_tool_calls"

@dataclass
class ToolCallRecord:
    """Record of a single tool call."""
    tool_name: str
    arguments: Dict[str, Any]
    timestamp: datetime
    iteration: int
    success: bool = True
    error: Optional[str] = None
    # THE CLASS OF THE FAILURE (the tool-reliability arc, F2): the executor's own
    # label (`ValidationError`, `ToolNotFound`, …) or a handler's declared one
    # (`not_found`, `missing_argument`, …). Recorded SEPARATELY from the message
    # because the count is grouped by it — the free text is for a reader, this is
    # for the tally. `None` means the call did not name a class (either it
    # succeeded, or a handler refused without one).
    error_type: Optional[str] = None

    def matches(self, other: "ToolCallRecord", ignore_args: bool = False) -> bool:
        """Check if this call matches another (same tool and optionally args)."""
        if self.tool_name != other.tool_name:
            return False
        if ignore_args:
            return True
        return self.arguments == other.arguments

class ToolCallTracker:
    """
    Tracks tool calls to detect loops and prevent spam.

    Features:
        - Detects repeated tool calls with same arguments
        - Enforces maximum consecutive calls per tool
        - Tracks call history for debugging
        - Provides warnings before enforcing limits

    Usage:
        tracker = ToolCallTracker(max_consecutive_calls=4)
        
        # Before executing tool
        if not tracker.should_execute("datetime", {"operation": "now"}):
            logger.warning("Tool call blocked - rate limit exceeded")
            return ToolExecutionResult(success=False, error="Rate limit exceeded")
        
        # After executing tool
        tracker.record_call("datetime", {"operation": "now"}, success=True)
    """

    def __init__(
        self,
        max_consecutive_calls: int = 4,
        dedup_window_seconds: int = 30,
        max_total_calls_per_tool: int = 30,
    ):
        """
        Initialize tracker.

        Args:
            max_consecutive_calls: Max same tool+args calls before blocking.

                RAISED 2 -> 4 (2026-09-10). THE VERIFY PATTERN COLLIDED WITH
                THE SPAM GUARD: read a file, write it, read it back to
                confirm the write — two identical reads in a row — and the
                guard blocked the second as a repeat. A reporter doing
                exactly what this system asks (verify before reporting) had
                her turn killed mid-job: "All 1 tool calls blocked -
                breaking loop", then a text-only reply she could not act
                from. The guard exists to stop a STUCK loop, not a careful
                agent. Four consecutive identical calls is still spam.

            dedup_window_seconds: Time window for deduplication (default 30s)
            max_total_calls_per_tool: Max total calls per tool per session.

                RAISED 10 -> 30 (same incident, same reason): verifying a
                workspace means reading what is there — the reporter hit 12
                file-info calls taking inventory and was cut off. Thirty is
                still a ceiling; ten was a tripwire on ordinary work.
        """
        self.max_consecutive_calls = max_consecutive_calls
        self.dedup_window = timedelta(seconds=dedup_window_seconds)
        self.max_total_calls = max_total_calls_per_tool

        # Call history: list of all calls in order
        self.call_history: List[ToolCallRecord] = []

        # Consecutive call counter: tool_name -> count
        self.consecutive_counts: Dict[str, int] = defaultdict(int)

        # Last call per tool
        self.last_call: Dict[str, ToolCallRecord] = {}

        # Total calls per tool
        self.total_calls: Dict[str, int] = defaultdict(int)

        # THE REFUSALS THIS GUARD MADE (the tool-reliability arc, F4). A blocked
        # call is NOT a call that happened — nothing is committed to the counters
        # above (see the module docstring's nuance) — so the refusal is counted
        # BESIDE them instead. Without it a turn the guard killed reads, in every
        # number the app has, exactly like a turn that never touched a tool.
        self.blocked_calls: int = 0
        self.blocked_by_tool: Dict[str, int] = defaultdict(int)

    def limits_for(self, tool_name: str, consecutive: int) -> Tuple[Limit, ...]:
        """This tool's ceilings as limits, in the order the guard judged them.

        ``consecutive`` is the repeat count INCLUDING the call being judged
        (`should_execute` passes it, because "would this call make it the
        fourth?" is the question). The numbers come from this tracker's own
        thresholds; the sentences are the guard's existing copy, which is what
        the reason field is for — it reaches the log line and the turn's
        message verbatim.
        """
        total = self.total_calls[tool_name]
        return (
            Limit(
                key=TOOL_CALLS_KEY,
                kind=HARD,
                scope=TURN,
                threshold=self.max_total_calls,
                reason=(
                    f"Tool '{tool_name}' has been called {total} times. "
                    f"Maximum ({self.max_total_calls}) reached. Breaking loop."
                ),
            ),
            # The warning one call before the block — the guard has always
            # warned before it plugs, and that is what makes it a soft line.
            Limit(
                key=CONSECUTIVE_KEY,
                kind=SOFT,
                scope=TURN,
                threshold=max(self.max_consecutive_calls - 1, 1),
                reason=(
                    f"Tool '{tool_name}' called {consecutive} times consecutively "
                    f"with the same arguments. One more call will block."
                ),
            ),
            Limit(
                key=CONSECUTIVE_KEY,
                kind=HARD,
                scope=TURN,
                threshold=self.max_consecutive_calls,
                reason=(
                    f"Tool '{tool_name}' called {consecutive} consecutive times with "
                    f"same arguments. Maximum ({self.max_consecutive_calls}) reached. "
                    f"Breaking loop to prevent spam."
                ),
            ),
        )

    def should_execute(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        iteration: int,
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Check if tool call should be executed.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
            iteration: Current iteration number

        Returns:
            Tuple of (should_execute, warning_message, error_message)
            - (True, None, None)    = OK to execute
            - (True, warning, None) = Allow, but emit warning (one more call will block)
            - (False, None, error)  = Block execution

            The warning and the error are the fired LIMIT's reason (B.5), so the
            sentence the turn is told with and the sentence in the log line are
            the same one.
        """
        now = datetime.now()
        record = ToolCallRecord(
            tool_name=tool_name,
            arguments=arguments,
            timestamp=now,
            iteration=iteration,
        )

        # THE LIMITS (B.5, the token-limit arc): the guard's two ceilings are
        # judged by the ONE limit model (`limits.py`), so its verdicts are
        # limit verdicts — `⚠️ LIMIT SOFT …` one call before a block, `🚫 LIMIT
        # HARD STOP …` at it — instead of a private subsystem's own messages.
        # The numbers still come from THIS tracker's thresholds (C.4: its
        # default IS the policy), and the sentences the turn is told with are
        # the ones the guard always used (they are the limits' reasons).
        last = self.last_call.get(tool_name)
        is_repeat = bool(last and last.matches(record, ignore_args=False))
        # The measurement is the count AFTER this call: a repeat is judged as
        # the repeat it would make. Nothing is committed until the call passes,
        # so a blocked call leaves the counters untouched (the guard's own rule).
        consecutive = self.consecutive_counts[tool_name] + (1 if is_repeat else 0)
        verdict = check_limits(
            {
                TOOL_CALLS_KEY: self.total_calls[tool_name],
                CONSECUTIVE_KEY: consecutive,
            },
            self.limits_for(tool_name, consecutive),
        )
        if verdict.stopped:
            # THE REFUSAL IS COUNTED HERE — this IS the guard, and both loops
            # reach it through this one method, so neither can forget (F4). The
            # call itself stays uncommitted to the counters above: "calls that
            # happened" keeps the meaning the turn's own messages quote.
            self.blocked_calls += 1
            self.blocked_by_tool[tool_name] += 1
            logger.error(f"   Arguments: {arguments}")
            return (False, None, verdict.reason)
        if is_repeat:
            self.consecutive_counts[tool_name] = consecutive
        if verdict.warned:
            return (True, verdict.reason, None)

        # Check 3: Deduplication within time window
        for prev in reversed(self.call_history[-10:]):  # Check last 10 calls
            if (
                prev.matches(record, ignore_args=False)
                and (now - prev.timestamp) < self.dedup_window
            ):
                # Same tool+args within dedup window
                logger.warning(
                    f"⚠️  DEDUP: Tool '{tool_name}' called again within "
                    f"{self.dedup_window.seconds}s window. This may indicate a loop."
                )
                break

        # Reset consecutive count if different tool/args
        if last and not last.matches(record, ignore_args=False):
            self.consecutive_counts[tool_name] = 1
        elif not last:
            self.consecutive_counts[tool_name] = 1

        return (True, None, None)

    def record_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        iteration: int,
        success: bool = True,
        error: Optional[str] = None,
        error_type: Optional[str] = None,
    ) -> None:
        """
        Record a tool call after execution.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
            iteration: Iteration number
            success: Whether call succeeded
            error: Error message if failed
            error_type: The failure's CLASS (the executor's label or a handler's
                declared one) — grouped in the summary, so a count can say WHAT
                went wrong rather than only how often. The record keeps it beside
                the free-text message, which no tally should parse.
        """
        record = ToolCallRecord(
            tool_name=tool_name,
            arguments=arguments,
            timestamp=datetime.now(),
            iteration=iteration,
            success=success,
            error=error,
            error_type=error_type,
        )

        self.call_history.append(record)
        self.last_call[tool_name] = record
        self.total_calls[tool_name] += 1

        logger.debug(
            f"📊 Tool call recorded: {tool_name} (total: {self.total_calls[tool_name]}, "
            f"consecutive: {self.consecutive_counts[tool_name]})"
        )

    def get_recent_calls(self, limit: int = 10) -> List[ToolCallRecord]:
        """Get most recent tool calls."""
        return self.call_history[-limit:]

    def get_call_count(self, tool_name: str) -> int:
        """Get total calls for a tool."""
        return self.total_calls[tool_name]

    def reset(self) -> None:
        """Reset all tracking data."""
        self.call_history.clear()
        self.consecutive_counts.clear()
        self.last_call.clear()
        self.total_calls.clear()

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of tool call activity — the turn's tool numbers, in one shape.

        THE RELIABILITY HALF (the tool-reliability arc, F1/F2/F4/F5) rides here:
        `attempts` is every call the model EMITTED (the ones that happened plus the
        ones the guard refused), `failures`/`failures_by_type` say how many did not
        succeed and of what class, and `blocked` says how often the guard said no.
        The DENOMINATOR is not here — it is the turn's (`tools_offered` in
        `TurnState`), because only the turn knows whether a tool was offered at all.
        A failure whose class nobody named is counted in `failures_unnamed`, so
        `sum(failures_by_type.values()) + failures_unnamed == failures` always
        holds: a reader can check the tally instead of trusting it.
        """
        total_calls = sum(self.total_calls.values())
        failures = [r for r in self.call_history if not r.success]
        by_type: Dict[str, int] = defaultdict(int)
        unnamed = 0
        for record in failures:
            if record.error_type:
                by_type[record.error_type] += 1
            else:
                unnamed += 1
        return {
            "total_calls": total_calls,
            "attempts": total_calls + self.blocked_calls,
            "blocked": self.blocked_calls,
            "blocked_by_tool": dict(self.blocked_by_tool),
            "failures": len(failures),
            "failures_by_type": dict(by_type),
            "failures_unnamed": unnamed,
            "calls_by_tool": dict(self.total_calls),
            "consecutive_counts": dict(self.consecutive_counts),
            "recent_calls": [
                {
                    "tool": r.tool_name,
                    "args": r.arguments,
                    "success": r.success,
                    "error": r.error,
                    "error_type": r.error_type,
                }
                for r in self.get_recent_calls(5)
            ],
        }

@dataclass
class DelegationHop:
    """
    Record of a single delegation hop in a chain.

    Each hop represents one agent delegating a task to another agent
    within a traceable chain identified by a unique trace_id.
    """
    trace_id: str
    source_agent_name: str
    source_agent_id: int
    target_agent_id: int
    depth: int
    task_preview: str
    timestamp: datetime
    success: Optional[bool] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None
    result_preview: Optional[str] = None

