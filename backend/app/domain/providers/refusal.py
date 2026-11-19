"""THE PRE-TURN REFUSAL — the ONE "can this turn run right now?" question, and its sentence.

The service-capability arc, phase 6 group 5 (G5-F3/F4). The availability ruling's DOWN half (user,
2026-09-30):

    "when llama.cpp is up we can use it, when it is down the agent is either disabled or uses a
    fallback, either of which can be configured … I should get a signal that lois is not available
    and chat should be refused with a message about llm not available."

TWO states refuse a turn, and they are the two the ruling names:

* **the capability is switched off** — `resolve()` answers `reason='disabled'`, so nothing is
  configured to answer it and quietly falling through to a default row would be the second answer
  this arc removes;
* **the primary service is not available and the turn cannot fall over** — the agent's declared
  service is down and there is nothing to try instead.

**"No fallback configured" uses the app's OWN lever, because that is the phrase the app already
means.** The chat executor walks a chain only when the agent's `fallback_enabled` is on
(`executor.py`: `fallbacks=bool(agent.fallback_enabled)`), and the failure statement reads exactly
that flag when it says *"No fallback is configured for this agent."* So a turn can fail over iff
the fallback is **switched on** AND the chain has a **backup**; anything else is a single attempt
that is going to fail, which is what this module says BEFORE the pipeline starts.

**The read is the CACHE only** (`availability.cached` / `cached_by_name`): a turn never pays a
probe, and an `unknown` or stale state NEVER refuses. The at-turn chain walk stays the arbiter, so
the app never refuses a turn over a service nobody actually checked. The consequence is deliberate
and named: a COLD cache refuses nothing — the refusal is a fast path for what the app already
knows, not a substitute for the walk.

**A fallback that can run means the turn RUNS.** When the chain has a backup and the fallback is
switched on, this returns None: the walk tries and fails over, and the failure path's own statement
speaks if the whole chain runs out.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

from app.domain.providers.availability import (
    STATE_UNKNOWN,
    Availability,
    cached,
    cached_by_name,
    read_availability_for,
)
from app.domain.providers.capabilities import REASON_DISABLED
from app.domain.providers.failure_statement import EXA_DIAGNOSIS_OFFER, model_subject


def _cached_for(candidate: Any) -> Optional[Availability]:
    """The MEMO's state for a candidate's service — by row id when it has one, else by name.

    A configured (or global-default) candidate carries its provider row's id; an AGENT's declared
    candidate carries only the provider NAME, because the resolver does not resolve a declaration
    to a row. Both reads are the same in-process memo and neither probes.
    """
    provider_id = getattr(candidate, "provider_id", None)
    if provider_id is not None:
        found = cached(int(provider_id))
        if found is not None:
            return found
    name = getattr(candidate, "provider", None)
    if name:
        return cached_by_name(str(name))
    return None


def can_fail_over(candidates: Sequence[Any], *, fallback_enabled: bool) -> bool:
    """Whether this turn has something to try after the primary — the walk's own condition.

    Both halves are required: a backup the walk is not allowed to use (`fallback_enabled` off) is
    not a fallback, and a fallback switched on over a chain with nothing after the primary has
    nowhere to go.
    """
    return bool(fallback_enabled) and len(candidates) > 1


def blocking_service(
    *,
    resolution_reason: str,
    candidates: Sequence[Any],
    fallback_enabled: bool,
) -> Optional[Availability]:
    """The service that stops this turn from running, or None when the turn can proceed.

    THE ONE PREDICATE both consumers share — the pre-turn refusal below and the agent surface's
    *"cannot run now"* badge — so the two surfaces can never disagree about one agent.

    A `disabled` capability is NOT a blocking SERVICE (there is no row to point at); its own state
    is the answer, and the caller handles it. A cold or `unknown` memo is not an answer either: a
    service nobody checked never blocks a turn.
    """
    if resolution_reason == REASON_DISABLED:
        return None
    if can_fail_over(candidates, fallback_enabled=fallback_enabled):
        return None
    if not candidates:
        return None
    service = _cached_for(candidates[0])
    if service is None or service.available is None or service.available:
        return None
    return service


def refusal_statement(
    capability: str,
    *,
    resolution_reason: str,
    candidates: Sequence[Any],
    fallback_enabled: bool = False,
) -> Optional[str]:
    """The refusal for a turn that cannot run, or None to let the pipeline start.

    `capability` is the capability KEY (`chat`), the same handle `NoProviderConfiguredError` names,
    so a refusal and a "nothing is configured" message read as one family. The sentence names the
    offending service the way every other failure surface does (`failure_statement.py`) — provider
    AND model, no model recommended, the Exa offer — because the reader has to be able to act on it.
    """
    if resolution_reason == REASON_DISABLED:
        return (
            f"The '{capability}' capability is switched off, so this turn was refused. "
            f"Turn it on at Providers → Capabilities (/providers/capabilities)."
        )

    service = blocking_service(
        resolution_reason=resolution_reason,
        candidates=candidates,
        fallback_enabled=fallback_enabled,
    )
    if service is None:
        return None

    primary = candidates[0]
    subject = model_subject(getattr(primary, "model", None), getattr(primary, "provider", None))
    clause = (service.reason or "").strip().rstrip(".")
    sentence = f"{subject} is unavailable" + (f" — {clause}" if clause else "")
    sentence += ". No fallback is configured for this agent."
    return f"{sentence} {EXA_DIAGNOSIS_OFFER}"


# ── The same question, asked by a SURFACE (G5-F2's agent half) ───────────────────────────────────
#
# The agent profiles page answers *"can this agent run right now?"* — and that is the question the
# refusal above already answers, so it is answered by the SAME predicate and never by a second
# opinion. The difference is only the READ: a page can afford the probe (it is cached for the whole
# 60s window and every surface shares it), while a turn reads the memo only.

STATE_DISABLED = "disabled"  # the capability itself is switched off — not a service's state


@dataclass(frozen=True)
class RunReadiness:
    """Whether one agent's `chat` chain can run right now, and the service that stops it.

    `available` is None when NOTHING was checked (the honest "we do not know"), never False — the
    same rule as `Availability.available`, so a surface can say "not checked" instead of calling a
    working agent broken.
    """

    state: str
    available: Optional[bool]
    reason: str = ""
    checked_at: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None


def readiness(resolved: Any, *, fallback_enabled: bool) -> RunReadiness:
    """The verdict for one resolved `chat` chain — the same rule the pre-turn refusal applies."""
    if resolved.reason == REASON_DISABLED:
        return RunReadiness(
            state=STATE_DISABLED,
            available=False,
            reason=f"the '{resolved.capability}' capability is switched off",
        )

    primary = resolved.primary
    if primary is None:
        return RunReadiness(
            state=STATE_UNKNOWN,
            available=None,
            reason="nothing is configured for this agent",
        )

    blocking = blocking_service(
        resolution_reason=resolved.reason,
        candidates=resolved.candidates,
        fallback_enabled=fallback_enabled,
    )
    if blocking is not None:
        return RunReadiness(
            state=blocking.state,
            available=False,
            reason=blocking.reason,
            checked_at=blocking.checked_at,
            provider=primary.provider,
            model=primary.model,
        )

    if can_fail_over(resolved.candidates, fallback_enabled=fallback_enabled):
        # The primary may be down, but the walk will try the next one: the agent can still run, so
        # this is NOT the "cannot run now" state (the two surfaces must not disagree).
        return RunReadiness(
            state="available",
            available=True,
            reason="a fallback is configured for this agent",
            provider=primary.provider,
            model=primary.model,
        )

    checked = _cached_for(primary)
    if checked is None:
        return RunReadiness(
            state=STATE_UNKNOWN,
            available=None,
            reason="not checked",
            provider=primary.provider,
            model=primary.model,
        )
    return RunReadiness(
        state=checked.state,
        available=checked.available,
        reason=checked.reason,
        checked_at=checked.checked_at,
        provider=primary.provider,
        model=primary.model,
    )


async def chat_readiness(db: Any, agents: Sequence[Any]) -> Dict[int, RunReadiness]:
    """agent_id -> can it run now? — ONE availability pass, then the shared predicate.

    The pass runs FIRST (`read_availability_for`, the same one the capability read-out makes), so
    the memo holds a current answer for the predicate to read. `agent` is resolved through the
    resolver's own agent rung (`chat` + the agent), so this badge and a real turn's chain come from
    one place.
    """
    from app.domain.providers.capabilities import CHAT_CAPABILITY_KEY, resolve

    agents = [a for a in agents if getattr(a, "id", None) is not None]
    if not agents:
        return {}

    resolved_by_agent = {
        agent.id: await resolve(db, CHAT_CAPABILITY_KEY, agent=agent) for agent in agents
    }
    await read_availability_for(db, list(resolved_by_agent.values()))

    return {
        agent.id: readiness(
            resolved_by_agent[agent.id],
            fallback_enabled=bool(getattr(agent, "fallback_enabled", False)),
        )
        for agent in agents
    }
