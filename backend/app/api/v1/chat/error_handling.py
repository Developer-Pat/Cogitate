"""
Error handling for chat streaming operations.

Provides centralized error handling with full context logging
and frontend error event generation.
"""

import json
import logging
import time
import traceback
from typing import Any, AsyncGenerator, Dict, Optional


from app.domain.chat.services import ChatService
from app.domain.providers.failure_statement import (
    EXA_DIAGNOSIS_OFFER,  # noqa: F401  (re-export — the chat path's diagnosis offer)
    PROVIDER_FAILURE_CATEGORIES,  # noqa: F401  (re-export — the statement's own category set)
    FailureSubject,
    failure_sentence_for,
    failure_sentence_for_subject,
    model_label,  # noqa: F401  (re-export — `model_subject`'s vocabulary; importers name it here)
    model_subject,  # noqa: F401  (re-export — `chat.router` imports it from here)
    provider_reason,  # noqa: F401  (re-export — the chat path's reason helper, unchanged importers)
    provider_reported,
)

from .logging_service import ChatLoggingService
from .context import ChatContext

logger = logging.getLogger(__name__)


async def handle_streaming_error(
    error: Exception,
    context: Optional[ChatContext],
    service: ChatService,
    logger_service: ChatLoggingService,
    start_time: float,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Handle streaming error with full context logging.

    Args:
        error: The exception that occurred
        context: Chat context (may be None if error occurred early)
        service: Chat service
        logger_service: Logging service
        start_time: Request start time
        provider: Provider name (override)
        model: Model name (override)

    Yields:
        SSE-formatted error events
    """
    # Build context dict for logging
    context_dict = build_error_context(
        error=error,
        context=context,
        start_time=start_time,
        provider=provider,
        model=model,
    )

    # Log error with full context
    if isinstance(error, ValueError):
        logger_service.log_value_error(
            error=error,
            session_id=context.session_id if context else None,
        )
    else:
        logger_service.log_error(
            error=error,
            context=context_dict,
        )

    # Build error event for frontend
    interpretation = (context_dict or {}).get('error_interpretation') or {}
    error_event = {
        'error': {
            'type': get_error_type(error),
            # `message` stays the provider's own text (a diagnostic), and the
            # HONEST SENTENCE now rides alongside it: the interpretation was
            # built for the log only, so the user met the raw traceback and had
            # nothing to act on.
            'message': str(error),
            'user_message': (
                f"{interpretation['summary']} — {interpretation['suggested_action']}"
                if interpretation.get('summary') else None
            ),
            'category': interpretation.get('category'),
            'error_class': type(error).__name__,
            'provider': context_dict.get('provider'),
            'model': context_dict.get('model'),
            'session_id': context_dict.get('session_id'),
        }
    }
    yield f"event: error\ndata: {json.dumps(error_event)}\n\n"

    # Log usage as failure
    await service._log_usage(
        provider=context_dict.get('provider', 'unknown'),
        model=context_dict.get('model', 'unknown'),
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        response_time_ms=int((time.time() - start_time) * 1000),
        success=False,
        session_id=context.session_id if context else None,
        agent_id=context.agent_id if context else None,
        error_message=f'{type(error).__name__}: {str(error)}'
    )


def extract_litellm_error_details(error: Exception) -> Dict[str, Any]:
    """
    Extract detailed information from LiteLLM errors.
    
    This captures provider-specific error details that help diagnose issues.
    
    Args:
        error: The exception to analyze
        
    Returns:
        Dictionary with detailed error information
    """
    details = {}
    
    # Check if this is a LiteLLM error
    litellm_attrs = [
        'llm_provider', 'model', 'status_code', 'code', 'type',
        'param', 'request_id', 'num_retries', 'max_retries',
        'litellm_debug_info'
    ]
    
    for attr in litellm_attrs:
        if hasattr(error, attr):
            try:
                value = getattr(error, attr)
                if value is not None:
                    details[attr] = value
            except Exception:
                pass
    
    # Extract response details
    if hasattr(error, 'response') and error.response is not None:
        try:
            response = error.response
            details['response_status'] = response.status_code
            details['response_reason'] = getattr(response, 'reason_phrase', None)
            
            # Try to read response body
            if hasattr(response, 'text'):
                details['response_body'] = response.text[:1000]  # Limit to 1000 chars
        except Exception:
            pass
    
    # Extract request details
    if hasattr(error, 'request') and error.request is not None:
        try:
            request = error.request
            details['request_method'] = getattr(request, 'method', None)
            details['request_url'] = str(getattr(request, 'url', None))
        except Exception:
            pass
    
    return details


def build_error_context(
    error: Exception,
    context: Optional[ChatContext],
    start_time: float,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build context dict for error logging.

    Args:
        error: The exception
        context: Chat context
        start_time: Request start time
        provider: Provider name override
        model: Model name override

    Returns:
        Context dict for logging
    """
    context_dict: Dict[str, Any] = {
        'session_id': context.session_id if context else None,
        'agent_id': context.agent_id if context else None,
        'agent_name': context.agent_name if context else None,
        'provider': provider or (context.provider if context else None),
        'model': model or (context.model if context else None),
        'error': str(error),
        'error_type': type(error).__name__,
        'error_class': type(error).__module__,
        'traceback': traceback.format_exc(),
        'elapsed_ms': round((time.time() - start_time) * 1000, 2),
        'messages_count': context.messages_count if context else 0,
        'tools_count': context.tools_count if context else 0,
    }
    
    # A MID-STREAM FALLBACK IS RECOGNISED BY ITS CLASS (2026-09-26), not by the
    # provider's payload: litellm raises it when a provider switches models
    # part-way through a stream, and it need carry none of the attributes the
    # block below reads — so it is checked BEFORE that block, or it would fall
    # through unclassified for exactly the case it exists to name.
    if 'midstreamfallback' in type(error).__name__.lower():
        context_dict['error_interpretation'] = {
            'category': 'mid_stream_fallback',
            'summary': 'The provider switched models part-way through the answer',
            'likely_cause': 'A provider-side fallback fired mid-stream (litellm MidStreamFallbackError)',
            # THE ACTION NEVER RECOMMENDS A MODEL (user, 2026-09-29): the app names the
            # offender and says it is not working; picking a replacement is the user's call.
            'suggested_action': 'Retry the turn',
            'is_user_error': False,
            'is_retryable': True,
        }

    # Extract LiteLLM-specific error details
    litellm_details = extract_litellm_error_details(error)
    if litellm_details:
        context_dict['litellm_details'] = litellm_details
        
        # Add interpretation hints
        raw_status_code = litellm_details.get('status_code') or litellm_details.get('code')
        # Normalize to int for safe comparison (LiteLLM may return string)
        try:
            status_code = int(raw_status_code) if raw_status_code is not None else None
        except (ValueError, TypeError):
            status_code = None
        error_type = litellm_details.get('type', '')
        error_type_l = (error_type or '').lower()
        # The provider's OWN words: the exception text plus whatever body the
        # response carried (OpenRouter puts its reason there).
        raw = f"{error} {litellm_details.get('response_body') or ''}".lower()

        # THE UPSTREAM IS DOWN FOR THIS ROUTE — checked BEFORE the status codes,
        # because a saturated upstream usually arrives as a 503 and the generic
        # server_error text ("Temporary provider issue") tells a user nothing
        # they can act on. OpenRouter reports `provider_unavailable` when every
        # upstream behind a route is busy, which on a `:free` route is routine:
        # nine of the eleven curated models are free.
        if ('provider_unavailable' in error_type_l or 'provider_unavailable' in raw
                or 'overloaded' in raw or 'upstream' in error_type_l):
            context_dict['error_interpretation'] = {
                'category': 'provider_unavailable',
                'summary': 'The upstream for this model is overloaded or unavailable',
                'likely_cause': 'Every upstream behind this route is saturated — routine on :free routes',
                'suggested_action': 'Retry shortly',
                'is_user_error': False,
                'is_retryable': True,
            }
        elif 'mid_stream' in error_type_l or 'fallback' in error_type_l:
            context_dict['error_interpretation'] = {
                'category': 'mid_stream_fallback',
                'summary': 'The provider switched models part-way through the answer',
                'likely_cause': 'A provider-side fallback fired mid-stream (litellm MidStreamFallbackError)',
                'suggested_action': 'Retry the turn',
                'is_user_error': False,
                'is_retryable': True,
            }
        elif status_code == 429 or 'rate_limit' in error_type.lower() or 'throttling' in error_type.lower():
            context_dict['error_interpretation'] = {
                'category': 'rate_limit',
                'summary': 'Provider rate limit exceeded',
                'likely_cause': 'Free tier quota exhausted or too many requests',
                'suggested_action': 'Wait and retry',
                'is_user_error': False,
                'is_retryable': True,
            }
        elif status_code == 401:
            context_dict['error_interpretation'] = {
                'category': 'authentication',
                'summary': 'Authentication failed',
                'likely_cause': 'Invalid or missing API key',
                'suggested_action': 'Check API key configuration',
                'is_user_error': True,
                'is_retryable': False,
            }
        elif status_code == 403:
            # A 403 IS NOT ALWAYS THE KEY: OpenRouter refuses some routes by
            # POLICY — "only available on agentic harnesses" — which no key or
            # permission change can fix, and which the permission wording sent
            # the user chasing the wrong thing.
            if ('only available' in raw or 'agentic harness' in raw
                    or 'policy' in raw or 'not available' in raw):
                context_dict['error_interpretation'] = {
                    'category': 'policy_refusal',
                    'summary': 'The provider refuses this model to this client',
                    'likely_cause': "The provider's own policy, not your key — e.g. a route reserved for other harnesses",
                    'suggested_action': 'Use a different model',
                    'is_user_error': False,
                    'is_retryable': False,
                }
            else:
                context_dict['error_interpretation'] = {
                    'category': 'permission',
                    'summary': 'Permission denied',
                    'likely_cause': 'API key lacks permission for this model',
                    'suggested_action': 'Check model access permissions',
                    'is_user_error': True,
                    'is_retryable': False,
                }
        elif status_code == 404:
            context_dict['error_interpretation'] = {
                'category': 'not_found',
                'summary': 'Model not found',
                'likely_cause': 'Model name incorrect or unavailable',
                'suggested_action': 'Verify model name and provider',
                'is_user_error': True,
                'is_retryable': False,
            }
        elif status_code and status_code >= 500:
            context_dict['error_interpretation'] = {
                'category': 'server_error',
                'summary': 'Provider server error',
                'likely_cause': 'Temporary provider issue',
                'suggested_action': 'Wait and retry',
                'is_user_error': False,
                'is_retryable': True,
            }
    
    return context_dict


# `model_label`, `model_subject`, `EXA_DIAGNOSIS_OFFER`, `provider_reason` and `provider_reported`
# MOVED to the DOMAIN (`app/domain/providers/failure_statement.py`) and are imported at the top of
# this module — phase 6 group 3 gave the wording a second consumer (the title service's auto path,
# which had no failure surface at all), and a domain module may not import from `api/`. They stay
# bound here so every existing import site is unchanged: `router.py` imports
# `failure_sentence`/`model_subject` from this module, and so does
# `tests/unit/test_failure_statement.py`.


def failure_sentence(context: Optional[ChatContext], reason: str) -> str:
    """A failure sentence that FINGERS THE LLM — for the failures the classifier does not cover.

    The fallback attempt itself can fail, time out, or come back with no choices; the old copy
    for those was "I apologize, but I encountered an error…", which names nothing and leaves the
    reader with no way to act. `reason` is a short clause; the name leads.

    The sentence has ONE home (the domain module imported above); this is the `ChatContext` façade
    over it, so the chat call sites keep reading as they always did.
    """
    return failure_sentence_for(
        context.model if context else None,
        context.provider if context else None,
        reason,
    )

# `PROVIDER_FAILURE_CATEGORIES` MOVED to the domain (`app/domain/providers/failure_statement.py`)
# with the wording it belongs to, and is imported at the top of this module — WHICH failures mention
# the fallback setting is a rule about the STATEMENT, not about the classifier that names them.


def fallback_configured(context: Optional[ChatContext]) -> bool:
    """Whether this agent has a provider fallback switched ON (the setting, not its chain)."""
    return bool(getattr(getattr(context, "agent", None), "fallback_enabled", False))


def build_failure_statement(
    error: Optional[Exception],
    context: Optional[ChatContext],
) -> Optional[str]:
    """The DEFINITIVE statement of where a failure is — `None` only when there is no error.

    THE POINT IS TO FINGER THE OFFENDER, not to diagnose it: the user has to be able to act,
    and acting needs the LLM and its provider named. A conclusive cause is explicitly NOT
    required — a classified failure carries its short summary, and an UNCLASSIFIED one carries
    the provider's own words, but either way the NAME is there, because that is the part the
    reader can change.

    IT NEVER RECOMMENDS A MODEL (user, 2026-09-29): it names the LLM and its provider, says the
    thing is not working, mentions the fallback setting where a fallback would have carried the
    turn, and offers Exa for the diagnosis. Which model to use instead is the reader's decision.

    The sentence itself lives in the DOMAIN (G4-F3, `failure_statement.py`): this builds the
    `FailureSubject` off the classifier and renders it, so the chat path, the title path and the
    workflow path share ONE wording in ONE place.
    """
    if error is None:
        return None

    context_dict = build_error_context(
        error=error,
        context=context,
        start_time=time.time(),
        provider=context.provider if context else None,
        model=context.model if context else None,
    )
    interpretation = (context_dict or {}).get('error_interpretation') or {}
    summary = (interpretation.get('summary') or '').strip()

    subject = FailureSubject(
        model=context.model if context else None,
        provider=context.provider if context else None,
        # A classified failure carries the classifier's short summary (written as a standalone
        # sentence, so it reads lower-cased mid-sentence); an unclassified one carries the
        # provider's own words, labelled as theirs. NEITHER is a diagnosis. The renderer
        # terminates the clause, so no full stop is appended here.
        reason=(
            f"{summary[0].lower()}{summary[1:]}"
            if summary
            else provider_reported(error)
        ),
        category=interpretation.get('category'),
    )
    # THE SETTING, NOT A SUGGESTION: the renderer adds the fallback note only where the model
    # itself failed (a category in PROVIDER_FAILURE_CATEGORIES) and the agent has none switched
    # on — the chat path is the caller that knows the agent, so it answers the question.
    return failure_sentence_for_subject(
        subject,
        fallback_configured=fallback_configured(context) if context is not None else True,
    )


def get_error_type(error: Exception) -> str:
    """
    Get error type string for frontend.

    Args:
        error: The exception

    Returns:
        Error type string
    """
    if isinstance(error, ValueError):
        return 'value_error'
    elif isinstance(error, TimeoutError):
        return 'timeout'
    elif isinstance(error, ConnectionError):
        return 'connection_error'
    elif isinstance(error, PermissionError):
        return 'permission_error'
    else:
        return 'streaming_exception'


async def handle_empty_response(
    context: ChatContext,
    service: ChatService,
    logger_service: ChatLoggingService,
    start_time: float,
    total_time_ms: float,
) -> AsyncGenerator[str, None]:
    """
    Handle empty response (no chunks received).

    Args:
        context: Chat context
        service: Chat service
        logger_service: Logging service
        start_time: Request start time
        total_time_ms: Total time elapsed

    Yields:
        SSE-formatted error events
    """
    logger_service.log_empty_response(
        context=context,
        total_time_ms=total_time_ms,
    )

    # Send error to frontend
    error_event = {
        'error': {
            'type': 'empty_response',
            'message': 'LLM returned no data - stream was empty',
            'provider': context.provider,
            'model': context.model,
            'session_id': context.session_id,
        }
    }
    yield f"event: error\ndata: {json.dumps(error_event)}\n\n"

    # Log usage as failure
    await service._log_usage(
        provider=context.provider,
        model=context.model,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        response_time_ms=int(total_time_ms),
        success=False,
        session_id=context.session_id,
        agent_id=context.agent_id,
        error_message='empty_response'
    )


# THE EMPTY-COMPLETION NOTICE (2026-09-10, the user's "she died again,
# no warning or messages"): the finalize guard refuses to persist an
# empty assistant message — correctly — but the refusal used to be
# SILENT, so the user saw a turn that produced nothing at all. This is
# the minimal, factual copy surfaced when that happens: what happened,
# and the usual fix. Keep it minimal — no diagnostics, no blame.
EMPTY_COMPLETION_NOTICE = (
    "No answer was produced this turn. "
    "Starting a new session usually fixes this when the conversation history is the cause."
)


def build_empty_completion_event(context: ChatContext) -> str:
    """Build the SSE error frame for a refused empty completion.

    THE CONVENTION (F1, 2026-08-03, see handle_streaming_error): a
    user-visible stream failure rides `event: error` +
    `data: {"error": {type, message, provider, model, session_id}}` —
    the frontend already routes that shape to a toast + onStreamError.
    The empty-completion guard uses it so a discarded response is
    never silent.

    Args:
        context: Chat context (provider/model/session)

    Returns:
        SSE-formatted error frame (str)
    """
    error_event = {
        'error': {
            'type': 'empty_completion',
            'message': EMPTY_COMPLETION_NOTICE,
            'provider': context.provider,
            'model': context.model,
            'session_id': context.session_id,
        }
    }
    return f"event: error\ndata: {json.dumps(error_event)}\n\n"


def build_limit_stop_event(context: ChatContext, message: str) -> str:
    """Build the SSE error frame for a turn STOPPED by a hard limit (D.3, F2).

    Same convention as the empty-completion guard above: `event: error` +
    `data: {"error": {type, message, provider, model, session_id}}`, which the
    frontend routes to a toast + `onStreamError` and treats as the end of the
    stream. The partial answer has already been streamed; the finalize that
    follows SAVES it (D7 (a) — never a lost turn).

    The message is built by `limits.stop_message` (the limit's reason + what
    happened to the turn + "say 'continue'"), so the copy cannot drift from the
    note the row carries.

    Args:
        context: Chat context (provider/model/session)
        message: The user-facing reason, from `limits.stop_message`

    Returns:
        SSE-formatted error frame (str)
    """
    error_event = {
        'error': {
            'type': 'limit_stop',
            'message': message,
            'provider': context.provider,
            'model': context.model,
            'session_id': context.session_id,
        }
    }
    return f"event: error\ndata: {json.dumps(error_event)}\n\n"


def build_refusal_event(context: ChatContext, message: str) -> str:
    """Build the SSE error frame for a turn REFUSED before the pipeline started (G5-F3/F4).

    Same convention as the empty-completion guard and the limit stop (`event: error` +
    `data: {"error": {type, message, provider, model, session_id}}`), which is the whole point of
    the ruled transport: the frontend already routes that shape to a toast + `onStreamError`, so a
    refusal needs NO new frontend path and reads exactly like the failed turn it stands in for.

    `type` is its own value (`capability_unavailable`) so a consumer can tell a refusal from a
    failure of the provider, and so the log says which one happened.

    Args:
        context: Chat context (provider/model/session)
        message: The refusal sentence, from `domain.providers.refusal.refusal_statement`

    Returns:
        SSE-formatted error frame (str)
    """
    error_event = {
        'error': {
            'type': 'capability_unavailable',
            'message': message,
            'provider': context.provider,
            'model': context.model,
            'session_id': context.session_id,
        }
    }
    return f"event: error\ndata: {json.dumps(error_event)}\n\n"


async def handle_no_content(
    context: ChatContext,
    service: ChatService,
    logger_service: ChatLoggingService,
    start_time: float,
    chunk_count: int,
    invalid_chunks: int,
    total_time_ms: float,
) -> AsyncGenerator[str, None]:
    """
    Handle no content response (chunks received but no content/tool calls).

    Args:
        context: Chat context
        service: Chat service
        logger_service: Logging service
        start_time: Request start time
        chunk_count: Number of chunks received
        invalid_chunks: Number of invalid chunks
        total_time_ms: Total time elapsed

    Yields:
        SSE-formatted error events
    """
    logger_service.log_no_content(
        context=context,
        chunk_count=chunk_count,
        invalid_chunks=invalid_chunks,
        total_time_ms=total_time_ms,
    )

    # Send error to frontend
    error_event = {
        'error': {
            'type': 'no_content',
            'message': 'LLM returned no content or tool calls',
            'chunks_received': chunk_count,
            'invalid_chunks': invalid_chunks,
            'session_id': context.session_id,
        }
    }
    yield f"event: error\ndata: {json.dumps(error_event)}\n\n"

    # Log usage as failure
    await service._log_usage(
        provider=context.provider,
        model=context.model,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        response_time_ms=int(total_time_ms),
        success=False,
        session_id=context.session_id,
        agent_id=context.agent_id,
        error_message='no_content'
    )
