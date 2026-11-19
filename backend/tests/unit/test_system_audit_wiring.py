"""The system-audit template registers and resolves as a graph, and is not scheduled.

The user's directive: "wire it but don't fire it; don't put it
on a schedule." The template exists + resolves; there is NO
trigger row; the three trigger paths (startup / Exa / user) are
available through the existing execute endpoint.
"""
import sqlite3
from pathlib import Path

import pytest

from app.core.config import Paths, get_settings


@pytest.fixture(scope="module")
def db():
    con = sqlite3.connect(str(Paths.from_settings(get_settings()).shared_db))
    yield con
    con.close()


def test_system_audit_template_registered(db):
    row = db.execute(
        "SELECT id, kind_id FROM workflow_templates WHERE id = 'system-audit'"
    ).fetchone()
    assert row is not None
    assert row[1] == "system-audit"


def test_system_audit_is_not_scheduled(db):
    """The directive: no trigger row — the audit only runs when
    started (boot), triggered (Exa/user), or requested."""
    n = db.execute(
        "SELECT COUNT(*) FROM workflow_triggers WHERE workflow_id = 'system-audit'"
    ).fetchone()[0]
    assert n == 0


def test_system_audit_graph_resolves():
    from app.workflows.api.workflow_router import get_workflow_graph, compile_workflow
    g = get_workflow_graph("system-audit")
    assert g is not None
    compiled = compile_workflow("system-audit")
    assert compiled is not None


def test_system_audit_kind_factory():
    from app.domain.workflows.kinds.registry import resolve_kind_graph_factory, get_kind
    f = resolve_kind_graph_factory("system-audit")
    assert f is not None
    assert f.__name__ == "create_system_audit_graph"
    k = get_kind("system-audit")
    assert k is not None and k.product_type == "report"
