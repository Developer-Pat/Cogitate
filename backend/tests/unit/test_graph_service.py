"""The knowledge-graph service tests.

The GraphService + the derived FK walk + the wiki graph:
- the service resolves entities across both providers
- the derived graph answers 'what fires this workflow' (the
  semantic trigger edges)
- the wiki graph answers 'which pages relate to X'
- graph-query works through the registry (the tool path)
"""
import asyncio
import shutil

import pytest

from app.domain.graph import GraphService
from app.domain.graph.derived import DerivedGraphProvider
from app.domain.graph.wiki import WikiGraphProvider


@pytest.fixture(autouse=True)
def _app_db(tmp_path, monkeypatch, live_db_path):
    """Point the app's RESOLVER at a COPY of the installation's database.

    The graph is walked over real content (Bob's links, the wiki pages), so the
    copy is the fixture — `live_db_path` is the suite's own source for "the real
    database". What this pins is the RESOLUTION: `Paths.from_settings`, which is
    what the providers and the graph-query tool read. The class attribute
    (`Paths.shared_db`) is a dataclass FIELD DEFAULT that ignores DATABASE_URL —
    patching it, as this module used to, pinned nothing and left the providers
    reading whatever the operator's live database happened to hold.
    """
    from app.core.config import Paths as CorePaths
    from tests import conftest as cf

    db_copy = tmp_path / "cogitate.db"
    shutil.copy(live_db_path, db_copy)
    # THE CONTENT IS RESTORED INTO THE COPY. The suite truncates every
    # ORM-managed table between tests, so a copy taken later in a run (or on a
    # clean clone, where the sandbox was built by `create_all`) has an empty
    # catalog and the walk finds no triggers, no tools, no workflows. The
    # reference rows are what "the installation's database" MEANS here.
    cf._load_reference_rows(str(db_copy))
    # Resolved BEFORE the patch — `rooted_at` derives through `from_settings`.
    sandbox = CorePaths.rooted_at(db_copy)
    monkeypatch.setattr(CorePaths, "from_settings", classmethod(lambda cls, _settings: sandbox))


@pytest.fixture
def svc(_app_db):
    return GraphService([DerivedGraphProvider(), WikiGraphProvider()])


def test_entity_resolution(svc):
    e = svc.get_entity("agent-hello")
    assert e is not None
    assert e["kind"] == "workflow"  # agent-hello IS the workflow template
    e2 = svc.get_entity("nope-nope")
    assert e2 is None


def test_derived_trigger_edges(svc):
    n = svc.get_neighbors("agent-hello")
    kinds = {ed["kind"] for ed in n["edges"]}
    assert "fires" in kinds
    assert any(ed["to"].startswith("workflow_triggers:") for ed in n["edges"])


def test_agent_neighbors(svc):
    # (2026-08-26, the sweep): 'Scheherazade' was the framework's
    # original seeding — the live db's agents have been pruned by the
    # testing over the months. Bob (the current active agent with the
    # tool links) carries the neighbors now.
    n = svc.get_neighbors("Bob")
    assert len(n["edges"]) > 0


def test_wiki_graph_links(svc):
    e = svc.get_entity("workflow-system")
    assert e is not None
    assert e["kind"] == "wiki-page"
    n = svc.get_neighbors("workflow-system")
    assert len(n["edges"]) >= 1


def test_topology_shape(svc):
    t = svc.get_topology()
    assert len(t["nodes"]) > 500  # the wiki pages + the system entities
    assert len(t["edges"]) > 1000


@pytest.mark.asyncio
async def test_graph_query_tool():
    from app.domain.tools.registry import init_default_registry
    reg = init_default_registry()
    r = await reg.execute_tool("graph-query", {}, {"entity": "agent-hello"})
    assert r.get("success") is True
    assert r.get("verified") is True
    assert len(r.get("edges", [])) >= 1
    r2 = await reg.execute_tool("graph-query", {}, {"entity": "nope"})
    assert r2.get("success") is False
    assert r2.get("error_type") == "not_found"
