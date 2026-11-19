"""The CHAT CHAIN — the resolver's answer, threaded where the executor can read it.

Both chat paths build an ``AgentDescriptor`` and hand it to a pipeline, and neither used to ask the
resolver anything: the executor's failover walked a hardcoded list of providers. The chain is the
resolver's answer (R3), and it is resolved HERE because the resolution needs a database session —
which the executor does not have (it logs usage over a raw sqlite3 connection precisely because
*"no ORM session here"*). This is the same seam `output_budget` uses: resolve where the session is,
carry the answer, and let the executor's own default speak when there is no answer.

The chain's ORDER is the resolver's (`capabilities.resolve`: the agent's declaration as the lead
candidate, its `preferred_providers` as the backups) — this module only moves it.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from .models import AgentDescriptor

logger = logging.getLogger(__name__)


async def attach(descriptor: AgentDescriptor, db: Optional[AsyncSession], *, path: str) -> AgentDescriptor:
    """Put the `chat` capability's resolved chain on ``descriptor`` and return it.

    A resolution that cannot read (no session, an unreadable driver) leaves ``candidates`` empty —
    the executor's own single attempt speaks, exactly as before this existed — and the reason is
    logged rather than swallowed. A turn never dies on a missing reading.

    Args:
        descriptor: the agent's declaration, already built (its provider/model are the effective
            pair for this turn — an override or a runtime config may have moved them).
        db: the session to resolve with; None leaves the descriptor untouched.
        path: the calling path's label, for the log line (`agent_chat`, `chat`).
    """
    if db is None:
        return descriptor
    try:
        from app.domain.providers.capabilities import (
            CHAT_CAPABILITY_KEY,
            describe_chain,
            resolve,
        )

        resolved = await resolve(db, CHAT_CAPABILITY_KEY, agent=descriptor)
        descriptor.candidates = resolved.candidates
        # WHICH RUNG ANSWERED — carried so the consumer can act on `disabled` (a capability
        # switched off must be REFUSED, not walked) without re-resolving the ladder (G5-F3).
        descriptor.chain_reason = resolved.reason
        logger.info(
            "%s: chain resolved (reason=%s): %s",
            path,
            resolved.reason,
            describe_chain(resolved),
        )
    except Exception as exc:  # noqa: BLE001 — a missing reading must not fail the turn
        logger.warning(
            "%s: no chain for agent %s (%s) — the executor's own attempt speaks",
            path,
            getattr(descriptor, "id", "?"),
            exc,
        )
    return descriptor
