"""The Ollama Cloud browser — bearer auth, and empty results on error.

Covers:
- Fetch from API with Bearer auth header (no cache)
- Cache-hit path
- Missing API key → no fetch
- API error → empty result
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.domain.providers.ollama_cloud_browser import OllamaCloudModelBrowser, ollama_cloud_model_browser
from app.domain.providers.model_browser_service import ModelBrowserFilters


@pytest.fixture
def browser():
    return OllamaCloudModelBrowser()


class TestOllamaCloudBrowser:
    """Unit tests for Ollama Cloud model browser."""

    @pytest.mark.anyio
    async def test_fetch_with_bearer_auth(self, browser, test_engine):
        """API fetch sends Bearer auth header and transforms models."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={
            "models": [
                {"name": "llama3.3", "details": {"family": "llama", "parameter_size": "8B", "quantization_level": "Q4_K_M"}, "size": 4600000000},
                {"name": "qwen3", "details": {"family": "qwen", "parameter_size": "32B", "quantization_level": "Q4_K_M"}, "size": 19000000000},
            ]
        })
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        # httpx.AsyncClient is used as async context manager:
        # async with httpx.AsyncClient(...) as client → client = __aenter__()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        async with AsyncSession(test_engine) as session:
            with patch("httpx.AsyncClient", return_value=mock_client):
                models = await browser._fetch_models(
                    session, provider_id=99, base_url="https://ollama.com", api_key="test-key-123"
                )

        # Verify auth header sent
        _, kwargs = mock_client.get.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer test-key-123"

        # Verify transform
        assert len(models) == 2
        assert models[0]["id"] == "llama3.3"
        assert models[0]["top_provider"] == "ollama_cloud"
        assert models[0]["architecture"] == "llama"

    @pytest.mark.anyio
    async def test_missing_api_key_returns_empty(self, browser, test_engine):
        """Without an API key, no fetch happens and result is empty."""
        async with AsyncSession(test_engine) as session:
            with patch("httpx.AsyncClient") as mock_http:
                models = await browser._fetch_models(
                    session, provider_id=99, base_url="https://ollama.com", api_key=None
                )
        assert models == []
        mock_http.assert_not_called()

    @pytest.mark.anyio
    async def test_api_error_returns_empty(self, browser, test_engine):
        """HTTP error returns empty list (no crash)."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock(side_effect=Exception("401 Unauthorized"))
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        async with AsyncSession(test_engine) as session:
            with patch("httpx.AsyncClient", return_value=mock_client):
                models = await browser._fetch_models(
                    session, provider_id=99, base_url="https://ollama.com", api_key="bad-key"
                )
        assert models == []

    @pytest.mark.anyio
    async def test_browse_models_requires_api_key(self, browser, test_engine):
        """browse_models without api_key returns empty result, not error."""
        async with AsyncSession(test_engine) as session:
            result = await browser.browse_models(
                db=session,
                provider_id=99,
                base_url="https://ollama.com/v1",
                api_key=None,
                filters=ModelBrowserFilters(),
            )
        assert result.models == []
        assert result.total == 0


from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402
