"""Unit tests for the agent health scan (check_agent_health.py).

Covers:
- Broken provider (missing) → FAIL
- Inactive provider → FAIL
- Unresolvable model → FAIL
- Valid config → OK
- Recent usage failures → WARN (does not fail gate)
"""

import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Test file: backend/tests/unit/providers/ → up 5 levels = project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent  # path-ok: locates the SOURCE tree to read source files; only DATA follows the installation root
sys.path.insert(0, str(_PROJECT_ROOT / "scripts" / "core"))
import check_agent_health  # noqa: E402


@pytest.fixture
def health_db(tmp_path):
    """Build a minimal cogitate.db-shaped database."""
    db = tmp_path / "cogitate.db"
    conn = sqlite3.connect(db)
    _today = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
    conn.executescript(
        """
        CREATE TABLE providers (
            id INTEGER PRIMARY KEY, name TEXT, is_active INTEGER
        );
        CREATE TABLE agents (
            id INTEGER PRIMARY KEY, name TEXT, provider TEXT, model TEXT,
            is_active INTEGER, is_builtin INTEGER, health_dismissed_at TEXT
        );
        CREATE TABLE provider_model_cache (
            id INTEGER PRIMARY KEY, provider_id INTEGER, model_id TEXT
        );
        CREATE TABLE curated_models (
            id INTEGER PRIMARY KEY, provider_id INTEGER, model_id TEXT
        );
        CREATE TABLE usage_logs (
            id INTEGER PRIMARY KEY, agent_id INTEGER, provider TEXT, model TEXT,
            success INTEGER, error_message TEXT, created_at TEXT
        );
        """
    )
    conn.execute(
        "INSERT INTO providers (id, name, is_active) VALUES (1, 'deepseek', 1), (2, 'ollama', 0)"
    )
    conn.execute(
        "INSERT INTO provider_model_cache (provider_id, model_id) VALUES (1, 'deepseek-v4-flash')"
    )
    conn.execute(
        "INSERT INTO agents (id, name, provider, model, is_active, is_builtin) VALUES "
        "(1, 'Healthy', 'deepseek', 'deepseek-v4-flash', 1, 0),"
        "(2, 'Bad Provider', 'nonexistent-provider', 'x', 1, 0),"
        "(3, 'Bad Model', 'deepseek', 'deepseek-v99-nope', 1, 0),"
        "(4, 'Inactive Prov', 'ollama', 'llama3.2', 1, 0),"
        "(5, 'Recent Failures', 'deepseek', 'deepseek-v4-flash', 1, 0)"
    )
    conn.execute(
        "INSERT INTO usage_logs (agent_id, provider, model, success, error_message, created_at) "
        "VALUES (5, 'deepseek', 'deepseek-v4-flash', 0, 'Rate limit', ?)",
        (_today,),
    )
    conn.commit()
    conn.close()
    return db


def _statuses(db_path):
    """Run the scan and return {agent_name: status}."""
    reports = check_agent_health.check_agents(db_path)
    return {r["name"]: r["status"] for r in reports}


class TestAgentHealthScan:
    """Unit tests for the health scan logic."""

    def test_healthy_agent_ok(self, health_db):
        """A valid provider/model with no failures is OK (not reported)."""
        statuses = _statuses(health_db)
        assert "Healthy" not in statuses  # ok agents are excluded by default

    def test_missing_provider_fails(self, health_db):
        """An agent whose provider doesn't exist → FAIL."""
        statuses = _statuses(health_db)
        assert statuses.get("Bad Provider") == "fail"

    def test_inactive_provider_fails(self, health_db):
        """An agent on an inactive provider → FAIL."""
        statuses = _statuses(health_db)
        assert statuses.get("Inactive Prov") == "fail"

    def test_unresolvable_model_fails(self, health_db):
        """An agent whose model isn't in cache/curated → FAIL."""
        statuses = _statuses(health_db)
        assert statuses.get("Bad Model") == "fail"

    def test_recent_failures_warns(self, health_db):
        """Usage failures on valid config → WARN (not FAIL)."""
        statuses = _statuses(health_db)
        assert statuses.get("Recent Failures") == "warn"

    def test_include_healthy_reports_ok(self, health_db):
        """--include-healthy surfaces OK agents too."""
        reports = check_agent_health.check_agents(health_db, include_healthy=True)
        statuses = {r["name"]: r["status"] for r in reports}
        assert statuses.get("Healthy") == "ok"
