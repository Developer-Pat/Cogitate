"""READING a shelf.

Every shelf is a directory whose children are the entries, so the scan is one
function used by four adapters rather than four near-copies. The RUNS shelf
keeps its own reader (its entries carry the run's identity and its files are
known by name); everything else is this.
"""

from __future__ import annotations

import os
from pathlib import Path

from app.domain.trash.interface import TrashEntry

#: How many file names an entry reports. A shelf entry is a retired folder or a
#: retired file, and the reader wants to recognise it — not to receive a
#: recursive listing of a database directory.
_MAX_FILES = 40


def _size_of(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _folder_size(path: Path) -> tuple[int, list[str]]:
    total = 0
    names: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(path):
        for fn in filenames:
            fp = Path(dirpath) / fn
            total += _size_of(fp)
            if len(names) < _MAX_FILES:
                names.append(str(fp.relative_to(path)))
    return total, sorted(names)


def scan_shelf(root: Path) -> list[TrashEntry]:
    """What is on the shelf at `root`, newest first.

    An absent (or unreadable) directory is an EMPTY shelf, never an error: an
    installation starts without a trash, and a person who has never deleted
    anything has nothing to see.
    """
    root = Path(root)
    if not root.is_dir():
        return []

    entries: list[TrashEntry] = []
    for path in sorted(root.iterdir()):
        if path.name.startswith("."):
            continue  # dot-entries are bookkeeping, not shelf contents
        try:
            retired_at = path.stat().st_mtime
        except OSError:
            continue
        if path.is_dir():
            size, files = _folder_size(path)
            entries.append(
                TrashEntry(
                    name=path.name, is_dir=True, size_bytes=size,
                    retired_at=retired_at, files=files,
                )
            )
        else:
            entries.append(
                TrashEntry(
                    name=path.name, is_dir=False, size_bytes=_size_of(path),
                    retired_at=retired_at,
                )
            )
    return sorted(entries, key=lambda e: e.retired_at, reverse=True)
