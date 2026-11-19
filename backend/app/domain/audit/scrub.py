"""The orphan scrub service (2026-08-24, the sweep's cleanup half).

THE DESIGN (local/system-sweep/03-scrub.md): the sweep REPORTS,
the scrub REPAIRS — a separate, explicit, GUARDED surface. The
guardrails:
1. dry-run by default (returns the would-delete, deletes nothing)
2. the typed confirm (the real run requires the counts to match
   the proposal)
3. a DB backup taken before the real run
4. the outcome reported (the deleted counts + the re-audit)
"""

import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# THE SCRUB'S SCOPE: the orphan class ONLY (rows whose FK target
# row is missing). The session-3 GHOSTS (the collided Exa messages
# in a LIVE session) are NOT orphans — never touched.
ORPHAN_TABLES = [
    ("chat_messages", "session_id", "chat_sessions"),
    ("usage_logs", "session_id", "chat_sessions"),
    ("chat_attachments", "session_id", "chat_sessions"),
]


class OrphanScrubService:
    """The guarded orphan cleanup."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    # ── the count + the delete ────────────────────────────────────

    def _orphan_counts(self, conn: sqlite3.Connection) -> Dict[str, int]:
        """The live orphan counts per table (the proposal's truth)."""
        counts: Dict[str, int] = {}
        for table, col, target in ORPHAN_TABLES:
            try:
                n = conn.execute(
                    f"SELECT COUNT(*) FROM {table} "
                    f"WHERE {col} NOT IN (SELECT id FROM {target})"
                ).fetchone()[0]
                counts[table] = n
            except sqlite3.OperationalError:
                counts[table] = 0
        return counts

    def _delete_orphans(self, conn: sqlite3.Connection) -> Dict[str, int]:
        """Delete the orphans; return the per-table deleted counts."""
        deleted: Dict[str, int] = {}
        for table, col, target in ORPHAN_TABLES:
            try:
                cur = conn.execute(
                    f"DELETE FROM {table} "
                    f"WHERE {col} NOT IN (SELECT id FROM {target})"
                )
                deleted[table] = cur.rowcount
            except sqlite3.OperationalError:
                deleted[table] = 0
        return deleted

    def _backup(self) -> str:
        """A timestamped backup BEFORE the destructive run (the
        migration/damage backup rule)."""
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = self.db_path.with_name(f"{self.db_path.name}.bak-scrub-{stamp}")
        shutil.copy2(self.db_path, target)
        return str(target)

    # ── the run ───────────────────────────────────────────────────

    def scrub(
        self,
        dry_run: bool = True,
        expected_counts: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """Run the scrub with the guardrails.

        dry_run=True (default): report the would-delete, touch
        nothing. dry_run=False: verify the expected counts match
        the live counts (the typed confirm), take the backup,
        delete, re-audit.
        """
        conn = sqlite3.connect(str(self.db_path))
        try:
            live = self._orphan_counts(conn)
            total = sum(live.values())

            if dry_run:
                return {
                    "dry_run": True,
                    "would_delete": live,
                    "total": total,
                }

            # THE TYPED CONFIRM: the caller must state what it's
            # deleting — the counts must match the live truth.
            if not expected_counts:
                raise ValueError("confirm expected_counts is required for the real run")
            mismatch = {
                table: {"expected": expected_counts.get(table, 0), "live": live.get(table, 0)}
                for table, _col, _target in ORPHAN_TABLES
                if expected_counts.get(table, 0) != live.get(table, 0)
            }
            if mismatch:
                raise ValueError(
                    f"The counts changed — re-propose, don't guess: {mismatch}"
                )
            if total == 0:
                return {
                    "dry_run": False,
                    "deleted": {},
                    "total": 0,
                    "re_audit": {"status": "clean", "violations": 0},
                    "backup": None,
                    "note": "nothing to scrub",
                }

            # the backup + the delete
            backup = self._backup()
            deleted = self._delete_orphans(conn)
            conn.commit()

            # THE READ-BACK: re-run the audit — the outcome proof
            from app.domain.audit.integrity import IntegrityAudit
            re_audit = IntegrityAudit(self.db_path).run()

            logger.info(
                "Scrub complete: deleted %s (backup %s)",
                deleted, backup,
            )
            return {
                "dry_run": False,
                "deleted": deleted,
                "total": sum(deleted.values()),
                "re_audit": {
                    "status": re_audit["status"],
                    "violations": re_audit["violations"],
                },
                "backup": backup,
            }
        finally:
            conn.close()
