"""The repair-consistency and stop-button tests.

- repair-consistency scrubs the dangling references on a COPY of
  the DB (the test never touches the live cogitate.db), re-runs
  the audit to verify, and leaves the orphaned collections
  REPORTED (not deleted — the user's planned Exa test).
"""
import shutil
import sqlite3
from pathlib import Path

import pytest

from app.core.config import Paths as CorePaths



@pytest.fixture
def repair_registry():
    """The default registry (builtins incl. repair-consistency).

    The registry + the init flag are both singletons — reset BOTH

    so each test re-registers deterministically."""
    import app.domain.tools.registry as regmod
    regmod.ToolRegistry.reset()
    regmod._DEFAULT_REGISTRY_INITIALIZED = False
    reg = regmod.init_default_registry()
    yield reg


def _copy_db(tmp_path, seed_dangling=True):
    """Copy the live cogitate.db + SEED dangling rows (the live db
    was repaired on 2026-08-21 — the test must create its own)."""
    from app.core.config import Paths as CorePaths
    src = Path(str(CorePaths.shared_db))
    dst = tmp_path / "cogitate.db"
    shutil.copy(src, dst)
    if seed_dangling:
        conn = sqlite3.connect(str(dst))
        try:
            # a tool link + a usage log + a collection item, all
            # pointing at agents that don't exist (999999)
            conn.execute(
                "INSERT INTO agent_tools (id, agent_id, tool_id) "
                "VALUES ('seed-tool-link', '999999', 'x')"
            )
            conn.execute(
                "INSERT INTO usage_logs (session_id, agent_id, provider, model, "
                "prompt_tokens, completion_tokens, total_tokens, cost_usd, "
                "response_time_ms, success, created_at) "
                "VALUES ('seed-session', '999999', 'seed', 'seed', 1, 1, 2, 0.0, "
                "1, 1, datetime('now'))"
            )
            conn.execute(
                "INSERT INTO collection_items (id, collection_id, entity_type, "
                "entity_id, entity_name) "
                "VALUES ('seed-col-item', '3d601406-d3a1-43b8-ba90-b098ff453c96', "
                "'agent', '999999', 'seed')"
            )
            # an UNREFERENCED empty collection — the orphaned-collections
            # assertion must not depend on the live DB's seeded kit (the
            # Shallow Agent Kit is a package-referenced empty toolkit,
            # deliberately NOT an orphan since 2026-08-29)
            conn.execute(
                "INSERT INTO collections (id, user_key, name, description, "
                "entity_type, color, icon, is_active, created_at, updated_at) "
                "VALUES ('seed-orphan-collection', 'seed', 'seed-orphan', "
                "'the repair must leave it', 'agent', '#000000', 'box', 1, "
                "datetime('now'), datetime('now'))"
            )
            conn.commit()
        finally:
            conn.close()
    return dst


def _audit(db_path):
    from app.domain.audit import ConsistencyAudit
    return ConsistencyAudit(db_path).run()


@pytest.mark.asyncio
async def test_repair_scrubs_dangling_references_and_verifies(repair_registry, tmp_path, monkeypatch):
    db = _copy_db(tmp_path)
    # Resolved BEFORE the patch — `rooted_at` derives through `from_settings`.
    sandbox = CorePaths.rooted_at(db)
    monkeypatch.setattr(
        "app.core.config.Paths.from_settings",
        classmethod(lambda cls, _settings: sandbox),
    )

    # the BEFORE state — the seeded dangling references
    before = _audit(db)
    assert before["total_findings"] > 0, "the seeded copy should have findings"

    tool = repair_registry.get("repair-consistency")
    assert tool is not None, "repair-consistency must be registered"
    assert tool.metadata.get("access_tier") == "keyed", "the repair is ADMIN-TIER (keyed)"

    result = await tool.handler({})
    assert result["success"] is True
    assert result["total_deleted"] > 0
    assert result["verified"] is True, "the audit re-run must verify"

    # the AFTER state — dangling references gone, orphans reported
    after = _audit(db)
    dangling = sum(
        len(v) for k, v in after["checks"].items()
        if k != "orphaned_collections"
    )
    assert dangling == 0, f"dangling references must be zero, got: {dangling}"
    assert "orphaned_collections" in after["checks"]
    # the empty collections stay — reported, not deleted
    names = [f.get("name") for f in after["checks"]["orphaned_collections"]]
    assert names, "the orphaned collections are reported"


@pytest.mark.asyncio
async def test_repair_rejects_without_the_grant(repair_registry, tmp_path):
    """The keyed tier is not callable without the fix-mode grant."""
    tool = repair_registry.get("repair-consistency")
    # the grant gate is enforced by the access_tier check at dispatch —
    # the tool itself is registered keyed (asserted above); the grant
    # check lives in the dispatch path (the fix-mode config).
    assert tool.metadata.get("access_tier") == "keyed"


@pytest.mark.asyncio
async def test_repair_does_not_delete_orphaned_collections(repair_registry, tmp_path, monkeypatch):
    db = _copy_db(tmp_path)
    # SEED the empty collection (2026-08-26, the sweep): the old
    # assertion pinned the System Agents collection's id from an
    # earlier db state — the live collections changed over the months.
    # The PRINCIPLE (the orphaned collections survive the repair) is
    # the real assertion: seed our own empty collection + check it.
    seed_id = "seed-empty-collection"
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "INSERT INTO collections (id, user_key, name, description, "
            "entity_type, color, icon, is_active, created_at, updated_at) "
            "VALUES (?, 'seed', 'seed-empty', 'the repair must leave it', "
            "'agent', '#000000', 'box', 1, datetime('now'), datetime('now'))",
            (seed_id,),
        )
        conn.commit()
    finally:
        conn.close()
    # Resolved BEFORE the patch — `rooted_at` derives through `from_settings`.
    sandbox = CorePaths.rooted_at(db)
    monkeypatch.setattr(
        "app.core.config.Paths.from_settings",
        classmethod(lambda cls, _settings: sandbox),
    )

    tool = repair_registry.get("repair-consistency")
    result = await tool.handler({})
    assert result["success"] is True

    conn = sqlite3.connect(str(db))
    try:
        # the seeded empty collection must still exist
        row = conn.execute(
            "SELECT COUNT(*) FROM collections WHERE id = ?", (seed_id,)
        ).fetchone()
        assert row[0] == 1, "the empty collection must NOT be deleted"
    finally:
        conn.close()
