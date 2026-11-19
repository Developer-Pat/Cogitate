"""
Deleting a RUN — a MOVE, never an unlink.

THE USER-TESTING PAGE. A person who ran a run should be able to get rid of it,
and C1 filed that as this page's own action: one folder, chosen by hand, no
retention rule and no pruning anywhere. This is that one action.

WHY A MOVE AND NOT `shutil.rmtree`. A run is a small directory of artifacts a
person may have been reading a second ago, and the page cannot ask "are you
sure?" about something it has already destroyed. Moving the folder into the
trash keeps the action recoverable: `trash/test-runs/<name>/` holds exactly the
run that was there, with its report.md, report.xml and events.jsonl intact. The
precedent is this project's own: the pre-B0 reports were moved to
`trash/reports/` rather than deleted, and the db backups live in `trash/dbs/`.

WHAT IT REFUSES. **A run in progress is not deletable.** The lock already knows
which run that is; deleting the folder under a live run would break its stream
and strand its artifacts mid-write. The refusal is the lock's own sentence, so
the reason arrives from the state rather than from this module's opinion.

WHAT IT CANNOT DO. It cannot delete a run a person started from a terminal and
left half-finished with no lock — there is nothing to stop. And it does not
touch the runs dir's `.run.lock`: the trash holds run FOLDERS, and the lock is
state, not a run.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Paths
from app.domain.testing.reports import resolve_run_dir
from app.domain.testing.run_lock import RunInProgress, read_lock

#: The shelf that holds retired runs. The name IS the trash registry key (the
#: trash's domain registry validates it like any other), and it is read by the
#: locator's `trash_dir_for` — never composed at a call site.
TRASH_SUBDIR = "test-runs"

#: How many colliding names to try before giving up. A name repeats only when a
#: run is restored and deleted again, so this is generous rather than tight.
_MAX_SUFFIX = 100


@dataclass(frozen=True)
class TrashedRun:
    """Where a run went, so the caller can say where it is."""

    name: str
    moved_to: Path
    contents: list[str]

    def as_dict(self) -> dict[str, object]:
        """The shape the API returns — a path RELATIVE to the project root, so
        the answer is meaningful to a person reading it in a browser."""
        root = Path(Paths.root)
        try:
            relative = str(self.moved_to.relative_to(root))
        except ValueError:
            relative = str(self.moved_to)
        return {"name": self.name, "moved_to": relative, "contents": self.contents}


def trash_root() -> Path:
    """Where retired runs are kept — `trash/test-runs`, resolved by the
    locator (a shelf is asked for by name; it is never composed here)."""
    return Paths.trash_dir_for(TRASH_SUBDIR)


def _resolve(run_dir: Path, name: str) -> Path | None:
    """Kept as the name this module's callers use; the rule itself lives in one
    place (`reports.resolve_run_dir`), so the reader, the trash and Save cannot
    come to disagree about what containment means."""
    return resolve_run_dir(run_dir, name)


def _free_name(trash: Path, name: str) -> str:
    """`name`, or `name-2`, `name-3`… when the trash already holds that name.

    Never overwrite: the run in the trash may be the earlier copy of a run that
    was restored and deleted again, and silently replacing it would destroy the
    very thing the trash exists to keep.
    """
    if not (trash / name).exists():
        return name
    for n in range(2, _MAX_SUFFIX + 2):
        candidate = f"{name}-{n}"
        if not (trash / candidate).exists():
            return candidate
    raise RuntimeError(f"the trash holds {_MAX_SUFFIX} copies of {name} already")


def running_run_name(runs_dir: Path | None = None) -> str | None:
    """The id of the run in progress, or None.

    The LOCK's answer, not a page-side guess: it is the same source the
    `/runs/current` endpoint reports, so "you cannot delete the running run"
    and "a run is in progress" can never disagree.
    """
    lock = read_lock(Path(runs_dir) if runs_dir is not None else Path(Paths.test_runs_dir))
    if lock is None or not lock.alive():
        return None
    return lock.id


def trash_run(name: str, runs_dir: Path | None = None, trash: Path | None = None) -> TrashedRun | None:
    """Move one run folder into the trash.

    Returns None when there is no such run (the caller answers 404 — a name that
    is not a run is not an error worth a stack trace). Raises RunInProgress when
    the run named is the one IN PROGRESS, because that is a refusal the caller
    must be able to state.

    The move is a RENAME on the same filesystem, so nothing is copied and a
    crash mid-way cannot leave half a run in each place; shutil.move falls back
    to copy+unlink across filesystems, which the trash dir never is.
    """
    runs = Path(runs_dir) if runs_dir is not None else Path(Paths.test_runs_dir)
    live = running_run_name(runs)
    if live == name:
        held = read_lock(runs)
        raise RunInProgress(held, stale=False)

    source = _resolve(runs, name)
    if source is None:
        return None

    # Read the contents BEFORE the move, so the caller can name what went.
    contents = sorted(p.name for p in source.iterdir() if p.is_file())

    destination_root = Path(trash) if trash is not None else trash_root()
    destination_root.mkdir(parents=True, exist_ok=True)
    moved_to = destination_root / _free_name(destination_root, source.name)
    shutil.move(str(source), str(moved_to))

    return TrashedRun(name=name, moved_to=moved_to, contents=contents)


# ── what is IN the trash, and the two ways out of it ────────────────────────


@dataclass(frozen=True)
class TrashedEntry:
    """One retired run, as the trash view reads it."""

    name: str
    files: list[str]
    size_bytes: int
    #: When it was retired: the folder's mtime, an observation of THIS machine
    #: rather than a property of the run.
    retired_at: float

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "files": self.files,
            "size_bytes": self.size_bytes,
            "retired_at": self.retired_at,
        }


def list_trash(trash: Path | None = None) -> list[TrashedEntry]:
    """What has been retired, newest first.

    An absent trash dir is an EMPTY trash, not an error: an installation starts
    without one, and a person who has never retired a run has nothing to see.
    """
    root = Path(trash) if trash is not None else trash_root()
    if not root.is_dir():
        return []

    entries: list[TrashedEntry] = []
    for path in sorted(root.iterdir()):
        if not path.is_dir():
            continue
        files = sorted(p.name for p in path.rglob("*") if p.is_file())
        size = sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
        entries.append(
            TrashedEntry(
                name=path.name,
                files=files,
                size_bytes=size,
                retired_at=path.stat().st_mtime,
            )
        )
    return sorted(entries, key=lambda e: e.retired_at, reverse=True)


@dataclass(frozen=True)
class RestoredRun:
    """Where a run went BACK to — which may not be the name it left with."""

    name: str
    restored_to: Path
    #: True when the name it left with was taken, so it came back as `name-2`.
    renamed: bool

    def as_dict(self) -> dict[str, object]:
        root = Path(Paths.root)
        try:
            relative = str(self.restored_to.relative_to(root))
        except ValueError:
            relative = str(self.restored_to)
        return {"name": self.name, "restored_to": relative, "renamed": self.renamed}


def restore_run(
    name: str,
    runs_dir: Path | None = None,
    trash: Path | None = None,
) -> RestoredRun | None:
    """Move a retired run back into the runs dir — the way BACK, and the reason a
    delete here is a move rather than a loss.

    Returns None when the trash holds no such run. A name that has since been
    taken (the run was re-created from the page, or the folder was restored
    twice) gets the same collision suffix a delete uses, and the answer SAYS so
    rather than quietly returning a run under a different name.
    """
    runs = Path(runs_dir) if runs_dir is not None else Path(Paths.test_runs_dir)
    root = Path(trash) if trash is not None else trash_root()
    source = _resolve(root, name)
    if source is None:
        return None

    runs.mkdir(parents=True, exist_ok=True)
    final = _free_name(runs, source.name)
    destination = runs / final
    shutil.move(str(source), str(destination))
    return RestoredRun(name=name, restored_to=destination, renamed=final != name)


# ── emptying the shelf is NOT here ──────────────────────────────────────────
#
# Removing entries from a shelf — with the containment guard that stops a wrong
# directory from being wiped — is `app.domain.trash.mechanics`. This module owns
# what is runs-specific: THE MOVE (trash_run / restore_run), the collision rule,
# and the lock question. Two implementations of "empty" would drift, and the
# guard is the half that must never drift.
