"""A turn holds no write transaction while it is waiting on a provider.

SQLite allows exactly one writer, and this project's turn path writes the user
message before it asks the provider anything. If that write is left uncommitted,
the whole application cannot write for as long as the model takes to answer:
every other request -- a second turn's session row, a settings save, an agent
update -- waits out the connection's thirty-second busy timeout and fails, while
reads keep answering normally, so the app looks alive and is not.

The defect is invisible from inside the request that causes it, so it is pinned
here from OUTSIDE: a connection of its own asks the database for the write lock
while a stubbed provider is mid-stream. The invariant is that it gets it -- at
the moment the provider is called, and again while its stream is open.
"""

from __future__ import annotations

import asyncio
import sqlite3
from types import SimpleNamespace

from sqlalchemy import select


class _StubChunk:
    """A stream chunk in the shape `_stream_llm_response` reads."""

    def __init__(self, content="", finish_reason=None, tool_calls=None, usage=None):
        self.choices = [
            SimpleNamespace(
                delta=SimpleNamespace(
                    content=content, tool_calls=tool_calls,
                    reasoning="", reasoning_content="",
                ),
                finish_reason=finish_reason,
            )
        ]
        self.usage = usage


class _GatedStream:
    """A provider stream that delivers its chunks and then keeps the call OPEN.

    Every chunk arrives normally, then the stream waits on a gate before it ends
    -- which is a slow model in miniature, and the window this test probes from.
    Opening the gate lets the turn finish, so the same test proves the turn it
    interrupted was a healthy one.
    """

    def __init__(self, chunks, gate: asyncio.Event, open_for_business: asyncio.Event):
        self._chunks = list(chunks)
        self._gate = gate
        self._open_for_business = open_for_business

    def __aiter__(self):
        self._it = iter(self._chunks)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            self._open_for_business.set()
            await self._gate.wait()
            raise StopAsyncIteration


def _write_lock(test_engine) -> tuple[bool, str]:
    """Can an independent connection start a write transaction right now?

    Probed from a connection of its own against the same file: the question is
    whether the DATABASE is writable by anyone else, which the app's own session
    cannot answer about itself.
    """
    conn = sqlite3.connect(test_engine.url.database, timeout=2.0, isolation_level=None)
    try:
        conn.execute("PRAGMA busy_timeout=2000")
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("ROLLBACK")
        return True, "free"
    except sqlite3.OperationalError as exc:
        return False, str(exc)
    finally:
        conn.close()


def _force_shallow_route(monkeypatch):
    """One pass, so the provider calls counted here are the turn's own."""

    def _route(**kwargs):
        from app.services.cognitive_pipeline.conduit import ConduitDecision, Route

        return ConduitDecision(route=Route.SHALLOW, reason="forced for the test")

    monkeypatch.setattr(
        "app.services.cognitive_pipeline.conduit.conduit_route", _route,
    )


async def _make_agent(test_session):
    from app.infrastructure.database.models import Agent

    agent = Agent(
        name="Write Lock Agent", provider="deepseek", model="deepseek-v4-flash",
        system_prompt="You are a test agent.", is_active=True,
    )
    test_session.add(agent)
    await test_session.commit()
    await test_session.refresh(agent)
    return agent


async def test_a_turn_holds_no_write_transaction_while_the_provider_streams(
    test_session, test_engine, monkeypatch,
):
    """The invariant, from outside: the file stays writable for the whole call."""
    from app.api.v1.chat import llm_utils
    from app.api.v1.chat import router as mod
    from app.domain.chat.services import ChatService
    from app.infrastructure.database.models import ChatMessage

    answer = "The answer, written while nothing was holding the lock."
    agent = await _make_agent(test_session)

    gate = asyncio.Event()
    streaming = asyncio.Event()
    at_each_call: list[tuple[bool, str]] = []

    async def fake_completion(**kwargs):
        at_each_call.append(_write_lock(test_engine))
        return _GatedStream(
            [_StubChunk(content=answer), _StubChunk(finish_reason="stop")],
            gate, streaming,
        )

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)
    _force_shallow_route(monkeypatch)

    request = SimpleNamespace(
        agent_id=agent.id, message="hello", session_id=None,
        attachment_ids=None, generate_title=False,
    )

    async def _drain():
        return [chunk async for chunk in mod.generate_stream(request, ChatService(test_session))]

    turn = asyncio.create_task(_drain())
    try:
        await asyncio.wait_for(streaming.wait(), timeout=15)
        mid_stream = _write_lock(test_engine)
    finally:
        gate.set()
    frames = await asyncio.wait_for(turn, timeout=30)

    # 1. THE INVARIANT: nothing was holding the write lock when the provider was
    #    asked, and nothing holds it while the provider's stream is open.
    held = [why for free, why in at_each_call if not free]
    assert not held, (
        "the turn called the provider while its own write was uncommitted, so the "
        f"file was not writable by anything else: {held}"
    )
    assert mid_stream[0], (
        "the turn held SQLite's only write lock while the provider was streaming: "
        f"{mid_stream[1]} — every other write in the app waits 30s and fails there"
    )

    # 2. and the turn it interrupted was a healthy one: it answered, and the
    #    answer is on the row rather than rolled back.
    assert any(answer in frame for frame in frames), "the answer never reached the stream"
    rows = (await test_session.execute(
        select(ChatMessage).where(ChatMessage.role == "assistant")
    )).scalars().all()
    assert rows, "the turn saved nothing"
    assert rows[-1].content == answer
