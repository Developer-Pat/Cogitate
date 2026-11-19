"""The curated-models API — CRUD plus the validation on create.

Covers:
- CRUD lifecycle (list/create/get/update/delete)
- Provider filtering
- Validation (bad category, duplicate, missing provider)
- FK enforcement
"""

import logging

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import delete, select

from app.infrastructure.database.models import CuratedModel, Provider, ProviderModelCache


@pytest.fixture
async def test_providers(test_engine) -> dict:
    """The provider rows curated models need for their FK — created only if absent.

    REUSE, not a blind insert: the session-scoped ``test_engine`` seeds this database from
    the real one, which already carries ``openrouter`` and ``ollama``, while the suite's
    ``auto_clean_tables`` fixture truncates only AFTER each test — so an insert here
    collides whenever this file is the session's first test file (measured:
    ``UNIQUE constraint failed: providers.name``).
    """
    wanted = [("openrouter", "openrouter"), ("ollama", "ollama")]
    async with AsyncSession(test_engine) as session:
        ids: dict = {}
        for name, provider_type in wanted:
            provider = (
                await session.execute(select(Provider).where(Provider.name == name))
            ).scalar_one_or_none()
            if provider is None:
                provider = Provider(
                    name=name, provider_type=provider_type, is_active=True
                )
                session.add(provider)
                await session.commit()
                await session.refresh(provider)
            ids[name] = provider.id
        return ids


class TestCuratedModelsAPI:
    """Integration tests for /api/v1/curated-models endpoints."""

    @pytest.mark.anyio
    async def test_list_empty(
        self, client: AsyncClient, test_engine, test_providers
    ) -> None:
        """List returns an empty array when nothing is curated.

        The session-scoped database is seeded from the real one, and the suite's cleanup
        runs only AFTER each test — so this empties the table itself instead of assuming a
        fresh one. The assumption held only when some earlier test file happened to run
        first; as this file's own first test it read the seeded rows (measured: 12).
        """
        async with AsyncSession(test_engine) as session:
            await session.execute(delete(CuratedModel))
            await session.commit()

        response = await client.get("/api/v1/curated-models")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    @pytest.mark.anyio
    async def test_create_model(
        self, client: AsyncClient, test_providers
    ) -> None:
        """Create a curated model returns 201 with correct data."""
        response = await client.post(
            "/api/v1/curated-models",
            json={
                "provider": "openrouter",
                "model_id": "test/sample-model",
                "model_name": "Sample Model",
                "category": "chat",
                "context_length": 128000,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["model_id"] == "test/sample-model"
        assert data["model_name"] == "Sample Model"
        assert data["provider"] == "openrouter"
        assert data["category"] == "chat"
        assert data["context_length"] == 128000
        # Phase 4: the cost is DERIVED from the provider's cached pricing, and this model has no
        # cached payload at all — so the row says UNKNOWN rather than the "paid" a False default
        # used to claim. (The derivation's own cases live in `TestTheCostIsDerived`.)
        assert data["is_free"] is None
        assert data["is_active"] is True
        # `sort_order` was RETIRED in this arc's Phase 2 — it must not come back on the
        # wire either, or a client would read a field the API no longer carries.
        assert "sort_order" not in data
        # ...and `featured` went the same way in Phase 3 (the standing ruling: assert the
        # ABSENCE on the response, or a client keeps reading a field the API dropped).
        assert "featured" not in data
        assert data["id"] is not None
        # verified is EARNED by model sync, not settable at create
        assert data["verified"] is False

    @pytest.mark.anyio
    async def test_create_duplicate_model(
        self, client: AsyncClient, test_providers
    ) -> None:
        """Creating a duplicate (provider, model_id) returns 400."""
        payload = {
            "provider": "openrouter",
            "model_id": "test/dup",
            "model_name": "Dup",
        }
        first = await client.post("/api/v1/curated-models", json=payload)
        assert first.status_code == 201
        second = await client.post("/api/v1/curated-models", json=payload)
        assert second.status_code == 400
        assert "already curated" in second.json()["detail"]

    @pytest.mark.anyio
    async def test_create_missing_provider(
        self, client: AsyncClient, test_providers
    ) -> None:
        """Creating with an unknown provider returns 400."""
        response = await client.post(
            "/api/v1/curated-models",
            json={
                "provider": "does-not-exist",
                "model_id": "x/y",
                "model_name": "X",
            },
        )
        assert response.status_code == 400
        assert "Provider not found" in response.json()["detail"]

    @pytest.mark.anyio
    async def test_create_invalid_category(
        self, client: AsyncClient, test_providers
    ) -> None:
        """Creating with an invalid category returns 400."""
        response = await client.post(
            "/api/v1/curated-models",
            json={
                "provider": "openrouter",
                "model_id": "test/badcat",
                "model_name": "BadCat",
                "category": "not-a-real-category",
            },
        )
        assert response.status_code == 400
        assert "Invalid category" in response.json()["detail"]

    @pytest.mark.anyio
    async def test_get_model(
        self, client: AsyncClient, test_providers
    ) -> None:
        """Get a single curated model by id."""
        created = await client.post(
            "/api/v1/curated-models",
            json={
                "provider": "openrouter",
                "model_id": "test/getme",
                "model_name": "Get Me",
            },
        )
        assert created.status_code == 201
        cid = created.json()["id"]

        response = await client.get(f"/api/v1/curated-models/{cid}")
        assert response.status_code == 200
        assert response.json()["model_id"] == "test/getme"

    @pytest.mark.anyio
    async def test_get_missing_model(
        self, client: AsyncClient, test_providers
    ) -> None:
        """Get a non-existent curated model returns 404."""
        response = await client.get("/api/v1/curated-models/999999")
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_update_model(
        self, client: AsyncClient, test_providers
    ) -> None:
        """Update category/is_active on a curated model.

        The premise of this test was REVERSED on purpose in Phase 2: it used to send
        and assert `sort_order` (the field is retired — see the two refusal tests below).
        `featured` followed in Phase 3, so the update no longer sends it either.
        """
        created = await client.post(
            "/api/v1/curated-models",
            json={
                "provider": "ollama",
                "model_id": "test/update-me",
                "model_name": "Update Me",
                "category": "chat",
            },
        )
        assert created.status_code == 201
        cid = created.json()["id"]

        response = await client.put(
            f"/api/v1/curated-models/{cid}",
            json={
                "category": "code",
                "is_active": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "code"
        assert "sort_order" not in data
        assert "featured" not in data
        assert data["is_active"] is False

    @pytest.mark.anyio
    async def test_create_refuses_the_retired_sort_order(
        self, client: AsyncClient, test_providers
    ) -> None:
        """A create still carrying `sort_order` is REFUSED, not silently ignored.

        The standing ruling: a retired key that is merely ignored is the worst option —
        the writer keeps succeeding while its value goes nowhere. So the request is
        refused with the reason, and nothing is stored.
        """
        response = await client.post(
            "/api/v1/curated-models",
            json={
                "provider": "openrouter",
                "model_id": "test/retired-key",
                "model_name": "Retired Key",
                "sort_order": 3,
            },
        )
        assert response.status_code == 422
        assert "sort_order" in response.text
        assert "retired" in response.text

        listed = await client.get("/api/v1/curated-models?provider=openrouter")
        assert all(m["model_id"] != "test/retired-key" for m in listed.json())

    @pytest.mark.anyio
    async def test_update_refuses_the_retired_sort_order(
        self, client: AsyncClient, test_providers
    ) -> None:
        """The same key on the UPDATE path is refused too."""
        created = await client.post(
            "/api/v1/curated-models",
            json={
                "provider": "openrouter",
                "model_id": "test/retired-key-update",
                "model_name": "Retired Key Update",
            },
        )
        assert created.status_code == 201
        cid = created.json()["id"]

        response = await client.put(
            f"/api/v1/curated-models/{cid}",
            json={"category": "code", "sort_order": 42},
        )
        assert response.status_code == 422
        assert "retired" in response.text

    @pytest.mark.anyio
    async def test_create_refuses_the_retired_featured(
        self, client: AsyncClient, test_providers
    ) -> None:
        """A create still carrying `featured` is REFUSED, not silently ignored.

        The same ruling as `sort_order`: pydantic IGNORES an unknown key by default, so
        without this guard the request answers 201 while the value goes nowhere — a writer
        succeeding with its input dropped, indistinguishable from a working save. The flag's
        home is gone (the arc's Phase 3) and nothing replaces it; the request must say so,
        and nothing may be stored.
        """
        response = await client.post(
            "/api/v1/curated-models",
            json={
                "provider": "openrouter",
                "model_id": "test/retired-featured",
                "model_name": "Retired Featured",
                "category": "chat",
                "featured": True,
            },
        )
        assert response.status_code == 422
        assert "featured" in response.text
        assert "retired" in response.text

        listed = await client.get("/api/v1/curated-models?provider=openrouter")
        assert all(m["model_id"] != "test/retired-featured" for m in listed.json())

    @pytest.mark.anyio
    async def test_update_refuses_the_retired_featured(
        self, client: AsyncClient, test_providers
    ) -> None:
        """The same key on the UPDATE path is refused too — and the row is left untouched."""
        created = await client.post(
            "/api/v1/curated-models",
            json={
                "provider": "openrouter",
                "model_id": "test/retired-featured-update",
                "model_name": "Retired Featured Update",
                "category": "chat",
            },
        )
        assert created.status_code == 201
        cid = created.json()["id"]

        response = await client.put(
            f"/api/v1/curated-models/{cid}",
            json={"category": "code", "featured": False},
        )
        assert response.status_code == 422
        assert "retired" in response.text

        # The refusal is not a partial write: the row still says what it said.
        listed = await client.get("/api/v1/curated-models?provider=openrouter")
        row = next(m for m in listed.json() if m["id"] == cid)
        assert row["category"] == "chat"

    @pytest.mark.anyio
    async def test_the_list_is_ordered_by_provider_then_model_id(
        self, client: AsyncClient, test_providers
    ) -> None:
        """The server's order is its guarantee to a client that does not sort.

        `sort_order` used to be that guarantee. It is gone, so the order is
        `(provider, model_id)` — asserted here as a property (the whole list is sorted)
        rather than against a fixed sequence, so rows other tests leave behind cannot
        make this brittle.
        """
        for provider, model_id in (
            ("openrouter", "zzz/last"),
            ("openrouter", "aaa/first"),
            ("ollama", "mmm/middle"),
        ):
            created = await client.post(
                "/api/v1/curated-models",
                json={"provider": provider, "model_id": model_id, "model_name": model_id},
            )
            assert created.status_code == 201

        response = await client.get("/api/v1/curated-models")
        assert response.status_code == 200
        keys = [(m["provider"], m["model_id"]) for m in response.json()]
        assert keys == sorted(keys)

        mine = [k for k in keys if k[1] in ("zzz/last", "aaa/first", "mmm/middle")]
        assert mine == [
            ("ollama", "mmm/middle"),
            ("openrouter", "aaa/first"),
            ("openrouter", "zzz/last"),
        ]

    @pytest.mark.anyio
    async def test_update_missing_model(
        self, client: AsyncClient, test_providers
    ) -> None:
        """Update a non-existent curated model returns 404."""
        response = await client.put(
            "/api/v1/curated-models/999999",
            json={"category": "code"},
        )
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_delete_model(
        self, client: AsyncClient, test_providers
    ) -> None:
        """Delete a curated model removes it."""
        created = await client.post(
            "/api/v1/curated-models",
            json={
                "provider": "openrouter",
                "model_id": "test/delete-me",
                "model_name": "Delete Me",
            },
        )
        assert created.status_code == 201
        cid = created.json()["id"]

        response = await client.delete(f"/api/v1/curated-models/{cid}")
        assert response.status_code == 204

        # Now 404 on get
        get_resp = await client.get(f"/api/v1/curated-models/{cid}")
        assert get_resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_missing_model(
        self, client: AsyncClient, test_providers
    ) -> None:
        """Delete a non-existent curated model returns 404."""
        response = await client.delete("/api/v1/curated-models/999999")
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_list_filter_by_provider(
        self, client: AsyncClient, test_providers
    ) -> None:
        """List filtered by provider only returns that provider's models."""
        await client.post(
            "/api/v1/curated-models",
            json={"provider": "openrouter", "model_id": "a/one", "model_name": "A One"},
        )
        await client.post(
            "/api/v1/curated-models",
            json={"provider": "ollama", "model_id": "b/two", "model_name": "B Two"},
        )

        response = await client.get("/api/v1/curated-models?provider=ollama")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["model_id"] == "b/two"
        assert data[0]["provider"] == "ollama"


class TestTheCapabilityDimensions:
    """`thinking` / `location` — the deliberate setter (F.3's label gains a CRUD path).

    Every assertion reads the ROW back through its own session rather than the response
    body: the claim is "the stored value is what was sent", and a response could agree
    with the request while the row said something else.
    """

    @staticmethod
    async def _row(test_engine, cid: int) -> CuratedModel:
        async with AsyncSession(test_engine) as session:
            return (
                await session.execute(
                    select(CuratedModel).where(CuratedModel.id == cid)
                )
            ).scalar_one()

    @pytest.mark.anyio
    async def test_create_stores_what_was_sent(
        self, client: AsyncClient, test_engine, test_providers
    ) -> None:
        """A create carrying the two dimensions stores exactly those values."""
        created = await client.post(
            "/api/v1/curated-models",
            json={
                "provider": "openrouter",
                "model_id": "test/thinks-hard",
                "model_name": "Thinks Hard",
                "thinking": "high",
                "location": "local",
            },
        )
        assert created.status_code == 201
        row = await self._row(test_engine, created.json()["id"])
        assert (row.thinking, row.location) == ("high", "local")

    @pytest.mark.anyio
    async def test_create_defaults_the_dimensions(
        self, client: AsyncClient, test_engine, test_providers
    ) -> None:
        """Sending neither dimension stores the schema's defaults, not NULL."""
        created = await client.post(
            "/api/v1/curated-models",
            json={
                "provider": "openrouter",
                "model_id": "test/undeclared-driver",
                "model_name": "Undeclared Driver",
            },
        )
        assert created.status_code == 201
        row = await self._row(test_engine, created.json()["id"])
        assert (row.thinking, row.location) == ("none", "cloud")

    @pytest.mark.anyio
    async def test_create_refuses_an_unknown_dimension(
        self, client: AsyncClient, test_providers
    ) -> None:
        """A level or home outside the vocabulary is refused, and no row is written.

        `thinking` is load-bearing (it ranks the substitution matcher and feeds the
        output-budget floor), so an unreadable value would rank 0 and read as "does not
        think". `location` is compared exactly, so "any" — a SPEC-side tolerance — is not
        a home a row can state.
        """
        for field, value in (("thinking", "high3"), ("location", "any")):
            response = await client.post(
                "/api/v1/curated-models",
                json={
                    "provider": "openrouter",
                    "model_id": f"test/refused-{field}",
                    "model_name": "Refused",
                    field: value,
                },
            )
            assert response.status_code == 422, f"{field}={value!r} was accepted"

        listed = await client.get("/api/v1/curated-models?provider=openrouter")
        written = [m["model_id"] for m in listed.json()]
        assert "test/refused-thinking" not in written
        assert "test/refused-location" not in written

    @pytest.mark.anyio
    async def test_update_moves_the_dimensions(
        self, client: AsyncClient, test_engine, test_providers
    ) -> None:
        """An update sets the two dimensions on an existing row."""
        created = await client.post(
            "/api/v1/curated-models",
            json={
                "provider": "openrouter",
                "model_id": "test/reclassified",
                "model_name": "Reclassified",
                "thinking": "none",
            },
        )
        assert created.status_code == 201
        cid = created.json()["id"]

        response = await client.put(
            f"/api/v1/curated-models/{cid}",
            json={"thinking": "mandatory", "location": "local"},
        )
        assert response.status_code == 200
        row = await self._row(test_engine, cid)
        assert (row.thinking, row.location) == ("mandatory", "local")

    @pytest.mark.anyio
    async def test_update_leaves_the_dimensions_alone_when_not_sent(
        self, client: AsyncClient, test_engine, test_providers
    ) -> None:
        """Not sending a dimension leaves it — the path is overwrite-only."""
        created = await client.post(
            "/api/v1/curated-models",
            json={
                "provider": "openrouter",
                "model_id": "test/untouched-label",
                "model_name": "Untouched Label",
                "thinking": "high",
                "location": "local",
            },
        )
        assert created.status_code == 201
        cid = created.json()["id"]

        response = await client.put(
            f"/api/v1/curated-models/{cid}", json={"model_name": "Renamed"}
        )
        assert response.status_code == 200
        row = await self._row(test_engine, cid)
        assert (row.model_name, row.thinking, row.location) == ("Renamed", "high", "local")

    @pytest.mark.anyio
    async def test_update_refuses_an_unknown_dimension(
        self, client: AsyncClient, test_engine, test_providers
    ) -> None:
        """An unknown level or home is refused on update too, and the row is unchanged."""
        created = await client.post(
            "/api/v1/curated-models",
            json={
                "provider": "openrouter",
                "model_id": "test/stubborn-label",
                "model_name": "Stubborn Label",
                "thinking": "high",
            },
        )
        assert created.status_code == 201
        cid = created.json()["id"]

        for field, value in (("thinking", "MANDATORY"), ("location", "disk")):
            response = await client.put(
                f"/api/v1/curated-models/{cid}", json={field: value}
            )
            assert response.status_code == 422, f"{field}={value!r} was accepted"

        row = await self._row(test_engine, cid)
        assert (row.thinking, row.location) == ("high", "cloud")


class TestTheRowIsBornVerified:
    """G1 + G3: a create READS the provider's claim, and the row is born carrying it.

    The claim is the fact the intake used to leave in prose (the row's description) or
    nowhere at all, so a driver whose payload says `reasoning: {mandatory: true}` sat on
    the list labelled `none` — excluded by the substitution matcher and reading as "does
    not think" — and every new row was unverified until somebody remembered to check it.
    These tests put the payload in the cache and assert the ROW, plus the log line that
    reports a disagreement."""

    @staticmethod
    async def _cache_claim(
        test_engine, provider_name: str, model_id: str, reasoning: dict,
        context_length: int | None = None,
    ) -> None:
        """One cached catalog row, shaped like the discovery fetch writes it."""
        async with AsyncSession(test_engine) as session:
            provider = (
                await session.execute(select(Provider).where(Provider.name == provider_name))
            ).scalar_one()
            session.add(
                ProviderModelCache(
                    provider_id=provider.id,
                    model_id=model_id,
                    name=model_id,
                    in_context_training=False,
                    function_calling=False,
                    is_cached=True,
                    context_length=context_length,
                    raw_data={"id": model_id, "name": model_id, "reasoning": reasoning},
                )
            )
            await session.commit()

    @staticmethod
    async def _row(test_engine, cid: int) -> CuratedModel:
        async with AsyncSession(test_engine) as session:
            return (
                await session.execute(select(CuratedModel).where(CuratedModel.id == cid))
            ).scalar_one()

    @pytest.mark.anyio
    async def test_create_records_a_mandatory_claim(
        self, client: AsyncClient, test_engine, test_providers
    ) -> None:
        """A mandatory driver is never born `none` — the label comes off the payload."""
        await self._cache_claim(
            test_engine, "openrouter", "test/mandatory-driver",
            {"mandatory": True, "default_effort": "max"},
        )

        created = await client.post(
            "/api/v1/curated-models",
            json={
                "provider": "openrouter",
                "model_id": "test/mandatory-driver",
                "model_name": "Mandatory Driver",
            },
        )

        assert created.status_code == 201
        assert created.json()["thinking"] == "mandatory"
        row = await self._row(test_engine, created.json()["id"])
        assert row.thinking == "mandatory"

    @pytest.mark.anyio
    async def test_create_records_a_milder_claim(
        self, client: AsyncClient, test_engine, test_providers
    ) -> None:
        """A claim that states an effort lands on our scale rather than being dropped."""
        await self._cache_claim(
            test_engine, "openrouter", "test/low-effort-driver",
            {"default_enabled": True, "default_effort": "low"},
        )

        created = await client.post(
            "/api/v1/curated-models",
            json={
                "provider": "openrouter",
                "model_id": "test/low-effort-driver",
                "model_name": "Low Effort",
            },
        )

        assert created.status_code == 201
        row = await self._row(test_engine, created.json()["id"])
        assert row.thinking == "low"

    @pytest.mark.anyio
    async def test_the_providers_record_wins_over_a_stated_level(
        self, client: AsyncClient, test_engine, test_providers, caplog
    ) -> None:
        """A stated level is the FALLBACK, and the disagreement is reported.

        The READ path resolves the claim first (`resolve_model_thinking`), so a row stating
        the opposite would be a second truth nothing acts on. Adopting the claim and
        logging it is E.4's rule, applied to the label.
        """
        await self._cache_claim(
            test_engine, "openrouter", "test/claim-and-call",
            {"mandatory": True, "default_effort": "max"},
        )

        with caplog.at_level(logging.WARNING):
            created = await client.post(
                "/api/v1/curated-models",
                json={
                    "provider": "openrouter",
                    "model_id": "test/claim-and-call",
                    "model_name": "Claim And Call",
                    "thinking": "high",
                },
            )

        assert created.status_code == 201
        assert created.json()["thinking"] == "mandatory"
        row = await self._row(test_engine, created.json()["id"])
        assert row.thinking == "mandatory"
        assert any("THINKING ADOPTED at create" in r.message for r in caplog.records)

    @pytest.mark.anyio
    async def test_a_stated_level_stands_when_the_claim_is_silent(
        self, client: AsyncClient, test_engine, test_providers
    ) -> None:
        """A payload that states no reasoning leaves the stated level alone."""
        await self._cache_claim(
            test_engine, "openrouter", "test/silent-claim", {}, context_length=131072,
        )

        created = await client.post(
            "/api/v1/curated-models",
            json={
                "provider": "openrouter",
                "model_id": "test/silent-claim",
                "model_name": "Silent Claim",
                "thinking": "high",
            },
        )

        assert created.status_code == 201
        row = await self._row(test_engine, created.json()["id"])
        assert row.thinking == "high"

    @pytest.mark.anyio
    async def test_create_adopts_the_window_and_earns_verified(
        self, client: AsyncClient, test_engine, test_providers
    ) -> None:
        """G3: the window lands on the row at create, and `verified` is earned there."""
        await self._cache_claim(
            test_engine, "openrouter", "test/window-known", {}, context_length=262144,
        )

        created = await client.post(
            "/api/v1/curated-models",
            json={
                "provider": "openrouter",
                "model_id": "test/window-known",
                "model_name": "Window Known",
            },
        )

        assert created.status_code == 201
        body = created.json()
        assert (body["context_length"], body["verified"]) == (262144, True)
        row = await self._row(test_engine, body["id"])
        assert (row.context_length, row.verified) == (262144, True)

    @pytest.mark.anyio
    async def test_a_differing_window_is_adopted_and_reported(
        self, client: AsyncClient, test_engine, test_providers, caplog
    ) -> None:
        """The provider's number is the fact; the disagreement is logged, not silent."""
        await self._cache_claim(
            test_engine, "openrouter", "test/window-differs", {}, context_length=262144,
        )

        with caplog.at_level(logging.WARNING):
            created = await client.post(
                "/api/v1/curated-models",
                json={
                    "provider": "openrouter",
                    "model_id": "test/window-differs",
                    "model_name": "Window Differs",
                    "context_length": 131072,
                },
            )

        assert created.status_code == 201
        row = await self._row(test_engine, created.json()["id"])
        assert row.context_length == 262144
        assert any("WINDOW MISMATCH at create" in r.message for r in caplog.records)

    @pytest.mark.anyio
    async def test_a_model_nobody_fetched_comes_back_unverified(
        self, client: AsyncClient, test_engine, test_providers, caplog
    ) -> None:
        """No claim is not a verified row — and the note says which it is."""
        with caplog.at_level(logging.WARNING):
            created = await client.post(
                "/api/v1/curated-models",
                json={
                    "provider": "openrouter",
                    "model_id": "test/never-fetched",
                    "model_name": "Never Fetched",
                },
            )

        assert created.status_code == 201
        body = created.json()
        assert body["verified"] is False
        assert body["context_length"] is None
        assert any("WINDOW UNVERIFIED at create" in r.message for r in caplog.records)

    @pytest.mark.anyio
    async def test_nothing_cached_records_the_honest_default(
        self, client: AsyncClient, test_engine, test_providers
    ) -> None:
        """No payload to read is not a claim of "does not think" — but the column must hold
        something, so it holds the default, stated here rather than left to the column."""
        created = await client.post(
            "/api/v1/curated-models",
            json={
                "provider": "openrouter",
                "model_id": "test/nobody-has-seen-this",
                "model_name": "Nobody Has Seen This",
            },
        )

        assert created.status_code == 201
        row = await self._row(test_engine, created.json()["id"])
        assert row.thinking == "none"


class TestTheCostIsDerived:
    """Phase 4: `is_free` is READ off the provider's cached pricing — never stated by the request.

    Three answers, and the third is why the column had to become nullable: a payload priced at
    zero is free, a payload carrying a price is paid, and a model nobody has priced is UNKNOWN —
    not the "paid" a non-nullable `default=False` used to claim. The request cannot state any of
    them: the API refuses the key on both write paths.
    """

    @staticmethod
    async def _cache_priced(
        test_engine, provider_name: str, model_id: str, pricing: dict
    ) -> None:
        """One cached catalog row carrying PRICING, shaped like the discovery fetch writes it."""
        async with AsyncSession(test_engine) as session:
            provider = (
                await session.execute(
                    select(Provider).where(Provider.name == provider_name)
                )
            ).scalar_one()
            session.add(
                ProviderModelCache(
                    provider_id=provider.id,
                    model_id=model_id,
                    name=model_id,
                    in_context_training=False,
                    function_calling=False,
                    is_cached=True,
                    raw_data={
                        "id": model_id,
                        "name": model_id,
                        "_raw": {"pricing": pricing},
                    },
                )
            )
            await session.commit()

    @pytest.mark.anyio
    async def test_the_row_says_what_the_providers_payload_says(
        self, client: AsyncClient, test_engine, test_providers
    ) -> None:
        """A payload priced at zero stores free; one carrying a price stores paid."""
        await self._cache_priced(
            test_engine, "openrouter", "test/free-model", {"prompt": "0", "completion": "0"}
        )
        await self._cache_priced(
            test_engine,
            "openrouter",
            "test/paid-model",
            {"prompt": "0.000001", "completion": "0.000002"},
        )

        for model_id, expected in (("test/free-model", True), ("test/paid-model", False)):
            created = await client.post(
                "/api/v1/curated-models",
                json={
                    "provider": "openrouter",
                    "model_id": model_id,
                    "model_name": model_id,
                },
            )
            assert created.status_code == 201, created.text
            assert created.json()["is_free"] is expected

    @pytest.mark.anyio
    async def test_a_cloud_model_nobody_has_priced_is_UNKNOWN(
        self, client: AsyncClient, test_providers
    ) -> None:
        """No price is not a price of zero: the row says UNKNOWN rather than asserting "paid"."""
        created = await client.post(
            "/api/v1/curated-models",
            json={
                "provider": "openrouter",
                "model_id": "test/nobody-priced-this",
                "model_name": "Nobody Priced This",
            },
        )
        assert created.status_code == 201, created.text
        assert created.json()["is_free"] is None

    @pytest.mark.anyio
    async def test_a_local_model_nobody_has_priced_is_FREE(
        self, client: AsyncClient, test_providers
    ) -> None:
        """The one absence with an answer: calling a local model costs nothing.

        Nothing on the live curated table is local, so this branch is proven HERE rather than on
        the page — and it is the branch that would otherwise read UNKNOWN and look like a gap.
        """
        created = await client.post(
            "/api/v1/curated-models",
            json={
                "provider": "ollama",
                "model_id": "test/local-unpriced",
                "model_name": "Local Unpriced",
                "location": "local",
            },
        )
        assert created.status_code == 201, created.text
        assert created.json()["is_free"] is True

    @pytest.mark.anyio
    async def test_create_refuses_a_stated_cost(
        self, client: AsyncClient, test_providers
    ) -> None:
        """The key is refused with its reason, and nothing is stored."""
        response = await client.post(
            "/api/v1/curated-models",
            json={
                "provider": "openrouter",
                "model_id": "test/stated-cost",
                "model_name": "Stated Cost",
                "is_free": True,
            },
        )
        assert response.status_code == 422
        assert "derived" in response.text

        listed = await client.get("/api/v1/curated-models?provider=openrouter")
        assert all(m["model_id"] != "test/stated-cost" for m in listed.json())

    @pytest.mark.anyio
    async def test_update_refuses_a_stated_cost(
        self, client: AsyncClient, test_providers
    ) -> None:
        """The same key on the UPDATE path — and the row is left exactly as it was."""
        created = await client.post(
            "/api/v1/curated-models",
            json={
                "provider": "openrouter",
                "model_id": "test/stated-cost-update",
                "model_name": "Stated Cost Update",
            },
        )
        assert created.status_code == 201
        cid = created.json()["id"]
        before = created.json()["is_free"]

        response = await client.put(
            f"/api/v1/curated-models/{cid}", json={"is_free": False}
        )
        assert response.status_code == 422
        assert "derived" in response.text

        listed = await client.get("/api/v1/curated-models?provider=openrouter")
        row = next(m for m in listed.json() if m["id"] == cid)
        assert row["is_free"] == before
