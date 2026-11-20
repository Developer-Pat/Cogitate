"""
Agent Executor — pipeline component that executes the agent's logic.

The Executor takes the assembled ``Context`` and runs the agent's
core logic — typically an LLM call with tool execution, but potentially
any execution strategy (direct code execution, workflow dispatch, etc.).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from .models import (
    AgentDescriptor,
    ComponentTrace,
    Context,
    Timer,
)
from .registry import Registry
from .output_budget import (
    DEEP_MIN_BUDGET,
    EXECUTOR_PASS1_CAP,
    FALLBACK_BUDGET,
    FAST_POLICY_BUDGET,
    floor_budget,
)
from .reasoning_support import extract_response_text
from app.domain.providers.litellm_route import api_base_for, litellm_model_string

logger = logging.getLogger(__name__)


def log_usage(
    agent: AgentDescriptor,
    attempt_str: str,
    response: Any,
    response_time_ms: int,
    success: bool,
    error_message: str | None = None,
) -> None:
    """Log an LLM call to usage_logs (THE LOCAL-OLLAMA TRACKING —
    2026-08-24: the pipeline workers bypassed the chat logger, so
    the local volumes were invisible in the cost page).

    Direct-sqlite (the established sync pattern for the background
    paths — no ORM session here). session_id is NULL for pipeline
    calls (the model now allows it); agent_id carries the worker.
    NEVER raises — a usage-log failure must not kill the pipeline.
    """
    try:
        usage = getattr(response, "usage", None)
        prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion = int(getattr(usage, "completion_tokens", 0) or 0)
        provider = attempt_str.split("/", 1)[0] if "/" in attempt_str else attempt_str
        model = attempt_str.split("/", 1)[1] if "/" in attempt_str else attempt_str

        # WHO IS LOGGING, and as whom. A pipeline call is the one place a row can
        # be attributed to an agent, so the line names the agent it charges.
        logger.info(
            "usage log: agent=%s attempt=%s tokens=%d/%d ms=%d success=%s",
            agent.id, attempt_str, prompt, completion, response_time_ms, success,
        )

        import sqlite3

        from app.core.config import get_settings
        from app.core.config import Paths as _Paths
        # THE SETTINGS-DERIVED PATH, never the class attribute. `Paths.shared_db`
        # is a dataclass FIELD DEFAULT (config.py) — a fixed BASE_DIR/cogitate.db —
        # so it ignores DATABASE_URL, which is exactly how the test suite came to
        # write usage rows into the operator's live database: this function reached
        # for the default while every redirected path (agents, trash, data) followed
        # `from_settings`. One locator, and it is the settings one.
        _db = _Paths.from_settings(get_settings()).shared_db
        conn = sqlite3.connect(str(_db))
        try:
            conn.execute(
                "INSERT INTO usage_logs (session_id, agent_id, provider, model,"
                " prompt_tokens, completion_tokens, total_tokens, cost_usd,"
                " response_time_ms, success, error_message)"
                " VALUES (NULL, ?, ?, ?, ?, ?, ?, 0.0, ?, ?, ?)",
                (agent.id, provider, model, prompt, completion,
                 prompt + completion, response_time_ms,
                 1 if success else 0, error_message),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:  # noqa: BLE001
        logger.warning("usage log failed (agent=%s): %s", agent.id, e)


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class AgentExecutor(ABC):
    """Interface for agent execution strategies."""

    @abstractmethod
    async def execute(
        self,
        context: Context,
        agent: AgentDescriptor,
    ) -> str:
        """Execute the agent's logic and return the raw response text.

        Args:
            context: The assembled execution context.
            agent: Descriptor of the agent being invoked.

        Returns:
            The raw response text from the agent.
        """
        ...


# ---------------------------------------------------------------------------
# LiteLLM-based implementation (real LLM calls)
# ---------------------------------------------------------------------------

def budget_for(
    agent: Any,
    fallback: int,
    *,
    minimum: int = 0,
) -> int:
    """The budget one executor call runs with (G-F).

    `agent.output_budget` is the RESOLVER's answer for this run (set by whoever built
    the descriptor — `/agent-chat`, whose turn never used to meet the resolver at all).
    When it is present it is the number; when it is absent the executor's own
    constructor default speaks, which is the pre-G-F behaviour for every caller that
    has no resolver answer to give.

    `minimum` is the deep pass's named floor (C.3): a pass meant to reason must not run
    below it, whichever of the two numbers arrived.
    """
    resolved = getattr(agent, "output_budget", None)
    chosen = int(resolved) if resolved else int(fallback)
    return max(chosen, minimum)


class LiteLLMExecutor(AgentExecutor):
    """Executor that calls the actual LLM via LiteLLM's ``acompletion``.

    Builds a message list from the context (system prompt + history + user
    message) and sends it to the provider/model specified in the agent
    descriptor.
    """

    def __init__(self, max_tokens: int = FALLBACK_BUDGET, temperature: float = 0.7) -> None:
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def execute(
        self,
        context: Context,
        agent: AgentDescriptor,
    ) -> str:
        # Build the message list
        messages: List[Dict[str, str]] = []

        # System prompt
        if context.system_prompt:
            messages.append({"role": "system", "content": context.system_prompt})

        # Session history
        for turn in context.session_history:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            messages.append({"role": role, "content": content})

        # Current user message
        messages.append({"role": "user", "content": context.user_message})

        # Build the model string for LiteLLM: "provider/model"
        model_str = f"{agent.provider}/{agent.model}" if agent.provider else agent.model

        logger.info(
            "LiteLLMExecutor calling model=%s with %d messages",
            model_str,
            len(messages),
        )

        response, chain_used = await self._call_with_fallback(
            messages=messages,
            agent=agent,
            # G-F: the resolver's answer when the caller supplied one, else this
            # executor's own default (the pre-G-F behaviour).
            max_tokens=floor_budget(
                model_str, budget_for(agent, self.max_tokens)
            ),
        )

        if chain_used:
            # THE TURN'S OWN RECORD (R3): the response's trace names what was tried, so a degraded
            # turn is visible in the payload and not only in the log — the context is per-turn, so
            # this cannot race with another executor call.
            context.metadata["fallback_chain_used"] = list(chain_used)
            logger.warning(
                "LiteLLMExecutor FAILED OVER to %s (agent=%s fallback_enabled)",
                " → ".join(chain_used),
                agent.name,
            )
            # THE FALLBACK WARNING (2026-09-01, the user's 'silent
            # fallbacks are bad'): the user SEES the degradation —
            # the toast, not just the log.
            from app.domain.messaging.services import publish_warning

            publish_warning(
                f"{agent.name} fell back",
                f"The primary provider ({model_str}) failed — "
                f"answering via {' → '.join(chain_used)}.",
                kind="provider-fallback",
            )

        # Extract the response text (content, with the reasoning-field fallback)
        text = extract_response_text(response, model_str)
        if not text:
            logger.warning("LiteLLM returned empty response for model=%s", model_str)
        return text

    async def _call_with_fallback(
        self,
        messages: List[Dict[str, str]],
        agent: AgentDescriptor,
        max_tokens: int | None = None,
    ) -> tuple[Any, List[str]]:
        """
        Call the LLM, failing over across the RESOLUTION's ordered chain (R3).

        The chain is the resolver's — `agent.candidates`, built where the session is (the
        `output_budget` seam) — and the WALK itself is the shared loop
        (`capabilities.attempt_chain`), so an attempt and its failure logging have one home. The
        order: the lead candidate first, the agent's `preferred_providers` as its backups.

        An EMPTY chain means no resolution was supplied: the descriptor's own provider/model is the
        single attempt, and a failure propagates — the pre-resolution behaviour, preserved for every
        caller with no reading to give. ``agent.fallback_enabled`` keeps its meaning: OFF = the
        primary only, fail visibly.

        Returns:
            (response, chain_used) — chain_used lists the BACKUPS actually attempted
            ([] = the primary answered, no failover).
        """
        from litellm import acompletion

        from app.domain.providers.capabilities import (
            SOURCE_AGENT,
            ServiceCandidate,
            attempt_chain,
        )

        candidates: tuple[ServiceCandidate, ...] = tuple(
            getattr(agent, "candidates", ()) or ()
        )
        if not candidates:
            candidates = (
                ServiceCandidate(
                    ordinal=0,
                    provider=agent.provider,
                    model=agent.model or None,
                    source=SOURCE_AGENT,
                ),
            )

        async def _attempt(candidate: ServiceCandidate) -> Any:
            """One attempt — the route, the reasoning floor, the keyless local placeholder.

            THE ROUTE (2026-10-12, `litellm_route` — the ONE mapping): the handler comes from the
            candidate's provider_type, so a local llama-server rides the openai adapter with its own
            api_base (without it litellm rejects the unknown 'llama' prefix) and the ollama family
            rides the tool-capable `ollama_chat`.
            """
            model_name = litellm_model_string(
                candidate.provider or "", candidate.model or "", candidate.provider_type
            )
            # THE ADDRESS RIDES THE CANDIDATE (2026-10-12, stage 2) — the resolver filled it from the
            # row it already held, so nothing here looks an address up or carries a copy of one.
            api_base = candidate.endpoint
            logger.info("LiteLLMExecutor attempt model=%s", model_name)
            kwargs: dict = {
                "model": model_name,
                "messages": messages,
                # the reasoning-model floor applies per attempt (the
                # fallback provider may be a different family)
                "max_tokens": floor_budget(
                    model_name, budget_for(agent, max_tokens or self.max_tokens)
                ),
                "temperature": self.temperature,
            }
            if api_base:
                # THE ROOT THE HANDLER NEEDS, not the table's value verbatim: an `ollama_cloud`
                # candidate rides `ollama_chat`, which composes its own `/api/chat` onto the root.
                kwargs["api_base"] = api_base_for(model_name, api_base)
                # Keyless LOCAL servers only — a cloud endpoint with no key must fail as missing.
                from app.domain.providers.llm_factory import placeholder_key_for
                _placeholder = placeholder_key_for(kwargs["api_base"], model_name)
                if _placeholder:
                    kwargs["api_key"] = _placeholder


            _timer = Timer()
            with _timer:
                response = await acompletion(**kwargs)
            # WHAT ACTUALLY ANSWERED is what the usage row records. This used to log the PRIMARY's
            # model string, unconditionally, so a call answered by a backup left no usage row of its
            # own and the primary was credited with the backup's tokens.
            log_usage(agent, model_name, response, _timer.duration_ms, True)
            return response

        outcome = await attempt_chain(
            candidates,
            call=_attempt,
            capability="chat",
            fallbacks=bool(getattr(agent, "fallback_enabled", False)),
        )
        return outcome.response, list(outcome.fell_back_to)


# ---------------------------------------------------------------------------
# Default (stub) implementation — kept for backward compatibility
# ---------------------------------------------------------------------------

class DefaultExecutor(AgentExecutor):
    """Default executor that simulates an LLM call.

    This is a fallback stub. Use ``LiteLLMExecutor`` for real LLM calls.
    """

    async def execute(
        self,
        context: Context,
        agent: AgentDescriptor,
    ) -> str:
        return (
            f"This is a simulated response from **{agent.name}**.\n\n"
            f"You said: \"{context.user_message}\"\n\n"
            f"*Agent description:* {agent.description}\n"
            f"*History turns:* {len(context.session_history)}\n"
            f"*Provider:* {agent.provider} / {agent.model}"
        )



class FastExecutor(AgentExecutor):
    """Fast executor — optimized for speed over quality.

    Single-pass LLM call with reduced max_tokens, no tool execution,
    and minimal prompt overhead. Best for simple factual queries where
    speed matters more than depth.

    Uses LiteLLM like the default executor but with constrained parameters.
    """

    def __init__(self, max_tokens: int = FAST_POLICY_BUDGET, temperature: float = 0.3) -> None:
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def execute(
        self,
        context: Context,
        agent: AgentDescriptor,
    ) -> str:
        from litellm import acompletion

        messages: List[Dict[str, str]] = []
        if context.system_prompt:
            messages.append({"role": "system", "content": context.system_prompt})
        messages.append({"role": "user", "content": context.user_message})

        model_str = f"{agent.provider}/{agent.model}" if agent.provider else agent.model

        effective_max = floor_budget(model_str, self.max_tokens)

        logger.info(
            "FastExecutor calling model=%s (max_tokens=%d, temperature=%.1f)",
            model_str, effective_max, self.temperature,
        )

        try:
            from .models import Timer as _Timer
            with _Timer() as _t:
                response = await acompletion(
                    model=model_str,
                    messages=messages,
                    max_tokens=effective_max,
                    temperature=self.temperature,
                )
            log_usage(agent, model_str, response, _t.duration_ms, True)
            return extract_response_text(response, model_str)
        except Exception as e:
            log_usage(agent, model_str, None, 0, False, str(e)[:200])
            logger.error("FastExecutor failed for model=%s: %s", model_str, e, exc_info=True)
            raise


class HybridExecutor(AgentExecutor):
    """Hybrid executor — two-pass: fast shallow then deep reasoning.

    First pass: quick LLM call with low max_tokens and temperature.
    If the response seems incomplete or the query needs deeper reasoning
    (detected via heuristics like short responses, questions, analysis
    keywords), a second pass is made with higher token budget and
    temperature for thorough reasoning.

    Best for complex queries where you want speed when possible
    and depth when needed.
    """

    def __init__(
        self,
        fast_max_tokens: int = EXECUTOR_PASS1_CAP,
        fast_temperature: float = 0.3,
        deep_max_tokens: int = DEEP_MIN_BUDGET,
        deep_temperature: float = 0.7,
        min_deep_response_length: int = 50,
    ) -> None:
        self.fast_max_tokens = fast_max_tokens
        self.fast_temperature = fast_temperature
        self.deep_max_tokens = deep_max_tokens
        self.deep_temperature = deep_temperature
        self.min_deep_response_length = min_deep_response_length

    async def execute(
        self,
        context: Context,
        agent: AgentDescriptor,
    ) -> str:
        from litellm import acompletion

        model_str = f"{agent.provider}/{agent.model}" if agent.provider else agent.model

        # ---------- Pass 1: Fast shallow ----------
        fast_messages: List[Dict[str, str]] = []
        if context.system_prompt:
            fast_messages.append({"role": "system", "content": context.system_prompt})
        fast_messages.append({"role": "user", "content": context.user_message})

        fast_budget = floor_budget(model_str, budget_for(agent, self.fast_max_tokens))

        logger.info(
            "HybridExecutor pass 1 (fast) — model=%s, max_tokens=%d",
            model_str, fast_budget,
        )

        try:
            fast_response = await acompletion(
                model=model_str,
                messages=fast_messages,
                max_tokens=fast_budget,
                temperature=self.fast_temperature,
            )
        except Exception as e:
            logger.error("HybridExecutor pass 1 failed: %s", e, exc_info=True)
            raise

        fast_text = extract_response_text(fast_response, model_str)

        # Decide whether a second pass is needed
        needs_deep = self._needs_deep_reasoning(fast_text, context.user_message)

        if not needs_deep:
            logger.info("HybridExecutor — fast pass sufficient (%d chars)", len(fast_text))
            return fast_text

        # ---------- Pass 2: Deep reasoning ----------
        deep_messages: List[Dict[str, str]] = []
        if context.system_prompt:
            deep_messages.append({"role": "system", "content": context.system_prompt})
        for turn in context.session_history:
            deep_messages.append({"role": turn.get("role", "user"), "content": turn.get("content", "")})
        deep_messages.append({
            "role": "user",
            "content": (
                "[Previous quick response was insufficient]\n\n"
                + f"Original query: {context.user_message}\n\n"
                + "Please provide a thorough, well-reasoned response to the query above. "
                + "Consider multiple perspectives and show your reasoning."
            ),
        })

        deep_budget = floor_budget(
            model_str, budget_for(agent, self.deep_max_tokens, minimum=DEEP_MIN_BUDGET)
        )

        logger.info(
            "HybridExecutor pass 2 (deep) — model=%s, max_tokens=%d",
            model_str, deep_budget,
        )

        try:
            deep_response = await acompletion(
                model=model_str,
                messages=deep_messages,
                max_tokens=deep_budget,
                temperature=self.deep_temperature,
            )
        except Exception as e:
            logger.error("HybridExecutor pass 2 failed, falling back to fast response: %s", e)
            return fast_text

        deep_text = extract_response_text(deep_response, model_str)
        if deep_text:
            return deep_text

        return fast_text

    def _needs_deep_reasoning(self, fast_text: str, query: str) -> bool:
        """Determine if the fast response needs a deeper follow-up."""
        if not fast_text:
            return True
        if len(fast_text) < self.min_deep_response_length:
            return True
        deep_keywords = [
            "analyze", "explain", "compare", "contrast", "why", "how",
            "difference", "pros and cons", "advantages", "disadvantages",
            "evaluate", "summarize", "describe in detail", "reason",
            "think step by step", "what are the", "list all",
        ]
        query_lower = query.lower()
        for kw in deep_keywords:
            if kw in query_lower:
                return True
        return False


# ---------------------------------------------------------------------------
# Registry wrapper
# ---------------------------------------------------------------------------

class ExecutorRegistry:
    """Typed registry wrapper for AgentExecutor implementations."""

    def __init__(self) -> None:
        self._registry = Registry[AgentExecutor]()

    def register(self, name: str, executor: AgentExecutor, overwrite: bool = False) -> None:
        self._registry.register(name, executor, overwrite=overwrite)

    def get(self, name: str) -> AgentExecutor:
        return self._registry.get(name)

    def list(self) -> List[str]:
        return self._registry.list()

    def __contains__(self, name: str) -> bool:
        return name in self._registry


def create_default_registry() -> ExecutorRegistry:
    """Create a registry pre-populated with the default and LiteLLM implementations."""
    registry = ExecutorRegistry()
    registry.register("default", LiteLLMExecutor())
    registry.register("stub", DefaultExecutor())
    registry.register("fast", FastExecutor())
    registry.register("hybrid", HybridExecutor())
    return registry


# ---------------------------------------------------------------------------
# Convenience: run with tracing
# ---------------------------------------------------------------------------

async def run_executor(
    executor: AgentExecutor,
    context: Context,
    agent: AgentDescriptor,
) -> tuple[str, ComponentTrace]:
    """Execute an agent and return (response_text, trace)."""
    trace = ComponentTrace(strategy=_strategy_name(executor))
    timer = Timer()

    try:
        with timer:
            response = await executor.execute(context=context, agent=agent)
        trace.duration_ms = timer.duration_ms
        trace.tokens_used = _estimate_response_tokens(response)
        trace.input_tokens = _estimate_context_tokens(context)
        trace.output_tokens = _estimate_response_tokens(response)
        trace.metadata = {
            "response_length": len(response),
            "context_tokens": _estimate_context_tokens(context),
        }
        # A DEGRADED TURN IS REPORTED, not only logged: the executor walked a chain and fell over,
        # so the trace says which service answered (R3 — the statement a surface reads).
        if context.metadata.get("fallback_chain_used"):
            trace.metadata["fallback_chain_used"] = context.metadata["fallback_chain_used"]
    except Exception as exc:
        trace.duration_ms = timer.duration_ms
        trace.error = str(exc)
        logger.exception("Executor failed: %s", exc)
        raise

    return response, trace


def _strategy_name(executor: AgentExecutor) -> str:
    return type(executor).__name__.replace("Executor", "").lower() or "custom"


def _estimate_response_tokens(response: str) -> int:
    return len(response.split())


def _estimate_context_tokens(context: Context) -> int:
    total = len(context.user_message.split())
    total += len(context.system_prompt.split())
    for turn in context.session_history:
        total += len(str(turn).split())
    total += sum(len(r.split()) for r in context.rag_results)
    return total
