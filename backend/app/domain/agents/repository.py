"""Agent repository — the storage seam (agent-lifecycle Phase A).

The fork boundary: routers + lifecycle flows speak THIS contract;
the storage implementation swaps behind it. Today: SQLite row +
disk workspace. The industrial fork writes DbAgentRepository and
flips the factory — nothing else changes (study 02: the fork
vision).

This is the Repository pattern (the software-patterns
documentation todo will name it).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from pathlib import Path

from app.infrastructure.database.models import Agent, ChatSession
# the full model chain (the Tool→TeamTool→Collection mapper cycle
# requires importing the whole chain, not isolated models)
from app.domain.tools.models import AgentTool, AgentToolGrant
from app.domain.collections.models import CollectionItem

# the UUID-column form note: raw rows store hyphen-less ids; the
# ORM models are used here so the mapping is handled by SQLAlchemy
AgentToolGrantRow = AgentToolGrant
CollectionItemRow = CollectionItem
ChatSessionRow = ChatSession
AgentToolLink = AgentTool



class AgentRepository(ABC):
    """The lifecycle contract — the seam every agent flow writes through.

    Read side: resolve_agent (the white pages) + select_agents
    (the yellow pages) — built by the ARM project.
    Write side: create_agent, duplicate_agent (the clone: a scoped
    instance of a character) + delete_agent / hard_delete_agent
    (Phases B/C).
    Workspace: agent_workspace — the folder lookup by column, plus
    provision_workspace for a row that has none.
    """

    @abstractmethod
    async def create_agent(self, data: Dict[str, Any]) -> Agent:
        """Create an agent (row + workspace scaffold — Phase B)."""

    @abstractmethod
    async def provision_workspace(self, agent_id: int) -> Optional[Agent]:
        """Attach a workspace to an EXISTING agent (the shallow-agent
        provisioning, 2026-09-02): assign the stable key when the row
        has none + scaffold the folder. Idempotent — an agent with a
        workspace returns untouched."""

    @abstractmethod
    async def duplicate_agent(self, agent_id: int) -> Optional[Agent]:
        """Create a scoped INSTANCE of an agent (the clone ruling, 2026-10-12):
        the character's configuration, the instance's own workspace and state.
        None when the source does not exist."""

    @abstractmethod
    async def delete_agent(self, agent_id: int) -> Dict[str, Any]:
        """Delete an agent: BOM + soft-delete + archive (Phase C)."""

    @abstractmethod
    async def hard_delete_agent(self, agent_id: int) -> Dict[str, Any]:
        """Permanently scrub an agent: the row + every reference +
        the workspace + memory. IRREVERSIBLE — the caller must gate."""

    @abstractmethod
    async def reset_agent_memory(self, agent_id: int) -> Dict[str, Any]:
        """Reset an agent's learned state: clear the cognitive-memory
        DB + the chat sessions. The agent survives — it forgets."""

    @abstractmethod
    async def resolve_agent(self, name: str) -> Agent:
        """Resolve a unique name to exactly one agent (strict)."""

    @abstractmethod
    async def agent_workspace(self, agent_id: int) -> Optional[str]:
        """The agent's workspace folder path (by column, no scan)."""

    @abstractmethod
    async def select_agents(
        self, criteria: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Filter + rank the pool; return ARM cards."""

    @abstractmethod
    async def list_deleted(self) -> List[Dict[str, Any]]:
        """Soft-deleted agents + their archive paths (the restore
        view's data — recovery is DB-discoverable)."""

    @abstractmethod
    async def restore_agent(self, agent_id: int) -> Agent:
        """Restore a soft-deleted agent: re-import its archived
        workspace, clear the delete markers. ADDITIVE — explicit,
        never automatic."""


class DiskAgentRepository(AgentRepository):
    """SQLite row + disk workspace — the R&D implementation."""

    def __init__(self, db) -> None:
        self.db = db
        from app.domain.agents.services import AgentService
        from app.domain.agents.selection_service import select_agents
        self._svc = AgentService(db)
        self._select = select_agents

    async def create_agent(self, data: Dict[str, Any]) -> Agent:
        """Create the agent: row first, then the workspace scaffold.

        The row is the source of truth (the DB-first lens); the
        folder + derived agent.json manifest it. On a folder-write
        failure the row rolls back — no half-created agents.
        """
        from app.domain.agents.schemas import AgentCreate
        from app.domain.agents.workspace import (
            make_workspace_key, scaffold,
        )
        from app.infrastructure.database.models import Agent as AgentModel
        from sqlalchemy import select

        # stable, unique workspace key (folder-safe, rename-proof)
        existing = set(
            (await self.db.execute(
                select(AgentModel.workspace_key).where(
                    AgentModel.workspace_key.is_not(None)
                )
            )).scalars().all()
        )
        key = make_workspace_key(str(data.get("name", "agent")), existing)

        # THE FACE (2026-09-10): agents are characters — a new one gets its
        # own face rather than arriving blank. The template apply has its
        # own allocation; this covers the plain create.
        if not data.get("profile_image_url"):
            try:
                from app.domain.assets.faces import pick_agent_face
                from sqlalchemy import select
                used = (await self.db.execute(
                    select(AgentModel.profile_image_url).where(
                        AgentModel.profile_image_url.is_not(None)
                    )
                )).scalars().all()
                data["profile_image_url"] = pick_agent_face(used)
            except Exception as e:  # noqa: BLE001 — a face must not block a create
                import logging
                logging.getLogger(__name__).warning("face allocation skipped: %s", e)

        agent = await self._svc.create(AgentCreate(**data))
        try:
            agent.workspace_key = key
            await self.db.flush()
            # refresh BEFORE scaffolding: created_at etc. are
            # server-side defaults — a sync read would trigger
            # lazy IO on the async session (MissingGreenlet)
            await self.db.refresh(agent)
            scaffold(agent)
            await self.db.commit()
        except Exception:
            # roll back the row — no half-created agents (the insert
            # was never committed, so rollback removes it entirely)
            await self.db.rollback()
            raise
        await self.db.refresh(agent)
        return agent

    async def provision_workspace(self, agent_id: int) -> Optional[Agent]:
        """The disk implementation: row-first (the key is set + the
        scaffold derives agent.json from the row — the disk manifests
        the row, never a second source of truth). Idempotent."""
        from sqlalchemy import select
        from app.infrastructure.database.models import Agent as AgentModel
        from app.domain.agents.workspace import provision

        agent = await self._svc.get_by_id(agent_id)
        if agent is None:
            return None
        if agent.workspace_key:
            # already provisioned — ensure the folder exists (the
            # scaffold is idempotent; an archived-then-restored agent
            # may have the key but a missing folder)
            from app.domain.agents.workspace import scaffold as _scaffold
            ws = await self.agent_workspace(agent_id)
            if ws is None or not Path(ws).exists():
                _scaffold(agent)
                await self.db.flush()
                await self.db.commit()
            return agent

        # the stable key: unique against every provisioned agent
        existing = set(
            (await self.db.execute(
                select(AgentModel.workspace_key).where(
                    AgentModel.workspace_key.is_not(None)
                )
            )).scalars().all()
        )
        try:
            provision(agent, existing)
            await self.db.flush()
            await self.db.refresh(agent)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
        await self.db.refresh(agent)
        return agent

    async def duplicate_agent(self, agent_id: int) -> Optional[Agent]:
        """The scoped INSTANCE of a character (the 2026-10-12 ruling).

        `clone_character` decides what travels (everything describing the
        character) and what is fresh (the instance's own identity and state);
        the row and folder then go through `create_agent`, so the copy gets a
        minted key, the PARENT's face, the scaffold's rollback, and a folder
        derived from its own row. The tool surface is rows in `agent_kits`
        rather than a create field, so the source's kits are copied here.
        Returns None when the source does not exist.
        """
        from sqlalchemy import select

        from app.domain.agent_kits.service import AgentKitService
        from app.domain.agents.clone import clone_character
        from app.infrastructure.database.models import Agent as AgentModel

        source = await self._svc.get_by_id(agent_id)
        if source is None:
            return None

        # every name counts, soft-deleted rows included: the name ban matches on
        # the name alone, so a marker is only free when no row holds it
        names = (await self.db.execute(select(AgentModel.name))).scalars().all()
        payload = clone_character(source, names)
        agent = await self.create_agent(payload.model_dump())

        # the tool surface, copied kit by kit (attach is idempotent and refuses
        # anything that is not a tool-typed collection)
        try:
            kits = AgentKitService(self.db)
            for kit in await kits.kits_for_agent(agent_id):
                await kits.attach(agent.id, kit.id)
            await self.db.commit()
        except Exception as exc:
            # the instance exists and is usable; its kits are recoverable by hand
            await self.db.rollback()
            logger.error("duplicate_agent: kit copy failed for %s: %s", agent.name, exc)

        await self.db.refresh(agent)
        return agent

    async def delete_agent(self, agent_id: int) -> Dict[str, Any]:
        """Delete an agent: disclose the BOM, MOVE the workspace to the trash,
        soft-delete the row, keep history.

        Returns the result report: what was removed + where on the shelf it
        landed (recovery is discoverable — the trash page, and `GET /agents/deleted`,
        both read it).

        Raises ValueError for built-in agents (protected, 403).
        """
        from datetime import datetime, timezone

        from app.domain.agents import trash as agent_trash
        from sqlalchemy import delete as sa_delete
        from pathlib import Path

        agent = await self._svc.get_by_id(agent_id)
        if agent is None:
            return {"deleted": False, "agent_id": agent_id,
                    "reason": "not found"}
        if getattr(agent, "is_builtin", False):
            raise ValueError(
                f"Cannot delete built-in agent '{agent.name}' — "
                f"built-in agents are protected from deletion."
            )

        # 1. the BOM — gather the full footprint
        agent_id_s = str(agent_id)
        tool_links = (await self.db.execute(
            sa_delete(AgentToolLink).where(AgentToolLink.agent_id == agent_id_s)
        )).rowcount
        grants = (await self.db.execute(
            sa_delete(AgentToolGrantRow).where(
                AgentToolGrantRow.agent_id == agent_id_s
            )
        )).rowcount
        collections = (await self.db.execute(
            sa_delete(CollectionItemRow).where(
                CollectionItemRow.entity_id == agent_id_s,
                CollectionItemRow.entity_type == "agent",
            )
        )).rowcount
        sessions = (await self.db.execute(
            sa_delete(ChatSessionRow).where(
                ChatSessionRow.agent_id == agent_id
            )
        )).rowcount
        bom = {
            "tool_links": tool_links,
            "grants": grants,
            "collections": collections,
            "chat_sessions": sessions,
        }

        # 2. move the workspace onto the trash's AGENTS SHELF — a MOVE, never a
        #    removal. The shelf is a surface (a page, an API, Exa), which is
        #    what makes a deleted agent FINDABLE instead of merely recoverable
        #    by whoever still remembers its row.
        archived_path = None
        ws_path = await self.agent_workspace(agent_id)
        ws = Path(ws_path) if ws_path is not None else None
        if ws is not None and ws.exists():
            target = agent_trash.move_to_shelf(ws, agent.workspace_key or ws.name)
            archived_path = str(target)

        # 3. soft-delete the row (history KEPT — the row survives)
        agent.deleted_at = datetime.now(timezone.utc)
        agent.archived_path = archived_path
        agent.is_active = False
        await self.db.flush()
        await self.db.commit()

        return {
            "deleted": True,
            "agent_id": agent_id,
            "agent_name": agent.name,
            "bom": bom,
            "archived_path": archived_path,
        }

    async def hard_delete_agent(self, agent_id: int) -> Dict[str, Any]:
        """Permanently scrub an agent from the system.

        The IRREVERSIBLE delete: every reference the PURGE INVENTORY claims
        (`app.domain.agents.purge` — checked against the schema, so a new table
        naming agents cannot quietly outlive them), the workspace (shelved or
        live) and the cognitive-memory file. Nothing is moved. The caller must
        gate this (fix-mode grant + explicit confirmation) — nothing restores it.

        Returns the scrub report (the BOM: what was removed).
        """
        import shutil

        from app.domain.agents.purge import scrub_agent

        agent = await self._svc.get_by_id(agent_id)
        if agent is None:
            return {"deleted": False, "agent_id": agent_id, "reason": "not found"}
        name = agent.name

        # 1. the BOM — every reference, from the inventory (children first)
        bom = await scrub_agent(self.db, agent_id)

        # 2. the workspace — the SHELVED path OR the live dir, removed
        removed_workspace = None
        ws_target = None
        if agent.archived_path:
            ws_target = Path(agent.archived_path)
        elif agent.workspace_key:
            from app.domain.agents.workspace import AGENTS_ROOT
            ws_target = AGENTS_ROOT / agent.workspace_key
        if ws_target is not None and ws_target.exists():
            shutil.rmtree(str(ws_target), ignore_errors=True)
            removed_workspace = str(ws_target)

        # 3. the cognitive-memory file (the per-agent memory store)
        removed_memory = None
        if agent.workspace_key:
            from app.core.config import Paths, get_settings
            mem = Paths.from_settings(get_settings()).agents_dir / agent.workspace_key / "cognitive_memory.db"
            if mem.exists():
                mem.unlink(missing_ok=True)
                removed_memory = str(mem)

        # 4. the row itself
        await self.db.delete(agent)
        await self.db.flush()
        await self.db.commit()

        return {
            "deleted": True,
            "agent_id": agent_id,
            "agent_name": name,
            "bom": bom,
            "removed_workspace": removed_workspace,
            "removed_memory": removed_memory,
            "irreversible": True,
        }

    async def reset_agent_memory(self, agent_id: int) -> Dict[str, Any]:
        """Reset the learned state (2026-08-19): the cognitive-memory
        DB is cleared (the table truncated, the file kept — the deep
        agent's watch-it-learn demo restarts fresh) + the chat
        sessions + messages for this agent are removed. The agent
        survives: the row, workspace, skills, and identity stay.

        Returns the reset report (what was cleared).
        """
        from sqlalchemy import delete as sa_delete
        from app.infrastructure.database.models import (
            ChatMessage as ChatMessageRow,
        )

        agent = await self._svc.get_by_id(agent_id)
        if agent is None:
            return {"reset": False, "agent_id": agent_id, "reason": "not found"}

        # 1. the memory DB — truncate the table (the file stays)
        mem_rows = 0
        if agent.workspace_key:
            from app.core.config import Paths, get_settings
            mem = Paths.from_settings(get_settings()).agents_dir / agent.workspace_key / "cognitive_memory.db"
            if mem.exists():
                import sqlite3 as _sqlite
                try:
                    conn = _sqlite.connect(str(mem))
                    mem_rows = conn.execute("SELECT COUNT(*) FROM cognitive_memory").fetchone()[0]
                    conn.execute("DELETE FROM cognitive_memory")
                    conn.commit()
                    conn.close()
                except Exception:
                    pass  # the memory file is best-effort

        # 2. the chat sessions + their messages
        session_ids = (await self.db.execute(
            sa_delete(ChatSessionRow).where(ChatSessionRow.agent_id == agent_id).returning(ChatSessionRow.id)
        )).scalars().all()
        messages = 0
        for sid in session_ids:
            messages += (await self.db.execute(
                sa_delete(ChatMessageRow).where(ChatMessageRow.session_id == sid)
            )).rowcount
        await self.db.flush()
        await self.db.commit()

        return {
            "reset": True,
            "agent_id": agent_id,
            "agent_name": agent.name,
            "memory_rows_cleared": mem_rows,
            "chat_sessions_cleared": len(session_ids),
            "chat_messages_cleared": messages,
        }

    async def resolve_agent(self, name: str) -> Agent:
        return await self._svc.resolve_agent(name)

    async def agent_workspace(self, agent_id: int) -> Optional[str]:
        agent = await self._svc.get_by_id(agent_id)
        if agent is None or not agent.workspace_key:
            return None
        # absolute, anchored at the project root — never cwd-relative
        # (the sweep runs pytest from backend/; the path must be stable)
        from app.core.config import Paths, get_settings
        return str(Paths.from_settings(get_settings()).agents_dir / agent.workspace_key)

    async def select_agents(
        self, criteria: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        return await self._select(self.db, criteria)

    async def list_deleted(self) -> List[Dict[str, Any]]:
        from sqlalchemy import select
        rows = (await self.db.execute(
            select(Agent).where(Agent.deleted_at.is_not(None))
        )).scalars().all()
        return [{
            "id": a.id, "name": a.name, "deleted_at": a.deleted_at,
            "archived_path": a.archived_path,
            "workspace_key": a.workspace_key,
        } for a in rows]

    async def restore_agent(self, agent_id: int) -> Agent:
        """Restore a soft-deleted agent.

        Moves its shelved workspace back to `agents/<workspace_key>/` and clears
        the delete markers (`deleted_at`, `archived_path`) — the row is live
        again. ADDITIVE recovery: the move is reversible and a live folder is
        merged into rather than clobbered; nothing is lost.
        """
        from pathlib import Path

        from app.domain.agents import trash as agent_trash

        agent = await self._svc.get_by_id(agent_id)
        if agent is None or agent.deleted_at is None:
            raise ValueError(
                f"Agent {agent_id} is not soft-deleted — nothing to restore"
            )
        # move the shelved workspace back (if any)
        if agent.archived_path and agent.workspace_key:
            src = Path(agent.archived_path)
            if src.exists():
                agent_trash.move_back(src, agent.workspace_key)
        agent.deleted_at = None
        agent.archived_path = None
        agent.is_active = True
        await self.db.flush()
        await self.db.commit()
        # refresh — the commit expires attributes (MissingGreenlet
        # on the schema's lazy read)
        await self.db.refresh(agent)
        return agent


def get_agent_repository(db) -> AgentRepository:
    """The factory — returns the disk implementation today; the
    industrial fork flips this to DbAgentRepository (config-gated)."""
    return DiskAgentRepository(db)
