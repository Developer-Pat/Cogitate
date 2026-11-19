"""Workflow template kinds — every template classifies into a valid kind.

All 33 seeded rows are classified deterministically (reviewed
table). These tests assert the contract against the
LIVE DB: every template has a kind_id, the join surfaces
kind_name, and the key classification facts hold (the monitor
family → monitor; the workflow_type circle fix).
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.workflows.api.template_router import router as template_router
from app.api.v1.workflow_kinds_router import router as kinds_router

app = FastAPI()
app.include_router(template_router)
app.include_router(kinds_router)


# THE SUITE'S DB-ISOLATION (2026-08-26, the sweep): the earlier
# tests MUTATE the live db's workflow_templates.kind_id — the
# every-template-has-a-kind assertion reads the mutated db. The
# autouse copy + from_settings patch pins the classification
# contract against a CLEAN db.
@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch, live_db_path):
    import shutil
    from pathlib import Path
    from app.core.config import Paths as CorePaths
    db_copy = tmp_path / "cogitate.db"
    shutil.copy(live_db_path, db_copy)
    # Resolved BEFORE the patch — `rooted_at` derives through `from_settings`.
    sandbox = CorePaths.rooted_at(db_copy)
    monkeypatch.setattr(
        CorePaths, "from_settings",
        classmethod(lambda cls, settings: sandbox),
    )


@pytest.fixture
def client():
    with TestClient(app) as tc:
        yield tc


class TestClassification:
    def test_every_template_has_a_kind(self, client):
        d = client.get("/workflows/templates?limit=200").json()
        templates = d["templates"]
        assert templates, "expected templates to exist"
        for t in templates:
            assert t["kind_id"], f"{t['name']} missing kind_id"
            assert t["kind_name"], f"{t['name']} missing kind_name"

    def test_kind_names_are_valid_kinds(self, client):
        kinds = {k["name"] for k in client.get("/workflow-kinds").json()["kinds"]}
        d = client.get("/workflows/templates?limit=200").json()
        for t in d["templates"]:
            assert t["kind_name"] in kinds, f"{t['name']} → unknown kind {t['kind_name']}"

    def test_monitor_family_is_monitor_kind(self, client):
        d = client.get("/workflows/templates?limit=200").json()
        by_id = {t["id"]: t for t in d["templates"]}
        for tid in ("rss-monitor", "market-watch", "readiness-check"):
            assert by_id[tid]["kind_id"] == "monitor"
            # the circle fix: workflow_type renamed away from 'workflow'
            assert by_id[tid]["workflow_type"] == "monitor"

    def test_persona_kinds_are_process_kinds(self, client):
        d = client.get("/workflows/templates?limit=200").json()
        by_id = {t["id"]: t for t in d["templates"]}
        assert by_id["boss-agent"]["kind_id"] == "batch-orchestration"
        assert by_id["file-clerk"]["kind_id"] == "file-processing"

    def test_classification_counts(self, client):
        # the reviewed classification table, as counts
        d = client.get("/workflows/templates?limit=200").json()
        from collections import Counter
        counts = Counter(t["kind_id"] for t in d["templates"])
        assert counts == {
            "agent-task": 10,
            "chain": 7,
            "multi-agent": 8,
            "monitor": 3,
            "simple": 3,
            "batch-orchestration": 1,
            "context-indexing": 1,
            "file-processing": 1,
            "system-audit": 1,
            # the tag-survey study's template (2026-08-26)
            "tag-survey": 1,
        }
