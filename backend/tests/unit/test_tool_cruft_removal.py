"""Tool cruft removal — no dead rows, dangling references, or placeholder prose.

The dead tools and layers are gone — verified at the DB, registry,
and code levels so they can't silently return.

- 9 cruft tools: removed from the tools table (not NULLed)
- tool-crib: handler + registration + skill instructions gone
- toolbox assignment: service methods + router endpoints + frontend
  service methods gone (the many-to-many layer, study 08)
- Boris-era description prose: gone from DB + seed script
"""

import sqlite3
from pathlib import Path

import pytest

from app.domain.tools.registry import init_default_registry

# The shared DATABASE comes from the resolver — under test that is the temporary
# copy, which is the whole point.
from app.core.config import Paths, get_settings

LIVE_DB = Path(str(Paths.from_settings(get_settings()).shared_db))

# ROOT is different, and deliberately a parent-walk: this one locates the SOURCE
# tree (frontend/, backend/) to read source files in "this should be gone"
# assertions. Source lives where it lives; only DATA follows the installation.
ROOT = Path(__file__).parent.parent.parent.parent  # path-ok: locates the SOURCE tree to read source files; only DATA follows the installation root

CRUFT = {
    "boris-file-display", "boris-report-writer", "calc_e2e_live",
    "calc_test", "calculator_e2e", "check_schema", "echo",
    "test-tool-1", "tool-crib",
}


class TestDBCruftGone:
    def test_cruft_rows_absent(self):
        con = sqlite3.connect(LIVE_DB)
        try:
            rows = con.execute(
                "SELECT slug FROM tools WHERE slug IN ("
                + ",".join("'" + s + "'" for s in CRUFT) + ")"
            ).fetchall()
        finally:
            con.close()
        assert rows == [], f"cruft tools still in DB: {[r[0] for r in rows]}"

    def test_no_dangling_tool_references(self):
        con = sqlite3.connect(LIVE_DB)
        try:
            for t in ["agent_tools", "team_tools", "tool_collection_permissions"]:
                n = con.execute(
                    f"SELECT COUNT(*) FROM {t} WHERE tool_id NOT IN (SELECT id FROM tools)"
                ).fetchone()[0]
                assert n == 0, f"{t} has {n} dangling tool_id refs"
        finally:
            con.close()

    def test_no_boris_prose_in_descriptions(self):
        con = sqlite3.connect(LIVE_DB)
        try:
            n = con.execute(
                "SELECT COUNT(*) FROM tools WHERE description LIKE '%boris%' "
                "OR description LIKE '%ouroboros%'"
            ).fetchone()[0]
        finally:
            con.close()
        assert n == 0


class TestRegistryClean:
    def test_crib_not_registered(self):
        reg = init_default_registry()
        assert "tool-crib" not in reg._tools
        assert "echo" not in reg._tools

    def test_no_crib_refs_in_handlers(self):
        import pathlib
        # (parens, not a backslash: a comment cannot follow a line continuation)
        builtin_dir = (
            pathlib.Path(__file__).parent.parent.parent.parent  # path-ok: locates the SOURCE tree to read source files; only DATA follows the installation root
            / "backend/app/domain/tools/builtin"
        )
        for py in builtin_dir.glob("*.py"):
            text = py.read_text(errors="replace")
            assert "tool-crib" not in text, f"crib ref in {py.name}"


class TestToolboxLayerGone:
    def test_service_methods_gone(self):
        from app.domain.tools import team_tools_service
        src = open(team_tools_service.__file__).read()
        assert "assign_toolbox_to_team" not in src
        assert "remove_toolbox_from_team" not in src

    def test_router_endpoints_gone(self):
        import app.api.v1.teams.router as r
        src = open(r.__file__).read()
        assert "toolboxes" not in src

    def test_frontend_service_methods_gone(self):
        svc = ROOT / "frontend/src/services/domain/TeamToolService.ts"
        src = svc.read_text(errors="replace")
        assert "assignToolboxToTeam" not in src
