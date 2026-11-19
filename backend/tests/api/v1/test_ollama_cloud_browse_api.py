"""The Ollama Cloud browse endpoint — the key requirement and the curated annotation.

Verifies:
- Browse endpoint requires an API key for ollama_cloud (unlike local ollama)
- Router dispatch reaches the cloud browser (patched)
"""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import CuratedModel

from tests import conftest as cf


@pytest.fixture
async def ollama_cloud_provider(test_engine) -> int:
    """The `ollama_cloud` row these tests are about — FOUND, not inserted, with the copy's
    curated entries cleared off it.

    `conftest` starts the test database as a COPY of a real installation, so the operator's own
    `ollama_cloud` row is already there: inserting it is
    `UNIQUE constraint failed: providers.name`, reported as an ERROR at setup, for the first
    test a worker runs (`cf.get_or_create_provider` carries the rule). That row also arrives
    with the operator's CURATED entries on it — `gpt-oss:20b` among them — so this provider's
    curated rows are cleared here: `uq_curated_provider_model` is the same collision one level
    down, and what the tests below assert over is the slate THIS test states.
    """
    async with AsyncSession(test_engine) as session:
        provider = await cf.get_or_create_provider(
            session,
            name="ollama_cloud",
            provider_type="ollama_cloud",
            base_url="https://ollama.com",
            is_active=True,
        )
        provider_id = provider.id
        await session.execute(
            delete(CuratedModel).where(CuratedModel.provider_id == provider_id)
        )
        await session.commit()
        return provider_id


class TestOllamaCloudBrowseAPI:
    """API tests for /api/v1/providers/{id}/models/browse with ollama_cloud."""

    @pytest.mark.anyio
    async def test_browse_requires_api_key(
        self, client: AsyncClient, ollama_cloud_provider: int, monkeypatch
    ) -> None:
        """Browse without API key returns 400 for ollama_cloud.

        The router falls back to settings.ollama_cloud_api_key (.env) —
        patch it empty so the test asserts the true no-key path.
        """
        from app.core.config import get_settings
        from app.domain.providers.env_key_store import env_key_store
        monkeypatch.setattr(
            get_settings(), "ollama_cloud_api_key", ""
        )
        # EnvKeyStore is the secrets source (DB column removed) — clear it
        # so the no-key path is truly exercised.
        env_key_store.clear_key("ollama_cloud")
        response = await client.get(
            f"/api/v1/providers/{ollama_cloud_provider}/models/browse"
        )
        assert response.status_code == 400
        assert "API key not configured" in response.json()["detail"]

    @pytest.mark.anyio
    async def test_browse_with_api_key_dispatches_cloud_browser(
        self, client: AsyncClient, test_engine, ollama_cloud_provider: int
    ) -> None:
        """With API key, the cloud browser is used and returns models."""
        # Patch the singleton's browse_models to avoid real HTTP
        from app.api.v1.providers.models_router import ollama_cloud_model_browser

        from app.domain.providers.model_browser_service import ModelBrowserResult
        fake_result = ModelBrowserResult(
            models=[{"id": "llama3.3", "name": "llama3.3", "display_name": "llama3.3"}],
            total=1,
            page=1,
            page_size=50,
            total_pages=1,
            has_more=False,
            filters_applied={},
            from_cache=True,
        )
        with patch.object(
            ollama_cloud_model_browser, "browse_models", new=AsyncMock(return_value=fake_result)
        ):
            # Encrypt a key and store it on the provider (router decrypts it).
            # Keys live in .env via EnvKeyStore (DB column removed) — set
            # the env var for the browse path to pick up.
            from app.domain.providers.env_key_store import env_key_store
            env_key_store.set_key("ollama_cloud", "fake-ollama-cloud-key")

            response = await client.get(
                f"/api/v1/providers/{ollama_cloud_provider}/models/browse?page_size=10"
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["models"][0]["id"] == "llama3.3"


class TestCuratedEnrichment:
    """Browse endpoint annotates models with curated status."""

    @pytest.mark.anyio
    async def test_browse_annotates_curated_status(
        self, client: AsyncClient, test_engine, ollama_cloud_provider: int
    ) -> None:
        """Models that are curated carry verified info; others don't."""
        from app.api.v1.providers.models_router import ollama_cloud_model_browser
        from app.domain.providers.model_browser_service import ModelBrowserResult
        from app.infrastructure.database.models import CuratedModel

        # A curated entry for this provider
        async with AsyncSession(test_engine) as session:
            cm = CuratedModel(
                provider_id=ollama_cloud_provider, model_id="gpt-oss:20b",
                model_name="GPT-OSS 20B", category="chat",
                is_free=True, verified=True,
            )
            session.add(cm)
            await session.commit()

        fake_result = ModelBrowserResult(
            models=[
                {"id": "gpt-oss:20b", "name": "gpt-oss:20b", "display_name": "GPT-OSS 20B"},
                {"id": "not-curated", "name": "not-curated", "display_name": "Not Curated"},
            ],
            total=2, page=1, page_size=50, total_pages=1, has_more=False,
            filters_applied={}, from_cache=True,
        )
        import app.domain.providers.services as services_mod
        from cryptography.fernet import Fernet
        fixed_key = Fernet.generate_key().decode()
        with patch.object(
            ollama_cloud_model_browser, "browse_models", new=AsyncMock(return_value=fake_result)
        ), patch.object(
            services_mod.EncryptionService, "__init__",
            lambda self, encryption_key=None: self.__setattr__("key", fixed_key.encode())
            or self.__setattr__("cipher", Fernet(fixed_key.encode())),
        ):
            # Need an API key — patch settings to a fake one
            from app.core.config import get_settings
            import app.api.v1.providers.models_router as router_mod
            with patch.object(router_mod, "get_settings", return_value=type(
                "S", (), {"ollama_cloud_api_key": "fake-key", "openrouter_api_key": "", "deepseek_api_key": "",
                          "openai_api_key": "", "anthropic_api_key": ""})()):
                resp = await client.get(
                    f"/api/v1/providers/{ollama_cloud_provider}/models/browse?page_size=10"
                )

        assert resp.status_code == 200
        data = resp.json()
        by_id = {m["id"]: m for m in data["models"]}
        assert by_id["gpt-oss:20b"]["curated"] == {
            "is_curated": True, "verified": True,
        }
        assert by_id["not-curated"].get("curated") is None
