"""API tests for the provider test endpoints — the `.env` key resolution, through the ONE read.

Phase 6, group 5: `POST /providers/{config,managed}/{id}/test` and the legacy slug route
`POST /providers/{slug}/test` all RENDER `availability.read_availability_for` now. The env-key
resolution the old managed endpoint did inline is still exercised here, because it moved rather
than vanished: a row with no key in the store is attempted with the one from the secrets file
(`EnvKeyStore`, i.e. `.env`) — which is what `read_availability_for`'s `key_for` supplies.

`EnvKeyStore` resolves `.env` under the test installation (TEST_ROOT derives from the test
database), so `set_key` here never touches the project's own file.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests import conftest as cf


@pytest.fixture
async def env_key_provider(test_engine) -> int:
    """A cloud provider with NO stored DB key (uses .env fallback).

    Found-or-created (`cf.get_or_create_provider`): the test database is a copy of a real
    installation, so a named provider is an insert into a table the copy already owns.
    """
    async with AsyncSession(test_engine) as session:
        provider = await cf.get_or_create_provider(
            session,
            name="test-groq",
            provider_type="groq",
            base_url="https://api.groq.com/openai/v1",
            is_active=True,
        )
        provider_id = provider.id
        await session.commit()
        return provider_id


class TestProviderTestEnvFallback:
    """The test endpoint must use the .env key (EnvKeyStore) when none is stored in DB."""

    @pytest.mark.anyio
    async def test_test_uses_env_key_when_no_db_key(
        self, client: AsyncClient, env_key_provider: int, monkeypatch
    ) -> None:
        # EnvKeyStore is the secrets source (DB column removed) — set a
        # deterministic key so the read picks it up.
        from app.domain.providers.env_key_store import env_key_store
        env_key_store.set_key("groq", "fake-groq-key")

        # The ONE read's probe is the seam now (the endpoint no longer opens its own client).
        from app.domain.providers import availability as av

        seen: dict = {}

        async def probe(base_url: str, path: str, headers=None):
            seen["base_url"] = base_url
            seen["headers"] = headers or {}
            return {"data": []}

        monkeypatch.setattr(av, "probe_json", probe)
        av.clear_cache()

        resp = await client.post(f"/api/v1/providers/managed/{env_key_provider}/test")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "connected"
        # The env key was used for auth
        assert seen["headers"]["Authorization"] == "Bearer fake-groq-key"


class TestTheLegacySlugRoute:
    """`POST /providers/{slug}/test` — the route the EXTERNAL AGENT's skills call.

    It keeps its slug vocabulary (`PROVIDERS`) and now maps a slug to the provider ROW of that name
    and answers from the ONE read. A slug with no row behind it says so instead of probing the
    dict's hardcoded base_url — this installation's providers are rows.
    """

    @pytest.mark.anyio
    async def test_a_slug_is_answered_from_the_one_read(
        self, client: AsyncClient, test_engine, monkeypatch
    ) -> None:
        async with AsyncSession(test_engine) as session:
            # Found-or-created — the copied database already carries `openrouter`
            # (`cf.get_or_create_provider`; inserting it is a UNIQUE violation).
            await cf.get_or_create_provider(
                session,
                name="openrouter",
                provider_type="openrouter",
                base_url="https://openrouter.ai/api/v1",
                is_active=True,
            )
            await session.commit()

        from app.domain.providers import availability as av

        async def probe(base_url: str, path: str, headers=None):
            if base_url == "https://openrouter.ai/api/v1":
                return {"data": [{"id": "a"}, {"id": "b"}]}
            return None

        monkeypatch.setattr(av, "probe_json", probe)
        monkeypatch.setattr(av, "env_key", lambda provider_type: "zz-key")
        av.clear_cache()

        resp = await client.post("/api/v1/providers/openrouter/test")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "connected"
        assert data["state"] == "available"
        assert data["models_available"] == 2

    @pytest.mark.anyio
    async def test_a_slug_with_no_row_says_so_rather_than_probing_nothing(
        self, client: AsyncClient
    ) -> None:
        """`anthropic` is a slug this route knows and no ROW backs — the honest answer is that."""
        resp = await client.post("/api/v1/providers/anthropic/test")

        assert resp.status_code == 200
        assert resp.json()["status"] == "unknown_provider"

    @pytest.mark.anyio
    async def test_an_unknown_slug_is_still_a_404(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/providers/zz-not-a-provider/test")
        assert resp.status_code == 404
