"""
Deepseek API Client.

Handles all API communication with Deepseek.
Supports V4 API with dynamic model discovery.
"""

import logging
from typing import List, Dict, Any

import httpx

logger = logging.getLogger(__name__)


# Known Deepseek V4 model metadata.
# The API returns models dynamically, but metadata (context, pricing, capabilities)
# is documented separately. This dict provides that enrichment.
# Prices are in USD per 1M tokens (converted from Deepseek's published rates).
DEEPSEEK_MODEL_METADATA: Dict[str, Dict[str, Any]] = {
    "deepseek-v4-flash": {
        "display_name": "DeepSeek V4 Flash",
        "description": "DeepSeek's flagship V4 model optimized for speed and efficiency. Supports both non-thinking and thinking modes.",
        "context_length": 1_000_000,
        "max_output": 384_000,
        "architecture": "transformer",
        "modality": "text->text",
        "tokenizer": "Deepseek",
        "function_calling": True,
        "json_output": True,
        "tool_calls": True,
        "fim_completion": True,
        "thinking_mode": True,
        "pricing_prompt": 0.14,       # $0.14/1M tokens (cache miss)
        "pricing_completion": 0.28,    # $0.28/1M tokens
        "pricing_prompt_cached": 0.0028,  # $0.0028/1M tokens (cache hit)
    },
    "deepseek-v4-pro": {
        "display_name": "DeepSeek V4 Pro",
        "description": "DeepSeek's premium V4 model with enhanced reasoning and higher quality outputs.",
        "context_length": 1_000_000,
        "max_output": 384_000,
        "architecture": "transformer",
        "modality": "text->text",
        "tokenizer": "Deepseek",
        "function_calling": True,
        "json_output": True,
        "tool_calls": True,
        "fim_completion": True,
        "thinking_mode": True,
        "pricing_prompt": 0.435,       # $0.435/1M tokens (cache miss)
        "pricing_completion": 0.87,    # $0.87/1M tokens
        "pricing_prompt_cached": 0.003625,  # $0.003625/1M tokens (cache hit)
    },
}

class DeepseekClient:
    """
    Client for Deepseek API.

    Provides methods for:
    - Model discovery
    - Chat completions
    - Provider testing
    """

    # ── THE VENDOR'S OWN ROOT, HARDWIRED ON PURPOSE (the service-literals arc, F3) ──────────────
    # A DEFINITION, not a DECISION: this client exists to read ONE vendor's published catalog
    # (`GET {BASE_URL}/models`) and its constructor takes an API key only — no provider row reaches
    # it, so there is no configured address for it to disagree with. Which service answers a
    # COMPLETION is a row's business, resolved in ONE place (`provider_endpoints.resolve_endpoint`).
    # The root is deliberately BARE (no `/v1`): `/models` is read off the host itself, whereas the
    # registry's `deepseek` entry carries the OpenAI-compatible `/v1` root — what the TYPE resolves
    # to only when a row declares no endpoint (the live `deepseek` row declares this bare host).
    # Both answer here — the 2026-10-11 probe could not tell them apart (all four paths 401).
    BASE_URL = "https://api.deepseek.com"
    TIMEOUT_SECONDS = 30.0

    def __init__(self, api_key: str):
        """
        Initialize Deepseek client.

        Args:
            api_key: Deepseek API key
        """
        self.api_key = api_key
        self.base_url = self.BASE_URL
        self.timeout = httpx.Timeout(self.TIMEOUT_SECONDS)

    async def list_models(self) -> List[Dict[str, Any]]:
        """
        List all available models from Deepseek.

        Returns:
            List of model dictionaries with metadata
        """
        url = f"{self.base_url}/models"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                logger.info("📡 Fetching models from Deepseek API...")
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                data = response.json()
                models = data.get("data", [])

                logger.info(f"✅ Retrieved {len(models)} models from Deepseek")

                # Transform to our format with enriched metadata
                transformed = [self._transform_model(model) for model in models]

                return transformed

            except httpx.HTTPStatusError as e:
                logger.error(f"❌ Deepseek API error: {e.response.status_code} - {e.response.text}")
                raise DeepseekAPIError(f"HTTP {e.response.status_code}: {e.response.text}")
            except httpx.ConnectError as e:
                logger.error(f"❌ Deepseek connection error: {e}")
                raise DeepseekAPIError(f"Connection failed: {e}")
            except Exception as e:
                logger.error(f"❌ Unexpected error fetching Deepseek models: {e}")
                raise DeepseekAPIError(f"Unexpected error: {e}")

    def _transform_model(self, model: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform Deepseek model response to our internal format.

        Uses dynamic API response data enriched with known metadata.

        Args:
            model: Raw model data from Deepseek API

        Returns:
            Transformed model dictionary
        """
        model_id = model.get("id", "")
        metadata = DEEPSEEK_MODEL_METADATA.get(model_id, {})

        return {
            # Core identifiers
            "id": model_id,
            "name": model_id,
            "display_name": metadata.get("display_name", model_id.replace("-", " ").title()),
            "description": metadata.get(
                "description",
                f"Deepseek model: {model_id}",
            ),

            # Capabilities
            "context_length": metadata.get("context_length", 1_000_000),
            "max_output": metadata.get("max_output", 384_000),
            "architecture": metadata.get("architecture", "transformer"),
            "modality": metadata.get("modality", "text->text"),
            "tokenizer": metadata.get("tokenizer", "Deepseek"),
            "function_calling": metadata.get("function_calling", False),
            "json_output": metadata.get("json_output", False),
            "tool_calls": metadata.get("tool_calls", False),
            "thinking_mode": metadata.get("thinking_mode", False),

            # Pricing — PER TOKEN, the single unit `provider_model_cache` stores and
            # `ProviderModelCacheService.pricing_for_model` reads (which multiplies by 1000 to
            # answer `calculate_cost`'s per-1K unit). The metadata above is per 1M, so
            # `_per_token` divides by 1e6. Storing per 1K here instead — the old `_per_1k` —
            # charged every deepseek CATALOG row 1000x its real rate, and the number looked
            # plausible, which is why it survived.
            "pricing_prompt": self._per_token(metadata.get("pricing_prompt", 0.14)),
            "pricing_completion": self._per_token(metadata.get("pricing_completion", 0.28)),

            # Provider info
            "top_provider": "deepseek",

            # Raw data for reference
            "_raw": model,
        }

    def _per_token(self, per_1m_price: float) -> float:
        """Convert a per-1M-token price to the per-TOKEN unit the catalog column stores."""
        return per_1m_price / 1_000_000

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test Deepseek API connectivity.

        Returns:
            Connection test results
        """
        url = f"{self.base_url}/models"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        import time
        start_time = time.time()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, headers=headers)
                latency_ms = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    data = response.json()
                    models = data.get("data", [])
                    return {
                        "status": "connected",
                        "latency_ms": round(latency_ms, 2),
                        "models_available": len(models),
                        "message": f"Deepseek API accessible with {len(models)} models",
                    }
                else:
                    return {
                        "status": "error",
                        "latency_ms": round(latency_ms, 2),
                        "message": f"Deepseek API returned status {response.status_code}",
                    }

            except httpx.ConnectError as e:
                return {
                    "status": "unreachable",
                    "message": f"Cannot connect to Deepseek: {e}",
                }
            except Exception as e:
                return {
                    "status": "error",
                    "message": str(e),
                }


class DeepseekAPIError(Exception):
    """Custom exception for Deepseek API errors."""
    pass


# Factory function
def create_deepseek_client(api_key: str) -> DeepseekClient:
    """
    Create Deepseek client instance.

    Args:
        api_key: Deepseek API key

    Returns:
        Configured DeepseekClient instance
    """
    if not api_key:
        raise ValueError("Deepseek API key is required")

    return DeepseekClient(api_key)
