"""
Agent domain service.

Business logic for agent operations.
"""

import logging
import re
from typing import Optional, List, Dict, Any, cast
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.domain.agents.schemas import (
    AgentCard,
    AgentHealth,
    AgentOutputBudget,
    AgentObservedBudget,
    AgentCapabilities,
    checked_parameters,
    AgentCreate,
    AgentSkill,
    AgentStatsResponse,
    AgentUpdate,
    SystemPromptTemplate,
    AgentTemplateCreate,
    AgentTemplateUpdate,
    DuplicateGroup,
    DuplicateAgentInfo,
    DuplicatesResponse,
    AgentArmCard,
)
from app.infrastructure.database.models import Agent, AgentTemplate, UsageLog
from app.domain.tools.models import AgentTool
from app.domain.tools.services import AgentToolService
from app.domain.tools.schemas import ToolSummary
from app.services.cognitive_pipeline.output_budget import (
    PATH_DEFAULT,
    declared_output_budget,
    resolve_output_budget,
)

logger = logging.getLogger(__name__)


# Tool caching configuration
TOOL_CACHE_TTL_SECONDS = 300  # 5 minutes
_tool_cache: Dict[str, Dict] = {}




class AgentService:
    """
    Service for agent business logic.

    Handles CRUD operations and business rules for agents.
    """

    # Pre-built system prompt templates
    TEMPLATES = {
        "helpful": SystemPromptTemplate(
            id="helpful",
            name="Helpful Assistant",
            description="A friendly, helpful assistant for general tasks",
            prompt=(
                "You are a helpful, friendly AI assistant. "
                "Your goal is to provide clear, accurate, and useful information to users. "
                "Be concise but thorough in your responses. "
                "If you don't know something, admit it honestly. "
                "Always be respectful and professional."
            ),
            variables=[]
        ),
        "coder": SystemPromptTemplate(
            id="coder",
            name="Coding Expert",
            description="An expert programmer and software developer",
            prompt=(
                "You are an expert software developer and programming assistant. "
                "Your role is to help users write, debug, and understand code. "
                "Provide clear, well-commented code examples. "
                "Explain your reasoning and suggest best practices. "
                "Support multiple programming languages and frameworks. "
                "When showing code, use appropriate formatting and include relevant imports."
            ),
            variables=[]
        ),
        "analyst": SystemPromptTemplate(
            id="analyst",
            name="Data Analyst",
            description="A data analysis and research specialist",
            prompt=(
                "You are a skilled data analyst and researcher. "
                "Your role is to help users analyze data, interpret results, and draw insights. "
                "Approach problems methodically and logically. "
                "Explain statistical concepts clearly. "
                "When presenting findings, be precise and support conclusions with evidence. "
                "Suggest appropriate visualization methods when relevant."
            ),
            variables=[]
        ),
        "creative": SystemPromptTemplate(
            id="creative",
            name="Creative Writer",
            description="A creative writing and storytelling specialist",
            prompt=(
                "You are a creative writer and storyteller. "
                "Your role is to help users with creative writing, brainstorming, and ideation. "
                "Be imaginative, expressive, and engaging in your responses. "
                "Use vivid language and metaphors when appropriate. "
                "Help develop characters, plots, and worlds. "
                "Adapt your tone to match the desired style (humorous, dramatic, poetic, etc.)."
            ),
            variables=[]
        ),
        "custom": SystemPromptTemplate(
            id="custom",
            name="Custom Template",
            description="A customizable template with variables",
            prompt=(
                "You are {assistant_name}, a {role} assistant. "
                "Your tone should be {tone}. "
                "You are helping {user_name} with their tasks. "
                "Provide responses that are {style} and {focus}."
            ),
            variables=["assistant_name", "role", "tone", "user_name", "style", "focus"]
        ),
    }

    def __init__(self, db: AsyncSession):
        """
        Initialize agent service.

        Args:
            db: Async database session
        """
        self.db = db
        self.agent_tool_service = AgentToolService(db)

    async def cognitive_profile_readouts(
        self, profile_ids: List[Optional[int]]
    ) -> Dict[int, Dict[str, Optional[str]]]:
        """profile_id -> {name, depth} for a batch of cognitive-profile ids.

        The depth family comes from the ONE canonical map
        (selection_service.depth_family) — the UI chip and the agent
        selection share the same vocabulary (2026-09-06).
        """
        from app.domain.agents.selection_service import depth_family
        from app.infrastructure.database.models import CognitiveProfile

        ids = {pid for pid in profile_ids if pid is not None}
        if not ids:
            return {}
        result = await self.db.execute(
            select(CognitiveProfile).where(CognitiveProfile.id.in_(ids))
        )
        out: Dict[int, Dict[str, Optional[str]]] = {}
        for prof in result.scalars().all():
            out[prof.id] = {"name": prof.name, "depth": depth_family(prof.name)}
        return out

    async def output_budget_for_agents(
        self, agents: List[Any]
    ) -> Dict[int, "AgentOutputBudget"]:
        """agent_id -> what the row DECLARES and what a turn would SEND (Phase G.1).

        The chat path decides its budget at send time from four inputs: the agent's
        declaration, the driver's thinking signal, the driver's window, and the run
        path. `_apply_output_budget` (the router) feeds the resolver all four. This
        read feeds it the same function and the same driver facts, so the profile
        page can show the number BEFORE a turn is spent — and the reason it differs
        from the declaration, which is the half a reader cannot guess.

        Both driver reads are per DISTINCT (provider, model): two agents on one
        driver cost one window read and one thinking read, not two each. The window
        read is two indexed lookups (`resolve_model_window`), and the thinking read
        logs its fact once per driver per process — so a page load is log-quiet
        after the first time.

        The per-session `runtime_configs.max_tokens` override is deliberately NOT
        applied: it belongs to a session, and this read answers for the AGENT.

        Returns `{agent_id: AgentOutputBudget}`; an empty list returns `{}`, never
        a zero — a missing entry must not read as a budget of zero.
        """
        from app.domain.providers.model_window import (
            resolve_model_thinking,
            resolve_model_window,
        )

        rows = [a for a in (agents or []) if a is not None]
        if not rows:
            return {}

        drivers: Dict[tuple, tuple] = {}
        for agent in rows:
            provider = getattr(agent, "provider", None)
            model = getattr(agent, "model", None)
            key = (provider or "", model or "")
            if key in drivers:
                continue
            window = await resolve_model_window(self.db, provider, model)
            thinking = await resolve_model_thinking(self.db, provider, model)
            drivers[key] = (window.value, thinking)

        # THE OBSERVED HALF (G-A ii): one query for the whole page, before the loop.
        # A caller with no session (the resolver-only path) gets no observation — the
        # same "None is the honest state for a caller with no database read" convention
        # the thinking signal and the window already use.
        observed = (
            await self._observed_budgets([a.id for a in rows])
            if self.db is not None else {}
        )

        out: Dict[int, AgentOutputBudget] = {}
        for agent in rows:
            provider = getattr(agent, "provider", None) or ""
            model = getattr(agent, "model", None) or ""
            window, thinking = drivers.get((provider, model), (None, None))
            driver = f"{provider}/{model}" if provider else model
            effective, reason = resolve_output_budget(
                agent,
                driver,
                thinking=thinking,
                path=PATH_DEFAULT,
                window=window,
            )
            out[agent.id] = AgentOutputBudget(
                declared=declared_output_budget(agent),
                effective=effective,
                reason=reason,
                path=PATH_DEFAULT,
                observed=observed.get(agent.id),
            )
        return out

    async def _observed_budgets(
        self, agent_ids: List[int]
    ) -> Dict[int, "AgentObservedBudget"]:
        """agent_id -> what its LAST turn actually carried (G-A ii), or absent.

        Read from each agent's most recent assistant message: the turn wrote
        {sent, declared, reason, path} into that row's `meta` when it finished, so this
        is the app's own record of the wire rather than a second reading of it. One
        query for the page, newest first, first hit per agent wins.

        A message whose meta carries no `budget` (a turn from before the record
        existed, or one that never reached a provider) is SKIPPED, not guessed at: the
        page shows the prediction alone rather than inventing an observation.
        """
        from app.infrastructure.database.models import ChatMessage, ChatSession

        ids = [i for i in agent_ids if i is not None]
        if not ids:
            return {}

        result = await self.db.execute(
            select(
                ChatMessage.meta,
                ChatMessage.created_at,
                ChatSession.agent_id,
            )
            .join(ChatSession, ChatSession.id == ChatMessage.session_id)
            .where(ChatMessage.role == "assistant", ChatSession.agent_id.in_(ids))
            .order_by(ChatMessage.id.desc())
        )

        out: Dict[int, AgentObservedBudget] = {}
        seen: set = set()
        for meta, created_at, agent_id in result.all():
            # NEWEST FIRST: the first message per agent IS its last turn. If that turn
            # recorded no budget, the observation is ABSENT — falling through to an
            # older message would label a stale number "last turn carried", which is
            # the kind of quiet lie this whole arc exists to remove.
            if agent_id in seen:
                continue
            seen.add(agent_id)
            budget = meta.get("budget") if isinstance(meta, dict) else None
            if not isinstance(budget, dict) or not isinstance(budget.get("sent"), int):
                continue
            out[agent_id] = AgentObservedBudget(
                sent=budget["sent"],
                declared=budget.get("declared"),
                reason=str(budget.get("reason") or ""),
                path=str(budget.get("path") or ""),
                at=created_at,
            )
        return out

    async def health_for_agents(self, agent_ids: List[int]) -> Dict[int, AgentHealth]:
        """
        Compute provider health for a set of agents from usage_logs.

        Mirrors scripts/core/check_agent_health.py so UI badges match the
        sweep scan: consecutive failures (most recent run), last error,
        and 7-day failure count. Agents with no usage → healthy (ok).

        Args:
            agent_ids: Agent ids to compute health for (may be empty)

        Returns:
            {agent_id: AgentHealth}
        """
        if not agent_ids:
            return {}

        # 7-day window. usage_logs.created_at = server_default func.now()
        # → SQLite CURRENT_TIMESTAMP = UTC, stored as a NAIVE string. So the
        # cutoff must be naive UTC too (aware or local would be off by the
        # host offset — host is UTC-5 here).
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)
        result = await self.db.execute(
            select(UsageLog)
            .where(UsageLog.agent_id.in_(agent_ids))
            .order_by(UsageLog.id.desc())
        )
        rows = [
            row for row in result.scalars().all()
            if row.created_at is not None and row.created_at >= cutoff
        ]

        # Group by agent preserving desc order
        by_agent: Dict[int, List[UsageLog]] = {}
        for row in rows:
            if row.agent_id is not None:
                by_agent.setdefault(row.agent_id, []).append(row)

        # Fetch dismissal timestamps in one query
        dismiss_result = await self.db.execute(
            select(Agent.id, Agent.health_dismissed_at).where(
                Agent.id.in_(agent_ids)
            )
        )
        dismissed_at: Dict[int, Optional[datetime]] = {
            agent_id: dismissed for agent_id, dismissed in dismiss_result.all()
        }

        health_map: Dict[int, AgentHealth] = {}
        for agent_id in agent_ids:
            logs = by_agent.get(agent_id, [])
            h = AgentHealth()
            failures_7d = 0
            consecutive = 0

            # A dismissal acknowledges failures up to its timestamp — only
            # failures AFTER it count (and only those within the 7d window).
            dismiss_ts = dismissed_at.get(agent_id)
            relevant = [
                log for log in logs
                if dismiss_ts is None or log.created_at is None
                or log.created_at > dismiss_ts
            ]

            # Count all failures in the 7-day window (for failures_7d)…
            for log in relevant:
                if not log.success:
                    failures_7d += 1
                    if h.last_error is None:
                        h.last_error = log.error_message
                        h.last_failure_at = log.created_at

            # …but consecutive only counts from the MOST RECENT log —
            # a success anywhere breaks the chain.
            for log in relevant:
                if log.success:
                    break
                consecutive += 1

            h.consecutive_failures = consecutive
            h.failures_7d = failures_7d
            if consecutive >= 3:
                h.status = "fail"  # degraded — likely broken config
            elif failures_7d > 0:
                h.status = "warn"
            health_map[agent_id] = h
        return health_map

    async def dismiss_health(self, agent_id: int) -> bool:
        """
        Dismiss an agent's health warning (F6).

        Sets health_dismissed_at = now, acknowledging all failures up to
        this moment. Returns True if the agent exists.

        Args:
            agent_id: Agent id

        Returns:
            True if the agent exists and was updated
        """
        agent = await self.db.get(Agent, agent_id)
        if not agent:
            return False
        # Naive UTC to match created_at storage (server_default func.now()).
        agent.health_dismissed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await self.db.flush()
        return True

    async def undismiss_health(self, agent_id: int) -> bool:
        """
        Clear an agent's health dismissal — warnings re-evaluate fully.

        Args:
            agent_id: Agent id

        Returns:
            True if the agent exists and was updated
        """
        agent = await self.db.get(Agent, agent_id)
        if not agent:
            return False
        agent.health_dismissed_at = None
        await self.db.flush()
        return True

    async def get_agent_card(self, agent_id: int) -> Optional[AgentCard]:
        """
        Build an A2A AgentCard for a given agent.

        Generates a standardized agent discovery document from the agent's
        database record, including skills derived from system_prompt and
        enabled tools.

        Args:
            agent_id: Agent ID

        Returns:
            AgentCard if agent found, None otherwise
        """
        agent = await self.get_by_id(agent_id)
        if not agent:
            return None

        # Build skills list from system_prompt (as primary skill)
        skills: list[AgentSkill] = []

        if agent.system_prompt:
            # Truncate system prompt to first 200 chars for skill description
            skill_desc = agent.system_prompt[:200]
            if len(agent.system_prompt) > 200:
                skill_desc += "..."
            skills.append(AgentSkill(
                id=f"agent-{agent.id}-primary",
                name=agent.name,
                description=skill_desc,
                examples=["Ask this agent to perform its designated task"],
            ))

        # Add tool-based skills
        tools = await self.get_enabled_tools_for_agent(str(agent.id))
        for tool in tools:
            tool_name = tool.get("function", {}).get("name", "unknown")
            tool_desc = tool.get("function", {}).get("description", "")
            skills.append(AgentSkill(
                id=f"agent-{agent.id}-tool-{tool_name}",
                name=tool_name,
                description=tool_desc,
                examples=[f"Use the {tool_name} tool"],
            ))

        # Determine capabilities
        capabilities = AgentCapabilities(
            streaming=True,
            push_notifications=False,
            delegation=True,  # Agents can receive delegated tasks
        )

        # ARM resource card (Phase F) — the SELECTION surface,
        # separate from the user-facing persona (study 09)
        arm = await self._build_arm_card(agent, tools)

        return AgentCard(
            name=agent.name,
            description=agent.description,
            agent_id=agent.id,
            provider=agent.provider,
            model=agent.model,
            skills=skills,
            capabilities=capabilities,
            version="1.0",
            arm=arm,
        )

    async def _build_arm_card(self, agent, tools) -> Optional[AgentArmCard]:
        """The ARM resource card: depth, competence, spec, capability.

        Two-audience principle: the user sees the persona; ARM sees
        this card when selecting agents for orchestration. All
        fields derived or declared — never user-entered at runtime.
        """
        from app.domain.tools.provider_spec import spec_for
        from app.infrastructure.database.models import CognitiveProfile

        # depth: the cognitive profile name
        depth = None
        if agent.cognitive_profile_id is not None:
            prof = (
                await self.db.execute(
                    select(CognitiveProfile).where(
                        CognitiveProfile.id == agent.cognitive_profile_id
                    )
                )
            ).scalar_one_or_none()
            if prof:
                depth = prof.name

        # competence: the declared skills
        competence = list(agent.skills or [])

        # spec: provider location + size (the classifier)
        location, size = spec_for(agent.provider, agent.model)
        spec = {"location": location, "size": size}

        # capability: the enabled tool slugs (capability vocabulary)
        capability = []
        for tool in tools:
            fn = tool.get("function", {})
            slug = fn.get("name")
            if slug:
                capability.append(slug)

        return AgentArmCard(
            depth=depth, competence=competence,
            spec=spec, capability=capability,
        )

    async def list_all(
        self, skip: int = 0, limit: int = 100, search: Optional[str] = None
    ) -> tuple[list[Agent], int]:
        """
        List all agents with pagination and optional search filter.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            search: Optional search term to filter agents by name (case-insensitive)

        Returns:
            Tuple of (agents list, total count)
        """
        # Base query — the LIVE pool: soft-deleted agents (the
        # recoverable delete, Phase C) are excluded everywhere
        base_query = select(Agent).where(Agent.deleted_at.is_(None))

        # Apply search filter if provided
        if search:
            like_pattern = f"%{search}%"
            base_query = base_query.where(Agent.name.ilike(like_pattern))

        # Get total count
        count_query = select(func.count()).select_from(
            base_query.subquery()
        )
        total = await self.db.scalar(count_query)

        # Get paginated agents
        query = base_query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        agents = list(result.scalars().all())

        return agents, total or 0

    async def list_all_agents(
        self, search: Optional[str] = None
    ) -> tuple[list[Agent], int]:
        """
        List ALL agents without pagination.

        Args:
            search: Optional search term to filter agents by name (case-insensitive)

        Returns:
            Tuple of (all agents list, total count)
        """
        # Base query — the LIVE pool: soft-deleted agents (the
        # recoverable delete, Phase C) are excluded everywhere
        base_query = select(Agent).where(Agent.deleted_at.is_(None))

        # Apply search filter if provided
        if search:
            like_pattern = f"%{search}%"
            base_query = base_query.where(Agent.name.ilike(like_pattern))

        # Get total count
        count_query = select(func.count()).select_from(
            base_query.subquery()
        )
        total = await self.db.scalar(count_query)

        # Get all agents (no offset/limit)
        result = await self.db.execute(base_query)
        agents = list(result.scalars().all())

        return agents, total or 0

    async def get_agent_stats(self) -> AgentStatsResponse:
        """
        Get aggregate agent statistics for system management.

        Computes counts, provider/model distribution, delegation status,
        and tool assignment stats across all agents.

        Returns:
            AgentStatsResponse with aggregate statistics
        """
        # Get all agents
        result = await self.db.execute(select(Agent))
        all_agents = list(result.scalars().all())
        total = len(all_agents)

        # Count active/inactive
        active = sum(1 for a in all_agents if a.is_active)
        inactive = total - active

        # Count delegation
        delegation_enabled = sum(1 for a in all_agents if a.allow_delegation)
        delegation_disabled = total - delegation_enabled

        # Group by provider
        by_provider: dict[str, int] = {}
        for a in all_agents:
            provider = a.provider or "unknown"
            by_provider[provider] = by_provider.get(provider, 0) + 1

        # Group by model
        by_model: dict[str, int] = {}
        for a in all_agents:
            model = a.model or "unknown"
            by_model[model] = by_model.get(model, 0) + 1

        # Count agents with/without tools
        # Get distinct agent_ids from agent_tools that have at least one tool
        tools_result = await self.db.execute(
            select(AgentTool.agent_id).distinct()
        )
        agent_ids_with_tools = {
            str(row[0]) for row in tools_result.all()
        }

        # Agent.id is int, AgentTool.agent_id is str — compare stringified versions
        agents_with_tools = sum(
            1 for a in all_agents if str(a.id) in agent_ids_with_tools
        )
        agents_without_tools = total - agents_with_tools

        return AgentStatsResponse(
            total_agents=total,
            active_agents=active,
            inactive_agents=inactive,
            agents_with_delegation_enabled=delegation_enabled,
            agents_with_delegation_disabled=delegation_disabled,
            agents_with_tools=agents_with_tools,
            agents_without_tools=agents_without_tools,
            by_provider=by_provider,
            by_model=by_model,
        )

    async def find_duplicates(
        self,
        criteria: str = "all",
        min_confidence: float = 0.5,
    ) -> DuplicatesResponse:
        """
        Find duplicate agents based on specified criteria.

        Supports multiple duplicate detection levels:
        - direct_copy: Agents whose name starts with "Copy of {original_name}"
        - config_twin: Agents with same provider + model + system_prompt
        - functional_twin: Agents with same provider + model + system_prompt + tools
        - name_similar: Agents with similar names (fuzzy match) and same provider
        - all: All of the above

        Args:
            criteria: Duplicate detection criteria
            min_confidence: Minimum confidence threshold (0.0-1.0)

        Returns:
            DuplicatesResponse with grouped duplicate agents
        """
        # Load ALL agents (max page_size for complete analysis)
        query = select(Agent).order_by(Agent.name, Agent.id)
        result = await self.db.execute(query)
        all_agents = list(result.scalars().all())
        total_agents = len(all_agents)

        groups: list[DuplicateGroup] = []
        seen_agent_ids: set[int] = set()

        # ── Level 1: Direct Copies ──────────────────────────────────────
        if criteria in ("all", "direct_copy"):
            # Build a map: name -> agent for "Copy of" detection
            name_to_agents: dict[str, list[Agent]] = {}
            for agent in all_agents:
                base_name = agent.name
                # Strip "Copy of" prefix to find original
                while base_name.startswith("Copy of "):
                    base_name = base_name[8:]
                if base_name not in name_to_agents:
                    name_to_agents[base_name] = []
                name_to_agents[base_name].append(agent)

            for base_name, agents in name_to_agents.items():
                if len(agents) > 1:
                    # Sort by id to find original vs copies
                    agents_sorted = sorted(agents, key=lambda a: a.id)
                    original = agents_sorted[0]
                    copies = [a for a in agents_sorted[1:] if a.name.startswith("Copy of ") or " (Copy)" in a.name]
                    if copies:
                        group_agents = [original] + copies
                        group_info = [
                            DuplicateAgentInfo(
                                id=a.id,
                                name=a.name,
                                provider=a.provider,
                                model=a.model,
                                created_at=a.created_at,
                            )
                            for a in group_agents
                        ]
                        groups.append(DuplicateGroup(
                            criteria="direct_copy",
                            confidence=1.0,
                            agents=group_info,
                            match_reason=(
                                f"Agent(s) {', '.join(str(a.id) for a in copies)} "
                                f"are direct copies of Agent {original.id} ('{original.name}')"
                            ),
                            group_name=(
                                f"Direct Copy: '{original.name}' ({len(copies)} copy{'ies' if len(copies) != 1 else 'y'})"
                            ),
                        ))
                        for a in group_agents:
                            seen_agent_ids.add(a.id)

        # ── Level 2: Configuration Twins ────────────────────────────────
        if criteria in ("all", "config_twin"):
            # Group by provider + model + system_prompt
            config_groups: dict[tuple[str, str, str], list[Agent]] = {}
            for agent in all_agents:
                key = (agent.provider, agent.model, agent.system_prompt or "")
                if key not in config_groups:
                    config_groups[key] = []
                config_groups[key].append(agent)

            for (provider, model, _), agents in config_groups.items():
                if len(agents) > 1:
                    # Filter out agents already seen in higher-confidence groups
                    unseen = [a for a in agents if a.id not in seen_agent_ids]
                    if len(unseen) > 1:
                        group_info = [
                            DuplicateAgentInfo(
                                id=a.id,
                                name=a.name,
                                provider=a.provider,
                                model=a.model,
                                created_at=a.created_at,
                            )
                            for a in sorted(unseen, key=lambda a: a.id)
                        ]
                        groups.append(DuplicateGroup(
                            criteria="config_twin",
                            confidence=0.95,
                            agents=group_info,
                            match_reason=(
                                f"Agents share the same provider ('{provider}'), "
                                f"model ('{model}'), and system prompt"
                            ),
                            group_name=(
                                f"Configuration Twin: {provider}/{model} ({len(unseen)} agents)"
                            ),
                        ))
                        for a in unseen:
                            seen_agent_ids.add(a.id)

        # ── Level 3: Functional Twins (same config + same tools) ────────
        if criteria in ("all", "functional_twin"):
            # Load tool assignments for all agents
            all_agent_tools: dict[int, set[str]] = {}
            for agent in all_agents:
                if agent.id not in seen_agent_ids:
                    agent_tools = await self.agent_tool_service.list_agent_tools(
                        str(agent.id), is_enabled=True
                    )
                    tool_slugs = set()
                    for at in agent_tools:
                        if at.tool and at.tool.slug:
                            tool_slugs.add(at.tool.slug)
                    all_agent_tools[agent.id] = tool_slugs

            # Group agents by (provider, model, system_prompt, tool_set)
            # We use frozenset of tool slugs as part of the key
            functional_groups: dict[tuple[str, str, str, frozenset], list[Agent]] = {}
            for agent in all_agents:
                if agent.id in seen_agent_ids:
                    continue
                tool_set: set[str] = all_agent_tools.get(agent.id, set())
                func_key = (
                    agent.provider,
                    agent.model,
                    agent.system_prompt or "",
                    frozenset(tool_set),
                )
                if func_key not in functional_groups:
                    functional_groups[func_key] = []
                functional_groups[func_key].append(agent)

            for (provider, model, _, ftool_set), agents in functional_groups.items():
                if len(agents) > 1:
                    group_info = [
                        DuplicateAgentInfo(
                            id=a.id,
                            name=a.name,
                            provider=a.provider,
                            model=a.model,
                            created_at=a.created_at,
                        )
                        for a in sorted(agents, key=lambda a: a.id)
                    ]
                    tool_count = len(ftool_set)
                    groups.append(DuplicateGroup(
                        criteria="functional_twin",
                        confidence=0.9,
                        agents=group_info,
                        match_reason=(
                            f"Agents share the same provider ('{provider}'), "
                            f"model ('{model}'), system prompt, and {tool_count} tool(s)"
                        ),
                        group_name=(
                            f"Functional Twin: {provider}/{model} + {tool_count} tool{'s' if tool_count != 1 else ''} ({len(agents)} agents)"
                        ),
                    ))
                    for a in agents:
                        seen_agent_ids.add(a.id)

        # ── Level 4: Name Similarity ────────────────────────────────────
        if criteria in ("all", "name_similar"):
            # Simple name similarity: check for shared words in name
            name_groups: dict[tuple[str, ...], list[Agent]] = {}
            for agent in all_agents:
                if agent.id in seen_agent_ids:
                    continue
                # Normalize name: lowercase, strip special chars, extract words
                normalized = re.sub(r'[^a-z0-9\s]', '', agent.name.lower())
                words = set(normalized.split())
                # Skip single-word names (too generic)
                if len(words) < 2:
                    continue
                # Use a sorted tuple of words as the grouping key
                word_key = tuple(sorted(words))
                if word_key not in name_groups:
                    name_groups[word_key] = []
                name_groups[word_key].append(agent)

            for word_key, agents in name_groups.items():
                if len(agents) > 1:
                    # Filter by same provider for higher confidence
                    provider_groups: dict[str, list[Agent]] = {}
                    for a in agents:
                        if a.provider not in provider_groups:
                            provider_groups[a.provider] = []
                        provider_groups[a.provider].append(a)

                    for provider, p_agents in provider_groups.items():
                        if len(p_agents) > 1:
                            confidence = 0.8 if len(word_key) >= 3 else 0.6
                            if confidence >= min_confidence:
                                group_info = [
                                    DuplicateAgentInfo(
                                        id=a.id,
                                        name=a.name,
                                        provider=a.provider,
                                        model=a.model,
                                        created_at=a.created_at,
                                    )
                                    for a in sorted(p_agents, key=lambda a: a.id)
                                ]
                                groups.append(DuplicateGroup(
                                    criteria="name_similar",
                                    confidence=confidence,
                                    agents=group_info,
                                    match_reason=(
                                        f"Agents have similar names (shared keywords: "
                                        f"{', '.join(word_key)}) and same provider ('{provider}')"
                                    ),
                                    group_name=(
                                        f"Name Similarity: keywords '{', '.join(word_key)}' ({len(p_agents)} agents)"
                                    ),
                                ))
                                for a in p_agents:
                                    seen_agent_ids.add(a.id)

        # Filter by confidence threshold
        groups = [g for g in groups if g.confidence >= min_confidence]

        # Count unique agents in duplicates
        all_dup_ids: set[int] = set()
        for g in groups:
            for dup_agent in g.agents:
                all_dup_ids.add(dup_agent.id)

        return DuplicatesResponse(
            duplicate_groups=groups,
            total_agents_analyzed=total_agents,
            duplicate_groups_found=len(groups),
            total_agents_in_duplicates=len(all_dup_ids),
        )

    async def get_by_id(self, agent_id: int) -> Optional[Agent]:
        """
        Get agent by ID.

        Args:
            agent_id: Agent ID

        Returns:
            Agent if found, None otherwise
        """
        query = select(Agent).where(Agent.id == agent_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def resolve_agent(self, name: str) -> Agent:
        """The white pages (ARM Phase A): resolve a unique name to
        exactly one agent. STRICT — raises on missing (dead-letter,
        don't hang); the caller decides nearest-match if ever needed.
        """
        agent = (
            await self.db.execute(
                select(Agent).where(
                    Agent.name == name, Agent.deleted_at.is_(None)
                )
            )
        ).scalar_one_or_none()
        if agent is None:
            raise ValueError(
                f"No agent named '{name}' in the pool. "
                f"Address by an existing agent name (the registry is "
                f"the source of truth)."
            )
        return agent

    async def create(self, agent_data: AgentCreate) -> Agent:
        """
        Create a new agent.

        Args:
            agent_data: Agent creation data

        Returns:
            Created agent

        Raises:
            ValueError: If referenced cognitive_profile_id does not exist
        """
        data = agent_data.model_dump()

        # THE NAME BAN (Phase A, ARM roadmap — addressing precondition):
        # exact-name duplicates are rejected with a clear error, BEFORE
        # the DB unique constraint fires. Pool addressing requires
        # "use X" to resolve to exactly one agent.
        name = data.get("name", "").strip()
        existing = (
            await self.db.execute(select(Agent).where(Agent.name == name))
        ).scalar_one_or_none()
        if existing is not None:
            raise ValueError(
                f"An agent named '{name}' already exists (id={existing.id}). "
                f"Agent names are unique — the pool addresses agents by name. "
                f"Choose a different name, or update the existing agent."
            )

        # Validate cognitive_profile_id if provided
        cognitive_profile_id = data.get("cognitive_profile_id")
        if cognitive_profile_id is not None:
            from app.infrastructure.database.models import CognitiveProfile
            result = await self.db.execute(
                select(CognitiveProfile).where(CognitiveProfile.id == cognitive_profile_id)
            )
            if result.scalar_one_or_none() is None:
                raise ValueError(
                    f"Cognitive profile with id={cognitive_profile_id} does not exist"
                )

        # The readouts (cognitive_profile_name/_depth) are OUTPUT-only
        # (server-derived, 2026-09-06) — the Agent model stores the id.
        # model_dump() serializes them, so filter before constructing.
        data = {
            k: v for k, v in data.items()
            if k not in ("cognitive_profile_name", "cognitive_profile_depth")
        }
        agent = Agent(**data)
        self.db.add(agent)
        await self.db.flush()
        await self.db.refresh(agent)

        logger.info(f"Created agent: {agent.name} (id={agent.id})")
        return agent

    async def update(
        self, agent_id: int, agent_data: AgentUpdate
    ) -> Optional[Agent]:
        """
        Update an existing agent.

        Args:
            agent_id: Agent ID
            agent_data: Agent update data

        Returns:
            Updated agent if found, None otherwise

        Raises:
            ValueError: If referenced cognitive_profile_id does not exist
        """
        agent = await self.get_by_id(agent_id)
        if not agent:
            return None

        update_data = agent_data.model_dump(exclude_unset=True)

        # The readouts are OUTPUT-only (server-derived) — ignore any
        # client attempt to write them (setattr would silently no-op).
        update_data.pop("cognitive_profile_name", None)
        update_data.pop("cognitive_profile_depth", None)

        # THE RENAME (2026-08-19): a name change follows the create
        # BAN — unique names only (the pool addresses by name). The
        # workspace_key (the disk identity) NEVER changes — renames
        # don't move files; the agent.json's name field is synced.
        new_name = update_data.get("name")
        if new_name is not None:
            new_name = new_name.strip()
            if not new_name:
                raise ValueError("Agent name cannot be empty.")
            clash = (
                await self.db.execute(
                    select(Agent).where(
                        Agent.name == new_name,
                        Agent.id != agent_id,
                    )
                )
            ).scalar_one_or_none()
            if clash is not None:
                raise ValueError(
                    f"An agent named '{new_name}' already exists (id={clash.id}). "
                    f"Agent names are unique — the pool addresses agents by name. "
                    f"Choose a different name."
                )
            update_data["name"] = new_name

        # Validate cognitive_profile_id if being updated
        cognitive_profile_id = update_data.get("cognitive_profile_id")
        if cognitive_profile_id is not None:
            from app.infrastructure.database.models import CognitiveProfile
            result = await self.db.execute(
                select(CognitiveProfile).where(CognitiveProfile.id == cognitive_profile_id)
            )
            if result.scalar_one_or_none() is None:
                raise ValueError(
                    f"Cognitive profile with id={cognitive_profile_id} does not exist"
                )

        renamed = "name" in update_data
        for field, value in update_data.items():
            setattr(agent, field, value)

        # THE PERSONA SYNC (2026-09-02, the workspace-first partition):
        # a system_prompt update writes persona.md in the agent's
        # folder too (the file is the workspace home; the row keeps
        # the synced fallback). The file write happens BEFORE the
        # flush — the agent row already carries the new text.
        if "system_prompt" in update_data and agent.workspace_key:
            from app.domain.agents.persona import write_persona
            write_persona(agent, agent.system_prompt or "")

        await self.db.flush()
        await self.db.refresh(agent)

        # the disk-identity sync (2026-08-19): the workspace folder
        # and its key never change on rename; the agent.json's name
        # field reflects the new name (the workspace stays stable —
        # chat history, memory, and skills keep their home).
        if renamed and agent.workspace_key:
            from app.domain.agents.workspace import AGENTS_ROOT
            ws = AGENTS_ROOT / agent.workspace_key
            jf = ws / "agent.json"
            if jf.exists():
                import json as _json
                try:
                    blob = _json.loads(jf.read_text(encoding="utf-8", errors="replace"))
                    if isinstance(blob, dict):
                        blob["name"] = agent.name
                        jf.write_text(_json.dumps(blob, indent=2), encoding="utf-8")
                except Exception:
                    pass  # the agent.json is best-effort — the DB row is the truth

        logger.info(f"Updated agent: {agent.name} (id={agent.id})")
        return agent

    async def adopt_package(self, agent_id: int, package_id: str) -> Optional[Agent]:
        """
        THE ADOPT ACTION (2026-08-24, the agent-package Phase 2):
        provision this agent FROM a package blueprint.

        THE OWNERSHIP RULE: the agent OWNS its copies. Adopt COPIES
        the package's kit_id + skills + llm_spec into the agent's
        OWN fields + sets package_id (provenance). The package never
        owns the agent — later package edits don't mutate the agent.

        Args:
            agent_id: Agent ID
            package_id: The package blueprint id

        Returns:
            The updated agent, or None if the agent/package missing

        Raises:
            ValueError: if the package is inactive
        """
        from app.domain.agent_packages.models import AgentPackage

        agent = await self.get_by_id(agent_id)
        if not agent:
            return None

        pkg_row = await self.db.execute(
            select(AgentPackage).where(AgentPackage.id == package_id)
        )
        pkg = pkg_row.scalar_one_or_none()
        if not pkg:
            return None
        if not pkg.is_active:
            raise ValueError(f"Package '{pkg.name}' is inactive")

        # THE COPY — the agent's OWN fields (never a live read)
        agent.kit_id = pkg.kit_id
        agent.skills = list(pkg.skills or [])
        agent.llm_spec = dict(pkg.llm_spec) if pkg.llm_spec else None
        agent.package_id = pkg.id  # provenance

        await self.db.flush()
        await self.db.refresh(agent)
        logger.info(
            f"Agent {agent.name} (id={agent.id}) adopted package "
            f"'{pkg.name}' — kit={agent.kit_id}, skills={agent.skills}"
        )
        return agent

    async def delete(self, agent_id: int) -> bool:
        """
        Delete an agent.

        Args:
            agent_id: Agent ID

        Returns:
            True if deleted, False if not found

        Raises:
            ValueError: If agent is a built-in system agent (protected from deletion)
        """
        agent = await self.get_by_id(agent_id)
        if not agent:
            return False

        # Protect built-in agents from deletion
        if getattr(agent, 'is_builtin', False):
            logger.warning(
                f"Blocked deletion of built-in agent: {agent.name} (id={agent_id})"
            )
            raise ValueError(
                f"Cannot delete built-in agent '{agent.name}' (id={agent_id}). "
                f"Built-in agents are protected from deletion."
            )

        await self.db.delete(agent)
        await self.db.flush()

        logger.info(f"Deleted agent: {agent.name} (id={agent_id})")
        return True

    async def update_profile_image(
        self, agent_id: int, image_url: str
    ) -> Optional[Agent]:
        """
        Update agent profile image.

        Args:
            agent_id: Agent ID
            image_url: URL/path to profile image

        Returns:
            Updated agent if found, None otherwise
        """
        agent = await self.get_by_id(agent_id)
        if not agent:
            return None

        agent.profile_image_url = image_url
        await self.db.flush()
        await self.db.refresh(agent)

        logger.info(f"Updated profile image for agent: {agent.name} (id={agent.id})")
        return agent

    async def list_system_prompt_templates(self) -> List[SystemPromptTemplate]:
        """
        List all available system prompt templates (built-in + database agent templates).

        Returns:
            List of available templates
        """
        # Get built-in templates
        templates = list(self.TEMPLATES.values())
        
        # Get database agent templates
        try:
            from sqlalchemy import select
            stmt = select(AgentTemplate).where(AgentTemplate.is_public)
            result = await self.db.execute(stmt)
            db_templates = result.scalars().all()
            
            # Convert agent templates to system prompt templates
            for db_tpl in db_templates:
                templates.append(SystemPromptTemplate(
                    id=str(db_tpl.id),
                    name=db_tpl.name,
                    description=db_tpl.description,
                    prompt=db_tpl.system_prompt or "",
                    variables=[]
                ))
        except Exception:
            # Silently ignore database errors - just return built-in templates
            pass
        
        return templates

    async def get_template(self, template_id: str) -> Optional[SystemPromptTemplate]:
        """
        Get a specific template by ID.

        Args:
            template_id: Template identifier

        Returns:
            Template if found, None otherwise
        """
        return self.TEMPLATES.get(template_id)

    async def apply_template(
        self, template_id: str, variables: dict
    ) -> Optional[str]:
        """
        Apply a template with the given variables.

        Args:
            template_id: Template identifier (can be built-in ID or database agent template ID)
            variables: Dictionary of variable values

        Returns:
            Rendered prompt string if template found, None otherwise
        """
        # First try built-in templates
        template = self.TEMPLATES.get(template_id)
        if template:
            prompt = template.prompt
            # Replace variables in template
            for var_name, var_value in variables.items():
                placeholder = "{" + var_name + "}"
                prompt = prompt.replace(placeholder, str(var_value))
            
            # Remove any remaining unfilled placeholders
            prompt = re.sub(r'\{[^}]+\}', '', prompt)
            return prompt
        
        # Try database agent templates (convert to int if numeric)
        try:
            template_id_int = int(template_id)
            agent_template = await self.get_template_by_id(template_id_int)
            if agent_template:
                return agent_template.system_prompt
        except (ValueError, AttributeError):
            pass
        
        return None

    # ========================================================================
    # Agent Versioning Methods
    # ========================================================================

    async def create_template(
        self,
        template_data: AgentTemplateCreate,
        created_by: str | None = None,
    ) -> "AgentTemplate":
        """
        Create a new agent template.

        Args:
            template_data: Template creation data
            created_by: User ID who created the template

        Returns:
            Created AgentTemplate object
        """
        from app.infrastructure.database.models import AgentTemplate

        template = AgentTemplate(
            name=template_data.name,
            description=template_data.description,
            provider=template_data.provider,
            model=template_data.model,
            system_prompt=template_data.system_prompt,
            parameters=template_data.parameters,
            is_public=template_data.is_public,
            created_by=created_by,
            tags=template_data.tags,
            # THE FULL CONFIG (2026-09-10): these six exist on the schema AND
            # the table but were never copied — a template silently kept the
            # chatbot's provider/model and dropped everything else.
            cognitive_profile_id=template_data.cognitive_profile_id,
            execution_mode=template_data.execution_mode,
            behavior_config=template_data.behavior_config,
            preferred_providers=template_data.preferred_providers,
            fallback_enabled=template_data.fallback_enabled,
            allow_delegation=template_data.allow_delegation,
            # THE CHARACTER (the News Team arc)
            kit_ids=template_data.kit_ids,
            skills=template_data.skills,
            workspace_files=template_data.workspace_files,
            profile_image_url=template_data.profile_image_url,
        )

        self.db.add(template)
        await self.db.flush()
        await self.db.refresh(template)

        logger.info(f"✅ Created template: {template.name} (id={template.id})")
        return template

    async def get_template_by_id(self, template_id: int) -> Optional["AgentTemplate"]:
        """
        Get a template by ID.

        Args:
            template_id: Template ID

        Returns:
            AgentTemplate object if found, None otherwise
        """
        from app.infrastructure.database.models import AgentTemplate

        query = select(AgentTemplate).where(AgentTemplate.id == template_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_templates(
        self,
        is_public: bool | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list["AgentTemplate"], int]:
        """
        List all templates with optional filters.

        Args:
            is_public: Filter by public/private status (None = all)
            search: Search in name and description
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (templates list, total count)
        """
        from app.infrastructure.database.models import AgentTemplate
        from sqlalchemy import func

        # Build query
        query = select(AgentTemplate)

        # Apply filters
        if is_public is not None:
            query = query.where(AgentTemplate.is_public == is_public)

        if search:
            search_filter = (
                AgentTemplate.name.ilike(f"%{search}%") |
                AgentTemplate.description.ilike(f"%{search}%")
            )
            query = query.where(search_filter)

        # Get total count
        count_query = select(func.count()).select_from(AgentTemplate)
        if is_public is not None:
            count_query = count_query.where(AgentTemplate.is_public == is_public)
        if search:
            count_query = count_query.where(
                (AgentTemplate.name.ilike(f"%{search}%")) |
                (AgentTemplate.description.ilike(f"%{search}%"))
            )
        total = await self.db.scalar(count_query)

        # Get templates
        query = query.offset(skip).limit(limit).order_by(AgentTemplate.name)
        result = await self.db.execute(query)
        templates = list(result.scalars().all())

        return templates, total or 0

    async def update_template(
        self,
        template_id: int,
        template_data: AgentTemplateUpdate,
    ) -> Optional["AgentTemplate"]:
        """
        Update an existing template.

        Args:
            template_id: Template ID
            template_data: Template update data

        Returns:
            Updated AgentTemplate object if found, None otherwise
        """

        template = await self.get_template_by_id(template_id)
        if not template:
            return None

        update_data = template_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(template, field, value)

        await self.db.flush()
        await self.db.refresh(template)

        logger.info(f"✅ Updated template: {template.name} (id={template.id})")
        return template

    async def delete_template(self, template_id: int) -> bool:
        """
        Delete a template.

        Args:
            template_id: Template ID

        Returns:
            True if deleted, False if not found
        """

        template = await self.get_template_by_id(template_id)
        if not template:
            return False

        await self.db.delete(template)
        await self.db.flush()

        logger.info(f"🗑️ Deleted template: {template.name} (id={template_id})")
        return True

    async def apply_template_to_agent(
        self,
        template_id: int,
        agent_name: str,
        description: str | None = None,
    ) -> Optional["Agent"]:
        """
        Create a new agent from a template.

        Args:
            template_id: Template ID to use
            agent_name: Name for the new agent
            description: Optional description for the new agent

        Returns:
            Created Agent object if template found, None otherwise
        """

        # Get template
        template = await self.get_template_by_id(template_id)
        if not template:
            return None

        # Increment usage count
        template.usage_count += 1

        # the face for a template that carries none (agents are characters)
        _allocate_face: str | None = None
        if not template.profile_image_url:
            from app.domain.assets.faces import pick_agent_face
            _allocate_face = pick_agent_face(await self._used_faces())

        # Create agent from template
        agent = Agent(
            name=agent_name,
            description=description or template.description,
            provider=template.provider,
            model=template.model,
            system_prompt=template.system_prompt,
            # G-I: the row's parameters are validated as they are COPIED — this path
            # writes the JSON column directly and never meets a request schema, so a
            # stray key in a template row would otherwise ride into every agent made
            # from it.
            parameters=checked_parameters(template.parameters),
            template_id=str(template.id),
            cognitive_profile_id=template.cognitive_profile_id,
            execution_mode=template.execution_mode,
            behavior_config=template.behavior_config,
            preferred_providers=template.preferred_providers,
            fallback_enabled=template.fallback_enabled,
            allow_delegation=template.allow_delegation,
            # THE CHARACTER (2026-09-10): the skills seed from the shared
            # library (the scaffold copies them). The FACE comes from the
            # template only when one was set explicitly; otherwise the new
            # agent gets its own from the pool (never a silently-inherited
            # face — see the delivered request: a clone must look like a
            # NEW agent, and the user sets it properly in the profile).
            skills=template.skills,
            profile_image_url=template.profile_image_url or _allocate_face,
        )

        self.db.add(agent)
        await self.db.flush()
        await self.db.refresh(agent)

        # THE WORKSPACE (2026-09-10, the apply-path fix): a row alone gives
        # an agent with no folder, no persona, no state. The CREATE path
        # always went through the repository seam (`create_agent` →
        # `scaffold`); the apply bypassed it, so every agent made from a
        # template was born folder-less. Found by an empirical apply test:
        # the response carried `workspace_key: null` and no folder existed.
        try:
            from app.domain.agents.repository import get_agent_repository
            repo = get_agent_repository(self.db)
            await repo.provision_workspace(agent.id)
            await self.db.refresh(agent)

            # THE TOOL SURFACE (2026-09-10): attach the template's kits via
            # the join (the truth). Best-effort per kit — a kit that is no
            # longer installed must not fail the whole apply.
            for kit_id in (template.kit_ids or []):
                try:
                    from app.domain.agent_kits.service import AgentKitService
                    await AgentKitService(self.db).attach(agent.id, kit_id)
                except Exception as _e:  # noqa: BLE001
                    logger.warning(f"  kit {kit_id} not attached: {_e}")

            # THE WORKSPACE SEED (2026-09-10): plant the template's files
            # (the beat sheets and any other seed). Never overwrites an
            # existing file.
            if template.workspace_files and agent.workspace_key:
                from app.domain.agents.workspace import AGENTS_ROOT
                ws = AGENTS_ROOT / agent.workspace_key
                for rel, content in template.workspace_files.items():
                    target = ws / rel
                    if target.exists():
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(str(content), encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            # the row is already committed-worthy; a folder failure must not
            # silently vanish — report it and let the caller see the agent
            logger.error(
                f"⚠️  Applied agent {agent.id} but the workspace scaffold failed: {e}"
            )

        logger.info(f"✅ Created agent from template: {agent.name} (id={agent.id})")
        return agent

    async def _used_faces(self) -> set[str]:
        """Every profile_image_url already in use (for face allocation)."""
        from sqlalchemy import select
        from app.infrastructure.database.models import Agent as AgentModel

        rows = (await self.db.execute(
            select(AgentModel.profile_image_url).where(
                AgentModel.profile_image_url.is_not(None)
            )
        )).scalars().all()
        return {r for r in rows if r}

    async def _agent_kit_ids(self, agent_id: int) -> list[str]:
        """The agent's kit ids from the agent_kits join (the truth)."""
        from app.domain.agent_kits.model import AgentKit
        from sqlalchemy import select

        rows = (await self.db.execute(
            select(AgentKit.kit_id).where(AgentKit.agent_id == agent_id)
        )).scalars().all()
        return list(rows)

    def _capture_workspace_files(self, agent) -> dict | None:
        """Collect the agent's SEEDABLE workspace files for a template.

        NOTHING, deliberately (2026-09-10, the user's call).

        A template carries the CHARACTER: the soul (the row's
        system_prompt), the skills (seeded by name from the shared
        library), the tool surface (the kits) and a fresh face. It does
        NOT carry the agent's WORK — because, verbatim:

            "The whole purpose of creating a new agent is to have a new
             beat."

        A clone whose beat arrived pre-filled is a clone of the OLD
        assignment: the Middle East, the original's topics, and whatever
        stray file happened to sit in the folder (a new reporter inherited
        both a beat sheet and a ZERO-BYTE leftover, and had to notice
        "Bob's judgment decides what goes in" inside her own sheet and
        remove it herself).

        The mechanism stays — the field, and the apply's writer — so a
        template CAN seed files when that is genuinely wanted one day.
        The default is nothing. A new agent builds its beat with its user,
        through the beat-sheets skill and update-beat.
        """
        return None

    async def save_agent_as_template(
        self,
        agent_id: int,
        template_name: str,
        template_description: str | None = None,
        is_public: bool = False,
        tags: list[str] | None = None,
    ) -> "AgentTemplate":
        """
        Save an existing agent configuration as a new template.

        Args:
            agent_id: ID of agent to save as template
            template_name: Name for the new template
            template_description: Optional description for the template
            is_public: Whether template should be public
            tags: Optional list of tags

        Returns:
            Created AgentTemplate object

        Raises:
            ValueError: If agent not found
        """
        from app.infrastructure.database.models import AgentTemplate

        # Get agent
        agent = await self.get_by_id(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        # Create template from agent configuration
        template = AgentTemplate(
            name=template_name,
            description=template_description or agent.description or "",
            provider=agent.provider,
            model=agent.model,
            system_prompt=agent.system_prompt or "",
            # G-I: validated as it is copied — see the note on the template→agent path.
            parameters=checked_parameters(agent.parameters),
            cognitive_profile_id=agent.cognitive_profile_id,
            execution_mode=agent.execution_mode,
            behavior_config=agent.behavior_config,
            preferred_providers=agent.preferred_providers,
            fallback_enabled=agent.fallback_enabled,
            allow_delegation=agent.allow_delegation,
            is_public=is_public,
            created_by=None,  # Would be set from auth in real app
            tags=tags,
            # THE CHARACTER (2026-09-10): captured from the agent. The KITS
            # come from the agent_kits join — the truth; the singular
            # agents.kit_id slot is retired semantically.
            skills=agent.skills,
            # NOTE: the FACE is deliberately NOT captured. A clone that
            # wears the original's face is confusing in exactly the way a
            # clone should not be — every applied agent gets its own face
            # from the pool (and the user can set another in the profile).
            kit_ids=await self._agent_kit_ids(agent.id),
            # the beat sheets and any other seedable workspace files — NEVER
            # state.json (an agent's facts are its own), never the derived
            # agent.json, never persona.md (the row's system_prompt is it).
            workspace_files=self._capture_workspace_files(agent),
        )

        self.db.add(template)
        await self.db.flush()
        await self.db.refresh(template)

        logger.info(f"✅ Saved agent '{agent.name}' as template: {template.name} (id={template.id})")
        return template

    # ========================================================================
    # Tool Discovery Methods
    # ========================================================================

    async def get_agent_with_tools(self, agent_id: int) -> Optional[Dict[str, Any]]:
        """
        Get agent with their enabled tools.

        Args:
            agent_id: Agent ID

        Returns:
            Dictionary with agent data and tools list, or None if agent not found
        """
        agent = await self.get_by_id(agent_id)
        if not agent:
            return None

        tools = await self.get_enabled_tools_for_agent(str(agent.id))

        return {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "provider": agent.provider,
            "model": agent.model,
            "system_prompt": agent.system_prompt,
            "is_active": agent.is_active,
            "profile_image_url": agent.profile_image_url,
            "parameters": agent.parameters,
            "tools": tools,
        }

    async def get_enabled_tools_for_agent(self, agent_id: str, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Get all enabled tools for an agent with caching.

        Args:
            agent_id: Agent identifier (string)
            use_cache: Whether to use caching (default True)

        Returns:
            List of tool definitions formatted for LLM function calling
        """
        if use_cache:
            cached = self._get_cached_tools(agent_id)
            if cached is not None:
                return cached

        # Fetch from database via agent-tool service
        agent_tools = await self.agent_tool_service.list_agent_tools(
            agent_id, is_enabled=True
        )

        tool_definitions = []
        for agent_tool in agent_tools:
            if agent_tool.tool is None:
                continue
            tool_def = self._convert_to_llm_format(agent_tool.tool)
            tool_definitions.append(tool_def)

        # Cache the result
        if use_cache:
            self._set_cached_tools(agent_id, tool_definitions)

        return tool_definitions

    def _convert_to_llm_format(self, tool: "ToolSummary") -> Dict[str, Any]:
        """
        Convert a ToolResponse into the OpenAI function-calling format.

        Args:
            tool: ToolResponse schema object

        Returns:
            Dictionary in OpenAI function calling format
        """
        parameters = tool.arguments_schema if tool.arguments_schema else tool.config_schema

        return {
            "type": "function",
            "function": {
                "name": tool.slug,
                "description": tool.description,
                "parameters": parameters,
            },
            "x-cogitate-tool": {
                "id": tool.id,
                "icon": tool.icon,
                "color": tool.color,
                "category": tool.category.name if tool.category else None,
            },
        }

    def _get_cached_tools(self, agent_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get tools from cache if not expired.

        Args:
            agent_id: Agent identifier

        Returns:
            Cached tools list or None if not found/expired
        """
        if agent_id not in _tool_cache:
            return None

        cache_entry = _tool_cache[agent_id]
        now = datetime.now(timezone.utc)
        if now > cache_entry["expires_at"]:
            # Remove expired entry
            del _tool_cache[agent_id]
            return None

        return cast(list[dict[str, Any]] | None, cache_entry["tools"])

    def _set_cached_tools(self, agent_id: str, tools: List[Dict[str, Any]]) -> None:
        """
        Set tools in cache with TTL.

        Args:
            agent_id: Agent identifier
            tools: Tools list to cache
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=TOOL_CACHE_TTL_SECONDS)

        _tool_cache[agent_id] = {
            "tools": tools,
            "cached_at": now,
            "expires_at": expires_at,
        }

    def invalidate_tool_cache(self, agent_id: Optional[str] = None) -> None:
        """
        Invalidate tool cache for a specific agent or all agents.

        Args:
            agent_id: If provided, invalidate cache for this agent only.
                    If None, invalidate all cached tools.
        """
        if agent_id is None:
            _tool_cache.clear()
        elif agent_id in _tool_cache:
            del _tool_cache[agent_id]

