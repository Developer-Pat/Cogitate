"""
SAVING a run — the person KEEPS it.

THE USER'S OWN COPY. *"Save the report"* (the design's §8) means exactly that: a
copy of the run's folder goes somewhere the person names, and **nothing is implied
about this app keeping anything** — no repository, no rolling, no retention, no
index of what has been saved. The runs dir is untouched: Save COPIES, it never
moves, so the page's own history is exactly as it was.

**ALL THREE ARTIFACTS GO**, not just `report.md`. The markdown is the console tail;
the counts the page shows come from `report.xml`, and the events file is what the
diff reads. A save that kept only the third of a run that reads well in an editor
would be a save that loses the reason to open it.

WHAT IT REFUSES, each with its own reason:

- **A run the lock is writing** — its artifacts are mid-write and the copy would be
  a torn one. The refusal is the lock's own sentence.
- **An occupied destination** — an existing run folder is refused BY NAME rather
  than overwritten: a save that silently replaced an earlier one is not a save.
- **A destination inside the runs dir or the trash** — those two directories ARE
  the page's state, and writing into them by hand is how they stop meaning what
  they mean.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Paths
from app.domain.testing.reports import resolve_run_dir
from app.domain.testing.run_lock import RunInProgress, read_lock
from app.domain.testing.trash import running_run_name


@dataclass(frozen=True)
class SavedRun:
    """Where a run was copied to, so the caller can name the exact path."""

    name: str
    saved_to: Path
    files: list[str]

    def as_dict(self) -> dict[str, object]:
        """The shape the API returns — a path RELATIVE to the project root when it
        is inside one, so the answer is meaningful in a browser and honest when the
        person saved somewhere else entirely."""
        root = Path(Paths.root)
        try:
            where = str(self.saved_to.relative_to(root))
        except ValueError:
            where = str(self.saved_to)
        return {"name": self.name, "saved_to": where, "files": self.files}


def default_destination() -> Path:
    """Where a save goes when the person has not named anywhere else."""
    return Path(Paths.test_reports_dir)


def _refuse_protected(destination: Path) -> None:
    """The runs dir and the trash are STATE, not a filing cabinet."""
    protected = {
        "the test runs": Path(Paths.test_runs_dir).resolve(),
        "the trash": Path(Paths.trash_dir).resolve(),
    }
    resolved = destination.resolve()
    for what, where in protected.items():
        if resolved == where or where in resolved.parents:
            raise ValueError(f"cannot save into {what} — choose a destination outside it")


def save_run(
    name: str,
    destination: str | Path | None = None,
    runs_dir: Path | None = None,
) -> SavedRun | None:
    """Copy one run's folder into `destination/<name>/`.

    None when there is no such run (the caller answers 404). Raises RunInProgress
    for the run the lock is writing, ValueError for a destination that cannot be
    used, and FileExistsError when that run has already been saved there.
    """
    runs = Path(runs_dir) if runs_dir is not None else Path(Paths.test_runs_dir)

    if running_run_name(runs) == name:
        raise RunInProgress(read_lock(runs), stale=False)

    source = resolve_run_dir(runs, name)
    if source is None:
        return None

    if destination is None or str(destination).strip() == "":
        target_root = default_destination()
    else:
        target_root = Path(str(destination)).expanduser()
        if not target_root.is_absolute():
            # A relative path is relative to the PROJECT, not to whatever directory
            # the server happens to be running in — the same rule as the runner's
            # `--runs-dir`.
            target_root = Path(Paths.root) / target_root

    _refuse_protected(target_root)
    target_root.mkdir(parents=True, exist_ok=True)

    target = target_root / source.name
    if target.exists():
        raise FileExistsError(
            f"{source.name} is already saved at {target} — move or rename that copy first"
        )

    # copytree, not move: the run stays where the page can still read it, and the
    # copy is independent from then on.
    shutil.copytree(source, target)
    files = sorted(p.name for p in target.iterdir() if p.is_file())
    return SavedRun(name=name, saved_to=target, files=files)
