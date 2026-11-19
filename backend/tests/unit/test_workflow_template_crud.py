"""Template create, list, update and delete round-trip, and validation requires declared inputs.

The WorkflowTemplates editor called POST/PUT/DELETE
/api/v1/workflows/templates which did NOT exist (405/404) — the
"New template" flow was dead end-to-end (only GET list/categories
existed; the 33 templates were seeded). These tests cover the new
CRUD round-trip against a throwaway DB.
"""

import json
import sqlite3
import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.workflows.api import template_router


@pytest.fixture
def client(tmp_path, monkeypatch):
    # point the router's DB at a throwaway file
    db_path = tmp_path / "test_cogitate.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE workflow_templates (
            id TEXT PRIMARY KEY,
            name TEXT, description TEXT, category TEXT, version TEXT,
            author TEXT, tags TEXT, workflow_type TEXT, config TEXT,
            is_public INTEGER, is_customizable INTEGER,
            created_at TEXT, updated_at TEXT, inputs TEXT,
            kind_id TEXT
        )
        """
    )
    # the kinds catalog (the columns the model declares) — the
    # list endpoint LEFT JOINs it for kind_name
    conn.execute(
        """
        CREATE TABLE workflow_kinds (
            id TEXT PRIMARY KEY,
            name TEXT, description TEXT,
            builder_key TEXT, product_type TEXT, created_at TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO workflow_kinds (id, name, description, builder_key, product_type, created_at) "
        "VALUES ('simple', 'simple', 'a kind', 'simple_graph', 'report', '2026-08-14')"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(template_router, "DB_PATH", db_path)

    app = FastAPI()
    app.include_router(template_router.router)
    with TestClient(app) as tc:
        yield tc


def _create(tc, **overrides):
    body = {
        "name": "CRUD Test",
        "description": "a template",
        "category": "Test",
        "workflow_type": "simple",
        "config": {"test_mode": True},
        "tags": ["t1"],
    }
    body.update(overrides)
    return tc.post("/workflows/templates", json=body)


class TestTemplateCRUD:
    def test_create_returns_created_template(self, client):
        r = _create(client)
        assert r.status_code == 200
        d = r.json()
        assert d["name"] == "CRUD Test"
        assert d["workflow_type"] == "simple"
        assert d["config"] == {"test_mode": True}
        assert d["tags"] == ["t1"]
        assert d["id"]

    def test_created_template_appears_in_list(self, client):
        created = _create(client).json()
        r = client.get("/workflows/templates")
        assert r.status_code == 200
        ids = [t["id"] for t in r.json()["templates"]]
        assert created["id"] in ids

    def test_update_round_trips(self, client):
        created = _create(client).json()
        r = client.put(
            f"/workflows/templates/{created['id']}",
            json={"description": "updated", "tags": ["t1", "t2"], "config": {"delay_seconds": 5}},
        )
        assert r.status_code == 200
        d = r.json()
        assert d["description"] == "updated"
        assert d["tags"] == ["t1", "t2"]
        assert d["config"] == {"delay_seconds": 5}

    def test_delete_removes_and_404s_after(self, client):
        created = _create(client).json()
        r = client.delete(f"/workflows/templates/{created['id']}")
        assert r.status_code == 200
        assert r.json()["id"] == created["id"]
        r2 = client.delete(f"/workflows/templates/{created['id']}")
        assert r2.status_code == 404
        r3 = client.put(
            f"/workflows/templates/{created['id']}", json={"name": "x"}
        )
        assert r3.status_code == 404

    def test_update_missing_404(self, client):
        r = client.put(
            f"/workflows/templates/{uuid.uuid4()}", json={"name": "x"}
        )
        assert r.status_code == 404

    def test_validate_requires_name(self, client):
        r = client.post("/workflows/templates/validate", json={"name": "  "})
        assert r.status_code == 200
        d = r.json()
        assert d["isValid"] is False
        assert any("Name" in e for e in d["errors"])

    def test_validate_ok_with_name(self, client):
        r = client.post(
            "/workflows/templates/validate",
            json={"name": "ok", "steps": [{"id": "s1", "name": "plan"}]},
        )
        assert r.status_code == 200
        assert r.json()["isValid"] is True

    def test_validate_execution_requires_declared_inputs(self, client):
        created = _create(
            client,
            inputs=[{"name": "query", "required": True}, {"name": "limit", "required": False}],
        ).json()
        r = client.post(
            f"/workflows/templates/{created['id']}/validate-execution",
            json={"inputs": {"limit": 5}},
        )
        assert r.status_code == 200
        d = r.json()
        assert d["isValid"] is False
        assert any("query" in e for e in d["errors"])
        r2 = client.post(
            f"/workflows/templates/{created['id']}/validate-execution",
            json={"inputs": {"query": "x", "limit": 5}},
        )
        assert r2.json()["isValid"] is True
        # cleanup
        client.delete(f"/workflows/templates/{created['id']}")

    def test_validate_execution_missing_template_404(self, client):
        r = client.post(
            f"/workflows/templates/{uuid.uuid4()}/validate-execution", json={"inputs": {}}
        )
        assert r.status_code == 404
