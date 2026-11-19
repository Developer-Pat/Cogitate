"""The workflow kinds API — the canonical kinds and their declared inputs.

The kind registry is code-defined; the endpoints serve it. Tests
assert the contract: the 8 canonical kinds, filters, detail, 404.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.workflow_kinds_router import router

app = FastAPI()
app.include_router(router)


@pytest.fixture
def client():
    with TestClient(app) as tc:
        yield tc


class TestKindsList:
    def test_returns_all_nine_canonical_kinds(self, client):
        # system-audit became the 9th kind (2026-08-20); tag-survey
        # the 10th (2026-08-26, the tag-layer study) — the canonical
        # set is now ten
        r = client.get("/workflow-kinds")
        assert r.status_code == 200
        d = r.json()
        names = {k["name"] for k in d["kinds"]}
        assert d["total"] == 10
        assert names == {
            "monitor", "file-processing", "batch-orchestration",
            "multi-agent", "chain", "agent-task", "tag-survey",
            "context-indexing", "simple", "system-audit",
        }

    def test_shape(self, client):
        r = client.get("/workflow-kinds")
        for k in r.json()["kinds"]:
            assert "name" in k and "description" in k
            assert "builder_key" in k and "product_type" in k
            assert isinstance(k["inputs"], list)

    def test_monitor_kind_declares_source_kind_input(self, client):
        r = client.get("/workflow-kinds/monitor")
        assert r.status_code == 200
        k = r.json()
        assert k["builder_key"] == "monitor_graph"
        assert k["product_type"] == "report"
        input_names = [i["name"] for i in k["inputs"]]
        assert "source_kind" in input_names

    def test_product_type_filter(self, client):
        r = client.get("/workflow-kinds?product_type=file")
        names = [k["name"] for k in r.json()["kinds"]]
        assert names == ["file-processing"]

    def test_search_filter(self, client):
        r = client.get("/workflow-kinds?q=monitor")
        names = [k["name"] for k in r.json()["kinds"]]
        assert "monitor" in names

    def test_detail_404(self, client):
        assert client.get("/workflow-kinds/nonexistent").status_code == 404

    def test_kinds_are_process_names_not_personas(self, client):
        # the naming rule (study 01b): kinds are verb+object
        # processes; persona names (file-clerk, boss-agent) are NOT
        # kinds
        names = {k["name"] for k in client.get("/workflow-kinds").json()["kinds"]}
        assert "file-clerk" not in names
        assert "boss-agent" not in names
        assert "file-processing" in names
        assert "batch-orchestration" in names
