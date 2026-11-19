"""Deep-agent provisioning — the folder is created, and archive removes it.

Tests cover:
- Folder name validation
- Provision agent (creates folder + files)
- Duplicate provision (409)
- Agent status
- Archive agent

ISOLATION (the TestAgent resurrection root-cause, 2026-08-17): the
provisioning router writes the agent into the shared cogitate.db via
a raw sqlite3 connection derived from settings.database_url. This
test must point DATABASE_URL at a THROWAWAY DB (a temp file) so a
sweep run never writes "TestAgent" into the production database.
"""
import os
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def client(tmp_path, monkeypatch):
    # Point the router's shared-DB path at a throwaway file: the
    # router derives it from settings.database_url, so overriding
    # DATABASE_URL redirects the write. NEVER the production DB.
    test_db = tmp_path / "provisioning-test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{test_db}")
    # get_settings is @lru_cache'd — clear it so the new DATABASE_URL
    # is picked up (the router derives the DB path from settings).
    from app.core.config import get_settings
    get_settings.cache_clear()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    # THE CACHE IS PART OF THE REDIRECT (2026-09-25 — the cross-group interference).
    # `monkeypatch` puts the environment variable back, but `lru_cache`d settings are
    # NOT on its list: the stale object would keep naming this throwaway database for
    # every later test in the xdist worker, and those tests then die on
    # `no such table: workflow_templates` (only the real database carries the
    # migration-only tables). Clearing on the way IN was half the job. Clear on the
    # way OUT too — and this fixture's teardown runs after monkeypatch's, so the
    # rebuild that follows reads the restored environment.
    get_settings.cache_clear()


def _agent_dir(name="test-agent"):
    # Resolved through Paths: under test this is the TEMPORARY agents root, not
    # the live one. The hand-built crawl wrote test agents into production's
    # agents/ directory - the isolation gap, in a helper nobody was looking at.
    from app.core.config import Paths, get_settings

    return str(Paths.from_settings(get_settings()).agents_dir / name)


@pytest.mark.asyncio
async def test_provision_and_folder_check(client):
    """Provision an agent, verify folder on disk, then check duplicate 409."""
    import shutil
    ad = _agent_dir()
    if os.path.exists(ad):
        shutil.rmtree(ad)

    # Provision
    resp = await client.post(
        "/api/v1/agents/test-agent/provision",
        json={"name": "TestAgent", "description": "A test agent", "system_prompt": "You are a test."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "Agent 'test-agent' provisioned"
    assert data["agent"]["name"] == "TestAgent"

    # Verify folder on disk (3A: no per-agent cogitate.db — the per-agent
    # DB was wired-but-idle scaffolding, removed in DB cleanup Phase 3)
    assert os.path.exists(ad)
    assert os.path.exists(os.path.join(ad, "agent.json"))
    assert not os.path.exists(os.path.join(ad, "cogitate.db"))
    assert os.path.exists(os.path.join(ad, "skills"))

    # Status check
    resp = await client.get("/api/v1/agents/test-agent/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["exists"] is True
    assert "cogitate.db" not in data["databases"]
    assert "cognitive_memory.db" in data["databases"]

    # Duplicate
    resp = await client.post(
        "/api/v1/agents/test-agent/provision",
        json={"name": "TestAgent"},
    )
    assert resp.status_code == 409
    assert "already exists" in resp.text


@pytest.mark.asyncio
async def test_archive_and_verify(client):
    """Archive the agent and verify 404."""
    # PROVISION ITS OWN AGENT. This test used to rely on the agent left behind by
    # test_provision_and_folder_check — and it only ever worked because that
    # agent had been written to the PRODUCTION database, where it survived the
    # per-test truncation. With isolation fixed the state no longer carries over,
    # which exposed the hidden dependency. A test that needs an agent creates one.
    resp = await client.post(
        "/api/v1/agents/test-agent/provision",
        json={"name": "TestAgent", "description": "A test agent", "system_prompt": "You are a test."},
    )
    assert resp.status_code == 200, resp.text

    resp = await client.delete("/api/v1/agents/test-agent/archive")
    assert resp.status_code == 200
    data = resp.json()
    assert "archived" in data["message"]

    resp = await client.get("/api/v1/agents/test-agent/status")
    assert resp.status_code == 404
