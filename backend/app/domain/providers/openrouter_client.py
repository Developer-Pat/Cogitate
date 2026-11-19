"""
OpenRouter API Client.

Handles all API communication with OpenRouter.
"""

import logging
from typing import List, Dict, Any

import httpx

logger = logging.getLogger(__name__)


class OpenRouterClient:
    """
    Client for OpenRouter API.
    
    Provides methods for:
    - Model discovery
    - Chat completions
    - Provider testing
    """
    
    # ── THE VENDOR'S OWN ROOT, HARDWIRED ON PURPOSE (the service-literals arc, F3) ──────────────
    # A DEFINITION, not a DECISION: this client exists to read ONE vendor's published catalog
    # (`GET {BASE_URL}/models`) and its constructor takes an API key only — no provider row reaches
    # it. Which service answers a COMPLETION is a row's business, resolved in ONE place
    # (`provider_endpoints.resolve_endpoint`). This address agrees with the registry's `openrouter`
    # entry, which is the same vendor's endpoint for the dispatch path.
    BASE_URL = "https://openrouter.ai/api/v1"
    TIMEOUT_SECONDS = 30.0
    
    def __init__(self, api_key: str):
        """
        Initialize OpenRouter client.
        
        Args:
            api_key: OpenRouter API key
        """
        self.api_key = api_key
        self.base_url = self.BASE_URL
        self.timeout = httpx.Timeout(self.TIMEOUT_SECONDS)
    
    async def list_models(self) -> List[Dict[str, Any]]:
        """
        List all available models from OpenRouter.
        
        Returns:
            List of model dictionaries with metadata
        """
        url = f"{self.base_url}/models"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        # Add OpenRouter specific headers
        headers["HTTP-Referer"] = "https://github.com/cogitate"  # Required by OpenRouter
        headers["X-Title"] = "Cogitate"  # Optional app name
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                logger.info("📡 Fetching models from OpenRouter API...")
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                
                data = response.json()
                models = data.get("data", [])
                
                logger.info(f"✅ Retrieved {len(models)} models from OpenRouter")
                
                # Transform to our format
                return [self._transform_model(model) for model in models]
                
            except httpx.HTTPStatusError as e:
                logger.error(f"❌ OpenRouter API error: {e.response.status_code} - {e.response.text}")
                raise OpenRouterAPIError(f"HTTP {e.response.status_code}: {e.response.text}")
            except httpx.ConnectError as e:
                logger.error(f"❌ OpenRouter connection error: {e}")
                raise OpenRouterAPIError(f"Connection failed: {e}")
            except Exception as e:
                logger.error(f"❌ Unexpected error fetching OpenRouter models: {e}")
                raise OpenRouterAPIError(f"Unexpected error: {e}")
    
    def _transform_model(self, model: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform OpenRouter model response to our internal format.
        
        Args:
            model: Raw model data from OpenRouter API
            
        Returns:
            Transformed model dictionary
        """
        # OpenRouter model format:
        # {
        #   "id": "openai/gpt-4",
        #   "name": "GPT-4",
        #   "created": 1234567890,
        #   "description": "...",
        #   "context_length": 8192,
        #   "pricing": {
        #     "prompt": "0.00003",
        #     "completion": "0.00006"
        #   },
        #   "top_provider": { ... },
        #   "architecture": { ... },
        #   ...
        # }
        
        architecture = model.get("architecture", {})
        pricing = model.get("pricing", {})
        top_provider = model.get("top_provider", {})
        
        return {
            # Core identifiers
            "id": model.get("id", ""),
            "name": model.get("name", model.get("id", "")),
            "display_name": model.get("name"),
            "description": model.get("description"),
            
            # Capabilities
            "context_length": model.get("context_length"),
            "architecture": architecture.get("modality") if architecture else None,
            "modality": architecture.get("modality"),  # e.g., "text->text"
            "tokenizer": architecture.get("tokenizer"),
            "in_context_training": architecture.get("instruct_type") == "in_context",
            "function_calling": model.get("function_calling", False),
            
            # Pricing (OpenRouter uses per-token pricing in USD)
            "pricing_prompt": float(pricing.get("prompt", 0)) if pricing.get("prompt") else None,
            "pricing_completion": float(pricing.get("completion", 0)) if pricing.get("completion") else None,
            
            # Provider info
            "top_provider": top_provider.get("provider_name") if top_provider else None,
            
            # Raw data for reference
            "_raw": model,
        }
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test OpenRouter API connectivity.
        
        Returns:
            Connection test results
        """
        url = f"{self.base_url}/models"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/cogitate",
            "X-Title": "Cogitate",
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
                        "message": f"OpenRouter API accessible with {len(models)} models",
                    }
                else:
                    return {
                        "status": "error",
                        "latency_ms": round(latency_ms, 2),
                        "message": f"OpenRouter API returned status {response.status_code}",
                    }
                    
            except httpx.ConnectError as e:
                return {
                    "status": "unreachable",
                    "message": f"Cannot connect to OpenRouter: {e}",
                }
            except Exception as e:
                return {
                    "status": "error",
                    "message": str(e),
                }


class OpenRouterAPIError(Exception):
    """Custom exception for OpenRouter API errors."""
    pass


# Factory function
def create_openrouter_client(api_key: str) -> OpenRouterClient:
    """
    Create OpenRouter client instance.
    
    Args:
        api_key: OpenRouter API key
        
    Returns:
        Configured OpenRouterClient instance
    """
    if not api_key:
        raise ValueError("OpenRouter API key is required")
    
    return OpenRouterClient(api_key)
