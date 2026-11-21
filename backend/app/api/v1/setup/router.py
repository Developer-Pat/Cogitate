"""The install's setup surface — readiness, and the express picks.

`GET /api/v1/setup/readiness` returns what the Dashboard card and the Setup checklist both
render, and what `./cogitate.sh verify` quotes. It is READ-ONLY: nothing here writes, seeds,
probes a model or activates anything. See `domain/providers/readiness.py` for the measurement,
and for why a BLOCKED item must not ask the user to act yet.

`GET /api/v1/setup/express` and `POST /api/v1/setup/express/{key}/apply` are the express picks:
a packaged list of models (the one strong choice a stranger should be asked to make) and the one
press that adopts one. Both are thin — the write lives in `domain/providers/express_setup.py`
and goes through the same chain path the CLI does, so the page and `setup_models.py` cannot drift.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.providers import express_setup, readiness
from app.infrastructure.database import get_db_session

router = APIRouter(prefix="/setup", tags=["setup"])


class ExpressApplyBody(BaseModel):
    """The key a stranger pastes in the same press — optional, because it may already be set."""

    api_key: str | None = None


@router.get("/readiness")
async def get_readiness(db: AsyncSession = Depends(get_db_session)) -> dict:
    """The verdict, plus the items behind it."""
    report = await readiness.measure(db)
    return report.to_dict()


@router.get("/express")
async def get_express_picks(db: AsyncSession = Depends(get_db_session)) -> dict:
    """The packaged picks, in order, with what each needs and whether this install has it."""
    picks = await express_setup.list_picks(db)
    return {
        "picks": picks,
        "ready": [p["key"] for p in picks if p["state"] == "ready"],
    }


@router.post("/express/{key}/apply")
async def apply_express_pick(
    key: str, body: "ExpressApplyBody | None" = None, db: AsyncSession = Depends(get_db_session)
) -> dict:
    """Adopt one pick: its provider row, every llm capability, the default, the agents.

    `api_key` is OPTIONAL and is the whole point of express setup: a stranger pastes the key in
    the same press, and `.env` (the one secrets store) takes it before the pick is applied — so
    "one model, one key" is literally one control, not a trip to another tab.
    """
    pick = await express_setup.active_pick_or_none(db, key)
    if pick is None:
        raise HTTPException(status_code=404, detail=f"no setup pick called {key!r}")
    if body and body.api_key and pick.needs_env:
        from app.domain.providers.env_key_store import env_key_store

        if not env_key_store.set_key(pick.provider_type, body.api_key.strip()):
            raise HTTPException(
                status_code=400,
                detail=f"could not store a key for {pick.provider_type}",
            )
    try:
        log = await express_setup.apply_pick(db, key)
    except ValueError as exc:
        # 400, not 500: a pick that does not apply here is an answer, not a fault.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # The verdict is re-read AFTER the write, so the caller sees what it produced rather than
    # guessing an optimistic one.
    report = await readiness.measure(db)
    return {"applied": key, "log": log, "readiness": report.to_dict()}
