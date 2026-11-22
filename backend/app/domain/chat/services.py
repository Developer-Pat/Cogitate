"""
Chat domain service.

Business logic for chat operations.

Phase 3 Integration:
    Updated to use Provider Abstraction Layer for unified provider interface
    with automatic fallback, rate limiting, and quota management.
"""

import logging
import json
from types import SimpleNamespace
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.domain.chat.schemas import ChatRequest, ChatResponse
from app.domain.runtime_config.sampling import merge_sampling
from app.domain.chat.token_budget import (
    estimate_tokens,
    build_context_with_token_budget,
    input_budget_for,
    DEFAULT_INPUT_BUDGET,
    DEFAULT_MAX_CONTEXT_TOKENS,
    TOKENS_PER_MESSAGE_OVERHEAD,
    TOKENS_RESPONSE_HEADROOM,
)
from app.infrastructure.database.models import (
    ChatSession,
    ChatMessage,
    Agent,
    RuntimeConfig,
    Provider,
    UsageLog,
)
from app.domain.providers.completion_service import (
    provider_completion_service,
    CompletionRequest,
)
from app.domain.providers.services import EncryptionService
from app.domain.agents.services import AgentService
from app.domain.tools.execution_service import ToolExecutionService, ToolExecutionResult
from app.services.cognitive_pipeline.reasoning_support import history_message
from app.services.cognitive_pipeline.output_budget import (
    PATH_DEEP,
    PATH_DEFAULT,
    declared_output_budget,
    resolve_output_budget,
)

logger = logging.getLogger(__name__)


async def _resolved_fallback_chain(
    db: Any, provider: str, model: str, agent: Any
) -> list[str]:
    """The BACKUPS for a completion call, from the RESOLUTION (R3) — never a hardcoded list.

    `provider`/`model` are what this call will actually attempt, so they are the chain's PRIMARY
    (the resolver's agent rung reads them off the declaration, and skips a backup that repeats the
    primary); what comes back is only what to try AFTER it — the agent's own `preferred_providers`,
    else the capability's configured chain.

    A resolution that cannot read returns NO backups: the call is then a single attempt, which is
    what this surface did before the arc. It must never fail the call, and it must never invent a
    provider list — the literal this replaced also published a "fell back" warning to the user
    before anything had been attempted, a false alarm on every request.
    """
    try:
        from app.domain.providers.capabilities import CHAT_CAPABILITY_KEY, resolve

        resolved = await resolve(
            db,
            CHAT_CAPABILITY_KEY,
            agent=SimpleNamespace(
                provider=provider or "",
                model=model or "",
                preferred_providers=list(getattr(agent, "preferred_providers", None) or []),
            ),
        )
        return [candidate.provider for candidate in resolved.backups if candidate.provider]
    except Exception as exc:  # noqa: BLE001 — a chain reading must not fail the call
        logger.warning(
            "chat: no chain for agent %s (%s) — a single attempt it is",
            getattr(agent, "id", "?"),
            exc,
        )
        return []


def _output_budget(agent: Any, runtime_config: Any = None) -> Optional[int]:
    """The output budget the resolver decides, or None when nothing declares one.

    (the token-limit arc, C.1) This service builds a `CompletionRequest` for the
    provider completion service, where `max_tokens=None` means "the provider
    decides" — the existing meaning of an absent budget on this path. So the
    resolver speaks whenever there IS a declaration (the per-session override,
    the agent's own number, the reasoning floor) and stays out of the way when
    there is not; the number itself comes from the ONE resolver either way, not
    from this file's own copy of the rules.

    The floor matters here: without it a thinking model spends its whole budget
    thinking and returns an empty answer (the ox-alpha failure).
    """
    override = getattr(runtime_config, "max_tokens", None)
    model = str(getattr(agent, "model", "") or "")
    if override is None and declared_output_budget(agent) is None:
        return None
    budget, reason = resolve_output_budget(
        agent, model, path=PATH_DEFAULT, override=override,
    )
    logger.info(
        "💰 OUTPUT BUDGET (chat service) max_tokens=%s reason=%s model=%s",
        budget, reason, model,
    )
    return budget


class ChatService:
    """
    Service for chat business logic.

    Handles chat operations and LLM integration.

    Context Window Management:
        The conversation context sent to the LLM is limited to prevent token overflow
        and maintain response quality. The current implementation uses a simple approach:

        - CONTEXT_WINDOW_SIZE: Number of recent messages to include (default: 20)
        - Strategy: Keep the most recent N messages from the conversation
        - Rationale: Recent messages are typically most relevant for context

        Future Enhancements (see docs/rebuild/CONTEXT_WINDOW_MANAGEMENT.md):
        - Smarter truncation (keep system messages + recent pairs)
        - Token-based limiting instead of message count
        - Configurable per-agent or per-model
        - Summary-based compression for long conversations

    Phase 3 Integration:
        - Uses ProviderCompletionService for unified provider interface
        - Automatic fallback chain (OpenRouter → Deepseek → Ollama)
        - Rate limiting and quota management
        - Provider health monitoring
    
    Context Window Management:
        Token-based context budgeting ensures optimal use of model context limits.
        - DEFAULT_INPUT_BUDGET: the assembly ceiling for conversation history
          (the app's policy number — NOT the model's context window, which is a
          fact about the driver and only LOWERS this ceiling)
        - Strategy: Keep system prompt + recent messages within token budget
        - Always preserves at least one user/assistant pair for context
    """

    # Token-based context window configuration
    # Values imported from token_budget module so they're accessible as class
    # attributes for any callers that reference them via the service instance.
    DEFAULT_INPUT_BUDGET = DEFAULT_INPUT_BUDGET
    DEFAULT_MAX_CONTEXT_TOKENS = DEFAULT_MAX_CONTEXT_TOKENS   # deprecated alias
    TOKENS_PER_MESSAGE_OVERHEAD = TOKENS_PER_MESSAGE_OVERHEAD
    TOKENS_RESPONSE_HEADROOM = TOKENS_RESPONSE_HEADROOM

    def __init__(self, db: AsyncSession):
        """
        Initialize chat service.

        Args:
            db: Async database session
        """
        self.db = db
        # NOTE (2026-10-10, the service-literals arc): the local Ollama address used to live here as
        # `self.ollama_base_url = "http://localhost:11434"` — a third home for an address the `ollama`
        # ROW owns, and one that ignored the row entirely. It resolves per call now (`_ollama_endpoint`).
        self.encryption_service = EncryptionService()
        self.agent_service = AgentService(db)
        self.tool_execution_service = ToolExecutionService(db)

        # Initialize Provider Abstraction Layer (Phase 3)
        try:
            from litellm import acompletion
            self.acompletion = acompletion
            logger.info("✅ LiteLLM initialized successfully")
        except ImportError:
            logger.warning("⚠️ LiteLLM not installed, falling back to direct Ollama calls")
            self.acompletion = None

    async def execute_tool_from_chat(self, agent_id: int, tool_slug: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool from chat interface.

        Args:
            agent_id: Agent ID
            tool_slug: Tool slug
            tool_args: Tool arguments

        Returns:
            Tool execution result
        """
        try:
            # Delegate to tool execution service
            result = await self.tool_execution_service.execute_tool_for_agent(
                agent_id=agent_id,
                tool_slug=tool_slug,
                arguments=tool_args,
            )
            return {
                "success": True,
                "tool_slug": tool_slug,
                "result": result.result if result.success else None,
                "error": result.error if not result.success else None,
            }
        except Exception as e:
            logger.error(f"Error executing tool from chat: {e}")
            return {
                "success": False,
                "tool_slug": tool_slug,
                "error": str(e),
                "result": None
            }

    async def _generate_response_with_tools(
        self,
        message: str,
        agent: Agent,
        conversation_history: List[Dict],
        tools: List[Dict],
        runtime_config: Optional[RuntimeConfig],
        session_id: int,
    ) -> Tuple[str, int, List[ToolExecutionResult]]:
        """
        Generate response with tool support.

        Returns:
            Tuple of (response content, token count, tool calls made)
        """
        messages = self._build_messages(message, conversation_history, agent)

        # First call - may include tool calls
        response = await self._call_llm_with_tools(
            messages=messages,
            agent=agent,
            tools=tools,
            runtime_config=runtime_config,
        )

        # Check for tool calls
        if not response.get("tool_calls"):
            # No tools called - return response
            return response["content"], response["tokens"], []

        # Tools were called - execute them
        tool_results = []
        for tool_call in response["tool_calls"]:
            result = await self._execute_tool_call(
                tool_call=tool_call,
                agent_id=str(agent.id),
                session_id=str(session_id),
            )
            tool_results.append(result)

        # Append tool results to conversation
        messages.append(response["message"])
        for result in tool_results:
            messages.append(result.to_llm_message())

        # Second call - get final response
        final_response = await self._call_llm_with_tools(
            messages=messages,
            agent=agent,
            tools=[],  # No tools on second call
            runtime_config=runtime_config,
        )

        return final_response["content"], final_response["tokens"], tool_results

    async def _call_llm_with_tools(
        self,
        messages: List[Dict],
        agent: Agent,
        tools: List[Dict],
        runtime_config: Optional[RuntimeConfig],
    ) -> Dict[str, Any]:
        """
        Call LLM with optional tools.

        Returns:
            Dictionary with content, tokens, and tool_calls
        """
        # Build completion request — per field, AGENT FIRST (`merge_sampling`). The
        # old shape wrote `params["temperature"] = runtime_config.temperature` with no
        # guard, so a row whose temperature was NULL sent None as a value, and a row
        # that set only a model override dropped the agent's sampling entirely.
        params: Dict[str, Any] = merge_sampling(agent.parameters, runtime_config)

        # The output budget comes from the resolver (C.1) — the override, the
        # agent's declaration, the reasoning floor; `None` still means "nothing
        # was declared, so send none", which is what this surface did before.
        max_tokens_arg: int | None = _output_budget(agent, runtime_config)

        from app.domain.providers.config_service import resolve_named_row_endpoint

        completion_request = CompletionRequest(
            messages=messages,
            model=agent.model,
            provider=agent.provider,
            endpoint=await resolve_named_row_endpoint(self.db, agent.provider),
            temperature=params.get("temperature"),
            max_tokens=max_tokens_arg,
            top_p=params.get("top_p"),
            stream=False,
            tools=tools if tools else None,
            tool_choice="auto" if tools else None,
        )

        # Call provider completion service. The CHAIN comes from the resolution (R3), never from
        # this file: the agent's own preferred providers, else the capability's configuration.
        response = await provider_completion_service.complete(
            completion_request,
            fallback_chain=await _resolved_fallback_chain(
                self.db, agent.provider, agent.model, agent
            ),
            max_retries=2,
        )

        if not response.success:
            raise RuntimeError(f"LLM call failed: {response.error_message}")

        # Parse tool calls from response
        tool_calls = []
        if hasattr(response, "tool_calls") and response.tool_calls:
            for tc in response.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                })

        return {
            "content": response.content,
            "tokens": response.completion_tokens,
            "tool_calls": tool_calls,
            "message": {
                "role": "assistant",
                "content": response.content,
            }
        }

    async def _execute_tool_call(
        self,
        tool_call: Dict[str, Any],
        agent_id: str,
        session_id: str,
    ) -> ToolExecutionResult:
        """
        Execute a tool call and return the result.

        Args:
            tool_call: Tool call dictionary from LLM
            agent_id: Agent ID
            session_id: Session ID

        Returns:
            ToolExecutionResult
        """
        try:
            tool_slug = tool_call["name"]
            tool_args = tool_call["arguments"]

            # Execute tool via service
            result = await self.tool_execution_service.execute_tool_for_agent(
                agent_id=int(agent_id),
                tool_slug=tool_slug,
                arguments=tool_args,
            )

            # Convert to ToolExecutionResult (assuming execute_tool_for_agent returns ToolExecutionResult)
            if isinstance(result, ToolExecutionResult):
                return result
            else:
                # If it's a dict, convert
                return ToolExecutionResult(
                    success=result.get("success", False),
                    tool_slug=tool_slug,
                    tool_name=tool_slug,
                    result=result.get("result"),
                    error=result.get("error"),
                    execution_time_ms=0,
                )
        except Exception as e:
            logger.error(f"Error executing tool call: {e}")
            return ToolExecutionResult(
                success=False,
                tool_slug=tool_call.get("name", "unknown"),
                tool_name=tool_call.get("name", "unknown"),
                result=None,
                error=str(e),
                execution_time_ms=0,
            )

    async def send_message(self, request: ChatRequest, enable_tools: bool = True) -> ChatResponse:
        """
        Send message with optional tool support.

        Args:
            request: Chat request
            enable_tools: Whether to enable tool execution

        Returns:
            Chat response
        """
        # Verify agent exists
        agent = await self._get_agent(request.agent_id)
        if not agent:
            raise ValueError(f"Agent {request.agent_id} not found")

        # Get or create session
        session = await self._get_or_create_session(request.session_id, request.agent_id)

        # Get runtime config
        runtime_config = await self._get_runtime_config(session.id)

        # Save user message
        user_message = ChatMessage(
            session_id=session.id,
            role="user",
            content=request.message,
        )
        self.db.add(user_message)
        await self.db.flush()
        await self.db.refresh(session)

        # Build context
        # THE REASONING REPLAY (2026-09-10, the poisoned-session fix):
        # assistant turns carry their stored `reasoning_content` back —
        # thinking-mode APIs (DeepSeek) 400 the whole request without it.
        previous_messages_data = [
            history_message(msg, model_str=getattr(agent, "model", "") or "")
            for msg in session.messages[:-1]
        ]

        # GET THE TOOLS FIRST (the input-budget arc, Phase B): the trim now deducts the tool
        # schemas' weight from the budget, so it cannot run before the schemas are known. One
        # fetch, same objects, only the order moved — the schemas are what the request puts in
        # its `tools=[...]` field, and `get_enabled_tools_for_agent` already returns them in that
        # (LLM-ready) form.
        tools = []
        if enable_tools:
            # Use ToolExecutionService to get enabled tools for agent
            tool_execution_service = ToolExecutionService(self.db)
            enabled_tools = await tool_execution_service.get_enabled_tools_for_agent(
                str(request.agent_id)
            )
            tools = enabled_tools

        previous_messages, context_tokens = self._build_context_with_token_budget(
            messages=previous_messages_data,
            system_prompt=agent.system_prompt,
            input_budget=await self._assembly_ceiling(agent, runtime_config),
            tools=tools,
        )

        # Generate response with tools
        assistant_content, completion_tokens, tool_calls = await self._generate_response_with_tools(
            request.message,
            agent,
            previous_messages,
            tools,
            runtime_config,
            session.id,
        )

        # Save assistant message
        assistant_message = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=assistant_content,
            model=agent.model,
        )
        self.db.add(assistant_message)
        await self.db.commit()

        return ChatResponse(
            message=assistant_content,
            session_id=session.id,
            model=agent.model,
            token_count=completion_tokens,
        )

    async def get_session(self, session_id: int) -> Optional[ChatSession]:
        """
        Get session by ID with messages.

        Args:
            session_id: Session ID

        Returns:
            Session with messages if found
        """
        query = select(ChatSession).where(ChatSession.id == session_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_sessions(
        self, skip: int = 0, limit: int = 100
    ) -> tuple[List[ChatSession], int]:
        """
        List all sessions with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum records to return

        Returns:
            Tuple of (sessions list, total count)
        """
        # Get total count
        count_query = select(func.count()).select_from(ChatSession)
        total = await self.db.scalar(count_query)

        # Get sessions
        query = (
            select(ChatSession)
            .order_by(ChatSession.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(query)
        sessions = list(result.scalars().all())

        return sessions, total or 0

    async def delete_session(self, session_id: int) -> bool:
        """
        Delete a session.

        Args:
            session_id: Session ID

        Returns:
            True if deleted, False if not found
        """
        session = await self.get_session(session_id)
        if not session:
            return False

        await self.db.delete(session)
        await self.db.flush()

        logger.info(f"Deleted session {session_id}")
        return True

    async def _get_agent(self, agent_id: int) -> Optional[Agent]:
        """Get agent by ID."""
        query = select(Agent).where(Agent.id == agent_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _get_or_create_session(
        self, session_id: Optional[int], agent_id: int
    ) -> ChatSession:
        """Get existing session or create new one.
        
        If the session exists but belongs to a different agent, a new session
        is created for the requesting agent — prevents message bleed across
        agents when switching in the chat UI.
        """
        if session_id:
            session = await self.get_session(session_id)
            if session:
                if session.agent_id != agent_id:
                    logger.info(
                        "Session %d belongs to agent %d, creating new session for agent %d",
                        session_id, session.agent_id, agent_id,
                    )
                else:
                    return session
            else:
                logger.warning(
                    "Orphan session: requested session_id=%d not found, creating new session for agent %d",
                    session_id, agent_id,
                )

        # Create new session — the "New Session" placeholder (never
        # None): the auto-title condition matches the placeholder
        # class, and a None title stranded sessions that were born
        # from temp-id requests (the session-lifecycle tangle, B1).
        session = ChatSession(agent_id=agent_id, title="New Session")
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def _get_runtime_config(self, session_id: int) -> Optional[RuntimeConfig]:
        """
        Get runtime config for a session.

        Args:
            session_id: Session ID

        Returns:
            RuntimeConfig if found, None otherwise
        """
        query = select(RuntimeConfig).where(RuntimeConfig.session_id == session_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    def _estimate_tokens(self, text: str) -> int:
        """Delegate to the shared ``estimate_tokens`` helper in token_budget."""
        return estimate_tokens(text)

    def _build_messages(
        self,
        message: str,
        conversation_history: List[Dict],
        agent: Agent,
    ) -> List[Dict]:
        """
        Build messages array for LLM call.

        Args:
            message: Current user message
            conversation_history: List of previous messages
            agent: Agent configuration

        Returns:
            List of message dictionaries in LLM format
        """
        messages = []

        # Add system prompt if exists
        if agent.system_prompt:
            messages.append({
                "role": "system",
                "content": agent.system_prompt,
            })

        # Add conversation history
        messages.extend(conversation_history)

        # Add current user message
        messages.append({
            "role": "user",
            "content": message,
        })

        return messages

    def _build_context_with_token_budget(
        self,
        messages: list,
        system_prompt: Optional[str],
        input_budget: Optional[int] = None,
        tools: Optional[list] = None,
    ) -> tuple[list, int]:
        """Delegate to the shared ``build_context_with_token_budget`` helper.

        ``input_budget`` is ``input_budget_for()``'s answer — the assembly ceiling
        for this turn, lowered by the model's window when the caller knows it
        (Phase E.1). ``None`` means the driver's window is unknown, so the
        constant stands (roadmap §2.4).

        ``tools`` is the tool schemas in LLM function-calling format — the request's
        ``tools=[...]`` field. Phase B deducts their weight from the budget, so a caller that has
        them passes them; ``None`` means this call sends no tools.
        """
        return build_context_with_token_budget(
            messages=messages,
            system_prompt=system_prompt,
            input_budget=input_budget,
            tools=tools,
        )

    async def _assembly_ceiling(self, agent: Agent, runtime_config: Any = None) -> int:
        """The assembly ceiling for this agent's driver (the token-limit arc, E.1).

        The window is READ — the curated row, else the provider's own cached claim,
        else unknown (`app/domain/providers/model_window.py`) — and used only to
        LOWER the constant, never to raise it (roadmap §2, E.1's F2 ruling). What it
        is reserved against is the largest output budget this turn could send (the
        deep pass's), because the assembly happens once, before the pass is chosen.

        An unknown window leaves the constant exactly where it was: §2.4's "an
        unknown window must not clamp blindly", which is what keeps a model nobody
        has recorded behaving as it does today.
        """
        from app.domain.providers.model_window import resolve_model_window

        model = (
            runtime_config.model_override
            if runtime_config is not None and getattr(runtime_config, "model_override", None)
            else getattr(agent, "model", None)
        )
        window = await resolve_model_window(
            self.db, getattr(agent, "provider", None), model
        )
        reserved = resolve_output_budget(
            agent, str(model or ""), None, PATH_DEEP
        )[0]
        return input_budget_for(window.value, reserved)

    async def _ollama_endpoint(self) -> str | None:
        """**THE address of the local Ollama server** — the `ollama` provider row's endpoint.

        One rule, one home (`provider_endpoints.resolve_endpoint`); this used to be an attribute holding
        `http://localhost:11434` that no row could ever change. ``None`` is an ANSWER — no row, or a row
        that declares no endpoint — and the caller reports it rather than dialling a guess.
        See `wiki/issues/resolved/embedded-service-literals/local-embedding-server.md` (RULED: option C, staged).
        """
        # Imported locally: the providers layer imports chat-adjacent modules, so a module-level
        # import here is a cycle waiting to happen.
        from app.domain.providers.config_service import resolve_named_row_endpoint

        return await resolve_named_row_endpoint(self.db, "ollama")

    async def _log_usage(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        response_time_ms: int,
        success: bool,
        session_id: Optional[int] = None,
        agent_id: Optional[int] = None,
        error_message: Optional[str] = None,
        cost_usd: Optional[float] = None
    ):
        """
        Log API usage for cost tracking.

        Args:
            provider: Provider name
            model: Model name
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            total_tokens: Total tokens
            response_time_ms: Response time in milliseconds
            success: Whether the request was successful
            session_id: Chat session ID
            agent_id: Agent ID
            error_message: Error message if failed
            cost_usd: Cost in USD (calculated if not provided)
        """
        if not session_id or not agent_id:
            logger.debug("Skipping usage log - no session/agent context provided")
            return
        
        # Calculate cost if not provided. The PRICE comes from the provider's own catalog
        # (the same rows the model picker shows); `calculate_cost` keeps the built-in table
        # as the fallback for models no provider publishes a price for.
        if cost_usd is None:
            from app.domain.providers.cache_service import ProviderModelCacheService
            from app.domain.providers.services import ProviderService

            pricing = await ProviderModelCacheService().pricing_for_model(
                self.db, provider, model
            )
            provider_service = ProviderService()
            cost_usd = provider_service.calculate_cost(
                provider=provider,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                pricing=pricing,
            )
        
        # Create usage log
        usage_log = UsageLog(
            session_id=session_id,
            agent_id=agent_id,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            response_time_ms=response_time_ms,
            success=success,
            error_message=error_message,
        )
        
        self.db.add(usage_log)
        await self.db.flush()
        
        if success:
            logger.info(f"💰 Usage logged - Cost: ${cost_usd:.6f}, Tokens: {total_tokens}")
        else:
            logger.warning(f"⚠️ Failed request logged - Provider: {provider}, Model: {model}")
