"""The integrity audit finds dead foreign keys, ghost rows and oversized logs.

Each check must find a SEEDED violation + a clean DB yields zero
findings (no false positives).
"""

import sqlite3
from pathlib import Path

import pytest

from app.domain.audit.integrity import IntegrityAudit


@pytest.fixture
def clean_db(tmp_path):
    """A clean DB: sessions + messages + agents, all consistent."""
    db = tmp_path / "test.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE agents (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE chat_sessions (id INTEGER PRIMARY KEY, agent_id INTEGER,
            FOREIGN KEY(agent_id) REFERENCES agents(id));
        CREATE TABLE chat_messages (id INTEGER PRIMARY KEY, session_id INTEGER,
            FOREIGN KEY(session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE);
        INSERT INTO agents (id, name) VALUES (1, 'a'), (2, 'b');
        INSERT INTO chat_sessions (id, agent_id) VALUES (1, 1), (2, 2);
        INSERT INTO chat_messages (id, session_id) VALUES (1, 1), (2, 2);
        """
    )
    con.commit()
    con.close()
    return db


@pytest.fixture
def dirty_db(tmp_path):
    """A DB with the GHOST-HISTORY class seeded: an orphaned
    message (a session that no longer exists) + a dead FK target."""
    db = tmp_path / "dirty.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE agents (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE chat_sessions (id INTEGER PRIMARY KEY, agent_id INTEGER,
            FOREIGN KEY(agent_id) REFERENCES agents(id));
        -- the dead FK target class: messages point at a GONE table
        CREATE TABLE chat_messages (id INTEGER PRIMARY KEY, session_id INTEGER,
            FOREIGN KEY(session_id) REFERENCES "chat_sessions_old"(id) ON DELETE CASCADE);
        INSERT INTO agents (id, name) VALUES (1, 'a');
        INSERT INTO chat_sessions (id, agent_id) VALUES (1, 1);
        INSERT INTO chat_messages (id, session_id) VALUES (1, 999);
        """
    )
    con.commit()
    con.close()
    return db


def test_clean_db_zero_findings(clean_db):
    audit = IntegrityAudit(clean_db)
    r = audit.run()
    # a clean DB may carry INFO watches (the AUTOINCREMENT note, the
    # pragma note) — but ZERO violations: the status is clean.
    assert r["status"] == "clean"
    assert r["violations"] == 0
    assert "critical" not in r["severities"]
    assert "warning" not in r["severities"]


def test_cascade_audit_finds_the_dead_fk_target(dirty_db):
    audit = IntegrityAudit(dirty_db)
    findings = audit.cascade_audit()
    hits = [f for f in findings if "chat_sessions_old" in f.get("message", "")]
    assert hits, "the dead FK target must be reported"
    assert hits[0]["severity"] == "critical"


def test_orphan_scan_finds_the_ghost_rows(dirty_db):
    # the dead FK target means the orphan scan SKIPS it (the cascade
    # audit owns it) — the orphan seed is unreachable here. Instead
    # verify the scan reports a REAL orphan on a resolvable FK.
    import sqlite3
    db = dirty_db
    con = sqlite3.connect(db)
    con.execute("ALTER TABLE chat_messages RENAME TO chat_messages_old")
    con.execute(
        'CREATE TABLE chat_messages (id INTEGER PRIMARY KEY, session_id INTEGER,'
        ' FOREIGN KEY(session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE)'
    )
    con.execute("INSERT INTO chat_messages (id, session_id) VALUES (1, 999)")
    con.commit()
    con.close()

    audit = IntegrityAudit(db)
    findings = audit.orphan_scan()
    hits = [f for f in findings if f["table"] == "chat_messages"]
    assert hits
    assert hits[0]["count"] >= 1


def test_id_reuse_watch_reports_no_autoincrement(clean_db):
    audit = IntegrityAudit(clean_db)
    findings = audit.id_reuse_watch()
    # the fixture's tables have no AUTOINCREMENT (no sqlite_sequence)
    assert any("NO AUTOINCREMENT" in f.get("message", "") for f in findings)


def test_log_roll_check_flags_large_logs(tmp_path):
    # a stub logs dir with a big + stale log
    logs = tmp_path / "logs"
    logs.mkdir()
    big = logs / "app.log.2"
    big.write_bytes(b"x" * (11 * 1024 * 1024))  # 11MB
    stale = logs / "app.log.5"
    stale.write_text("old")
    # age the stale one
    import os
    import time
    old = time.time() - (20 * 86400)
    os.utime(stale, (old, old))

    audit = IntegrityAudit(tmp_path / "nodb.db", logs)
    findings = audit.log_roll_check()
    names = {f["file"] for f in findings}
    assert "app.log.2" in names
    assert "app.log.5" in names

def test_db_ghost_check_finds_predating_messages(tmp_path):
    """A message that PREDATES its session is the ghost class the
    sweep must report (the id-reuse collision)."""
    import sqlite3
    from datetime import datetime, timedelta
    from app.domain.audit.integrity import IntegrityAudit

    db = tmp_path / "ghost.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE chat_sessions (id INTEGER PRIMARY KEY, title TEXT, created_at TEXT)")
    conn.execute("CREATE TABLE chat_messages (id INTEGER PRIMARY KEY, session_id INTEGER, role TEXT, content TEXT, created_at TEXT)")
    now = datetime.utcnow()
    # the session created NOW; the message created an HOUR EARLIER (the ghost)
    conn.execute("INSERT INTO chat_sessions VALUES (1, 's', ?)", (now.isoformat(),))
    conn.execute("INSERT INTO chat_messages VALUES (1, 1, 'assistant', 'ghost', ?)", ((now - timedelta(hours=1)).isoformat(),))
    # a legit message AFTER the session
    conn.execute("INSERT INTO chat_messages VALUES (2, 1, 'assistant', 'live', ?)", (now.isoformat(),))
    conn.commit()
    conn.close()

    findings = IntegrityAudit(db).db_ghost_check()
    assert len(findings) == 1
    assert findings[0]["ghost_count"] == 1
    assert findings[0]["severity"] == "warning"


def test_run_includes_the_new_checks(tmp_path):
    """The run() aggregates the zombie + ghost checks (the keys
    present, the sweep reports, never repairs)."""
    import sqlite3
    from app.domain.audit.integrity import IntegrityAudit

    db = tmp_path / "r.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE chat_sessions (id INTEGER PRIMARY KEY, title TEXT, created_at TEXT)")
    conn.execute("CREATE TABLE chat_messages (id INTEGER PRIMARY KEY, session_id INTEGER, role TEXT, content TEXT, created_at TEXT)")
    conn.commit()
    conn.close()

    result = IntegrityAudit(db).run()
    assert "app_zombie_check" in result["checks"]
    assert "db_ghost_check" in result["checks"]
    assert "ghost_db_files" in result["checks"]

def test_log_sweep_counts_and_floods(tmp_path):
    """The log sweep: the warnings/errors counted, the IDENTICAL
    clusters flagged as floods, the timestamped-only rule applied
    (the bare continuation lines excluded)."""
    from app.domain.audit.integrity import IntegrityAudit

    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "app.log").write_text(
        "2026-08-25 10:00:00 | INFO     | app.x | hello\n"
        "2026-08-25 10:00:01 | WARNING  | app.x | slow thing\n"
        "2026-08-25 10:00:02 | ERROR    | app.x | boom\n"
        # the flood: 6 identical errors
        + "2026-08-25 10:00:03 | ERROR    | app.y | same failure\n" * 6
        # the bare continuation lines (the false-flood lesson — excluded)
        + "Traceback (most recent call last):\n"
        + "raise ValueError('x')\n",
        encoding="utf-8",
    )

    # THE TIME WINDOW (2026-08-26): the default minutes_back=60
    # discounts the fixture's yesterday-timestamped lines entirely —
    # the count-test wants them all, so the filter is off.
    findings = IntegrityAudit(tmp_path / "x.db", logs_dir=logs).log_sweep(minutes_back=None)
    by_check = {}
    for f_ in findings:
        by_check[f_.get("message", "")[:40]] = f_
    # the counts (the 1 boom + the 6 flood errors = 7; 1 warning)
    assert any("7 ERROR/CRITICAL" in f_.get("message", "") for f_ in findings)
    assert any("1 WARNING" in f_.get("message", "") for f_ in findings)
    # the flood (6x identical)
    floods = [f_ for f_ in findings if "FLOOD" in f_.get("message", "")]
    assert len(floods) == 1
    assert floods[0]["flood_count"] == 6


def test_run_includes_the_log_sweep(tmp_path):
    """The run() aggregates the log sweep (the keys present)."""
    import sqlite3
    from app.domain.audit.integrity import IntegrityAudit

    db = tmp_path / "r2.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE chat_sessions (id INTEGER PRIMARY KEY, title TEXT, created_at TEXT)")
    conn.execute("CREATE TABLE chat_messages (id INTEGER PRIMARY KEY, session_id INTEGER, role TEXT, content TEXT, created_at TEXT)")
    conn.commit()
    conn.close()

    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "app.log").write_text("2026-08-25 10:00:01 | WARNING  | app.x | slow\n", encoding="utf-8")

    result = IntegrityAudit(db, logs_dir=logs).run()
    assert "log_sweep" in result["checks"]

def test_log_sweep_minutes_back_discounts_old_entries(tmp_path):
    """The TIME WINDOW (2026-08-25): the minutes_back discounts
    the OLD errors — a 2-hour-old error is NOT in the last-hour
    sweep; a fresh one is."""
    from datetime import datetime, timedelta
    from app.domain.audit.integrity import IntegrityAudit

    now = datetime.now()
    old = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    fresh = (now - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")

    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "app.log").write_text(
        f"{old} | ERROR    | app.old | ancient failure\n"
        f"{fresh} | ERROR    | app.fresh | new failure\n",
        encoding="utf-8",
    )

    # the 60-minute window: only the fresh error counts
    findings = IntegrityAudit(tmp_path / "x.db", logs_dir=logs).log_sweep(minutes_back=60)
    errs = [f_ for f_ in findings if "ERROR/CRITICAL" in f_.get("message", "")]
    assert len(errs) == 1
    assert "1 ERROR/CRITICAL" in errs[0]["message"]
    assert "60 min" in errs[0]["message"]


def test_ghost_db_files_finds_the_stray_file(tmp_path):
    """THE GHOST FILES (2026-09-07): a 0-byte stray .db under the
    repo root must be reported — the backend/cogitate.db class
    (created by a relative-path connect from the wrong cwd). The
    KNOWN stale path carries its descriptive reason; the unknown
    stray is flagged by size."""
    import sqlite3
    from app.domain.audit.integrity import IntegrityAudit

    db = tmp_path / "main.db"  # the canonical main DB (allowed)
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    # the KNOWN stale partial copy (the backend/cogitate.db class)
    stale = tmp_path / "backend" / "cogitate.db"
    stale.parent.mkdir()
    stale.write_bytes(b"")
    # an UNKNOWN stray ghost (not on the explicit list)
    stray = tmp_path / "stray.db"
    stray.write_bytes(b"")

    findings = IntegrityAudit(db).ghost_db_files()
    msgs = [f["message"] for f in findings]
    assert any("backend/cogitate.db" in m and "stale partial copy" in m for m in msgs)
    assert any("stray.db" in m and "ghost database" in m for m in msgs)
    # the main DB itself is canonical — never flagged
    assert all("main.db" not in m for m in msgs)
    assert all(f["severity"] == "warning" for f in findings)


def test_ghost_db_files_clean_repo_yields_nothing(tmp_path):
    """A repo containing only the canonical DB yields zero ghost
    findings (no false positives)."""
    import sqlite3
    from app.domain.audit.integrity import IntegrityAudit

    db = tmp_path / "main.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    assert IntegrityAudit(db).ghost_db_files() == []
