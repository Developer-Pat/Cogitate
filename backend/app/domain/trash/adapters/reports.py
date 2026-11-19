"""The REPORTS shelf — retired report areas.

WHAT LANDS HERE: report directories that were moved out of the way rather than
deleted — the pre-B0 run reports, and Exa's earlier health-report area. Nothing
writes here on its own; a person or a script moved them.

NO RESTORE. Nothing recorded where they came from, so there is no honest
destination to offer and the shelf says so instead of presenting a button that
cannot work.
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

_NO_RECORD = "no record of where this came from — purge only"


class ReportsTrash:
    key = "reports"
    label = "Reports"
    restorable = False
    needs_db = False

    def directory(self) -> Path:
        return Paths.trash_dir_for(self.key)

    def _scan(self) -> list[TrashEntry]:
        return [
            replace(e, note=e.note or _NO_RECORD)
            for e in scan_shelf(self.directory())
        ]

    async def entries(self, db: AsyncSession | None = None) -> list[TrashEntry]:
        return await asyncio.to_thread(self._scan)

    async def restore(self, name: str, db: AsyncSession | None = None) -> dict[str, Any]:
        raise ValueError(
            f"the reports shelf does not restore — {_NO_RECORD}; "
            f"{name!r} can be purged, or moved by hand"
        )

    async def purge(self, name: str, db: AsyncSession | None = None) -> bool:
        return await asyncio.to_thread(remove_entry, self.directory() / name)

    async def empty(self, db: AsyncSession | None = None) -> int:
        return await asyncio.to_thread(empty_shelf, self.directory())
