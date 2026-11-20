"""
Context preparation for chat operations.

Handles preparation of chat context including agent, session,
tools, and LLM request building.
"""

import logging
from app.domain.providers.litellm_route import api_base_for, litellm_model_string
from app.domain.providers.provider_endpoints import resolve_endpoint
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import Agent, ChatSession, Provider, RuntimeConfig
from app.domain.runtime_config.sampling import merge_sampling
from app.domain.chat.services import ChatService
from app.domain.tools.services import AgentToolService
from app.services.cognitive_pipeline.reasoning_support import (
    history_message,
)
from app.services.cognitive_pipeline.output_budget import (
    PATH_DEFAULT,
)

logger = logging.getLogger(__name__)


def _build_tools_section(llm_tools: List[Dict[str, Any]]) -> str:
    """The BEHAVIOURAL tool guidance — NOT an inventory of the tools.

    THE INVENTORY USED TO BE HERE (removed 2026-10-13, the input-budget arc). It printed one
    ``- **name**: description`` line per tool, and those exact names and descriptions already
    ride the request's ``tools=[...]`` field — every tool's schema carries the same two strings.
    Measured on a live agent: the section cost **1,281 tokens per call, 1,020 of them a verbatim
    second copy of the schemas**, i.e. the single largest *unneeded* prompt section the app had.
    It was doubly misleading where the schemas were withheld: the deep pass strips this section
    and sends no tools, so a list of tool names in the prompt was an invitation to answer with a
    tool call nobody could serve.

    What is left is what a schema cannot say: how to behave with tools — and without one.
    `llm_tools` is still the signal for "this turn has tools at all"; an empty list builds
    nothing.
    """
    if not llm_tools:
        return ""

    return (
        "## Tools\n\n"
        "Your available tools and their parameters are given to you with each request. Use them "
        "when they can answer better than you can alone; report what a tool returns exactly; and "
        "if you lack a tool for something the user asks, say so plainly rather than improvising "
        "one."
    )


@dataclass
class ChatContext:
    """
    Context for a chat operation.

    Attributes:
        agent: Agent instance
        session: Chat session
        runtime_config: Runtime configuration
        enabled_tools: List of enabled tools for agent
        llm_tools: Tools in LLM function calling format
        tool_map: Map of tool slug to tool ID
        messages: Messages for LLM request
        model: Model name to use
        provider: Provider name
        request_params: Additional request parameters
        tool_call_tracker: Tracker for detecting tool call loops (optional, set in router)
        turn_state: The turn's spending account (optional, set in router — Phase D.1)
    """
    agent: Agent
    session: ChatSession
    runtime_config: Optional[RuntimeConfig]
    enabled_tools: List[Any]
    llm_tools: List[Dict[str, Any]]
    tool_map: Dict[str, str]
    messages: List[Dict[str, Any]]
    model: str
    provider: str
    request_params: Dict[str, Any]
    session_id: int
    agent_id: int
    agent_name: str
    messages_count: int
    messages_preview: Optional[str]
    tools_count: int
    tools: List[str]
    parameters: Dict[str, Any]
    api_base: Optional[str] = None   # Provider base URL (e.g. Ollama host)
    api_key: Optional[str] = None    # Decrypted provider API key
    # THE RESOLVER'S CHAIN FOR THIS TURN (R3) — the ordered candidates, resolved in
    # the router where the session is (the `output_budget` seam). The stream's open
    # walks it, so the chat path can fail over too; empty = the request is the single
    # attempt, which is what this path did before the arc.
    candidates: Optional[List[Any]] = None
    tool_call_tracker: Optional[Any] = None  # ToolCallTracker instance
    # THE TURN'S ACCOUNT (the token-limit arc, Phase D.1) — a
    # `turn_state.TurnState` set in the router beside the tracker: one place the
    # turn's tokens in/out, provider calls, tool calls and elapsed accumulate
    # across the main loop and the deep pass.
    turn_state: Optional[Any] = None
    # THE DRIVER'S WINDOW (Phase E.1/E.2) — the `ModelWindow` this turn's driver
    # resolved to, read once here and used by the output clamp (E.2). `None` means
    # nobody recorded it: nothing is clamped, and the read already said so.
    model_window: Optional[Any] = None
    # THE DRIVER'S THINKING SIGNAL (F.3) — a `reasoning_support.ThinkingSignal`
    # resolved once, where the window is: the provider's own claim, else the curated
    # row's label. The resolver consumes it at every path (`_apply_output_budget`),
    # so the floor is decided on the driver's record rather than on a name guess.
    model_thinking: Optional[Any] = None
    # THE INPUT BUDGET in force for this turn (E.1/E.6) — the assembly ceiling after
    # the window's lowering, and the number the input soft is a fraction of. Carried
    # here because the limit judgement happens in the router, far from the assembly.
    input_budget: Optional[int] = None
    # WHAT THE TURN WAS ASKED (2026-10-13, the research-run arc) — the user's message for this
    # turn, carried so the notebook's automatic capture can name the assignment it opens
    # ("Check the local headlines") without re-deriving it from a message list the tool loop
    # has already appended to.
    turn_goal: str = ""


async def prepare_chat_context(
    db: AsyncSession,
    service: ChatService,
    agent_id: int,
    session_id: Optional[int],
    message: str,
) -> ChatContext:
    """
    Prepare chat context from request data.

    Args:
        db: Database session
        service: Chat service
        agent_id: Agent ID from request
        session_id: Session ID from request
        message: User message

    Returns:
        Prepared chat context

    Raises:
        ValueError: If agent not found
    """
    # Get agent and session
    agent = await service._get_agent(agent_id)
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")

    session = await service._get_or_create_session(session_id, agent_id)
    runtime_config = await service._get_runtime_config(session.id)

    # Get the agent's tools — THE PARADIGM COMPLETION (2026-08-19):
    # GRAS tools default-on (minus explicit exclusions); keyed tools
    # need the enabled link. The execution service owns the rule so
    # the LLM surface and the enforcement CANNOT diverge.
    from app.domain.tools.execution_service import ToolExecutionService
    tool_exec = ToolExecutionService(db)
    enabled_defs = await tool_exec.get_enabled_tools_for_agent(str(agent.id))
    # the raw rows (with the tool objects) for the tool_map
    agent_tool_service = AgentToolService(db)
    enabled_tools = await agent_tool_service.list_agent_tools(
        str(agent.id), is_enabled=True
    )

    # Debug logging for tool resolution
    logger.info(f"🔍 Agent {agent.name} (id={agent.id}): found {len(enabled_tools)} enabled tools")
    for at in enabled_tools:
        tool_obj = getattr(at, 'tool', None)
        tool_name = tool_obj.name if tool_obj else 'NO_TOOL_OBJECT'
        tool_slug = tool_obj.slug if tool_obj else 'N/A'
        logger.info(f"   Tool: {at.tool_id} -> {tool_name} (slug={tool_slug})")

    # Convert tools to LLM function calling format — the service's
    # full surface (default-on GRAS included), with the id map from
    # the raw rows.
    llm_tools = []
    tool_map: dict[str, str] = {}
    raw_by_slug = {
        at.tool.slug: at.tool for at in enabled_tools if at.tool
    }
    for tool_def in enabled_defs:
        slug = tool_def.get("function", {}).get("name")
        if not slug:
            continue
        llm_tools.append(tool_def)
        tool = raw_by_slug.get(slug)
        tool_map[slug] = str(getattr(tool, "id", ""))

    # Log tools available
    if llm_tools:
        logger.info(f"🔧 Agent {agent.name} has {len(llm_tools)} tools enabled: {[t['function']['name'] for t in llm_tools]}")
    else:
        logger.info(f"⚠️  Agent {agent.name} has NO tools enabled")

    # Save user message to database FIRST
    from app.infrastructure.database.models import ChatMessage
    user_message = ChatMessage(
        session_id=session.id,
        role="user",
        content=message,
    )
    db.add(user_message)
    await db.flush()
    await db.refresh(session)

    # THE PHASE BOUNDARY (the write-lock defect). Everything above is a WRITE —
    # the session row when this turn created one, and the user's message — and
    # this is the last moment before the turn asks a provider for anything.
    # SQLite has ONE writer: left uncommitted, this transaction refused every
    # other write in the application (a second turn's session INSERT, a settings
    # save, PUT /agents/<id>) for as long as the model took to answer — each of
    # them waiting out the 30s busy timeout and returning 500 while reads kept
    # answering, so the app looked alive. Committing here ends the transaction at
    # the boundary it belongs to; no provider call runs inside a write.
    await db.commit()

    # Determine model and provider — resolved BEFORE the history is
    # built: the reasoning replay below is gated on the model family.
    model = runtime_config.model_override if runtime_config and runtime_config.model_override else agent.model
    provider = getattr(agent, 'provider', 'ollama')

    # THE PROVIDER ROW — read HERE, before the model string: the litellm HANDLER is the row's
    # dialect (its provider_type), and the handler decides which root the request needs.
    # `domain/providers/litellm_route.py` is the ONE home for both decisions.
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    provider_row = None
    try:
        provider_result = await db.execute(
            select(Provider).where(
                Provider.name == provider,
                Provider.is_active,
            ).limit(1)
        )
        provider_row = provider_result.scalar_one_or_none()
        if provider_row is None:
            logger.debug(f"No active Provider row found for name='{provider}'; relying on LiteLLM env-var defaults")
    except Exception as prov_err:
        logger.warning(f"Error loading provider credentials for '{provider}': {prov_err}")

    # Normalize the model name to the litellm handler this provider speaks — the row's TYPE decides
    # it, the row NAME is the fallback (`litellm_route.litellm_model_string`).
    litellm_model = litellm_model_string(
        provider, model, provider_row.provider_type if provider_row else None
    )

    if provider_row:
        if provider_row.base_url:
            # THE ROOT THE HANDLER NEEDS, through the resolver that owns the rule (2026-10-12, stage 2):
            # the row's own `base_url`, else its type's canonical endpoint. The ollama family goes to
            # litellm's `ollama_chat` handler, which composes `{api_base}/api/chat` itself, so a row
            # carrying the compat root must be handed its NATIVE root or the dial lands one directory
            # outside the API (measured 404).
            api_base = api_base_for(
                litellm_model,
                resolve_endpoint(
                    provider_row.provider_type or provider_row.name,
                    provider_row.base_url,
                    provider_row.name,
                ),
            )
        if not api_key:
            from app.domain.providers.env_key_store import env_key_store
            api_key = env_key_store.get_key(provider)

    # Get conversation history using token-based budgeting
    # THE REASONING REPLAY (2026-09-10, the poisoned-session fix): a
    # thinking-mode turn's `reasoning_content` must be passed BACK on
    # every assistant message of the replayed history — DeepSeek 400s
    # the whole request otherwise ("The `reasoning_content` in the
    # thinking mode must be passed back to the API."), LiteLLM retries
    # the 400 into an empty completion, the empty-message guard
    # refuses to persist it and the session dies for every following
    # turn. The stored reasoning is in the row's `meta` column;
    # `history_message` carries it back (assistant turns with
    # reasoning only — the content the user sees is untouched).
    previous_messages_data = []
    if session.messages:
        previous_messages_data = [
            history_message(msg, model_str=litellm_model)
            for msg in session.messages[:-1]
        ]

    # THE MODEL'S WINDOW AND THE ASSEMBLY CEILING (the token-limit arc, E.1).
    # The window is physics, not policy: it is READ here (the curated row, else
    # the provider's own cached row, else unknown — `domain/providers/
    # model_window.py`) and used only to LOWER the assembly ceiling, never to
    # raise it (roadmap §2). What it is reserved against is the LARGEST output
    # budget this turn could send — the deep pass's — because the assembly happens
    # once, before the conduit decides which pass runs.
    #
    # The knob this replaces was DEAD, and worth recording: it read
    # `runtime_config.context_window_size`, which is not a column on RuntimeConfig
    # at all — so `hasattr` was always False and the input budget was the module
    # constant whatever the model was (§2.2's complaint, with nothing even
    # configured). A setting that reads as live and never fires is the C.4 class
    # of finding; it is removed rather than left in place.
    from app.domain.providers.model_window import (
        resolve_model_thinking,
        resolve_model_window,
    )
    from app.domain.chat.token_budget import input_budget_for
    from app.services.cognitive_pipeline.output_budget import (
        PATH_DEEP,
        resolve_output_budget,
    )

    model_window = await resolve_model_window(db, provider, model)
    # F.3: the driver's thinking signal, read beside the window and for the same
    # reason — both are FACTS about the driver, and both decide what a budget may be.
    model_thinking = await resolve_model_thinking(db, provider, model)
    reserved_output = resolve_output_budget(
        agent, litellm_model, model_thinking, PATH_DEEP,
    )[0]
    input_budget = input_budget_for(model_window.value, reserved_output)

    # Build context with token budgeting (includes system prompt deduction)
    # THE PERSONA HOME (2026-09-02, the workspace-first partition):
    # the persona.md file in the agent's folder is preferred; the row
    # is the synced fallback (folder-less agents + the export path).
    # An explicit runtime override still wins over both.
    from app.domain.agents.persona import read_persona
    system_prompt = read_persona(agent)
    if runtime_config and runtime_config.system_prompt_override:
        system_prompt = runtime_config.system_prompt_override

    # ------------------------------------------------------------------
    # THE SHARED CONVERSATION RULES (2026-09-01, the user's call — the
    # GENERAL chatbot skills for EVERY agent, graduated out of the Bob
    # experimental block): the temporal/locus context, the etiquette,
    # and the source-integrity. The four Bob-session review (2026-09-01)
    # grounded them: the wall-of-text, the fabricated headlines, the
    # stale-snippet-date trap, and the apology spirals.
    # ------------------------------------------------------------------
    from datetime import datetime, timezone as _tz

    _now = datetime.now()
    _today = _now.strftime("%A, %Y-%m-%d")
    _timestr = _now.strftime("%H:%M %Z")
    _utc = datetime.now(_tz.utc).strftime("%H:%M UTC")

    shared_rules = (
        f"IMPORTANT: The current date is {_today} and the current time "
        f"is {_timestr} ({_utc}). This is the ONLY correct date and "
        f"time — never guess, infer, or recall a different date from "
        f"your training data, and never say you lack access to the "
        f"date or time. If asked, state EXACTLY this date and time.\n"
        f"THE SNIPPET-DATE RULE: search snippets can carry STALE dates "
        f"— the date above is authoritative over any date a snippet or "
        f"page shows; never adopt a snippet's date.\n"
        f"THE TURN-TAKING RULE: when you ask the user a question, END "
        f"your response there and wait for their answer — never "
        f"continue after a question. If you have MORE THAN ONE "
        f"question, NUMBER them, then stop.\n"
        f"THE NO-REPEAT RULE: never repeat information you have "
        f"already provided — each message adds new content.\n"
        f"THE CONCISENESS RULE: a wall of text is poor etiquette — "
        f"keep responses concise and scannable; prefer short "
        f"paragraphs and bullet points over long blocks; when the user "
        f"wants depth, offer to expand rather than dumping everything "
        f"at once.\n"
        f"THE SOLICITATION RULE: offer help ONCE and keep it focused "
        f"— never rattle a list of 'if you like, I can do X and Y and "
        f"Z' options.\n"
        f"THE SOURCE-INTEGRITY RULE: report ONLY what your search "
        f"results actually show — never state a headline, number, or "
        f"fact you did not see in a result. When the results are thin "
        f"or unclear, say so plainly instead of padding. When you were "
        f"wrong, correct the record BRIEFLY — no long apologies.\n"
        f"THE TOOL-HONESTY RULE: if a tool can provide what you need "
        f"(the date, the time, current facts), USE it — never claim "
        f"you lack access to something a tool gives you.\n"
        f"THE TIMELINESS RULE: when searching for time-sensitive "
        f"information (news, weather, prices, events), anchor the "
        f"query to the current period — the current date is {_today}, "
        f"so a news search targets the last few days, not the "
        f"archives; prefer recent results; when a result's date is "
        f"unclear or old, say so.\n"
        f"THE MULTI-SOURCE RULE: for facts that matter (dates, "
        f"numbers, breaking claims), verify with TWO independent "
        f"sources before stating them; for casual chat, one source or "
        f"none is fine.\n"
        f"THE REPORT-BACK RULE: when you have used tools to do work, "
        f"you MUST close your turn with a message to the user — what "
        f"you did and what you found. A TOOL CALL IS NOT A REPLY: work "
        f"that is never reported also counts as not done. If you wrote "
        f"a file, saved a report, or produced an artifact, say where it "
        f"is and lead with its headline. Never end a turn on a tool "
        f"call.\n"
    )
    system_prompt = shared_rules + (system_prompt or "")

    # THE NEWS-SCOUT PERSONA lives in Bob's STORED agent profile
    # (the agents row — data, not code: the role, the curated
    # beat, the locus). Code-side stays the runtime layer — the
    # shared rules above apply to EVERY agent; no name-gates
    # remain here.

    # THE SELF-STATE INJECTION (2026-09-02, the shallow-agent
    # build): an agent with a workspace state (state.json — facts
    # + sources, maintained through the update-state/update-sources
    # tools) sees it as the YOUR-STATE block. Unconditional — any
    # agent with stored state gets it; none without → None (no
    # name-gates; the store is the ONE home, the prompt reflects it).
    from app.domain.agents.agent_state import build_state_block
    _state_block = build_state_block(getattr(agent, "workspace_key", None))
    if _state_block:
        system_prompt = f"{system_prompt}\n\n{_state_block}"

    # THE NOTEBOOK IN THE PROMPT (2026-10-13, the research-run arc). The agent's OPEN assignments
    # — the goal, what the notebook holds, and WHICH sources are already gathered. That last line
    # is the point: measured over ~7 weeks, 91 URLs were fetched more than once (one weather page
    # 18×), and a source the prompt names is one the run does not pay for twice. Written by the
    # notebook tools, read HERE — one home, the prompt reflects the store. Silent when the agent
    # has no open assignment.
    from app.domain.agents.assignments import build_assignments_block
    _assignments_block = build_assignments_block(getattr(agent, "workspace_key", None))
    if _assignments_block:
        system_prompt = f"{system_prompt}\n\n{_assignments_block}"

    # Build dynamic tools section for system prompt
    tools_section = _build_tools_section(llm_tools)
    if tools_section:
        # Append tools section to system prompt
        if system_prompt:
            system_prompt = f"{system_prompt}\n\n{tools_section}"
        else:
            system_prompt = tools_section
        logger.debug(f"📋 System prompt enhanced with tools section for agent {agent.name}")

    previous_messages, context_tokens = service._build_context_with_token_budget(
        messages=previous_messages_data,
        system_prompt=system_prompt,
        input_budget=input_budget,
        # THE SCHEMAS THE REQUEST WILL CARRY (Phase B): the trim deducts their weight, so it has to
        # be told what they are. They are in hand here — `llm_tools` is the same list that goes into
        # the request's `tools=[...]` field a few lines below.
        tools=llm_tools,
    )

    # Build messages for LLM
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if previous_messages:
        messages.extend(previous_messages)
    messages.append({"role": "user", "content": message})

    # Determine model and provider
    # (already resolved above, before the history replay)

    # THE PROVIDER ROW, its endpoint and its key were resolved above — before the model string,
    # because the row's TYPE decides the handler and the handler decides the root.

    # Build request parameters
    #
    # PER FIELD, AGENT FIRST: the session's runtime config overrides the fields it
    # actually sets, and a row that exists for a model or prompt override alone no
    # longer drops the agent's own sampling (the shape, and the case it fixes, live in
    # `domain/runtime_config/sampling.py`).
    request_params: Dict[str, Any] = merge_sampling(agent.parameters, runtime_config)

    # THE OUTPUT BUDGET — the resolver decides it (the token-limit arc, C.1/C.5).
    # The runtime override, the agent's declared value and the reasoning floor
    # are read in ONE place, `resolve_output_budget`. The floor used to be
    # applied HERE and again in the router, and neither site could say which
    # number went on the wire; the effective-budget line is written where the
    # budget becomes FINAL — in the router, because the executor strategy
    # (fast / hybrid pass 1 / the conduit's deep pass) is not known yet here.
    # This is the DEFAULT path's number; the router re-resolves per path.
    _budget, _reason = resolve_output_budget(
        agent,
        str(litellm_model),
        path=PATH_DEFAULT,
        override=getattr(runtime_config, "max_tokens", None),
    )
    request_params["max_tokens"] = _budget

    return ChatContext(
        agent=agent,
        session=session,
        runtime_config=runtime_config,
        enabled_tools=enabled_tools,
        llm_tools=llm_tools,
        tool_map=tool_map,
        messages=messages,
        model=litellm_model,
        provider=provider,
        request_params=request_params,
        session_id=session.id,
        agent_id=int(agent.id),
        agent_name=agent.name,
        messages_count=len(messages),
        messages_preview=messages[-1]['content'][:100] if messages else None,
        tools_count=len(llm_tools),
        tools=[t['function']['name'] for t in llm_tools] if llm_tools else [],
        parameters=request_params,
        api_base=api_base,
        api_key=api_key,
        model_window=model_window,
        model_thinking=model_thinking,
        input_budget=input_budget,
        turn_goal=message,
    )



# IMPORTANT: Do NOT pass "retry", "num_retries", "retry_delay", or
# "fallbacks" in per-request kwargs. LiteLLM forwards unknown kwargs to
# OpenAI-compatible APIs (like Groq) which reject them as unsupported.


def build_llm_request(
    context: ChatContext,
    stream: bool = True,
) -> Dict[str, Any]:
    """
    Build LLM request kwargs from context.

    Args:
        context: Chat context
        stream: Whether to stream the response

    Returns:
        Kwargs dict for LLM API call
    """
    request_kwargs = {
        "model": context.model,
        "messages": context.messages,
        "stream": stream,
    }

    # THE CEILING TRAVELS WITH THE REQUEST (the input-budget arc, Phase A). The accounting line at
    # the call boundary reports the measured composition BESIDE the number the prompt was assembled
    # under, and that number is decided here (E.1's `context.input_budget`). It is a named parameter
    # of `acompletion_with_retry` — consumed there and never forwarded to litellm — so the request
    # can carry it without the provider seeing it.
    request_kwargs["prompt_budget"] = getattr(context, "input_budget", None)

    # Pass provider credentials resolved from the database
    if context.api_base:
        request_kwargs["api_base"] = context.api_base
    if context.api_key:
        request_kwargs["api_key"] = context.api_key
    elif context.api_base:
        # THE KEYLESS LOCAL SERVERS (2026-09-01, the Bonsai dig —
        # the ACTUAL build path): the llama needs a NON-EMPTY key
        # for the litellm's openai-adapter; the 'Missing
        # credentials' error otherwise. (The earlier fixes landed
        # in the router's chat_delegate — the WRONG function; the
        # stream's kwargs come from THIS build_llm_request.)
        from app.domain.providers.llm_factory import placeholder_key_for
        _placeholder = placeholder_key_for(context.api_base, getattr(context, "model", None))
        if _placeholder:
            request_kwargs["api_key"] = _placeholder
        logger.info("BUILD-DEBUG elif fired (api_base=%s)", bool(context.api_base))
    # THE OLLAMA CLOUD AUTH (2026-08-24, live): the ollama_chat
    # handler serves the LOCAL ollama (no auth) — it does NOT attach
    # the Authorization header, but ollama.com REQUIRES the Bearer.
    # The api_key kwarg alone is insufficient; the explicit header
    # is the guaranteed path.
    if (context.api_base and "ollama.com" in context.api_base and context.api_key):
        headers = request_kwargs.setdefault("extra_headers", {})
        if not isinstance(headers, dict):
            headers = {}
            request_kwargs["extra_headers"] = headers
        headers["Authorization"] = f"Bearer {context.api_key}"

    # Add tools if available
    if context.llm_tools:
        request_kwargs["tools"] = context.llm_tools
        request_kwargs["tool_choice"] = "auto"

    # Add parameters
    if context.request_params:
        request_kwargs.update(context.request_params)

    return request_kwargs
