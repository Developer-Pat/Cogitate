"""The catalog's timer is opt-in: nothing enabled, nothing done.

The app ships with no provider sync of its own. The maintenance job wakes hourly and asks whether any
ENABLED schedule is due — and a schedule row exists only because someone set an interval in that
provider's panel. On a fresh install the answer is always "none", so no provider is ever contacted
and the catalog stays exactly as it was found.

The second property is what "due" costs when it is not honoured: one provider being down must not
take every other provider's refresh with it, because this job has no caller to raise to and the next
tick is an hour away.
"""

from types import SimpleNamespace

import pytest

from app.domain.providers import scheduler as scheduler_mod


class _FakeScheduler:
    """Stands in for `ModelSyncScheduler` — the job builds its own, so the config is on the class.

    Mirrors the two methods the job uses and nothing else; `runs` is what the assertions read.
    """

    due: list[int] = []
    fail: set[int] = set()
    runs: list[int] = []

    async def get_due_syncs(self, db):
        return list(type(self).due)

    async def run_sync(self, db, provider_id):
        if provider_id in type(self).fail:
            raise RuntimeError(f"provider {provider_id} is down")
        type(self).runs.append(provider_id)
        return SimpleNamespace(status="ok")


class _Session:
    """The job opens its own session; nothing in it is read through the fake."""

    async def __aenter__(self):
        return object()

    async def __aexit__(self, *exc):
        return False


@pytest.fixture(autouse=True)
def _wire(monkeypatch):
    _FakeScheduler.due, _FakeScheduler.fail, _FakeScheduler.runs = [], set(), []
    monkeypatch.setattr(scheduler_mod, "ModelSyncScheduler", _FakeScheduler)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _Session())
    yield
    _FakeScheduler.due, _FakeScheduler.fail, _FakeScheduler.runs = [], set(), []


@pytest.mark.anyio
async def test_with_no_enabled_schedule_no_provider_is_contacted():
    """A fresh install: the job runs, finds nothing due, and does nothing."""
    await scheduler_mod.sync_due_providers()

    assert _FakeScheduler.runs == []


@pytest.mark.anyio
async def test_every_due_provider_is_synced():
    _FakeScheduler.due = [3, 7]

    await scheduler_mod.sync_due_providers()

    assert _FakeScheduler.runs == [3, 7]


@pytest.mark.anyio
async def test_one_provider_failing_does_not_take_the_others_refresh():
    _FakeScheduler.due = [3, 7, 9]
    _FakeScheduler.fail = {7}

    await scheduler_mod.sync_due_providers()  # must not raise

    assert _FakeScheduler.runs == [3, 9], "the providers on either side still synced"
