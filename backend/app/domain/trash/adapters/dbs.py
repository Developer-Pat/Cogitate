"""The DATABASES shelf — retired database backups.

WHAT LANDS HERE: backups taken before a migration or a repair and then retired —
whole-database snapshots, plus the occasional pre-change copy. They are RECOVERY
MATERIAL, which is why they get their own shelf rather than sitting loose among
report folders: a backup looks like junk right up to the moment it is the only
copy of something.

NO RESTORE, and that is a deliberate refusal: putting a backup back means
overwriting a live database, and nothing in this app does that automatically. A
person who wants one restored copies it out and restores it by hand.
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

_PURGE_ONLY = "a retired backup — purge only; putting one back is never automatic"


class DbsTrash:
    key = "dbs"
    label = "Databases"
    restorable = False
    needs_db = False

    def directory(self) -> Path:
        return Paths.trash_dir_for(self.key)

    def _scan(self) -> list[TrashEntry]:
        return [
            replace(e, note=e.note or _PURGE_ONLY)
            for e in scan_shelf(self.directory())
        ]

    async def entries(self, db: AsyncSession | None = None) -> list[TrashEntry]:
        return await asyncio.to_thread(self._scan)

    async def restore(self, name: str, db: AsyncSession | None = None) -> dict[str, Any]:
        raise ValueError(
            f"the databases shelf does not restore — {_PURGE_ONLY}; "
            f"{name!r} can be purged, or copied out by hand"
        )

    async def purge(self, name: str, db: AsyncSession | None = None) -> bool:
        return await asyncio.to_thread(remove_entry, self.directory() / name)

    async def empty(self, db: AsyncSession | None = None) -> int:
        return await asyncio.to_thread(empty_shelf, self.directory())
