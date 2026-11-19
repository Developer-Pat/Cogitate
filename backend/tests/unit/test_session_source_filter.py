"""The session-source filter regression tests — the Exa-leak dig.

THE BUG: the agent page's session loader fetched EVERY session
with no source filter, so Exa's conversations (source='exa', no
agent row) cluttered the agent chat's session list.

THE FIX: GET /api/v1/sessions gained a `source` query param
('agent' | 'exa'); the agent page requests 'agent', the Exa page
'exa'. The discriminator is a stable category constant — a display
rename of the Exa character must NOT change these strings.
"""

import pytest


@pytest.mark.anyio
async def test_list_sessions_filters_by_source(client, test_session):
    """The source filter separates the surfaces: agent sessions
    never appear under source=exa and vice versa."""
    # two sessions, one per surface (the exa one has agent_id=null)
    agent = (await client.post("/api/v1/sessions", json={
        "agent_id": None, "title": "agent-side chat", "source": "agent",
    })).json()
    exa = (await client.post("/api/v1/sessions", json={
        "agent_id": None, "title": "exa-side chat", "source": "exa",
    })).json()

    # the agent filter returns ONLY the agent session
    agent_list = (await client.get(
        "/api/v1/sessions?source=agent&page_size=100"
    )).json()
    agent_titles = [s["title"] for s in agent_list["sessions"]]
    assert "agent-side chat" in agent_titles
    assert "exa-side chat" not in agent_titles

    # the exa filter returns ONLY the exa session
    exa_list = (await client.get(
        "/api/v1/sessions?source=exa&page_size=100"
    )).json()
    exa_titles = [s["title"] for s in exa_list["sessions"]]
    assert "exa-side chat" in exa_titles
    assert "agent-side chat" not in exa_titles

    # the no-filter list still sees BOTH (the admin/tools surface)
    both = (await client.get("/api/v1/sessions?page_size=100")).json()
    all_titles = [s["title"] for s in both["sessions"]]
    assert "agent-side chat" in all_titles
    assert "exa-side chat" in all_titles


@pytest.mark.anyio
async def test_list_sessions_source_filter_default_is_agent(client):
    """The default (no source param) must NOT regress to hiding
    agent sessions — the pre-existing behavior lists everything."""
    made = (await client.post("/api/v1/sessions", json={
        "agent_id": None, "title": "default-view chat", "source": "agent",
    })).json()
    assert made["id"]
    resp = (await client.get("/api/v1/sessions?page_size=100")).json()
    titles = [s["title"] for s in resp["sessions"]]
    assert "default-view chat" in titles
