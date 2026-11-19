"""
Database retry utilities for SQLite lock contention.

Provides a decorator and helper function for retrying async database
operations that fail with ``sqlite3.OperationalError: database is locked``.

SQLite has limited concurrency — write transactions block each other.
When multiple requests hit the database simultaneously, one will acquire
the lock and the others will fail.  This module adds exponential-backoff
retry so that transient lock contention is handled gracefully.

Usage:
    from app.domain.macros.db_retry_utils import retry_on_db_lock

    @retry_on_db_lock(max_retries=3, base_delay=0.5)
    async def my_write_operation(self, ...):
        ...
        await session.commit()
"""

from __future__ import annotations

import asyncio
import logging
from functools import wraps
from typing import Any, Callable, TypeVar

from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# SQLite lock error code
SQLITE_LOCKED_MSG = "database is locked"


def _is_db_lock_error(exc: Exception) -> bool:
    """
    Check whether an exception is a SQLite ``database is locked`` error.

    Args:
        exc: The exception to check.

    Returns:
        True if the exception is an ``OperationalError`` containing the
        lock message, False otherwise.
    """
    if not isinstance(exc, OperationalError):
        return False
    msg = str(exc).lower()
    return SQLITE_LOCKED_MSG in msg


def retry_on_db_lock(
    max_retries: int = 3,
    base_delay: float = 0.25,
    max_delay: float = 2.0,
) -> Callable[[F], F]:
    """
    Decorator that retries an async function when it fails with a SQLite
    ``database is locked`` error, using exponential backoff.

    Non-lock errors are re-raised immediately without retry.

    Args:
        max_retries: Maximum number of retry attempts (default: 3).
        base_delay: Initial delay in seconds before the first retry
            (default: 0.25).  Doubled on each subsequent attempt.
        max_delay: Maximum delay in seconds between retries
            (default: 2.0).

    Returns:
        Decorated async function with retry logic.

    Example:
        @retry_on_db_lock(max_retries=5, base_delay=0.1)
        async def update_macro(self, db, macro_id, data):
            ...
            await db.commit()
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_error: Exception | None = None
            delay = base_delay

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    last_error = exc
                    if not _is_db_lock_error(exc):
                        raise  # Non-lock error — re-raise immediately

                    if attempt < max_retries:
                        logger.warning(
                            "DB lock contention on '%s' (attempt %d/%d). "
                            "Retrying in %.2fs...",
                            func.__name__,
                            attempt + 1,
                            max_retries,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, max_delay)
                    else:
                        logger.error(
                            "DB lock contention on '%s' — all %d retries "
                            "exhausted.",
                            func.__name__,
                            max_retries,
                        )

            # All retries exhausted — re-raise the last lock error
            raise last_error  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator
