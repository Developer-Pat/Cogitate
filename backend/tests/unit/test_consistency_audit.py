"""The consistency audit finds dangling agent and kit references by id and by name, read-only.

- the audit is READ-ONLY (reports; never mutates)
- the dangling-agent-reference checks find rows pointing at
  missing agents
- the 'external' pseudo-id (the Exa surface's grants) is NOT
  flagged — it is a known legitimate reference
- the workflow-name-reference check catches configs naming
  missing agents (the class an id-walk cannot catch)
"""
import json
import sqlite3
from pathlib import Path

import pytest

from app.domain.audit import ConsistencyAudit


@pytest.fixture
def audit_db(tmp_path):
    """A tiny throwaway DB with dangling references."""
    db = tmp_path / "audit.db"
    con = sqlite3.connect(str(db))
    con.executescript("""
        CREATE TABLE agents (id TEXT PRIMARY KEY, name TEXT, deleted_at TEXT);
        CREATE TABLE agent_tools (agent_id TEXT, tool_id TEXT);
        CREATE TABLE usage_logs (agent_id TEXT);
        CREATE TABLE agent_tool_grants (agent_id TEXT);
        CREATE TABLE tools (id TEXT PRIMARY KEY);
        CREATE TABLE collections (id TEXT PRIMARY KEY, name TEXT);
        CREATE TABLE collection_items (id INTEGER PRIMARY KEY, collection_id TEXT, entity_id TEXT, entity_type TEXT);
        CREATE TABLE workflow_compositions (id TEXT PRIMARY KEY, name TEXT, config_json TEXT);
        INSERT INTO agents VALUES ('1', 'Meta', NULL);
        INSERT INTO agents VALUES ('2', 'Bob', NULL);
        INSERT INTO agent_tools VALUES ('3', 't1');        -- dangling: agent 3 gone
        INSERT INTO agent_tools VALUES ('1', 't1');        -- fine
        INSERT INTO usage_logs VALUES ('4');               -- dangling: agent 4 gone
        INSERT INTO agent_tool_grants VALUES ('external'); -- the Exa pseudo-id (legit)
        INSERT INTO tools VALUES ('t1');
        INSERT INTO collections VALUES ('c1', 'Empty Team');
        INSERT INTO workflow_compositions VALUES ('w1', 'Daily', '{"recipient": "GhostAgent"}');
        INSERT INTO workflow_compositions VALUES ('w2', 'Clean', '{"recipient": "Bob"}');
    """)
    con.commit()
    con.close()
    return db


def test_audit_finds_dangling_agent_references(audit_db):
    a = ConsistencyAudit(audit_db)
    r = a.run()
    assert r["status"] == "inconsistent"
    refs = r["checks"]["agent_references"]
    labels = {f["label"] for f in refs}
    assert "tool link" in labels
    assert "usage log" in labels


def test_audit_ignores_the_external_pseudo_id(audit_db):
    a = ConsistencyAudit(audit_db)
    r = a.run()
    grants = r["checks"]["grant_references"]
    assert all(f["missing_agent_id"] != "external" for f in grants)


def test_audit_catches_name_references(audit_db):
    a = ConsistencyAudit(audit_db)
    r = a.run()
    names = r["checks"]["workflow_name_references"]
    assert any(f["missing_agent_name"] == "GhostAgent" for f in names)
    assert all(f["missing_agent_name"] != "Bob" for f in names)


def test_audit_is_read_only(audit_db):
    before = audit_db.read_bytes()
    ConsistencyAudit(audit_db).run()
    assert audit_db.read_bytes() == before


def test_audit_clean_db_reports_clean(tmp_path):
    db = tmp_path / "clean.db"
    con = sqlite3.connect(str(db))
    con.executescript("""
        CREATE TABLE agents (id TEXT PRIMARY KEY, name TEXT);
        CREATE TABLE agent_tools (agent_id TEXT, tool_id TEXT);
        CREATE TABLE usage_logs (agent_id TEXT);
        CREATE TABLE agent_tool_grants (agent_id TEXT);
        CREATE TABLE tools (id TEXT PRIMARY KEY);
        CREATE TABLE collections (id TEXT PRIMARY KEY, name TEXT);
        CREATE TABLE collection_items (id INTEGER PRIMARY KEY, collection_id TEXT, entity_id TEXT, entity_type TEXT);
        CREATE TABLE workflow_compositions (id TEXT PRIMARY KEY, name TEXT, config_json TEXT);
        INSERT INTO agents VALUES ('1', 'Meta');
        INSERT INTO tools VALUES ('t1');
        INSERT INTO agent_tools VALUES ('1', 't1');
    """)
    con.commit()
    con.close()
    r = ConsistencyAudit(db).run()
    assert r["status"] == "clean"
    assert r["total_findings"] == 0


def test_audit_empty_kit_referenced_by_package_is_not_orphaned(tmp_path):
    """The Shallow Agent Kit lesson (2026-08-29): an empty collection
    referenced as a package kit is a deliberate empty toolkit, not an
    orphan. Only empty AND unreferenced collections are reported."""
    db = tmp_path / "kit.db"
    con = sqlite3.connect(str(db))
    con.executescript("""
        CREATE TABLE agents (id TEXT PRIMARY KEY, name TEXT, deleted_at TEXT);
        CREATE TABLE agent_tools (agent_id TEXT, tool_id TEXT);
        CREATE TABLE usage_logs (agent_id TEXT);
        CREATE TABLE agent_tool_grants (agent_id TEXT);
        CREATE TABLE tools (id TEXT PRIMARY KEY);
        CREATE TABLE collections (id TEXT PRIMARY KEY, name TEXT);
        CREATE TABLE collection_items (id INTEGER PRIMARY KEY, collection_id TEXT, entity_id TEXT, entity_type TEXT);
        CREATE TABLE workflow_compositions (id TEXT PRIMARY KEY, name TEXT, config_json TEXT);
        CREATE TABLE agent_packages (id TEXT PRIMARY KEY, name TEXT, kit_id TEXT);
        INSERT INTO agents VALUES ('1', 'Meta', NULL);
        INSERT INTO tools VALUES ('t1');
        INSERT INTO collections VALUES ('kit', 'Shallow Agent Kit');  -- empty, but referenced
        INSERT INTO collections VALUES ('orphan', 'Ghost Team');      -- empty, unreferenced
        INSERT INTO agent_packages VALUES ('p1', 'shallow-agent', 'kit');
    """)
    con.commit()
    con.close()
    r = ConsistencyAudit(db).run()
    names = [f["name"] for f in r["checks"]["orphaned_collections"]]
    assert names == ["Ghost Team"]
