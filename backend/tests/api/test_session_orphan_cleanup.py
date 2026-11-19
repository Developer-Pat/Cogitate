"""The orphaned-messages regression tests — the ghost-history bug.

THE BUG: deleting a session left its chat_messages behind (the FK
cascade was dead — no PRAGMA foreign_keys), and SQLite REUSED the
deleted session id — the next session INHERITED the orphaned
messages. Bob 'knew about Exa' because a fresh 'Hello' session
absorbed a dead Exa conversation's history.

THE FIX: the delete paths now remove the messages WITH the
session (explicit + the FK pragma), so no session can ever
inherit another conversation's ghosts.
"""

import pytest


async def _count_messages(test_session, session_id):
    """Count a session's messages via the TEST engine (the same DB
    the API client wrote to — NOT the real cogitate.db)."""
    from sqlalchemy import func, select
    from app.infrastructure.database.models import ChatMessage
    n = await test_session.scalar(
        select(func.count()).select_from(ChatMessage).where(
            ChatMessage.session_id == session_id
        )
    )
    return n or 0


@pytest.mark.anyio
async def test_delete_session_removes_its_messages(client, test_session):
    """Delete a session -> its messages are GONE (no orphans)."""
    # a session with messages
    s = (await client.post("/api/v1/sessions", json={
        "agent_id": None, "title": "orphan test", "source": "chat",
    })).json()
    sid = s["id"]
    await client.post(f"/api/v1/sessions/{sid}/messages", json={
        "role": "user", "content": "hello",
    })
    await client.post(f"/api/v1/sessions/{sid}/messages", json={
        "role": "assistant", "content": "hi",
    })
    assert await _count_messages(test_session, sid) == 2

    # delete the session
    r = await client.delete(f"/api/v1/sessions/{sid}")
    assert r.status_code == 204

    # the messages must NOT survive
    n = await _count_messages(test_session, sid)
    assert n == 0, f"{n} orphaned messages survived the session delete"


@pytest.mark.anyio
async def test_bulk_delete_removes_messages(client, test_session):
    """bulk_delete also cleans the messages."""
    ids = []
    for i in range(2):
        s = (await client.post("/api/v1/sessions", json={
            "agent_id": None, "title": f"bulk {i}", "source": "chat",
        })).json()
        ids.append(s["id"])
        await client.post(f"/api/v1/sessions/{s['id']}/messages", json={
            "role": "user", "content": f"msg {i}",
        })

    r = await client.post("/api/v1/sessions/bulk-delete", json=ids)
    assert r.status_code == 200, r.text

    for sid in ids:
        n = await _count_messages(test_session, sid)
        assert n == 0, f"{n} orphaned messages survived the bulk delete (session {sid})"
