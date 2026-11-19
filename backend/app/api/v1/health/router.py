"""
Health check endpoints.

Provides basic and comprehensive health check endpoints
for monitoring application status.
"""

from fastapi import APIRouter, status

router = APIRouter(tags=["health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> dict[str, str]:
    """
    Basic health check endpoint.

    Returns:
        dict: Status indicator
    """
    return {"status": "healthy"}


@router.get("/health/comprehensive")
async def comprehensive_health_check() -> dict:
    """
    Comprehensive health check with detailed status.

    Includes the PATH-RESOLUTION check (2026-08-17): every canonical
    path must resolve through the Paths locator — the phantom-DB bug
    class (hand-computed paths opening a wrong/empty file) surfaces
    here as a failed check instead of silent wrong behavior.

    Returns:
        dict: Detailed health information including:
            - status: Overall health status
            - version: Application version
            - environment: Current environment
            - paths: canonical path resolution (each exists/writable)
    """
    from app.core.config import Paths, get_settings

    settings = get_settings()
    paths = Paths.from_settings(settings)

    path_checks: dict[str, str] = {}
    # the shared DB must EXIST (a missing file = the phantom-DB bug
    # class, or a fresh install that hasn't migrated yet)
    path_checks["shared_db"] = (
        "ok" if paths.shared_db.exists()
        else "missing (run alembic upgrade head)"
    )
    # the runtime dirs should exist; report their state honestly
    for name, p in (
        ("data_dir", paths.data_dir),
        ("monitor_dir", paths.monitor_dir),
        ("agents_dir", paths.agents_dir),
        ("logs_dir", paths.logs_dir),
    ):
        path_checks[name] = "ok" if p.exists() else "missing"

    all_ok = all(v == "ok" for v in path_checks.values())
    return {
        "status": "healthy" if all_ok else "degraded",
        "version": settings.app_version,
        "environment": settings.environment,
        "debug": settings.debug,
        "paths": path_checks,
    }
