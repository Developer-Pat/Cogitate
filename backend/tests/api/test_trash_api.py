"""The trash API — one surface over every shelf, and the promises it must keep.

Three of them are worth more than the average route test, because each is a way
the surface could quietly become a lie:

- **The shelves come from the REGISTRY.** The tab list is asserted to be the
  registry's own order, so a sixth shelf is a registration rather than a page
  edit — and a shelf with no directory reports ZERO rather than vanishing.
- **One shelf's act never reaches another.** Emptying one shelf must leave its
  neighbours intact; that is the property that matters now that one root holds
  four unrelated things, including database backups.
- **404 and 400 mean different things.** NOT THERE (a stale row) is told apart
  from REFUSED BY THE SHELF (reports keeps no record to restore to; the misc
  bucket will not take a shelf). A surface that answered both the same way would
  leave the page unable to say which happened.

The route functions are called directly, the way the testing API's own suite
does it, with the session the routes are really handed: the fixtures point
`Paths` at a temp directory, so nothing here can touch the operator's real trash.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.trash.router import (
    DestructiveRequest,
    empty_shelf,
    get_shelf,
    get_shelves,
    purge_entry,
    restore_entry,
)
from app.core.config import Paths
from app.domain.trash.registry import list_domains

#: The intent flag the destructive verbs require — see `DestructiveRequest`. The
#: tests below are about the SHELVES' behaviour, so they all declare it; the guard
#: itself has its own test, where the flag is what is missing.
CONFIRM = DestructiveRequest(confirm=True)


@pytest.fixture
def trash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A trash inside a temp dir. A test must never touch the real one.

    `root` moves with it: a listing's `directory` is reported relative to the
    installation, so the assertion is about that shape rather than about a temp
    path that merely happens to be absolute.
    """
    target = tmp_path / "trash"
    monkeypatch.setattr(Paths, "trash_dir", target)
    monkeypatch.setattr(Paths, "root", tmp_path)
    return target


def _shelf(trash: Path, key: str, *names: str) -> Path:
    """Put `names` on the `key` shelf, making the directory on the way."""
    shelf = trash / key
    shelf.mkdir(parents=True, exist_ok=True)
    for name in names:
        (shelf / name).write_text(f"{name} contents")
    return shelf


# ── the intent flag: a bare POST cannot destroy anything ────────────────────


async def test_a_destructive_verb_without_confirm_is_REFUSED(
    trash: Path, test_session: AsyncSession,
) -> None:
    """The cheap structural stop, and its LIMIT stated as a test.

    `confirm: true` separates a caller that decided from a POST that merely
    arrived. It does not stop a caller who means it — that is the design, and
    saying so here is what keeps the flag from being read as a gate.
    """
    _shelf(trash, "dbs", "old.db")
    _shelf(trash, "test-runs", "20260101-000000")

    for absent in (None, DestructiveRequest(), DestructiveRequest(confirm=False)):
        with pytest.raises(HTTPException) as caught:
            await purge_entry("dbs", "old.db", test_session, body=absent)
        assert caught.value.status_code == 400
        assert "confirm: true" in caught.value.detail

        with pytest.raises(HTTPException) as caught:
            await empty_shelf("dbs", test_session, body=absent)
        assert caught.value.status_code == 400
        assert "confirm: true" in caught.value.detail

    assert (trash / "dbs" / "old.db").exists()            # nothing was removed
    assert (trash / "test-runs" / "20260101-000000").exists()

    # The flag does not REPLACE the shelf's own checks: a misspelled shelf is
    # still refused before any directory is touched, flag or no flag.
    with pytest.raises(HTTPException) as caught:
        await empty_shelf("agnts", test_session, body=CONFIRM)
    assert caught.value.status_code == 404


# ── the tab list, which the page renders and never hand-writes ──────────────


async def test_the_shelves_are_the_REGISTRY_in_registration_order(
    trash: Path, test_session: AsyncSession,
) -> None:
    """The tab list is the registry's — including the count and the directory
    each tab needs — so a new shelf appears without a frontend edit."""
    answer = await get_shelves(test_session)

    assert [s["key"] for s in answer["shelves"]] == [d.key for d in list_domains()]
    assert [s["key"] for s in answer["shelves"]] == [
        "agents", "test-runs", "reports", "dbs", "misc",
    ]
    for shelf in answer["shelves"]:
        assert shelf["label"].strip()
        assert shelf["restorable"] in (True, False)
        assert shelf["directory"].startswith("trash/")
        assert shelf["count"] == 0          # no directory yet — ZERO, not absent


async def test_a_shelf_reports_its_entries_and_what_each_one_IS(
    trash: Path, test_session: AsyncSession,
) -> None:
    _shelf(trash, "dbs", "old.db")

    listing = await get_shelf("dbs", test_session)

    assert listing["key"] == "dbs"
    assert listing["count"] == 1
    assert listing["entries"][0]["name"] == "old.db"
    assert listing["entries"][0]["restorable"] is False    # a backup: purge only
    assert listing["entries"][0]["note"]                   # what it IS, stated
    assert listing["directory"] == "trash/dbs"


async def test_an_unknown_shelf_is_a_404_that_names_the_real_ones_and_PLANTS_nothing(
    trash: Path, test_session: AsyncSession,
) -> None:
    """A misspelling reads as a misspelling — and creates no directory, which is
    the invisible-holding-area failure this whole package removes."""
    with pytest.raises(HTTPException) as caught:
        await get_shelf("agnts", test_session)

    assert caught.value.status_code == 404
    assert "agnts" in caught.value.detail
    assert "test-runs" in caught.value.detail
    assert not trash.exists()


# ── purge: one entry, permanently, and never a claim it did not earn ────────


async def test_purge_removes_one_entry_and_404s_once_it_is_gone(
    trash: Path, test_session: AsyncSession,
) -> None:
    _shelf(trash, "dbs", "old.db")

    answer = await purge_entry("dbs", "old.db", test_session, body=CONFIRM)
    assert answer == {"purged": True, "shelf": "dbs", "name": "old.db"}
    assert not (trash / "dbs" / "old.db").exists()

    # The second attempt is a 404 — a stale row, not a refusal, and not a win.
    with pytest.raises(HTTPException) as caught:
        await purge_entry("dbs", "old.db", test_session, body=CONFIRM)
    assert caught.value.status_code == 404
    assert "old.db" in caught.value.detail


async def test_one_shelfs_purge_cannot_reach_ANOTHER(
    trash: Path, test_session: AsyncSession,
) -> None:
    """The property the one-root design must not lose: dbs holds recovery
    material, and the runs shelf's verbs have no path to it."""
    _shelf(trash, "dbs", "old.db")
    _shelf(trash, "test-runs", "20260101-000000")

    await purge_entry("dbs", "old.db", test_session, body=CONFIRM)

    assert (trash / "test-runs" / "20260101-000000").exists()
    assert not (trash / "dbs" / "old.db").exists()


async def test_a_purge_through_MISC_cannot_take_a_SHELF(
    trash: Path, test_session: AsyncSession,
) -> None:
    """Misc claims the loose entries; a shelf is not an entry. The shelf's own
    refusal arrives as a 400 — a 500 here would mean the guard fired and the API
    swallowed it."""
    _shelf(trash, "dbs", "old.db")

    with pytest.raises(HTTPException) as caught:
        await purge_entry("misc", "dbs", test_session, body=CONFIRM)

    assert caught.value.status_code == 400
    assert "is a trash SHELF" in caught.value.detail
    assert (trash / "dbs" / "old.db").exists()


# ── restore: only where a record exists to restore TO ───────────────────────


async def test_a_shelf_with_NO_way_back_refuses_restore_in_its_own_words(
    trash: Path, test_session: AsyncSession,
) -> None:
    _shelf(trash, "reports", "old-reports")

    with pytest.raises(HTTPException) as caught:
        await restore_entry("reports", "old-reports", test_session)

    assert caught.value.status_code == 400
    assert "does not restore" in caught.value.detail
    assert (trash / "reports" / "old-reports").exists()   # untouched by a refusal


async def test_restoring_something_that_is_not_there_is_a_404_not_a_refusal(
    trash: Path, test_session: AsyncSession,
) -> None:
    """The distinction the pre-check buys: an unknown entry could be stale or
    misspelled — either way the shelf was never asked to decide."""
    with pytest.raises(HTTPException) as caught:
        await restore_entry("test-runs", "20260101-000000", test_session)

    assert caught.value.status_code == 404
    assert "20260101-000000" in caught.value.detail


# ── empty: one shelf, its own entries, and nothing else ─────────────────────


async def test_empty_takes_one_shelf_and_leaves_its_neighbours(
    trash: Path, test_session: AsyncSession,
) -> None:
    """The verb is per SHELF, and the count it answers with is what actually went.

    No phrase: the caller has already decided, and a sentence retyped from the
    dialog in front of them was never a guard. What remains — and is asserted
    here — is the containment that gives the verb its scope: one shelf's empty
    does not reach its neighbour's entries, and the shelf directory itself stays.
    """
    _shelf(trash, "dbs", "old.db", "older.db")
    _shelf(trash, "test-runs", "20260101-000000")

    answer = await empty_shelf("dbs", test_session, body=CONFIRM)

    assert answer == {"emptied": True, "domain": "dbs", "deleted": 2}
    assert not (trash / "dbs" / "old.db").exists()
    assert not (trash / "dbs" / "older.db").exists()
    assert (trash / "test-runs" / "20260101-000000").exists()
    assert (trash / "dbs").is_dir()          # the shelf directory itself stays


# ── the announce: no other tab is left showing a row that is gone ───────────


@pytest.fixture
def runs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The runs dir, aimed at a temp dir so a restore has somewhere to land."""
    target = tmp_path / "runs"
    target.mkdir()
    monkeypatch.setattr(Paths, "test_runs_dir", target)
    return target


@pytest.fixture
def bus():
    """Collect every trash event published during a test — on the real bus."""
    from app.domain.messaging.services import event_bus

    event_bus.clear()
    seen: list[tuple[str, dict]] = []

    def handler(topic, payload):
        seen.append((topic, payload))

    event_bus.subscribe("trash:*", handler)
    yield seen
    event_bus.unsubscribe("trash:*", handler)
    event_bus.clear()


async def test_each_verb_announces_its_own_KIND(
    trash: Path, runs_dir: Path, bus, test_session: AsyncSession,
) -> None:
    """The cross-window contract, pinned on the BUS rather than on a mock.

    The topic is `trash:<shelf>:<event>` and the KIND rides in the payload — the
    bus hands a handler only the payload, so a `trash:*` subscriber receiving
    restored/purged/emptied without `event` could not tell them apart (the
    `useDomainSync('trash')` consumer reloads on any of them).
    """
    _shelf(trash, "dbs", "old.db")
    run = trash / "test-runs" / "20260101-000000"
    run.mkdir(parents=True)                  # the runs shelf reads DIRECTORIES
    (run / "report.md").write_text("x")

    await restore_entry("test-runs", "20260101-000000", test_session)
    await purge_entry("dbs", "old.db", test_session, body=CONFIRM)
    _shelf(trash, "dbs", "another.db")
    await empty_shelf("dbs", test_session, body=CONFIRM)

    # The payload is asserted by the fields THIS contract promises: the bus
    # stamps its own `event_id` alongside them (the replay dedupe), and pinning
    # the whole dict would make this test fail every time the bus grows a field.
    assert [t for t, _ in bus] == [
        "trash:test-runs:restored",
        "trash:dbs:purged",
        "trash:dbs:emptied",
    ]
    assert [p.get("id") for _, p in bus] == ["test-runs", "dbs", "dbs"]
    assert [p.get("event") for _, p in bus] == ["restored", "purged", "emptied"]
    assert [p.get("name") for _, p in bus] == ["20260101-000000", "old.db", None]
