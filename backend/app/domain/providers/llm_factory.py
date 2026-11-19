"""
LLM Factory for creating LangChain clients from provider configurations.

Provides unified interface for creating LLM clients across different providers:
- Ollama (local)
- OpenAI (cloud)
- Anthropic (cloud)
- OpenRouter (cloud)
- DeepSeek (cloud)
- Groq (cloud, OpenAI-compatible)

Usage:
    from app.domain.providers.llm_factory import get_llm_from_config

    config = default_provider_service.get_default_provider(db)
    llm = get_llm_from_config(config)
"""

import copy
import logging
from typing import Any, Optional, cast

from app.domain.providers.config_service import ProviderConfig
from app.core.config import get_settings

logger = logging.getLogger(__name__)

from app.domain.providers.provider_classes import PROVIDER_CLOUD_TYPES, provider_location
from app.domain.providers.provider_endpoints import compat_root_offer, resolve_endpoint

# The value a KEYLESS endpoint still has to be given: the openai adapter refuses to construct
# without a non-empty key, so a loopback service (the local llama.cpp server) gets a placeholder.
# It is spelled the same way the chat executors, the alias map and the discovery probe spell it;
# those other homes are banked in the todo's literal sweep rather than churned here.
LOCAL_KEY_PLACEHOLDER = "local-llama"


def single_served_model(config: ProviderConfig, base_url: str | None = None) -> str:
    """What a LOCAL server reports it is serving, when it reports EXACTLY ONE model.

    A local server MOUNTS its model at launch and answers `/v1/models` with it — the app
    cannot tell it which model to run, so a configured name the server does not report (a
    short alias against the full path the server was given) is stale by construction, and
    sending it is a guess that happens to work only because the server ignores it.

    With SEVERAL models served the configured name is how one is SELECTED, so this returns
    "" and the caller keeps its own answer. So does a cloud provider, an unreachable server,
    or anything unexpected — an empty answer here never overrides a caller's.

    ``base_url`` is the endpoint the caller RESOLVED (the row's own, else the type's canonical
    one), passed in so the probe asks the address the client will actually dial. Omitting it
    falls back to the row's own field.
    """
    if getattr(config, "location", "cloud") != "local":
        return ""
    base = (base_url if base_url is not None else (config.base_url or "")).strip()
    if not base:
        return ""

    from app.domain.providers.availability import OPENAI_MODELS_PATH, join_probe_url

    try:
        import httpx

        response = httpx.get(join_probe_url(base, OPENAI_MODELS_PATH), timeout=1.5)
        response.raise_for_status()
        data = response.json().get("data") or []
    except Exception:  # noqa: BLE001 — an unreachable server is not this function's business
        return ""

    ids = [
        str(m["id"])
        for m in data
        if isinstance(m, dict) and isinstance(m.get("id"), str) and m["id"]
    ]
    return ids[0] if len(ids) == 1 else ""


def get_llm_from_config(
    config: ProviderConfig,
    temperature: float = 0.0,
    top_p: float = 0.7,
    max_tokens: int = 2000,
    api_key: Optional[str] = None,
) -> Any:
    """
    Create LangChain LLM client from provider configuration.

    Args:
        config: Provider configuration
        temperature: LLM temperature (default: 0.0 for deterministic)
        top_p: Nucleus sampling (default: 0.7 for instruction following)
        max_tokens: Maximum tokens to generate (default: 2000)
        api_key: Optional API key (if not provided, uses config.has_api_key flag)

    Returns:
        LangChain BaseChatModel instance

    Raises:
        ValueError: If provider type is unsupported, configuration missing, or no model configured
    """
    provider_type = config.provider_type

    # THE ENDPOINT IS RESOLVED ONCE, HERE (2026-10-10, the service-literals arc) — through the ONE
    # house rule, `provider_endpoints.resolve_endpoint`: the row's own `base_url`, else the type's
    # canonical endpoint, and the omission REPORTED either way. Resolved BEFORE the probe below, so
    # the single-model rule and the client cannot be pointed at two servers. What this replaced:
    # `base_url or "<the vendor>"` written inside three adapters and at two call sites — one
    # decision with two homes, already disagreeing with a row. A `None` here means the row declares
    # nothing and its type has none (openai/anthropic): the adapter's own default applies.
    base_url = resolve_endpoint(provider_type, config.base_url, config.name)

    # THE ROW-vs-PROTOCOL REPORT AT THE DIAL (2026-10-11, the ruling — *"report, then offer"*). A
    # hybrid type (`provider_endpoints.NATIVE_API_ROOTS`) has two roots on one host, and its row must
    # carry the COMPAT one: with the native root the client below posts to `<row>/chat/completions`,
    # one directory outside the API — measured, 404 on ollama.com. Say what will be dialled and what
    # to set; never change it here — the row is the user's value.
    offer = compat_root_offer(provider_type, config.base_url)
    if offer:
        logger.warning(
            "Provider '%s' (%s) carries the service's NATIVE root (%s) where this call dials the "
            "OpenAI-compatible one — the request goes to %s/chat/completions. "
            "Set the row's endpoint to %s.",
            config.name,
            provider_type,
            base_url,
            (base_url or "").rstrip("/"),
            offer,
        )

    # Get model name from config, fallback to provider name
    model_name = None
    if config.config and isinstance(config.config, dict):
        model_name = config.config.get('default_model')

    # A SINGLE-MODEL LOCAL SERVER NAMES ITSELF (2026-10-09). See `single_served_model`: a
    # loopback server mounts one model and cannot be told which to run, so its answer wins
    # and a configured name it does not report is logged rather than quietly sent.
    served = single_served_model(config, base_url)
    if served:
        if model_name and model_name != served:
            logger.warning(
                "Provider '%s' is configured with model '%s' but the server serves '%s' — "
                "using what it serves (a single-model server cannot be told which to run).",
                config.name, model_name, served,
            )
        model_name = served

    if not model_name:
        model_name = config.name  # Fallback to provider name

    # Validate model is configured
    if not model_name or model_name == config.name:
        logger.warning(
            f"Provider '{config.name}' has no model configured. "
            f"Set a default_model in provider config or ensure '{config.name}' is a valid model name."
        )

    # Get API key if needed (for cloud providers)
    # Fallback chain: 1) passed as parameter, 2) from database (config.has_api_key), 3) from .env settings
    if provider_type in PROVIDER_CLOUD_TYPES:
        if not config.has_api_key and not api_key:
            logger.warning(
                f"Provider '{config.name}' ({provider_type}) has no API key configured in database. "
                "Attempting to use environment variable fallback..."
            )
            # Try to get API key from settings (.env)
            try:
                settings = get_settings()
                if provider_type == "openrouter":
                    api_key = settings.openrouter_api_key or None
                elif provider_type == "deepseek":
                    api_key = settings.deepseek_api_key or None
                elif provider_type == "groq":
                    api_key = settings.groq_api_key or None
                elif provider_type == "openai":
                    api_key = settings.openai_api_key or None
                elif provider_type == "anthropic":
                    api_key = settings.anthropic_api_key or None
                elif provider_type == "ollama_cloud":
                    api_key = settings.ollama_cloud_api_key or None
                
                if api_key:
                    logger.info(f"✅ Using API key from .env for {provider_type}")
                else:
                    logger.error(f"❌ No API key found in .env for {provider_type}")
            except Exception as e:
                logger.error(f"❌ Failed to load API key from settings: {e}")

    logger.info(f"Creating LLM client | provider={provider_type} | model={model_name}")

    # Create client based on provider type
    # Note: We only pass api_key if it's not None, allowing LangChain to use env vars as fallback
    if provider_type == "ollama":
        return _create_ollama_client(
            model=model_name,
            base_url=base_url,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )

    elif provider_type == "ollama_cloud":
        return _create_ollama_cloud_client(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )

    elif provider_type == "openai":
        return _create_openai_client(
            model=model_name,
            api_key=api_key,  # LangChain will use OPENAI_API_KEY env var if None
            base_url=base_url,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )

    elif provider_type == "anthropic":
        return _create_anthropic_client(
            model=model_name,
            api_key=api_key,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )

    elif provider_type == "openrouter":
        return _create_openrouter_client(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )

    elif provider_type == "deepseek":
        return _create_deepseek_client(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )

    elif provider_type == "groq":
        return _create_groq_client(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )

    else:
        raise ValueError(f"Unsupported provider type: {provider_type}")


def _create_ollama_cloud_client(
    model: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.0,
    top_p: float = 0.7,
    max_tokens: int = 2000,
) -> Any:
    """Create ChatOpenAI client for Ollama Cloud (OpenAI-compatible API).

    Ollama Cloud exposes an OpenAI-compatible endpoint at
    https://ollama.com/v1 — ChatOpenAI with base_url + api_key is the
    supported path (ChatOllama is local-only in this stack).
    """
    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=model,
            api_key=cast(Any, api_key) if api_key else None,
            base_url=base_url,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,  # type: ignore[call-arg]
        )
        logger.info(
            f"✅ Created ChatOpenAI client (Ollama Cloud) | model={model} | "
            f"base_url={base_url} | temperature={temperature} | top_p={top_p}"
        )
        return llm

    except ImportError as e:
        logger.error(f"❌ langchain_openai not installed: {e}")
        raise ImportError(
            "langchain_openai is required for Ollama Cloud provider. "
            "Install with: uv add langchain-openai"
        )


def _create_ollama_client(
    model: str,
    base_url: Optional[str] = None,
    temperature: float = 0.0,
    top_p: float = 0.7,
    max_tokens: int = 2000,
) -> Any:
    """Create ChatOllama client."""
    try:
        from langchain_ollama import ChatOllama

        llm = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=temperature,
            top_p=top_p,
            num_predict=max_tokens,
        )
        logger.info(f"✅ Created ChatOllama client | model={model} | base_url={base_url} | temperature={temperature} | top_p={top_p}")
        return llm
        
    except ImportError as e:
        logger.error(f"❌ langchain_ollama not installed: {e}")
        raise ImportError(
            "langchain_ollama is required for Ollama provider. "
            "Install with: uv add langchain-ollama"
        ) from e


def _create_openai_client(
    model: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.0,
    top_p: float = 0.7,
    max_tokens: int = 2000,
) -> Any:
    """Create ChatOpenAI client."""
    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=model,
            api_key=cast(Any, api_key) if api_key else None,
            base_url=base_url,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,  # type: ignore[call-arg]
        )
        logger.info(f"✅ Created ChatOpenAI client | model={model} | temperature={temperature} | top_p={top_p}")
        return llm
        
    except ImportError as e:
        logger.error(f"❌ langchain_openai not installed: {e}")
        raise ImportError(
            "langchain_openai is required for OpenAI provider. "
            "Install with: uv add langchain-openai"
        ) from e


def _create_anthropic_client(
    model: str,
    api_key: Optional[str] = None,
    temperature: float = 0.0,
    top_p: float = 0.7,
    max_tokens: int = 2000,
) -> Any:
    """Create ChatAnthropic client."""
    try:
        from langchain_anthropic import ChatAnthropic  # type: ignore[import-not-found]

        llm = ChatAnthropic(
            model=model,
            api_key=api_key,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )
        logger.info(f"✅ Created ChatAnthropic client | model={model} | temperature={temperature} | top_p={top_p}")
        return llm
        
    except ImportError as e:
        logger.error(f"❌ langchain_anthropic not installed: {e}")
        raise ImportError(
            "langchain_anthropic is required for Anthropic provider. "
            "Install with: uv add langchain-anthropic"
        ) from e


def _create_openrouter_client(
    model: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.0,
    top_p: float = 0.7,
    max_tokens: int = 2000,
) -> Any:
    """Create OpenRouter client (via OpenAI-compatible API)."""
    try:
        from langchain_openai import ChatOpenAI

        # OpenRouter uses OpenAI-compatible API
        llm = ChatOpenAI(
            model=model,
            api_key=cast(Any, api_key) if api_key else None,
            base_url=base_url,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,  # type: ignore[call-arg]
        )
        logger.info(f"✅ Created OpenRouter client | model={model} | temperature={temperature} | top_p={top_p}")
        return llm
        
    except ImportError as e:
        logger.error(f"❌ langchain_openai not installed: {e}")
        raise ImportError(
            "langchain_openai is required for OpenRouter provider. "
            "Install with: uv add langchain-openai"
        ) from e


def _create_deepseek_client(
    model: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.0,
    top_p: float = 0.7,
    max_tokens: int = 2000,
) -> Any:
    """Create DeepSeek client (via OpenAI-compatible API)."""
    try:
        from langchain_openai import ChatOpenAI

        # DeepSeek uses OpenAI-compatible API
        llm = ChatOpenAI(
            model=model,
            api_key=cast(Any, api_key) if api_key else None,
            base_url=base_url,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,  # type: ignore[call-arg]
        )
        logger.info(f"✅ Created DeepSeek client | model={model} | temperature={temperature} | top_p={top_p}")
        return llm
        
    except ImportError as e:
        logger.error(f"❌ langchain_openai not installed: {e}")
        raise ImportError(
            "langchain_openai is required for DeepSeek provider. "
            "Install with: uv add langchain-openai"
        ) from e


def _create_groq_client(
    model: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.0,
    top_p: float = 0.7,
    max_tokens: int = 2000,
) -> Any:
    """Create Groq client (via OpenAI-compatible API)."""
    try:
        from langchain_openai import ChatOpenAI

        # Groq uses OpenAI-compatible API
        llm = ChatOpenAI(
            model=model,
            api_key=cast(Any, api_key) if api_key else None,
            base_url=base_url,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,  # type: ignore[call-arg]
        )
        logger.info(f"✅ Created Groq client | model={model} | temperature={temperature} | top_p={top_p}")
        return llm

    except ImportError as e:
        logger.error(f"❌ langchain_openai not installed: {e}")
        raise ImportError(
            "langchain_openai is required for Groq provider. "
            "Install with: uv add langchain-openai"
        ) from e


# ── Resolution → a client, in one place ─────────────────────────────────────────────────────────
async def get_llm_for_capability(
    db: Any,
    capability: str,
    *,
    temperature: float = 0.0,
    top_p: float = 0.7,
    max_tokens: int = 2000,
    agent: Any = None,
    override: Optional[str] = None,
) -> Any:
    """Resolve a CAPABILITY and build the client from the row its answer NAMES.

    THE SHAPE `domain/title/services.py` ALREADY USES: `capabilities.resolve()` answers *which*
    service should answer, in what ORDER, and WHY; this turns its primary answer into a client
    through `get_llm_from_config`. The capability's key, the provider row and the model all come
    from the resolution, so a consumer never chooses a provider itself — which is what removes the
    hardwired `get_default_provider()` + `gpt-4o-mini` constructions this seam replaces.

    A caller that holds no session cannot use this: resolve where the session IS and carry the
    answer down (the rule phase 3 landed for the executor).

    Returns:
        A LangChain client, or **None** when the capability resolves to nothing usable — no
        candidate at all, a candidate that names no provider row (a `speech`/`process` service, or
        a class slot no active row fills), a row the database no longer holds, or an INACTIVE one.
        The CALLER surfaces that: this never falls back to a model written in code.

    NAMED GAP — the capability's BACKUPS are not walked here. Its callers are factories that hand
    back a CLIENT and call it later inside their own retry loops, so `capabilities.attempt_chain`
    (which wraps the CALL) does not fit them yet, and `workflow-llm` resolves to a single candidate
    today, so a walk would attempt nothing extra. A backup configured for this capability will not
    be tried until the walk lands for this family; the owner is the phase that teaches it the chain
    (phase 6's statement work is its natural home).
    """
    from app.domain.providers.capabilities import resolve

    resolved = await resolve(db, capability, agent=agent, override=override)
    primary = resolved.primary

    if primary is None:
        logger.warning(
            "capability '%s': nothing resolved (reason=%s) — the caller must surface it "
            "(this seam never falls back to a model written in code)",
            capability,
            resolved.reason,
        )
        return None

    if primary.provider_id is None:
        logger.warning(
            "capability '%s': resolved to '%s' (reason=%s), which names no provider row — "
            "it cannot answer an LLM call",
            capability,
            primary.describe(),
            resolved.reason,
        )
        return None

    from app.domain.providers.config_service import ProviderConfigService

    config_service = ProviderConfigService()
    config = await config_service.get_provider(db, primary.provider_id)
    if config is None:
        # Cannot happen while the FK cascades — but a resolution that silently loses its service
        # is the defect class this arc exists to remove, so it says so.
        logger.warning(
            "capability '%s': the row it names (provider_id=%s) does not exist",
            capability,
            primary.provider_id,
        )
        return None

    if not config.is_active:
        logger.warning(
            "capability '%s': the row it names ('%s') is INACTIVE — refusing to build a client "
            "on a service that is switched off",
            capability,
            config.name,
        )
        return None

    # THE KEY. A row that says it HAS one (`has_api_key`) still carries none: the value lives in the
    # secrets store, keyed by provider TYPE (`.env` via `EnvKeyStore`). The house
    # shape is to fetch it and hand it to the factory — the title service and
    # `workflows/nodes/agent_nodes.py` both do exactly this — because the openai-shaped adapters
    # refuse to construct without a non-empty key. Measured live (2026-09-30): without this fetch
    # every factory-built client died at `Missing credentials`, on the default row, before this
    # phase and after it.
    api_key = await config_service.get_api_key(db, primary.provider_id)
    if not api_key and provider_location(config.provider_type, config.base_url) == "local":
        # A LOOPBACK row is keyless by nature but its adapter still needs a non-empty value — the
        # house placeholder, spelled the same way the chat executors spell it.
        api_key = LOCAL_KEY_PLACEHOLDER

    # THE RESOLVER'S ANSWER IS THE MODEL. `get_llm_from_config` reads the model off the ROW, so a
    # candidate that PINS a model (a capability's own `model` column) would be silently ignored and
    # the row's default used instead — a second answer to a decided question. Hand the factory the
    # resolved model.
    effective = config
    if primary.model and primary.model != (config.config or {}).get("default_model"):
        effective = copy.copy(config)
        effective.config = {**(config.config or {}), "default_model": primary.model}

    logger.info(
        "✅ capability '%s' → %s (reason=%s)",
        capability,
        primary.describe(),
        resolved.reason,
    )
    return get_llm_from_config(
        effective,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        api_key=api_key,
    )


# The retired `get_default_llm()` used to live here: a convenience wrapper over
# `get_default_provider()` + `get_llm_from_config()` with ZERO callers tree-wide.
# It was a second answer to "which provider?", reading the default row — the exact
# thing the capability layer replaced. A consumer asks `get_llm_for_capability()`
# (above) or resolves its own capability; there is no default-row shortcut.
