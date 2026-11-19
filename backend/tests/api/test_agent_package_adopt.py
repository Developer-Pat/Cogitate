"""The agent-package ADOPT action tests.

THE OWNERSHIP RULE (the user's correction): the agent OWNS its
copies. Adopt COPIES the package's kit_id + skills + llm_spec
into the agent's OWN fields + sets package_id (provenance). The
package never owns the agent — later package edits (even a
DELETE) don't mutate the agent.
"""

import uuid

import pytest


def pkg_body() -> dict:
    return {
        "name": f"pkg-{uuid.uuid4().hex[:8]}",
        "description": "A test package with a kit + skills + spec.",
        "kit_id": None,  # no kit needed for the copy test
        "skills": ["greeting", "small-talk"],
        "llm_spec": {
            "kind": "chat",
            "thinking": "none",
            "location": "local",
            "min_context": 4096,
        },
    }


def agent_body(name: str) -> dict:
    return {
        "name": name,
        "description": "The adopt test agent.",
        "provider": "ollama",
        "model": "llama3.2:latest",
    }


@pytest.mark.anyio
async def test_adopt_copies_into_the_agents_own_fields(client):
    """Adopt COPIES the package's fields into the agent's OWN fields
    + sets the provenance package_id."""
    pkg = (await client.post("/api/v1/agent-packages", json=pkg_body())).json()
    ag = (await client.post(
        "/api/v1/agents", json=agent_body(f"adopt-{uuid.uuid4().hex[:6]}")
    )).json()

    r = await client.post(
        f"/api/v1/agents/{ag['id']}/adopt-package",
        json={"package_id": pkg["id"]},
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["package_id"] == pkg["id"]            # provenance set
    assert d["skills"] == ["greeting", "small-talk"]  # the copied skillset
    assert d["llm_spec"]["thinking"] == "none"     # the copied contract
    assert d["llm_spec"]["location"] == "local"


@pytest.mark.anyio
async def test_adopt_survives_package_delete(client):
    """THE OWNERSHIP RULE: deleting the package does NOT strip the
    agent — the copies are OWNED, not live reads."""
    pkg = (await client.post("/api/v1/agent-packages", json=pkg_body())).json()
    ag = (await client.post(
        "/api/v1/agents", json=agent_body(f"owner-{uuid.uuid4().hex[:6]}")
    )).json()
    await client.post(
        f"/api/v1/agents/{ag['id']}/adopt-package",
        json={"package_id": pkg["id"]},
    )
    # delete the package blueprint
    dr = await client.delete(f"/api/v1/agent-packages/{pkg['id']}")
    assert dr.status_code == 204

    # the agent's owned copies survive (the GET has them)
    gr = await client.get(f"/api/v1/agents/{ag['id']}")
    assert gr.status_code == 200
    d = gr.json()
    assert d["skills"] == ["greeting", "small-talk"]
    assert d["llm_spec"]["thinking"] == "none"


@pytest.mark.anyio
async def test_adopt_unknown_package_404(client):
    ag = (await client.post(
        "/api/v1/agents", json=agent_body(f"nopkg-{uuid.uuid4().hex[:6]}")
    )).json()
    r = await client.post(
        f"/api/v1/agents/{ag['id']}/adopt-package",
        json={"package_id": "does-not-exist"},
    )
    assert r.status_code == 404


@pytest.mark.anyio
async def test_adopt_missing_package_id_400(client):
    ag = (await client.post(
        "/api/v1/agents", json=agent_body(f"noid-{uuid.uuid4().hex[:6]}")
    )).json()
    r = await client.post(f"/api/v1/agents/{ag['id']}/adopt-package", json={})
    assert r.status_code == 400


@pytest.mark.anyio
async def test_agent_without_package_has_no_package_id(client):
    ag = (await client.post(
        "/api/v1/agents", json=agent_body(f"bare-{uuid.uuid4().hex[:6]}")
    )).json()
    assert ag["package_id"] is None
    assert ag["llm_spec"] is None
