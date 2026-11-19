"""The two-phase shutdown record tests.

THE PROPERTY UNDER TEST is not "we wrote a row". It is that **a crash during
shutdown is distinguishable from a clean exit** — which a single "was clean"
row cannot do, because a crash leaves the PREVIOUS clean row in place and the
successor reads it happily.

Three outcomes at boot, and the third is the honest one:

    clean    — phase `complete`; report any abandoned work by name
    unclean  — phase still `draining`: the previous exit DIED MID-SHUTDOWN
    none     — no record; say exactly that and claim nothing

Sessions are INJECTED, because this module talks to the DB directly and so
cannot use `dependency_overrides` the way conftest isolates everything else.
Without the injection these tests would write into the production database.
"""
import json

import pytest
import pytest_asyncio
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core import shutdown_record
from app.infrastructure.database.models import ShutdownRecord


@pytest_asyncio.fixture
async def record_db(test_engine):
    """Point the record module at the TEST database for the duration."""
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    shutdown_record.set_session_factory(factory)
    yield factory
    shutdown_record.set_session_factory(None)


async def _count(factory) -> int:
    async with factory() as db:
        return (await db.execute(select(func.count()).select_from(ShutdownRecord))).scalar_one()


@pytest.mark.anyio
async def test_a_clean_shutdown_reads_as_clean(record_db):
    """The ordinary path — and the one the user insisted on: the report is
    written EITHER WAY, so that its absence can mean something."""
    record_id = await shutdown_record.begin_shutdown_record("sigterm")
    assert record_id is not None
    await shutdown_record.complete_shutdown_record(record_id, completed=["inbox processor"])

    result = await shutdown_record.report_last_shutdown()
    assert result["state"] == "clean"
    assert result["record"]["completed"] == ["inbox processor"]
    assert result["record"]["abandoned"] == []


@pytest.mark.anyio
async def test_an_exit_that_died_mid_shutdown_reads_as_unclean(record_db):
    """THE UGLY PATH, and the reason for two phases.

    This is what `kill -9` leaves behind: phase one written, phase two never
    reached. Nothing marks the row — its STALENESS is the evidence. A design
    with one phase would show the previous clean row here and report calm.
    """
    await shutdown_record.begin_shutdown_record("sigterm")
    # ... and then the process dies. No completion. That is the whole setup.

    result = await shutdown_record.report_last_shutdown()
    assert result["state"] == "unclean", "a stale `draining` row must not read as clean"
    assert result["record"]["phase"] == "draining"
    assert result["record"]["completed_at"] is None
    assert result["how"] == "died-mid-shutdown"


@pytest.mark.anyio
async def test_an_exit_killed_while_running_reads_as_unclean(record_db):
    """THE HOLE THE FIRST DRAFT HAD, and why there are three states.

    A `kill -9` runs NO shutdown code at all. Phase one never writes, so a
    two-state design leaves the PREVIOUS clean row in place and the successor
    reads "clean" — a crash wearing the last good exit's clothes. That is not a
    hypothetical: it is exactly what the acceptance test produces.

    With a liveness marker written at boot, the stale `running` row is the
    evidence. Found by walking the ugly path in the head before running it.
    """
    await shutdown_record.mark_running()   # up...
    # ...and then killed. No draining, no completion, no goodbye.

    result = await shutdown_record.report_last_shutdown()
    assert result["state"] == "unclean"
    assert result["how"] == "died-while-running"
    assert result["record"]["phase"] == "running"


@pytest.mark.anyio
async def test_work_not_finished_is_named_never_counted(record_db):
    """'2 items abandoned' gives an operator nothing to act on."""
    record_id = await shutdown_record.begin_shutdown_record("sigterm")
    await shutdown_record.complete_shutdown_record(
        record_id,
        completed=["inbox processor"],
        abandoned=["workflow trigger scheduler (shutdown raised)"],
    )

    result = await shutdown_record.report_last_shutdown()
    assert result["state"] == "clean"          # it DID complete
    assert result["record"]["abandoned"] == ["workflow trigger scheduler (shutdown raised)"]


@pytest.mark.anyio
async def test_no_record_claims_nothing(record_db):
    """A first boot and a wiped store are indistinguishable. Inventing 'clean'
    would be exactly the lie this arc exists to stop."""
    result = await shutdown_record.report_last_shutdown()
    assert result["state"] == "none"
    assert result["record"] is None


@pytest.mark.anyio
async def test_in_flight_is_recorded_at_phase_one(record_db, monkeypatch):
    """Phase one must name what was running, because after a crash phase two
    never runs — the in-flight list is the ONLY record of what was lost."""
    monkeypatch.setattr(shutdown_record, "snapshot", lambda: ["chat session 41"])
    await shutdown_record.begin_shutdown_record("sigterm")

    result = await shutdown_record.report_last_shutdown()
    assert result["state"] == "unclean"
    assert result["record"]["in_flight"] == ["chat session 41"]


@pytest.mark.anyio
async def test_the_table_stays_bounded(record_db):
    """Retention: the newest N. A pattern of unclean exits should be visible,
    and an unbounded table is its own problem."""
    for i in range(shutdown_record.SHUTDOWN_RECORD_KEEP + 5):
        rid = await shutdown_record.begin_shutdown_record(f"run-{i}")
        await shutdown_record.complete_shutdown_record(rid)

    assert await _count(record_db) == shutdown_record.SHUTDOWN_RECORD_KEEP
