"""The install's readiness — one read, one verdict (thin).

`GET /api/v1/setup/readiness` returns what the Dashboard card and the Setup checklist both
render, and what `./cogitate.sh verify` will quote. It is READ-ONLY: nothing here writes,
seeds, probes a model or activates anything. See `domain/providers/readiness.py` for the
measurement, and for why a BLOCKED item must not ask the user to act yet.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.providers import readiness
from app.infrastructure.database import get_db_session

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/readiness")
async def get_readiness(db: AsyncSession = Depends(get_db_session)) -> dict:
    """The verdict, plus the items behind it."""
    report = await readiness.measure(db)
    return report.to_dict()
