"""The derived FK-walk provider (Phase 5, 2026-08-19).

Option A from the study: the graph is a VIEW over cogitate.db's
foreign keys — the schema DECLARES the edges, the walk reads
them. Always true (it reads the DB); the cost is walk-time,
fine at this scale. The demo (2026-08-18) proved the shape; this
is the service form.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import Paths
from app.domain.graph import GraphProvider


def _settings_db_path() -> Path:
    """THE DATABASE FILE, resolved through settings — never the class attribute
    `Paths.shared_db`, which is a dataclass FIELD DEFAULT (a fixed
    BASE_DIR/cogitate.db) and so ignores DATABASE_URL. Reading the default here
    pointed the graph provider at the operator's live database inside tests.
    """
    from app.core.config import get_settings

    return Paths.from_settings(get_settings()).shared_db

# the topology-relevant tables + their display kinds
NODE_KINDS = {
    "agents": "agent",
    "workflow_templates": "workflow",
    "workflow_triggers": "trigger",
    "workflow_compositions": "composition",
    "tools": "tool",
    "chat_sessions": "session",
    "providers": "provider",
    "collections": "collection",
    "documents": "document",
    "macro_sets": "macro",
}

# the FK edges worth showing (table -> ref_table -> label)
EDGE_LABELS = {
    ("agent_tools", "tools"): "uses-tool",
    ("chat_sessions", "agents"): "belongs-to",
    ("runtime_configs", "agents"): "configures",
    ("runtime_configs", "chat_sessions"): "configures-session",
    ("workflow_triggers", "workflow_templates"): "fires",
    ("workflow_execution_history", "workflow_compositions"): "executes",
    ("workflow_execution_history", "workflow_execution_history"): "parent-of",
    ("workflow_approvals", "workflow_compositions"): "approves",
    ("agent_versions", "agents"): "version-of",
    ("tools", "tool_categories"): "categorized-by",
    ("team_tools", "tools"): "team-uses",
    ("team_tools", "collections"): "team-has",
    ("provider_model_cache", "providers"): "cached-by",
    ("provider_sync_schedules", "providers"): "synced-by",
    ("usage_logs", "agents"): "used-by",
    ("usage_logs", "chat_sessions"): "logged-in",
}


class DerivedGraphProvider(GraphProvider):
    """Walk cogitate.db's foreign keys as the topology graph."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = str(db_path or _settings_db_path())

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _kind_of(self, table: str) -> str | None:
        return NODE_KINDS.get(table)

    def _resolve_entity(self, entity_id: str) -> Dict[str, Any] | None:
        """Find the node an id belongs to — the entity + its table."""
        conn = self._conn()
        try:
            # the id might be a bare slug (agent-hello, rss-monitor) or
            # a table-specific id — probe the known tables by their
            # name/id columns
            # PHASE-5 (2026-08-19): the probe ORDER matters — a slug
            # like 'agent-hello' matches BOTH the agents.name AND the
            # workflow_templates.id (the seed templates share the slug).
            # The agents table is the canonical identity for agent-*
            # slugs; probe it first, then the rest by specificity.
            probes = [
                ("agents", "name"),
                ("workflow_triggers", "id"),
                ("workflow_templates", "id"),
                ("workflow_compositions", "id"),
                ("tools", "slug"),
                ("chat_sessions", "id"),
                ("providers", "id"),
                ("collections", "id"),
            ]
            for table, col in probes:
                try:
                    row = conn.execute(
                        f'SELECT * FROM "{table}" WHERE "{col}" = ?', (entity_id,)
                    ).fetchone()
                except sqlite3.OperationalError:
                    continue
                if row is not None:
                    keys = row.keys()
                    name = (
                        row["name"] if "name" in keys
                        else row["title"] if "title" in keys
                        else row[col]
                    )
                    return {
                        "id": str(row[col]),
                        "kind": self._kind_of(table) or table,
                        "name": str(name),
                        "table": table,
                        "row": dict(row),
                    }
            return None
        finally:
            conn.close()

    def get_entity(self, entity_id: str) -> Dict[str, Any] | None:
        found = self._resolve_entity(entity_id)
        if found is None:
            return None
        return {k: v for k, v in found.items() if k != "row"}

    def get_neighbors(self, entity_id: str, depth: int = 1) -> Dict[str, Any]:
        entity = self._resolve_entity(entity_id)
        if entity is None:
            return {"entity": entity_id, "edges": []}
        conn = self._conn()
        try:
            table = entity["table"]
            pk = "id"
            if table == "agents":
                pk = "name"
            elif table == "tools":
                pk = "slug"
            edges: List[Dict[str, Any]] = []
            # 1. outgoing: this table's rows reference others
            fks = conn.execute(
                'SELECT "table" AS refs, "from" AS via FROM pragma_foreign_key_list(?)',
                (table,),
            ).fetchall()
            for fk in fks:
                refs, via = fk["refs"], fk["via"]
                label = EDGE_LABELS.get((table, refs), "references")
                try:
                    rows = conn.execute(
                        f'SELECT "{via}" AS fk FROM "{table}" WHERE "{pk}" = ?',
                        (entity_id,),
                    ).fetchall()
                except sqlite3.OperationalError:
                    continue
                for r in rows:
                    if r["fk"] is None:
                        continue
                    edges.append({
                        "kind": label,
                        "direction": "out",
                        "to": f"{refs}:{r['fk']}",
                        "to_kind": self._kind_of(refs) or refs,
                    })
            # 2. incoming: other tables reference this row. The FK
            # columns hold the NUMERIC pk (agent_id = 15), not the
            # display id ('Scheherazade') — resolve the row's numeric
            # pk first (Phase 5, 2026-08-19).
            numeric_pk = None
            pk_col = "id"
            if table == "agents":
                pk_col = "name"
            elif table == "tools":
                pk_col = "slug"
            try:
                row_pk = conn.execute(
                    f'SELECT "{pk_col}" AS pk, id FROM "{table}" WHERE "{pk_col}" = ?',
                    (entity_id,),
                ).fetchone()
                if row_pk is not None and "id" in row_pk.keys():
                    numeric_pk = row_pk["id"]
            except sqlite3.OperationalError:
                pass
            for src_table, (refs, via) in self._incoming_fks(conn, table):
                lookup_val = numeric_pk if numeric_pk is not None else entity_id
                try:
                    rows = conn.execute(
                        f'SELECT * FROM "{src_table}" WHERE "{via}" = ?',
                        (lookup_val,),
                    ).fetchall()
                except sqlite3.OperationalError:
                    continue
                for r in rows:
                    src_pk = "id"
                    if src_table == "agents":
                        src_pk = "name"
                    elif src_table == "tools":
                        src_pk = "slug"
                    src_id = r[src_pk] if src_pk in r.keys() else r[0]
                    edges.append({
                        "kind": EDGE_LABELS.get((src_table, refs), "referenced-by"),
                        "direction": "in",
                        "to": f"{src_table}:{src_id}",
                        "to_kind": self._kind_of(src_table) or src_table,
                    })
            # 3. SEMANTIC edges (Phase 5, 2026-08-19): the declared FKs
            # miss the most important relationships — workflow_triggers
            # has NO FK constraint (the workflow_id -> templates link is
            # implicit). These are the known implicit edges, walked
            # explicitly. The view stays true (it reads the DB).
            if table == "agents":
                # THE AGENT TOOL LINKS (2026-08-24): agent_tools
                # declares NO agent_id FK (only tool_id) — the
                # declared-FK walk misses the uses-tool edges. Walk
                # them explicitly (the purge surfaced it: an agent's
                # graph evidence can't depend on usage history).
                for r in conn.execute(
                    "SELECT t.slug FROM agent_tools at JOIN tools t ON t.id = at.tool_id "
                    "WHERE at.agent_id = ?",
                    (numeric_pk,),
                ).fetchall():
                    edges.append({
                        "kind": "uses-tool",
                        "direction": "out",
                        "to": f"tools:{r['slug']}",
                        "to_kind": "tool",
                    })
            if table == "workflow_templates":
                for r in conn.execute(
                    'SELECT id FROM workflow_triggers WHERE workflow_id = ?',
                    (entity_id,),
                ).fetchall():
                    edges.append({
                        "kind": "fires",
                        "direction": "in",
                        "to": f"workflow_triggers:{r['id']}",
                        "to_kind": "trigger",
                    })
            elif table == "workflow_triggers":
                # the trigger's workflow_id column holds the TEMPLATE id
                for r in conn.execute(
                    'SELECT workflow_id FROM workflow_triggers WHERE id = ?',
                    (entity_id,),
                ).fetchall():
                    if r["workflow_id"]:
                        edges.append({
                            "kind": "fires",
                            "direction": "out",
                            "to": f"workflow_templates:{r['workflow_id']}",
                            "to_kind": "workflow",
                        })
            return {"entity": entity_id, "edges": edges}
        finally:
            conn.close()

    def _incoming_fks(self, conn: sqlite3.Connection, target: str):
        """All (src_table, (refs, via)) where src references target."""
        out = []
        for m in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall():
            src = m["name"]
            for fk in conn.execute(
                'SELECT "table" AS refs, "from" AS via FROM pragma_foreign_key_list(?)',
                (src,),
            ).fetchall():
                if fk["refs"] == target:
                    out.append((src, (fk["refs"], fk["via"])))
        return out

    def get_topology(self, kind: str | None = None) -> Dict[str, Any]:
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        conn = self._conn()
        try:
            for table, node_kind in NODE_KINDS.items():
                if kind and node_kind != kind:
                    continue
                try:
                    name_col = "name" if table != "tools" else "slug"
                    rows = conn.execute(f'SELECT * FROM "{table}"').fetchall()
                except sqlite3.OperationalError:
                    continue
                for r in rows:
                    pk = "id"
                    if table == "agents":
                        pk = "name"
                    elif table == "tools":
                        pk = "slug"
                    keys = r.keys()
                    nodes.append({
                        "id": f"{table}:{r[pk] if pk in keys else r[0]}",
                        "kind": node_kind,
                        "name": str(r[name_col] if name_col in keys else r[pk]),
                    })
            # the edges: for the FK-pairs we label, emit one edge row
            for (src, refs), label in EDGE_LABELS.items():
                try:
                    rows = conn.execute(f'SELECT * FROM "{src}"').fetchall()
                except sqlite3.OperationalError:
                    continue
                for r in rows:
                    keys = r.keys()
                    pk = "id"
                    if src == "agents":
                        pk = "name"
                    elif src == "tools":
                        pk = "slug"
                    src_id = r[pk] if pk in keys else r[0]
                    if refs == "workflow_execution_history":
                        to_id = r[0]
                    else:
                        to_id = None
                        for cand in ("workflow_id", "tool_id", "agent_id", "composition_id",
                                     "provider_id", "category_id", "parent_id", "session_id",
                                     "team_id", "collection_id", "document_id", "related_document_id"):
                            if cand in keys and r[cand] is not None:
                                to_id = r[cand]
                                break
                    edges.append({
                        "kind": label,
                        "from": f"{src}:{src_id}",
                        "to": f"{refs}:{to_id}",
                    })
        finally:
            conn.close()
        return {"nodes": nodes, "edges": edges}
