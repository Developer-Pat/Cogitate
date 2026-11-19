"""
LLM utility helpers.

Provides an explicit async retry wrapper around ``litellm.acompletion``.

Why this exists
---------------
LiteLLM's module-level ``litellm.num_retries`` and ``litellm.retry_delay``
settings **only** apply to the synchronous ``completion()`` function.  They
are silently ignored for the async ``acompletion()`` variant which is used
throughout the codebase (chat streaming, etc.).

This wrapper fills the gap so that rate-limit errors (429 / RateLimitError)
are automatically retried with a configurable delay, regardless of whether
the underlying call is streaming or non‑streaming.

It is also where a model call is **traced**. Every chat call goes through here, so one wrapper covers
them all: the call becomes a Langfuse ``generation`` hanging from the turn's span, carrying the model,
the messages, the assistant's text and the tokens — the four things the tracing baseline asks for and
the one place they are all in hand. A call made with no trace open (the delegate path, the
``/completions`` passthrough) is left alone rather than manufactured into a trace of its own.
"""

import asyncio
import logging
import sys
from contextlib import ExitStack
from typing import Any, AsyncIterator, Callable, Dict, Optional, Tuple

from litellm import acompletion
from litellm.exceptions import RateLimitError

from app.domain.providers import availability
from app.services.cognitive_pipeline import turn_config
from app.services.cognitive_pipeline.turn_state import response_usage

logger = logging.getLogger(__name__)

# The observation's name for a chat model call: the OPERATION, verb-first and stable, so a dashboard
# or an evaluator can target it. A caller with a different operation passes `call_name`.
DEFAULT_CALL_NAME = "generate-response"


def _generation_fields(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """The generation's own fields, read off a litellm request."""
    return {"model": kwargs.get("model"), "input": kwargs.get("messages")}


def _cost_details(usage: Tuple[int, int], pricing: Dict[str, float]) -> Dict[str, float]:
    """The call's cost per usage type, keyed as `usage_details` is.

    The unit is `calculate_cost`'s — the price is PER 1K TOKENS — so this figure and the one on the
    usage row come out of one arithmetic. Langfuse takes the number as given, which is the point:
    the app can price a model no definition knows, and nothing has to be seeded to keep it current.
    """
    return {
        "input": round(usage[0] / 1000 * pricing.get("prompt", 0.0), 6),
        "output": round(usage[1] / 1000 * pricing.get("completion", 0.0), 6),
    }


def _finish_generation(
    observation: Any,
    *,
    output: Any,
    usage: Optional[Tuple[int, int]],
    pricing: Optional[Dict[str, float]] = None,
    error: Optional[BaseException] = None,
) -> None:
    """Attach what a finished call carries — the text, the tokens, the cost, and how it ended.

    THE COST IS THE APP'S OWN (2026-10-08). When the caller resolved a price for this model, the
    generation carries `cost_details` and Langfuse uses it as given — no model definition needed, so
    a local or private model is priced like any other, and there is no second copy of the prices to
    refresh. When there is NO price, nothing is sent: a `0.0` would read as "this call was free",
    which is a claim the app cannot make (`ollama_cloud` and the local servers publish nothing).
    """
    if observation is None:
        return

    from app.workflows.observability.langfuse_config import LangfuseManager

    fields: Dict[str, Any] = {}
    if output:
        fields["output"] = output
    if usage:
        # The keys are the usage type names the model definition declares; "input"/"output" is what
        # these providers' definitions use. Cost follows from these plus `model`.
        fields["usage_details"] = {"input": usage[0], "output": usage[1]}
    if usage and pricing:
        fields["cost_details"] = _cost_details(usage, pricing)
    if error is not None:
        fields["level"] = "ERROR"
        fields["status_message"] = str(error)[:300]
    LangfuseManager.update(observation, **fields)


def _response_text(response: Any) -> Optional[str]:
    """The assistant's text out of a NON-streamed completion, or None."""
    choices = getattr(response, "choices", None)
    if not choices:
        return None
    content = getattr(getattr(choices[0], "message", None), "content", None)
    return content if isinstance(content, str) and content else None


def _chunk_text(chunk: Any) -> Optional[str]:
    """The text one STREAMED chunk carries, or None (a usage-only chunk has none)."""
    choices = getattr(chunk, "choices", None)
    if not choices:
        return None
    content = getattr(getattr(choices[0], "delta", None), "content", None)
    return content if isinstance(content, str) and content else None


async def _traced_stream(
    stream: Any,
    kwargs: Dict[str, Any],
    name: str,
    pricing: Optional[Dict[str, float]] = None,
) -> AsyncIterator[Any]:
    """Yield the provider's chunks through, with one ``generation`` spanning the whole stream.

    The generation opens when the consumer starts reading — the point at which the provider's first
    token is being awaited — and closes when the consumer stops, exhausts, or **abandons** the stream
    (the client disconnect the chat route already treats as an interrupted turn). Nothing about the
    chunks changes: they are passed through untouched, so the caller sees exactly what it saw before.

    ``pricing`` is this model's price when the caller resolved one; the finished generation carries
    the cost it implies. Unpriced means no cost at all — see ``_finish_generation``.
    """
    from app.workflows.observability.langfuse_config import LangfuseManager

    stack = ExitStack()
    observation = stack.enter_context(LangfuseManager.generation(name=name, **_generation_fields(kwargs)))

    text: list[str] = []
    usage: Optional[Tuple[int, int]] = None
    try:
        async for chunk in stream:
            piece = _chunk_text(chunk)
            if piece:
                text.append(piece)
            chunk_usage = response_usage(chunk)
            if chunk_usage:
                usage = chunk_usage
            yield chunk
    finally:
        # No `await` here: this also runs on abandon (GeneratorExit). `exc_info` is non-None when the
        # stream died, which is what marks the generation errored rather than successful.
        _finish_generation(
            observation,
            output="".join(text),
            usage=usage,
            pricing=pricing,
            error=sys.exc_info()[1],
        )
        stack.close()


def _log_prompt_account(kwargs: Dict[str, Any], prompt_budget: Optional[int]) -> None:
    """Log ONE measured line about the prompt this call is about to send.

    The input-budget arc's Phase A. Everything else in this module is about the call's mechanics;
    this is the only part that says what the call *carries*. It observes and returns nothing —
    Phase B is the phase that acts on the numbers (the trim deducts the schemas and the replay),
    and this line is what B is diffed against.

    Never raises: bookkeeping must not turn a working call into a dead one, and a prompt nobody
    could measure is not a prompt anybody can limit.
    """
    try:
        from app.services.cognitive_pipeline.limits import INPUT_SOFT_FRACTION
        from app.services.cognitive_pipeline.prompt_accounting import log_prompt_account

        threshold = (
            int(prompt_budget * INPUT_SOFT_FRACTION) if prompt_budget is not None else None
        )
        log_prompt_account(
            messages=kwargs.get("messages"),
            tools=kwargs.get("tools"),
            input_budget=prompt_budget,
            soft_threshold=threshold,
        )
    except Exception:  # noqa: BLE001 — an account that raises is worse than one that is missing
        logger.debug("prompt accounting unavailable for this call", exc_info=True)


def _note_outcome(kwargs: Dict[str, Any], provider: Optional[str], *, failure: Optional[str]) -> None:
    """Report ONE real call's outcome to the availability bridge — the bridge's second producer.

    The destination is where this call was ALREADY going: the request's `api_base` when it carries one
    (every local row, and the openai-compatible rows), else the model slug's provider prefix
    (`deepseek/deepseek-chat` -> `deepseek`) — which is what makes two cloud services two destinations
    for the verdict's corroboration. `failure` is a FAILURE_* class, or None when the call answered.

    Never raises: bookkeeping must not turn a working call into a dead one, and an unrecorded outcome
    is still a call that happened.
    """
    try:
        destination = kwargs.get("api_base") or str(kwargs.get("model") or "").split("/")[0]
        availability.note_call_outcome(
            destination,
            failure=failure,
            provider=provider,
            model=kwargs.get("model"),
        )
    except Exception:  # noqa: BLE001 — an unrecorded outcome is better than a broken call
        logger.debug("call outcome not recorded", exc_info=True)


async def acompletion_with_retry(
    max_retries: Optional[int] = None,
    retry_delay: Optional[int] = None,
    on_attempt: Optional[Callable[[int], None]] = None,
    call_name: Optional[str] = None,
    pricing: Optional[Dict[str, float]] = None,
    prompt_budget: Optional[int] = None,
    provider: Optional[str] = None,
    **kwargs: Any,
) -> Any:
    """
    Call ``litellm.acompletion`` with explicit async retry on rate limits.

    Parameters
    ----------
    max_retries
        Maximum number of attempts (including the initial call). ``None`` — the default — means
        the turn config's value (`turn_config.retry_attempts()`), read HERE rather than
        bound to a default argument, because a default argument freezes its value at import
        and the config service exists so the source behind a number can change.
    retry_delay
        Base delay in seconds between retries (uses linear back-off:
        ``delay * attempt_number``). ``None`` means `turn_config.retry_delay_s()`, read the
        same way.
    on_attempt
        Called with the 0-based attempt index immediately BEFORE each
        ``acompletion`` call, the first one included. The caller's turn
        accounting (``chat/router.py``, Phase D.1) uses it to count the retries
        this wrapper makes on the turn's behalf — they are invisible to the
        caller otherwise and a retry storm is what the provider-call limits are
        about. Inert when unset.
    call_name
        The traced generation's name — the OPERATION, not the model (``generate-response``).
        ``None`` uses ``DEFAULT_CALL_NAME``; a caller whose call does something else says so.
    pricing
        This model's price, PER 1K TOKENS — ``calculate_cost``'s unit — when the caller knows it.
        The generation then carries ``cost_details``, so Langfuse prices the call from the app's own
        catalog: no model definition to seed, and nothing to keep in step when a price changes.
        ``None`` — the default — sends no cost, because a ``0.0`` on a model whose price is unknown
        is a claim that the call was free.
    prompt_budget
        The assembly ceiling this call's prompt was built under (``context.input_budget``, E.1).
        Used for ONE thing: the accounting line below prints the measured composition beside the
        number the prompt was assembled under. ``None`` means the caller named no ceiling and the
        app's own default is reported as such. It is consumed here, never forwarded to litellm.
    provider
        The provider ROW this call is made against (``deepseek``, ``llama``), when the caller knows
        it — the availability bridge's CARRIER (its third seam). Every call's outcome is reported to
        ``availability.note_call_outcome``, which is how a real turn's traffic feeds the connection
        verdict and how a service that stops answering becomes a fact the app can announce without
        probing anything. ``None`` — the default — means the caller cannot name a row (the
        ``/completions`` passthrough takes a raw model string): the call is still observed, but no
        service is accused of anything. Consumed here, never forwarded to litellm.
    **kwargs
        All keyword arguments are forwarded directly to ``litellm.acompletion``.

    Returns
    -------
    The return value of ``litellm.acompletion`` – either a response object
    (non‑streaming) or an async generator (streaming). The streaming case is wrapped so the
    generation stays open for as long as the consumer reads; the chunks themselves are unchanged.

    Raises
    ------
    RateLimitError
        If all retry attempts are exhausted due to rate limiting.
    Any other exception
        Propagated immediately (no retry for non‑rate‑limit errors).
    """
    # THE CONFIGURED VALUES ARE READ HERE, NOT AT IMPORT (the turn config service): a default
    # argument freezes its value when the module loads, so a number whose source is meant to be
    # able to change cannot be bound in the signature.
    attempts = turn_config.retry_attempts() if max_retries is None else max_retries
    delay = turn_config.retry_delay_s() if retry_delay is None else retry_delay
    name = call_name or DEFAULT_CALL_NAME

    # ASK FOR THE TOKENS ON A STREAM (2026-10-08). Several providers report usage on a
    # streamed call ONLY when asked — measured on llama.cpp (local) and groq, documented by
    # OpenAI and DeepSeek. Without it those turns carried no tokens at all, so the turn's own
    # account fell back to an ESTIMATE (`turn_state`: `tokens=estimated`) and the traced
    # generation had nothing to price. OpenRouter is indifferent (it always sends usage) and
    # Ollama's compat layer models the field, so asking costs nothing we have measured.
    # `stream_options` is only valid with a stream, which is why the funnel sets it rather
    # than every caller; an explicit caller value wins.
    if kwargs.get("stream"):
        kwargs.setdefault("stream_options", {"include_usage": True})

    # THE PROMPT'S ACCOUNT (the input-budget arc, Phase A) — ONE line per provider call, here
    # because every chat call funnels through this wrapper: the loop, the fallback, the delegate.
    # It measures the prompt by contributor (system · history · tool results · tool schemas ·
    # replayed reasoning) and prints it beside the ceiling in force, so "the budget governs less
    # than the prompt sends" is a reading rather than an argument. It observes only: nothing here
    # trims, blocks or refuses, and a failure to measure is swallowed (an account that breaks a
    # working call would be a worse defect than the one it reports).
    _log_prompt_account(kwargs, prompt_budget)

    last_exception: Optional[Exception] = None

    for attempt in range(attempts):
        # THE ATTEMPT CALLBACK (the token-limit arc, D.1/F2): the caller's turn
        # accounting counts the attempts made here on its behalf — the retries
        # are invisible to the router otherwise, and "how often did this turn
        # reach a provider?" is what the retry storm is about.
        if on_attempt is not None:
            on_attempt(attempt)
        try:
            if kwargs.get("stream"):
                # THE STREAM OPENS ITS GENERATION LATER, on the first chunk: this call only RETURNS
                # the iterator, so the observation has to span the CONSUMER's loop (see
                # `_traced_stream`), not this line.
                # THE SAME HOLDS FOR THE BRIDGE'S OUTCOME: a returned iterator is not an answer, and a
                # failure arriving mid-stream surfaces in the CONSUMER — so a streamed call is
                # observed only when it fails to OPEN (the `except` arms below).
                return _traced_stream(await acompletion(**kwargs), kwargs, name, pricing)

            # A retried call is a SECOND generation, deliberately: each invocation is its own unit,
            # and the failed attempt is what a rate-limit story is made of. The failure reaches the
            # observation from inside the block, so it is marked errored before the retry.
            from app.workflows.observability.langfuse_config import LangfuseManager

            with LangfuseManager.generation(name=name, **_generation_fields(kwargs)) as observation:
                response = await acompletion(**kwargs)
                _finish_generation(
                    observation,
                    output=_response_text(response),
                    usage=response_usage(response),
                    pricing=pricing,
                )
            # THE CALL ANSWERED (the bridge's success case): real traffic, and real evidence that the
            # service and the path to it are working.
            _note_outcome(kwargs, provider, failure=None)
            return response
        except RateLimitError as e:
            # A 429 IS AN ANSWER: the provider replied, so this is evidence the PATH works (the
            # verdict's positive half) and NOT a service outage — the retry below is the turn's own
            # business, and a provider that rate-limits is a provider that answered.
            _note_outcome(kwargs, provider, failure=availability.FAILURE_ANSWERED)
            last_exception = e
            if attempt < attempts - 1:
                wait = delay * (attempt + 1)
                logger.warning(
                    "Rate limit hit (attempt %d/%d), retrying in %ds: %s",
                    attempt + 1,
                    attempts,
                    wait,
                    e,
                )
                await asyncio.sleep(wait)
            else:
                logger.error(
                    "Rate limit exceeded after %d attempts: %s",
                    attempts,
                    e,
                )
        except Exception as exc:
            # THE BRIDGE'S OWN OUTCOME (seam 3), read BEFORE the re-raise so a caller's error copy and
            # the bridge's fact cannot disagree: WHICH END it came from is read off the exception, and
            # the wrapper's own type is not trusted to say (measured — litellm raises a refused
            # connection as a status-bearing `InternalServerError`).
            _note_outcome(kwargs, provider, failure=availability.classify_call_error(exc))
            # Non‑rate‑limit errors are not retried – propagate immediately.
            raise

    # All retries exhausted.
    raise last_exception  # type: ignore[misc]

