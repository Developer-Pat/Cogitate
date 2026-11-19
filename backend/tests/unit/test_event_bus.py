"""Topic and wildcard delivery, fan-out, unsubscribe, and isolated handler errors.

The roadmap's test contract: publish/subscribe, wildcards, fan-out,
no subscriber = no-op, handler exceptions isolated.
"""

from app.domain.messaging.services import EventBusService


def _mk_bus():
    b = EventBusService()
    return b


def test_publish_subscribe_exact_topic():
    b = _mk_bus()
    got = []
    b.subscribe("workflow:123.started", lambda topic, payload: got.append((topic, payload)))
    b.publish("workflow:123.started", {"workflow_id": "123"})
    assert len(got) == 1
    assert got[0][0] == "workflow:123.started"
    assert got[0][1]["workflow_id"] == "123"


def test_wildcard_pattern():
    b = _mk_bus()
    got = []
    b.subscribe("batch:*", lambda topic, payload: got.append(topic))
    b.publish("batch:1.done", {"rows": 12})
    b.publish("batch:2.done", {"rows": 11})
    b.publish("workflow:1.started", {})  # not matched
    assert got == ["batch:1.done", "batch:2.done"]


def test_fan_out_multiple_subscribers():
    b = _mk_bus()
    a, c = [], []
    b.subscribe("system:*", lambda t, p: a.append(t))
    b.subscribe("system:*", lambda t, p: c.append(t))
    b.publish("system:ready", {})
    assert a == ["system:ready"]
    assert c == ["system:ready"]


def test_no_subscriber_is_noop():
    b = _mk_bus()
    # must not raise
    b.publish("unmatched.topic", {"x": 1})


def test_handler_exception_isolated():
    b = _mk_bus()
    got = []

    def bad(topic, payload):
        raise RuntimeError("boom")

    b.subscribe("workflow:*", bad)
    b.subscribe("workflow:*", lambda t, p: got.append(t))
    # the bad handler must NOT break the fan-out
    b.publish("workflow:1.started", {})
    assert got == ["workflow:1.started"]


def test_unsubscribe():
    b = _mk_bus()
    got = []

    def h(topic, payload):
        got.append(topic)

    b.subscribe("notify:*", h)
    b.publish("notify:test", {})
    b.unsubscribe("notify:*", h)
    b.publish("notify:test", {})
    assert got == ["notify:test"]


def test_payload_defaults_to_empty():
    b = _mk_bus()
    got = []
    b.subscribe("system:*", lambda t, p: got.append(p))
    b.publish("system:ready")
    # THE EVENT-ID STAMP (2026-08-29, the event-id chain): the bus
    # injects event_id into the payload at publish — the tests
    # predating the stamp assert the raw {}; the current contract
    # carries the stamp.
    assert got == [{"event_id": "e1"}]
