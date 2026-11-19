"""The AGENTS shelf — trashed agent workspaces, and the residue beside them.

TWO KINDS OF ENTRY, and the difference is a ROW:

- **A TRASHED AGENT** — the workspace of an agent whose row is soft-deleted and
  whose `archived_path` names this folder. It can be RESTORED (the row is the
  destination) and purged for good (the row, every reference, the folder and the
  memory file all go — the repository's hard delete).
- **RESIDUE** — a folder the shelf holds and NO row names. It can be purged and
  nothing else, because nothing records where it came from. This is the class
  that used to be invisible: a folder under `agents/.archived/` became
  unreadable the moment its row went away, and thirty of them accumulated.

WHY THIS SHELF NEEDS THE DATABASE. Only the row can say whether an entry is a
trashed agent or residue, and purging a trashed agent is a scrub across a dozen
tables — not a directory removal. So this is the one shelf that declares
`needs_db`, and the service passes the session through.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.agents import trash as agent_trash
from app.domain.trash.interface import TrashEntry
from app.domain.trash.listing import scan_shelf
from app.domain.trash.mechanics import remove_entry

_RESIDUE = "no record names this folder — residue, purge only"
_NEEDS_DB = "the agents shelf needs a database session to tell an agent from residue"


class AgentsTrash:
    #: The shelf's directory name and its registry key are ONE string, owned by
    #: the agent lifecycle module.
    key = agent_trash.SHELF
    label = "Agents"
    restorable = True
    needs_db = True

    def directory(self) -> Path:
        return agent_trash.shelf_root()

    # ── the row side ────────────────────────────────────────────────────────

    async def _rows(self, db: AsyncSession) -> list[Any]:
        """Every soft-deleted agent that has a workspace on the shelf."""
        from app.infrastructure.database.models import Agent

        rows = (await db.execute(
            select(Agent).where(Agent.deleted_at.is_not(None))
        )).scalars().all()
        return [r for r in rows if r.archived_path]

    async def _row_for(self, db: AsyncSession, name: str) -> Any | None:
        """The row whose shelved workspace is the entry called `name`."""
        for row in await self._rows(db):
            if Path(row.archived_path).name == name:
                return row
        return None

    # ── the contract ────────────────────────────────────────────────────────

    async def entries(self, db: AsyncSession | None = None) -> list[TrashEntry]:
        if db is None:
            raise ValueError(_NEEDS_DB)
        named = {Path(r.archived_path).name: r for r in await self._rows(db)}
        scanned = await asyncio.to_thread(scan_shelf, self.directory())
        out: list[TrashEntry] = []
        for entry in scanned:
            row = named.get(entry.name)
            if row is None:
                out.append(replace(entry, note=_RESIDUE))
            else:
                out.append(replace(
                    entry,
                    restorable=True,
                    note=f"the agent “{row.name}” is trashed — restore it, or purge it for good",
                ))
        return out

    async def restore(self, name: str, db: AsyncSession | None = None) -> dict[str, Any]:
        if db is None:
            raise ValueError(_NEEDS_DB)
        row = await self._row_for(db, name)
        if row is None:
            raise ValueError(
                f"no record names {name!r} — residue cannot be restored; "
                f"it can be purged, or moved by hand"
            )
        from app.domain.agents.repository import get_agent_repository

        agent = await get_agent_repository(db).restore_agent(row.id)
        return {
            "restored": True,
            "agent_id": row.id,
            "name": agent.name,
            "workspace_key": agent.workspace_key,
        }

    async def purge(self, name: str, db: AsyncSession | None = None) -> bool:
        if db is None:
            raise ValueError(_NEEDS_DB)
        row = await self._row_for(db, name)
        if row is None:
            # residue: the folder is all there is, and the shelf owns removal
            return await asyncio.to_thread(remove_entry, self.directory() / name)
        # a trashed agent: the scrub reaches every table that names it, plus the
        # folder and the memory file — the repository's own hard delete
        from app.domain.agents.repository import get_agent_repository

        report = await get_agent_repository(db).hard_delete_agent(row.id)
        return bool(report.get("deleted"))

    async def empty(self, db: AsyncSession | None = None) -> int:
        if db is None:
            raise ValueError(_NEEDS_DB)
        gone = 0
        for entry in await self.entries(db):
            if await self.purge(entry.name, db):
                gone += 1
        return gone
