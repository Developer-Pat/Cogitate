"""The consistency audit (2026-08-19) — the read-only system check.

Walks the reference graph and reports every DANGLING edge: rows
that point at agents (or tools / workflows / collectives) that no
longer exist. The delete path scrubs its own references by id, but
(1) pre-BOM deletes left historical residue, and (2) name-based
references (the AgentDistributor's addressing in workflow configs)
can never be caught by an id-walk — the audit checks those too.

READ-ONLY by contract: it reports; repair is a separate explicit
(action) — the house rule for destructive transforms.
"""
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List


class ConsistencyAudit:
    """The FK-walk consistency audit. Direct-sqlite (the sync pattern
    the tool handlers use — no ORM session needed for a read)."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    # ── the checks ────────────────────────────────────────────────

    def dangling_agent_references(self) -> List[Dict[str, Any]]:
        """Rows pointing at agent ids that no longer exist."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            refs = []
            # id-based reference tables (the BOM's scope). The table
            # may not exist (a fresh/partial schema) — the audit
            # tolerates it (defensive: report what it CAN see).
            tables = [
                ("agent_tools", "agent_id", "tool link"),
                ("usage_logs", "agent_id", "usage log"),
                # collection_items is NOT here — the entity_id is a
                # TEXT-UUID that never matches the INT agent ids; the
                # uncast NOT IN would wrongly flag the tool/workflow
                # collection rows as dangling agent-refs. The AGENT
                # rows are checked below, entity_type-scoped + CAST'd
                # (2026-08-26, the repair-verify gap: the audit counted
                # 7 phantom agent-refs the repair correctly left).
                ("chat_sessions", "agent_id", "chat session"),
            ]
            existing = {
                r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            for table, col, label in tables:
                if table not in existing:
                    continue
                rows = conn.execute(
                    f"SELECT {col} AS ref, COUNT(*) AS n FROM {table} "
                    f"WHERE {col} NOT IN (SELECT id FROM agents) "
                    f"GROUP BY {col}"
                ).fetchall()
                for r in rows:
                    refs.append({
                        "check": f"{table}.{col}",
                        "label": label,
                        "missing_agent_id": str(r["ref"]),
                        "count": r["n"],
                    })
            # the AGENT-scoped collection_items (the CAST'd ids — the
            # audit's agent-references must match the repair's scrub!)
            if "collection_items" in existing:
                for r in conn.execute(
                    "SELECT entity_id AS ref, COUNT(*) AS n FROM collection_items "
                    "WHERE entity_type = 'agent' AND entity_id NOT IN "
                    "         (SELECT CAST(id AS TEXT) FROM agents) "
                    "GROUP BY entity_id"
                ).fetchall():
                    refs.append({
                        "check": "collection_items.entity_id",
                        "label": "collection item (agent)",
                        "missing_agent_id": str(r["ref"]),
                        "count": r["n"],
                    })
            return refs
        finally:
            conn.close()

    def dangling_grant_references(self) -> List[Dict[str, Any]]:
        """agent_tool_grants pointing at missing agents."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            try:
                rows = conn.execute(
                    "SELECT agent_id AS ref, COUNT(*) AS n FROM agent_tool_grants "
                    "WHERE agent_id NOT IN (SELECT id FROM agents) "
                    "  AND agent_id != 'external' "  # the Exa surface's pseudo-id (legit)
                    "GROUP BY agent_id"
                ).fetchall()
            except sqlite3.OperationalError:
                return []
            return [{
                "check": "agent_tool_grants.agent_id",
                "label": "tool grant",
                "missing_agent_id": str(r["ref"]),
                "count": r["n"],
            } for r in rows]
        finally:
            conn.close()

    def dangling_collection_items(self) -> List[Dict[str, Any]]:
        """collection_items pointing at missing tools / workflows
        (the agents case is covered by dangling_agent_references —
        entity_type disambiguates)."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            # the tool check: entity_id (text) vs tools.id (text)
            # the workflow check: entity_id (text) vs CAST(id AS TEXT)
            rows = conn.execute(
                "SELECT entity_type, entity_id AS ref, COUNT(*) AS n "
                "FROM collection_items "
                "WHERE (entity_type = 'tool' AND entity_id NOT IN "
                "         (SELECT CAST(id AS TEXT) FROM tools)) "
                "   OR (entity_type = 'workflow_list' AND entity_id NOT IN "
                "         (SELECT CAST(id AS TEXT) FROM workflow_compositions)) "
                "GROUP BY entity_type, entity_id"
            ).fetchall()
            return [{
                "check": f"collection_items.{r['entity_type']}",
                "label": "collection item",
                "missing_entity": str(r["ref"]),
                "count": r["n"],
            } for r in rows]
        finally:
            conn.close()

    def orphaned_collections(self) -> List[Dict[str, Any]]:
        """Collections with no remaining items (or collections whose
        item rows reference nothing valid).

        An EMPTY collection referenced as a package KIT
        (agent_packages.kit_id) is NOT orphaned — an empty toolkit is
        a deliberate, legitimate state (the shallow-agent seed: zero
        tools by design). Only empty AND unreferenced collections are
        reported (2026-08-29, the recurring Shallow Agent Kit false
        positive)."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            existing = {
                r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            # the kit guard: a collection that a package still points
            # at is a live (empty) toolkit, not a dangling edge. The
            # table may not exist on a fresh/partial schema — omit.
            kit_guard = ""
            if "agent_packages" in existing:
                kit_guard = (
                    " AND NOT EXISTS (SELECT 1 FROM agent_packages ap "
                    "WHERE ap.kit_id = c.id)"
                )
            rows = conn.execute(
                "SELECT c.id AS collection_id, c.name, COUNT(ci.id) AS items "
                "FROM collections c LEFT JOIN collection_items ci ON ci.collection_id = c.id "
                "GROUP BY c.id, c.name "
                f"HAVING COUNT(ci.id) = 0{kit_guard}"
            ).fetchall()
            return [{
                "check": "collections",
                "label": "empty collection",
                "collection_id": r["collection_id"],
                "name": r["name"],
                "count": 0,
            } for r in rows]
        finally:
            conn.close()

    def workflow_name_references(self) -> List[Dict[str, Any]]:
        """Workflow configs that name agents (the AgentDistributor's
        addressing) — the class an id-walk CANNOT catch. The config
        names an agent that no longer exists (active or archived)."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT id, name, config_json FROM workflow_compositions"
            ).fetchall()
            found = []
            for r in rows:
                try:
                    cfg = json.loads(r["config_json"]) if r["config_json"] else {}
                except (json.JSONDecodeError, TypeError):
                    continue
                # collect every string that looks like an agent name
                named = self._extract_names(cfg)
                for n in named:
                    exists = conn.execute(
                        "SELECT id FROM agents WHERE name = ?", (n,)
                    ).fetchone()
                    if exists is None:
                        found.append({
                            "check": "workflow_compositions.config_json",
                            "label": "agent name reference",
                            "workflow_id": r["id"],
                            "workflow_name": r["name"],
                            "missing_agent_name": n,
                        })
            return found
        finally:
            conn.close()

    @staticmethod
    def _extract_names(obj: Any) -> List[str]:
        """Every string in the config that looks like a reference —
        the recipient/agent/address/name keys + free strings that
        match the known-agent-name shape."""
        names: List[str] = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str) and k.lower() in (
                    "recipient", "agent", "agent_name", "target_agent",
                    "address", "deliver_to", "assigned_agent",
                ):
                    names.append(v)
                else:
                    names.extend(ConsistencyAudit._extract_names(v))
        elif isinstance(obj, list):
            for item in obj:
                names.extend(ConsistencyAudit._extract_names(item))
        return names

    # ── the run ───────────────────────────────────────────────────

    def run(self) -> Dict[str, Any]:
        """Run every check + summarize. READ-ONLY — reports only."""
        checks: Dict[str, Any] = {
            "agent_references": self.dangling_agent_references(),
            "grant_references": self.dangling_grant_references(),
            "collection_items": self.dangling_collection_items(),
            "orphaned_collections": self.orphaned_collections(),
            "workflow_name_references": self.workflow_name_references(),
        }
        total = sum(len(v) for v in checks.values())
        return {
            "audited_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
            "status": "clean" if total == 0 else "inconsistent",
            "total_findings": total,
            "checks": checks,
            "note": ("READ-ONLY audit — reports the dangling references; "
                     "repair is a separate explicit action (never automatic)."),
        }
