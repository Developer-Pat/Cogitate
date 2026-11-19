"""
Conduit Router — shallow-to-deep agent delegation.

Provides conduit_route() for deciding the execution path and
conduit_delegate() for routing queries to named deep agents.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class Route(Enum):
    """Execution route chosen by the conduit."""

    SHALLOW = "shallow"
    """Respond directly with the standard LLM call."""

    HYBRID = "hybrid"
    """Use the existing HybridExecutor deep pass (same agent)."""

    DELEGATE = "delegate"
    """Route to a named deep agent with full cognitive pipeline."""


@dataclass
class ConduitDecision:
    """Result of the conduit route decision."""

    route: Route
    reason: str = ""
    target_agent_id: Optional[int] = None
    """Agent ID to delegate to (only for DELEGATE route)."""


# ---------------------------------------------------------------------------
# Delegation targets — agents registered as conduit delegates
# ---------------------------------------------------------------------------

DELEGATION_TARGETS: Dict[str, int] = {
    "researcher": 45,
    # "system-manager": 48 — RETIRED 2026-08-19: Exa is the system
    # agent now; the System Manager agent was deleted (recoverable
    # archive). The conduit delegates to DB agents; Exa is reached
    # through the external-agent surface, not here.
}


def get_delegate_agent_id(name: str) -> Optional[int]:
    """Look up a named delegate target.

    Returns the agent ID, or None if the name is not registered.
    """
    return DELEGATION_TARGETS.get(name.lower())


def list_delegate_names() -> List[str]:
    """Return all registered delegate target names."""
    return list(DELEGATION_TARGETS.keys())


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------

DEEP_KEYWORDS = [
    "research", "analyze", "explain", "compare", "contrast",
    "why", "how", "difference", "pros and cons", "evaluate",
    "summarize", "investigate", "deep dive", "literature review",
    "synthesize",
]

RESEARCH_DELEGATE_KEYWORDS = [
    "research", "investigate", "deep dive", "literature review",
    "synthesize", "comprehensive analysis",
]

SYSTEM_DELEGATE_KEYWORDS = [
    "create agent", "set up", "configure", "manage",
    "deploy", "provision", "onboard", "system status",
    "health check", "diagnostics",
    "workflow", "provider",
]


def conduit_route(
    *,
    message: str,
    executor_strategy: str,
    accumulated_content: Optional[str],
    tools_were_used: bool,
) -> ConduitDecision:
    """Decide the execution route for a query.

    Supports HYBRID (current agent deep pass with tools/memory).
    Does NOT auto-delegate to a different agent — agent switching is
    done manually by the user in the chat UI.
    DELEGATION_TARGETS and keywords preserved for future team chat.
    """
    query_lower = message.lower()

    # Check for hybrid (deep pass) eligibility — current agent only
    # THE TOOLS-TRIGGER REMOVED (2026-09-02, the Bob DOUBLE-glitch):
    # tools_were_used no longer forces a deep pass. In the streaming
    # router the tool loop runs until the model writes its final text
    # answer (no more tool calls) — the synthesis ALREADY happened,
    # so re-answering duplicates the whole report (Bob's session:
    # two full reports glued into one message). Deep pass fires only
    # when the first pass is genuinely insufficient: short content,
    # or the query asks for depth (deep keywords).
    if executor_strategy == "hybrid" and accumulated_content:
        is_short = len(accumulated_content) < 500

        matched_deep_kws = [kw for kw in DEEP_KEYWORDS if kw in query_lower]
        needs_deep = bool(matched_deep_kws)

        if is_short or needs_deep:
            logger.info(
                "Conduit: HYBRID route — short=%s, deep=%s, kws=%s, content_len=%d, tools=%s",
                is_short, needs_deep, matched_deep_kws if needs_deep else [],
                len(accumulated_content), tools_were_used,
            )
            return ConduitDecision(
                route=Route.HYBRID,
                reason=f"short={is_short}, deep_keywords={needs_deep}",
            )

    # Default: shallow
    logger.info(
        "Conduit: SHALLOW route — strategy=%s, has_content=%s, content_len=%d, tools=%s",
        executor_strategy, bool(accumulated_content),
        len(accumulated_content) if accumulated_content else 0,
        tools_were_used,
    )
    return ConduitDecision(
        route=Route.SHALLOW,
        reason="Standard query, no deep processing needed",
    )
