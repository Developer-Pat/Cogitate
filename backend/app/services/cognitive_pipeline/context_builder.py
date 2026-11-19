"""
Context Builder — pipeline component that assembles the execution context.

The Context Builder gathers information from the session, agent descriptor,
and memory store, then produces a ``Context`` object that the Executor
will use to drive the agent's response.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List

from .models import (
    AgentDescriptor,
    ComponentTrace,
    Context,
    MemoryDelta,
    Timer,
)
from .registry import Registry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class ContextBuilder(ABC):
    """Interface for context-building strategies."""

    @abstractmethod
    async def build(
        self,
        user_message: str,
        agent: AgentDescriptor,
        session_history: List[dict],
        memory_delta: MemoryDelta | None = None,
    ) -> Context:
        """Assemble the execution context.

        Args:
            user_message: The raw message from the user.
            agent: Descriptor of the agent being invoked.
            session_history: Previous turns in the session.
            memory_delta: Optional memory changes from a previous run.

        Returns:
            A fully populated ``Context`` object.
        """
        ...


# ---------------------------------------------------------------------------
# Default implementation
# ---------------------------------------------------------------------------

class DefaultContextBuilder(ContextBuilder):
    """Default context builder.

    Assembles a context from:
    - The agent's system prompt
    - Session history (last N turns)
    - The current user message
    - Any RAG results or tool outputs already available
    """

    def __init__(self, max_history_turns: int = 20) -> None:
        self.max_history_turns = max_history_turns

    async def build(
        self,
        user_message: str,
        agent: AgentDescriptor,
        session_history: List[dict],
        memory_delta: MemoryDelta | None = None,
    ) -> Context:
        history = session_history[-self.max_history_turns:] if session_history else []

        context = Context(
            user_message=user_message,
            system_prompt=agent.system_prompt,
            session_history=history,
            agent_name=agent.name,
            agent_description=agent.description,
            metadata={
                "agent_id": agent.id,
                "provider": agent.provider,
                "model": agent.model,
                "history_turns_used": len(history),
                "total_history_available": len(session_history),
            },
        )

        if memory_delta and memory_delta.summary:
            context.metadata["memory_summary"] = memory_delta.summary

        return context

class MinimalContextBuilder(ContextBuilder):
    """Minimal context builder.

    Only includes the current user message and system prompt.
    No session history, no RAG results. Useful for stateless queries
    where history would add noise or token cost.
    """

    async def build(
        self,
        user_message: str,
        agent: AgentDescriptor,
        session_history: List[dict],
        memory_delta: MemoryDelta | None = None,
    ) -> Context:
        context = Context(
            user_message=user_message,
            system_prompt=agent.system_prompt,
            session_history=[],  # intentionally empty
            agent_name=agent.name,
            agent_description=agent.description,
            metadata={
                "agent_id": agent.id,
                "provider": agent.provider,
                "model": agent.model,
                "history_turns_used": 0,
                "total_history_available": len(session_history),
                "strategy": "minimal",
            },
        )
        return context

class AugmentedContextBuilder(ContextBuilder):
    """Augmented context builder.

    Includes everything from DefaultContextBuilder plus RAG results,
    web search context, and tool results injected into the assembled context.
    Sets metadata flags so downstream components (Executor, ResponseFormatter)
    know augmented data is available.

    This is a foundation for RAG-enabled agents and research tasks.
    """

    def __init__(self, max_history_turns: int = 20) -> None:
        self.max_history_turns = max_history_turns

    async def build(
        self,
        user_message: str,
        agent: AgentDescriptor,
        session_history: List[dict],
        memory_delta: MemoryDelta | None = None,
    ) -> Context:
        history = session_history[-self.max_history_turns:] if session_history else []

        context = Context(
            user_message=user_message,
            system_prompt=(
                agent.system_prompt
                + "\n\n[Augmented mode enabled — RAG results, web search, "
                "and tool outputs may be available as additional context.]"
                if agent.system_prompt
                else ""
            ),
            session_history=history,
            agent_name=agent.name,
            agent_description=agent.description,
            metadata={
                "agent_id": agent.id,
                "provider": agent.provider,
                "model": agent.model,
                "history_turns_used": len(history),
                "total_history_available": len(session_history),
                "strategy": "augmented",
                "rag_enabled": True,
            },
        )

        if memory_delta and memory_delta.summary:
            context.metadata["memory_summary"] = memory_delta.summary
            context.system_prompt += (
                f"\n\n[Previous conversation summary: {memory_delta.summary}]"
            )

        return context


# ---------------------------------------------------------------------------
# Skill-aware context builder
# ---------------------------------------------------------------------------

class SkillAwareContextBuilder(ContextBuilder):
    """Context builder that injects skills into the system prompt.

    Skills are loaded from two locations:
    1. Global ``skills/{name}.skill.md`` directory (shareable)
    2. Per-agent ``agents/{agent.folder}/skills/{name}.skill.md`` (overrides)

    The ``agent.json`` ``skills`` field lists which skills to load.
    """

    def __init__(self, max_history_turns: int = 20):
        self.max_history_turns = max_history_turns
        self._skill_cache: dict[str, str] = {}

    def _load_skill(self, name: str, agent_folder: str | None = None) -> str | None:
        """Load a skill by name. Checks agent-local first, then global."""
        import os as _os
        # Check cache
        cache_key = f"{agent_folder or ''}:{name}"
        if cache_key in self._skill_cache:
            return self._skill_cache[cache_key]

        candidates = []

        # 1. Per-agent override
        if agent_folder:
            from app.core.config import Paths, get_settings
            agent_skills = str(Paths.from_settings(get_settings()).agents_dir / agent_folder / "skills")
            candidates.append(_os.path.join(agent_skills, f"{name}.skill.md"))

        # 2. Global skills directory
        from app.core.config import Paths, get_settings
        candidates.append(str(Paths.from_settings(get_settings()).skills_dir / f"{name}.skill.md"))

        for path in candidates:
            if _os.path.exists(path):
                try:
                    with open(path) as f:
                        content = f.read()
                    # Extract body after frontmatter
                    parts = content.split("---", 2)
                    body = parts[2].strip() if len(parts) >= 3 else content.strip()
                    self._skill_cache[cache_key] = body
                    return body
                except Exception:
                    continue
        return None

    async def build(
        self,
        user_message: str,
        agent: AgentDescriptor,
        session_history: List[dict],
        memory_delta: MemoryDelta | None = None,
    ) -> Context:
        # Start with default context assembly
        context, _ = await run_context_builder(
            builder=DefaultContextBuilder(max_history_turns=self.max_history_turns),
            user_message=user_message,
            agent=agent,
            session_history=session_history,
            memory_delta=memory_delta,
        )

        # Load and inject skills from agent.json if available
        skill_names = getattr(agent, 'skills', None)
        if not skill_names and hasattr(agent, 'folder') and agent.folder:
            # Try to load from agent.json
            import json as _json, os as _os
            from app.core.config import Paths, get_settings
            agent_json_path = _os.path.join(
                str(Paths.from_settings(get_settings()).agents_dir / agent.folder / "agent.json")
            )
            if _os.path.exists(agent_json_path):
                try:
                    with open(agent_json_path) as f:
                        agent_data = _json.load(f)
                    skill_names = agent_data.get("skills", [])
                except Exception:
                    pass

        if skill_names:
            agent_folder = getattr(agent, 'folder', None)
            loaded = []
            for name in skill_names:
                body = self._load_skill(name, agent_folder)
                if body:
                    loaded.append(f"--- {name} ---\n{body}")
                    context.metadata[f"skill:{name}"] = "loaded"
                else:
                    context.metadata[f"skill:{name}"] = "not_found"

            if loaded:
                skills_text = "\n\n".join(loaded)
                context.system_prompt += (
                    f"\n\n[Skills]\n{skills_text}\n[/Skills]"
                )

        context.metadata["strategy"] = "skill_aware"
        return context


# ---------------------------------------------------------------------------
# Registry wrapper
# ---------------------------------------------------------------------------

class ContextBuilderRegistry:
    """Typed registry wrapper for ContextBuilder implementations."""

    def __init__(self) -> None:
        self._registry = Registry[ContextBuilder]()

    def register(self, name: str, builder: ContextBuilder, overwrite: bool = False) -> None:
        self._registry.register(name, builder, overwrite=overwrite)

    def get(self, name: str) -> ContextBuilder:
        return self._registry.get(name)

    def list(self) -> List[str]:
        return self._registry.list()

    def __contains__(self, name: str) -> bool:
        return name in self._registry


def create_default_registry() -> ContextBuilderRegistry:
    """Create a registry pre-populated with the default implementation."""
    registry = ContextBuilderRegistry()
    registry.register("default", DefaultContextBuilder())
    registry.register("minimal", MinimalContextBuilder())
    registry.register("augmented", AugmentedContextBuilder())
    registry.register("skill_aware", SkillAwareContextBuilder())
    return registry


# ---------------------------------------------------------------------------
# Convenience: run with tracing
# ---------------------------------------------------------------------------

async def run_context_builder(
    builder: ContextBuilder,
    user_message: str,
    agent: AgentDescriptor,
    session_history: List[dict],
    memory_delta: MemoryDelta | None = None,
) -> tuple[Context, ComponentTrace]:
    """Execute a context builder and return (result, trace)."""
    trace = ComponentTrace(strategy=_strategy_name(builder))
    timer = Timer()

    try:
        with timer:
            context = await builder.build(
                user_message=user_message,
                agent=agent,
                session_history=session_history,
                memory_delta=memory_delta,
            )
        trace.duration_ms = timer.duration_ms
        trace.tokens_used = _estimate_context_tokens(context)
        trace.metadata = {
            "history_turns": len(context.session_history),
            "rag_sources": len(context.rag_results),
            "tool_results": len(context.tool_results),
        }
    except Exception as exc:
        trace.duration_ms = timer.duration_ms
        trace.error = str(exc)
        logger.exception("ContextBuilder failed: %s", exc)
        raise

    return context, trace


def _strategy_name(builder: ContextBuilder) -> str:
    return type(builder).__name__.replace("ContextBuilder", "").lower() or "custom"


def _estimate_context_tokens(context: Context) -> int:
    """Rough token estimate for the assembled context."""
    total = len(context.user_message.split())
    total += len(context.system_prompt.split())
    for turn in context.session_history:
        total += len(str(turn).split())
    total += sum(len(r.split()) for r in context.rag_results)
    return total
