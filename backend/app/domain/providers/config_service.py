"""
Provider configuration service.

Business logic for provider configuration management.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update as sa_update

from app.infrastructure.database.models import Provider
from app.domain.providers.provider_classes import provider_location
from app.domain.providers.provider_endpoints import resolve_endpoint
from app.domain.providers.services import EncryptionService
from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def resolve_named_row_endpoint(db: AsyncSession, name: str) -> str | None:
    """**THE address of the provider row called `name`** — the row's own ``base_url``, else its
    TYPE's canonical entry (``provider_endpoints.resolve_endpoint``), else ``None``.

    The service-literals arc's ruling (``wiki/issues/resolved/embedded-service-literals/local-embedding-server.md``, IRW option C staged)
    makes the ROW the one home for *which server answers*. This is the lookup that lets a caller
    outside the providers layer obey that rule without writing an address down — the rag health
    response, the ingest job and the chat service's direct Ollama path all resolve through here.

    ``None`` is an ANSWER, not a failure: there is no such row, or its type has none to fall back on
    (``openai``/``anthropic``). A caller must REPORT that — nothing may dial a guessed address.
    """
    row = (await db.execute(select(Provider).where(Provider.name == name))).scalar_one_or_none()
    if row is None:
        return None
    return resolve_endpoint(row.provider_type or name, row.base_url, row.name)


class ProviderConfig:
    """Provider configuration data class."""

    def __init__(
        self,
        id: Optional[int] = None,
        name: str = "",
        display_name: Optional[str] = None,
        provider_type: str = "",
        base_url: Optional[str] = None,
        is_active: bool = True,
        priority: int = 99,
        is_default: bool = False,
        config: Optional[dict] = None,
        has_api_key: bool = False,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        location: Optional[str] = None,
    ):
        self.id = id
        self.name = name
        self.display_name = display_name
        self.provider_type = provider_type
        self.base_url = base_url
        self.is_active = is_active
        self.priority = priority
        self.is_default = is_default
        self.config = config or {}
        self.has_api_key = has_api_key
        self.created_at = created_at
        self.updated_at = updated_at
        # THE LOCATION SEAM (2026-09-08, the A1 split): derived from
        # the provider_type unless the caller pinned it explicitly.
        self.location = location or provider_location(provider_type, base_url)

    @property
    def default_model(self) -> str:
        """The row's OWN default model, from its ``config`` blob, or ``""``.

        A provider row has no model column: the model it serves lives in
        ``config["default_model"]`` — the same key ``capabilities._model_from_config``
        reads off the ORM row. This is a property rather than a constructor field
        because ``from_model`` does not read it and a row's config is replaced
        wholesale on update.

        A surface reporting *this row's* model reads THIS; it must never fall back
        to a model name written in code (`Settings.default_llm_model`).
        """
        cfg = self.config if isinstance(self.config, dict) else {}
        return str(cfg.get("default_model") or "")

    @classmethod
    def from_model(cls, provider: Provider) -> "ProviderConfig":
        """Create ProviderConfig from database model."""
        return cls(
            id=provider.id,
            name=provider.name,
            display_name=provider.display_name,
            provider_type=provider.provider_type,
            base_url=provider.base_url,
            is_active=provider.is_active,
            priority=provider.priority,
            is_default=provider.is_default,
            config=provider.config,
            has_api_key=_factory_has_env_key(provider),
            created_at=provider.created_at,
            updated_at=provider.updated_at,
        )


def _factory_has_env_key(provider) -> bool:
    """Env-only key check for the DTO factory (no instance available)."""
    from app.domain.providers.env_key_store import env_key_store
    return bool(env_key_store.get_key(provider.provider_type))


class ProviderConfigService:
    """
    Service for provider configuration management.

    Handles CRUD operations for providers stored in the database.
    """

    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize provider config service.

        Args:
            encryption_key: Optional encryption key. If not provided,
                           uses the key from settings.
        """
        settings = get_settings()
        self.encryption_key = encryption_key or settings.cogitate_encryption_key
        self._encryption_service: Optional[EncryptionService] = None

    @property
    def encryption_service(self) -> EncryptionService:
        """Get or create encryption service."""
        if self._encryption_service is None:
            self._encryption_service = EncryptionService(self.encryption_key)
        return self._encryption_service

    async def list_providers(
        self,
        db: AsyncSession,
        include_inactive: bool = True,
    ) -> List[ProviderConfig]:
        """
        List all provider configurations.

        Args:
            db: Database session
            include_inactive: Whether to include inactive providers

        Returns:
            List of ProviderConfig objects
        """
        query = select(Provider).order_by(Provider.priority)

        if not include_inactive:
            query = query.where(Provider.is_active)

        result = await db.execute(query)
        providers = result.scalars().all()

        return [ProviderConfig.from_model(p) for p in providers]

    async def get_provider(
        self,
        db: AsyncSession,
        provider_id: int,
    ) -> Optional[ProviderConfig]:
        """
        Get provider configuration by ID.

        Args:
            db: Database session
            provider_id: Provider ID

        Returns:
            ProviderConfig or None if not found
        """
        query = select(Provider).where(Provider.id == provider_id)
        result = await db.execute(query)
        provider = result.scalar_one_or_none()

        if provider:
            return ProviderConfig.from_model(provider)
        return None

    async def get_provider_by_name(
        self,
        db: AsyncSession,
        name: str,
    ) -> Optional[ProviderConfig]:
        """
        Get provider configuration by name.

        Args:
            db: Database session
            name: Provider name

        Returns:
            ProviderConfig or None if not found
        """
        query = select(Provider).where(Provider.name == name)
        result = await db.execute(query)
        provider = result.scalar_one_or_none()

        if provider:
            return ProviderConfig.from_model(provider)
        return None

    async def create_provider(
        self,
        db: AsyncSession,
        name: str,
        provider_type: str,
        display_name: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        is_active: bool = True,
        priority: int = 99,
        config: Optional[dict] = None,
    ) -> ProviderConfig:
        """
        Create a new provider configuration.

        Args:
            db: Database session
            name: Provider name (e.g., 'openai', 'anthropic')
            provider_type: Provider type (e.g., 'openai', 'anthropic', 'ollama')
            display_name: Human-readable display name
            base_url: Base URL for API
            api_key: API key (will be encrypted)
            is_active: Whether provider is active
            priority: Priority for fallback (lower = higher priority)
            config: Additional configuration

        Returns:
            Created ProviderConfig

        Raises:
            ValueError: If provider with name already exists
        """
        # Check if provider already exists
        existing = await self.get_provider_by_name(db, name)
        if existing:
            raise ValueError(f"Provider '{name}' already exists")

        # API key → .env (the app's secrets store, decision 2026-08-04)
        if api_key:
            from app.domain.providers.env_key_store import env_key_store
            if env_key_store.env_var_for(provider_type):
                env_key_store.set_key(provider_type, api_key)

        # Create provider
        provider = Provider(
            name=name,
            display_name=display_name or name.title(),
            provider_type=provider_type,
            base_url=base_url,
            is_active=is_active,
            priority=priority,
            config=config,
        )

        db.add(provider)
        await db.flush()
        await db.refresh(provider)

        logger.info(f"✅ Created provider: {provider.name} (ID: {provider.id})")

        return ProviderConfig.from_model(provider)

    async def update_provider(
        self,
        db: AsyncSession,
        provider_id: int,
        display_name: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        is_active: Optional[bool] = None,
        priority: Optional[int] = None,
        config: Optional[dict] = None,
    ) -> Optional[ProviderConfig]:
        """
        Update provider configuration.

        Args:
            db: Database session
            provider_id: Provider ID
            display_name: New display name
            base_url: New base URL
            api_key: New API key (will be encrypted)
            is_active: New active status
            priority: New priority
            config: New additional configuration

        Returns:
            Updated ProviderConfig or None if not found
        """
        query = select(Provider).where(Provider.id == provider_id)
        result = await db.execute(query)
        provider = result.scalar_one_or_none()

        if not provider:
            return None

        # Update fields if provided
        if display_name is not None:
            provider.display_name = display_name
        if base_url is not None:
            provider.base_url = base_url
        if is_active is not None:
            provider.is_active = is_active
        if priority is not None:
            provider.priority = priority
        if config is not None:
            provider.config = config

        # API key → .env (the app's secrets store, decision 2026-08-04).
        # DB column retired from new writes; clear any legacy value.
        if api_key:
            from app.domain.providers.env_key_store import env_key_store
            provider_type = provider.provider_type
            if env_key_store.env_var_for(provider_type):
                env_key_store.set_key(provider_type, api_key)

        await db.flush()
        await db.refresh(provider)

        logger.info(f"✅ Updated provider: {provider.name} (ID: {provider.id})")

        return ProviderConfig.from_model(provider)

    async def delete_provider(
        self,
        db: AsyncSession,
        provider_id: int,
    ) -> bool:
        """
        Delete provider configuration.

        Args:
            db: Database session
            provider_id: Provider ID

        Returns:
            True if deleted, False if not found
        """
        query = select(Provider).where(Provider.id == provider_id)
        result = await db.execute(query)
        provider = result.scalar_one_or_none()

        if not provider:
            return False

        await db.delete(provider)
        await db.flush()

        logger.info(f"✅ Deleted provider: {provider.name} (ID: {provider.id})")

        return True

    async def set_api_key(
        self,
        db: AsyncSession,
        provider_id: int,
        api_key: str,
    ) -> bool:
        """
        Set provider API key.

        Args:
            db: Database session
            provider_id: Provider ID
            api_key: API key to set (will be encrypted)

        Returns:
            True if updated, False if not found
        """
        query = select(Provider).where(Provider.id == provider_id)
        result = await db.execute(query)
        provider = result.scalar_one_or_none()

        if not provider:
            return False

        from app.domain.providers.env_key_store import env_key_store
        provider_type = provider.provider_type
        if env_key_store.env_var_for(provider_type):
            env_key_store.set_key(provider_type, api_key)

        await db.flush()
        await db.refresh(provider)

        logger.info(f"✅ Set API key for provider: {provider.name} (ID: {provider.id})")

        return True

    async def get_api_key(
        self,
        db: AsyncSession,
        provider_id: int,
    ) -> Optional[str]:
        """
        Get decrypted API key for provider.

        Args:
            db: Database session
            provider_id: Provider ID

        Returns:
            Decrypted API key or None if not configured
        """
        query = select(Provider).where(Provider.id == provider_id)
        result = await db.execute(query)
        provider = result.scalar_one_or_none()

        if not provider:
            return None

        # .env is the secrets store (EnvKeyStore); the legacy DB
        # column was removed (DB hygiene round 2)
        from app.domain.providers.env_key_store import env_key_store
        provider_type = provider.provider_type
        return env_key_store.get_key(provider_type)

    async def has_api_key(
        self,
        db: AsyncSession,
        provider_id: int,
    ) -> bool:
        """
        Check if provider has API key configured.

        Args:
            db: Database session
            provider_id: Provider ID

        Returns:
            True if API key is configured
        """
        result = await db.execute(select(Provider).where(Provider.id == provider_id))
        provider = result.scalar_one_or_none()
        if not provider:
            return False

        from app.domain.providers.env_key_store import env_key_store
        provider_type = provider.provider_type
        return bool(env_key_store.get_key(provider_type))

    async def validate_provider(
        self,
        db: AsyncSession,
        provider_id: int,
    ) -> bool:
        """
        Validate provider configuration.

        Args:
            db: Database session
            provider_id: Provider ID

        Returns:
            True if provider is valid and accessible
        """
        provider = await self.get_provider(db, provider_id)
        if not provider:
            return False

        # Check if provider is active
        if not provider.is_active:
            return False

        # Check if model is configured
        if not provider.config or not isinstance(provider.config, dict):
            logger.warning(f"Provider '{provider.name}' has no config")
            return False
        
        # For Ollama, check if default_model is set
        if provider.provider_type == "ollama":
            model = provider.config.get('default_model')
            if not model:
                logger.warning(f"Provider '{provider.name}' has no default_model configured")
                return False

        # For cloud providers, check if API key is configured
        if provider.provider_type in ["openai", "anthropic", "openrouter", "deepseek"]:
            if not await self.has_api_key(db, provider_id):
                return False

        return True


class DefaultProviderService:
    """
    Service for managing default LLM provider configuration.
    
    Provides centralized provider management for all services
    (workflows, title generation, chat, etc.).
    
    Features:
    - System-wide default provider
    - Provider switching
    - Connection testing
    - Automatic default provider initialization (Ollama)
    """
    
    def __init__(self) -> None:
        """Initialize default provider service."""
        self._config_service: Optional[ProviderConfigService] = None
    
    @property
    def config_service(self) -> ProviderConfigService:
        """Get or create provider config service."""
        if self._config_service is None:
            self._config_service = ProviderConfigService()
        return self._config_service
    
    async def get_default_provider(
        self,
        db: AsyncSession,
    ) -> Optional[ProviderConfig]:
        """
        Get the current default provider configuration.
        
        Args:
            db: Database session
            
        Returns:
            ProviderConfig of default provider or None if not configured
        """
        query = select(Provider).where(
            Provider.is_default,
            Provider.is_active
        )
        result = await db.execute(query)
        provider = result.scalar_one_or_none()
        
        if provider:
            return ProviderConfig.from_model(provider)
        return None
    
    async def set_default_provider(
        self,
        db: AsyncSession,
        provider_id: int,
    ) -> bool:
        """
        Set a provider as the system default.
        
        This will unset any existing default provider first.
        
        Args:
            db: Database session
            provider_id: ID of provider to set as default
            
        Returns:
            True if successful, False if provider not found
        """
        # First, unset any existing default
        await db.execute(
            sa_update(Provider)
            .where(Provider.is_default)
            .values(is_default=False)
        )
        
        # Check if provider exists
        query = select(Provider).where(Provider.id == provider_id)
        result = await db.execute(query)
        provider = result.scalar_one_or_none()
        
        if not provider:
            return False
        
        # Set new default
        provider.is_default = True
        await db.flush()
        await db.refresh(provider)
        
        logger.info(f"✅ Set default provider: {provider.name} (ID: {provider.id})")
        return True
    
    async def initialize_default_provider(
        self,
        db: AsyncSession,
    ) -> Optional[ProviderConfig]:
        """
        Initialize default provider if none exists.

        Creates the default Ollama ROW if no providers exist, and names NO model: a fresh
        install gets a place to choose a model, not a model somebody else chose. (A seeded
        `llama3.2` only "works" when that model happens to be installed anyway.)

        Args:
            db: Database session

        Returns:
            ProviderConfig of initialized provider or None if failed
        """
        # Check if default already exists
        existing_default = await self.get_default_provider(db)
        if existing_default:
            return existing_default

        # Check if any providers exist
        providers = await self.config_service.list_providers(db)
        if providers:
            # If providers exist but no default, set first active one as default
            for provider in providers:
                if provider.is_active and provider.id is not None:
                    await self.set_default_provider(db, provider.id)
                    logger.info(f"✅ Set existing provider '{provider.name}' as default")
                    return provider
            return None

        # A FRESH INSTALL SEEDS NO MODEL (2026-10-10, the service-literals arc).
        # This row used to be created carrying `default_model: llama3.2:latest` — a model nobody
        # chose, on an install where nothing is even running yet. Which model runs is the USER's
        # (and Exa's) to decide, exactly as a fresh install boots with an EMPTY curated table
        # rather than a shipped seed. Setting up a curated install is Exa's job (an installation
        # skill), not a literal compiled into the app. The row's own `base_url` STAYS: an endpoint
        # on a row IS the decision about which server answers, and the row is where it is edited.
        logger.info("🔧 Creating the default Ollama provider row (no model — nothing is chosen yet)...")
        try:
            ollama_config = await self.config_service.create_provider(
                db=db,
                name="ollama",
                provider_type="ollama",
                display_name="Ollama (Local)",
                base_url="http://localhost:11434",
                is_active=True,
                priority=1,  # High priority for local provider
                config={},
            )

            # Set as default
            if ollama_config.id is not None:
                await self.set_default_provider(db, ollama_config.id)
            logger.info(
                f"✅ Initialized the default provider row: {ollama_config.name} "
                "(no model configured yet)"
            )
            return ollama_config

        except Exception as e:
            logger.error(f"❌ Failed to initialize default provider: {e}")
            return None
    
    async def is_default_provider_ready(
        self,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Check if default provider is configured and ready for use.

        Args:
            db: Database session

        Returns:
            Dictionary with status and details:
            - ready: bool - Whether default provider is ready
            - provider: ProviderConfig or None
            - message: str - Status message
            - issues: List[str] - List of configuration issues
        """
        config = await self.get_default_provider(db)
        
        if not config:
            return {
                "ready": False,
                "provider": None,
                "message": "No default provider configured",
                "issues": ["No default provider found in database"],
            }
        
        issues = []
        
        # Check if provider is active
        if not config.is_active:
            issues.append("Provider is not active")
        
        # Check if model is configured
        if config.provider_type == "ollama":
            if not config.config or not config.config.get('default_model'):
                issues.append("No model configured - please select a model from the provider settings")
        
        # Check if API key is configured for cloud providers
        if config.provider_type in ["openai", "anthropic", "openrouter", "deepseek"]:
            if not config.has_api_key:
                issues.append("API key not configured")
        
        return {
            "ready": len(issues) == 0,
            "provider": config,
            "message": "Default provider is ready" if not issues else "; ".join(issues),
            "issues": issues,
        }
