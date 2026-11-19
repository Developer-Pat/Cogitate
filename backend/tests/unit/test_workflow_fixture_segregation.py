"""Workflow fixture segregation — test fixtures kept out of the user library.

The 33 seeded rows are recategorized: test fixtures → testing
namespace (22), user-visible stays clean (monitoring/office-work/
multi-agent-parallel/examples = 11). E2E rules: the monitor family
stays in the user library; test-calculator (the tool-path leg)
lives IN testing. Recategorize, never delete — total stays 33.
"""

import sqlite3

from pathlib import Path

# backend/tests/unit/ → project root is parent×4 (backend/cogitate.db
# is a stray 0-byte file — never connect to it)
from app.core.config import Paths as CorePaths, get_settings
DB_PATH = Path(str(CorePaths.from_settings(get_settings()).shared_db))


class TestSegregation:
    def test_total_unchanged(self):
        con = sqlite3.connect(DB_PATH)
        try:
            total = con.execute("SELECT COUNT(*) FROM workflow_templates").fetchone()[0]
        finally:
            con.close()
        assert total == 36, "the current template count — recategorize, never delete"

    def test_testing_namespace_holds_the_fixtures(self):
        con = sqlite3.connect(DB_PATH)
        try:
            rows = con.execute(
                "SELECT id FROM workflow_templates WHERE category = 'testing'"
            ).fetchall()
            ids = {r[0] for r in rows}
        finally:
            con.close()
        # the fixtures that belong in testing
        expected = {
            "test-llm-connection", "test-llm-chain", "test-llm-summary",
            "test-llm-comparison", "test-deepseek", "test-openrouter",
            "agent-hello", "agent-math", "agent-code-review", "agent-summary",
            "test-calculator", "test-datetime", "test-file-info",
            "test-text-tools", "test-todo-list",
            "creative-chain-triple", "research-enhanced-writer",
            "story-collab-hunter-editor", "story-enhance-scheherazade-tooled",
            "test-basic", "test-long-running", "simple-hello",
        }
        assert ids == expected, f"mismatch: missing={expected - ids} extra={ids - expected}"

    def test_monitor_family_stays_in_the_user_library(self):
        # the E2E flagship (study 06: ≥1 end-to-end workflow-system
        # test stays in the user library)
        con = sqlite3.connect(DB_PATH)
        try:
            rows = con.execute(
                "SELECT id FROM workflow_templates WHERE category = 'monitoring'"
            ).fetchall()
            ids = {r[0] for r in rows}
        finally:
            con.close()
        # system-audit joined the family (2026-08-20): it IS a
        # system monitor — the system-up sanity check
        assert ids == {"rss-monitor", "market-watch", "readiness-check", "system-audit"}

    def test_tool_path_fixture_lives_in_testing(self):
        # the second E2E leg (study 06: ≥1 tool-path fixture in testing)
        con = sqlite3.connect(DB_PATH)
        try:
            row = con.execute(
                "SELECT category FROM workflow_templates WHERE id = 'test-calculator'"
            ).fetchone()
        finally:
            con.close()
        assert row and row[0] == "testing"

    def test_user_visible_categories_are_clean(self):
        # no test-fixture categories leak into the user surface
        con = sqlite3.connect(DB_PATH)
        try:
            rows = con.execute(
                "SELECT DISTINCT category FROM workflow_templates "
                "WHERE category != 'testing'"
            ).fetchall()
        finally:
            con.close()
        cats = {r[0] for r in rows}
        assert cats == {"monitoring", "office-work", "multi-agent-parallel", "examples", "deep-agents"}
