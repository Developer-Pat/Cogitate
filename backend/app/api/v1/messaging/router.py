"""Messaging API Router — the SSE bridge (Phase B, 2026-08-24).

THE OUTWARD STREAM: the event bus -> SSE -> the frontend.

- GENERIC: any topic, any consumer. The frontend subscribes to
  whatever the bus carries (workflow:*, batch:*, the_boss:*,
  notify:*, system:*).
- sse-starlette's EventSourceResponse (the FastAPI-native SSE —
  the proposal's library decision): heartbeats + disconnect
  handling built in.
- THE THREAD BOUNDARY: the bus publishes from worker THREADS (the
  workflow executor); the SSE generator runs on the event loop.
  The handler bridges via loop.call_soon_threadsafe — never touch
  the asyncio queue from a foreign thread directly.
- Cleanup: on disconnect (CancelledError / generator close), the
  subscriptions are removed — one connection, one client.

Mounted at /api/v1/messaging/stream via the parent router.
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.domain.messaging.services import event_bus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/messaging", tags=["messaging"])

# the heartbeat interval (seconds) — keeps the connection alive +
# lets proxies see the stream is live.
_HEARTBEAT_SECONDS = 15

# THE OBSERVABILITY PASS (2026-08-24): the per-client SSE buffer cap —
# a slow consumer's queue can no longer grow unbounded; a full queue
# logs a WARNING (the strain becomes visible).
_QUEUE_MAXSIZE = 500


@router.get("/stream")
async def stream(topics: str = "system:*", heartbeat: float = _HEARTBEAT_SECONDS) -> EventSourceResponse:
    """Stream the bus events for the given topic patterns.

    topics: comma-separated patterns (e.g. 'workflow:*,batch:*').
    Each matching event is sent as an SSE `event: <topic>` line
    with the payload as JSON. A heartbeat fires every 15s so the
    connection stays warm.
    """
    patterns = [t.strip() for t in topics.split(",") if t.strip()]
    if not patterns:
        patterns = ["system:*"]

    # THE OBSERVABILITY PASS (2026-08-24, the user's ask): the queue
    # was UNBOUNDED — a slow consumer's memory grew silently and a
    # bog-down never logged. Now bounded; a full queue and a
    # disconnect-race drop both log a WARNING (the strain is visible).
    queue: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
    loop = asyncio.get_running_loop()

    def _put(topic: str, payload: dict) -> None:
        # runs IN the event loop (called via call_soon_threadsafe) —
        # the QueueFull surfaces HERE, not in the foreign thread
        try:
            queue.put_nowait((topic, payload))
        except asyncio.QueueFull:
            logger.warning(
                f"  ⚠️ SSE queue FULL ({queue.qsize()}/{_QUEUE_MAXSIZE}) — "
                f"dropped event {topic} (slow consumer — the tab is behind)"
            )

    def _handler(topic: str, payload: dict) -> None:
        # Called from ANY thread (the bus is thread-safe). Bridge
        # into the event loop — NEVER put on the asyncio queue from
        # a foreign thread directly.
        try:
            loop.call_soon_threadsafe(_put, topic, payload)
        except RuntimeError:
            logger.warning(
                f"  ⚠️ SSE drop (disconnect race): event {topic} — the loop closed"
            )

    for pattern in patterns:
        event_bus.subscribe(pattern, _handler)
    logger.info(f"  📡 SSE stream opened: {patterns}")

    async def _gen():
        try:
            # THE RING REPLAY (Phase F, 2026-08-24): a late subscriber
            # (connect after events fired) catches up with the recent
            # history BEFORE the live stream — the live-only loss is
            # bounded (the last RING_SIZE events per matching pattern).
            for pattern in patterns:
                for ev in event_bus.recent(pattern, limit=20):
                    yield {"event": ev.topic, "data": json.dumps(ev.payload)}
            while True:
                try:
                    topic, payload = await asyncio.wait_for(queue.get(), timeout=heartbeat)
                    yield {"event": topic, "data": json.dumps(payload)}
                except asyncio.TimeoutError:
                    yield {"event": "heartbeat", "data": "{}"}
        finally:
            # THE CLEANUP RULE: remove the subscriptions on disconnect
            # (one connection, one client — no orphan handlers).
            for pattern in patterns:
                event_bus.unsubscribe(pattern, _handler)
            logger.info(f"  📡 SSE stream closed: {patterns}")

    return EventSourceResponse(_gen())
