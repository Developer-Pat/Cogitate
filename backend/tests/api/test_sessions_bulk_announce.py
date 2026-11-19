"""The BULK session wipes announce on the bus — the cross-window sync's hole.

`clear_all_sessions` (DELETE /api/v1/sessions) and `delete_all_sessions`
(DELETE /api/v1/sessions/all) destroyed EVERY session and told nobody: the other
open tabs kept rendering rows that no longer existed. The single-session paths
have announced since 2026-08-25; each bulk path now publishes ONE event with
`scope='all'` — the topic is `session:all:<event>`, and the frontend's
`useSessionSync` reloads the list on it.

WHY THIS IS A TEST AND NOT A LIVE CHECK: exercising these endpoints means wiping
a real database. The announce is exactly what the fix adds, so it is pinned here
— on the bus, at the topic, not on a mock.
"""

import pytest

from app.domain.messaging.services import event_bus


@pytest.fixture
def bus():
    """Collect every session event published during a test."""
    event_bus.clear()
    seen: list[tuple[str, dict]] = []

    def handler(topic, payload):
        seen.append((topic, payload))

    event_bus.subscribe("session:*", handler)
    yield seen
    event_bus.unsubscribe("session:*", handler)
    event_bus.clear()


async def _seed(client, n=2):
    ids = []
    for i in range(n):
        r = await client.post("/api/v1/sessions", json={
            "agent_id": None, "title": f"bulk announce {i}", "source": "chat",
        })
        assert r.status_code in (200, 201), r.text
        ids.append(r.json()["id"])
    return ids


@pytest.mark.anyio
async def test_clear_all_announces_one_bulk_event(client, bus):
    await _seed(client, 2)

    r = await client.delete("/api/v1/sessions")
    assert r.status_code == 200
    deleted = r.json()["deleted_count"]
    assert deleted >= 2

    bulk = [(t, p) for t, p in bus if t == "session:all:cleared"]
    assert bulk, f"the clear-all announced nothing (topics seen: {[t for t, _ in bus]})"
    payload = bulk[-1][1]
    assert payload["event"] == "cleared"
    assert payload["scope"] == "all"
    assert payload["count"] == deleted


@pytest.mark.anyio
async def test_delete_all_announces_one_bulk_event(client, bus):
    await _seed(client, 2)

    r = await client.delete("/api/v1/sessions/all")
    assert r.status_code == 200
    assert r.json()["total_deleted"] >= 2

    bulk = [(t, p) for t, p in bus if t == "session:all:deleted_all"]
    assert bulk, f"the delete-all announced nothing (topics seen: {[t for t, _ in bus]})"
    payload = bulk[-1][1]
    assert payload["event"] == "deleted_all"
    assert payload["scope"] == "all"


@pytest.mark.anyio
async def test_delete_all_with_nothing_to_delete_stays_quiet(client, bus):
    """No sessions deleted -> no event: a reload in every open tab is noise."""
    await client.delete("/api/v1/sessions")   # drain whatever a fixture left
    bus.clear()

    r = await client.delete("/api/v1/sessions/all")
    assert r.status_code == 200
    assert r.json()["total_deleted"] == 0
    assert bus == []


@pytest.mark.anyio
async def test_single_session_paths_keep_their_own_topics(client, bus):
    """The scope parameter must NOT have disturbed the per-session topics."""
    s = (await client.post("/api/v1/sessions", json={
        "agent_id": None, "title": "topic guard", "source": "chat",
    })).json()
    sid = s["id"]

    await client.put(f"/api/v1/sessions/{sid}", json={"title": "topic guard renamed"})
    await client.delete(f"/api/v1/sessions/{sid}")

    topics = [t for t, _ in bus]
    assert f"session:{sid}:created" in topics
    assert f"session:{sid}:updated" in topics
    assert f"session:{sid}:deleted" in topics
