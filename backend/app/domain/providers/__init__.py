"""
Provider domain module.

Contains provider business logic and schemas.

Phase 3: Provider Abstraction Layer
    - ProviderFactory: Unified provider client creation
    - ProviderCompletionService: Completion service with fallback
    - RateLimiter: Rate limiting and quota management

Phase 4: Provider Management
    - ProviderConfigService: Provider configuration management
    - UsageTracker: Usage aggregation and analytics
    - ModelSyncScheduler: Automatic model synchronization
"""

from app.domain.providers.services import ProviderService, OllamaService, EncryptionService
from app.domain.providers.factory import provider_factory, ProviderFactory
from app.domain.providers.completion_service import (
    provider_completion_service,
    ProviderCompletionService,
    CompletionRequest,
    CompletionResponse,
)
from app.domain.providers.rate_limiter import (
    rate_limiter,
    quota_manager,
    health_monitor,
    RateLimiter,
    QuotaManager,
    ProviderHealthMonitor,
)
from app.domain.providers.config_service import (
    ProviderConfigService,
    ProviderConfig,
    DefaultProviderService,
)
from app.domain.providers.llm_factory import (
    get_llm_from_config,
)
from app.domain.providers.usage_tracker import UsageTracker, UsagePeriod, UsageStats
from app.domain.providers.scheduler import ModelSyncScheduler, SyncSchedule, SyncStatus

__all__ = [
    # Legacy services
    "ProviderService",
    "OllamaService",
    "EncryptionService",
    # Phase 3: Provider Abstraction
    "provider_factory",
    "ProviderFactory",
    "provider_completion_service",
    "ProviderCompletionService",
    "CompletionRequest",
    "CompletionResponse",
    "rate_limiter",
    "quota_manager",
    "health_monitor",
    "RateLimiter",
    "QuotaManager",
    "ProviderHealthMonitor",
    # Phase 4: Provider Management
    "ProviderConfigService",
    "ProviderConfig",
    "DefaultProviderService",
    "get_llm_from_config",
    "UsageTracker",
    "UsagePeriod",
    "UsageStats",
    "ModelSyncScheduler",
    "SyncSchedule",
    "SyncStatus",
]
