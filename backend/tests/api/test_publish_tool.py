"""Publishing emits a valid event; validation rejects bad namespaces and non-dict payloads.

The roadmap's contract: the tool publishes, the SSE stream shows
it. The validation: bad namespaces rejected, payload must be a
dict, JSON-serializable.
"""

import asyncio

from app.domain.tools.builtin.publish_handler import PublishTool
from app.api.v1.messaging.router import stream as sse_stream
from app.domain.messaging.services import event_bus


async def test_publish_tool_emits_valid_event():
    event_bus.clear()
    # SUBSCRIBE FIRST (the bus is live-only — an event published
    # before the subscriber exists is lost by design; the real flow
    # opens the stream before the run fires)
    resp = await sse_stream(topics="batch:*")

    tool = PublishTool()
    r = await tool.execute({}, arguments={"topic": "batch:5:done", "payload": {"rows": 12}})
    assert r["success"] is True

    # the SSE stream must carry it
    chunks = []
    try:
        async for chunk in resp.body_iterator:
            chunks.append(chunk)
            if isinstance(chunk, dict) and chunk.get("event") == "batch:5:done":
                break
            if len(chunks) > 5:
                break
    except Exception:
        pass
    finally:
        event_bus.clear()

    events = [c.get("event") for c in chunks if isinstance(c, dict)]
    assert "batch:5:done" in events, f"event missing: {events!r}"


async def test_publish_tool_rejects_bad_namespace():
    tool = PublishTool()
    r = await tool.execute({}, arguments={"topic": "bad.topic", "payload": {}})
    assert r["success"] is False
    assert "topic must start with" in r["error"]


async def test_publish_tool_requires_topic():
    tool = PublishTool()
    r = await tool.execute({}, arguments={})
    assert r["success"] is False
    assert "topic is required" in r["error"]


async def test_publish_tool_rejects_non_dict_payload():
    tool = PublishTool()
    r = await tool.execute({}, arguments={"topic": "notify:x", "payload": "not-a-dict"})
    assert r["success"] is False
