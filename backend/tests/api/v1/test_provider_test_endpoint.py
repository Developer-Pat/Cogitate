"""`POST /providers/config/{id}/test` — the endpoint RENDERS the ONE availability read.

Phase 6, group 5. This endpoint used to carry its own inline probe (a branch per provider type and
per provider NAME) — the copy the Health button used. It now calls
`availability.read_availability_for(force=True)` and maps the state onto the SAME
`ProviderTestResponse` shape, so `providerConfigService.testProvider` and the Health modal are
unaffected while the answer comes from one place.

What these tests pin:

* the card's four-word vocabulary is DERIVED from the availability state, not probed again
  (`connected` / `unreachable` / `not_configured`);
* `force=True` — an explicit test does not answer from the memo;
* `state` and `checked_at` ride along, so a caller can have the finer answer and the age;
* an unknown id is still a 404.

The tier's `_offline_availability` fixture patches `availability.probe_json` (nothing answers); a
test that needs a live answer patches it again — after the fixture, so its patch wins.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import Provider


async def _provider(
    test_engine, *, name: str, provider_type: str, base_url: str
) -> int:
    async with AsyncSession(test_engine) as session:
        row = Provider(
            name=name, provider_type=provider_type, base_url=base_url, is_active=True
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row.id


@pytest.mark.anyio
async def test_a_service_that_does_not_answer_reads_as_unreachable(client: AsyncClient, test_engine) -> None:
    provider_id = await _provider(
        test_engine, name="zz-dead", provider_type="openai", base_url="http://127.0.0.1:18999/v1"
    )

    resp = await client.post(f"/api/v1/providers/config/{provider_id}/test")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "unreachable"
    assert data["state"] in ("down", "down-by-occupancy")
    # The reason is the availability read's own words, not a second paragraph written here.
    assert "local server" in data["message"]
    assert data["checked_at"], "the card must be able to say WHEN it looked"


@pytest.mark.anyio
async def test_a_service_that_answers_reads_as_connected_with_its_catalogue(
    client: AsyncClient, test_engine, monkeypatch
) -> None:
    from app.domain.providers import availability as av

    provider_id = await _provider(
        test_engine, name="zz-alive", provider_type="openai", base_url="http://127.0.0.1:18888/v1"
    )

    async def probe(base_url: str, path: str, headers=None):
        if base_url == "http://127.0.0.1:18888/v1":
            return {"data": [{"id": "a"}, {"id": "b"}]}
        return None

    # AFTER the tier fixture — this patch wins.
    monkeypatch.setattr(av, "probe_json", probe)
    av.clear_cache()

    resp = await client.post(f"/api/v1/providers/config/{provider_id}/test")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "connected"
    assert data["state"] == "available"
    assert data["models_available"] == 2
    assert "zz-alive is running with 2 model(s)" == data["message"]


@pytest.mark.anyio
async def test_a_cloud_row_without_a_key_reads_as_not_configured(
    client: AsyncClient, test_engine
) -> None:
    """A CONFIGURATION fact, not an outage — the card must not send the reader after the network."""
    provider_id = await _provider(
        test_engine, name="zz-cloud", provider_type="deepseek", base_url="https://api.deepseek.com"
    )

    resp = await client.post(f"/api/v1/providers/config/{provider_id}/test")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "not_configured"
    assert data["state"] == "unconfigured"


@pytest.mark.anyio
async def test_an_explicit_test_does_not_answer_from_the_memo(
    client: AsyncClient, test_engine, monkeypatch
) -> None:
    """`force=True`: a Test button must not report a minute-old reading as if it just looked.

    The memo is primed with `available`, the service is then silent, and the endpoint is expected to
    go and LOOK — which is also what refreshes the shared memo every other surface reads.
    """
    from app.domain.providers import availability as av

    provider_id = await _provider(
        test_engine, name="zz-flip", provider_type="openai", base_url="http://127.0.0.1:18777/v1"
    )
    row = {
        "id": provider_id, "name": "zz-flip", "provider_type": "openai",
        "base_url": "http://127.0.0.1:18777/v1",
    }

    async def answers(base_url: str, path: str, headers=None):
        return {"data": [{"id": "a"}]}

    monkeypatch.setattr(av, "probe_json", answers)
    av.clear_cache()
    primed = await av.read_availability([row])
    assert primed["zz-flip"].state == av.STATE_AVAILABLE, "the memo starts warm and positive"

    async def silent(base_url: str, path: str, headers=None):
        return None

    monkeypatch.setattr(av, "probe_json", silent)

    resp = await client.post(f"/api/v1/providers/config/{provider_id}/test")

    assert resp.json()["status"] == "unreachable", "an explicit test must re-probe, not read the memo"


@pytest.mark.anyio
async def test_an_unknown_provider_is_still_a_404(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/providers/config/999999/test")
    assert resp.status_code == 404
