"""
Memory Manager — pipeline component that manages conversation memory.

The Memory Manager decides what to retain from each interaction turn.
It supports different strategies: sliding window, LLM summarization,
key-value storage, etc. The default implementation uses a sliding window
with optional summarization when the window is exceeded.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, cast

from .models import (
    AgentDescriptor,
    ComponentTrace,
    Context,
    MemoryDelta,
    Timer,
)
from .registry import Registry

if TYPE_CHECKING:  # the chain's type, for the annotations only — the call imports it where it is used
    from app.domain.providers.capabilities import ServiceCandidate

logger = logging.getLogger(__name__)

# Which capability supplies this manager's LLM calls — the turn summarization in `remember` and the
# fact extraction beside it. The constant lives HERE because this module is the CONSUMER (the same
# shape as `SUMMARY_CAPABILITY_KEY` in the conversation compactor), so a caller imports it rather
# than retyping the string.
MEMORY_CAPABILITY_KEY = "memory"


# ---------------------------------------------------------------------------
# The `memory` capability's chain — one attempt, and its one walk
# ---------------------------------------------------------------------------


async def _ask_service(
    candidate: ServiceCandidate,
    messages: List[Dict[str, Any]],
    max_tokens: int,
) -> str:
    """ONE attempt: ask ``candidate``'s service for ``messages``.

    Raises on failure rather than papering over it — the chain's NEXT candidate is the remedy, and the
    shared walk logs this attempt (the service, its model, which attempt it was).
    """
    from litellm import acompletion

    from app.domain.providers.litellm_route import api_base_for, litellm_model_string

    model = candidate.model
    if not model:
        raise ValueError(f"the '{candidate.describe()}' service names no model for memory work")

    # THE ROUTE (2026-10-12, `litellm_route`): the handler comes from the candidate's provider_type —
    # hand-rolling `{provider}/{model}` produced `ollama_cloud/<m>` and `llama/<m>`, which litellm
    # REJECTS ("LLM Provider NOT provided", measured). A local row also needs its address, or the
    # adapter would dial litellm's own default rather than the row's server.
    litellm_model = litellm_model_string(candidate.provider or "", model, candidate.provider_type)
    api_base = candidate.endpoint
    kwargs: dict = {
        "model": litellm_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }
    if api_base:
        kwargs["api_base"] = api_base_for(litellm_model, api_base)
        # The keyless local servers still need a NON-EMPTY key for litellm's openai adapter
        # (the Bonsai test, 2026-09-01 — the 'Missing credentials' error).
        kwargs["api_key"] = "local-llama"

    response = await acompletion(**kwargs)
    return response.choices[0].message.content or ""


async def _via_memory_chain(
    candidates: Sequence[ServiceCandidate],
    *,
    messages: List[Dict[str, Any]],
    max_tokens: int,
) -> Optional[str]:
    """Walk the `memory` capability's RESOLVED chain for ONE completion.

    The chain is the CALLER's answer, carried on the turn's ``Context.capability_chains``: this module
    holds no database session (the manager is a registered SINGLETON built at import, and logs usage
    over a raw sqlite3 connection), so it cannot resolve one — and per-turn state must not be written
    onto the instance, because two concurrent turns share it.

    ``None`` — with the reason said out loud — when nothing was configured: **no chain means the call
    is SKIPPED**, never aimed at a service named in code. That is the difference between "not
    configured" and a second answer, and it is why the literal pair that used to live here (`ollama` /
    `llama3.2`) left the `memory` capability a capability that **nothing consumed** (the
    service-capability arc's phase-8 audit).
    """
    if not candidates:
        logger.warning(
            "memory: the '%s' capability resolved no service — skipping this call (nothing is "
            "configured, and no service is named in code)",
            MEMORY_CAPABILITY_KEY,
        )
        return None

    from app.domain.providers.capabilities import attempt_chain  # the resolver's layer, on demand

    outcome = await attempt_chain(
        list(candidates),
        call=lambda candidate: _ask_service(candidate, messages, max_tokens),
        capability=MEMORY_CAPABILITY_KEY,
    )
    # `AttemptOutcome.response` is `Any` (the chain serves several kinds); here the caller's `call`
    # is the only thing that produced it, and it returns a completion's text.
    return cast(str, outcome.response)


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class MemoryManager(ABC):
    """Interface for memory management strategies."""

    # Shared attributes — the chat router sets these on any manager
    # instance (per-agent DB path, deep-agent flag, summarization
    # settings). Concrete managers override __init__ to set them.
    _db_path: Optional[str] = None
    _is_deep: bool = False
    _summarization_enabled: bool = False
    summarization_threshold: int = 50

    def _get_conn(self):
        """Open a SQLite connection to this manager's DB (KV-store only)."""
        raise NotImplementedError("_get_conn is implemented by KVStoreMemoryManager")

    def _init_db(self) -> None:
        """Create the cognitive_memory table (KV-store only)."""
        raise NotImplementedError("_init_db is implemented by KVStoreMemoryManager")

    @abstractmethod
    async def remember(
        self,
        context: Context,
        response: str,
        agent: AgentDescriptor,
        session_id: str | None = None,
    ) -> MemoryDelta:
        """Process and store the current turn in memory.

        Args:
            context: The context used for this turn.
            response: The raw response from the executor.
            agent: Descriptor of the agent being invoked.

        Returns:
            A ``MemoryDelta`` describing what changed in memory.
        """
        ...

    @abstractmethod
    async def recall(
        self,
        agent: AgentDescriptor,
        session_id: str | None = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve stored memories for the given agent/session.

        Args:
            agent: Descriptor of the agent.
            session_id: Optional session identifier.

        Returns:
            A list of memory entries (dicts with role, content, timestamp).
        """
        ...

    async def recall_summaries(
        self,
        agent: AgentDescriptor,
        max_count: int = 5,
    ) -> list[str]:
        """Retrieve summaries from ALL past sessions for cross-session context."""
        return []


    async def recall_facts(
        self,
        agent: AgentDescriptor,
    ) -> list[str]:
        """Retrieve stored facts about the user."""
        import json as _json
        facts_key = f"agent_{agent.id}:facts"
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT value FROM cognitive_memory WHERE key = ?",
                (facts_key,),
            )
            row = cursor.fetchone()
            if row:
                facts = _json.loads(row["value"])
                return facts if isinstance(facts, list) else []
            return []
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Default implementation
# ---------------------------------------------------------------------------


class DefaultMemoryManager(MemoryManager):
    """Default memory manager using an in-memory sliding window.

    Stores the last N turns in memory. When the limit is exceeded, the
    oldest entries are evicted. No LLM summarization is performed.
    """

    def __init__(self, max_turns: int = 50) -> None:
        self.max_turns = max_turns
        self._store: Dict[str, List[Dict[str, Any]]] = {}

    def _store_key(self, agent: AgentDescriptor, session_id: str | None) -> str:
        return f"{agent.id}:{session_id or 'default'}"

    async def remember(
        self,
        context: Context,
        response: str,
        agent: AgentDescriptor,
        session_id: str | None = None,
    ) -> MemoryDelta:
        key = self._store_key(agent, None)
        if key not in self._store:
            self._store[key] = []

        entry: Dict[str, Any] = {
            "role": "user",
            "content": context.user_message,
            "timestamp": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
        }
        self._store[key].append(entry)

        entry = {
            "role": "assistant",
            "content": response,
            "timestamp": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
        }
        self._store[key].append(entry)

        evicted: List[str] = []
        compaction = False
        if len(self._store[key]) > self.max_turns * 2:
            excess = len(self._store[key]) - self.max_turns * 2
            self._store[key] = self._store[key][excess:]
            evicted = [f"turn_{i}" for i in range(excess // 2)]
            compaction = True

        return MemoryDelta(
            stored_keys=[f"turn_{len(self._store[key]) // 2}"],
            evicted_keys=evicted,
            compaction_triggered=compaction,
        )

    async def recall(
        self,
        agent: AgentDescriptor,
        session_id: str | None = None,
    ) -> List[Dict[str, Any]]:
        key = self._store_key(agent, session_id)
        return self._store.get(key, [])

class NoopMemoryManager(MemoryManager):
    """No-op memory manager — stateless.

    Stores nothing, recalls nothing. Every conversation starts fresh.
    Used by the "stateless" memory profile.
    """

    async def remember(
        self,
        context: Context,
        response: str,
        agent: AgentDescriptor,
        session_id: str | None = None,
    ) -> MemoryDelta:
        return MemoryDelta(
            stored_keys=[],
            evicted_keys=[],
            compaction_triggered=False,
        )

    async def recall(
        self,
        agent: AgentDescriptor,
        session_id: str | None = None,
    ) -> List[Dict[str, Any]]:
        return []


class KVStoreMemoryManager(MemoryManager):
    """Key-value store memory manager — persistent across restarts.

    Stores conversation memory as JSON blobs in a dedicated SQLite
    database (``data/cognitive_memory.db``).  Each agent+session pair
    gets its own key.

    Unlike DefaultMemoryManager (in-memory, lost on restart), this
    manager persists data to disk so memory survives restarts.
    """

    def __init__(
        self,
        db_path: str | None = None,
        max_turns: int = 100,
        summarization_threshold: int = 50,
    ) -> None:
        self.max_turns = max_turns
        self.summarization_threshold = summarization_threshold
        if db_path is None:
            import os as _os
            from app.core.config import Paths, get_settings
            _base = Paths.from_settings(get_settings()).data_dir
            _os.makedirs(_base, exist_ok=True)
            db_path = _os.path.join(_base, "cognitive_memory.db")
            self._is_deep = False
        else:
            self._is_deep = True
            import os as _os
            _os.makedirs(_os.path.dirname(db_path), exist_ok=True)
        self._db_path = db_path
        self._init_db()

    def _get_conn(self):
        import sqlite3
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS cognitive_memory ("
                "key TEXT PRIMARY KEY, "
                "value TEXT NOT NULL, "
                "turn_count INTEGER NOT NULL DEFAULT 0, "
                "created_at TEXT NOT NULL DEFAULT (datetime('now')), "
                "updated_at TEXT NOT NULL DEFAULT (datetime('now'))"
                ")"
            )
            conn.commit()
        finally:
            conn.close()

    def _store_key(self, agent: AgentDescriptor, session_id: str | None) -> str:
        return f"agent_{agent.id}:{session_id or 'default'}"

    async def remember(
        self,
        context: Context,
        response: str,
        agent: AgentDescriptor,
        session_id: str | None = None,
    ) -> MemoryDelta:
        import json as _json
        key = self._store_key(agent, session_id)
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT value, turn_count FROM cognitive_memory WHERE key = ?", (key,)
            )
            row = cursor.fetchone()
            if row:
                turns = _json.loads(row["value"])
                turn_count = row["turn_count"]
            else:
                turns = []
                turn_count = 0

            import datetime as _dt
            turns.append({
                "role": "user",
                "content": context.user_message,
                "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            })
            turns.append({
                "role": "assistant",
                "content": response,
                "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            })
            turn_count += 1

            evicted = []
            compaction = False
            if len(turns) > self.max_turns * 2:
                excess = len(turns) - self.max_turns * 2
                turns = turns[excess:]
                evicted = [f"turn_{i}" for i in range(excess // 2)]
                compaction = True

            summary = None
            if getattr(self, '_summarization_enabled', False) and turn_count >= self.summarization_threshold:
                # The summarizer's service is the `memory` capability's chain, carried on THIS turn's
                # context by the caller that holds the session (see `_via_memory_chain`). The literal
                # pair `ollama`/`llama3.2` that used to be read here is gone.
                candidates = context.capability_chains.get(MEMORY_CAPABILITY_KEY, ())
                try:
                    text = "\n".join(
                        f"{t['role']}: {t['content']}" for t in turns
                    )
                    summary = await _via_memory_chain(
                        candidates,
                        messages=[
                            {"role": "system", "content": "Summarize this conversation concisely. Preserve key facts, decisions, and the user's preferences. Output a single paragraph."},
                            {"role": "user", "content": text},
                        ],
                        max_tokens=300,
                    )
                except Exception as exc:
                    # The chain is EXHAUSTED — every attempt's failure is already logged by the shared
                    # walk, and this says the whole chain is out. Note the last resort below asks no
                    # service at all: it is the turn count, not a name moved from code to config.
                    logger.error(
                        "memory: no service in the '%s' chain answered (%s) — storing the turn count instead",
                        MEMORY_CAPABILITY_KEY,
                        exc,
                    )
                if not summary:
                    summary = f"Conversation reached {turn_count} turns"
                # Store the summary separately for cross-session recall
                if self._is_deep:
                    summary_key = f"summary:{session_id or 'default'}"
                else:
                    summary_key = f"agent_{agent.id}:summary:{session_id or 'default'}"
                try:
                    import json as _json2
                    conn.execute(
                        "INSERT OR REPLACE INTO cognitive_memory (key, value, turn_count, updated_at) "
                        "VALUES (?, ?, ?, datetime('now'))",
                        (summary_key, _json2.dumps({"summary": summary, "turn_count": turn_count}), turn_count),
                    )
                    conn.commit()
                except Exception:
                    pass  # Summary storage is best-effort
                # Also extract and store user facts
                try:
                    turns_for_facts = turns[-10:] if len(turns) > 10 else turns
                    await self.extract_facts(agent, turns_for_facts, session_id, candidates)
                except Exception as exc:
                    logger.warning("memory: fact extraction failed (%s) — best-effort", exc)
                compaction = True

            conn.execute(
                "INSERT OR REPLACE INTO cognitive_memory (key, value, turn_count, updated_at) "
                "VALUES (?, ?, ?, datetime('now'))",
                (key, _json.dumps(turns), turn_count),
            )
            conn.commit()

            return MemoryDelta(
                stored_keys=[key],
                evicted_keys=evicted,
                compaction_triggered=compaction,
                summary=summary,
            )
        finally:
            conn.close()

    async def recall(
        self,
        agent: AgentDescriptor,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        import json as _json
        key = self._store_key(agent, session_id)
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT value FROM cognitive_memory WHERE key = ?", (key,)
            )
            row = cursor.fetchone()
            if row:
                _data = _json.loads(row["value"])
                return _data if isinstance(_data, list) else []
            return []
        finally:
            conn.close()


    async def recall_summaries(
        self,
        agent: AgentDescriptor,
        max_count: int = 5,
    ) -> list[str]:
        """Retrieve LLM-generated summaries from ALL past sessions."""
        if self._is_deep:
            pattern = "summary:%"
        else:
            pattern = f"agent_{agent.id}:summary:%"
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT value FROM cognitive_memory WHERE key LIKE ? ORDER BY updated_at DESC",
                (pattern,),
            )
            import json as _json
            summaries: list[str] = []
            for row in cursor.fetchall():
                try:
                    data = _json.loads(row["value"])
                    if isinstance(data, dict) and "summary" in data:
                        summaries.append(data["summary"])
                except (_json.JSONDecodeError, TypeError, KeyError):
                    continue
            return summaries[:max_count]
        finally:
            conn.close()

    async def extract_facts(
        self,
        agent: AgentDescriptor,
        turns: list[dict],
        session_id: str | None = None,
        candidates: Sequence[ServiceCandidate] = (),
    ) -> None:
        """Extract user facts from conversation turns and store them.

        ``candidates`` is the ``memory`` capability's RESOLVED chain — supplied by whoever HOLDS the
        capability reading (``remember`` takes it off the turn's context). **No chain = no call**: the
        extraction SKIPS and the reason is logged, rather than aiming at a service named in code.
        """
        try:
            import json as _json
            text = "\n".join(f'{t["role"]}: {t["content"]}' for t in turns[-10:])
            content = await _via_memory_chain(
                candidates,
                messages=[{
                    "role": "system",
                    "content": (
                        "Extract facts about the user from this conversation. "
                        "Return ONLY a JSON array of strings, each a clear standalone fact. "
                        "Example: ['User is a Python developer.', 'User prefers concise answers.'] "
                        "If no facts, return []."
                    ),
                }, {
                    "role": "user",
                    "content": text,
                }],
                max_tokens=500,
            )
            if not content:
                return  # nothing was configured (or the service answered emptily) — said out loud above
            new_facts = _json.loads(content)
            if not isinstance(new_facts, list):
                return
            existing = await self.recall_facts(agent)
            merged = list(dict.fromkeys(existing + new_facts))
            facts_key = f"agent_{agent.id}:facts"
            conn = self._get_conn()
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO cognitive_memory (key, value, turn_count, updated_at) "
                    "VALUES (?, ?, ?, datetime('now'))",
                    (facts_key, _json.dumps(merged), len(merged)),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            # Best-effort by design — a turn must not die on fact extraction. Not SILENT any more:
            # the failure that used to vanish here is what let a dead local service go unnoticed.
            logger.warning("memory: fact extraction failed (%s) — best-effort", exc)

    async def recall_facts(
        self,
        agent: AgentDescriptor,
    ) -> list[str]:
        """Retrieve stored facts about the user."""
        import json as _json
        facts_key = f"agent_{agent.id}:facts"
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT value FROM cognitive_memory WHERE key = ?",
                (facts_key,),
            )
            row = cursor.fetchone()
            if row:
                facts = _json.loads(row["value"])
                return facts if isinstance(facts, list) else []
            return []
        finally:
            conn.close()

    async def clear_session(self, agent: AgentDescriptor, session_id: str) -> None:
        """Delete memory for a single session."""
        key = self._store_key(agent, session_id)
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM cognitive_memory WHERE key = ?", (key,))
            conn.commit()
        finally:
            conn.close()

    async def clear_agent(self, agent: AgentDescriptor) -> None:
        """Delete ALL memory for an agent (all sessions)."""
        pattern = f"agent_{agent.id}:%"
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM cognitive_memory WHERE key LIKE ?", (pattern,))
            conn.commit()
        finally:
            conn.close()

    async def clear_all(self) -> None:
        """Delete ALL memory for all agents."""
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM cognitive_memory")
            conn.commit()
        finally:
            conn.close()

    async def prune_old(self, max_days: int = 30) -> int:
        """Delete entries older than N days. Returns count of deleted rows."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM cognitive_memory WHERE updated_at < datetime('now', ?)",
                (f"-{max_days} days",),
            )
            conn.commit()
            return int(cursor.rowcount or 0)
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Registry wrapper
# ---------------------------------------------------------------------------

class MemoryManagerRegistry:
    """Typed registry wrapper for MemoryManager implementations."""

    def __init__(self) -> None:
        self._registry = Registry[MemoryManager]()

    def register(self, name: str, manager: MemoryManager, overwrite: bool = False) -> None:
        self._registry.register(name, manager, overwrite=overwrite)

    def get(self, name: str) -> MemoryManager:
        return self._registry.get(name)

    def list(self) -> List[str]:
        return self._registry.list()

    def __contains__(self, name: str) -> bool:
        return name in self._registry


def create_default_registry() -> MemoryManagerRegistry:
    """Create a registry pre-populated with the default implementation."""
    registry = MemoryManagerRegistry()
    registry.register("default", DefaultMemoryManager())
    registry.register("noop", NoopMemoryManager())
    registry.register("kv_store", KVStoreMemoryManager())
    return registry


# ---------------------------------------------------------------------------
# Convenience: run with tracing
# ---------------------------------------------------------------------------

async def run_memory_manager(
    manager: MemoryManager,
    context: Context,
    response: str,
    agent: AgentDescriptor,
    session_id: str | None = None,
) -> tuple[MemoryDelta, ComponentTrace]:
    """Run memory management and return (delta, trace)."""
    trace = ComponentTrace(strategy=_strategy_name(manager))
    timer = Timer()

    try:
        with timer:
            delta = await manager.remember(
                context=context,
                response=response,
                agent=agent,
                session_id=session_id,
            )
        trace.duration_ms = timer.duration_ms
        trace.tokens_used = len(response.split()) if delta.summary else 0
        trace.metadata = {
            "stored_keys": delta.stored_keys,
            "evicted_keys": delta.evicted_keys,
            "compaction_triggered": delta.compaction_triggered,
            "has_summary": delta.summary is not None,
        }
    except Exception as exc:
        trace.duration_ms = timer.duration_ms
        trace.error = str(exc)
        logger.exception("MemoryManager failed: %s", exc)
        raise

    return delta, trace


def _strategy_name(manager: MemoryManager) -> str:
    return type(manager).__name__.replace("MemoryManager", "").lower() or "custom"
