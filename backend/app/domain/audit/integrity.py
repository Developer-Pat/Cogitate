"""The integrity checks (2026-08-24, the system-sweep Phase 1).

The GHOST-HISTORY class the sweep must catch: dead FK targets,
orphaned rows, disabled cascade enforcement, id reuse. READ-ONLY
by contract — reports, never repairs (the house rule).

The checks:
1. cascade_audit   — every declared FK's target table EXISTS + the
                     foreign_keys pragma is ON (the chat_sessions_old
                     class: four tables referenced a dead table).
2. orphan_scan     — for every FK that resolves, rows whose target
                     row is missing (the ghost-history residue).
3. id_reuse_watch  — INTEGER-PK tables WITHOUT AUTOINCREMENT can
                     reuse deleted ids (harmless once orphans are
                     gone, but worth watching).
4. log_roll_check  — the rotated log files (app.log.N): sizes +
                     ages — flag logs that may need rolling/deleting.
5. ghost_db_files  — the GHOST FILES (2026-09-07, the
                     backend/cogitate.db lesson): stray/empty .db
                     files under the repo root that should not exist
                     — created when an LLM/script opens a relative
                     path from the wrong cwd. The startup sweep's
                     copy (the manual twin lives in
                     scripts/core/sweep/backend.py).
"""

import sqlite3
from datetime import datetime, timedelta
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class IntegrityAudit:
    """The sweep's integrity checks. Direct-sqlite (the sync read
    pattern of the ConsistencyAudit — no ORM session needed)."""

    def __init__(self, db_path: Path, logs_dir: Path | None = None):
        self.db_path = Path(db_path)
        self.logs_dir = Path(logs_dir) if logs_dir else self.db_path.parent / "logs"

    # ── the checks ────────────────────────────────────────────────

    def cascade_audit(self) -> List[Dict[str, Any]]:
        """Every declared FK's target table must EXIST (the dead
        chat_sessions_old class) + the foreign_keys pragma must be
        ON (the dead-cascade class)."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            tables = [
                r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            ]
            findings = []
            for t in tables:
                fks = conn.execute(f"PRAGMA foreign_key_list({t})").fetchall()
                for fk in fks:
                    target = fk[2]
                    if target not in tables:
                        findings.append({
                            "check": "cascade_audit",
                            "severity": "critical",
                            "table": t,
                            "column": fk[3],
                            "message": f"FK references the MISSING table '{target}' — every write to {t} fails",
                        })
            # the pragma (per-connection — the app's engine sets it;
            # a fresh raw connection shows the DEFAULT: off)
            # the pragma NOTE (info, not a violation): a raw sqlite
            # connection defaults to OFF — the APP's engine sets it
            # ON (the 2026-08-24 fix). The finding class is the dead
            # FK TARGET above; this is a watch on the enforcement.
            pragma = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            if not pragma:
                findings.append({
                    "check": "cascade_audit",
                    "severity": "info",
                    "table": "(connection)",
                    "column": None,
                    "message": "PRAGMA foreign_keys is OFF on raw connections (the app engine sets it ON) — watched",
                })
            return findings
        finally:
            conn.close()

    def orphan_scan(self) -> List[Dict[str, Any]]:
        """For every FK that RESOLVES (its target table exists), rows
        whose target row is missing — the ghost-history residue."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            tables = {
                r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            findings = []
            for t in sorted(tables):
                fks = conn.execute(f"PRAGMA foreign_key_list({t})").fetchall()
                for fk in fks:
                    target = fk[2]
                    if target not in tables:
                        continue  # the cascade_audit owns the dead ones
                    col = fk[3]
                    target_pk = fk[4]
                    try:
                        rows = conn.execute(
                            f"SELECT COUNT(*) AS n FROM {t} "
                            f"WHERE {col} NOT IN (SELECT {target_pk} FROM {target})"
                        ).fetchone()
                    except sqlite3.OperationalError:
                        continue  # type mismatches etc — reportable but skip
                    n = rows[0] if rows else 0
                    if n:
                        findings.append({
                            "check": "orphan_scan",
                            "severity": "warning",
                            "table": t,
                            "column": col,
                            "target": target,
                            "count": n,
                            "message": f"{n} orphaned row(s): {t}.{col} → {target}",
                        })
            return findings
        finally:
            conn.close()

    def id_reuse_watch(self) -> List[Dict[str, Any]]:
        """INTEGER-PK tables without AUTOINCREMENT can reuse deleted
        ids. Harmless once orphans are gone — but the sweep watches
        (the ghost-history used exactly this)."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            try:
                seq = {
                    r[0] for r in conn.execute(
                        "SELECT name FROM sqlite_sequence"
                    ).fetchall()
                }
            except sqlite3.OperationalError:
                # NO sqlite_sequence table = NO AUTOINCREMENT anywhere
                # — that IS the finding (every INTEGER-PK table can
                # reuse deleted ids).
                seq = set()
            findings = []
            for t in ["chat_sessions", "agents", "chat_messages"]:
                try:
                    max_id = conn.execute(f"SELECT MAX(id) FROM {t}").fetchone()[0]
                except sqlite3.OperationalError:
                    continue
                if t not in seq:
                    findings.append({
                        "check": "id_reuse_watch",
                        "severity": "info",
                        "table": t,
                        "message": f"{t} has NO AUTOINCREMENT (max id {max_id}) — deleted ids can be reused (harmless now, watched)",
                    })
            return findings
        finally:
            conn.close()

    def log_roll_check(self) -> List[Dict[str, Any]]:
        """The rotated log files: sizes + ages. Flag old/large logs
        that may need rolling or deleting (the user's ask)."""
        if not self.logs_dir.exists():
            return []
        findings = []
        for f in sorted(self.logs_dir.glob("app.log*")):
            try:
                size = f.stat().st_size
                age_days = (__import__("datetime").datetime.now() - __import__("datetime").datetime.fromtimestamp(f.stat().st_mtime)).days
            except OSError:
                continue
            if size > 10 * 1024 * 1024 or age_days > 14:
                findings.append({
                    "check": "log_roll_check",
                    "severity": "info",
                    "file": f.name,
                    "size_mb": round(size / 1024 / 1024, 1),
                    "age_days": age_days,
                    "message": f"{f.name}: {round(size/1024/1024,1)}MB, {age_days}d old — consider rolling/deleting",
                })
        return findings

    def app_zombie_check(self) -> List[Dict[str, Any]]:
        """Orphaned/stray backend processes from the restart churn
        (fuser -k can strand the reloader's children; a killed parent
        reparents its children to init). Reports pid/age/command —
        NEVER auto-kills (the sweep's report-only doctrine)."""
        findings: List[Dict[str, Any]] = []
        try:
            import os as _os
            self_pid = _os.getpid()  # the sweep runs IN the backend — never flag itself
            procs = []
            for pid_dir in Path("/proc").glob("[0-9]*"):
                pid = int(pid_dir.name)
                if pid == self_pid:
                    continue
                try:
                    cmdline = (pid_dir / "cmdline").read_bytes().decode(errors="replace").replace("\0", " ").strip()
                    if "uvicorn" not in cmdline and "app.main:app" not in cmdline:
                        continue
                    stat = (pid_dir / "stat").read_text(errors="replace")
                    ppid = int(stat.split(")")[-1].split()[1]) if ")" in stat else -1
                    age_min = round((time.time() - pid_dir.stat().st_mtime) / 60, 1)
                    procs.append({"pid": pid, "ppid": ppid, "age_min": age_min, "cmd": cmdline[:90]})
                except (OSError, ValueError):
                    continue
            live_pids = {p["pid"] for p in procs}
            for p in procs:
                # an orphan: the parent is dead (reparented to init)
                if p["ppid"] == 1 and int(str(p["age_min"])) > 5:
                    findings.append({
                        "check": "app_zombie_check",
                        "severity": "info",
                        "pid": p["pid"],
                        "age_min": p["age_min"],
                        "message": f"backend pid {p['pid']} reparented to init ({p['age_min']}m) — the restart churn stranded the reloader; verify /health BEFORE killing (it may be the live server)",
                    })
            if len(procs) > 1:
                findings.append({
                    "check": "app_zombie_check",
                    "severity": "info",
                    "pids": [p["pid"] for p in procs],
                    "message": f"{len(procs)} backend processes running — the restart churn may have stranded instances",
                })
        except Exception as e:  # /proc unreadable — never kill the sweep
            findings.append({
                "check": "app_zombie_check",
                "severity": "info",
                "message": f"process scan failed: {e}",
            })
        return findings

    def db_ghost_check(self) -> List[Dict[str, Any]]:
        """THE GHOST ROWS (the user's 2026-08-24 ask): messages in
        the LIVE sessions that PREDATE their session — the id-reuse
        collision class (the session-3 ghosts). Beyond the orphan
        scan (which finds rows with NO session at all)."""
        findings: List[Dict[str, Any]] = []
        try:
            conn = sqlite3.connect(str(self.db_path))
            try:
                rows = conn.execute("""
                    SELECT m.session_id, s.created_at AS sess_created,
                           COUNT(*) AS n, MIN(m.created_at) AS oldest_msg
                    FROM chat_messages m
                    JOIN chat_sessions s ON s.id = m.session_id
                    WHERE m.created_at < s.created_at
                    GROUP BY m.session_id
                """).fetchall()
                for session_id, sess_created, n, oldest in rows:
                    findings.append({
                        "check": "db_ghost_check",
                        "severity": "warning",
                        "session_id": session_id,
                        "ghost_count": n,
                        "message": f"session {session_id}: {n} message(s) predate the session ({oldest} < {sess_created}) — the id-reuse ghost class",
                    })
            finally:
                conn.close()
        except sqlite3.Error as e:
            findings.append({
                "check": "db_ghost_check",
                "severity": "info",
                "message": f"ghost scan failed: {e}",
            })
        return findings

    def ghost_db_files(self) -> List[Dict[str, Any]]:
        """THE GHOST FILES (2026-09-07, the backend/cogitate.db
        lesson): stray/empty .db files under the repo root that
        should not exist. The Aug-30 gap: backend/cogitate.db was
        born when an agent session opened the RELATIVE path
        'cogitate.db' from the backend/ cwd (a connect-only open
        leaves a 0-byte file), and no startup sweep ever scanned
        FILES — this check lives in the audit so every restart
        reports ghosts. READ-ONLY by contract (reports + the rm
        hint, never deletes).

        Semantics mirror the manual twin in
        scripts/core/sweep/backend.py (check_ghost_databases +
        check_stale_cogitate_dbs): known canonical DBs are allowed;
        anything else under the repo root smaller than 1 KB is a
        ghost. Traversal prunes the skip dirs (node_modules, .venv,
        .git, backups, trash, caches) so the startup walk stays
        fast."""
        findings: List[Dict[str, Any]] = []
        repo_root = self.db_path.parent  # the main DB sits at the repo root
        try:
            # the KNOWN stale partial copies (explicit list + reason)
            stale = [
                ("backend/cogitate.db", "stale partial copy — created by scripts using a wrong relative path from backend/"),
                ("backend/cogitate-backup-pre-apikey.db", "stale 0-byte backup artifact — leftover from the API key migration"),
            ]
            stale_paths = set()
            for rel, reason in stale:
                p = repo_root / rel
                if not p.exists():
                    continue
                stale_paths.add(p)
                findings.append({
                    "check": "ghost_db_files",
                    "severity": "warning",
                    "file": rel,
                    "size": p.stat().st_size,
                    "message": f"{rel} ({p.stat().st_size} bytes) — {reason}",
                })

            # the canonical DBs (allowed to exist)
            canonical = {
                self.db_path.resolve(),
                (repo_root / "checkpoints.db").resolve(),
                (repo_root / "data" / "cogitate_docs_en.db").resolve(),
                (repo_root / "backend" / "checkpoints.db").resolve(),
            }
            skip_names = {
                "backups", "trash", ".mypy_cache", "node_modules",
                ".venv", ".git", ".hermes",  # .hermes: the agent home — its DBs are legit
            }
            threshold = 1024  # 1 KB — anything smaller is a ghost
            import os as _os
            for dirpath, dirnames, filenames in _os.walk(repo_root):
                dirnames[:] = [d for d in dirnames if d not in skip_names]
                for fn in filenames:
                    if not fn.endswith(".db"):
                        continue
                    p = Path(dirpath) / fn
                    if p.resolve() in canonical or p in stale_paths:
                        continue
                    try:
                        size = p.stat().st_size
                    except OSError:
                        continue
                    if size >= threshold:
                        continue
                    rel_path = p.relative_to(repo_root)
                    findings.append({
                        "check": "ghost_db_files",
                        "severity": "warning",
                        "file": str(rel_path),
                        "size": size,
                        "message": f"{rel_path} ({size} bytes) — ghost database (zero/near-zero size, should not exist)",
                    })
        except Exception as e:  # the sweep must never die on a scan
            findings.append({
                "check": "ghost_db_files",
                "severity": "info",
                "message": f"ghost file scan failed: {e}",
            })
        return findings

    def log_sweep(self, max_lines: int = 3000, flood_threshold: int = 5,
                  minutes_back: Optional[int] = 60) -> List[Dict[str, Any]]:
        """THE LOG SWEEP (2026-08-25, the user's ask): the recent
        log window's warnings + errors + FLOODING (a large number of
        IDENTICAL logs). The timestamped lines ONLY — the bare
        continuation lines are the multi-line entries' parts (the
        false-flood lesson: the line-based window filter was fooled
        by yesterday's bare continuation lines).

        THE TIME WINDOW (2026-08-25, the user's call): minutes_back
        discounts the OLD errors — only the last N minutes count
        (the sweep is for the RECENT health, not the week's noise).
        None = no time filter (the line cap only)."""
        findings: List[Dict[str, Any]] = []
        try:
            log_file = self.logs_dir / "app.log"
            if not log_file.exists():
                return findings
            lines = log_file.read_text(errors="replace").splitlines()[-max_lines:]
            cutoff = None
            if minutes_back is not None:
                cutoff = datetime.now() - timedelta(minutes=minutes_back)
            warns = errs = 0
            clusters: Dict[tuple[str, str], int] = {}   # (logger, message) -> count
            for ln in lines:
                # the timestamped-only rule (the '2026-08-25 HH:MM:SS |' prefix)
                if len(ln) < 24 or not (ln[:4].isdigit() and ln[4:5] == '-'):
                    continue
                # THE TIME FILTER: the old entries discounted
                if cutoff is not None:
                    try:
                        ts = datetime.strptime(ln[:19], "%Y-%m-%d %H:%M:%S")
                        if ts < cutoff:
                            continue
                    except ValueError:
                        continue
                if "| WARNING" in ln:
                    warns += 1
                elif "| ERROR" in ln or "| CRITICAL" in ln:
                    errs += 1
                else:
                    continue
                # the identity: the logger + the message (the timestamp stripped)
                try:
                    parts = ln.split(" | ")
                    key = (parts[1].strip(), " | ".join(parts[2:])[:160])
                    clusters[key] = clusters.get(key, 0) + 1
                except IndexError:
                    continue
            window_desc = f"last {minutes_back} min" if minutes_back is not None else f"last {max_lines} lines"
            if errs:
                findings.append({
                    "check": "log_sweep", "severity": "warning",
                    "error_count": errs, "window": window_desc,
                    "message": f"{errs} ERROR/CRITICAL line(s) in the {window_desc}",
                })
            if warns:
                findings.append({
                    "check": "log_sweep", "severity": "info",
                    "warning_count": warns, "window": window_desc,
                    "message": f"{warns} WARNING line(s) in the {window_desc}",
                })
            # THE FLOODING: the identical (logger, message) clusters
            for (logger, text), n in sorted(clusters.items(), key=lambda kv: -kv[1]):
                if n >= flood_threshold:
                    findings.append({
                        "check": "log_sweep", "severity": "warning",
                        "flood_count": n, "logger": logger,
                        "message": f"FLOOD: {n}x identical log from {logger}: {text[:110]}",
                    })
        except Exception as e:
            findings.append({
                "check": "log_sweep", "severity": "info",
                "message": f"log sweep failed: {e}",
            })
        return findings

    # ── the run ───────────────────────────────────────────────────

    def run(self) -> Dict[str, Any]:
        """Run every check + summarize. READ-ONLY — reports only."""
        checks: Dict[str, Any] = {
            "cascade_audit": self.cascade_audit(),
            "orphan_scan": self.orphan_scan(),
            "id_reuse_watch": self.id_reuse_watch(),
            "log_roll_check": self.log_roll_check(),
            "app_zombie_check": self.app_zombie_check(),
            "db_ghost_check": self.db_ghost_check(),
            "ghost_db_files": self.ghost_db_files(),
            "log_sweep": self.log_sweep(),
        }
        total = sum(len(v) for v in checks.values())
        # the severity roll-up
        severities: Dict[str, int] = {}
        for findings in checks.values():
            for f in findings:
                s = f.get("severity", "info")
                severities[s] = severities.get(s, 0) + 1
        # THE STATUS SEMANTICS: only WARNING/CRITICAL findings make
        # the sweep 'inconsistent' — INFO findings are watches (the
        # AUTOINCREMENT note), not violations.
        violations = severities.get("warning", 0) + severities.get("critical", 0)
        return {
            "audited_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
            "status": "clean" if violations == 0 else "inconsistent",
            "total_findings": total,
            "violations": violations,
            "severities": severities,
            "checks": checks,
        }

    def render_markdown(self) -> str:
        """The report body (the WorkflowProduct body)."""
        r = self.run()
        lines = [
            "# Integrity Sweep",
            "",
            f"**Status:** {r['status']} — {r['total_findings']} finding(s)",
            f"**Audited at:** {r['audited_at']}",
            "",
        ]
        for check_name, findings in r["checks"].items():
            if not findings:
                continue
            lines.append(f"## {check_name} — {len(findings)} finding(s)")
            for f in findings:
                sev = f.get("severity", "info")
                msg = f.get("message", str(f))
                lines.append(f"- [{sev}] {msg}")
            lines.append("")
        if r["total_findings"] == 0:
            lines.append("_No findings — the integrity surface is clean._")
        return "\n".join(lines)
