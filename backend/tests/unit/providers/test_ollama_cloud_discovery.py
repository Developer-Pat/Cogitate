"""Ollama Cloud usage normalisation — which name shapes it rewrites, and which it leaves."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.providers.usage_tracker import _normalize_model_display


class TestNormalizeModelDisplay:
    """Usage model string normalization (old {id}/{provider}/{model} format)."""

    def test_strips_leading_numeric_segment(self) -> None:
        assert _normalize_model_display("3/deepseek/deepseek-v4-flash") == "deepseek/deepseek-v4-flash"

    def test_keeps_normal_format(self) -> None:
        assert _normalize_model_display("deepseek/deepseek-v4-flash") == "deepseek/deepseek-v4-flash"

    def test_keeps_single_segment(self) -> None:
        assert _normalize_model_display("llama3.2:latest") == "llama3.2:latest"

    def test_empty_string(self) -> None:
        assert _normalize_model_display("") == ""

    def test_numeric_in_middle_is_kept(self) -> None:
        # Only a LEADING numeric segment is stale; "nemotron-3-nano:30b" must survive
        assert _normalize_model_display("ollama/nemotron-3-nano:30b") == "ollama/nemotron-3-nano:30b"


class TestOllamaCloudDiscovery:
    """discover_ollama_cloud_models transform + cache write."""

    @pytest.mark.anyio
    async def test_transforms_and_caches(self) -> None:
        from app.domain.providers.discovery_service import provider_discovery_service
        from app.domain.providers.cache_service import provider_model_cache_service

        fake_payload = {
            "models": [
                {"name": "gpt-oss:20b", "details": {"family": "gptoss"}},
                {"name": "kimi-k3", "details": {"family": ""}},
            ]
        }

        with patch.object(
            provider_model_cache_service, "cache_models", new=AsyncMock()
        ) as mock_cache:
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_response = AsyncMock()
                mock_response.raise_for_status = MagicMock()
                mock_response.json = MagicMock(return_value=fake_payload)
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                # httpx.AsyncClient used as async context manager:
                # async with httpx.AsyncClient(...) as client → client = __aenter__()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                db = AsyncMock()
                db.commit = AsyncMock()

                result = await provider_discovery_service.discover_ollama_cloud_models(
                    db, provider_id=5, api_key="test-key", base_url="https://ollama.com"
                )

        assert result["total"] == 2
        assert result["provider"] == "ollama_cloud"
        models = result["models"]
        assert models[0]["id"] == "gpt-oss:20b"
        assert models[0]["display_name"] == "gpt-oss"
        assert models[1]["id"] == "kimi-k3"
        mock_cache.assert_awaited_once()


class TestVerifiedSync:
    """cache_models marks curated entries verified when the model is fetched."""

    @pytest.mark.anyio
    async def test_cache_models_syncs_curated_verified(self, test_engine) -> None:
        from app.domain.providers.cache_service import provider_model_cache_service
        from app.infrastructure.database.models import CuratedModel
        from sqlalchemy import delete, select

        from tests import conftest as cf

        async with AsyncSession(test_engine) as session:
            # FOUND, NOT INSERTED: the copied database already carries the installation's own
            # `ollama_cloud` row — `cf.get_or_create_provider` carries the rule.
            provider = await cf.get_or_create_provider(
                session,
                name="ollama_cloud",
                provider_type="ollama_cloud",
                base_url="https://ollama.com",
                is_active=True,
            )
            provider_id = provider.id

            # …and that row arrives with the operator's curated entries, `gpt-oss:20b` among
            # them. They go first, so the state asserted below is the one THIS test declares.
            await session.execute(
                delete(CuratedModel).where(CuratedModel.provider_id == provider_id)
            )

            # A curated entry that exists but is NOT yet verified
            cm = CuratedModel(
                provider_id=provider_id, model_id="gpt-oss:20b",
                model_name="GPT-OSS 20B", category="chat",
                is_free=True, verified=False,
            )
            session.add(cm)
            await session.commit()

        # Sync the cache — the curated entry should become verified
        async with AsyncSession(test_engine) as session:
            await provider_model_cache_service.cache_models(
                session, provider_id,
                [{"id": "gpt-oss:20b", "name": "gpt-oss:20b"}],
                ttl_hours=1,
            )

        async with AsyncSession(test_engine) as session:
            row = (
                await session.execute(
                    select(CuratedModel).where(CuratedModel.model_id == "gpt-oss:20b")
                )
            ).scalar_one()
            assert row.verified is True
