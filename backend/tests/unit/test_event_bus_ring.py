"""The event ring replays to a late subscriber and stays bounded at its limit.

The roadmap's contract: a late subscriber (connect after events
fired) catches up with the recent history — the live-only loss is
bounded. The SSE bridge replays on connect.
"""

from app.domain.messaging.services import EventBusService
from app.api.v1.messaging.router import stream as sse_stream


async def test_ring_replays_to_late_subscriber():
    b = EventBusService(ring_size=10)
    # publish BEFORE any subscriber exists (the live-only loss case)
    b.publish("workflow:1:started", {"workflow_id": 1})
    b.publish("batch:1:done", {"rows": 12})
    b.publish("workflow:1:completed", {"workflow_id": 1})

    # the late subscriber catches up via recent()
    recent = b.recent("workflow:*", limit=20)
    assert len(recent) == 2
    assert recent[0].topic == "workflow:1:started"
    assert recent[1].topic == "workflow:1:completed"

    # the wildcard narrows
    batch = b.recent("batch:*")
    assert len(batch) == 1
    assert batch[0].topic == "batch:1:done"


async def test_ring_is_bounded():
    b = EventBusService(ring_size=3)
    for i in range(10):
        b.publish(f"batch:{i}:done", {"rows": i})
    recent = b.recent("batch:*", limit=100)
    assert len(recent) == 3  # the deque dropped the oldest 7
    assert recent[0].topic == "batch:7:done"
    assert recent[-1].topic == "batch:9:done"


async def test_ring_limit():
    b = EventBusService(ring_size=10)
    for i in range(5):
        b.publish(f"batch:{i}:done", {"rows": i})
    recent = b.recent("batch:*", limit=2)
    assert len(recent) == 2
    assert recent[0].topic == "batch:3:done"


async def test_sse_stream_replays_ring_on_connect():
    from app.domain.messaging.services import event_bus
    event_bus.clear()
    # publish before the stream opens (the real late-subscriber case)
    event_bus.publish("batch:9:done", {"rows": 9})

    resp = await sse_stream(topics="batch:*")
    chunks = []
    try:
        async for chunk in resp.body_iterator:
            chunks.append(chunk)
            if isinstance(chunk, dict) and chunk.get("event") == "batch:9:done":
                break
            if len(chunks) > 5:
                break
    except Exception:
        pass
    finally:
        event_bus.clear()

    events = [c.get("event") for c in chunks if isinstance(c, dict)]
    assert "batch:9:done" in events, f"the replay missing: {events!r}"
