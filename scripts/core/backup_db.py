#!/usr/bin/env python3
"""
Database backup script — a DEVELOPMENT UTILITY, not a release feature.

Creates timestamped, point-in-time copies of the SQLite databases used by the
development installation. Safe to run while the server is running.

HOW IT IS CONSISTENT (this used to be a lie — read it before changing the
copy path): each database is copied with **sqlite3's `backup()` API**, which
takes a proper transactional snapshot. It does NOT read the file with a
filesystem copy.

The previous implementation used `shutil.copy2` on the database and then copied
the `-wal`/`-shm` files as separate steps. That pair is NOT atomic: a write
landing between the two copies yields a main file and a WAL that do not match.
For a WAL-mode database the result is a corrupt or silently stale backup — and
the docstring claimed it was "consistent for WAL-mode", so the one person who
would have checked had been told not to.

Because `backup()` produces a single consistent file, no `-wal`/`-shm` files are
copied, and none should be.

Usage:
    python3 scripts/backup_db.py                          # default: 10 most recent kept
    python3 scripts/backup_db.py --keep 5                  # keep only 5 most recent
    python3 scripts/backup_db.py --dry-run                 # preview without copying
    python3 scripts/backup_db.py --backup-dir /tmp/db-bak  # custom backup location

Databases backed up (paths from backend/app/core/config.py):
  - cogitate.db          (main application database)
  - data/cogitate_docs_en.db  (documents database)
"""

import argparse
import json
import logging
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("backup_db")

# ─── Paths ────────────────────────────────────────────────────────────────────

# The application owns the path knowledge, so ask IT rather than re-deriving the
# layout here. The previous code crawled `parents[2]` by hand — the exact
# mechanism the path scanner flags, and a second source of truth that drifts.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.core.config import Paths, get_settings  # noqa: E402

_paths = Paths.from_settings(get_settings())

BASE_DIR = _paths.base_dir if hasattr(_paths, "base_dir") else _paths.shared_db.parent

DATABASES: dict[str, Path] = {
    "cogitate": _paths.shared_db,
    "documents": _paths.data_dir / "cogitate_docs_en.db",
}

DEFAULT_BACKUP_DIR = BASE_DIR / "backups"
DEFAULT_KEEP = 10


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _timestamp() -> str:
    """Return a compact, sortable timestamp string."""
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _snapshot_sqlite(src_path: Path, dst_path: Path) -> None:
    """Copy a SQLite database with the backup API — a consistent snapshot.

    `sqlite3.Connection.backup()` copies page-by-page inside a transaction, so
    it is correct while another process is writing, and the destination is a
    single self-contained file. That is why no WAL/SHM handling is needed here:
    the snapshot has already had the WAL applied.

    A filesystem copy cannot do this (see the module docstring). Opens the
    source READ-ONLY so a backup can never write to the database it copies.
    """
    import sqlite3

    src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(str(dst_path))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def _human_size(path: Path) -> str:
    """Return a human-readable file size."""
    # float from the start: the loop divides in place, and an int cannot hold the
    # result (pre-existing mypy error, fixed while the file was open).
    size = float(path.stat().st_size)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _find_backups(backup_dir: Path) -> list[Path]:
    """Return sorted list of existing backup directories (oldest first)."""
    if not backup_dir.exists():
        return []
    candidates = sorted(
        [d for d in backup_dir.iterdir() if d.is_dir() and d.name.startswith("20")],
    )
    return candidates


def _prune_old_backups(backup_dir: Path, keep: int) -> None:
    """Remove oldest backup directories beyond ``keep`` count."""
    backups = _find_backups(backup_dir)
    if len(backups) <= keep:
        return
    to_remove = backups[: len(backups) - keep]
    for old_dir in to_remove:
        shutil.rmtree(old_dir)
        logger.info("Pruned old backup: %s", old_dir)


def _backup_info(backup_dir: Path) -> list[dict]:
    """Return structured metadata about existing backups."""
    records: list[dict] = []
    for d in _find_backups(backup_dir):
        meta_file = d / "backup_meta.json"
        meta = {}
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text())
            except Exception:
                meta = {"note": "failed to read metadata"}
        records.append({
            "path": str(d),
            "name": d.name,
            "timestamp": meta.get("timestamp", d.name),
            "databases": meta.get("databases", []),
        })
    return records


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backup all Cogitate SQLite databases.",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=DEFAULT_KEEP,
        help=f"Number of recent backups to keep (default: {DEFAULT_KEEP})",
    )
    parser.add_argument(
        "--backup-dir",
        type=str,
        default=str(DEFAULT_BACKUP_DIR),
        help=f"Backup directory (default: {DEFAULT_BACKUP_DIR})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be backed up without copying",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_backups",
        help="List existing backups and exit",
    )
    args = parser.parse_args()

    backup_dir = Path(args.backup_dir)

    # ── List mode ──
    if args.list_backups:
        records = _backup_info(backup_dir)
        if not records:
            print("No backups found.")
            return 0
        print(f"Existing backups in {backup_dir}:")
        for r in records:
            dbs = ", ".join(r["databases"]) if r["databases"] else "(unknown)"
            print(f"  {r['name']}  [{dbs}]")
        return 0

    # ── Verify databases exist ──
    missing: list[str] = []
    available: dict[str, Path] = {}
    for name, path in DATABASES.items():
        if path.exists():
            available[name] = path
        else:
            missing.append(name)

    if not available:
        logger.error("No databases found — nothing to back up.")
        return 1

    if missing:
        logger.warning("Some databases not found (skipped): %s", ", ".join(missing))

    # ── Create backup directory ──
    ts = _timestamp()
    dest_dir = backup_dir / ts
    if args.dry_run:
        print(f"[DRY RUN] Would create: {dest_dir}/")
        for name, src_path in available.items():
            print(f"  {name}: {src_path} ({_human_size(src_path)})")
            print("    → snapshot via sqlite3 backup() (consistent, single file)")
        print(f"Would keep {args.keep} most recent backups.")
        return 0

    dest_dir.mkdir(parents=True, exist_ok=True)
    start = time.time()

    # ── Snapshot each database ──
    # sqlite3's backup() API, NOT a filesystem copy: it takes a transactional
    # snapshot that is consistent even while the server is writing, and it
    # produces ONE file -- so no -wal/-shm pair to get out of step. See the
    # module docstring for what the previous implementation got wrong.
    copied: list[str] = []
    for name, src_path in available.items():
        dst_path = dest_dir / src_path.name
        _snapshot_sqlite(src_path, dst_path)
        copied.append(name)
        logger.info("Snapshotted %s → %s (%s)", name, dst_path, _human_size(dst_path))

    elapsed = time.time() - start

    # ── Write metadata ──
    meta = {
        "timestamp": ts,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "databases": copied,
        "elapsed_seconds": round(elapsed, 2),
        "backend_base_dir": str(BASE_DIR),
    }
    (dest_dir / "backup_meta.json").write_text(json.dumps(meta, indent=2))

    # ── Prune old backups ──
    _prune_old_backups(backup_dir, args.keep)

    logger.info(
        "Backup complete: %s (%d databases, %.2fs)",
        dest_dir,
        len(copied),
        elapsed,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
