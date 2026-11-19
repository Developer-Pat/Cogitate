"""The ring eviction counter counts churn, and is skipped for non-recorded events.

The bus logs crashes but not strain — the pass adds:
- the ring eviction counter + the log (the churn becomes visible)
- (the SSE queue bounds live in the router; the router test below
  covers the replay + the bounded delivery)
"""

import logging
import pytest

from app.domain.messaging.services import EventBusService


def test_ring_eviction_counter_counts_churn():
    """A ring that fills beyond maxlen must count + log the evictions."""
    bus = EventBusService(ring_size=5)
    assert bus._ring_evictions == 0

    # fill the ring exactly
    for i in range(5):
        bus.publish("test:evict", {"i": i}, record=True)
    assert bus._ring_evictions == 0
    assert len(bus._ring) == 5

    # the eviction begins — the 6th record evicts the 1st
    bus.publish("test:evict", {"i": 5}, record=True)
    assert bus._ring_evictions == 1
    assert len(bus._ring) == 5
    # the event-id stamp rides the recorded payloads (2026-08-29)
    assert bus._ring[0].payload == {"event_id": "e2", "i": 1}  # the oldest dropped


def test_ring_eviction_skipped_for_non_recorded():
    """The high-frequency chunk topics (record=False) never churn the ring."""
    bus = EventBusService(ring_size=5)
    for i in range(20):
        bus.publish("chat:chunk", {"i": i}, record=False)
    assert bus._ring_evictions == 0
    assert len(bus._ring) == 0
