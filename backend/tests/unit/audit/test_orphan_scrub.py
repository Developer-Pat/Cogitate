"""The orphan scrub is dry-run by default, confirmed by matching counts, and re-audited after.

THE GUARDRAILS (local/system-sweep/03-scrub.md): dry-run by
default; the typed confirm (the counts must match the live truth);
a DB backup before the real run; the outcome reported (the deleted
counts + the re-audit).
"""

import sqlite3
from pathlib import Path

import pytest

from app.domain.audit.scrub import OrphanScrubService


@pytest.fixture
def orphan_db(tmp_path):
    """A DB with orphaned rows (the ghost residue class)."""
    db = tmp_path / "test.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE agents (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE chat_sessions (id INTEGER PRIMARY KEY, agent_id INTEGER);
        CREATE TABLE chat_messages (id INTEGER PRIMARY KEY, session_id INTEGER);
        CREATE TABLE usage_logs (id INTEGER PRIMARY KEY, session_id INTEGER,
            agent_id INTEGER, provider TEXT, model TEXT, prompt_tokens INTEGER,
            completion_tokens INTEGER, total_tokens INTEGER, cost_usd REAL,
            response_time_ms INTEGER, success BOOLEAN, error_message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE chat_attachments (id INTEGER PRIMARY KEY, session_id INTEGER,
            original_filename TEXT, stored_filename TEXT, file_type TEXT,
            file_size INTEGER, file_path TEXT, mime_type TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
        INSERT INTO agents (id, name) VALUES (1, 'a');
        INSERT INTO chat_sessions (id, agent_id) VALUES (1, 1);
        -- 2 live messages + 3 orphans
        INSERT INTO chat_messages (id, session_id) VALUES (1, 1), (2, 1), (3, 999), (4, 998), (5, 997);
        INSERT INTO usage_logs (id, session_id, agent_id, provider, model, prompt_tokens,
            completion_tokens, total_tokens, cost_usd, success)
            VALUES (1, 1, 1, 'p', 'm', 1, 1, 2, 0, 1), (2, 999, 1, 'p', 'm', 1, 1, 2, 0, 1);
        INSERT INTO chat_attachments (id, session_id, original_filename, stored_filename,
            file_type, file_size, file_path) VALUES (1, 1, 'a', 'a', 'txt', 1, '/x'), (2, 998, 'b', 'b', 'txt', 1, '/y');
        """
    )
    con.commit()
    con.close()
    return db


def test_dry_run_reports_without_touching(orphan_db):
    svc = OrphanScrubService(orphan_db)
    r = svc.scrub(dry_run=True)
    assert r["dry_run"] is True
    assert r["would_delete"]["chat_messages"] == 3
    assert r["would_delete"]["usage_logs"] == 1
    assert r["would_delete"]["chat_attachments"] == 1
    assert r["total"] == 5
    # nothing deleted
    con = sqlite3.connect(orphan_db)
    n = con.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0]
    con.close()
    assert n == 5


def test_real_run_requires_the_confirm(orphan_db):
    svc = OrphanScrubService(orphan_db)
    with pytest.raises(ValueError):
        svc.scrub(dry_run=False, expected_counts=None)


def test_real_run_rejects_the_wrong_counts(orphan_db):
    svc = OrphanScrubService(orphan_db)
    with pytest.raises(ValueError, match="changed"):
        svc.scrub(dry_run=False, expected_counts={"chat_messages": 99})


def test_real_run_deletes_backs_up_reaudits(orphan_db):
    svc = OrphanScrubService(orphan_db)
    r = svc.scrub(dry_run=False, expected_counts={
        "chat_messages": 3, "usage_logs": 1, "chat_attachments": 1,
    })
    assert r["dry_run"] is False
    assert r["deleted"]["chat_messages"] == 3
    assert r["deleted"]["usage_logs"] == 1
    assert r["deleted"]["chat_attachments"] == 1
    assert r["total"] == 5
    assert r["backup"] and Path(r["backup"]).exists()
    assert r["re_audit"]["violations"] == 0

    # the live rows survive; the orphans are gone
    con = sqlite3.connect(orphan_db)
    n = con.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0]
    con.close()
    assert n == 2
