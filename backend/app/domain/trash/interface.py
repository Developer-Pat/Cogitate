"""THE TRASH DOMAIN CONTRACT.

A DOMAIN is a shelf: a directory under the trash, the entries on it, and the two
ways off it. RESTORE puts a thing back where it came from, and exists only where
a RECORD of that exists (an agent has a row naming its workspace; a retired run
knows its runs dir). PURGE is the irreversible one.

WHY THE VERBS ARE ASYNC. Four shelves are pure filesystem work, and one — the
agents — is ROW-BACKED: whether an entry can be restored, and what purging it
means, is a question only the database can answer. A synchronous contract would
have forced that shelf out of the registry and left the page with a special case;
one async verb set keeps every shelf answered the same way.

WHAT A DOMAIN DOES NOT DO:

- It does not guard its own `empty()`. Emptying a shelf is a deliberate act, and
  the decision to make it is the CALLER's — the shelf carries it out rather than
  asking again. What is enforced here is mechanical and is the one thing that
  must never be skipped: containment. Nothing outside the trash is ever removed,
  and every path that destroys anything goes through that check.
- It does not decide what the page shows. It reports FACTS — what is there, how
  big, how old, and whether a record exists to restore it to — and the page
  presents them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class TrashEntry:
    """One thing on a shelf, as a reader needs it.

    `retired_at` is the entry's own mtime — an observation of THIS machine, not
    a property of the thing (the same wording the test-runs trash uses for its
    retired runs, and true for every shelf here).
    """

    name: str
    is_dir: bool
    size_bytes: int
    retired_at: float
    #: What is inside, for a directory; empty for a loose file.
    files: list[str] = field(default_factory=list)
    #: True only when a record exists to put this entry BACK to.
    restorable: bool = False
    #: Why it is not restorable, or what the entry is — shown, not guessed at.
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "is_dir": self.is_dir,
            "size_bytes": self.size_bytes,
            "retired_at": self.retired_at,
            "files": self.files,
            "restorable": self.restorable,
            "note": self.note,
        }


@runtime_checkable
class TrashDomain(Protocol):
    """One shelf. Every verb here is a FACT or a MECHANICAL act; policy is the
    service's."""

    #: The registry key AND the directory name — one clean path segment.
    key: str
    #: What a person sees on the tab.
    label: str
    #: Whether this shelf has a way back at all.
    restorable: bool
    #: True when the shelf's answers depend on the database (the agents shelf,
    #: whose entries are row-backed); the service then requires a session.
    needs_db: bool

    def directory(self) -> Path:
        """Where the shelf lives — always via the locator, never arithmetic."""
        ...

    async def entries(self, db: AsyncSession | None = None) -> list[TrashEntry]:
        """What is on the shelf, newest first. An absent shelf is EMPTY, never
        an error: an installation starts without one."""
        ...

    async def restore(self, name: str, db: AsyncSession | None = None) -> dict[str, Any]:
        """Put one entry back. Raises ValueError when the shelf cannot, or when
        the entry is not there."""
        ...

    async def purge(self, name: str, db: AsyncSession | None = None) -> bool:
        """Remove ONE entry permanently. False when there is no such entry."""
        ...

    async def empty(self, db: AsyncSession | None = None) -> int:
        """Remove EVERY entry on this shelf. Returns how many went."""
        ...
