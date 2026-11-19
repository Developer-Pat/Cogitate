"""The SSE stream delivers a published event, and heartbeats while idle.

The roadmap's contract: subscribe to the stream, publish on the
bus, see the event. The publish is IN-PROCESS (the bus + the SSE
endpoint share the event_bus singleton).

NOTE (the httpx trap): ASGITransport BUFFERS the whole response —
it cannot stream an infinite SSE body, so a client.stream() test
hangs by design. The honest test: iterate the
EventSourceResponse.body_iterator directly.
"""

import asyncio
import json

from app.api.v1.messaging.router import stream as sse_stream
from app.domain.messaging.services import event_bus


async def test_sse_stream_delivers_published_event():
    event_bus.clear()
    resp = await sse_stream(topics="test:*")

    # publish BEFORE iterating (the handler is registered when the
    # endpoint builds the response)
    event_bus.publish("test:ping", {"hello": "world"})

    chunks = []
    try:
        async for chunk in resp.body_iterator:
            chunks.append(chunk)
            # the chunks are dicts: {'event': ..., 'data': ...}
            if isinstance(chunk, dict) and chunk.get("event") == "test:ping":
                break
            if len(chunks) > 5:
                break
    except Exception:
        pass
    finally:
        event_bus.clear()

    events = [c.get("event") for c in chunks if isinstance(c, dict)]
    assert "test:ping" in events, f"event missing: {events!r}"
    assert any("hello" in (c.get("data", "") or "") for c in chunks if isinstance(c, dict))


async def test_sse_stream_heartbeat_on_idle():
    event_bus.clear()
    resp = await sse_stream(topics="test:*", heartbeat=0.1)

    chunks = []
    try:
        async for chunk in resp.body_iterator:
            chunks.append(chunk)
            if isinstance(chunk, dict) and chunk.get("event") == "heartbeat":
                break
            if len(chunks) > 5:
                break
    except Exception:
        pass
    finally:
        event_bus.clear()

    events = [c.get("event") for c in chunks if isinstance(c, dict)]
    assert "heartbeat" in events, f"heartbeat missing: {events!r}"
