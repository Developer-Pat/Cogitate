"""The trash: the registry, the locator, the service, and the guards.

The trash removes things permanently, so the tests here are about the GUARDS and
the two structural promises the package makes:

- an UNKNOWN shelf is refused before any directory is touched, so a misspelling
  cannot plant a shelf nothing renders;
- ONE shelf's action never reaches another — emptying the runs must leave the
  backups alone, and the containment rule refuses a directory outside the trash;
- NOTHING in the trash is invisible: the misc shelf carries whatever no other
  shelf claims.

The shelves themselves are tested beside their own domains: the runs shelf in
the testing API suite, the agents shelf in `test_agents_shelf.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Paths
from app.domain.trash.mechanics import empty_shelf, remove_entry
from app.domain.trash.registry import get_domain, list_domains, register_domain
from app.domain.trash.services import TrashService


class _StubShelf:
    """A shelf that satisfies the contract and does nothing — for testing the
    REGISTRY's rules about keys, where the behaviour of a real shelf is noise."""

    def __init__(self, key: str) -> None:
        self.key = key
        self.label = "Stub"
        self.restorable = False
        self.needs_db = False

    def directory(self) -> Path:
        return Paths.trash_dir_for(self.key)

    async def entries(self, db=None) -> list:
        return []

    async def restore(self, name: str, db=None) -> dict:
        raise ValueError("nothing to restore to")

    async def purge(self, name: str, db=None) -> bool:
        return False

    async def empty(self, db=None) -> int:
        return 0


@pytest.fixture
def trash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A trash inside a temp dir. A test must never touch the real one."""
    target = tmp_path / "trash"
    monkeypatch.setattr(Paths, "trash_dir", target)
    return target


def _shelf(trash: Path, key: str, *names: str) -> Path:
    """Put `names` on the `key` shelf, making the directory on the way."""
    shelf = trash / key
    shelf.mkdir(parents=True, exist_ok=True)
    for name in names:
        (shelf / name).write_text(f"{name} contents")
    return shelf


# ── the registry: the vocabulary, and what it refuses ───────────────────────


def test_an_UNKNOWN_shelf_is_refused_by_name(trash: Path) -> None:
    """A misspelling reads as a misspelling — and, critically, CREATES NOTHING.

    A shelf planted by a typo would be a directory nothing renders: exactly the
    invisible holding area this package exists to remove.
    """
    with pytest.raises(ValueError) as caught:
        get_domain("agnts")

    assert "agnts" in str(caught.value)
    assert "test-runs" in str(caught.value)        # the message names the real ones
    assert not trash.exists()


def test_a_shelf_key_must_be_ONE_clean_path_segment(trash: Path) -> None:
    """`../x`, `a/b` and a dot-name are refused at registration — the locator's
    own shape rule, applied where the vocabulary lives."""
    for bad in ("a/b", "..", ".hidden", ""):
        with pytest.raises(ValueError):
            register_domain(_StubShelf(bad))
    assert not trash.exists()


def test_two_shelves_cannot_share_a_key(trash: Path) -> None:
    """A doubled key would silently make one shelf inherit the other's entries."""
    with pytest.raises(ValueError) as caught:
        register_domain(_StubShelf("dbs"))
    assert "already has a shelf" in str(caught.value)


def test_the_locator_refuses_a_MALFORMED_shelf_name(trash: Path) -> None:
    for bad in ("agnts/../x", "..", ".hidden", "", "a/b"):
        with pytest.raises(ValueError):
            Paths.trash_dir_for(bad)
    # and a clean name resolves UNDER the trash, with no arithmetic at the site
    assert Paths.trash_dir_for("agents") == trash / "agents"


def test_every_shelf_has_its_OWN_directory(trash: Path) -> None:
    """Two shelves over one directory is the silent collision this map exists to
    prevent: one shelf would inherit the other's entries."""
    directories = [d.directory() for d in list_domains()]
    assert len(set(directories)) == len(directories)


# ── the service: one policy over every shelf ────────────────────────────────


async def test_shelves_reports_every_shelf_with_a_count_and_zero_when_absent(
    trash: Path, test_session,
) -> None:
    """A shelf with no directory reports ZERO rather than vanishing — a tab that
    disappears cannot tell you it is empty."""
    rows = await TrashService().shelves(test_session)
    assert [r["key"] for r in rows] == [d.key for d in list_domains()]
    assert all(r["count"] == 0 for r in rows)
    assert all("restorable" in r and "directory" in r for r in rows)


async def test_listing_an_absent_shelf_is_an_honest_EMPTY(trash: Path) -> None:
    listing = await TrashService().listing("dbs")
    assert listing["count"] == 0
    assert listing["entries"] == []
    assert listing["directory"].endswith("trash/dbs")


async def test_purge_removes_one_entry_and_admits_a_missing_one(trash: Path) -> None:
    """False — not an exception and not a claim of success — when there is
    nothing to remove; the caller answers 404 rather than inventing a win."""
    _shelf(trash, "dbs", "old.db")
    service = TrashService()

    assert await service.purge("dbs", "old.db") is True
    assert not (trash / "dbs" / "old.db").exists()
    assert await service.purge("dbs", "old.db") is False


async def test_empty_clears_ONE_shelf_and_leaves_its_neighbours(trash: Path) -> None:
    """No phrase and no policy — the caller has already decided. What the service
    still owns is WHICH shelf, and one shelf's empty never reaches another."""
    _shelf(trash, "dbs", "old.db")
    _shelf(trash, "misc", "loose.txt")
    service = TrashService()

    answer = await service.empty("dbs")

    assert answer == {"emptied": True, "domain": "dbs", "deleted": 1}
    assert not (trash / "dbs" / "old.db").exists()
    # THE SIBLING SHELF SURVIVES — the property that matters now there is more
    # than one shelf.
    assert (trash / "misc" / "loose.txt").exists()


async def test_a_shelf_with_NO_way_back_says_so(trash: Path) -> None:
    """Reports, databases and misc have no record of where their entries came
    from, so restore refuses in the shelf's own words instead of offering a
    button that cannot work."""
    _shelf(trash, "dbs", "old.db")
    with pytest.raises(ValueError) as caught:
        await TrashService().restore("dbs", "old.db")
    assert "does not restore" in str(caught.value)


# ── nothing in the trash is invisible ──────────────────────────────────────


async def test_misc_is_the_FALLBACK_bucket(trash: Path) -> None:
    """A loose file in the root is an ENTRY on the misc shelf; a registered
    shelf's directory is never mistaken for one; and misc refuses to purge a
    shelf by name."""
    trash.mkdir(parents=True, exist_ok=True)
    (trash / "START_APP.sh").write_text("#!/bin/sh\n")
    (trash / "stray-dir").mkdir()
    _shelf(trash, "dbs", "old.db")
    service = TrashService()

    names = [e["name"] for e in (await service.listing("misc"))["entries"]]

    assert "START_APP.sh" in names
    assert "stray-dir" in names
    assert "dbs" not in names                      # a shelf, not an entry

    with pytest.raises(ValueError) as caught:
        await service.purge("misc", "dbs")
    assert "is a trash SHELF" in str(caught.value)
    assert (trash / "dbs" / "old.db").exists()


# ── the containment rule, on the one act that cannot be walked back ────────


def test_removal_refuses_anything_OUTSIDE_the_trash(trash: Path) -> None:
    """A wrong directory takes a whole tree with it, so it is refused rather
    than obeyed."""
    outside = trash.parent / "not-the-trash"
    outside.mkdir(parents=True)
    (outside / "precious.txt").write_text("keep me")

    with pytest.raises(ValueError):
        empty_shelf(outside)
    with pytest.raises(ValueError):
        remove_entry(outside / "precious.txt")

    assert (outside / "precious.txt").exists()
