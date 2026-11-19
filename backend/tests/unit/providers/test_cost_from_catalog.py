"""The cost path reads the provider's own catalog — and its unit is per 1K tokens.

`ProviderService.PRICING` is eleven hand-added entries. The catalog
(`provider_model_cache`) is what the app actually fetched from each provider and shows in
the model picker — 434 of 460 openrouter models priced, 2 of 2 deepseek. The cost path read
the dict and never the catalog, so the usage page showed $0.00 for the model actually in
use while its real price sat in the table, unread.

Four things are pinned here, because four things can go quietly wrong — plus a fifth, on the
WRITING side:

* the catalog price REACHES the cost site and WINS over the built-in table;
* the CONVERSION is right — the catalog stores per TOKEN and `calculate_cost` works per 1K,
  so a 1000x slip still reads as a plausible number. A token count with a known answer
  guards it;
* every WRITER stores per TOKEN — the reader is only right if its writers agree with it. A
  writer on another unit (deepseek briefly stored per 1K) is 1000x wrong and looks plausible;
* a ZERO is not a price: a provider that publishes nothing gets `0.0` written into the
  cache (groq, ollama_cloud and llama all read zero), so an all-zero row must fall through
  to the honest fallback rather than let the app claim the model is free;
* IDENTITY: the wire carries `provider/model`, the catalog carries what the provider calls
  it — and an id that is itself `vendor/model` must keep its inner slash.

Provider rows are named per test (`zz-…` + a uuid): the test database is seeded from a real
one, so the live provider names are already taken and `providers` is not among the tables
the fixture clears.
"""

import uuid
from typing import Optional

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.providers.cache_service import ProviderModelCacheService
from app.domain.providers.deepseek_client import DeepseekClient
from app.domain.providers.services import ProviderService
from app.infrastructure.database.models import Provider, ProviderModelCache

# The live case: absent from PRICING, priced by the openrouter catalog.
CATALOG_ID = "inclusionai/ling-3.0-flash"
WIRE_MODEL = f"openrouter/{CATALOG_ID}"


def _unique(prefix: str) -> str:
    return f"zz-{prefix}-{uuid.uuid4().hex[:8]}"


async def _provider(session: AsyncSession, name: str) -> Provider:
    row = Provider(
        name=name,
        display_name=name,
        provider_type="openrouter",
        is_active=True,
        priority=99,
        config={},
    )
    session.add(row)
    await session.flush()
    return row


async def _cached(
    session: AsyncSession,
    provider: Provider,
    model_id: str,
    prompt: Optional[float],
    completion: Optional[float],
) -> None:
    """A catalog row as discovery writes it — `pricing_*` are PER TOKEN."""
    session.add(
        ProviderModelCache(
            provider_id=provider.id,
            model_id=model_id,
            name=model_id,
            pricing_prompt=prompt,
            pricing_completion=completion,
            is_cached=True,
        )
    )
    await session.flush()


class TestTheCatalogPriceIsTheOneTheCostUses:
    @pytest.mark.anyio
    async def test_the_catalog_price_reaches_the_cost_and_wins(
        self, test_session: AsyncSession
    ) -> None:
        name = _unique("catalog")
        provider = await _provider(test_session, name)
        await _cached(test_session, provider, CATALOG_ID, 2.1e-08, 6.3e-08)

        pricing = await ProviderModelCacheService().pricing_for_model(
            test_session, name, f"{name}/{CATALOG_ID}"
        )

        assert pricing == {"prompt": pytest.approx(2.1e-05), "completion": pytest.approx(6.3e-05)}
        cost = ProviderService().calculate_cost("openrouter", WIRE_MODEL, 1000, 1000, pricing=pricing)
        # `calculate_cost` rounds to 6 decimals, so the expectation is the rounded sum.
        assert cost == pytest.approx(round(2.1e-05 + 6.3e-05, 6))

    @pytest.mark.anyio
    async def test_the_stored_unit_is_per_token_and_the_cost_site_works_per_1k(
        self, test_session: AsyncSession
    ) -> None:
        """$1 per million tokens: 1e-06 per token, so 1000 of them cost 1e-03 — not 1e-06."""
        name = _unique("unit")
        provider = await _provider(test_session, name)
        await _cached(test_session, provider, "vendor/pricey", 1e-06, 2e-06)

        pricing = await ProviderModelCacheService().pricing_for_model(
            test_session, name, f"{name}/vendor/pricey"
        )

        assert pricing == {"prompt": pytest.approx(1e-03), "completion": pytest.approx(2e-03)}
        cost = ProviderService().calculate_cost(
            "openrouter", "openrouter/vendor/pricey", 1000, 0, pricing=pricing
        )
        assert cost == pytest.approx(1e-03)
        assert cost != pytest.approx(1e-06)

    @pytest.mark.anyio
    async def test_the_catalog_price_beats_the_built_in_table(self, test_session: AsyncSession) -> None:
        """The two disagree for this model, so which one answered is visible in the number."""
        name = _unique("wins")
        provider = await _provider(test_session, name)
        # The openrouter catalog's own row for a model PRICING also carries.
        await _cached(test_session, provider, "deepseek/deepseek-v4-flash", 7.63e-08, 1.526e-07)

        pricing = await ProviderModelCacheService().pricing_for_model(
            test_session, name, f"{name}/deepseek/deepseek-v4-flash"
        )

        assert pricing == {"prompt": pytest.approx(7.63e-05), "completion": pytest.approx(1.526e-04)}
        cost = ProviderService().calculate_cost(
            "openrouter", "openrouter/deepseek/deepseek-v4-flash", 1000, 1000, pricing=pricing
        )
        assert cost == pytest.approx(round(7.63e-05 + 1.526e-04, 6))
        # PRICING's own entry for the same id is a different number (8e-05 / 1.59e-04).
        assert cost != pytest.approx(0.000080 + 0.000159)

    def test_without_a_catalog_price_the_built_in_table_still_answers(self, caplog) -> None:
        """The regression guard: the fallback still computes, and still says nothing inactive."""
        with caplog.at_level("WARNING"):
            cost = ProviderService().calculate_cost(
                "deepseek", "deepseek/deepseek-v4-flash", 1000, 1000
            )

        assert cost > 0
        assert not any("cost limit inactive" in r.getMessage() for r in caplog.records)


class TestAZeroIsNotAPrice:
    @pytest.mark.anyio
    async def test_an_all_zero_row_is_not_a_price(self, test_session: AsyncSession) -> None:
        """groq's shape: fifteen rows, every one of them zero, meaning "no price published"."""
        name = _unique("zero")
        provider = await _provider(test_session, name)
        await _cached(test_session, provider, "llama-3.3-70b-versatile", 0.0, 0.0)

        assert (
            await ProviderModelCacheService().pricing_for_model(
                test_session, name, f"{name}/llama-3.3-70b-versatile"
            )
            is None
        )

    @pytest.mark.anyio
    async def test_a_null_row_is_not_a_price(self, test_session: AsyncSession) -> None:
        name = _unique("null")
        provider = await _provider(test_session, name)
        await _cached(test_session, provider, "vendor/silent", None, None)

        assert (
            await ProviderModelCacheService().pricing_for_model(
                test_session, name, f"{name}/vendor/silent"
            )
            is None
        )

    @pytest.mark.anyio
    async def test_a_model_no_provider_prices_is_not_a_price(self, test_session: AsyncSession) -> None:
        name = _unique("absent")
        await _provider(test_session, name)

        assert (
            await ProviderModelCacheService().pricing_for_model(
                test_session, name, f"{name}/nobody/unknown"
            )
            is None
        )

    @pytest.mark.anyio
    async def test_an_all_zero_row_leaves_the_honest_fallback_in_place(
        self, test_session: AsyncSession, caplog
    ) -> None:
        """Nothing priced it, so the number stays $0 AND says why (D8, not a silent free)."""
        name = _unique("honest")
        provider = await _provider(test_session, name)
        await _cached(test_session, provider, "llama-3.3-70b-versatile", 0.0, 0.0)
        pricing = await ProviderModelCacheService().pricing_for_model(
            test_session, name, f"{name}/llama-3.3-70b-versatile"
        )

        with caplog.at_level("WARNING"):
            cost = ProviderService().calculate_cost(
                name, f"{name}/llama-3.3-70b-versatile", 1000, 1000, pricing=pricing
            )

        assert cost == 0.0
        line = next(r.getMessage() for r in caplog.records if "no pricing" in r.getMessage())
        assert "cost limit inactive" in line


class TestTheIdentity:
    @pytest.mark.anyio
    async def test_the_catalog_id_matches_with_or_without_the_provider_prefix(
        self, test_session: AsyncSession
    ) -> None:
        name = _unique("both")
        provider = await _provider(test_session, name)
        await _cached(test_session, provider, CATALOG_ID, 2.1e-08, 6.3e-08)
        service = ProviderModelCacheService()

        wire = await service.pricing_for_model(test_session, name, f"{name}/{CATALOG_ID}")
        bare = await service.pricing_for_model(test_session, name, CATALOG_ID)

        assert wire is not None and bare is not None
        assert wire == bare

    @pytest.mark.anyio
    async def test_a_bare_vendor_model_id_is_not_reduced_to_its_last_segment(
        self, test_session: AsyncSession
    ) -> None:
        """`vendor/model` and `model` can be two DIFFERENT models with different prices.

        Only the calling provider's own prefix may come off: an implementation that took the
        last path segment, or stripped any `something/`, would answer with the wrong row here.
        """
        name = _unique("segment")
        provider = await _provider(test_session, name)
        await _cached(test_session, provider, "vendor/model", 1e-06, 1e-06)
        await _cached(test_session, provider, "model", 9e-05, 9e-05)

        pricing = await ProviderModelCacheService().pricing_for_model(test_session, name, "vendor/model")

        assert pricing == {"prompt": pytest.approx(1e-03), "completion": pytest.approx(1e-03)}

    @pytest.mark.anyio
    async def test_another_providers_catalog_does_not_answer(self, test_session: AsyncSession) -> None:
        name_a = _unique("owner")
        name_b = _unique("other")
        provider_a = await _provider(test_session, name_a)
        await _provider(test_session, name_b)
        await _cached(test_session, provider_a, "some-model", 1e-06, 1e-06)

        assert (
            await ProviderModelCacheService().pricing_for_model(test_session, name_b, f"{name_a}/some-model")
            is None
        )
        assert (
            await ProviderModelCacheService().pricing_for_model(test_session, name_a, "some-model")
            is not None
        )


class TestTheWritersStorePerToken:
    """The contract's other half. The reader is pinned above; a WRITER on another unit is the
    bug, because the reader would then convert a per-1K number as if it were per token.

    deepseek did exactly that: `_per_1k` stored per 1K, so `pricing_for_model` (per token x 1000)
    answered 1000x the real price for any deepseek CATALOG row — and the number still looked like
    a number, which is why it survived. No network here: `_transform_model` is pure.
    """

    def test_deepseek_stores_per_token(self) -> None:
        model = DeepseekClient("test-key")._transform_model({"id": "deepseek-v4-pro"})

        # DEEPSEEK_MODEL_METADATA: $0.435 / 1M prompt, $0.87 / 1M completion.
        assert model["pricing_prompt"] == pytest.approx(4.35e-07)
        assert model["pricing_completion"] == pytest.approx(8.7e-07)

    @pytest.mark.anyio
    async def test_a_deepseek_catalog_row_prices_a_turn_at_the_published_rate(
        self, test_session: AsyncSession
    ) -> None:
        """$0.435 / 1M through the real reader: 1000 prompt tokens cost $0.000435, not $0.435."""
        name = _unique("deepseek-unit")
        provider = await _provider(test_session, name)
        row = DeepseekClient("test-key")._transform_model({"id": "deepseek-v4-pro"})
        await _cached(
            test_session,
            provider,
            "deepseek-v4-pro",
            row["pricing_prompt"],
            row["pricing_completion"],
        )

        pricing = await ProviderModelCacheService().pricing_for_model(
            test_session, name, "deepseek-v4-pro"
        )
        cost = ProviderService().calculate_cost(
            "deepseek", "deepseek/deepseek-v4-pro", 1000, 0, pricing=pricing
        )

        assert cost == pytest.approx(0.000435)
        assert cost != pytest.approx(0.435)
