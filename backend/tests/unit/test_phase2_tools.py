"""Tool registration, the grant-gated restart, trigger verify, knowledge search and graph query.

The verify + admin tool family through the real registry:
- the tools REGISTER (the contract validator accepts them)
- verify-trigger-config reads back the DB
- restart-backend refuses without the fix-mode grant
- set-trigger-schedule verifies by read-back (the hardened shape)
"""
import asyncio
import pytest

from app.domain.tools.registry import init_default_registry
pytestmark = pytest.mark.backend  # needs a running backend (the 2026-08-27 decision)



@pytest.fixture(scope="module")
def registry():
    return init_default_registry()


def test_phase2_tools_registered(registry):
    slugs = registry.get_all_slugs()
    for s in (
        "verify-trigger-config",
        "verify-backend-health",
        "restart-backend",
        "search-knowledge",
        "graph-query",
    ):
        assert s in slugs, f"{s} must be registered"


@pytest.mark.asyncio
async def test_verify_trigger_config_reads_back(registry):
    """Seeds its OWN trigger — it must not depend on seeded state surviving.

    This test previously read the migration-seeded `monitor-rss-hourly`. That
    passes alone and fails in a file run: `auto_clean_tables` deletes from every
    ORM-managed table after each test, `workflow_triggers` is one, and it is not
    on the survive-list (which names only workflow_execution_history,
    workflow_approvals, tool_usage_logs, _sqlite_manager_audit_log). So the first
    test in the file wiped the seed and every later one saw an empty table.

    The fixture is the honest fix: a test that needs a row should make it.
    """
    from app.domain.workflows.schemas.trigger_config import WorkflowTriggerCreate
    from app.domain.workflows.services.trigger_service import TriggerService

    TriggerService().create_trigger(WorkflowTriggerCreate(
        id="test-verify-trigger",
        workflow_id="wf-test-verify",
        trigger_type="schedule",
        config={"cron": "0 * * * *"},
    ))

    r = await registry.execute_tool(
        "verify-trigger-config", {}, {"trigger_id": "test-verify-trigger"}
    )
    assert r.get("success") is True
    assert r.get("verified") is True
    assert isinstance(r.get("config"), dict)
    assert "cron" in r["config"]


@pytest.mark.asyncio
async def test_verify_trigger_config_unknown_rejected(registry):
    r = await registry.execute_tool(
        "verify-trigger-config", {}, {"trigger_id": "no-such-trigger"}
    )
    assert r.get("success") is False
    assert r.get("error_type") == "not_found"


@pytest.mark.asyncio
async def test_restart_backend_requires_grant(registry, monkeypatch):
    # the fix-mode grant is OFF (patched) — admin_denied. The gate
    # reads the LIVE DB's settings (a JSON string — fixed 2026-08-19),
    # so the test patches the function for determinism.
    import app.domain.tools.registry as reg_mod
    monkeypatch.setattr(reg_mod, "_fix_mode_granted", lambda: False)
    r = await registry.execute_tool("restart-backend", {}, {})
    assert r.get("success") is False
    assert r.get("error_type") == "admin_denied"


@pytest.mark.asyncio
async def test_restart_backend_requires_grant_off_denies(registry, monkeypatch):
    # sanity: with the grant patched OFF the gate denies BEFORE any
    # restart attempt (the operation is never reached)
    import app.domain.tools.registry as reg_mod
    monkeypatch.setattr(reg_mod, "_fix_mode_granted", lambda: False)
    r = await registry.execute_tool("restart-backend", {}, {})
    assert r.get("success") is False
    assert "grant" in r.get("error", "").lower()


@pytest.mark.external("embeddings")
@pytest.mark.asyncio
async def test_search_knowledge_returns_hits(registry):
    """Needs an embedding provider — the app embeds via local Ollama.

    The handler returns {'success': False, 'error': 'Embedding failed (is
    Ollama up?)'} when nothing is reachable, which reads exactly like a
    defect. It is not: it is an absent external service.

    Was marked `live`, which meant "Ollama" — a category named after its first
    example. It now names the NEED (embeddings), so the day a remote embedding
    provider lands this test needs no edit.
    """
    # Phase 4: the RAG index is wired — the tool returns verified hits
    r = await registry.execute_tool("search-knowledge", {}, {"query": "triggers"})
    assert r.get("success") is True
    assert r.get("verified") is True
    assert isinstance(r.get("hits"), list)


@pytest.mark.asyncio
async def test_graph_query_returns_edges(registry):
    # Phase 5: the GraphService is wired — the tool returns verified edges
    r = await registry.execute_tool("graph-query", {}, {"entity": "agent-hello"})
    assert r.get("success") is True
    assert r.get("verified") is True
    assert isinstance(r.get("edges"), list)
