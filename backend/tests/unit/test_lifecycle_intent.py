"""The lifecycle intent: a button press must be distinguishable from a reload.

THE DEFECT THIS COVERS (found by the acceptance test, not by reading code): the
shutdown button's first implementation called `begin_shutdown_record()` directly to
record its intent. Two things went wrong:

  1. THE INTENT WAS LOST. The app's real shutdown handler then wrote its OWN
     record with the default reason, and THAT is the one that completes — so the
     successor read "sigterm" and could not tell a button press from a reloader.

  2. A PHANTOM CRASH. The early row sat at `draining` forever, and in this design
     a `draining` row means "died mid-shutdown". The button was planting a false
     crash signal in the very system built to detect crashes.

So the intent is PARKED (`set_pending_reason`) and picked up by the one record the
real shutdown writes. One shutdown, one record, the right reason.

WHY THIS NEEDS A TEST: the resolution order is the whole feature, and the failure
mode is silent — a wrong reason still produces a `complete` record that looks
perfectly healthy. Only the REASON reveals that the human action was lost.
"""
from __future__ import annotations

import pytest

from app.core import shutdown_record as sr


@pytest.fixture(autouse=True)
def _clear_pending():
    """Isolate: the pending reason is module state, so reset around each test."""
    sr.set_pending_reason(None)
    yield
    sr.set_pending_reason(None)


def _resolve(reason=None) -> str:
    """Mirror of begin_shutdown_record's resolution, reading the global AT CALL
    TIME. (A test that imports `_PENDING_REASON` by value binds the old value and
    silently tests nothing — which is exactly how this bug hid once already.)"""
    return reason or sr._PENDING_REASON or "sigterm"


class TestPendingReason:
    def test_defaults_to_sigterm_when_nothing_was_requested(self):
        assert _resolve() == "sigterm"

    def test_a_parked_intent_wins_over_the_default(self):
        sr.set_pending_reason("user-requested-restart")
        assert _resolve() == "user-requested-restart"

    def test_an_explicit_argument_still_wins(self):
        """Explicit beats parked: a caller that names a reason means it."""
        sr.set_pending_reason("user-requested-stop")
        assert _resolve("sigterm") == "sigterm"

    def test_clearing_restores_the_default(self):
        sr.set_pending_reason("user-requested-stop")
        sr.set_pending_reason(None)
        assert _resolve() == "sigterm"

    def test_get_pending_reason_reports_what_was_set(self):
        assert sr.get_pending_reason() is None
        sr.set_pending_reason("user-requested-stop")
        assert sr.get_pending_reason() == "user-requested-stop"


class TestTheReasonSurvivesToTheRecord:
    @pytest.mark.asyncio
    async def test_begin_shutdown_record_uses_the_parked_reason(self, test_session):
        """The end-to-end point: the record the shutdown writes carries the
        human's action, not the default."""
        from sqlalchemy import select

        from app.infrastructure.database.models import ShutdownRecord

        sr.set_session_factory(lambda: _session_ctx(test_session))
        sr.set_pending_reason("user-requested-restart")

        record_id = await sr.begin_shutdown_record()
        assert record_id is not None

        row = (
            await test_session.execute(
                select(ShutdownRecord).where(ShutdownRecord.id == record_id)
            )
        ).scalar_one()
        assert row.reason == "user-requested-restart"
        assert row.phase == "draining"


class _session_ctx:
    """A minimal async context manager yielding the test session.

    `shutdown_record` opens its own session from a factory, so the test supplies
    the harness's session rather than letting it build one.
    """

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return False
