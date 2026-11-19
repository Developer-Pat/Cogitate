"""THE TRASH SERVICE — the ONE policy layer over every shelf.

The verbs are the same for all shelves, so they live here and nowhere else:

    shelves(db)                  what the page's TABS render from
    listing(key, db)             one shelf: its entries and its directory
    restore(key, name, db)       put one entry back where it came from
    purge(key, name, db)         remove ONE entry permanently
    empty(key, db)               remove every entry on the shelf

WHAT BELONGS HERE, AND WHY IT IS NOT IN THE SHELVES. One thing is policy rather
than mechanics: **which shelf you are talking to**, resolved once, so an unknown
key is refused before any directory is touched. Everything else — where a shelf
is, what is on it, how a thing goes back — is the domain's own answer, in
`adapters/`.

THE TYPED PHRASE IS GONE, and this is where it used to live. Emptying a shelf
demanded a sentence ("empty the databases trash"), checked here so that every
shelf was gated the same way and none could end up weaker than its neighbours.
Measured in use, the gate was pointed at the wrong question: the shelf's sentence
is the wrong thing to demand when what you are removing is ONE entry, and a
confirmation the person retypes from the dialog in front of them is a speed bump
rather than a guard. So the guard is now the ACT — an irreversible removal that
has to be asked for deliberately, in a dialog that names what goes — and nothing
here pretends to check anybody's intent.

THE SESSION IS PASSED, NOT HELD. Most shelves ignore it; the agents shelf cannot
say whether an entry is a trashed agent or residue without it. Handing it in per
call keeps the service stateless and keeps the database's owner in the caller.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Paths
from app.domain.trash.registry import get_domain, list_domains


def _relative(path: Path) -> str:
    """A path as a person reads it — relative to the installation root."""
    try:
        return str(Path(path).relative_to(Paths.root))
    except ValueError:
        return str(path)


class TrashService:
    """The trash's single entry point. Stateless: a session is handed to each
    call and nothing about it is remembered."""

    async def shelves(self, db: AsyncSession | None = None) -> list[dict[str, Any]]:
        """Every shelf with its count — the tabs, and the badges on them.

        A shelf whose directory does not exist yet reports ZERO rather than
        being absent: an installation starts without a trash, and a tab that
        vanishes is a tab that cannot tell you it is empty.
        """
        out: list[dict[str, Any]] = []
        for domain in list_domains():
            out.append({
                "key": domain.key,
                "label": domain.label,
                "count": len(await domain.entries(db)),
                "restorable": domain.restorable,
                "directory": _relative(domain.directory()),
            })
        return out

    async def listing(self, key: str, db: AsyncSession | None = None) -> dict[str, Any]:
        """One shelf, read out: the entries, and where it lives."""
        domain = get_domain(key)
        entries = await domain.entries(db)
        return {
            "key": domain.key,
            "label": domain.label,
            "restorable": domain.restorable,
            "directory": _relative(domain.directory()),
            "count": len(entries),
            "entries": [e.as_dict() for e in entries],
        }

    async def restore(self, key: str, name: str, db: AsyncSession | None = None) -> dict[str, Any]:
        """Put one entry back. The SHELF owns the refusal when it has no way
        back — it can say why in its own words."""
        return await get_domain(key).restore(name, db)

    async def purge(self, key: str, name: str, db: AsyncSession | None = None) -> bool:
        """Remove ONE entry permanently. False when there is no such entry, so
        the caller can answer 404 rather than claiming a destruction that did
        not happen."""
        return await get_domain(key).purge(name, db)

    async def empty(self, key: str, db: AsyncSession | None = None) -> dict[str, Any]:
        """Empty ONE shelf — every entry on it, permanently.

        No phrase and no policy: the decision was the caller's, and this layer
        carries it out. What is NOT dropped is the containment rule — nothing
        outside the trash is ever removed — which lives in `mechanics` and
        applies to every path that destroys anything.
        """
        domain = get_domain(key)
        return {"emptied": True, "domain": domain.key, "deleted": await domain.empty(db)}


def get_trash_service() -> TrashService:
    """The factory — one stateless instance, the same shape the other domains
    use so a fork can swap the implementation later."""
    return _SERVICE


_SERVICE = TrashService()
