"""The LOCAL occupancy endpoint (A3, the read side — 2026-09-09).

GET /api/v1/providers/local/occupancy — the local-page occupancy:
per-daemon state (healthy / down-by-occupancy / down) + the loaded
models + the running set. The daemon class = the same seam the A1
split uses (the cloud whitelist + the loopback tiebreaker).
"""

import logging
from typing import Annotated, Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.domain.providers.config_service import ProviderConfigService
from app.domain.providers.local_occupancy_service import get_local_occupancy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("/local/occupancy")
async def read_local_occupancy(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Dict[str, Any]:
    """The local-daemon occupancy: states + the loaded models.

    Read-only and fast (the probes are short-timeout). The local
    page renders the state classes distinctly: an occupancy-down is
    a swap-away (informational), never alert noise.
    """
    service = ProviderConfigService()
    providers = await service.list_providers(db, include_inactive=False)
    local = [
        p for p in providers
        if getattr(p, "location", None) == "local"
    ]
    result = await get_local_occupancy([vars(p) for p in local])
    logger.info("Local occupancy read: running=%s", result.get("running"))
    return result
