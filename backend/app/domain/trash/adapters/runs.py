"""The RUNS shelf — retired test-run folders.

A WRAPPER, not a reimplementation. The mechanics that matter here are already
written and tested in `app.domain.testing.trash`: a delete is a MOVE, a run in
progress is not deletable, a colliding name never overwrites, and the contents
are read BEFORE the move so the caller can name what went. This adapter puts
that shelf behind the trash contract so the page's tabs, the API and Exa all
reach it the same way as every other shelf.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.testing.trash import (
    TRASH_SUBDIR,
    list_trash,
    restore_run,
    trash_root,
)
from app.domain.trash.interface import TrashEntry
from app.domain.trash.mechanics import empty_shelf, remove_entry


class RunsTrash:
    #: The shelf's directory name and its registry key are ONE string — the
    #: runs module owns it (it was the first shelf), and the registry validates
    #: it like any other key.
    key = TRASH_SUBDIR
    label = "Test runs"
    restorable = True
    needs_db = False

    def directory(self) -> Path:
        return trash_root()

    async def entries(self, db: AsyncSession | None = None) -> list[TrashEntry]:
        def scan() -> list[TrashEntry]:
            return [
                TrashEntry(
                    name=e.name,
                    is_dir=True,
                    size_bytes=e.size_bytes,
                    retired_at=e.retired_at,
                    files=e.files,
                    restorable=True,
                    note="a retired run — put it back into the runs dir",
                )
                for e in list_trash()
            ]

        return await asyncio.to_thread(scan)

    async def restore(self, name: str, db: AsyncSession | None = None) -> dict[str, Any]:
        result = await asyncio.to_thread(restore_run, name)
        if result is None:
            raise ValueError(f"no run named {name!r} in the trash")
        # The run's own report — where it landed, and whether the name had been
        # taken since. The FACTS about this action are the shelf's to state; the
        # surface adds only that it happened.
        return result.as_dict()

    async def purge(self, name: str, db: AsyncSession | None = None) -> bool:
        return await asyncio.to_thread(remove_entry, self.directory() / name)

    async def empty(self, db: AsyncSession | None = None) -> int:
        return await asyncio.to_thread(empty_shelf, self.directory())
