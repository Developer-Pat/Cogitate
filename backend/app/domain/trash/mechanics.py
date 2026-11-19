"""REMOVING — the irreversible half, behind one guard.

Every shelf's purge and empty come through here, so the containment rule is
stated once: **nothing is removed that is not inside the trash.** This is the
only place in the trash package that destroys anything, and the check exists
because this is the one act a mistake cannot be walked back.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from app.core.config import Paths


def assert_inside_trash(target: Path) -> Path:
    """Resolve `target` and refuse anything that is not inside the trash dir.

    Raises ValueError. The caller answers 400; the guard is here because a
    wrong destination is a destroyed installation, not a bad request.
    """
    trash = Path(Paths.trash_dir).resolve()
    resolved = Path(target).resolve()
    if resolved != trash and trash not in resolved.parents:
        raise ValueError(
            f"refusing to remove {target} — it is not inside the trash "
            f"({trash})"
        )
    return resolved


def remove_entry(path: Path) -> bool:
    """Remove ONE entry — a file, or a directory and everything in it.

    False when there is nothing at `path` (an entry already gone is not an
    error worth a stack trace). Raises ValueError when the path is outside the
    trash.
    """
    resolved = assert_inside_trash(path)
    if resolved == Path(Paths.trash_dir).resolve():
        raise ValueError("refusing to remove the trash itself")
    if not resolved.exists():
        return False
    if resolved.is_dir():
        shutil.rmtree(resolved)
    else:
        resolved.unlink()
    return True


def empty_shelf(root: Path) -> int:
    """Remove every entry on the shelf at `root`, keeping the shelf directory
    itself. Returns how many went."""
    resolved = assert_inside_trash(root)
    if not resolved.is_dir():
        return 0
    gone = 0
    for path in sorted(resolved.iterdir()):
        if remove_entry(path):
            gone += 1
    return gone
