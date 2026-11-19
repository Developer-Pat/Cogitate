"""
Retry logic for failed workflow nodes.

Provides:
- RetryConfig: Configuration for retry behavior
- RetryResult: Result of retry attempt
- execute_with_retry: Execute function with retry logic

Supports:
- Configurable max retries
- Exponential backoff
- Retry on specific exception types
- Retry callbacks for monitoring
"""

from typing import Any, Callable, Dict, List, Optional, Type
from datetime import datetime, UTC
import time
import asyncio


class RetryConfig:
    """
    Configuration for retry behavior.

    Attributes:
        max_retries: Maximum number of retry attempts (default: 3)
        delay: Initial delay between retries in seconds (default: 1.0)
        backoff_multiplier: Multiplier for exponential backoff (default: 2.0)
        max_delay: Maximum delay between retries (default: 60.0)
        retry_on: Exception types to retry on (default: all exceptions)
        retryable_status_codes: HTTP status codes to retry on (for API calls)
    """

    def __init__(
        self,
        max_retries: int = 3,
        delay: float = 1.0,
        backoff_multiplier: float = 2.0,
        max_delay: float = 60.0,
        retry_on: Optional[List[Type[Exception]]] = None,
    ):
        self.max_retries = max_retries
        self.delay = delay
        self.backoff_multiplier = backoff_multiplier
        self.max_delay = max_delay
        self.retry_on = retry_on or [Exception]  # Retry on all exceptions by default

    def get_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt using exponential backoff.

        Args:
            attempt: Attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        delay = self.delay * (self.backoff_multiplier ** attempt)
        return min(delay, self.max_delay)

    def should_retry(self, exception: Exception) -> bool:
        """
        Check if exception should trigger retry.

        Args:
            exception: Exception that was raised

        Returns:
            True if should retry, False otherwise
        """
        return any(isinstance(exception, exc_type) for exc_type in self.retry_on)


class RetryResult:
    """
    Result of retry attempt.

    Attributes:
        success: Whether execution succeeded
        result: Result value (if successful)
        error: Error value (if failed)
        attempts: Number of attempts made
        total_time: Total time spent in seconds
    """

    def __init__(
        self,
        success: bool,
        result: Any = None,
        error: Optional[Exception] = None,
        attempts: int = 1,
        total_time: float = 0.0,
    ):
        self.success = success
        self.result = result
        self.error = error
        self.attempts = attempts
        self.total_time = total_time
        self.timestamp = datetime.now(UTC).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        return {
            "success": self.success,
            "result": self.result,
            "error": str(self.error) if self.error else None,
            "attempts": self.attempts,
            "total_time": self.total_time,
            "timestamp": self.timestamp,
        }


def execute_with_retry(
    func: Callable,
    *args,
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
    **kwargs,
) -> RetryResult:
    """
    Execute function with retry logic.

    Args:
        func: Function to execute
        *args: Positional arguments for func
        config: Retry configuration (uses defaults if not provided)
        on_retry: Optional callback called before each retry
                  Signature: callback(attempt, exception, delay)
        **kwargs: Keyword arguments for func

    Returns:
        RetryResult with success/failure information

    Usage:
        ```python
        def flaky_function():
            # May fail intermittently
            pass

        result = execute_with_retry(
            flaky_function,
            config=RetryConfig(max_retries=3, delay=1.0),
            on_retry=lambda attempt, exc, delay: print(f"Retry {attempt}: {exc}")
        )

        if result.success:
            print(f"Success after {result.attempts} attempts")
        else:
            print(f"Failed: {result.error}")
        ```
    """
    if config is None:
        config = RetryConfig()

    start_time = time.time()
    last_exception = None

    for attempt in range(config.max_retries + 1):
        try:
            # Execute function
            result = func(*args, **kwargs)

            # Success
            total_time = time.time() - start_time
            return RetryResult(
                success=True,
                result=result,
                attempts=attempt + 1,
                total_time=total_time,
            )

        except Exception as e:
            last_exception = e

            # Check if we should retry
            if not config.should_retry(e):
                # Don't retry on this exception type
                total_time = time.time() - start_time
                return RetryResult(
                    success=False,
                    error=e,
                    attempts=attempt + 1,
                    total_time=total_time,
                )

            # Check if we have retries left
            if attempt >= config.max_retries:
                # No more retries
                break

            # Calculate delay
            delay = config.get_delay(attempt)

            # Call retry callback if provided
            if on_retry:
                on_retry(attempt + 1, e, delay)

            # Wait before retry
            time.sleep(delay)

    # All retries exhausted
    total_time = time.time() - start_time
    return RetryResult(
        success=False,
        error=last_exception,
        attempts=config.max_retries + 1,
        total_time=total_time,
    )


async def execute_with_retry_async(
    func: Callable,
    *args,
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
    **kwargs,
) -> RetryResult:
    """
    Execute async function with retry logic.

    Args:
        func: Async function to execute
        *args: Positional arguments for func
        config: Retry configuration
        on_retry: Optional callback called before each retry
        **kwargs: Keyword arguments for func

    Returns:
        RetryResult with success/failure information
    """
    if config is None:
        config = RetryConfig()

    start_time = time.time()
    last_exception = None

    for attempt in range(config.max_retries + 1):
        try:
            # Execute async function
            result = await func(*args, **kwargs)

            # Success
            total_time = time.time() - start_time
            return RetryResult(
                success=True,
                result=result,
                attempts=attempt + 1,
                total_time=total_time,
            )

        except Exception as e:
            last_exception = e

            # Check if we should retry
            if not config.should_retry(e):
                total_time = time.time() - start_time
                return RetryResult(
                    success=False,
                    error=e,
                    attempts=attempt + 1,
                    total_time=total_time,
                )

            # Check if we have retries left
            if attempt >= config.max_retries:
                break

            # Calculate delay
            delay = config.get_delay(attempt)

            # Call retry callback if provided
            if on_retry:
                on_retry(attempt + 1, e, delay)

            # Wait before retry (async)
            await asyncio.sleep(delay)

    # All retries exhausted
    total_time = time.time() - start_time
    return RetryResult(
        success=False,
        error=last_exception,
        attempts=config.max_retries + 1,
        total_time=total_time,
    )
