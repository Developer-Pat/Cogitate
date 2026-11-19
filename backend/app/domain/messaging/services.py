"""
Messaging domain service (Phase A, 2026-08-24).

The Application Event Bus — a GENERIC in-process pub-sub transport
built on blinker (the battle-tested signal lib). Follows the
microservice shape: app/domain/messaging/services.py (the domain
service) + app/api/v1/messaging/router.py (the API surface, Phase B).

The Boss-Batching pipeline is ONE consumer; the bus serves the
whole app (workflows, agents, UI state, notify).

TOPICS (the ALL-COLON convention — `namespace:sub:event` so a
`namespace:*` wildcard ALWAYS matches everything under it):
- workflow:<id>:started / :completed / :failed  (lifecycle)
- batch:<id>:done / :failed                      (fan-out progress)
- agent:<id>:published                           (the publish tool)
- the_boss:proposed                              (the consolidation)
- notify:<kind>                                  (the toaster, opt-in)
- system:<kind>                                  (app-level events)
- a subscriber can match the whole tree: `workflow:*` matches
  workflow:1:started, workflow:2:done, etc. (the mix of `:` and
  `.` from the early drafts broke this — settled 2026-08-24)

DESIGN (the proposal's decisions):
- live-only (no persistence; the history tables are durable).
- thread-safe (blinker's dispatch is locked; the workflow workers
  run in threads).
- handler isolation: one subscriber's exception must NOT break the
  fan-out (blinker propagates by default — we isolate here).
- the singleton is the service instance (one bus per app).
"""

import fnmatch
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any, Callable

from blinker import Signal

logger = logging.getLogger(__name__)

# THE RING-BUFFER SIZE (Phase F, 2026-08-24): the bounded recent-event
# history. New subscribers (the SSE bridge on connect) replay it —
# the live-only loss (events published before a subscriber exists)
# is bounded: the last N events are recoverable.
RING_SIZE = 200


@dataclass
class BusEvent:
    """A ring-buffered event (the recent-history entry)."""
    topic: str
    payload: dict[str, Any]
    id: str = ""  # the bus-sequence id (the publish stamps it!)
    at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"))


class EventBusService:
    """The in-process pub-sub bus (the transport — the service)."""

    def __init__(self, ring_size: int = RING_SIZE) -> None:
        self._lock = threading.RLock()
        self._seq = 0  # THE EVENT-SEQUENCE (2026-08-29): the frontend's
        # center keys on the event_id — the same content at a NEW
        # event is a NEW record (the dedupe/tombstone stopped eating
        # the new events!). The toast's replay-guard keys on it too.
        self._signals: dict[str, Signal] = {}
        self._subscriptions: list[tuple[str, Callable]] = []
        self._ring: deque[BusEvent] = deque(maxlen=ring_size)
        # THE OBSERVABILITY PASS (2026-08-24): the deque evicts the
        # oldest silently — the counter makes the churn visible
        self._ring_evictions = 0

    # ---- the public surface -------------------------------------------------

    def publish(self, topic: str, payload: dict[str, Any] | None = None, record: bool = True) -> None:
        """Fan out an event. NEVER raises (subscriber errors isolated).

        record=False skips the ring append — the high-frequency
        chunk/progress topics use it (the ring would churn with
        thousands of token events; useless as history). The
        lifecycle events keep record=True (a late-joiner sees the
        recent trace).
        """
        try:
            payload = payload or {}
            # THE EVENT-ID STAMP (2026-08-29): every published event
            # gets the bus-sequence id — the ring + the live
            # subscribers both carry it (the center's dedupe keys on
            # it: the same event's replay is silent, the NEW events
            # always land!)
            self._seq += 1
            payload = dict(payload)
            payload["event_id"] = f"e{self._seq}"
            with self._lock:
                subs = list(self._subscriptions)
                sigs = list(self._signals.items())
            # the direct subscribers (exact + wildcard patterns)
            for pattern, handler in subs:
                if fnmatch.fnmatch(topic, pattern):
                    self._dispatch_safe(handler, topic, payload)
            # the signal subscribers (exact topic)
            for t, sig in sigs:
                if t == topic:
                    sig.send(None, **payload)
            # THE RING APPEND (Phase F): record the event for the
            # recent-history replay (bounded — the deque drops the
            # oldest beyond maxlen). The volume guard: record=False
            # (the chunk topics) skips this entirely.
            if record:
                if len(self._ring) == self._ring.maxlen:
                    # an eviction is imminent — the recent-history
                    # buffer churned (a high-frequency event stream)
                    self._ring_evictions += 1
                    logger.info(
                        f"  🔄 Ring eviction #{self._ring_evictions} "
                        f"(topic={topic}) — the recent-history buffer churned"
                    )
                self._ring.append(BusEvent(topic=topic, payload=dict(payload), id=payload.get("event_id", "")))
        except Exception as e:  # the bus itself never dies
            logger.error(f"  ❌ EventBusService.publish({topic}) failed: {e}")

    def subscribe(self, topic_pattern: str, handler: Callable) -> None:
        """Register a handler for a topic pattern (wildcard `*` OK)."""
        with self._lock:
            self._subscriptions.append((topic_pattern, handler))
        logger.info(f"  📡 Bus subscriber: {topic_pattern}")

    def unsubscribe(self, topic_pattern: str, handler: Callable) -> None:
        """Remove a handler (the SSE bridge uses this on disconnect)."""
        with self._lock:
            self._subscriptions = [
                (p, h) for (p, h) in self._subscriptions
                if not (p == topic_pattern and h == handler)
            ]

    def recent(self, topic_pattern: str, limit: int = 20) -> list[BusEvent]:
        """THE RING REPLAY (Phase F): the recent events matching a
        topic pattern, oldest-first (the SSE bridge replays them on
        connect so a late subscriber catches up). Bounded by the
        ring size."""
        with self._lock:
            matches = [e for e in self._ring if fnmatch.fnmatch(e.topic, topic_pattern)]
        return matches[-limit:]

    def clear(self) -> None:
        """Test/teardown helper — drop all subscriptions + signals."""
        with self._lock:
            self._subscriptions.clear()
            self._signals.clear()
            self._ring.clear()

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscriptions)

    # ---- internals -----------------------------------------------------------

    def _dispatch_safe(self, handler: Callable, topic: str, payload: dict) -> None:
        try:
            handler(topic, payload)
        except Exception as e:
            # THE HANDLER-ISOLATION RULE: one bad subscriber must not
            # break the fan-out (the proposal's decision).
            logger.error(f"  ❌ Bus handler for {topic} raised: {e}")


# the module-level singleton (the app's one bus — the service)
event_bus: EventBusService = EventBusService()


def publish(topic: str, payload: dict[str, Any] | None = None, record: bool = True) -> None:
    """Module-level convenience for the app code (the lifecycle
    wiring imports this)."""
    event_bus.publish(topic, payload, record=record)


def publish_warning(title: str, message: str, kind: str = "provider-fallback") -> None:
    """The WARNING toast through the bus (2026-09-01, the user's
    'silent fallbacks are bad'): the fallback-alert — the SSE
    carries it to every open tab; the bridge toasts it (the
    warning-class — the attention-worthy, the sound-level gates
    it). The fallback-points call this instead of logging only."""
    publish(
        f"notify:{kind}",
        {
            "title": title,
            "message": message,
            "type": "warning",
            "from": "system",
            "kind": kind,
        },
    )
