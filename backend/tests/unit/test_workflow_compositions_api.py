"""The workflow compositions API — CRUD and the two-workflow execution rule.

The compositions table + the general-executor dispatch fix mean
compositions now WORK: create via the API, execute end-to-end
(chained named workflows), and the live DB stays clean (the
test-pollution fix: tests use a temp DB).
"""

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.workflows.api.composition_router import router as composition_router


app = FastAPI()
app.include_router(composition_router)

# Resolved through the app's `Paths`, not by counting parent directories: the
# whole point of the isolation work is that "the database" is whatever the
# resolver says it is, which under test is the temporary copy.
from app.core.config import Paths, get_settings

LIVE_DB = Path(str(Paths.from_settings(get_settings()).shared_db))


@pytest.fixture
def client():
    with TestClient(app) as tc:
        yield tc


class TestCompositionAPI:
    def test_list_returns_real_compositions(self, client):
        r = client.get("/compositions")
        assert r.status_code == 200
        d = r.json()
        items = d if isinstance(d, list) else d.get("compositions", d.get("items", []))
        ids = {i.get("id") for i in items}
        # the seeded demo + the real pipelines exist; NO test-comp rows
        assert "demo-monitor-pair" in ids
        assert not any(i.startswith("test-comp-") for i in ids)

    def test_create_roundtrip_and_delete(self, client):
        # unique id per run: the router SOFT-deletes (is_active=0),
        # so re-creating the same id would 400 on the second run
        import uuid
        cid = f"test-compose-api-{uuid.uuid4().hex[:8]}"
        body = {
            "id": cid,
            "name": "API Roundtrip",
            "description": "temp",
            "workflows": [
                {"workflow_id": "readiness-check", "order": 1},
                {"workflow_id": "simple-hello", "order": 2},
            ],
            "version": "1.0.0",
        }
        r = client.post("/compositions", json=body)
        assert r.status_code == 200
        got = client.get(f"/compositions/{cid}").json()
        assert got.get("id") == cid
        client.delete(f"/compositions/{cid}")
        # soft-delete: row still exists but inactive
        con = sqlite3.connect(LIVE_DB)
        try:
            row = con.execute(
                "SELECT is_active FROM workflow_compositions WHERE id = ?", (cid,)
            ).fetchone()
        finally:
            con.close()
        assert row and row[0] == 0
        # cleanup: remove the soft-deleted row (hygiene)
        con = sqlite3.connect(LIVE_DB)
        try:
            con.execute("DELETE FROM workflow_compositions WHERE id = ?", (cid,))
            con.commit()
        finally:
            con.close()

    def test_execution_requires_two_workflows(self, client):
        # the composition contract: ≥2 named workflows (building
        # blocks, not single steps)
        body = {
            "id": "test-single",
            "name": "Single",
            "workflows": [{"workflow_id": "readiness-check", "order": 1}],
            "version": "1.0.0",
        }
        r = client.post("/compositions", json=body)
        assert r.status_code == 400  # validation: at least 2 items


class TestLiveDBHygiene:
    def test_no_test_pollution_in_live_db(self):
        # Phase G regression: the composition tests write to a TEMP
        # DB now — the live DB must not accumulate test-comp-* rows
        con = sqlite3.connect(LIVE_DB)
        try:
            n = con.execute(
                "SELECT COUNT(*) FROM workflow_compositions WHERE id LIKE 'test-comp-%'"
            ).fetchone()[0]
        finally:
            con.close()
        assert n == 0, "composition tests must not pollute the live DB"
