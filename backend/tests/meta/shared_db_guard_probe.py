"""The guard's PROBE FIXTURE — run by `tests/unit/test_shared_db_guard_meta.py`.

NOT collected by the groups (the filename does not match pytest's default
`test_*.py`, so only an explicit path reaches it). Every test here is meant to
provoke the shared-db guard, which is why it cannot live among the ordinary
tests: a suite cannot contain three tests that are supposed to go red.

Run it by hand to see the guard's messages:

    cd backend && uv run pytest tests/meta/shared_db_guard_probe.py -q -p no:randomly
"""

from sqlalchemy import text


async def test_innocent_test_stays_quiet(client):
    """A plain request/response test — the guard must say nothing about it."""
    r = await client.get("/api/v1/agents")
    assert r.status_code in (200, 401, 403)


async def test_off_rails_talks_to_its_own_database(tmp_path):
    """Stands up a private database — check 1 must fail it."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'private.db'}")
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TABLE private_thing (id INTEGER)"))
    finally:
        await engine.dispose()


async def test_leaks_rows_nothing_cleans(test_session):
    """Deletes the migration-seeded workflow kinds and walks away — check 2 must fail it.

    `workflow_kinds` has no ORM model, so `auto_clean_tables` never touches it:
    the rows it holds are seeded once by the copy and read by whoever comes next
    in the worker.
    """
    await test_session.execute(text("DELETE FROM workflow_kinds"))
    await test_session.commit()
