"""The MISC shelf — the fallback bucket.

WHAT LANDS HERE: everything in the trash that no other shelf claims — a loose
file dropped in the root, a directory nobody registered, a shelf's leftovers
after something else moved in. It exists so that the trash ROOT itself has no
invisible content: whatever is not a shelf is an ENTRY, and an entry is shown.

WHY THAT MATTERS. The failure this package exists to remove is a holding area
whose contents no surface can read. A registry with a fallback cannot produce
that state: the tabs are the registered shelves plus this one, so there is
nowhere left for a file to hide.

NO RESTORE, by construction: by the time something is here, nothing knows what
it belonged to. Removing it is the only verb.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Paths
from app.domain.trash.interface import TrashEntry
from app.domain.trash.listing import scan_shelf
from app.domain.trash.mechanics import empty_shelf, remove_entry

_LOOSE = "not claimed by any shelf — purge only"


class MiscTrash:
    key = "misc"
    label = "Misc"
    restorable = False
    needs_db = False

    def directory(self) -> Path:
        return Paths.trash_dir_for(self.key)

    def _claimed(self) -> set[str]:
        """The shelf keys — imported at CALL time, because the registry imports
        this module."""
        from app.domain.trash.registry import list_domains

        return {d.key for d in list_domains()}

    def _scan(self) -> list[TrashEntry]:
        claimed = self._claimed()
        parked = [replace(e, note=e.note or _LOOSE) for e in scan_shelf(self.directory())]
        loose = [
            replace(e, note=_LOOSE)
            for e in scan_shelf(Path(Paths.trash_dir))
            if e.name not in claimed
        ]
        return sorted(parked + loose, key=lambda e: e.retired_at, reverse=True)

    async def entries(self, db: AsyncSession | None = None) -> list[TrashEntry]:
        return await asyncio.to_thread(self._scan)

    async def restore(self, name: str, db: AsyncSession | None = None) -> dict[str, Any]:
        raise ValueError(
            f"the misc shelf does not restore — nothing records what {name!r} "
            f"belonged to; it can be purged, or moved by hand"
        )

    def _purge_now(self, name: str) -> bool:
        if name in self._claimed():
            raise ValueError(
                f"{name!r} is a trash SHELF, not an entry — empty it through "
                f"its own domain"
            )
        parked = self.directory() / name
        if parked.exists():
            return remove_entry(parked)
        return remove_entry(Path(Paths.trash_dir) / name)

    async def purge(self, name: str, db: AsyncSession | None = None) -> bool:
        return await asyncio.to_thread(self._purge_now, name)

    def _empty_now(self) -> int:
        """Clear the parked shelf AND the loose entries. Both are Misc's to
        clear, and the shelf's own directory stays where it is."""
        gone = empty_shelf(self.directory())
        for entry in self._scan():
            if entry.name in self._claimed():
                continue
            if (self.directory() / entry.name).exists():
                continue  # already cleared with the shelf
            if remove_entry(Path(Paths.trash_dir) / entry.name):
                gone += 1
        return gone

    async def empty(self, db: AsyncSession | None = None) -> int:
        return await asyncio.to_thread(self._empty_now)
