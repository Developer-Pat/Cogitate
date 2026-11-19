"""Curated matching filters by thinking level, location and min-context floor.

THE RULE: substitution is a PROPOSAL, never automatic. The matcher
returns candidates (free-first); an HONEST EMPTY when nothing
matches. The thinking level is a FLOOR: a 'low' spec accepts
low/medium/high models; 'none' accepts everything.
"""

import uuid

import pytest
from sqlalchemy import delete, select

from app.infrastructure.database.models import Provider, CuratedModel, ProviderModelCache

from tests import conftest as cf


async def _get_or_create_provider(db, name: str) -> Provider:
    """The provider row for `name`, reused when the copied database already has it.

    The rule has ONE home now — `conftest.get_or_create_provider` — because the reason is the
    copied database and not this file's fixtures: the test database starts as a copy of a real
    installation, so `openrouter` and `ollama` are usually already present, and inserting them
    again is a UNIQUE violation at fixture setup.
    """
    return await cf.get_or_create_provider(db, name=name, provider_type=name)


@pytest.fixture
async def seeded_models(test_session):
    """Seed the test DB with the curated models the matcher needs.

    THE FIXTURE OWNS THE TABLE. It CLEARS the curated rows it does not seed before
    adding its own — because the test database is a COPY of a real one (`conftest`)
    and `auto_clean_tables` wipes tables only AFTER each test, so a test that happens
    to be the FIRST one a worker runs still sees the copy's own curated rows.

    That made the assertions over "every candidate" claims about rows this file never
    seeded, and two of them were green only by distribution luck:

    * `all(c["thinking"] == "high")` met the copy's `mandatory` row (which the 'high'
      floor legitimately accepts);
    * `all(context_length >= 1000000)` met the copy's ten rows with no recorded window
      (which the floor's NULL-tolerant guard let through).

    Both surfaced in the parallel api group when xdist started a worker with one of
    them. Owning the table is the fix: the premise a test asserts over is now the
    premise the fixture creates.
    """
    await test_session.execute(delete(CuratedModel))

    # providers
    orp = await _get_or_create_provider(test_session, "openrouter")
    oll = await _get_or_create_provider(test_session, "ollama")
    # the models
    models = [
        CuratedModel(model_id="qwen/qwen3.8-max", model_name="Qwen3.8 Max", provider_id=orp.id, is_free=True, thinking="high", location="cloud", context_length=1048576),
        CuratedModel(model_id="deepseek/deepseek-v4-flash", model_name="DeepSeek V4 Flash", provider_id=orp.id, is_free=False, thinking="none", location="cloud", context_length=1000000),
        CuratedModel(model_id="llama3.2:latest", model_name="Llama 3.2", provider_id=oll.id, is_free=True, thinking="none", location="local", context_length=128000),
        CuratedModel(model_id="qwen/qwen3-next-80b-a3b-instruct", model_name="Qwen3 Next 80B", provider_id=orp.id, is_free=True, thinking="low", location="cloud", context_length=128000),
    ]
    test_session.add_all(models)
    await test_session.commit()
    return test_session


@pytest.mark.anyio
async def test_match_thinking_none_accepts_all(client, seeded_models):
    """A 'none' spec (a chat bot) accepts every model — free-first."""
    r = await client.post("/api/v1/curated-models/match", json={
        "thinking": "none", "location": "any",
    })
    assert r.status_code == 200
    d = r.json()
    assert d["total"] >= 1
    # free first
    assert d["candidates"][0]["is_free"] is True


@pytest.mark.anyio
async def test_match_thinking_high_only_the_high_model(client, seeded_models):
    """A 'high' spec (the Boss's contract) matches ONLY the high
    models — qwen3.8-max is the known one (the ox-alpha stand-in
    after the 2026-09-07 scrub)."""
    r = await client.post("/api/v1/curated-models/match", json={
        "thinking": "high", "location": "cloud",
    })
    assert r.status_code == 200
    d = r.json()
    ids = [c["model_id"] for c in d["candidates"]]
    assert "qwen/qwen3.8-max" in ids
    # every candidate is high (the floor == the exact level here)
    assert all(c["thinking"] == "high" for c in d["candidates"])


@pytest.mark.anyio
async def test_match_thinking_low_floor(client, seeded_models):
    """A 'low' spec accepts low AND high models (the floor)."""
    r = await client.post("/api/v1/curated-models/match", json={
        "thinking": "low", "location": "cloud",
    })
    d = r.json()
    levels = {c["thinking"] for c in d["candidates"]}
    assert "low" in levels
    assert "high" in levels  # the floor accepts higher


@pytest.mark.anyio
async def test_match_location_local(client, seeded_models):
    """A 'local' spec returns ONLY local models."""
    r = await client.post("/api/v1/curated-models/match", json={
        "thinking": "none", "location": "local",
    })
    d = r.json()
    assert d["total"] >= 1
    assert all(c["location"] == "local" for c in d["candidates"])
    ids = {c["model_id"] for c in d["candidates"]}
    assert "llama3.2:latest" in ids


@pytest.mark.anyio
async def test_match_honest_empty(client, seeded_models):
    """NO candidates when nothing matches (an honest empty — no
    fake picks). The registry has no local high models."""
    r = await client.post("/api/v1/curated-models/match", json={
        "thinking": "high", "location": "local",
    })
    d = r.json()
    assert d["total"] == 0
    assert d["candidates"] == []


@pytest.mark.anyio
async def test_match_min_context_floor(client, seeded_models):
    """The min_context floor filters small-context models."""
    r = await client.post("/api/v1/curated-models/match", json={
        "thinking": "none", "location": "any", "min_context": 1000000,
    })
    d = r.json()
    assert d["total"] >= 1
    assert all(
        (c.get("context_length") or 0) >= 1000000 for c in d["candidates"]
    )


# ── E.3: the window fit is REPORTED, never a filter (D9) ─────────────────────

@pytest.mark.anyio
async def test_a_window_too_small_for_the_need_WARNS_and_is_still_offered(
    client, seeded_models, caplog
):
    """A driver that cannot hold the prompt floor + the declared output is ALLOWED.

    It stays in the candidate list (the runtime will clamp the budget to fit,
    `reason=window_clamp`) and the mismatch is said at match time — 128000 cannot
    hold 100000 of prompt plus 50000 of answer.
    """
    import logging

    with caplog.at_level(logging.WARNING, logger="app.domain.providers.curated_models_service"):
        r = await client.post("/api/v1/curated-models/match", json={
            "thinking": "none", "location": "any",
            "min_context": 100000, "max_output": 50000,
        })

    assert r.status_code == 200
    d = r.json()
    small = [c for c in d["candidates"] if c["context_length"] == 128000]
    assert small, "the too-small driver was filtered out — D9 says it is offered"
    assert "WINDOW FIT" in caplog.text
    assert "window_clamp" in caplog.text


@pytest.mark.anyio
async def test_a_window_nobody_recorded_is_NOT_offered_against_a_floor(
    client, seeded_models, test_session, caplog
):
    """A row with no recorded window is NOT offered when a floor is stated.

    THE PREMISE OF THIS TEST WAS REVERSED ON PURPOSE (2026-09-28). It used to assert the
    opposite — "a NULL window escapes the floor check, so it is offered" — and the
    reversal IS the decision rather than a tidy-up: the floor is a `>=` claim, NULL is not
    a number that satisfies it, and such a row's honest state is "unknown", not "meets the
    floor". The Model Browser's own context filter has always read unknown as 0 and
    excluded it; the matcher now agrees with it.

    What the old assertion protected — that the row is not SILENTLY dropped — survives as
    the log line asserted below.
    """
    import logging

    from app.infrastructure.database.models import CuratedModel

    provider = (await test_session.execute(
        select(Provider).where(Provider.name == "ollama")
    )).scalar_one()
    test_session.add(CuratedModel(
        model_id="codellama:latest", model_name="Code Llama",
        provider_id=provider.id, is_free=True, thinking="none", location="local",
        context_length=None,
    ))
    await test_session.commit()

    with caplog.at_level(logging.WARNING, logger="app.domain.providers.curated_models_service"):
        r = await client.post("/api/v1/curated-models/match", json={
            "thinking": "none", "location": "local", "min_context": 100000,
        })

    d = r.json()
    ids = {c["model_id"] for c in d["candidates"]}
    assert "codellama:latest" not in ids   # nothing recorded it, so it proves nothing
    assert "llama3.2:latest" in ids        # a LOCAL row whose window IS recorded
    assert "NOT OFFERED" in caplog.text    # excluded, and never silently
    assert "codellama:latest" in caplog.text


@pytest.mark.anyio
async def test_a_window_nobody_recorded_is_still_offered_when_NO_floor_is_stated(
    client, seeded_models, test_session, caplog
):
    """The other half, kept: with no floor there is nothing to prove, so the row is
    offered — and the window-fit warning is what says its window is unknown.

    Both states are named because they are different questions: a floor is a promise the
    matcher must keep, and a model nobody measured is a thing to record, not to hide.
    """
    import logging

    from app.infrastructure.database.models import CuratedModel

    provider = (await test_session.execute(
        select(Provider).where(Provider.name == "ollama")
    )).scalar_one()
    test_session.add(CuratedModel(
        model_id="codellama:latest", model_name="Code Llama",
        provider_id=provider.id, is_free=True, thinking="none", location="local",
        context_length=None,
    ))
    await test_session.commit()

    with caplog.at_level(logging.WARNING, logger="app.domain.providers.curated_models_service"):
        r = await client.post("/api/v1/curated-models/match", json={
            "thinking": "none", "location": "local",
        })

    d = r.json()
    ids = {c["model_id"] for c in d["candidates"]}
    assert "codellama:latest" in ids
    assert "WINDOW UNKNOWN" in caplog.text


@pytest.mark.anyio
async def test_a_grant_below_the_declaration_warns_at_match_time(
    client, seeded_models, caplog
):
    """G4: the provider's own output grant is named where the pairing is decided.

    `top_provider.max_completion_tokens` was parsed and then unused — a declaration
    above it is cut by the provider, and the operator should hear that at match time
    rather than meet it as a truncated answer.
    """
    import logging

    session = seeded_models
    provider = (
        await session.execute(select(Provider).where(Provider.name == "openrouter"))
    ).scalar_one()
    session.add(
        ProviderModelCache(
            provider_id=provider.id,
            model_id="deepseek/deepseek-v4-flash",
            name="deepseek/deepseek-v4-flash",
            in_context_training=False,
            function_calling=False,
            is_cached=True,
            context_length=1000000,
            raw_data={
                "id": "deepseek/deepseek-v4-flash",
                "top_provider": {"max_completion_tokens": 32768},
            },
        )
    )
    await session.commit()

    with caplog.at_level(logging.WARNING, logger="app.domain.providers.curated_models_service"):
        response = await client.post(
            "/api/v1/curated-models/match",
            json={"thinking": "none", "max_output": 49152},
        )

    assert response.status_code == 200
    assert "PAIRING ADVICE" in caplog.text
    assert "grants at most 32768" in caplog.text
    assert "49152 will be asked for" in caplog.text


@pytest.mark.anyio
async def test_a_thinking_driver_announces_the_floor_at_match_time(
    client, seeded_models, caplog
):
    import logging

    """G5's residue: the declared number is not the number that goes out for a reasoner."""
    import logging

    with caplog.at_level(logging.WARNING, logger="app.domain.providers.curated_models_service"):
        response = await client.post(
            "/api/v1/curated-models/match",
            json={"thinking": "high", "max_output": 4096},
        )

    assert response.status_code == 200
    assert "PAIRING ADVICE" in caplog.text
    assert "floored at 16000" in caplog.text


@pytest.mark.anyio
async def test_the_ranking_is_cost_first_then_the_model_id(client, seeded_models):
    """R3, PINNED: candidates rank `(is_free, model_id)` — cost first, then the id.

    The editorial `featured` flag that used to sit BETWEEN these two keys went with the
    column (this arc's Phase 3), and `prefer_free` — the parameter that documented itself
    as this ordering's control and was passed by NOTHING (one hit tree-wide: its own
    signature) — retired in the same commit.

    The fixture makes this test pass only for the RIGHT reason: ordering by `model_id`
    ALONE would put `deepseek/deepseek-v4-flash` (paid) FIRST, so a green here cannot be
    an id-order in disguise. The free rows themselves also pin the tie-break — they come
    back in id order, which is why the expected list is not the fixture's own order.
    """
    response = await client.post(
        "/api/v1/curated-models/match",
        json={"thinking": "none", "location": "any"},
    )
    assert response.status_code == 200
    assert [c["model_id"] for c in response.json()["candidates"]] == [
        "llama3.2:latest",
        "qwen/qwen3-next-80b-a3b-instruct",
        "qwen/qwen3.8-max",
        "deepseek/deepseek-v4-flash",
    ]


@pytest.mark.anyio
async def test_an_unpriced_row_ranks_after_a_priced_one(client, seeded_models):
    """Phase 4's third state has a POSITION: free, then priced, then unpriced.

    `not m["is_free"]` — the shape that ranked this list before this phase — reads `None`
    as TRUTHY, so a row nobody priced would have sorted as PAID: a cost claim no provider
    made, ranking ahead of a model whose price the catalog actually states. The fixture's
    paid row is deliberately `deepseek/...` (first by model id) so a green here cannot be
    id-order in disguise.
    """
    orp = await _get_or_create_provider(seeded_models, "openrouter")
    seeded_models.add(
        CuratedModel(
            model_id="aai/never-priced",
            model_name="Never Priced",
            provider_id=orp.id,
            is_free=None,
            thinking="none",
            location="cloud",
            context_length=128000,
        )
    )
    await seeded_models.commit()

    response = await client.post(
        "/api/v1/curated-models/match",
        json={"thinking": "none", "location": "any"},
    )
    assert response.status_code == 200
    assert [c["model_id"] for c in response.json()["candidates"]] == [
        "llama3.2:latest",
        "qwen/qwen3-next-80b-a3b-instruct",
        "qwen/qwen3.8-max",
        "deepseek/deepseek-v4-flash",   # priced — and still ahead of the unknown
        "aai/never-priced",             # unpriced: last, because it claims nothing
    ]
