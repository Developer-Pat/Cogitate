"""
Sequential Thinking Tool — Ephemeral Reasoning Scratchpad for the system manager.

Provides a ``SequentialThinkingTool`` that lets the system manager maintain a structured,
session-scoped reasoning chain across tool round-trips.  The ``ThoughtStore``
holds numbered thoughts with intent anchors, and the ``format_history()``
method produces text suitable for injection into the LLM message list.

Architecture
────────────
- ``Thought`` — Dataclass for a single reasoning step (number, text, timestamp)
- ``ThoughtStore`` — Per-session in-memory list of thoughts
- ``SequentialThinkingTool`` — Tool handler class registered as a builtin
- ``SessionStateManager`` — Centralized manager for all per-session state
  (replaces the old module-level ``_thought_stores`` dict)

Tags
────
- ``op:think`` — It's a thinking/prereasoning operation
- ``purpose:reasoning`` — Belongs in the reasoning category
- ``source:local`` — Executes locally, no external API call
- ``safe`` — Read-only, no side effects

Addresses
─────────
- Issue #1 (Plan Generation Quality)
- Issue #3 (Reasoning Thread Continuity)
- Issue #5 (Impulse Control)
- M4.2 — [intent: replan] Detection (detect when LLM signals need to replan)
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List


# ─── Data Structures ───────────────────────────────────────────────────────────


@dataclass
class Thought:
    """A single step in the reasoning chain."""

    number: int
    thought: str
    timestamp: float


class ThoughtStore:
    """Session-scoped sequential thought history with intent anchor support."""

    def __init__(self) -> None:
        self._thoughts: List[Thought] = []

    def add_thought(self, thought: str) -> Thought:
        """Add a thought and return it with its sequence number."""
        t = Thought(
            number=len(self._thoughts) + 1,
            thought=thought,
            timestamp=time.time(),
        )
        self._thoughts.append(t)
        return t

    def get_history(self) -> List[Thought]:
        """Return the full thought chain."""
        return list(self._thoughts)

    def format_history(self) -> str:
        """Format thoughts as a numbered list for injection into LLM context."""
        if not self._thoughts:
            return ""
        lines = ["[Your reasoning chain so far:]"]
        for t in self._thoughts:
            lines.append(f"{t.number}. {t.thought}")
        return "\n".join(lines)

    def clear(self) -> None:
        """Reset for a new session/task."""
        self._thoughts.clear()

    def __len__(self) -> int:
        return len(self._thoughts)

    @property
    def last_thought(self) -> Thought | None:
        """Get the most recent thought, or None if the store is empty."""
        return self._thoughts[-1] if self._thoughts else None

    # ── M4.2: [intent: replan] Detection ──────────────────────────────────

    REPLAN_PATTERN = re.compile(
        r"\[intent:\s*replan\]",
        re.IGNORECASE,
    )
    """Regex to detect ``[intent: replan]`` in thought text."""

    DEADEND_PATTERNS = [
        re.compile(r"dead.?end", re.IGNORECASE),
        re.compile(r"cannot\s+(proceed|continue|resolve)", re.IGNORECASE),
        re.compile(r"stuck|blocked|no\s+way\s+forward", re.IGNORECASE),
        re.compile(r"contradictory\s+results", re.IGNORECASE),
        re.compile(r"plan\s+failed", re.IGNORECASE),
    ]
    """Additional signals that may indicate a need to replan."""

    def detect_replan_intent(self) -> bool:
        """Check if the latest thought contains explicit ``[intent: replan]``.

        Returns:
            True if the most recent thought carries a replan intent anchor.
        """
        last = self.last_thought
        if last is None:
            return False
        return bool(self.REPLAN_PATTERN.search(last.thought))

    def detect_deadend_signal(self) -> bool:
        """Check if the latest thought signals a dead-end or contradictory state.

        Scans the last thought for phrases like "dead-end", "cannot proceed",
        "contradictory results", etc.

        Returns:
            True if a dead-end signal is detected.
        """
        last = self.last_thought
        if last is None:
            return False
        for pattern in self.DEADEND_PATTERNS:
            if pattern.search(last.thought):
                return True
        return False

    def needs_replan(self) -> bool:
        """High-level check: should we trigger a replan?

        Returns True if either:
        - The latest thought has an explicit ``[intent: replan]`` anchor, OR
        - The latest thought signals a dead-end / contradictory state.

        This is the main entry point for the stream service to poll.
        """
        return self.detect_replan_intent() or self.detect_deadend_signal()

    # ── End M4.2 ──────────────────────────────────────────────────────────


# ─── Session State Manager Integration ─────────────────────────────────────────

# Centralized manager for all per-session state.
# Replaces the old module-level ``_thought_stores`` dict.

# Session state — simple in-memory dict
_thought_stores: Dict[str, List[Dict[str, Any]]] = {}
_ephemeral_dbs: Dict[str, Any] = {}

def _get_thought_store(session_id: str, factory=None) -> Any:
    if session_id not in _thought_stores:
        if factory:
            _thought_stores[session_id] = factory(session_id)
        else:
            _thought_stores[session_id] = []
    return _thought_stores[session_id]

def _set_thought_store(session_id: str, store: Any) -> None:
    _thought_stores[session_id] = store


def _clear_thought_store(session_id: str) -> None:
    _thought_stores.pop(session_id, None)
    _ephemeral_dbs.pop(session_id, None)

def _get_ephemeral_db(session_id: str) -> Any:
    if session_id not in _ephemeral_dbs:
        from collections import defaultdict
        _ephemeral_dbs[session_id] = {"tables": defaultdict(list)}
    return _ephemeral_dbs[session_id]

def _list_sessions() -> List[str]:
    return list(_thought_stores.keys())


# ─── Tool Handler ──────────────────────────────────────────────────────────────


class SequentialThinkingTool:
    """
    Ephemeral scratchpad for step-by-step reasoning across tool calls.

    Tags:
        - op:think
        - purpose:reasoning
        - source:local
        - safe
    """

    name = "Sequential Thinking"
    slug = "sequential-thinking"
    capability = "reasoning-aid"
    description = (
        "Record a thought in your step-by-step reasoning chain. "
        "Use this to maintain context across tool calls: think about what "
        "you know, what you need to find out, what tool to use, and what "
        "to do with the result. The full thought history is returned. "
        "Include an [intent: ...] anchor at the start of each thought "
        "to preserve the overarching purpose across tool round-trips."
    )
    tags = ["op:think", "purpose:reasoning", "source:local", "safe"]
    icon = "brain"
    color = "#6F42C1"  # Purple

    arguments_schema = {
        "type": "object",
        "properties": {
            "thought": {
                "type": "string",
                "description": "Your next reasoning step. Be specific about what "
                "you know, what you need, and what tool to use next. "
                "Start with an [intent: ...] anchor.",
                "maxLength": 2000,
            },
            "next_thought_needed": {
                "type": "boolean",
                "description": "Set false when your reasoning chain is complete "
                "and you're ready to act/output.",
                "default": True,
            },
        },
        "required": ["thought"],
    }

    config_schema = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    async def execute(self, config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Record a thought and return the updated reasoning chain.

        The LLM should call this before each tool call and after receiving
        results, to maintain a coherent reasoning thread.

        Args:
            thought: The reasoning step text (required)
            next_thought_needed: Whether more reasoning steps follow (default: True)
            _session_id: Injected by the execution loop for store lookup
        """
        thought_text = kwargs.get("thought", "").strip()
        if not thought_text:
            return {
                "success": False,
                "error": "No thought provided",
                "error_type": "ValidationError",
            }

        session_id = kwargs.get("_session_id", "default")
        next_needed = kwargs.get("next_thought_needed", True)

        store = _get_thought_store(
            session_id,
            factory=lambda sid: ThoughtStore(),
        )
        thought = store.add_thought(thought_text)

        return {
            "success": True,
            "thought_number": thought.number,
            "total_thoughts": len(store),
            "next_thought_needed": next_needed,
            "history": store.format_history(),
        }


# ─── Convenience Accessors ─────────────────────────────────────────────────────


def get_thought_store(session_id: str) -> ThoughtStore:
    """Get or create a thought store for the given session.

    Uses the centralized ``SessionStateManager`` instead of a module-level dict.
    """
    store = _get_thought_store(session_id)
    if not isinstance(store, ThoughtStore):
        store = ThoughtStore()
        _set_thought_store(session_id, store)
    return store


def clear_thought_store(session_id: str) -> None:
    """Clear the thought store for a session (on reset/archive)."""
    _clear_thought_store(session_id)
