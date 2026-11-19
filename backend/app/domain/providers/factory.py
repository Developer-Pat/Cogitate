"""
Provider Factory.

Creates and manages provider clients with unified interface.
"""

import logging
from typing import Optional, Dict, Any


from app.domain.providers.openrouter_client import create_openrouter_client
from app.domain.providers.deepseek_client import create_deepseek_client
from app.domain.providers.provider_endpoints import resolve_endpoint
from app.domain.providers.services import OllamaService

logger = logging.getLogger(__name__)


class ProviderFactory:
    """
    Factory for creating provider clients.

    Provides unified interface for:
    - Creating provider clients
    - Managing provider configuration
    - Provider health checking
    - Fallback chain management
    """

    # Supported provider types
    SUPPORTED_PROVIDERS = {
        "ollama": "local",
        "ollama_cloud": "cloud",
        "openrouter": "cloud",
        "deepseek": "cloud",
        "openai": "cloud",
        "anthropic": "cloud",
    }

    def __init__(self) -> None:
        """Initialize provider factory."""
        self._client_cache: Dict[str, Any] = {}

    def get_client(
        self,
        provider_type: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> Any:
        """
        Get provider client instance.

        Args:
            provider_type: Provider type (ollama, openrouter, deepseek, etc.)
            api_key: API key (required for cloud providers)
            base_url: Base URL (optional, uses default if not provided)

        Returns:
            Provider client instance

        Raises:
            ValueError: If provider type is unsupported or API key missing
        """
        if provider_type not in self.SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported provider: {provider_type}")

        # Create client based on provider type
        if provider_type == "ollama":
            return OllamaService(
                base_url=resolve_endpoint(provider_type, base_url, "the provider factory")
            )

        elif provider_type == "openrouter":
            if not api_key:
                raise ValueError("OpenRouter API key is required")
            return create_openrouter_client(api_key)

        elif provider_type == "deepseek":
            if not api_key:
                raise ValueError("Deepseek API key is required")
            return create_deepseek_client(api_key)

        elif provider_type == "openai":
            # Will be handled by LiteLLM directly
            return {"type": "openai", "api_key": api_key, "base_url": base_url}

        elif provider_type == "anthropic":
            # Will be handled by LiteLLM directly
            return {"type": "anthropic", "api_key": api_key, "base_url": base_url}

        else:
            raise ValueError(f"Unsupported provider: {provider_type}")

    def is_provider_available(self, provider_type: str) -> bool:
        """
        Check if provider type is available.

        Args:
            provider_type: Provider type

        Returns:
            True if provider is supported
        """
        return provider_type in self.SUPPORTED_PROVIDERS

    def get_provider_info(self, provider_type: str) -> Dict[str, Any]:
        """
        Get provider information.

        Args:
            provider_type: Provider type

        Returns:
            Provider information dictionary
        """
        if provider_type not in self.SUPPORTED_PROVIDERS:
            return {
                "type": provider_type,
                "supported": False,
            }

        return {
            "type": provider_type,
            "supported": True,
            "category": self.SUPPORTED_PROVIDERS[provider_type],
        }

    def clear_cache(self):
        """Clear client cache."""
        self._client_cache.clear()
        logger.info("🧹 Provider client cache cleared")


# Singleton instance
provider_factory = ProviderFactory()
