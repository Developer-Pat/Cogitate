"""
Logs API endpoints.

Provides access to application logs.
"""

import csv
import io
import json
import logging
from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import BASE_DIR
from app.core.database import get_db_session
from pathlib import Path

from app.domain.logs.schemas import (
    FrontendLogEntry,
    LogEntryResponse,
    LogStatsResponse,
    PaginatedLogsResponse,
)
from app.domain.logs.services import LogService
from app.infrastructure.database.models import Log

logger = logging.getLogger(__name__)


def _announce(event: str, payload: dict) -> None:
    """THE CROSS-WINDOW SYNC (2026-08-25, the roadmap Phase 7):
    log:<id>:<event> — the frontend's sync reloads the open pages."""
    try:
        from app.domain.messaging.services import publish
        publish(f"log:{payload.get('log_id')}:{event}", payload)
    except Exception as e:  # pragma: no cover
        logger.error(f"  ❌ log:{event} publish failed: {e}")

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("", response_model=PaginatedLogsResponse)
async def get_logs(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    level: Annotated[Optional[str], Query()] = None,
    source: Annotated[Optional[str], Query()] = None,
    from_time: Annotated[Optional[str], Query(alias="from")] = None,
    to_time: Annotated[Optional[str], Query(alias="to")] = None,
    search: Annotated[Optional[str], Query()] = None,
    session_id: Annotated[Optional[str], Query()] = None,
):
    """
    Get application logs with filtering and pagination.

    Args:
        page: Page number
        page_size: Items per page
        level: Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        source: Filter by source (frontend, backend, or specific module)
        from: Start time filter (ISO 8601 format)
        to: End time filter (ISO 8601 format)
        search: Full-text search in message
        session_id: Filter by session ID

    Returns:
        dict: Paginated logs including:
            - items: List of log entries
            - total: Total number of log entries
            - page: Current page
            - page_size: Items per page
            - has_more: Whether there are more pages
    """
    try:
        log_service = LogService(db)
        
        # Get logs with filters
        logs, total = await log_service.get_logs(
            skip=(page - 1) * page_size,
            limit=page_size,
            level=level,
            source=source,
            from_time=from_time,
            to_time=to_time,
            search=search,
            session_id=session_id
        )
        
        # Convert to response format
        items = [
            LogEntryResponse(
                id=log.id,
                timestamp=log.timestamp,
                level=log.level,
                source=log.source,
                message=log.message,
                context=log.context,
                user_agent=log.user_agent,
                url=log.url,
                session_id=log.session_id,
                trace_id=log.trace_id,
                created_at=log.created_at
            )
            for log in logs
        ]
        
        return PaginatedLogsResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=(page - 1) * page_size + page_size < total
        )
    except Exception as e:
        logger.error(f"Failed to get logs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve logs: {str(e)}")


@router.get("/stats", response_model=LogStatsResponse)
async def get_logs_stats(
    db: Annotated[AsyncSession, Depends(get_db_session)]
):
    """
    Get log statistics.

    Returns:
        dict: Log statistics including:
            - total: Total number of log entries
            - by_level: Count by log level
            - by_source: Count by source
            - recent_activity: Recent log activity
            - frontend_logs: Count of frontend logs
            - backend_logs: Count of backend logs
    """
    try:
        log_service = LogService(db)
        stats = await log_service.get_stats()
        return LogStatsResponse(**stats)
    except Exception as e:
        logger.error(f"Failed to get log stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve log statistics: {str(e)}")


@router.post("/frontend", status_code=201)
async def create_frontend_log(
    entry: FrontendLogEntry
):
    """
    Create a new frontend log entry.

    Writes to FILE ONLY (no database). Fast and lightweight.

    Args:
        entry: Frontend log entry data

    Returns:
        dict: Created log entry status
    """
    logger.debug(f"Received frontend log request: {entry.source} - {entry.message}")

    try:
        from pathlib import Path
        log_file = Path("logs/frontend.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Opening log file: {log_file.absolute()}")

        # Handle timestamp (might be string or datetime)
        timestamp_str = entry.timestamp
        if isinstance(timestamp_str, str):
            # Clean up ISO format for readability
            timestamp_str = timestamp_str.replace('T', ' ').replace('Z', '').split('.')[0]

        context_str = ""
        if entry.context:
            import json as json_module
            context_str = f" | {json_module.dumps(entry.context, default=str)}"

        log_line = f"{timestamp_str} | {entry.level:8s} | {entry.source:30s} | {entry.message}{context_str}\n"
        logger.debug(f"Writing log line: {log_line[:50]}...")

        with open(log_file, "a") as f:
            f.write(log_line)

        logger.debug(f"Successfully wrote log to file: {log_file}")

        return {
            "status": "created",
            "logged_to": "file",
            "file": str(log_file.absolute())
        }
    except Exception as e:
        logger.error(f"Failed to write log to file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to write log to file: {str(e)}")


@router.get("/files")
async def list_log_files() -> dict:
    """Every log the system writes, with its size — THE MONITOR.

    2026-09-12. The log page showed a healthy ~30 MB while a 162 MB capture grew
    behind it, because nothing surfaced the captures at all: the UI reads the
    managed frontend.log/app.log, and the files that actually break things were
    neither rotated nor visible. This names every file, its size, and whether it
    is managed or an unmanaged capture — so the next flood is visible where
    someone looks, instead of felt as a slow chat.
    """

    cap_bytes = 10 * 1024 * 1024  # matches the launcher's LOG_CAP_MB
    managed_names = {"frontend.log", "app.log"}

    files = []
    for path, label in _log_file_registry():
        exists = path.exists()
        try:
            size = path.stat().st_size if exists else 0
        except OSError:
            size = 0
        files.append({
            "source": label,
            "file": path.name,
            "exists": exists,
            "size_bytes": size,
            "size_mb": round(size / 1048576, 2),
            "managed": path.name in managed_names,
            "over_cap": size >= cap_bytes,
            # a rotated generation, if the cap has fired
            "rotated": (path.parent / (path.name + ".1.gz")).exists(),
        })

    return {
        "files": files,
        "cap_mb": cap_bytes // 1048576,
        "warnings": [f["source"] for f in files if f["over_cap"]],
    }


@router.post("/file", status_code=200)
async def log_to_file_only(
    entry: FrontendLogEntry
):
    """
    Write log to FILE ONLY (no database).
    
    Use this endpoint when database is locked or for high-volume logging.
    
    Args:
        entry: Frontend log entry data
        
    Returns:
        dict: Success status
    """
    try:
        from pathlib import Path
        log_file = Path("logs/frontend.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Handle timestamp
        timestamp_str = entry.timestamp
        if isinstance(timestamp_str, str):
            timestamp_str = timestamp_str.replace('T', ' ').replace('Z', '').split('.')[0]
        
        context_str = ""
        if entry.context:
            import json as json_module
            context_str = f" | {json_module.dumps(entry.context, default=str)}"
        
        log_line = f"{timestamp_str} | {entry.level:8s} | {entry.source:30s} | {entry.message}{context_str}\n"
        
        with open(log_file, "a") as f:
            f.write(log_line)
        
        return {
            "success": True,
            "logged_to": "file",
            "file": str(log_file.absolute())
        }
    except Exception as e:
        logger.error(f"Failed to write log to file: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/frontend/batch", status_code=201)
async def create_frontend_logs_batch(
    entries: list[FrontendLogEntry]
):
    """
    Create multiple frontend log entries in a batch.

    Writes to FILE ONLY (no database). Fast and lightweight.

    Args:
        entries: List of frontend log entries

    Returns:
        dict: Number of logs created
    """
    from pathlib import Path
    
    log_file = Path("logs/frontend.log")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    written_count = 0
    errors = []
    
    for i, entry in enumerate(entries):
        try:
            # Handle timestamp
            timestamp_str = entry.timestamp
            if isinstance(timestamp_str, str):
                timestamp_str = timestamp_str.replace('T', ' ').replace('Z', '').split('.')[0]

            context_str = ""
            if entry.context:
                import json as json_module
                context_str = f" | {json_module.dumps(entry.context, default=str)}"

            log_line = f"{timestamp_str} | {entry.level:8s} | {entry.source:30s} | {entry.message}{context_str}\n"

            with open(log_file, "a") as f:
                f.write(log_line)

            written_count += 1
        except Exception as e:
            logger.error(f"Failed to write log entry {i} to file: {e}")
            errors.append({"index": i, "error": str(e)})

    return {
        "count": written_count,
        "total": len(entries),
        "status": "created",
        "logged_to": "file",
        "errors": errors if errors else None
    }


# ---------------------------------------------------------------------------
# THE UNMANAGED CAPTURES (2026-09-12, the monitor).
#
# `console.log` and `logs/vite.log` are raw redirect captures — the launcher
# writes them, nothing rotates them by default, and the log API could not see
# them. That blindness is what let the 2026-09-11 flood run to 162 MB while
# this page reported a healthy 30 MB: the UI was reading the managed files only.
#
# TWO RULES for reading them:
#   1. TAIL ONLY. console.log is unbounded by design; readlines() on a 162 MB
#      file would blow the request up — the endpoint meant to diagnose the
#      flood would become a denial of service against the chat stream.
#   2. Name the source plainly, so a reader knows which capture they are in.
# ---------------------------------------------------------------------------
CAPTURE_READ_BYTES = 2 * 1024 * 1024  # 2 MB tail per file — plenty for diagnosis


def _tail_lines(path: "Path", max_bytes: int = CAPTURE_READ_BYTES) -> list:
    """Read the END of a log file without loading it whole.

    Seeks to (size - max_bytes), drops the partial first line, and decodes
    defensively — a log can contain a truncated multi-byte character.
    """
    try:
        size = path.stat().st_size
        if size == 0:
            return []
        with open(path, "rb") as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
                f.readline()  # discard the partial line the seek landed in
            return f.read().decode("utf-8", errors="replace").splitlines()
    except Exception:
        return []


def _log_file_registry() -> list:
    """Every log the system writes: (path, source label).

    Uses the Paths resolver rather than literals or parent-walks (the
    ONE-resolver doctrine). The captures live in two directories on purpose:
    the backend's own logs under backend/logs, and the launcher's frontend
    capture at the project root.
    """
    from app.core.config import Paths

    return [
        (Paths.logs_dir / "frontend.log", "frontend"),
        (Paths.logs_dir / "app.log", "backend"),
        (Paths.logs_dir / "console.log", "console"),   # the backend's stdout capture
        (Paths.root / "logs" / "vite.log", "vite"),  # the vite supervisor's capture
        # NOTE: two directories on purpose — the backend's own logs live in
        # backend/logs (Paths.logs_dir); the LAUNCHER's frontend capture lives
        # at the project root (Paths.root / "logs"). Using the resolver's `root`
        # rather than a parent-walk is the 2026-08-17 doctrine; I had first
        # written Paths.Base_DIR, which does not exist — the same class of
        # path-arithmetic bug the resolver was built to end.
    ]


@router.get("/file/recent")
async def get_recent_file_logs(
    n: Annotated[int, Query(ge=1, le=1000, description="Number of recent logs to retrieve")] = 100,
    level: Annotated[Optional[str], Query(description="Filter by log level")] = None,
    source: Annotated[Optional[str], Query(description="Filter by source")] = None,
    search: Annotated[Optional[str], Query(description="Full-text search in message")] = None,
    from_time: Annotated[Optional[str], Query(alias="from", description="Start time (ISO 8601)")] = None,
    to_time: Annotated[Optional[str], Query(alias="to", description="End time (ISO 8601)")] = None,
    log_type: Annotated[Optional[str], Query(description="Filter by log type (frontend/backend)")] = None,
):
    """
    Get recent logs from both frontend.log and app.log files with advanced filtering.

    Parses the log files and returns entries as JSON. Does not query the database.

    Args:
        n: Number of recent logs to retrieve (1-1000, default: 100)
        level: Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        source: Filter by source (case-insensitive partial match)
        search: Full-text search in message (case-insensitive)
        from: Start time filter (ISO 8601 format, e.g., 2026-03-20T10:00:00)
        to: End time filter (ISO 8601 format)
        log_type: Filter by log type (frontend or backend)

    Returns:
        list: List of log entries, newest first

    Examples:
        curl http://localhost:8000/api/v1/logs/file/recent?n=50

        curl "http://localhost:8000/api/v1/logs/file/recent?n=20&level=ERROR"

        curl "http://localhost:8000/api/v1/logs/file/recent?search=cache&level=info"

        curl "http://localhost:8000/api/v1/logs/file/recent?log_type=backend&n=50"
    """
    from datetime import datetime

    # Read every log file the system writes, TAIL-ONLY (see the note above).
    # Before 2026-09-12 this listed two files and used readlines() on each —
    # so the two captures that actually break things were invisible, and any
    # one of them growing without bound would have taken this endpoint down.
    log_files = _log_file_registry()

    all_lines = []
    for log_file, file_type in log_files:
        for line in _tail_lines(log_file):
            # Tag each line with its source file type
            all_lines.append((line + "\n", file_type))

    if not all_lines:
        return {
            "items": [],
            "total": 0,
            "note": "No log files exist yet"
        }

    try:
        # Parse log entries
        # Format: YYYY-MM-DD HH:MM:SS | LEVEL     | source                         | message | context
        parsed_logs = []

        # Parse time filters
        from_dt = None
        to_dt = None
        if from_time:
            try:
                from_dt = datetime.fromisoformat(from_time.replace('Z', '+00:00'))
            except ValueError:
                pass
        if to_time:
            try:
                to_dt = datetime.fromisoformat(to_time.replace('Z', '+00:00'))
            except ValueError:
                pass

        # Process lines in reverse order (newest first)
        for line, file_type in reversed(all_lines):
            line = line.strip()
            if not line:
                continue

            parts = line.split(" | ", 4)
            if len(parts) < 4:
                continue
            timestamp = parts[0] if len(parts) > 0 else ""
            log_level = parts[1].strip() if len(parts) > 1 else ""
            source_val = parts[2].strip() if len(parts) > 2 else ""
            message = parts[3] if len(parts) > 3 else ""
            context_str = parts[4] if len(parts) > 4 else ""

            # Apply level filter
            if level and log_level.upper() != level.upper():
                continue

            # Apply source filter (case-insensitive partial match)
            if source and source.lower() not in source_val.lower():
                continue

            # Apply log_type filter
            if log_type and log_type != file_type:
                continue

            # Apply search filter (case-insensitive, searches message and context)
            if search:
                search_lower = search.lower()
                if search_lower not in message.lower():
                    # Also search in context if present
                    if context_str and search_lower not in context_str.lower():
                        continue

            # Apply time filters
            if from_dt or to_dt:
                try:
                    log_dt = datetime.strptime(timestamp.split('.')[0], "%Y-%m-%d %H:%M:%S")
                    if from_dt and log_dt < from_dt:
                        continue
                    if to_dt and log_dt > to_dt:
                        continue
                except (ValueError, IndexError):
                    # If we can't parse the timestamp, skip time filtering
                    pass
            
            # Parse context if present
            context = {}
            if context_str:
                try:
                    import json as json_module
                    context = json_module.loads(context_str)
                except (json_module.JSONDecodeError, Exception):
                    context = {"raw": context_str}

            parsed_logs.append({
                "timestamp": timestamp,
                "level": log_level,
                "source": source_val,
                "message": message,
                "context": context,
                "log_type": file_type,  # Use the file type directly
                "user_agent": context.get('userAgent') or context.get('user_agent')
            })

        # THE TRUE MERGE (2026-09-06 fix): both files were read but the old
        # loop broke as soon as ONE file (app.log — appended last, reversed
        # first) filled n — frontend.log entries NEVER appeared in the
        # unfiltered 'all' view. Parse both fully, sort by timestamp desc
        # (the pipe format's timestamps are string-sortable), THEN take n.
        parsed_logs.sort(key=lambda e: e["timestamp"], reverse=True)
        parsed_logs = parsed_logs[:n]

        return {
            "items": parsed_logs,
            "total": len(parsed_logs),
            "filters": {
                "level": level,
                "source": source,
                "limit": n
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to read log file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read log file: {str(e)}")


@router.post("/rotate")
async def rotate_logs(
    compress: Annotated[bool, Query(description="Compress archived logs")] = True,
    keep_days: Annotated[int, Query(ge=1, description="Days to retain archives")] = 7,
    dry_run: Annotated[bool, Query(description="Show what would be done")] = False,
):
    """
    Manually trigger log rotation.

    Rotates log files by archiving current logs with timestamps, optionally compressing them,
    and creating fresh empty log files.

    Args:
        compress: Whether to compress archived logs with gzip (default: True)
        keep_days: Number of days to retain archived logs (default: 7)
        dry_run: If True, only show what would be done without making changes

    Returns:
        dict: Rotation results including archived files and cleanup status

    Example:
        curl -X POST http://localhost:8000/api/v1/logs/rotate

        curl -X POST "http://localhost:8000/api/v1/logs/rotate?compress=true&keep_days=14"

        curl -X POST "http://localhost:8000/api/v1/logs/rotate?dry_run=true"
    """
    import gzip
    import shutil
    from datetime import datetime, timedelta
    from pathlib import Path

    # Get logs directory (relative to backend/)
    # router.py is at: backend/app/api/v1/logs/router.py
    # Need to go up 4 levels to reach backend/
    script_dir = Path(__file__).parent
    backend_dir = script_dir.parent.parent.parent.parent  # Go up 4 levels to backend/
    logs_dir = backend_dir / "logs"
    
    if not logs_dir.exists():
        raise HTTPException(status_code=400, detail="Logs directory does not exist")
    
    log_files = ["frontend.log", "app.log"]
    results: dict[str, Any] = {
        "rotated": [],
        "archived": [],
        "deleted_archives": [],
        "dry_run": dry_run,
        "settings": {
            "compress": compress,
            "keep_days": keep_days
        }
    }
    
    cutoff = datetime.now() - timedelta(days=keep_days)
    
    for log_file_name in log_files:
        log_path = logs_dir / log_file_name
        
        if not log_path.exists():
            continue
        
        # Skip empty files
        if log_path.stat().st_size == 0:
            continue
        
        file_size_mb = log_path.stat().st_size / 1024 / 1024
        
        if dry_run:
            results["rotated"].append({
                "file": log_file_name,
                "size_mb": round(file_size_mb, 2),
                "action": "would_rotate"
            })
            continue
        
        # Create archive name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"{log_file_name}.{timestamp}"
        archive_path = logs_dir / archive_name
        
        try:
            # Move current log to archive
            shutil.move(str(log_path), str(archive_path))
            
            # Compress if requested
            if compress:
                compressed_path = archive_path.with_suffix(archive_path.suffix + ".gz")
                with open(archive_path, "rb") as f_in:
                    with gzip.open(compressed_path, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                archive_path.unlink()  # Remove uncompressed archive
                archive_path = compressed_path
                compressed_size_mb = archive_path.stat().st_size / 1024 / 1024
                compression_ratio = round((1 - compressed_size_mb / file_size_mb) * 100, 1) if file_size_mb > 0 else 0
                
                results["archived"].append({
                    "original": log_file_name,
                    "archive": archive_path.name,
                    "original_size_mb": round(file_size_mb, 2),
                    "compressed_size_mb": round(compressed_size_mb, 2),
                    "compression_ratio_percent": compression_ratio
                })
            else:
                results["archived"].append({
                    "original": log_file_name,
                    "archive": archive_path.name,
                    "size_mb": round(file_size_mb, 2)
                })
            
            # Create new empty log file
            log_path.touch()
            
        except Exception as e:
            logger.error(f"Failed to rotate {log_file_name}: {e}")
            results["rotated"].append({
                "file": log_file_name,
                "error": str(e)
            })
    
    # Cleanup old archives
    for log_file_name in log_files:
        pattern = f"{log_file_name}.*"
        for archive_path in logs_dir.glob(pattern):
            if archive_path.name == log_file_name:
                continue
            
            try:
                # Extract timestamp from filename
                name = archive_path.name
                if name.endswith(".gz"):
                    name = name[:-3]
                
                parts = name.split(".")
                if len(parts) >= 2:
                    timestamp_str = parts[-1]
                    archive_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    
                    if archive_time < cutoff:
                        if dry_run:
                            results["deleted_archives"].append({
                                "file": archive_path.name,
                                "action": "would_delete"
                            })
                        else:
                            archive_path.unlink()
                            results["deleted_archives"].append({
                                "file": archive_path.name,
                                "action": "deleted"
                            })
            except (ValueError, IndexError) as e:
                logger.warning(f"Could not parse timestamp from {archive_path.name}: {e}")
    
    return results


@router.get("/file/stats")
async def get_file_logs_stats():
    """
    Get file sizes and rotation settings for log files.

    Returns information about current log files and their archives.

    Returns:
        dict: File statistics including sizes, counts, and rotation settings

    Example:
        curl http://localhost:8000/api/v1/logs/file/stats
    """
    from pathlib import Path

    # Get logs directory
    # router.py is at: backend/app/api/v1/logs/router.py
    # Need to go up 4 levels to reach backend/
    script_dir = Path(__file__).parent
    backend_dir = script_dir.parent.parent.parent.parent  # Go up 4 levels to backend/
    logs_dir = backend_dir / "logs"
    
    log_files = ["frontend.log", "app.log"]
    retention_days = 7  # Default retention
    
    stats = {
        "logs_directory": str(logs_dir.absolute()),
        "retention_days": retention_days,
        "files": {},
        "archives": [],
        "total_size_mb": 0
    }
    
    # Get current log file stats
    for log_file_name in log_files:
        log_path = logs_dir / log_file_name
        
        if log_path.exists():
            size_mb = log_path.stat().st_size / 1024 / 1024
            mtime = datetime.fromtimestamp(log_path.stat().st_mtime)
            
            stats["files"][log_file_name] = {
                "size_mb": round(size_mb, 4),
                "exists": True,
                "modified_at": mtime.isoformat(),
                "path": str(log_path.absolute())
            }
            stats["total_size_mb"] += size_mb
        else:
            stats["files"][log_file_name] = {
                "exists": False,
                "size_mb": 0
            }
    
    # Get archive stats
    for log_file_name in log_files:
        pattern = f"{log_file_name}.*"
        for archive_path in logs_dir.glob(pattern):
            if archive_path.name == log_file_name:
                continue
            
            size_mb = archive_path.stat().st_size / 1024 / 1024
            mtime = datetime.fromtimestamp(archive_path.stat().st_mtime)
            
            stats["archives"].append({
                "name": archive_path.name,
                "size_mb": round(size_mb, 4),
                "created_at": mtime.isoformat(),
                "is_compressed": archive_path.name.endswith(".gz")
            })
            stats["total_size_mb"] += size_mb
    
    # Sort archives by modification time (newest first)
    stats["archives"].sort(key=lambda x: x["created_at"], reverse=True)
    stats["total_size_mb"] = round(stats["total_size_mb"], 4)
    stats["archive_count"] = len(stats["archives"])
    
    return stats




# ---------------------------------------------------------------------------
# TEST-LOG GENERATION (2026-09-06, the user's intent): each test writes a
# FULL level spread — DEBUG / INFO / WARNING / ERROR / CRITICAL — so the
# Logs page shows every badge style at once AND proves the write path works
# end-to-end (the old endpoints wrote ONE INFO entry — the 'the test does
# nothing' confusion). Entries are staggered by a second so the table's
# time-desc sort stacks them DEBUG (bottom) -> CRITICAL (top).
# ---------------------------------------------------------------------------
_TEST_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def _write_test_spread(path: Path, marker: str, label: str):
    from datetime import datetime, timedelta

    now = datetime.now()
    lines = []
    for i, level in enumerate(_TEST_LOG_LEVELS):
        ts = now + timedelta(seconds=i)
        ts_parsed = ts.isoformat().replace("T", " ")[:19]
        lines.append(
            f"{ts_parsed} | {level:<8} | TestEndpoint | [TEST LOG {marker}] {label} {level.lower()} test - {ts.isoformat()}\n"
        )
    with open(path, "a") as f:
        f.writelines(lines)
    return len(lines)

@router.post("/test/frontend", status_code=201)
async def generate_test_frontend_log():
    """Generate a full level spread in frontend.log only."""
    count = _write_test_spread(
        Path(BASE_DIR) / "backend" / "logs" / "frontend.log",
        "FRONTEND", "Frontend",
    )
    return {"success": True, "type": "frontend", "count": count,
            "message": f"{count} frontend test entries (all levels)"}


@router.post("/test/backend", status_code=201)
async def generate_test_backend_log():
    """Generate a full level spread in app.log only."""
    count = _write_test_spread(
        Path(BASE_DIR) / "backend" / "logs" / "app.log",
        "BACKEND", "Backend",
    )
    return {"success": True, "type": "backend", "count": count,
            "message": f"{count} backend test entries (all levels)"}


@router.post("/test", status_code=201)
async def create_test_log():
    """
    Create test log entries for debugging (frontend + backend).

    Each source gets a full level spread (DEBUG..CRITICAL) so the
    Logs page shows every badge style and proves the write path.
    """
    from app.core.config import BASE_DIR
    from pathlib import Path

    logs_dir = Path(BASE_DIR) / "backend" / "logs"
    frontend_count = _write_test_spread(logs_dir / "frontend.log", "FRONTEND", "Frontend")
    backend_count = _write_test_spread(logs_dir / "app.log", "BACKEND", "Backend")
    results = {
        "frontend": {"count": frontend_count},
        "backend": {"count": backend_count},
    }
    
    return {"success": True, "results": results}


@router.get("/test", status_code=200)
async def get_test_logs(
    db: Annotated[AsyncSession, Depends(get_db_session)]
):
    """
    Get recent test logs created by the /test POST endpoint.
    
    Returns:
        list: Recent test logs for verification
    """
    log_service = LogService(db)
    
    # Get logs with source containing "Test"
    logs, total = await log_service.get_logs(
        skip=0,
        limit=10,
        search="[BACKEND TEST]"
    )
    
    return {
        "count": len(logs),
        "total_matching": total,
        "logs": [
            {
                "id": log.id,
                "timestamp": log.timestamp,
                "message": log.message,
                "source": log.source,
                "level": log.level
            }
            for log in logs
        ]
    }


@router.delete("/file/clear", status_code=200)
async def clear_log_files(
    frontend: bool = False,
    backend: bool = False,
    archives: bool = False,
):
    """
    Clear log files and/or archives.

    Args:
        frontend: Clear frontend.log (default: False)
        backend: Clear app.log (default: False)
        archives: Clear all archive files (default: False)

    Returns:
        dict: Deletion status
    """
    from pathlib import Path
    import glob

    # Get logs directory
    script_dir = Path(__file__).parent
    backend_dir = script_dir.parent.parent.parent.parent
    logs_dir = backend_dir / "logs"

    result: dict[str, list[str]] = {
        "deleted": [],
        "errors": []
    }

    # Clear frontend.log
    if frontend:
        frontend_log = logs_dir / "frontend.log"
        if frontend_log.exists():
            try:
                # TRUNCATE, never unlink+recreate (2026-09-06, the
                # deleted-fd dig): the backend's own RotatingFileHandler
                # holds these files open — unlink() orphaned the running
                # process's fd, which kept writing to the deleted inode
                # (all backend logs silently lost after Clear ALL at
                # 10:00; app.log sat at 0 bytes). open('w') clears in
                # place and the handler keeps its fd.
                with open(frontend_log, "w"):
                    pass
                result["deleted"].append("frontend.log")
                logger.info("Cleared frontend.log file")
            except Exception as e:
                result["errors"].append(f"Failed to clear frontend.log: {e}")
                logger.error(f"Failed to clear frontend.log: {e}")
        else:
            result["deleted"].append("frontend.log (did not exist)")

    # Clear app.log (optional)
    if backend:
        app_log = logs_dir / "app.log"
        if app_log.exists():
            try:
                with open(app_log, "w"):
                    pass  # truncate in place (see the frontend block above)
                result["deleted"].append("app.log")
                logger.info("Cleared app.log file")
            except Exception as e:
                result["errors"].append(f"Failed to clear app.log: {e}")
                logger.error(f"Failed to clear app.log: {e}")
        else:
            result["deleted"].append("app.log (did not exist)")

    # Clear archives (optional)
    if archives:
        try:
            # Find all .gz files in logs directory
            archive_pattern = str(logs_dir / "*.gz")
            archive_files = glob.glob(archive_pattern)
            for archive_file in archive_files:
                try:
                    Path(archive_file).unlink()
                    result["deleted"].append(Path(archive_file).name)
                except Exception as e:
                    result["errors"].append(f"Failed to clear {archive_file}: {e}")
            logger.info(f"Cleared {len(archive_files)} archive files")
        except Exception as e:
            result["errors"].append(f"Failed to clear archives: {e}")
            logger.error(f"Failed to clear archives: {e}")

    return {
        "deleted": result["deleted"],
        "errors": result["errors"],
        "status": "success" if not result["errors"] else "partial"
    }




@router.delete("/{log_id}", status_code=200)
async def delete_log(
    log_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)]
):
    """
    Delete a specific log by ID.
    
    Args:
        log_id: ID of log to delete
        db: Database session
    
    Returns:
        dict: Deletion status
    """
    from sqlalchemy import delete
    
    result = await db.execute(
        delete(Log).where(Log.id == log_id)
    )
    await db.commit()
    
    if result.rowcount == 0:  # type: ignore[attr-defined]
        return {"deleted": 0, "status": "not_found", "message": f"Log {log_id} not found"}
    
    _announce("deleted", {"log_id": log_id, "event": "deleted"})
    return {"deleted": 1, "status": "success", "id": log_id}


@router.get("/sources")
async def get_log_sources(
    db: Annotated[AsyncSession, Depends(get_db_session)]
):
    """
    Get all unique log sources.
    
    Returns:
        list: List of unique source names
    """
    try:
        log_service = LogService(db)
        sources = await log_service.get_sources()
        return {"sources": sources, "total": len(sources)}
    except Exception as e:
        logger.error(f"Failed to get log sources: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve log sources: {str(e)}")


@router.get("/stream")
async def stream_logs(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    level: Annotated[Optional[str], Query()] = None,
    source: Annotated[Optional[str], Query()] = None,
):
    """
    Stream logs in real-time using Server-Sent Events (SSE).
    
    Args:
        level: Filter by log level
        source: Filter by source
        db: Database session
        
    Returns:
        StreamingResponse: SSE stream of log entries
    """
    import asyncio
    
    async def generate_logs():
        """Generate log events as SSE messages."""
        last_log_id = 0
        
        # Get the most recent log ID to start from
        try:
            log_service = LogService(db)
            recent_logs, _ = await log_service.get_logs(skip=0, limit=1)
            if recent_logs:
                last_log_id = recent_logs[0].id
        except Exception as e:
            logger.error(f"Failed to get recent logs for stream: {e}")
        
        while True:
            try:
                # Check for new logs
                log_service = LogService(db)
                new_logs, _ = await log_service.get_logs(
                    skip=0,
                    limit=100,
                    level=level,
                    source=source
                )
                
                # Send new logs
                for log in reversed(new_logs):  # Reverse to get newest last
                    if log.id > last_log_id:
                        last_log_id = log.id
                        
                        log_data = {
                            "id": log.id,
                            "timestamp": log.timestamp,
                            "level": log.level,
                            "source": log.source,
                            "message": log.message,
                            "context": log.context,
                            "user_agent": log.user_agent,
                            "url": log.url,
                            "session_id": log.session_id,
                            "trace_id": log.trace_id,
                            "log_type": log.log_type
                        }
                        
                        yield f"data: {json.dumps(log_data)}\n\n"
                
                # Wait before checking again
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error in log stream: {e}")
                # Send error event
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                await asyncio.sleep(5)
    
    return StreamingResponse(
        generate_logs(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/recent", response_model=list[LogEntryResponse])
async def get_recent_logs(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    n: Annotated[int, Query(ge=1, le=1000, description="Number of recent logs to retrieve")] = 100,
    level: Annotated[Optional[str], Query(description="Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")] = None,
    source: Annotated[Optional[str], Query(description="Filter by source")] = None,
):
    """
    Get the N most recent logs.

    This endpoint is designed for programmatic access via CLI tools like curl.
    It returns logs in reverse chronological order (newest first).

    Args:
        n: Number of recent logs to retrieve (1-1000, default: 100)
        level: Optional filter by log level
        source: Optional filter by source

    Returns:
        list[LogEntryResponse]: List of log entries, newest first

    Example:
        curl http://localhost:8000/api/v1/logs/recent?n=50

        curl "http://localhost:8000/api/v1/logs/recent?n=20&level=error"

        curl "http://localhost:8000/api/v1/logs/recent?n=100&source=ChatInterface"
    """
    try:
        log_service = LogService(db)

        # Get recent logs (no pagination, just limit)
        logs, _ = await log_service.get_logs(
            skip=0,
            limit=n,
            level=level,
            source=source
        )

        # Convert to response format
        def format_value(value):
            """Format value for JSON response"""
            if value is None:
                return None
            if hasattr(value, 'isoformat'):
                return value.isoformat()
            return value
        
        items = [
            LogEntryResponse(
                id=log.id,
                timestamp=format_value(log.timestamp),
                level=log.level,
                source=log.source,
                message=log.message,
                context=log.context or {},
                user_agent=format_value(log.user_agent),
                url=format_value(log.url),
                session_id=format_value(log.session_id),
                trace_id=format_value(log.trace_id),
                created_at=format_value(log.created_at)
            )
            for log in logs
        ]

        return items

    except Exception as e:
        logger.error(f"Failed to get recent logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/traces/export")
async def export_traces(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    format: Annotated[str, Query(description="Export format: json or csv")] = "json",
    flow: Annotated[Optional[str], Query(description="Filter by flow name")] = None,
    limit: Annotated[int, Query(ge=1, le=10000, description="Max traces to return")] = 1000,
    since: Annotated[Optional[int], Query(description="Unix timestamp, traces after this time")] = None,
):
    """
    Export trace logs in JSON or CSV format.

    This endpoint is designed for programmatic access to flow traces.
    It filters logs by source='FlowTrace' and returns them in the specified format.

    Args:
        format: Export format - 'json' or 'csv' (default: json)
        flow: Optional filter by flow name (e.g., 'ChatFlow')
        limit: Max traces to return (1-10000, default: 1000)
        since: Optional Unix timestamp to filter traces after this time

    Returns:
        Response: File download with traces in specified format

    Example:
        curl "http://localhost:8000/api/v1/logs/traces/export?format=json&limit=10"

        curl "http://localhost:8000/api/v1/logs/traces/export?format=csv&flow=ChatFlow"
    """
    try:
        log_service = LogService(db)

        # Get trace logs (source contains 'FlowTrace')
        # Build source filter - we want logs where source contains 'FlowTrace'
        logs, _ = await log_service.get_logs(
            skip=0,
            limit=limit,
            source="FlowTrace"  # This will do ILIKE %FlowTrace%
        )

        # Filter by flow name if provided
        if flow:
            logs = [log for log in logs if flow in log.source or (log.message and flow in log.message)]

        # Filter by since timestamp if provided
        if since:
            since_dt = datetime.fromtimestamp(since)
            filtered_logs = []
            for log in logs:
                try:
                    log_timestamp = log.timestamp
                    if isinstance(log_timestamp, str):
                        log_time = datetime.fromisoformat(log_timestamp.replace('Z', '+00:00'))
                    else:
                        log_time = log_timestamp
                    if log_time >= since_dt:
                        filtered_logs.append(log)
                except (ValueError, TypeError):
                    continue
            logs = filtered_logs

        # Format trace data
        def format_value(value):
            """Format value for JSON response"""
            if value is None:
                return None
            if hasattr(value, 'isoformat'):
                return value.isoformat()
            return value

        def extract_flow_from_message(message: str) -> str:
            """Extract flow name from trace message like '[FLOW TRACE #123] ChatFlow:sendMessage'"""
            if not message:
                return "Unknown"
            # Try to extract from pattern "[FLOW TRACE #N] FlowName:step"
            if "] " in message:
                after_prefix = message.split("] ", 1)[1] if "] " in message else message
                if ":" in after_prefix:
                    return after_prefix.split(":")[0]
            return "Unknown"

        def extract_step_from_message(message: str) -> str:
            """Extract step name from trace message"""
            if not message:
                return "Unknown"
            if "] " in message:
                after_prefix = message.split("] ", 1)[1] if "] " in message else message
                if ":" in after_prefix:
                    parts = after_prefix.split(":")
                    if len(parts) > 1:
                        return parts[1].split("(")[0]  # Remove any parentheses
            return "Unknown"

        traces = []
        for log in logs:
            context = log.context or {}
            sequence = context.get('sequence', 0)
            flow = extract_flow_from_message(log.message)
            step = extract_step_from_message(log.message)

            trace_data = {
                "sequence": sequence,
                "timestamp": format_value(log.timestamp),
                "flow": flow,
                "step": step,
                "message": log.message,
                "context": context
            }
            traces.append(trace_data)

        # Sort by sequence number
        traces.sort(key=lambda x: x.get('sequence', 0))

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        if format.lower() == "csv":
            # Create CSV response
            output = io.StringIO()
            fieldnames = ['sequence', 'timestamp', 'flow', 'step', 'message', 'context']
            writer = csv.DictWriter(output, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)

            writer.writeheader()
            for trace in traces:
                # JSON-encode the context field for CSV
                row = trace.copy()
                row['context'] = json.dumps(trace['context'])
                writer.writerow(row)

            csv_content = output.getvalue()

            return Response(
                content=csv_content,
                media_type="text/csv",
                headers={
                    "Content-Disposition": f'attachment; filename="traces-export-{timestamp}.csv"'
                }
            )
        else:
            # Create JSON response
            response_data = {
                "traces": traces,
                "total": len(traces),
                "format": "json"
            }

            json_content = json.dumps(response_data, indent=2)

            return Response(
                content=json_content,
                media_type="application/json",
                headers={
                    "Content-Disposition": f'attachment; filename="traces-export-{timestamp}.json"'
                }
            )

    except Exception as e:
        logger.error(f"Failed to export traces: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to export traces: {str(e)}")
