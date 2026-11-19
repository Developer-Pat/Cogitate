"""The pre-turn refusal — the ONE "can this turn run right now?" question (phase 6, G5-F3/F4).

What these tests pin, in the availability ruling's own terms:

* a capability switched OFF is REFUSED (it must not quietly fall through to a default row);
* a primary that is cached-**down** with nothing the walk may fail over to is REFUSED, and the
  sentence names the service, says no fallback is configured and offers Exa — the statement shape;
* a fallback that CAN run means the turn RUNS (the walk tries and fails over);
* **the cold/`unknown` state NEVER refuses** — the discriminator the ruling turns on: the refusal
  must not guess about a service nobody checked, because the at-turn walk is the arbiter;
* an `available` primary does not refuse, and a NAMED service (a speech engine, the Exa process)
  never blocks an LLM turn.

The memo is seeded directly — no daemons, no network, no probe.
"""

from __future__ import annotations

import time

import pytest

from app.domain.providers import availability as av
from app.domain.providers.capabilities import (
    REASON_AGENT,
    REASON_CAPABILITY,
    REASON_DISABLED,
    ServiceCandidate,
)
from app.domain.providers.refusal import (
    blocking_service,
    can_fail_over,
    readiness,
    refusal_statement,
)


def _candidate(provider: str, model: str = "some-model", provider_id=None) -> ServiceCandidate:
    return ServiceCandidate(
        ordinal=0, provider=provider, provider_id=provider_id, model=model, source=REASON_AGENT
    )


def _memo(name: str, state: str, reason: str, *, provider_id: int = 42) -> av.Availability:
    """Put a state in the memo under `name` the way a real read would have."""
    entry = av.Availability(
        provider_id=provider_id,
        name=name,
        state=state,
        reason=reason,
        checked_at="2026-10-05T00:00:00Z",
    )
    av._CACHE[provider_id] = (time.monotonic() + av.DEFAULT_TTL_SECONDS, entry)
    return entry


@pytest.fixture(autouse=True)
def _cold_cache():
    av.clear_cache()
    yield
    av.clear_cache()


# ── the two refusing states ──────────────────────────────────────────────────────────────────────

def test_a_capability_switched_off_is_refused_and_names_no_llm() -> None:
    """'Off' is a statement about the capability — there is no service to finger, and none is named."""
    statement = refusal_statement(
        "chat",
        resolution_reason=REASON_DISABLED,
        candidates=[],
        fallback_enabled=True,
    )

    assert statement is not None
    assert "'chat' capability is switched off" in statement
    assert "/providers/capabilities" in statement
    # NOT the failure shape: no service is named and nothing is offered for diagnosis.
    assert "is unavailable" not in statement
    assert "Exa" not in statement


def test_a_down_primary_with_no_fallback_reads_as_the_statement_shape() -> None:
    """Names provider + model, says no fallback is configured, offers Exa — the one rule, one shape."""
    _memo("llama", av.STATE_DOWN, "the local server is not running and no local server answers")

    statement = refusal_statement(
        "chat",
        resolution_reason=REASON_AGENT,
        candidates=[_candidate("llama", "Bonsai-27B-Q1_0.gguf")],
        fallback_enabled=False,
    )

    assert statement is not None
    assert "Bonsai 27b Q1 0.gguf (llama)" in statement, "the offender is named by provider AND model"
    assert "is unavailable" in statement
    assert "the local server is not running" in statement, "the availability reason rides along"
    assert "No fallback is configured for this agent." in statement
    assert "Exa" in statement


def test_a_fallback_that_can_run_lets_the_turn_proceed() -> None:
    """The ruling's other half: with a backup AND the fallback switched on, the walk tries."""
    _memo("llama", av.STATE_DOWN, "silent")

    assert refusal_statement(
        "chat",
        resolution_reason=REASON_AGENT,
        candidates=[_candidate("llama"), _candidate("openrouter")],
        fallback_enabled=True,
    ) is None


def test_a_backup_the_walk_may_not_use_is_not_a_fallback() -> None:
    """`fallback_enabled` OFF means ONE attempt (`executor.attempt_chain(fallbacks=False)`).

    A declared backup the walk is not allowed to reach cannot carry the turn, so the turn is
    refused exactly as if the chain had nothing after the primary — this is the live Bob/Lois shape
    (`fallback_enabled=0` beside a `preferred_providers` entry).
    """
    _memo("llama", av.STATE_DOWN, "silent")

    statement = refusal_statement(
        "chat",
        resolution_reason=REASON_AGENT,
        candidates=[_candidate("llama"), _candidate("openrouter")],
        fallback_enabled=False,
    )

    assert statement is not None
    assert "No fallback is configured for this agent." in statement


# ── what does NOT refuse — the discriminators ────────────────────────────────────────────────────

def test_a_service_nobody_checked_never_refuses() -> None:
    """THE ruling: an `unknown`/cold state never refuses — a guess is the false signal to avoid."""
    # Nothing in the memo at all (a cold cache).
    assert refusal_statement(
        "chat",
        resolution_reason=REASON_AGENT,
        candidates=[_candidate("llama")],
        fallback_enabled=False,
    ) is None

    # An entry that IS the `unknown` state.
    _memo("llama", av.STATE_UNKNOWN, "never checked")
    assert refusal_statement(
        "chat",
        resolution_reason=REASON_AGENT,
        candidates=[_candidate("llama")],
        fallback_enabled=False,
    ) is None


def test_an_available_primary_does_not_refuse() -> None:
    _memo("llama", av.STATE_AVAILABLE, "the local server is running and serves Bonsai-27B-Q1_0.gguf")
    assert refusal_statement(
        "chat",
        resolution_reason=REASON_AGENT,
        candidates=[_candidate("llama")],
        fallback_enabled=False,
    ) is None


def test_a_named_service_candidate_never_blocks_an_llm_turn() -> None:
    """A speech engine / the Exa process has no provider row — it is a different question."""
    named = ServiceCandidate(ordinal=0, service_name="edge", source="named")
    assert refusal_statement(
        "tts",
        resolution_reason=REASON_CAPABILITY,
        candidates=[named],
        fallback_enabled=False,
    ) is None


def test_nothing_resolved_is_not_this_refusal() -> None:
    """A chain that resolved to NOTHING is the caller's own failure path (it names nobody)."""
    assert refusal_statement(
        "chat",
        resolution_reason="none",
        candidates=[],
        fallback_enabled=False,
    ) is None


# ── the shared predicate (the agent surface's half) ──────────────────────────────────────────────

def test_blocking_service_returns_the_service_that_stops_the_turn() -> None:
    """Both consumers share this, so the refusal and the agent badge cannot disagree."""
    _memo("llama", av.STATE_DOWN_BY_OCCUPANCY, "another local server owns the GPU")

    service = blocking_service(
        resolution_reason=REASON_AGENT,
        candidates=[_candidate("llama")],
        fallback_enabled=False,
    )

    assert service is not None
    assert service.state == av.STATE_DOWN_BY_OCCUPANCY
    assert service.name == "llama"


def test_blocking_service_returns_none_for_a_disabled_capability() -> None:
    """A disabled capability has no blocking SERVICE — its own state is the answer."""
    assert blocking_service(
        resolution_reason=REASON_DISABLED, candidates=[], fallback_enabled=False
    ) is None


def test_can_fail_over_needs_both_halves() -> None:
    assert can_fail_over([_candidate("a"), _candidate("b")], fallback_enabled=True) is True
    assert can_fail_over([_candidate("a"), _candidate("b")], fallback_enabled=False) is False
    assert can_fail_over([_candidate("a")], fallback_enabled=True) is False


# ── the name lookup the agent-declared candidate needs ───────────────────────────────────────────

def test_a_row_candidate_is_answered_by_its_id_and_a_declared_one_by_its_name() -> None:
    """A declared candidate carries no row id, so the memo must be askable by NAME.

    This is the whole reason `cached_by_name` exists: the same memo, reached from a handle the row
    candidates do not use. It must not be a second cache.
    """
    _memo("llama", av.STATE_DOWN, "silent", provider_id=6)

    # By id — the row candidate's handle.
    assert av.cached(6) is not None
    # By name — the agent-declared candidate's handle.
    assert av.cached_by_name("llama") is not None
    assert av.cached_by_name("llama").state == av.STATE_DOWN
    # A name nobody memoised answers nothing (and never a guess).
    assert av.cached_by_name("openrouter") is None

    # The refusal reaches the memo through the NAME when the candidate has no id.
    statement = refusal_statement(
        "chat",
        resolution_reason=REASON_AGENT,
        candidates=[ServiceCandidate(ordinal=0, provider="llama", model="Bonsai-27B-Q1_0.gguf")],
        fallback_enabled=False,
    )
    assert statement is not None and "Bonsai 27b Q1 0.gguf (llama)" in statement


def test_cached_by_name_ignores_a_stale_entry() -> None:
    """A stale memo is not an answer — `cached` and `cached_by_name` agree on the TTL."""
    entry = av.Availability(
        provider_id=6, name="llama", state=av.STATE_DOWN, reason="silent",
        checked_at="2026-10-05T00:00:00Z",
    )
    av._CACHE[6] = (time.monotonic() - 1, entry)  # already expired

    assert av.cached(6) is None
    assert av.cached_by_name("llama") is None


# ── the surface's half: the SAME question, asked by the agent profiles page (G5-F2) ─────────────

def _resolved(reason: str, *candidates: ServiceCandidate, capability: str = "chat"):
    from app.domain.providers.capabilities import ResolvedService

    return ResolvedService(capability=capability, kind="llm", reason=reason, candidates=candidates)


def test_readiness_reports_an_agent_that_cannot_run() -> None:
    """The badge's `False` is the refusal's own state — one predicate, so they cannot disagree."""
    _memo("llama", av.STATE_DOWN, "the local server is not running")

    verdict = readiness(
        _resolved(REASON_AGENT, _candidate("llama", "Bonsai-27B-Q1_0.gguf")),
        fallback_enabled=False,
    )

    assert verdict.available is False
    assert verdict.state == av.STATE_DOWN
    assert verdict.provider == "llama"
    assert verdict.model == "Bonsai-27B-Q1_0.gguf"
    assert "not running" in verdict.reason


def test_readiness_is_none_when_nothing_was_checked() -> None:
    """`available=None`, never False — "we do not know" is not a badge that calls an agent broken."""
    verdict = readiness(_resolved(REASON_AGENT, _candidate("llama")), fallback_enabled=False)

    assert verdict.available is None
    assert verdict.state == av.STATE_UNKNOWN


def test_readiness_is_positive_when_a_fallback_can_carry_the_turn() -> None:
    """A down primary with a usable backup is NOT "cannot run" — the turn would fail over."""
    _memo("llama", av.STATE_DOWN, "silent")

    verdict = readiness(
        _resolved(REASON_AGENT, _candidate("llama"), _candidate("openrouter")),
        fallback_enabled=True,
    )

    assert verdict.available is True
    assert "fallback" in verdict.reason


def test_readiness_carries_a_switched_off_capability() -> None:
    verdict = readiness(_resolved(REASON_DISABLED), fallback_enabled=True)

    assert verdict.available is False
    assert verdict.state == "disabled"
    assert "switched off" in verdict.reason
