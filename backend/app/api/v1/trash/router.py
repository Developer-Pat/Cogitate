"""THE TRASH API — one surface over every shelf.

The trash is a DOMAIN (`app/domain/trash/`): five shelves behind ONE verb set,
registered in ONE map. This router is the map's second reader — the page is the
first and Exa the third — and it exists so that neither has to know a shelf's
name in advance. The shelves come from the REGISTRY, which is what makes a sixth
shelf a file plus a registration rather than an endpoint plus a page edit.

FIVE ROUTES, and they are the domain's own verbs, one shelf at a time:

    GET  /trash                          the shelves, with the counts on their tabs
    GET  /trash/{shelf}                  one shelf: the entries and where it lives
    POST /trash/{shelf}/restore/{name}   put one entry back where it came from
    POST /trash/{shelf}/purge/{name}     remove one entry for good
    POST /trash/{shelf}/empty            remove every entry on the shelf

WHY THE SHELF IS IN THE ADDRESS. Removing things is scoped to one shelf for the
same reason the page's verbs are: one call over a root that holds database backups
beside report folders would take more than the caller was looking at. There is
deliberately NO global empty, and no verb here prunes on a schedule.

WHAT THE STATUS CODES MEAN, because the page and Exa both read them:

- **404** — an unknown SHELF (a misspelling the registry refuses before any
  directory is touched), or a shelf that exists and does not hold that ENTRY.
- **400** — the shelf is real and the request is refused BY IT: restoring from
  the reports shelf (nothing records where its entries came from), or purging a
  SHELF through the misc bucket.

WHY RESTORE IS CHECKED AND PURGE IS NOT. An entry that is not on the shelf is a
404 in both cases, but only restore needs the shelf to be CONSULTED first: three
shelves answer "not there" and "I cannot do that" with the same ValueError, so
the listing is what tells them apart. Purge already answers with a boolean, and
the one refusal it can raise — the misc bucket declining to take a SHELF — is a
sentence worth hearing, so the shelf is asked FIRST and the 404 only follows a
plain `False`.

WHO GUARDS THE IRREVERSIBLE ACT. Nothing here, and that is deliberate rather than
an omission. `purge` and `empty` are asked for by a caller that has already
decided; this surface does not demand a phrase or a second password, because a
confirmation is a conversation between a person and the surface they are using
and a check the server makes ON THE CLIENT'S BEHALF is only ever as strong as the
client. What is enforced is factual and structural, and it is the part that
matters: the shelf must exist, the entry must be there, and nothing outside the
trash is ever removed (the containment rule, which every destroying path in the
domain goes through).
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.domain.trash.registry import get_domain
from app.domain.trash.services import get_trash_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trash", tags=["trash"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


class DestructiveRequest(BaseModel):
    """The caller's explicit statement that this removal is INTENDED.

    **Not a gate** — any caller can send `true` — and it is not meant to be one.
    It is the difference between "a POST happened to reach this route" and "a
    caller decided to destroy something", which is what makes the awkward shapes
    FAIL instead of delete: a stray `curl` with no body, a retry whose body was
    dropped, a script whose default happened to be "empty everything".

    Restore carries no such flag. It is additive and recoverable, and a
    confirmation on the way BACK would be a checkpoint with nothing behind it.
    """

    confirm: bool = False


def _announce(shelf: str, event: str, name: str | None = None) -> None:
    """THE CROSS-WINDOW SYNC: one tab's removal leaves no other tab stale.

    A purge in one window must not leave another showing a row that is gone —
    the house rule for a mutating router (the sessions, agents and collections
    routers all announce for the same reason). The topic is
    `trash:<shelf>:<event>` and the payload carries `id` (the shelf) and `event`;
    the frontend's `useDomainSync('trash')` hears it and calls the page's reload.

    The event kind rides IN THE PAYLOAD because the bus delivers only the payload
    to a handler — a `trash:*` subscriber receiving restored/purged/emptied could
    not tell them apart otherwise.
    """
    try:
        from app.domain.messaging.services import publish

        payload: dict[str, Any] = {"id": shelf, "event": event}
        if name is not None:
            payload["name"] = name
        publish(f"trash:{shelf}:{event}", payload)
    except Exception as e:  # pragma: no cover
        logger.error("trash:%s:%s publish failed: %s", shelf, event, e)


def _require_intent(
    shelf: str, doing: str, body: "DestructiveRequest | None",
) -> None:
    """400 unless the caller said so out loud — the shelf's verb is permanent.

    `body` may be None: a POST with NO body at all is refused here rather than by
    the request validator, so every way of *not* saying it lands on the same 400
    with the same sentence. The default shape (FastAPI's 422 `body: Field
    required`) is a standard error about a malformed request, which is not what
    this is — the request is well-formed and the CALLER has not decided.
    """
    if body is None or not body.confirm:
        raise HTTPException(
            status_code=400,
            detail=(
                f"refusing to {doing} on the {shelf} shelf without "
                f"confirm: true — this cannot be undone"
            ),
        )


def _shelf(key: str) -> Any:
    """The shelf registered under `key`, or 404 naming the ones that exist.

    Resolved before any verb runs, so every route answers a misspelling the same
    way — and so a later ValueError from a shelf is unambiguously that shelf's
    own refusal rather than the registry's.
    """
    try:
        return get_domain(key)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


async def _entry_on(shelf: str, name: str, db: AsyncSession | None) -> None:
    """404 unless `name` is on `shelf` right now.

    Read at THIS moment rather than trusted from the page's last listing, so a
    row the page is holding after someone else emptied the shelf is refused
    honestly instead of acting on a name that is no longer there.
    """
    listing = await get_trash_service().listing(shelf, db)
    if not any(entry["name"] == name for entry in listing["entries"]):
        raise HTTPException(
            status_code=404,
            detail=f"nothing named {name!r} is on the {shelf} shelf",
        )


@router.get("")
async def get_shelves(db: DbSession) -> dict[str, Any]:
    """Every shelf with its count — **the page's tabs, rendered from here.**

    A shelf whose directory does not exist yet reports ZERO rather than being
    absent: an installation starts without a trash, and a tab that vanishes is a
    tab that cannot tell you it is empty.

    The count is the shelf's real one, read at this moment — never a number the
    page keeps in step by hand.
    """
    return {"shelves": await get_trash_service().shelves(db)}


@router.get("/{shelf}")
async def get_shelf(shelf: str, db: DbSession) -> dict[str, Any]:
    """ONE shelf, read out: what is on it and what each entry IS.

    Every entry says whether a RECORD backs it (`restorable`) and, where one does
    not, what it is instead (`note`) — the difference between a trashed agent and
    residue is the difference between a button that works and one that cannot,
    and the shelf states it rather than the page guessing.
    """
    _shelf(shelf)
    return await get_trash_service().listing(shelf, db)


@router.post("/{shelf}/restore/{name}")
async def restore_entry(shelf: str, name: str, db: DbSession) -> dict[str, Any]:
    """Put ONE entry back where it came from — the way off the shelf.

    The shelf owns the report (an agent comes back with its id and workspace key;
    a run says where it landed, and `renamed` when its name had been taken
    since). A shelf with no way back — reports, dbs, misc — refuses in its own
    words, which arrive as a 400 rather than a silent no-op.
    """
    _shelf(shelf)
    await _entry_on(shelf, name, db)
    try:
        result = await get_trash_service().restore(shelf, name, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("trash: restored %s from the %s shelf", name, shelf)
    _announce(shelf, "restored", name)
    return {"restored": True, **result}


@router.post("/{shelf}/purge/{name}")
async def purge_entry(
    shelf: str, name: str, db: DbSession, body: DestructiveRequest | None = None,
) -> dict[str, Any]:
    """Remove ONE entry **permanently** — the irreversible half, one thing wide.

    The caller must say so (`confirm: true`): see `DestructiveRequest` for what
    that is and is not. The shelf then answers first, because it has more to say
    than yes or no — the misc bucket refuses a SHELF by name in its own words (a
    400), and a plain `False` means nothing by that name is there (a 404), so a
    purge that removed nothing cannot read as a purge that worked. The
    containment rule (nothing outside the trash is ever removed) lives in the
    domain's mechanics; this route does not restate it, and does not weaken it.
    """
    _shelf(shelf)
    _require_intent(shelf, f"purge {name!r}", body)
    try:
        purged = await get_trash_service().purge(shelf, name, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not purged:
        raise HTTPException(
            status_code=404,
            detail=f"nothing named {name!r} is on the {shelf} shelf",
        )
    logger.info("trash: purged %s from the %s shelf", name, shelf)
    _announce(shelf, "purged", name)
    return {"purged": True, "shelf": shelf, "name": name}


@router.post("/{shelf}/empty")
async def empty_shelf(
    shelf: str, db: DbSession, body: DestructiveRequest | None = None,
) -> dict[str, Any]:
    """Remove **every** entry on ONE shelf, permanently.

    The caller must say so (`confirm: true`) — a bare POST cannot empty a shelf
    by accident, and the accidental shapes are the ones worth stopping (a stray
    curl, a lost body, a script defaulting to everything). No phrase, though:
    the check that used to ask the caller to retype a sentence only ever made
    them repeat themselves. The shelf is still resolved first, so a misspelled
    key empties nothing.

    `deleted` is a count of what actually went, not a claim — the page reports
    the number it is given.
    """
    _shelf(shelf)
    _require_intent(shelf, "empty", body)
    result = await get_trash_service().empty(shelf, db)
    logger.info("trash: emptied the %s shelf (%d gone)", shelf, result["deleted"])
    _announce(shelf, "emptied")
    return result
