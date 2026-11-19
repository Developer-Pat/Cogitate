"""Workflow error taxonomy (Phase F).

The kind's error contract names what's RETRYABLE vs what
DEAD-LETTERS. LangGraph's native RetryPolicy has a `retry_on`
hook — this module is the bridge: the taxonomy → a RetryPolicy.

Canonical rules (study 07 §2-3):
- RETRYABLE: transient infrastructure — LLM timeouts, rate
  limits, connection errors, 5xx. The LLM or network hiccuped;
  the step is safe to run again.
- NON-RETRYABLE (dead-letter): configuration/validation errors,
  malformed inputs, provider/model misconfiguration. Retrying
  can't fix them; they produce the error PRODUCT instead of
  hanging or crashing.

Defensive basics (study 07 §3): dead-letter, don't hang; bound
everything (max attempts); idempotent steps (a retried step must
be safe to run twice).
"""

from __future__ import annotations

from typing import Sequence, Type

from langgraph.types import RetryPolicy


# ── The taxonomy ───────────────────────────────────────────────────────

def is_retryable(exc: BaseException) -> bool:
    """The retryable vs dead-letter decision.

    Retryable: transient infrastructure failures. Everything else
    (validation, config, programming errors) dead-letters.
    """
    # connection/timeout family — the network hiccuped
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return True
    # generic transient marker — class name OR message (providers
    # wrap their own: RuntimeError('rate limit exceeded'))
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    haystack = name + " " + message
    if any(tok in haystack for tok in ("timeout", "rate limit", "throttl",
                                       "temporar", "overload", "busy",
                                       "unavailable", "5xx", "connection",
                                       "retry", "429", "503")):
        return True
    return False


# ── The contract ───────────────────────────────────────────────────────

class ErrorContract:
    """A kind's declared error behavior.

    Fields:
        retryable_exceptions: exception classes the kind retries
            (default: the taxonomy's is_retryable decision).
        max_attempts: total attempts including the first (native
            RetryPolicy semantics; default 3).
        backoff_factor: exponential multiplier (default 2.0).
        error_product_type: what a dead-lettered run delivers
            (default 'report' — the error report).
    """

    def __init__(
        self,
        retryable_exceptions: Sequence[Type[BaseException]] = (),
        max_attempts: int = 3,
        backoff_factor: float = 2.0,
        error_product_type: str = "report",
    ) -> None:
        self.retryable_exceptions = tuple(retryable_exceptions)
        self.max_attempts = max_attempts
        self.backoff_factor = backoff_factor
        self.error_product_type = error_product_type

    def to_retry_policy(self) -> RetryPolicy:
        """The native LangGraph RetryPolicy for this contract."""
        exceptions = self.retryable_exceptions

        def retry_on(exc: BaseException) -> bool:
            if exceptions:
                return isinstance(exc, exceptions)
            return is_retryable(exc)

        return RetryPolicy(
            max_attempts=self.max_attempts,
            backoff_factor=self.backoff_factor,
            jitter=True,
            retry_on=retry_on,
        )


# ── The defaults per kind family ───────────────────────────────────────

DEFAULT_CONTRACT = ErrorContract()
LLM_CONTRACT = ErrorContract(
    retryable_exceptions=(
        TimeoutError, ConnectionError, OSError,
    ),
    max_attempts=4,          # LLM steps get a bit more patience
    backoff_factor=2.0,
)
TOOL_CONTRACT = ErrorContract(
    retryable_exceptions=(
        TimeoutError, ConnectionError, OSError,
    ),
    max_attempts=3,
    backoff_factor=2.0,
)


def contract_for(kind_name: str) -> ErrorContract:
    """The default error contract per kind family."""
    if kind_name in ("chain", "multi-agent", "agent-task"):
        return LLM_CONTRACT
    if kind_name == "monitor":
        return LLM_CONTRACT  # fetch + summarize — network-heavy
    if kind_name in ("file-processing", "context-indexing"):
        return TOOL_CONTRACT
    return DEFAULT_CONTRACT
