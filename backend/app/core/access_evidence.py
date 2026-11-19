"""The access-evidence middleware (2026-08-20).

A lightweight request journal — the VERIFIED source for the
verify-http-evidence tool. uvicorn's access log goes to the
process stdout (process-bound, unrotated, lost on restart); this
middleware appends `method path status timestamp` to a ROTATING
file (backend/logs/access.log — 10MB x 3), decoupled from the
process lifecycle. The tool reads THIS file; the industrial fork's
systemd/Docker deployment gets the same evidence.

Deliberately minimal: no bodies, no headers, no client ids —
just the evidence that a request happened (the claim-verification
use case). The query string is preserved for tool-path matching.
"""
import logging
from datetime import datetime, timezone
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)

# THE DESTRUCTIVE-EVIDENCE LINE (2026-09-11). The journal above is
# deliberately minimal — it proves a request HAPPENED (the
# claim-verification case) and says nothing about what the request
# destroyed. That is the wrong shape for a destructive operation: a
# bulk delete left `POST /api/v1/sessions/bulk-delete 200`, which
# answers "did it happen" and not "what went" — and the ids live only
# in app.log, which rotates independently of this file.
#
# So the destructive ENDPOINTS write their own line here, at the moment
# they hold the ids. The middleware stays minimal (no body reading, no
# per-request cost); only the operations that destroy something pay.
DESTRUCTIVE_MARKER = "DESTRUCTIVE"

# A clear-all can name thousands of ids. Cap the list and SAY SO —
# a silently truncated evidence line is worse than no line.
_MAX_LISTED_IDS = 50

# Set when the middleware is registered; falls back to Paths for
# callers that run before/without it (tests, scripts).
_ACCESS_FILE: Path | None = None


def format_ids(ids) -> str:
    """Compact an id list for the journal, truncation made explicit."""
    listed = [str(i) for i in ids]
    if len(listed) <= _MAX_LISTED_IDS:
        return f"[{', '.join(listed)}]"
    shown = ", ".join(listed[:_MAX_LISTED_IDS])
    return f"[{shown}, ... +{len(listed) - _MAX_LISTED_IDS} more]"


def record_destructive_evidence(path: str, detail: str) -> None:
    """Append a DESTRUCTIVE line naming what a request destroyed.

    Called by the destructive endpoints themselves — they are the only
    place the ids are known without reading a request body.

    Args:
        path: The endpoint's path (pass ``request.url.path`` so it
            cannot drift from the route).
        detail: What was destroyed, e.g. ``"deleted=8 ids=[27, 26]"``.

    Never raises: the journal must not be able to fail a delete that
    otherwise succeeded (the same doctrine as the middleware).
    """
    try:
        journal = _ACCESS_FILE
        if journal is None:
            from app.core.config import Paths

            journal = Path(Paths.access_log)
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        journal.parent.mkdir(parents=True, exist_ok=True)
        with open(journal, "a", encoding="utf-8") as f:
            f.write(f"{ts} | {DESTRUCTIVE_MARKER} {path} | {detail}\n")
    except Exception as e:  # never let evidence break the operation
        logger.warning(f"destructive-evidence write failed: {e}")


class AccessEvidenceMiddleware(BaseHTTPMiddleware):
    """Record `method path status` per request to the access file."""

    def __init__(self, app, access_file: Path):
        super().__init__(app)
        self.access_file = Path(access_file)

    async def dispatch(self, request: Request, call_next):
        method = request.method
        path = request.url.path
        query = request.url.query
        full = f"{path}?{query}" if query else path
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            status = 500
            raise
        try:
            ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self.access_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.access_file, "a", encoding="utf-8") as f:
                f.write(f"{ts} | {method} {full} {status}\n")
        except Exception as e:  # the journal must never break a request
            logger.warning(f"access-evidence write failed: {e}")
        return response


def add_access_evidence_middleware(app, access_file: Path) -> None:
    """Register the journal (called from app.main after the routers)."""
    global _ACCESS_FILE
    _ACCESS_FILE = Path(access_file)
    app.add_middleware(AccessEvidenceMiddleware, access_file=access_file)


def rotate_access_file(access_file: Path, max_bytes: int = 10 * 1024 * 1024,
                       backups: int = 3) -> None:
    """Rotate the access file when it exceeds max_bytes (called on
    startup — the file is append-only otherwise)."""
    p = Path(access_file)
    if not p.exists():
        return
    if p.stat().st_size < max_bytes:
        return
    for i in range(backups, 0, -1):
        older = Path(f"{p}.{i}")
        if older.exists():
            older.unlink()
    if Path(f"{p}.1").exists():
        Path(f"{p}.1").replace(Path(f"{p}.2"))
    p.replace(Path(f"{p}.1"))
