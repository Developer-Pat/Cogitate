"""
Title Service for auto-generating chat session titles.

Provides dedicated title generation with:
- Configurable LLM provider (local Ollama or cloud providers)
- Error handling and logging
- User settings integration (enable/disable toggle)
- Monitoring and metrics tracking (Task 3.3.5)
"""

import logging
import os
import re
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from litellm import acompletion

# THE STATEMENT'S ONE HOME (phase 6, group 3). A domain module may not import from `api/`, so the
# wording the chat path uses lives in the domain and both paths render through it — one wording,
# one place, every surface (the roadmap's decision 3).
from app.domain.providers.failure_statement import failure_sentence_for, provider_reported

logger = logging.getLogger(__name__)

# The capability this service resolves through — the key the seed created for it
# (`alembic/versions/z5a6b7c8d9e0_capabilities.py`). Read at CALL time, not bound at
# import, so a caller (or a test) can point the service at another row.
TITLE_CAPABILITY_KEY = "title"


@dataclass
class TitleGenerationMetrics:
    """Metrics for title generation monitoring."""
    total_attempts: int = 0
    successful_generations: int = 0
    failed_generations: int = 0
    total_time_ms: float = 0.0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_attempts == 0:
            return 0.0
        return (self.successful_generations / self.total_attempts) * 100
    
    @property
    def average_time_ms(self) -> float:
        """Calculate average generation time."""
        if self.successful_generations == 0:
            return 0.0
        return self.total_time_ms / self.successful_generations
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_attempts": self.total_attempts,
            "successful_generations": self.successful_generations,
            "failed_generations": self.failed_generations,
            "success_rate": round(self.success_rate, 2),
            "average_time_ms": round(self.average_time_ms, 2),
            "last_error": self.last_error,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
        }


class TitleService:
    """
    Service for generating chat session titles.
    
    Features:
    - Dedicated LLM configuration separate from agent chat
    - Supports both local (Ollama) and cloud providers
    - Configurable via environment variables
    - Error handling with comprehensive logging
    - Monitoring and metrics tracking (Task 3.3.5)
    """
    
    # Title generation prompts for different model types
    TITLE_PROMPTS = {
        "default": """Generate a concise title (3-5 words) for this conversation. Respond with ONLY the title, no quotes or explanation.

Conversation:
{messages}

Title:""",
        
        "simple": """Summarize this conversation in 3-5 words:
{messages}""",
        
        "keyword": """Extract 3 key topics from this conversation. Respond with comma-separated topics only:
{messages}

Topics:""",
    }
    
    def __init__(self) -> None:
        """
        Initialize title service — the CAPABILITY over the provider rows
        (2026-09-03, the Option-A refactor).

        Configuration resolution — THE RESOLVER's ladder, one home
        (`domain/providers/capabilities.py`; this service became its first
        consumer in the service-capability arc's Phase 2, 2026-09-30):
        1. An explicit model_override from the caller (agent-model / custom
           preference, passed per-request) — the ladder's OVERRIDE rung.
        2. The `title` capability's own chain (the seed points it at the
           default provider row), then the global default row — the
           "backend_default" path. Same connectivity as chat: aliases,
           keys, rows.
        3. NO silent fallback. If resolution fails (nothing configured,
           inactive provider, missing key) the failure is LOUD — a
           structured TITLE-GEN FAILED log with the reason — and the
           caller surfaces it to the user.

        NO AGENT is passed to the resolver here: the title never follows
        an agent's model, which is the behaviour it has always had.

        Reasoning models (deepseek-v4-flash and friends) "think" before
        answering and eat a small max_tokens budget entirely -> empty
        titles (the Aug-22 mystery, reproduced 2026-09-02). The title
        task is SIMPLE: a reasoning model here is an anti-pattern. The
        fix is provider-aware reasoning_effort="none" (deepseek accepts
        it; the local llama-server's openai adapter REJECTS it), not a
        universal knob.
        """
        # Global enable/disable toggle
        self.enabled = os.getenv("TITLE_LLM_ENABLED", "true").lower() == "true"

        # Model-specific settings (titles are short; 128 is ample once
        # reasoning is off — the old 20/64 budgets were reasoning-eaten)
        self.max_tokens = int(os.getenv("TITLE_LLM_MAX_TOKENS", "128"))
        self.temperature = float(os.getenv("TITLE_LLM_TEMPERATURE", "0.3"))

        # Runtime configuration (populated per-request from the DB
        # default provider row or the model_override)
        self.provider: Optional[str] = None
        self.model: Optional[str] = None
        self.provider_type: Optional[str] = None
        self.base_url: Optional[str] = None
        self.api_key: Optional[str] = None

        # Monitoring metrics (Task 3.3.5)
        self.metrics = TitleGenerationMetrics()

        # Configuration TTL: re-read the database after this many seconds so
        # a provider change takes effect without a server restart.
        self._CONFIG_TTL_SECONDS = 300
        # Timestamp of the last successful config load (None = never loaded)
        self._config_loaded_at: Optional[float] = None

        logger.info(
            f"TitleService initialized (capability-over-provider-rows): "
            f"enabled={self.enabled}, max_tokens={self.max_tokens}, "
            f"temperature={self.temperature}"
        )

    def _config_is_fresh(self) -> bool:
        """Return True if the config was loaded within the TTL window."""
        if self._config_loaded_at is None:
            return False
        return (time.time() - self._config_loaded_at) < self._CONFIG_TTL_SECONDS

    async def load_config_from_database(self, db) -> bool:
        """
        Resolve the `title` capability through THE resolver — one answer to
        "which service?" (`domain/providers/capabilities.py`; this service is
        its first CONSUMER, the service-capability arc's Phase 2) — and load
        the provider row that resolution NAMES.

        The ladder lives in that one module: an explicit override, the
        capability's own chain, then the global default row. NO agent is
        passed, so the per-agent rung is skipped by design.

        The resolver answers WHICH service; the row it names supplies the
        connection details (base_url, whether a key is present, whether it is
        active), because a resolution carries no client. Resolution honors the
        litellm alias map by provider NAME (the local 'llama' row is
        provider_type 'openai' + base_url 127.0.0.1:8080 — routing through the
        shared alias keeps the model string correct). Sets
        self.reasoning_effort when the resolved provider is a
        reasoning-capable cloud family (deepseek accepts
        reasoning_effort="none"; the local llama-server REJECTS it — the knob
        is provider-aware, never universal).

        Returns:
            True if a service resolved AND validated, False if not
            (the caller applies the NO-SILENT-FALLBACK marker).
        """
        try:
            from app.domain.providers.capabilities import resolve
            from app.domain.providers.config_service import ProviderConfigService
            from app.domain.providers.litellm_route import HANDLER_BY_TYPE

            resolved = await resolve(db, TITLE_CAPABILITY_KEY)
            primary = resolved.primary

            if primary is None:
                logger.warning(
                    "No service resolved for the title capability "
                    f"(reason={resolved.reason}).",
                    extra={"action": "configure_default_provider",
                           "fallback_reason": "no_default_provider",
                           "resolution_reason": resolved.reason},
                )
                return False

            if primary.provider_id is None:
                logger.warning(
                    f"Title capability resolved to '{primary.describe()}' "
                    f"(reason={resolved.reason}) — not a provider row, so it cannot "
                    f"answer a title.",
                    extra={"action": "configure_default_provider",
                           "fallback_reason": "candidate_names_no_provider_row",
                           "resolution_reason": resolved.reason},
                )
                return False

            config = await ProviderConfigService().get_provider(db, primary.provider_id)
            if config is None:
                # Cannot happen while the FK cascades — but a resolution that
                # silently loses its service is the defect class this arc
                # exists to remove, so it says so.
                logger.warning(
                    f"Title capability resolved to provider {primary.provider_id}, "
                    f"which does not exist.",
                    extra={"action": "configure_default_provider",
                           "fallback_reason": "provider_row_missing",
                           "resolution_reason": resolved.reason},
                )
                return False

            # Validate configuration
            issues = []
            if not config.is_active:
                issues.append("Provider is not active")

            # The resolver already applied "an explicit model on the candidate
            # beats the row's own default_model" — its answer IS the model.
            model_name = primary.model

            # THE TYPE/NAME RESOLUTION (2026-09-03): the providers table
            # conflates adapter-type with identity. The local 'llama' row
            # is provider_type='openai' (the litellm adapter) but its NAME
            # is 'llama'. Cloud families need an API key; ADAPTER rows are
            # keyless by nature. Those are the rows whose TYPE litellm has no
            # prefix for (`litellm_route.HANDLER_BY_TYPE`) — the same table the
            # handler itself comes from, so this can never disagree with it.
            provider_key = config.name or config.provider_type
            is_local_alias = (config.provider_type or provider_key) in HANDLER_BY_TYPE

            if not is_local_alias and config.provider_type in ["openai", "anthropic", "openrouter", "deepseek"]:
                if not config.has_api_key:
                    issues.append("API key not configured")
            elif is_local_alias:
                # A LOCAL SERVER THAT NAMES ITSELF IS NOT MISCONFIGURED (2026-10-09). A
                # loopback server mounts its model at launch and reports it on /v1/models;
                # `get_llm_from_config` takes that answer, so an empty local default_model is
                # not the fault this check was written to catch. An unreachable server still is.
                from app.domain.providers.llm_factory import single_served_model

                if not model_name and not single_served_model(config):
                    issues.append("No model configured (set the local provider's default_model)")

            if issues:
                logger.warning(
                    f"Resolved title provider has issues: {'; '.join(issues)}.",
                    extra={"issues": issues,
                           "fallback_reason": "provider_validation_failed"},
                )
                return False

            # The provider NAME drives the local-server lookup ('llama' -> the
            # 127.0.0.1:8080 address); provider_type is the fallback key and is what decides the
            # litellm handler the request rides (`litellm_route`).
            self.provider = provider_key
            self.model = model_name
            self.provider_type = config.provider_type
            self.base_url = config.base_url

            # The api_key for cloud providers (env_key_store — .env is the store)
            self.api_key = None
            if config.has_api_key and config.id is not None:
                try:
                    from app.domain.providers.config_service import ProviderConfigService
                    key_service = ProviderConfigService()
                    self.api_key = await key_service.get_api_key(db, config.id)
                except Exception as key_err:
                    logger.warning(
                        f"Could not load API key for provider '{config.name}': {key_err}",
                        extra={"provider": config.name, "error_type": type(key_err).__name__}
                    )

            # REASONING-EFFORT: provider-aware, never universal. The local
            # llama-server (openai adapter) REJECTS the kwarg (proven
            # 2026-09-02 — UnsupportedParamsError); deepseek accepts
            # "none" and NEEDS it for the simple title task (the empty-
            # title bug — reasoning ate the budget). Non-alias cloud rows
            # are the reasoning-capable families.
            self.reasoning_effort = None
            if not is_local_alias and provider_key not in ("openai", "anthropic"):
                # deepseek / openrouter / groq-style cloud rows: the
                # reasoning models live here — turn thinking OFF for the
                # simple title task.
                self.reasoning_effort = "none"
                logger.info(
                    f"Title capability: {provider_key} resolved — "
                    f"reasoning_effort='none' (the simple-task anti-reasoning rule)"
                )

            logger.info(
                f"Title capability resolved (resolver — {resolved.reason}): "
                f"provider={self.provider}, model={self.model}, "
                f"base_url={self.base_url}, has_api_key={self.api_key is not None}"
            )
            self._config_loaded_at = time.time()
            return True

        except Exception as e:
            logger.error(
                f"Failed to load config from database: {e}",
                exc_info=True,
                extra={"error_type": type(e).__name__}
            )
            return False
    def apply_fallback_config(self, reason: str = "database_unavailable") -> None:
        """
        NO-SILENT-FALLBACK (2026-09-03, the choke-point semantics the
        user asked for): the title service resolves ONLY through the
        `title` capability's resolver (its configured chain, then the
        global default row) or an explicit per-request override. When
        that resolution fails, the service does NOT quietly point at a
        second-best provider — it marks itself unresolved and logs a
        LOUD structured marker. The caller turns that into a user-visible
        error. The old TITLE_LLM_* env universe (ollama/llama3.2) is
        GONE — that silent swap was the rename-dead root cause (ollama
        OOM on the Bonsai-occupied GPU).

        Args:
            reason: Reason for the failed resolution (for the log)
        """
        # The unresolved state — generation will fail loudly at the call site
        self.provider = None
        self.model = None
        self.base_url = None
        self.api_key = None

        # THE CHOKE-POINT MARKER: one grep-able line per fallback event
        logger.error(
            f"TITLE-GEN CONFIG FAILED reason={reason} "
            f"resolved_provider=None model=None — no silent fallback (the "
            f"old TITLE_LLM_* env universe is retired)",
            extra={
                "action": "title_capability_resolution",
                "fallback_reason": reason,
                "silent_fallback": False,
            }
        )
        self._config_loaded_at = time.time()

    def _get_model_string(self) -> str:
        """
        Get the litellm model string — the ONE alias map applied
        (2026-09-03). 'llama' routes through the openai adapter with the
        api_base; 'ollama_cloud' through the openai adapter + ollama.com;
        everything else is provider/model. This is the SAME map the chat
        executors use — the title capability rides the chat connectivity.
        """
        from app.domain.providers.litellm_route import litellm_model_string
        return litellm_model_string(self.provider or "", self.model or "", self.provider_type)

    def _get_llm_config(self) -> Dict[str, Any]:
        """
        Get LLM configuration for title generation — alias-aware
        (2026-09-03).

        Returns:
            Configuration dict for LiteLLM (model, max_tokens, temp,
            optional api_base / api_key / reasoning_effort)
        """
        from app.domain.providers.litellm_route import api_base_for, litellm_model_string
        from app.domain.providers.provider_endpoints import resolve_endpoint
        model_name = litellm_model_string(self.provider or "", self.model or "", self.provider_type)
        # THE ROW's address, through the resolver that owns the rule (2026-10-12, stage 2) — the
        # row's own `base_url`, else its type's canonical endpoint. No table, no copy.
        api_base = api_base_for(
            model_name,
            resolve_endpoint(
                self.provider_type or self.provider or "", self.base_url, self.provider or ""
            ),
        )

        config: Dict[str, Any] = {
            "model": model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        # Alias-mapped local servers carry their api_base (llama ->
        # 127.0.0.1:8080/v1, ollama_cloud -> ollama.com); they are
        # keyless — litellm's openai adapter needs a NON-EMPTY key
        # (the Bonsai test, 2026-09-01 — 'Missing credentials').
        if api_base:
            config["api_base"] = api_base
            if self.api_key:
                config["api_key"] = self.api_key
            else:
                from app.domain.providers.llm_factory import placeholder_key_for

                _placeholder = placeholder_key_for(api_base, model_name)
                if _placeholder:
                    config["api_key"] = _placeholder
        elif self.api_key:
            config["api_key"] = self.api_key

        # REASONING-EFFORT — set ONLY when the resolution flagged a
        # reasoning-capable cloud family; never sent to the local
        # servers (their openai adapter rejects the kwarg).
        effort = getattr(self, "reasoning_effort", None)
        if effort:
            config["reasoning_effort"] = effort

        return config

    def _report_failure(self, reason: str, *, notify: bool) -> None:
        """Say a title failure where the user can SEE it — A2, the phase 6 group 3 landing.

        THE DEFECT THIS CLOSES: the auto path's failure had no surface at all. `generate_title`
        logs a grep-able marker and returns `None`, so its caller could not report anything — it
        cannot even tell a failure from a benign refusal, and it holds no provider to name.

        The report happens HERE because this is where the failure is KNOWN: this method's caller
        holds the provider and model it resolved to, and the exception it caught.

        `notify` is the AUTO path's opt-in and it is a per-CALL decision, not a policy of the
        service, because both paths call `generate_title` and only one of them needs a toast. The
        MANUAL path (`POST /chat/generate-title`) passes False: its 500 + detail is already the
        surface, and a toast on top would report one failure twice (`chat/title_router.py`).
        """
        if not notify:
            return

        # The house's local import at the publish site (the executor, the chat router and the
        # completion service all do this) — the bus is a singleton wiring concern, not a domain
        # dependency of the title service.
        from app.domain.messaging.services import publish_warning

        publish_warning(
            "Session title not generated",
            failure_sentence_for(self.model, self.provider, reason),
            kind="title-failure",
        )

    async def generate_title(
        self,
        messages: List[Dict[str, str]],
        user_enabled: bool = True,
        db: Optional[Any] = None,
        model_override: Optional[str] = None,
        notify_failure: bool = False,
    ) -> Optional[str]:
        """
        Generate a title for the conversation.

        Args:
            messages: List of conversation messages (role, content)
            user_enabled: Whether user has enabled auto-title in settings
            db: Optional database session (AsyncSession) for resolving the title
                capability through the resolver
            model_override: Optional model string to override configured model (e.g., "ollama/llama3.2")
            notify_failure: Publish the failure as a WARNING the user SEES. The AUTO path passes
                True — its failure had no surface at all (phase 6, group 3) — while the MANUAL path
                leaves it False because its own 500 + detail is already the surface.

        Returns:
            Generated title string, or None if generation failed/disabled
        """
        # Check if title service is enabled globally
        if not self.enabled:
            logger.debug("TitleService is disabled globally")
            return None
        
        # Check if user has enabled auto-title
        if not user_enabled:
            logger.debug("Auto-title disabled by user settings")
            return None
        
        # Need at least one message (user or assistant)
        if not messages:
            logger.debug("No messages for title generation")
            return None
        
        # Load configuration if not loaded or if TTL has expired
        if not self._config_is_fresh():
            if db:
                loaded_from_db = await self.load_config_from_database(db)
                if not loaded_from_db:
                    self.apply_fallback_config(reason="no_default_provider")
            else:
                # No database session provided — the capability cannot
                # resolve without the provider row; loud marker.
                self.apply_fallback_config(reason="database_unavailable")
        
        # Validate configuration before proceeding
        if not self.model:
            logger.error(
                "TitleService has no model configured after loading. "
                "Cannot generate title.",
                extra={"action": "configure_title_service_model"}
            )
            return None
        
        # Track metrics (Task 3.3.5)
        self.metrics.total_attempts += 1
        start_time = time.time()
        
        try:
            # Prepare conversation context (limit to first 5 messages)
            conversation_text = "\n".join(
                f"{m['role']}: {m['content']}"
                for m in messages[:5]
            )
            
            # Build prompt
            prompt = self.TITLE_PROMPTS["default"].format(messages=conversation_text)

            # Model override handling — the resolver's OVERRIDE rung (the
            # service-capability arc's Phase 2, 2026-09-30): the override string
            # is "provider/model" (deepseek/deepseek-v4-flash from the
            # frontend's agent/custom preference, or an alias name like llama/…
            # for local servers) and it is resolved THROUGH the one ladder
            # rather than parsed here, so "which service" has ONE home for both
            # entry paths. A caller with no session resolves the same rung
            # through the same module (override_candidate) — never by splitting
            # the string again. Resolution sets the service state FIRST
            # (provider/model/key) then ONE alias-aware _get_llm_config() build.
            #
            # The guard is deliberate and unchanged: a slashless override is
            # IGNORED (the capability resolution stands), exactly as before.
            if model_override and "/" in model_override:
                from app.domain.providers.capabilities import override_candidate, resolve
                from app.domain.providers.litellm_route import HANDLER_BY_TYPE

                if db:
                    chosen = (await resolve(db, TITLE_CAPABILITY_KEY, override=model_override)).primary
                    if chosen is None:  # rung 1 always yields a candidate; the type says Optional
                        chosen = override_candidate(model_override)
                else:
                    chosen = override_candidate(model_override)

                override_provider = chosen.provider or ""
                is_alias = (chosen.provider_type or override_provider) in HANDLER_BY_TYPE

                self.provider = override_provider
                self.model = chosen.model
                self.provider_type = chosen.provider_type
                self.api_key = None

                if not is_alias:
                    # Cloud-family override: load the key from the provider
                    # row (env_key_store), then the anti-reasoning rule.
                    if db:
                        try:
                            from app.domain.providers.config_service import ProviderConfigService
                            key_service = ProviderConfigService()
                            provider_config = await key_service.get_provider_by_name(db, override_provider)
                            if provider_config and provider_config.has_api_key and provider_config.id is not None:
                                self.api_key = await key_service.get_api_key(db, provider_config.id)
                                logger.info(
                                    f"Loaded API key for override provider '{override_provider}'",
                                    extra={"provider": override_provider}
                                )
                        except Exception as key_err:
                            logger.warning(
                                f"Could not load API key for override provider '{override_provider}': {key_err}",
                                extra={"provider": override_provider, "error_type": type(key_err).__name__}
                            )
                    # THE SIMPLE-TASK ANTI-REASONING RULE: cloud overrides
                    # (deepseek etc.) get reasoning_effort="none" — a
                    # reasoning model on a 3-5-word title burns the budget
                    # thinking and returns empty (the Aug-22 mystery).
                    self.reasoning_effort = "none"
                    logger.info(
                        f"Title override {override_provider}: reasoning_effort='none' "
                        f"(the simple-task anti-reasoning rule)"
                    )
                else:
                    # Alias override (llama/...): local server — never send
                    # reasoning_effort (the openai adapter rejects it).
                    self.reasoning_effort = None

                logger.info(
                    f"Using model override: {model_override} (resolver — override)",
                    extra={"model_override": model_override, "alias": is_alias}
                )

            # Get LLM configuration (alias-aware: model string, api_base,
            # keyless placeholder for local, reasoning_effort when set)
            llm_config = self._get_llm_config()
            # Call LLM — reasoning_effort rides llm_config when the
            # resolution flagged a reasoning-capable cloud family (the
            # simple-task anti-reasoning rule); absent for local servers.
            response = await acompletion(
                model=llm_config["model"],
                messages=[
                    {"role": "system", "content": "Generate concise titles. Respond with ONLY the title, no markdown formatting, no quotes, no explanations."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=llm_config["max_tokens"],
                temperature=llm_config["temperature"],
                api_base=llm_config.get("api_base"),
                api_key=llm_config.get("api_key"),
                reasoning_effort=llm_config.get("reasoning_effort"),
            )

            # Extract and clean title
            title = response.choices[0].message.content.strip()

            # Remove markdown formatting
            # Remove bold/italic markers: **text**, *text*, __text__, _text_
            title = re.sub(r'\*\*(.+?)\*\*', r'\1', title)  # Remove **bold**
            title = re.sub(r'\*(.+?)\*', r'\1', title)      # Remove *italic*
            title = re.sub(r'__(.+?)__', r'\1', title)      # Remove __bold__
            title = re.sub(r'_(.+?)_', r'\1', title)        # Remove _italic_
            title = re.sub(r'`(.+?)`', r'\1', title)        # Remove `code`
            
            # Remove quotes if present
            if title.startswith('"') and title.endswith('"'):
                title = title[1:-1]
            if title.startswith("'") and title.endswith("'"):
                title = title[1:-1]
            
            # Remove any leading/trailing special characters
            title = title.strip('*_`"\' ')

            # Limit title length
            if len(title) > 100:
                title = title[:97] + "..."
            
            # Track successful generation (Task 3.3.5)
            elapsed_ms = (time.time() - start_time) * 1000
            self.metrics.successful_generations += 1
            self.metrics.total_time_ms += elapsed_ms
            
            logger.info(
                f"Generated title: '{title}'",
                extra={
                    "elapsed_ms": round(elapsed_ms, 2),
                    "success_rate": round(self.metrics.success_rate, 2),
                }
            )
            return title
            
        except Exception as e:
            # Track failed generation (Task 3.3.5)
            self.metrics.failed_generations += 1
            self.metrics.last_error = str(e)
            self.metrics.last_error_time = datetime.now()

            # THE STRUCTURED FAILURE MARKER (2026-09-03, the user's
            # "log the failure so it's easy to diagnose" ask): one
            # grep-able line carrying provider/model/config-source/reason
            # — a title failure is diagnosable from the log alone.
            logger.error(
                f"TITLE-GEN FAILED provider={self.provider} model={self.model} "
                f"reason={type(e).__name__}: {e}",
                exc_info=True,
                extra={
                    "action": "title_generation",
                    "provider": self.provider,
                    "model": self.model,
                    "config_source": "capability_resolution" if self.provider else "unresolved",
                    "reasoning_effort": getattr(self, "reasoning_effort", None),
                    "error_type": type(e).__name__,
                }
            )
            # AND THE SURFACE (phase 6, group 3). The marker above is for the log; this is for the
            # user — the same failure, in the one wording, naming the provider and model it was
            # sent to. Before this the auto path stopped at the log line and the session simply
            # never got a title.
            self._report_failure(provider_reported(e), notify=notify_failure)
            return None
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test the title capability LLM connection — the alias-aware
        config (2026-09-03): the SAME _get_llm_config the generation
        uses (model string via the ONE map, api_base, keyless
        placeholder, reasoning_effort when set). This is the "Test
        service" button's backend — it validates the provider row the
        way the real call will use it.

        Returns:
            Dict with connection status and details
        """
        from litellm import acompletion
        result = {
            "success": False,
            "provider": self.provider,
            "model": self.model,
            "error": None,
        }

        try:
            llm_config = self._get_llm_config()
            await acompletion(
                model=llm_config["model"],
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
                api_base=llm_config.get("api_base"),
                api_key=llm_config.get("api_key"),
                reasoning_effort=llm_config.get("reasoning_effort"),
            )

            result["success"] = True
            result["message"] = f"Successfully connected to {self.provider}/{self.model}"
            logger.info(f"TitleService connection test successful: {result}")

        except Exception as e:
            result["error"] = str(e)
            result["message"] = f"Failed to connect: {e}"
            logger.error(f"TitleService connection test failed: {e}", exc_info=True)

        return result
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get current title service configuration.
        
        Returns:
            Dict with current configuration
        """
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get title generation metrics.
        
        Returns:
            Dict with metrics including success rate, average time, etc.
        """
        return self.metrics.to_dict()


# Singleton instance for use across the application
_title_service_instance: Optional[TitleService] = None


def get_title_service() -> TitleService:
    """Get or create the title service singleton."""
    global _title_service_instance
    if _title_service_instance is None:
        _title_service_instance = TitleService()
    return _title_service_instance