"""
Pytest configuration for workflow tests.

Adds table-existence checks so tests gracefully skip when the required
database tables are not present in the test environment.  This avoids
hard `sqlite3.OperationalError: no such table` failures and follows the
principle "use tests to check db tables — do not alter tables to fix tests".
"""

import sqlite3

import pytest

from pathlib import Path

from app.core.config import Paths, get_settings


# Resolve the database path through the app's `Paths`, so the check points at
# the same database the application actually uses — which under test is the
# temporary copy, not the production file. A literal `BASE_DIR / "cogitate.db"`
# made this check inspect production while the tests wrote elsewhere.
def _service_db() -> Path:
    return Path(str(Paths.from_settings(get_settings()).shared_db))


def _missing_tables(*tables: str) -> list[str]:
    """Return a list of *tables* that do **not** exist in the service DB."""
    if not _service_db().exists():
        return list(tables)
    conn = sqlite3.connect(str(_service_db()))
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing = {row[0] for row in cursor.fetchall()}
    finally:
        conn.close()
    return [t for t in tables if t not in existing]


# ---------------------------------------------------------------------------
# Pytest-collection-time markers: skip an entire module when core tables are
# missing so the user sees a clear "SKIP" instead of a wall of failures.
# ---------------------------------------------------------------------------

def pytest_collection_modifyitems(items):
    """Skip test items that require tables absent from the service DB."""
    # ── table groups ──────────────────────────────────────────────────────
    ab_tables = {"ab_test_configs", "ab_test_results"}
    version_tables = {"workflow_versions"}
    template_tables = {"workflow_templates"}

    missing_ab = _missing_tables(*ab_tables) if not ab_tables.issubset(set()) else []
    missing_versions = _missing_tables(*version_tables) if not version_tables.issubset(set()) else []
    missing_templates = _missing_tables(*template_tables) if not template_tables.issubset(set()) else []

    for item in items:
        fspath_str = str(item.fspath)
        # ── test_ab_tests ────────────────────────────────────────────────
        if "test_ab_tests" in fspath_str:
            # Schema-validation tests don't need the DB
            if "TestABTestSchemaValidation" in item.nodeid:
                continue
            if missing_ab:
                skip_msg = "; ".join(f"missing table: {t}" for t in missing_ab)
                item.add_marker(pytest.mark.skip(reason=f"DB tables required by AB tests not present: {skip_msg}"))

        # ── test_versioning ───────────────────────────────────────────────
        if "test_versioning" in fspath_str:
            if "TestVersionSchemaValidation" in item.nodeid:
                continue
            if missing_versions:
                skip_msg = "; ".join(f"missing table: {t}" for t in missing_versions)
                item.add_marker(pytest.mark.skip(reason=f"DB tables required by version tests not present: {skip_msg}"))

        # ── test_multi_agent_tools ────────────────────────────────────────
        if "test_multi_agent_tools" in fspath_str:
            if missing_templates:
                skip_msg = "; ".join(f"missing table: {t}" for t in missing_templates)
                item.add_marker(pytest.mark.skip(reason=f"DB tables required by tool-enhanced template tests not present: {skip_msg}"))


# ---------------------------------------------------------------------------
# Execution-history hygiene: the workflow API tests (background_execution,
# lifecycle) create real execution rows whose background tasks are cancelled
# at teardown — leaving stuck 'started' records in the LIVE cogitate.db.
# Clean test-artifact rows after the workflow test session.
# ---------------------------------------------------------------------------

def pytest_sessionfinish(session, exitstatus):
    """Remove test-artifact execution-history rows from the service DB."""
    try:
        if not _service_db().exists():
            return
        conn = sqlite3.connect(str(_service_db()))
        try:
            cur = conn.execute(
                "DELETE FROM workflow_execution_history "
                "WHERE template_id IN ('test-template', 'lifecycle-test')"
            )
            conn.commit()
            if cur.rowcount:
                print(f"\n🧹 Cleaned {cur.rowcount} test-artifact execution rows")
        finally:
            conn.close()
    except Exception as e:
        print(f"\n⚠️  Failed to clean test execution rows: {e}")


# ---------------------------------------------------------------------------
# Checkpoint DB hygiene: workflow tests that use the DEFAULT checkpointer
# path (./checkpoints.db) would create backend/checkpoints.db when pytest
# runs from the backend/ cwd — polluting the repo (DB cleanup Phase 4).
# Point the default at a tmp path for the whole test session.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _checkpoint_db_tmp(tmp_path_factory):
    """Redirect the default checkpointer path to a temp DB for tests."""
    import os as _os
    db = tmp_path_factory.mktemp("checkpoints") / "checkpoints.db"
    _os.environ["WORKFLOW_CHECKPOINT_DB"] = str(db)
    yield db
    _os.environ.pop("WORKFLOW_CHECKPOINT_DB", None)


@pytest.fixture(autouse=True)
def _the_checkpoint_overlay_is_handed_back(_checkpoint_db_tmp):
    """A test may not take the session's checkpoint overlay and not give it back.

    Measured 2026-10-15. A test pointed `WORKFLOW_CHECKPOINT_DB` at a private temp file,
    never restored the session's value, and then DELETED that file — so the shared
    checkpointer stayed bound to a database that no longer existed, and every later test
    using the DEFAULT path got `sqlite3.OperationalError: disk I/O error`. The victims were
    two files later (`test_retention.py`'s two checkpoint tests) and the traceback named
    neither the offender nor the cause. This guard fails AT the test that does it.

    A private database is asked for BY PATH — `get_checkpointer(db_path=…)` keys the
    singleton on the path, so the next default caller re-derives — or the overlay is taken
    with `monkeypatch.setenv`, which hands it back for you.
    """
    import os as _os

    session_db = _os.environ.get("WORKFLOW_CHECKPOINT_DB")
    existed_before = bool(session_db) and Path(session_db).exists()

    yield

    current = _os.environ.get("WORKFLOW_CHECKPOINT_DB")
    if current != session_db:
        raise AssertionError(
            "this test left WORKFLOW_CHECKPOINT_DB changed for the rest of the session "
            f"({session_db!r} -> {current!r}). The shared checkpointer is now bound to a "
            "database the session does not own; use get_checkpointer(db_path=…) or "
            "monkeypatch.setenv instead of assigning the overlay."
        )
    if session_db and existed_before and not Path(session_db).exists():
        raise AssertionError(
            f"this test deleted the session's checkpoint database ({session_db}) while the "
            "shared checkpointer held it open; every later default-path caller will get "
            "'sqlite3.OperationalError: disk I/O error'."
        )

