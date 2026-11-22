"""`GET /providers/health` reports what was OBSERVED, never a default.

The endpoint used to iterate the STATIC `SUPPORTED_PROVIDERS` registry, so a fresh install
listed `openai` and `anthropic` as `healthy` with no row, no key and no call ever made — a
default-green row that reads as a check. These tests pin the three facts that keep the
distinction:

1. an unseen provider is ABSENT (unknown), not `healthy`;
2. a recorded failure makes the provider appear, with the count;
3. the circuit breaker's own semantics are untouched — `is_healthy` still answers True for an
   unseen name, because there the question is "may the attempt run", not "what was measured".
"""

from __future__ import annotations

import pytest

from app.api.v1.providers import completion_router
from app.domain.providers.rate_limiter import ProviderHealthMonitor


async def test_an_unseen_provider_is_absent_from_the_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fresh monitor has observed NOTHING — the payload says so by being empty."""
    fresh = ProviderHealthMonitor()
    assert fresh.observed() == []

    monkeypatch.setattr(completion_router, "health_monitor", fresh)
    payload = await completion_router.get_provider_health()

    assert payload["providers"] == {}
    assert "openai" not in payload["providers"]
    assert "anthropic" not in payload["providers"]


async def test_a_recorded_failure_names_the_provider_with_its_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The provider appears once an outcome exists, and the payload carries that outcome."""
    fresh = ProviderHealthMonitor(failure_threshold=2)
    fresh.record_failure("deepseek")

    monkeypatch.setattr(completion_router, "health_monitor", fresh)
    payload = await completion_router.get_provider_health()

    assert set(payload["providers"]) == {"deepseek"}
    row = payload["providers"]["deepseek"]
    assert row["failure_count"] == 1
    assert row["healthy"] is True  # below the threshold: still allowed to run
    assert "rate_limit" in row


def test_the_breaker_still_allows_an_unseen_provider() -> None:
    """`is_healthy` answers a DIFFERENT question than the report — keep the two apart."""
    fresh = ProviderHealthMonitor()
    assert fresh.is_healthy("never-called") is True
    assert fresh.observed() == []


def test_reset_forgets_what_it_had_observed() -> None:
    fresh = ProviderHealthMonitor()
    fresh.record_success("groq")
    assert fresh.observed() == ["groq"]
    fresh.reset()
    assert fresh.observed() == []
