"""
Provider Discovery Service.

Handles model discovery for different providers with caching.
"""

import logging
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.providers.cache_service import provider_model_cache_service
from app.domain.providers.openrouter_client import create_openrouter_client, OpenRouterAPIError
from app.domain.providers.deepseek_client import create_deepseek_client, DeepseekAPIError
from app.domain.providers.groq_client import create_groq_client, GroqAPIError
from app.domain.providers.provider_endpoints import native_root

logger = logging.getLogger(__name__)


class ProviderDiscoveryService:
    """
    Service for discovering provider models.
    
    Handles:
    - Model discovery from various providers
    - Cache management
    - Error handling and fallbacks
    """
    
    async def discover_openrouter_models(
        self,
        db: AsyncSession,
        provider_id: int,
        api_key: str,
        force_refresh: bool = False,
        ttl_hours: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Discover OpenRouter models with caching.
        
        Args:
            db: Database session
            provider_id: Provider ID
            api_key: OpenRouter API key
            force_refresh: If True, bypass cache
            ttl_hours: Custom cache TTL
            
        Returns:
            Discovery results with models and cache info
        """
        # Check cache first (unless force refresh)
        if not force_refresh:
            cached_models = await provider_model_cache_service.get_cached_models(
                db, provider_id, force_refresh=False
            )
            
            if cached_models is not None:
                logger.info(f"✅ Using cached OpenRouter models ({len(cached_models)} models)")
                return {
                    "models": cached_models,
                    "total": len(cached_models),
                    "from_cache": True,
                    "provider": "openrouter",
                }
        
        # Cache miss or force refresh - fetch from API
        logger.info(f"🔄 Fetching fresh OpenRouter models (force_refresh={force_refresh})")
        
        try:
            # Create client and fetch models
            client = create_openrouter_client(api_key)
            models = await client.list_models()
            
            if not models:
                logger.warning("⚠️ OpenRouter returned no models")
                return {
                    "models": [],
                    "total": 0,
                    "from_cache": False,
                    "provider": "openrouter",
                    "message": "No models returned from OpenRouter API",
                }
            
            # Cache the results
            await provider_model_cache_service.cache_models(
                db, provider_id, models, ttl_hours
            )
            await db.commit()
            
            logger.info(f"✅ Discovered and cached {len(models)} OpenRouter models")
            
            return {
                "models": models,
                "total": len(models),
                "from_cache": False,
                "provider": "openrouter",
                "message": f"Successfully discovered {len(models)} models",
            }
            
        except OpenRouterAPIError as e:
            logger.error(f"❌ OpenRouter discovery failed: {e}")
            await db.rollback()
            
            # Try to return cached data even if expired
            cached_models = await provider_model_cache_service.get_cached_models(
                db, provider_id, force_refresh=False
            )
            
            if cached_models:
                logger.warning(f"⚠️ Returning expired cache due to API error ({len(cached_models)} models)")
                return {
                    "models": cached_models,
                    "total": len(cached_models),
                    "from_cache": True,
                    "provider": "openrouter",
                    "warning": "API error - returning expired cache",
                    "error": str(e),
                }
            
            return {
                "models": [],
                "total": 0,
                "from_cache": False,
                "provider": "openrouter",
                "error": str(e),
            }
            
        except Exception as e:
            logger.error(f"❌ Unexpected error during OpenRouter discovery: {e}")
            await db.rollback()
            return {
                "models": [],
                "total": 0,
                "from_cache": False,
                "provider": "openrouter",
                "error": f"Discovery failed: {str(e)}",
            }
    
    async def discover_ollama_models(
        self,
        db: AsyncSession,
        provider_id: int,
        base_url: str,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Discover Ollama models (local - no API key required).

        `base_url` is the resolved endpoint — the ROW's, else its type's canonical one
        (`provider_endpoints.resolve_endpoint`). It carries NO default: a backup here is how a
        configuration gap passes for a deliberate address (the service-literals arc).

        Note: Ollama models change frequently during development,
        so we use a shorter cache TTL or skip caching entirely.
        """
        import httpx

        url = f"{native_root(base_url)}/api/tags"
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                
                models = data.get("models", [])
                
                # Transform Ollama models to our format
                transformed_models = []
                for model in models:
                    transformed_models.append({
                        "id": model.get("name", ""),
                        "name": model.get("name", ""),
                        "display_name": model.get("name", "").split(":")[0],  # Remove tag
                        "description": f"Ollama model: {model.get('name')}",
                        "context_length": None,  # Ollama doesn't provide this
                        "architecture": model.get("details", {}).get("family"),
                        "modality": "text",
                        "function_calling": False,
                        "in_context_training": False,
                        "pricing_prompt": 0,  # Local - free
                        "pricing_completion": 0,
                        "top_provider": "ollama",
                    })
                
                # Cache Ollama models with shorter TTL (1 hour for dev)
                if transformed_models:
                    await provider_model_cache_service.cache_models(
                        db, provider_id, transformed_models, ttl_hours=1
                    )
                    await db.commit()
                
                return {
                    "models": transformed_models,
                    "total": len(transformed_models),
                    "from_cache": False,
                    "provider": "ollama",
                }
                
        except Exception as e:
            logger.error(f"❌ Ollama discovery failed: {e}")
            await db.rollback()
            
            # Try cache fallback
            cached_models = await provider_model_cache_service.get_cached_models(
                db, provider_id, force_refresh=False
            )
            
            if cached_models:
                return {
                    "models": cached_models,
                    "total": len(cached_models),
                    "from_cache": True,
                    "provider": "ollama",
                    "warning": "API error - returning expired cache",
                }
            
            return {
                "models": [],
                "total": 0,
                "from_cache": False,
                "provider": "ollama",
                "error": str(e),
            }
    
    async def discover_openai_compat_models(
        self,
        db: AsyncSession,
        provider_id: int,
        base_url: str,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Discover models from a keyless local openai-compat server
        (the llama.cpp / llama row — name-based alias, like the test
        route). Its /v1/models lists the loaded GGUF; no API key.

        `base_url` is the resolved endpoint and carries NO default.

        The model id is the FULL gguf path (the llama wiring has no
        short alias) — the display name is the path's basename.
        """
        import httpx

        url = f"{base_url}/models"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    url, headers={"Authorization": "Bearer local-llama"}
                )
                response.raise_for_status()
                data = response.json()

            models = data.get("data", []) or []

            transformed_models = []
            for model in models:
                mid = model.get("id", "")
                if not mid:
                    continue
                transformed_models.append(
                    {
                        "id": mid,
                        "name": mid,
                        "display_name": mid.rsplit("/", 1)[-1],
                        "description": f"Local model: {mid}",
                        "context_length": None,
                        "architecture": None,
                        "modality": "text",
                        "function_calling": False,
                        "in_context_training": False,
                        "pricing_prompt": 0,  # Local - free
                        "pricing_completion": 0,
                        "top_provider": "llama",
                    }
                )

            if transformed_models:
                await provider_model_cache_service.cache_models(
                    db, provider_id, transformed_models, ttl_hours=1
                )
                await db.commit()

            return {
                "models": transformed_models,
                "total": len(transformed_models),
                "from_cache": False,
                "provider": "llama",
            }

        except Exception as e:
            logger.error(f"OpenAI-compat discovery failed: {e}")
            await db.rollback()

            cached_models = await provider_model_cache_service.get_cached_models(
                db, provider_id, force_refresh=False
            )

            if cached_models:
                return {
                    "models": cached_models,
                    "total": len(cached_models),
                    "from_cache": True,
                    "provider": "llama",
                    "warning": "API error - returning expired cache",
                }

            return {
                "models": [],
                "total": 0,
                "from_cache": False,
                "provider": "llama",
                "error": f"OpenAI-compat discovery failed: {e}",
            }

    async def discover_ollama_cloud_models(
        self,
        db: AsyncSession,
        provider_id: int,
        api_key: str,
        base_url: str,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Discover Ollama Cloud models (hosted OpenAI-compatible API).

        Requires a Bearer API key (stored in .env or DB). Uses the native
        /api/tags endpoint (same shape as local Ollama) with auth — the
        NATIVE root of the resolved endpoint, because the native API does
        not live under the compat root (`provider_endpoints.native_root`;
        measured: /api/tags answers 200, /v1/api/tags answers 404).

        `base_url` is the resolved endpoint and carries NO default.
        """
        import httpx

        url = f"{native_root(base_url)}/api/tags"

        try:
            headers = {"Authorization": f"Bearer {api_key}"}
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

                models = data.get("models", [])

                transformed_models = []
                for model in models:
                    name = model.get("name", "")
                    transformed_models.append({
                        "id": name,
                        "name": name,
                        "display_name": name.split(":")[0],
                        "description": f"Ollama Cloud model: {name}",
                        "context_length": None,
                        "architecture": model.get("details", {}).get("family"),
                        "modality": "text",
                        "function_calling": False,
                        "in_context_training": False,
                        "pricing_prompt": 0,
                        "pricing_completion": 0,
                        "top_provider": "ollama_cloud",
                    })

                if transformed_models:
                    await provider_model_cache_service.cache_models(
                        db, provider_id, transformed_models, ttl_hours=1
                    )
                    await db.commit()

                return {
                    "models": transformed_models,
                    "total": len(transformed_models),
                    "from_cache": False,
                    "provider": "ollama_cloud",
                }

        except Exception as e:
            logger.error(f"❌ Ollama Cloud discovery failed: {e}")
            await db.rollback()

            # Try cache fallback
            cached_models = await provider_model_cache_service.get_cached_models(
                db, provider_id, limit=500
            )
            if cached_models:
                return {
                    "models": cached_models,
                    "total": len(cached_models),
                    "from_cache": True,
                    "provider": "ollama_cloud",
                    "warning": "API error - returning expired cache",
                }

            return {
                "models": [],
                "total": 0,
                "from_cache": False,
                "provider": "ollama_cloud",
                "error": str(e),
            }

    async def discover_deepseek_models(
        self,
        db: AsyncSession,
        provider_id: int,
        api_key: str,
        force_refresh: bool = False,
        ttl_hours: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Discover Deepseek models with caching.
        
        Args:
            db: Database session
            provider_id: Provider ID
            api_key: Deepseek API key
            force_refresh: If True, bypass cache
            ttl_hours: Custom cache TTL
            
        Returns:
            Discovery results with models and cache info
        """
        # Check cache first (unless force refresh)
        if not force_refresh:
            cached_models = await provider_model_cache_service.get_cached_models(
                db, provider_id, force_refresh=False
            )
            
            if cached_models is not None:
                logger.info(f"✅ Using cached Deepseek models ({len(cached_models)} models)")
                return {
                    "models": cached_models,
                    "total": len(cached_models),
                    "from_cache": True,
                    "provider": "deepseek",
                }
        
        # Cache miss or force refresh - fetch from API
        logger.info(f"🔄 Fetching fresh Deepseek models (force_refresh={force_refresh})")
        
        try:
            # Create client and fetch models
            client = create_deepseek_client(api_key)
            models = await client.list_models()
            
            if not models:
                logger.warning("⚠️ Deepseek returned no models")
                return {
                    "models": [],
                    "total": 0,
                    "from_cache": False,
                    "provider": "deepseek",
                    "message": "No models returned from Deepseek API",
                }
            
            # Cache the results
            await provider_model_cache_service.cache_models(
                db, provider_id, models, ttl_hours
            )
            await db.commit()
            
            logger.info(f"✅ Discovered and cached {len(models)} Deepseek models")
            
            return {
                "models": models,
                "total": len(models),
                "from_cache": False,
                "provider": "deepseek",
                "message": f"Successfully discovered {len(models)} models",
            }
            
        except DeepseekAPIError as e:
            logger.error(f"❌ Deepseek discovery failed: {e}")
            await db.rollback()
            
            # Try to return cached data even if expired
            cached_models = await provider_model_cache_service.get_cached_models(
                db, provider_id, force_refresh=False
            )
            
            if cached_models:
                logger.warning(f"⚠️ Returning expired cache due to API error ({len(cached_models)} models)")
                return {
                    "models": cached_models,
                    "total": len(cached_models),
                    "from_cache": True,
                    "provider": "deepseek",
                    "warning": "API error - returning expired cache",
                    "error": str(e),
                }
            
            return {
                "models": [],
                "total": 0,
                "from_cache": False,
                "provider": "deepseek",
                "error": str(e),
            }
            
        except Exception as e:
            logger.error(f"❌ Unexpected error during Deepseek discovery: {e}")
            await db.rollback()
            return {
                "models": [],
                "total": 0,
                "from_cache": False,
                "provider": "deepseek",
                "error": f"Discovery failed: {str(e)}",
            }


    async def discover_groq_models(
        self,
        db: AsyncSession,
        provider_id: int,
        api_key: str,
        force_refresh: bool = False,
        ttl_hours: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Discover Groq models with caching.

        Args:
            db: Database session
            provider_id: Provider ID
            api_key: Groq API key
            force_refresh: If True, bypass cache
            ttl_hours: Custom cache TTL

        Returns:
            Discovery results with models and cache info
        """
        # Check cache first (unless force refresh)
        if not force_refresh:
            cached_models = await provider_model_cache_service.get_cached_models(
                db, provider_id, force_refresh=False
            )

            if cached_models is not None:
                logger.info(f"✅ Using cached Groq models ({len(cached_models)} models)")
                return {
                    "models": cached_models,
                    "total": len(cached_models),
                    "from_cache": True,
                    "provider": "groq",
                }

        # Cache miss or force refresh - fetch from API
        logger.info(f"🔄 Fetching fresh Groq models (force_refresh={force_refresh})")

        try:
            # Create client and fetch models
            client = create_groq_client(api_key)
            models = await client.list_models()

            if not models:
                logger.warning("⚠️ Groq returned no models")
                return {
                    "models": [],
                    "total": 0,
                    "from_cache": False,
                    "provider": "groq",
                    "message": "No models returned from Groq API",
                }

            # Cache the results
            await provider_model_cache_service.cache_models(
                db, provider_id, models, ttl_hours
            )
            await db.commit()

            logger.info(f"✅ Discovered and cached {len(models)} Groq models")

            return {
                "models": models,
                "total": len(models),
                "from_cache": False,
                "provider": "groq",
                "message": f"Successfully discovered {len(models)} models",
            }

        except GroqAPIError as e:
            logger.error(f"❌ Groq discovery failed: {e}")
            await db.rollback()

            # Try to return cached data even if expired
            cached_models = await provider_model_cache_service.get_cached_models(
                db, provider_id, force_refresh=False
            )

            if cached_models:
                logger.warning(f"⚠️ Returning expired cache due to API error ({len(cached_models)} models)")
                return {
                    "models": cached_models,
                    "total": len(cached_models),
                    "from_cache": True,
                    "provider": "groq",
                    "warning": "API error - returning expired cache",
                    "error": str(e),
                }

            return {
                "models": [],
                "total": 0,
                "from_cache": False,
                "provider": "groq",
                "error": str(e),
            }

        except Exception as e:
            logger.error(f"❌ Unexpected error during Groq discovery: {e}")
            await db.rollback()
            return {
                "models": [],
                "total": 0,
                "from_cache": False,
                "provider": "groq",
                "error": f"Discovery failed: {str(e)}",
            }


# Singleton instance
provider_discovery_service = ProviderDiscoveryService()
