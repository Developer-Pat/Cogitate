"""Chat events publish with the convention topic, and recording can be turned off per call.

The roadmap's contract: the pipeline publishes the contract events
to the bus (observable by a monitor/the UI pump) while the direct
stream stays identical. Plus the volume guard: the record option.
"""

from app.api.v1.chat import chat_events
from app.domain.messaging.services import EventBusService
from app.services.cognitive_pipeline.models import (
    CognitiveResult, ComponentTrace, CognitiveTrace,
    CognitiveMetrics, MemoryDelta,
)


def _mk_trace(**over):
    base = dict(
        strategy="test", duration_ms=12, tokens_used=34,
        metadata={"sources": ["a.md"]}, error=None,
    )
    base.update(over)
    return ComponentTrace(**base)


def _mk_result():
    trace = CognitiveTrace(executor=_mk_trace())
    metrics = CognitiveMetrics(total_duration_ms=12, total_tokens=34)
    return CognitiveResult(response="hi", trace=trace, metrics=metrics,
                            memory_delta=MemoryDelta())


def test_bus_publish_record_default():
    b = EventBusService(ring_size=10)
    seen = []
    b.subscribe("chat:*", lambda t, p: seen.append(t))
    topic, payload = chat_events.build_executor_started("s-1", "test")
    b.publish(topic, payload)
    assert seen == ["chat:s-1:executor_started"]
    # the ring recorded it (the default)
    assert len(b.recent("chat:*")) == 1


def test_bus_publish_record_false_skips_ring():
    b = EventBusService(ring_size=10)
    seen = []
    b.subscribe("chat:*", lambda t, p: seen.append(t))
    topic, payload = chat_events.build_executor_started("s-1", "test")
    b.publish(topic, payload, record=False)  # the volume guard
    assert seen == ["chat:s-1:executor_started"]
    # the ring did NOT record it (the high-frequency guard)
    assert len(b.recent("chat:*")) == 0


def test_publish_convenience_passthrough():
    from app.domain.messaging.services import event_bus
    event_bus.clear()
    seen = []
    event_bus.subscribe("chat:*", lambda t, p: seen.append(t))
    topic, payload = chat_events.build_executor_completed("s-1", _mk_trace())
    event_bus.publish(topic, payload, record=False)
    assert seen == ["chat:s-1:executor_completed"]
    event_bus.clear()


def test_all_chat_topics_follow_convention():
    r = _mk_result()
    t = _mk_trace()
    cases = [
        chat_events.build_session_id("s-1"),
        chat_events.build_context_built("s-1", t),
        chat_events.build_executor_started("s-1", "x"),
        chat_events.build_executor_completed("s-1", t),
        chat_events.build_memory_updated("s-1", t),
        chat_events.build_response_formatted("s-1", t),
        chat_events.build_trace_complete("s-1", r),
    ]
    for topic, _ in cases:
        assert topic.startswith("chat:s-1:"), topic
