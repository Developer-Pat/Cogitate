"""Package CRUD with duplicate names rejected, unknown ids 404, and llm_spec validated.

THE VOCABULARY (the design): the llm_spec carries kind
(chat/workflow), thinking (none/low/medium/high), location
(local/cloud/any), min_context. The package is ADVISORY — a
blueprint; the provisioned agent owns its copies.
"""

import pytest


def shallow_pkg(name: str | None = None) -> dict:
    """The shallow package with a UNIQUE name per test — the DB
    persists across tests, so a fixed name collides (409)."""
    import uuid
    return {
        "name": name or f"shallow-{uuid.uuid4().hex[:8]}",
        "description": "The shallow-agent package: a chat bot with a minimal surface.",
        "skills": ["greeting", "small-talk"],
        "llm_spec": {
            "kind": "chat",
            "thinking": "none",
            "location": "local",
            "min_context": 4096,
        },
    }


@pytest.mark.anyio
async def test_create_package(client):
    r = await client.post("/api/v1/agent-packages", json=shallow_pkg())
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["name"].startswith("shallow-")
    assert d["skills"] == ["greeting", "small-talk"]
    assert d["llm_spec"]["thinking"] == "none"
    assert d["llm_spec"]["location"] == "local"
    assert d["id"]


@pytest.mark.anyio
async def test_duplicate_name_rejected(client):
    name = f"dup-{__import__('uuid').uuid4().hex[:8]}"
    await client.post("/api/v1/agent-packages", json=shallow_pkg(name))
    r = await client.post("/api/v1/agent-packages", json=shallow_pkg(name))
    assert r.status_code == 409


@pytest.mark.anyio
async def test_llm_spec_vocabulary_validated(client):
    """The vocabulary is enforced: bad kind/thinking/location -> 422."""
    bad = shallow_pkg("bad-spec")
    bad["llm_spec"] = {"kind": "sleeping", "thinking": "extreme", "location": "moon"}
    r = await client.post("/api/v1/agent-packages", json=bad)
    assert r.status_code == 422


@pytest.mark.anyio
async def test_list_packages(client):
    await client.post("/api/v1/agent-packages", json=shallow_pkg())
    r = await client.get("/api/v1/agent-packages")
    assert r.status_code == 200
    d = r.json()
    assert d["total"] >= 1
    names = {p["name"] for p in d["packages"]}
    assert any(n.startswith("shallow-") for n in names)


@pytest.mark.anyio
async def test_get_package(client):
    created = (await client.post("/api/v1/agent-packages", json=shallow_pkg())).json()
    r = await client.get(f"/api/v1/agent-packages/{created['id']}")
    assert r.status_code == 200
    assert r.json()["name"] == created["name"]


@pytest.mark.anyio
async def test_update_package(client):
    created = (await client.post("/api/v1/agent-packages", json=shallow_pkg())).json()
    r = await client.put(
        f"/api/v1/agent-packages/{created['id']}",
        json={"description": "updated", "llm_spec": {"kind": "workflow", "thinking": "low"}},
    )
    assert r.status_code == 200
    d = r.json()
    assert d["description"] == "updated"
    assert d["llm_spec"]["kind"] == "workflow"
    assert d["llm_spec"]["thinking"] == "low"
    # the untouched fields survive (partial update)
    assert d["skills"] == ["greeting", "small-talk"]


@pytest.mark.anyio
async def test_delete_package(client):
    created = (await client.post("/api/v1/agent-packages", json=shallow_pkg())).json()
    r = await client.delete(f"/api/v1/agent-packages/{created['id']}")
    assert r.status_code == 204
    r2 = await client.get(f"/api/v1/agent-packages/{created['id']}")
    assert r2.status_code == 404


@pytest.mark.anyio
async def test_unknown_package_404(client):
    r = await client.get("/api/v1/agent-packages/does-not-exist")
    assert r.status_code == 404
