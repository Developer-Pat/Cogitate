"""`POST /providers/complete` — the caller NAMES the service; no default is written in code.

This endpoint used to read `request_data.get("provider", "ollama")`: a provider NAME in code, aimed at
a local engine that need not be running. Its own schema declares `provider: str` (required), and the
external agent it exists for always names one — so an omission is a bad request, never a licence to
invent a service. The fallback chain it builds afterwards comes from the caller's name as an
`override`, so nothing here may supply one either.

What these tests pin:

* an omitted `provider` is a 400 that names it, and NOTHING is called — not the completion service,
  not the rate limiter (which would otherwise be handed an invented name);
* an empty name is not a name;
* the pre-existing required fields still read the same way.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

PAYLOAD = {"messages": [{"role": "user", "content": "hi"}], "model": "some-model"}


class _ServiceProbe:
    """Records any attempt to USE a service — the property under test is that none happens."""

    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("a service was called although the caller named none")


class _LimiterProbe:
    """Records every provider name the rate limiter is asked about."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    def can_proceed(self, provider: str) -> bool:
        self.asked.append(provider)
        return True

    def get_wait_time(self, provider: str) -> float:
        return 0.0

    def record_request(self, provider: str) -> None:
        self.asked.append(provider)


@pytest.fixture
def no_service(monkeypatch):
    """The completion service and the rate limiter, both replaced by probes."""
    from app.api.v1.providers import completion_router as mod

    probe = _ServiceProbe()
    limiter = _LimiterProbe()
    monkeypatch.setattr(mod, "provider_completion_service", probe)
    monkeypatch.setattr(mod, "rate_limiter", limiter)
    return probe, limiter


@pytest.mark.anyio
async def test_an_omitted_provider_is_refused_and_no_service_is_called(
    client: AsyncClient, no_service
) -> None:
    probe, limiter = no_service

    resp = await client.post("/api/v1/providers/complete", json=PAYLOAD)

    assert resp.status_code == 400
    assert "provider" in resp.json()["detail"]
    assert probe.calls == 0, "no literal default may answer for a caller that named nothing"
    assert limiter.asked == [], "an invented name must not even reach the rate limiter"


@pytest.mark.anyio
async def test_an_empty_provider_name_is_not_a_name(client: AsyncClient, no_service) -> None:
    probe, limiter = no_service

    resp = await client.post("/api/v1/providers/complete", json={**PAYLOAD, "provider": ""})

    assert resp.status_code == 400
    assert probe.calls == 0
    assert limiter.asked == []


@pytest.mark.anyio
async def test_the_required_fields_read_the_same_way(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/providers/complete", json={"provider": "deepseek"})

    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "messages" in detail
    assert "model" in detail
