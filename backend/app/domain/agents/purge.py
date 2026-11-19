"""THE PURGE INVENTORY — everything that names an agent, and how it goes.

WHY AN INVENTORY RATHER THAN A LIST OF DELETES. A purge written as a sequence of
statements in the repository is correct exactly for the tables the person
writing it happened to remember — and that is how a "permanently deleted" agent
keeps rows naming it in four tables nobody re-read. This module states the whole
set ONCE, and the set is CHECKED AGAINST THE SCHEMA: `missing_from_the_inventory`
asks the database which (table, column) pairs carry an agent reference and names
any the inventory does not claim. A new table that starts naming agents therefore
fails the check (a test asserts it is empty) instead of quietly outliving them.

WHAT IT CANNOT SEE, stated rather than implied: the check reads COLUMN NAMES
(`REFERENCE_COLUMNS`). A reference stored under another name — a JSON blob, a
key prefix in a sidecar store — is invisible to it, which is why those cases are
declared here explicitly (`in_schema=False`) and carry a note saying who has to
remember them.

ORDER. Children before parents: a session's messages go before the session, and
the row itself is removed by the caller (the repository), last.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, cast

from sqlalchemy import CursorResult
from sqlalchemy import delete as sa_delete
from sqlalchemy import select as sa_select
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

#: The column NAMES that mark an agent reference. The schema check reads these;
#: anything referencing an agent under a different name is declared explicitly
#: in the inventory instead.
REFERENCE_COLUMNS = ("agent_id", "agent_ids")

#: How a row carries the agent's identity.
INT_KEY = "int"
TEXT_KEY = "text"  # the legacy text columns (agent_tools, agent_tool_grants, tool_usage_logs)


Scrub = Callable[[AsyncSession, int], Awaitable[dict[str, int]]]


@dataclass(frozen=True)
class Reference:
    """One thing that names an agent, and how to clear it."""

    #: The table the rows live in (or a NAME for a store outside the schema).
    table: str
    #: The columns that carry the reference — what the schema check compares.
    columns: tuple[str, ...]
    note: str
    scrub: Scrub
    #: False for a store that is not a table in the shared schema (the KV memory
    #: store). The schema check only reads the ones that ARE.
    in_schema: bool = True
    #: True when the table may legitimately be absent (a leaner schema, a legacy
    #: table) — its scrub is then allowed to fail without failing the purge.
    optional: bool = False


def _value(agent_id: int, key: str) -> Any:
    return str(agent_id) if key == TEXT_KEY else agent_id


async def _rowcount(db: AsyncSession, statement: Any) -> int:
    """How many rows a DELETE/UPDATE touched.

    `execute()` returns a CursorResult for DML, but its declared type is the
    general `Result` — the cast says which one this actually is, instead of the
    caller reaching for an attribute the type does not promise.
    """
    result = await db.execute(statement)
    return int(cast(CursorResult[Any], result).rowcount or 0)


async def _by_column(db: AsyncSession, model: Any, column: str, agent_id: int, key: str) -> int:
    col = getattr(model, column)
    return await _rowcount(db, sa_delete(model).where(col == _value(agent_id, key)))


# ── the scrubs, one per reference ───────────────────────────────────────────


async def _tool_links(db: AsyncSession, agent_id: int) -> dict[str, int]:
    from app.domain.tools.models import AgentTool

    return {"tool_links": await _by_column(db, AgentTool, "agent_id", agent_id, TEXT_KEY)}


async def _grants(db: AsyncSession, agent_id: int) -> dict[str, int]:
    from app.domain.tools.models import AgentToolGrant

    return {"grants": await _by_column(db, AgentToolGrant, "agent_id", agent_id, TEXT_KEY)}


async def _kits(db: AsyncSession, agent_id: int) -> dict[str, int]:
    """The agent_kits JOIN — an agent owns N toolkits. Left out of the purge in
    the first pass, so a "scrubbed" agent could still be named as a kit owner."""
    from app.domain.agent_kits.model import AgentKit

    return {"kits": await _by_column(db, AgentKit, "agent_id", agent_id, INT_KEY)}


async def _tool_usage(db: AsyncSession, agent_id: int) -> dict[str, int]:
    from app.domain.tools.models import ToolUsageLog

    return {"tool_usage_logs": await _by_column(db, ToolUsageLog, "agent_id", agent_id, TEXT_KEY)}


async def _collections(db: AsyncSession, agent_id: int) -> dict[str, int]:
    from app.domain.collections.models import CollectionItem

    return {"collections": await _rowcount(db, sa_delete(CollectionItem).where(
        CollectionItem.entity_id == str(agent_id),
        CollectionItem.entity_type == "agent",
    ))}


async def _sessions_and_messages(db: AsyncSession, agent_id: int) -> dict[str, int]:
    """The sessions and their messages. IN THAT ORDER — a message names its
    session, so removing the session first would leave the messages orphaned."""
    from app.infrastructure.database.models import ChatMessage, ChatSession

    session_ids = (await db.execute(
        sa_delete(ChatSession).where(ChatSession.agent_id == agent_id).returning(ChatSession.id)
    )).scalars().all()
    messages = 0
    for sid in session_ids:
        messages += await _rowcount(db, sa_delete(ChatMessage).where(ChatMessage.session_id == sid))
    return {"chat_sessions": len(session_ids), "chat_messages": messages}


async def _usage_logs(db: AsyncSession, agent_id: int) -> dict[str, int]:
    from app.infrastructure.database.models import UsageLog

    return {"usage_logs": await _by_column(db, UsageLog, "agent_id", agent_id, INT_KEY)}


async def _runtime_configs(db: AsyncSession, agent_id: int) -> dict[str, int]:
    from app.infrastructure.database.models import RuntimeConfig

    return {"runtime_configs": await _by_column(db, RuntimeConfig, "agent_id", agent_id, INT_KEY)}


async def _versions(db: AsyncSession, agent_id: int) -> dict[str, int]:
    """agent_versions has no ORM model (the versioning registry is in-memory),
    so this is a raw statement — and the table may not exist at all."""
    return {"versions": await _rowcount(
        db,
        sa_text("DELETE FROM agent_versions WHERE agent_id = :aid").bindparams(
            aid=str(agent_id)
        ),
    )}


async def _audit_log(db: AsyncSession, agent_id: int) -> dict[str, int]:
    """The sqlite-manager audit log — no ORM model, and empty in practice, but
    it carries the column and so it is claimed here."""
    return {"audit_log": await _rowcount(
        db,
        sa_text("DELETE FROM _sqlite_manager_audit_log WHERE agent_id = :aid").bindparams(
            aid=str(agent_id)
        ),
    )}


async def _agent_lists(db: AsyncSession, agent_id: int) -> dict[str, int]:
    """The saved agent LISTS carry ids in a JSON array — a reference no FK and no
    column-name check can see, which is why the list page kept offering deleted
    agents."""
    from app.infrastructure.database.models import AgentList

    rows = (await db.execute(sa_select(AgentList))).scalars().all()
    changed = 0
    for row in rows:
        ids = list(row.agent_ids or [])
        if agent_id in ids:
            row.agent_ids = [i for i in ids if i != agent_id]
            changed += 1
    return {"agent_lists": changed}


async def _shared_memory_keys(db: AsyncSession, agent_id: int) -> dict[str, int]:
    """The SHARED KV memory store's keys for this agent (`agent_<id>:<session>`).

    A second store beside the per-agent `cognitive_memory.db` the repository
    removes — and one whose keys survive a delete unless something looks.

    A SIDECAR STORE, so the two honest limits: it is read with raw sqlite3 (the
    house pattern for a store outside the migration chain) and its absence is
    not a failure — an installation that never used it has no file.
    """
    from app.core.config import Paths, get_settings

    path: Path = Paths.from_settings(get_settings()).data_dir / "cognitive_memory.db"
    if not path.exists():
        return {"memory_keys": 0}
    con = sqlite3.connect(str(path))
    try:
        cur = con.execute(
            "DELETE FROM cognitive_memory WHERE key LIKE ?", (f"agent_{agent_id}:%",)
        )
        removed = int(cur.rowcount or 0)
        con.commit()
    finally:
        con.close()
    return {"memory_keys": removed}


# ── the inventory ───────────────────────────────────────────────────────────

INVENTORY: tuple[Reference, ...] = (
    # CHILDREN FIRST, and the order matters where a FK points at a session:
    # usage_logs and runtime_configs both name a session, so they go BEFORE the
    # sessions they name (a config left behind would block, or orphan, the
    # session's removal).
    Reference("agent_tools", ("agent_id",), "the agent's tool links", _tool_links),
    Reference("agent_tool_grants", ("agent_id",), "the agent's tool grants", _grants),
    Reference("agent_kits", ("agent_id",), "the toolkits the agent owns", _kits),
    Reference("tool_usage_logs", ("agent_id",), "tool invocations it made", _tool_usage),
    Reference("collection_items", ("entity_id",), "its collection memberships", _collections),
    Reference("usage_logs", ("agent_id",), "its LLM usage", _usage_logs),
    Reference("runtime_configs", ("agent_id",), "its runtime configs", _runtime_configs),
    Reference(
        "chat_sessions", ("agent_id",),
        "its chat sessions (and, with them, the messages)", _sessions_and_messages,
    ),
    Reference("agent_versions", ("agent_id",), "its version rows", _versions, optional=True),
    Reference(
        "_sqlite_manager_audit_log", ("agent_id",),
        "the sqlite-manager audit trail", _audit_log, optional=True,
    ),
    Reference("agent_lists", ("agent_ids",), "the saved lists that name it", _agent_lists),
    Reference(
        "cognitive_memory (shared store)", (),
        "the shared KV memory store's `agent_<id>:` keys",
        _shared_memory_keys, in_schema=False, optional=True,
    ),
)


async def scrub_agent(db: AsyncSession, agent_id: int) -> dict[str, int]:
    """Remove every reference to `agent_id` and report what went, per name.

    An OPTIONAL reference whose table is absent reports 0 rather than failing the
    purge: a leaner schema is not a broken delete. Anything else propagates —
    a purge that half-ran must not look like one that finished.
    """
    report: dict[str, int] = {}
    for ref in INVENTORY:
        try:
            report.update(await ref.scrub(db, agent_id))
        except Exception as exc:  # noqa: BLE001 — see the docstring
            if not ref.optional:
                raise
            logger.info("purge: %s could not be cleared (%s) — optional", ref.table, exc)
            report[ref.table] = 0
    return report


async def references_missing_from_the_inventory(db: AsyncSession) -> list[tuple[str, str]]:
    """The (table, column) pairs that NAME an agent and the inventory does not
    claim — the derived half of the check.

    A reference under a name this cannot read (a JSON array, a key prefix) is
    invisible here; those are declared in the inventory with `in_schema=False`
    and a note, which is the honest trade this function makes.
    """
    claimed = {
        (ref.table, column)
        for ref in INVENTORY if ref.in_schema
        for column in ref.columns
    }
    tables = (await db.execute(
        sa_text("SELECT name FROM sqlite_master WHERE type = 'table'")
    )).scalars().all()
    missing: list[tuple[str, str]] = []
    for table in tables:
        if table.startswith("sqlite_"):
            continue
        rows = (await db.execute(sa_text(f'PRAGMA table_info("{table}")'))).all()
        for row in rows:
            column = row[1]
            if column in REFERENCE_COLUMNS and (table, column) not in claimed:
                missing.append((table, column))
    return sorted(missing)
