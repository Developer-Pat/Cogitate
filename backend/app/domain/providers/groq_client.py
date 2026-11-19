"""
Groq API Client.

Handles all API communication with Groq.
"""

import logging
from typing import List, Dict, Any

import httpx

logger = logging.getLogger(__name__)


class GroqClient:
    """
    Client for Groq API.

    Provides methods for:
    - Model discovery
    - Chat completions
    - Provider testing
    """

    # ── THE VENDOR'S OWN ROOT, HARDWIRED ON PURPOSE (the service-literals arc, F3) ──────────────
    # A DEFINITION, not a DECISION: this client exists to read ONE vendor's published catalog
    # (`GET {BASE_URL}/models`) and its constructor takes an API key only — no provider row reaches
    # it. Which service answers a COMPLETION is a row's business, resolved in ONE place
    # (`provider_endpoints.resolve_endpoint`). This address agrees with the registry's `groq` entry.
    BASE_URL = "https://api.groq.com/openai/v1"
    TIMEOUT_SECONDS = 30.0

    def __init__(self, api_key: str):
        """
        Initialize Groq client.

        Args:
            api_key: Groq API key
        """
        self.api_key = api_key
        self.base_url = self.BASE_URL
        self.timeout = httpx.Timeout(self.TIMEOUT_SECONDS)

    async def list_models(self) -> List[Dict[str, Any]]:
        """
        List all available models from Groq.

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
                logger.info("📡 Fetching models from Groq API...")
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                data = response.json()
                models = data.get("data", [])

                logger.info(f"✅ Retrieved {len(models)} models from Groq")

                # Transform to our format
                return [self._transform_model(model) for model in models]

            except httpx.HTTPStatusError as e:
                logger.error(f"❌ Groq API error: {e.response.status_code} - {e.response.text}")
                raise GroqAPIError(f"HTTP {e.response.status_code}: {e.response.text}")
            except httpx.ConnectError as e:
                logger.error(f"❌ Groq connection error: {e}")
                raise GroqAPIError(f"Connection failed: {e}")
            except Exception as e:
                logger.error(f"❌ Unexpected error fetching Groq models: {e}")
                raise GroqAPIError(f"Unexpected error: {e}")

    def _transform_model(self, model: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform Groq model response to our internal format.

        Args:
            model: Raw model data from Groq API

        Returns:
            Transformed model dictionary
        """
        # Groq model format (OpenAI-compatible):
        # {
        #   "id": "llama3-70b-8192",
        #   "object": "model",
        #   "created": 1234567890,
        #   "owned_by": "groq"
        # }

        model_id = model.get("id", "")

        return {
            # Core identifiers
            "id": model_id,
            "name": model_id,
            "display_name": self._get_display_name(model_id),
            "description": self._get_model_description(model_id),

            # Capabilities (Groq doesn't provide detailed info via API)
            "context_length": self._get_context_length(model_id),
            "architecture": "transformer",
            "modality": "text->text",
            "tokenizer": "Groq",
            "in_context_training": False,
            "function_calling": self._supports_function_calling(model_id),

            # Pricing (Groq provides inference at no cost via their LPU)
            "pricing_prompt": 0.0,
            "pricing_completion": 0.0,

            # Provider info
            "top_provider": "groq",

            # Raw data for reference
            "_raw": model,
        }

    def _get_display_name(self, model_id: str) -> str:
        """Get human-readable display name."""
        names = {
            "llama3-70b-8192": "Llama 3 70B",
            "llama3-8b-8192": "Llama 3 8B",
            "llama-3.1-70b-versatile": "Llama 3.1 70B Versatile",
            "llama-3.1-8b-instant": "Llama 3.1 8B Instant",
            "llama-3.2-1b-preview": "Llama 3.2 1B Preview",
            "llama-3.2-3b-preview": "Llama 3.2 3B Preview",
            "llama-3.2-11b-vision-preview": "Llama 3.2 11B Vision Preview",
            "llama-3.2-90b-vision-preview": "Llama 3.2 90B Vision Preview",
            "llama-guard-3-8b": "Llama Guard 3 8B",
            "mixtral-8x7b-32768": "Mixtral 8x7B",
            "gemma2-9b-it": "Gemma 2 9B",
            "gemma-7b-it": "Gemma 7B",
            "whisper-large-v3": "Whisper Large V3",
            "whisper-large-v3-turbo": "Whisper Large V3 Turbo",
            "distil-whisper-large-v3-en": "Distil Whisper Large V3 EN",
        }
        return names.get(model_id, model_id.replace("-", " ").title())

    def _get_model_description(self, model_id: str) -> str:
        """Get model description."""
        descriptions = {
            "llama3-70b-8192": "Meta's Llama 3 70B model optimized for dialogue and reasoning",
            "llama3-8b-8192": "Meta's Llama 3 8B model for efficient inference",
            "llama-3.1-70b-versatile": "Meta's Llama 3.1 70B versatile model",
            "llama-3.1-8b-instant": "Meta's Llama 3.1 8B instant response model",
            "llama-3.2-1b-preview": "Meta's Llama 3.2 1B lightweight preview model",
            "llama-3.2-3b-preview": "Meta's Llama 3.2 3B efficient preview model",
            "llama-3.2-11b-vision-preview": "Meta's Llama 3.2 11B multimodal vision preview model",
            "llama-3.2-90b-vision-preview": "Meta's Llama 3.2 90B multimodal vision preview model",
            "mixtral-8x7b-32768": "Mistral's Mixtral 8x7B mixture of experts model with 32K context",
            "gemma2-9b-it": "Google's Gemma 2 9B instruction-tuned model",
            "gemma-7b-it": "Google's Gemma 7B instruction-tuned model",
        }
        return descriptions.get(model_id, f"Groq model: {model_id}")

    def _get_context_length(self, model_id: str) -> int:
        """Get context length for model."""
        # Groq models have varying context windows
        context_lengths = {
            "llama3-70b-8192": 8192,
            "llama3-8b-8192": 8192,
            "llama-3.1-70b-versatile": 8192,
            "llama-3.1-8b-instant": 8192,
            "llama-3.2-1b-preview": 8192,
            "llama-3.2-3b-preview": 8192,
            "llama-3.2-11b-vision-preview": 8192,
            "llama-3.2-90b-vision-preview": 8192,
            "mixtral-8x7b-32768": 32768,
            "gemma2-9b-it": 8192,
            "gemma-7b-it": 8192,
        }
        return context_lengths.get(model_id, 8192)

    def _supports_function_calling(self, model_id: str) -> bool:
        """Check if model supports function calling."""
        # Most Groq models support function/tool calling
        supported = [
            "llama3-70b-8192",
            "llama3-8b-8192",
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant",
            "llama-3.2-1b-preview",
            "llama-3.2-3b-preview",
            "llama-3.2-11b-vision-preview",
            "llama-3.2-90b-vision-preview",
            "mixtral-8x7b-32768",
            "gemma2-9b-it",
            "gemma-7b-it",
        ]
        return model_id in supported

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test Groq API connectivity.

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
                        "message": f"Groq API accessible with {len(models)} models",
                    }
                else:
                    return {
                        "status": "error",
                        "latency_ms": round(latency_ms, 2),
                        "message": f"Groq API returned status {response.status_code}",
                    }

            except httpx.ConnectError as e:
                return {
                    "status": "unreachable",
                    "message": f"Cannot connect to Groq: {e}",
                }
            except Exception as e:
                return {
                    "status": "error",
                    "message": str(e),
                }


class GroqAPIError(Exception):
    """Custom exception for Groq API errors."""
    pass


# Factory function
def create_groq_client(api_key: str) -> GroqClient:
    """
    Create Groq client instance.

    Args:
        api_key: Groq API key

    Returns:
        Configured GroqClient instance
    """
    if not api_key:
        raise ValueError("Groq API key is required")

    return GroqClient(api_key)
