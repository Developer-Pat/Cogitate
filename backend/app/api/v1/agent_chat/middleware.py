"""
External Access Toggle Middleware.

Checks the ``system_flags`` table on each request to the agent-chat API
and returns 403 when external access is disabled.

The flag is cached for the duration of the request to avoid repeated
database queries within a single request cycle.
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.infrastructure.database.models import SystemFlag

logger = logging.getLogger(__name__)

EXTERNAL_ACCESS_KEY = "external_access_enabled"

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


async def external_access_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """
    FastAPI middleware that checks the ``system_flags`` table for the
    ``external_access_enabled`` flag on every request to the agent-chat API.

    Returns ``403 Forbidden`` when the flag is ``"false"``, ``"0"``, or
    absent.  Requests with ``enabled=true`` pass through normally.
    """
    # Only intercept agent-chat routes
    if not request.url.path.startswith("/api/v1/agent-chat"):
        return await call_next(request)

    # Allow the status endpoints themselves (GET/PUT /status) so clients
    # can check and toggle the flag even when it's disabled.
    if request.url.path.rstrip("/").endswith("/status"):
        return await call_next(request)

    # Allow WebSocket bridge endpoints (ui-state, ui-navigate, ws) so
    # the frontend can always sync state and receive navigation commands.
    if request.url.path.rstrip("/").endswith("/ui-state"):
        return await call_next(request)
    if request.url.path.rstrip("/").endswith("/ui-navigate"):
        return await call_next(request)

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SystemFlag).where(SystemFlag.key == EXTERNAL_ACCESS_KEY)
            )
            flag: SystemFlag | None = result.scalar_one_or_none()

            if flag is None or flag.value.lower() in ("false", "0", ""):
                logger.warning(
                    "Blocked request to %s — external access is disabled",
                    request.url.path,
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "External access is disabled. "
                        "Use PUT /api/v1/agent-chat/status to enable it.",
                    },
                )
    except Exception:
        logger.exception(
            "Error checking external access flag — defaulting to disabled"
        )
        return JSONResponse(
            status_code=503,
            content={"detail": "Unable to verify access permissions."},
        )

    return await call_next(request)


# ---------------------------------------------------------------------------
# Lifespan helper — seed the default flag on startup
# ---------------------------------------------------------------------------


async def seed_external_access_flag() -> None:
    """
    Ensure the ``external_access_enabled`` flag exists in the
    ``system_flags`` table.  Called once during application startup.

    If the row is missing it is created with ``value="false"`` so that
    external access is **disabled by default** after a fresh migration.
    """
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SystemFlag).where(SystemFlag.key == EXTERNAL_ACCESS_KEY)
            )
            flag = result.scalar_one_or_none()

            if flag is None:
                db.add(SystemFlag(key=EXTERNAL_ACCESS_KEY, value="false"))
                await db.commit()
                logger.info(
                    "Seeded system_flag '%s' = false (default disabled)",
                    EXTERNAL_ACCESS_KEY,
                )
            else:
                logger.info(
                    "System flag '%s' already exists = '%s'",
                    EXTERNAL_ACCESS_KEY,
                    flag.value,
                )
    except Exception:
        logger.exception("Failed to seed external access flag")


# ---------------------------------------------------------------------------
# Wiring helper
# ---------------------------------------------------------------------------


def add_external_access_middleware(app: FastAPI) -> None:
    """Add the external access middleware to a FastAPI application."""
    app.middleware("http")(external_access_middleware)
    logger.info("External access toggle middleware registered")
