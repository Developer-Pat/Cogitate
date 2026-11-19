"""
Finalization logic for chat operations.

Handles response finalization, title generation,
usage logging, and metrics calculation.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.infrastructure.database.models import ChatMessage, ChatSession
from app.domain.chat.services import ChatService
from app.domain.title.services import get_title_service

from .schemas import StreamResult
from app.domain.tools.execution_service import ToolExecutionResult
from app.services.cognitive_pipeline.turn_state import TurnState
from app.services.cognitive_pipeline.reasoning_support import reasoning_replay_field
from .logging_service import ChatLoggingService
from .error_handling import EMPTY_COMPLETION_NOTICE
from .context import ChatContext

logger = logging.getLogger(__name__)


class ChatRequestModel:
    """Forward reference to chat request model."""
    pass


async def finalize_response(
    context: ChatContext,
    result: StreamResult,
    tool_results: List[ToolExecutionResult],
    request: Any,
    service: ChatService,
    db: AsyncSession,
    logger_service: ChatLoggingService,
    start_time: float,
    final_content: str,
    turn_state: Optional[TurnState] = None,
    nothing_said: Optional[str] = None,
    tool_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Finalize the chat response.

    Args:
        context: Chat context
        result: Stream result
        tool_results: Results from tool execution
        request: Original chat request
        service: Chat service
        db: Database session
        logger_service: Logging service
        start_time: Request start time
        final_content: Final response content
        turn_state: The turn's account (Phase D.1) — its crossed soft lines
            (D.2) ride the done frame and the saved row as the note on the
            message, the same way the truncation flag does
        nothing_said: The sentence to persist INSTEAD of an empty message, when
            the caller knows why the turn produced no answer (a hard plug that
            fired before any text, or a tool loop that used every round). The
            empty-message guard then does not fire — the turn is not silent, it
            explains itself.
        tool_summary: The turn's tool numbers (the tracker's summary — attempts,
            failures by class, refusals). It rides the row's meta AND the done
            frame's metadata, so the tool story survives a reload instead of living
            only in the log (the tool-reliability arc, F5). Read by the ROW too for
            the same reason `truncated` is: a reloaded turn must still be able to
            say what its tools did.

    Returns:
        Metadata dict for final chunk
    """
    # Auto-generate session title if requested and this is the first message.
    # Run as a background task so it never blocks the SSE "done" event.
    # THE PLACEHOLDER CLASS (2026-09-09, B1): any "New Session ..."
    # shape counts — the temp-commit fallback titles sessions
    # "New Session <timestamp>" and the exact-match only stranded
    # them, permanently untitled.
    _title = context.session.title
    if request.generate_title and (
        _title is None
        or _title == "Untitled"
        or (isinstance(_title, str) and _title.startswith("New Session"))
    ):
        asyncio.create_task(
            _generate_title_background(
                session_id=context.session.id,
                first_message=request.message,
                logger_service=logger_service,
            )
        )

    # THE TURN THAT SAID NOTHING (2026-09-23). When the caller KNOWS why the turn
    # produced no answer — a hard plug fired before any text arrived, or the tool
    # loop used every round it had — the turn SAYS SO in the guard's tone instead
    # of vanishing. This is the arc's own promise ("never silence, never a lost
    # turn") applied to its own paths: the live verification produced two turns
    # that ended with nothing (session 125: the loop's cap; session 127: a plug
    # with an empty partial), and both left the transcript EMPTY — the toast said
    # something, the conversation did not, and a reload showed no turn at all.
    #
    # The sentence becomes the message, so everything downstream (the row, the
    # done frame, the note) works unchanged, and the empty-message guard below
    # does not fire: there IS a message. The guard still protects the empty
    # completion nobody can explain.
    said_instead = False
    if nothing_said and not (final_content or "").strip():
        final_content = nothing_said
        said_instead = True
        logger.warning(
            "NOTHING TO SHOW session=%s model=%s provider=%s — the turn says WHY "
            "instead of leaving an empty turn: %s",
            context.session.id, context.model, context.provider, nothing_said,
        )

    # Calculate token counts if not provided by LiteLLM
    prompt_tokens = result.prompt_tokens
    completion_tokens = result.completion_tokens

    if prompt_tokens == 0:
        prompt_tokens = service._estimate_tokens("".join(msg.get("content", "") for msg in context.messages))
    if completion_tokens == 0:
        completion_tokens = service._estimate_tokens(final_content)

    # Calculate timing metrics
    end_time = time.time()
    total_time_ms = (end_time - start_time) * 1000
    tokens_per_second = completion_tokens / (end_time - start_time) if (end_time - start_time) > 0 else 0

    # THE SOFT-LIMIT NOTE (2026-09-22, Phase D.2): what this turn crossed, with
    # the sentence the bubble shows. It rides the row's meta AND the done frame's
    # metadata, so a reloaded turn still says it — the same shape as the
    # truncation flag above it. Computed BEFORE the empty guard, because a turn
    # that crossed a line and then produced nothing is exactly the turn someone
    # needs to read the note from.
    limit_meta: Dict[str, Any] = {}
    if turn_state is not None and getattr(turn_state, "crossings", None):
        limit_meta = {
            "limits": list(turn_state.crossings),
            "limit_notice": turn_state.notice_text(),
        }

    # THE SENTENCE THAT STOOD IN FOR AN ANSWER (2026-09-23): the row and the frame
    # both say the message is the SYSTEM's sentence about the turn, not the
    # model's answer — so a reader (or a later audit) never mistakes it for
    # output the agent produced.
    say_meta: Dict[str, Any] = {"stopped_without_answer": True} if said_instead else {}

    # THE TOOL NUMBERS (the tool-reliability arc, F5): the tracker's summary rides
    # the row's meta and the done frame's `metadata` — where the frontend already
    # reads (`parsed.metadata`) — instead of the frame's TOP LEVEL, where it used to
    # sit with no reader at all and never reached the row.
    tool_meta: Dict[str, Any] = (
        {"tool_call_summary": tool_summary} if tool_summary else {}
    )

    # THE BUDGET THE WIRE ACTUALLY CARRIED (G-A ii). The declaration is what an agent
    # WOULD send; this is what this turn DID — {sent, declared, reason, path} of the
    # turn's last request, read from the turn's own account. It rides the row's meta
    # and the done frame's `metadata` (the `tool_call_summary` shape) because the
    # effective-budget line it comes from lived ONLY in the log, and the log rotates:
    # a turn could not answer "what did you send?" a day later. One key, so the
    # reload's whitelist stays one entry.
    budget_meta: Dict[str, Any] = (
        {"budget": turn_state.budget}
        if turn_state is not None and getattr(turn_state, "budget", None)
        else {}
    )

    # THE EMPTY-MESSAGE GUARD (2026-09-02, the Bob empty-bubble bug):
    # an EMPTY assistant response is NEVER persisted as a finished
    # message — the tool loop now retries empty completions once and
    # falls back to the visible error text, but this guard is the
    # last line: an empty save would replay as a phantom "Bob said
    # nothing" bubble. Log the refusal loudly (session/model/provider)
    # so the failure is trackable, and skip the DB row.
    if not (final_content or "").strip():
        logger.error(
            "EMPTY-MESSAGE GUARD: refusing to persist an empty assistant "
            "message session=%s model=%s provider=%s elapsed_ms=%.0f — "
            "the empty completion was already retried/errored upstream",
            context.session.id, context.model, context.provider,
            (time.time() - start_time) * 1000,
        )
        return {
            "done": True,
            "session_id": context.session.id,
            # THE EMPTY-GUARD NOTICE (2026-09-10, the user's "she died
            # again, no warning or messages"): refusing the empty row
            # is correct — refusing it SILENTLY was the bug. The
            # machine-readable signal (`empty_guard` + `notice`) rides
            # the payload the router turns into the user-visible
            # `event: error` frame (see build_empty_completion_event).
            "empty_guard": True,
            "notice": EMPTY_COMPLETION_NOTICE,
            "metadata": {
                "tokenCount": 0,
                "totalTimeMs": round((time.time() - start_time) * 1000, 2),
                "tokensPerSecond": 0,
                "model": context.model.split('/')[-1] if '/' in context.model else context.model,
                "provider": context.provider,
                "empty_guard": True,
                "notice": EMPTY_COMPLETION_NOTICE,
                "reasoning": getattr(result, "accumulated_reasoning", "") or "",
                **limit_meta,
                **tool_meta,
            },
        }

    # THE TRUNCATION FLAG (2026-09-22, Bob's cut-off forecast reports):
    # finish_reason="length" is the provider saying the answer was cut
    # at the output budget. It used to be DROPPED — a cut answer was
    # saved, streamed and rendered as a complete one, and the only
    # thing that ever noticed was the frontend's token estimate
    # (StreamingService "Response truncated (token count fallback)"),
    # which fires only when the local estimate reaches the cap. The
    # flag now rides BOTH the done frame (the frontend's truncation
    # notice reads metadata.truncated) and the saved row (so a
    # reloaded turn still says it was cut).
    truncated = getattr(result, "finish_reason", "") == "length"
    truncation_meta: Dict[str, Any] = {}
    if truncated:
        logger.warning(
            "OUTPUT TRUNCATED session=%s model=%s provider=%s content=%d chars "
            "— finish_reason=length: the provider cut the answer at the output "
            "budget (max_tokens); the turn is saved and reported as truncated",
            context.session.id, context.model, context.provider, len(final_content),
        )
        truncation_meta = {"truncated": True, "truncationReason": "max_tokens"}

    # Save assistant message to database with metadata
    # THE THINKING SEGREGATION (2026-08-24): the meta column carries
    # the reasoning + the metrics — the Thinking fold survives the
    # reload (the column added 2026-08-24; the meta attr maps to the
    # DB "metadata" column — "metadata" is reserved in Declarative).
    assistant_message = ChatMessage(
        session_id=context.session.id,
        role="assistant",
        content=final_content,
        model=context.model,
        provider=context.provider,
        token_count=completion_tokens,
        total_time_ms=total_time_ms,
        tokens_per_second=tokens_per_second,
        meta={
            "reasoning": getattr(result, "accumulated_reasoning", "") or "",
            "model": context.model.split('/')[-1] if '/' in context.model else context.model,
            "provider": context.provider,
            **truncation_meta,
            **limit_meta,
            **say_meta,
            **tool_meta,
            **budget_meta,
        },
    )
    db.add(assistant_message)
    await db.flush()

    # Create metadata for final chunk
    metadata = {
        "done": True,
        "session_id": context.session.id,
        "metadata": {
            "tokenCount": completion_tokens,
            "totalTimeMs": round(total_time_ms, 2),
            "tokensPerSecond": round(tokens_per_second, 2),
            "model": context.model.split('/')[-1] if '/' in context.model else context.model,
            "provider": context.provider,
            # THE THINKING SEGREGATION (2026-08-24): the final
            # metadata carries the accumulated reasoning — the
            # frontend's Thinking fold survives the reload.
            "reasoning": getattr(result, "accumulated_reasoning", "") or "",
            # THE TRUNCATION FLAG (2026-09-22): the done frame tells the
            # UI the answer was cut at the output budget — the frontend's
            # truncation notice reads exactly this field.
            **truncation_meta,
            # THE SOFT-LIMIT NOTE (Phase D.2): the crossed soft lines and the
            # sentence the bubble shows (the frontend carries `parsed.metadata`
            # onto the message, so nothing else has to move for it to appear).
            **limit_meta,
            # THE SENTENCE THAT STOOD IN FOR AN ANSWER (2026-09-23): the frame
            # says the same thing the row does — the message is the system's
            # sentence about the turn, not the model's output.
            **say_meta,
            # THE TURN'S TOOL NUMBERS (the tool-reliability arc, F5): the same
            # summary the row carries, in the place the frontend already reads.
            **tool_meta,
            # THE BUDGET THE WIRE CARRIED (G-A ii): the same object the row keeps —
            # so the number the UI compares an answer against is the server's own,
            # not the client's arithmetic over the declaration.
            **budget_meta,
        }
    }

    # Log usage with real token counts
    await service._log_usage(
        provider=context.provider,
        model=context.model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        response_time_ms=int(total_time_ms),
        success=True,
        session_id=context.session_id,
        agent_id=context.agent_id,
    )

    # THE SAME BOUNDARY, at the turn's end: the answer's row and the turn's
    # usage become durable HERE — before the done frame goes out — rather than
    # at the response's teardown, where a client that goes away in between would
    # have the user's answer rolled back under them.
    await db.commit()

    logger_service.log_final_response(
        session_id=context.session.id,
        content_length=len(final_content)
    )

    return metadata


async def _generate_title_background(
    session_id: int,
    first_message: str,
    logger_service: ChatLoggingService,
) -> None:
    """
    Run title generation in a background task with its own database session.

    This is intentionally decoupled from the SSE request session so that it
    can safely commit after the streaming response has already completed.
    """
    try:
        async with AsyncSessionLocal() as bg_db:
            result = await bg_db.execute(
                select(ChatSession).where(ChatSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            if not session:
                logger.warning(f"Title background task: session {session_id} not found")
                return
            await generate_title_if_needed(
                session=session,
                first_message=first_message,
                db=bg_db,
                logger_service=logger_service,
            )
            await bg_db.commit()
    except Exception as e:
        logger.error(
            f"Title background task failed for session {session_id}: {e}",
            exc_info=True,
        )


async def generate_title_if_needed(
    session: ChatSession,
    first_message: str,
    db: AsyncSession,
    logger_service: ChatLoggingService,
) -> Optional[str]:
    """
    Generate session title from first message.

    Args:
        session: Chat session
        first_message: First user message
        db: Database session
        logger_service: Logging service

    Returns:
        Generated title or None
    """
    try:
        # Get title service instance
        title_service = get_title_service()

        # Prepare messages for title generation
        title_messages = [
            {"role": "user", "content": first_message}
        ]

        # Generate title using dedicated TitleService
        # `notify_failure=True` — THIS is the path whose failure had no surface (phase 6, group 3):
        # the background task is decoupled from the stream, so nothing else can tell the user. The
        # manual endpoint leaves it False (its 500 is the surface).
        generated_title = await title_service.generate_title(
            messages=title_messages,
            user_enabled=True,
            db=db,
            notify_failure=True,
        )

        if generated_title:
            # Update session title in database
            session.title = generated_title
            session.updated_at = datetime.now()
            await db.flush()

            logger_service.log_title_generation(
                session_id=session.id,
                title=generated_title
            )

            return generated_title
        else:
            logger.warning("Title generation returned None")
            return None

    except Exception as title_err:
        logger_service.log_title_generation_failed(
            session_id=session.id,
            error=title_err
        )
        return None


def build_tool_messages(
    accumulated_content: str,
    tool_calls_to_execute: List[Dict[str, Any]],
    tool_results: List[ToolExecutionResult],
    accumulated_reasoning: str = "",
) -> List[Dict[str, Any]]:
    """
    Build messages array with tool results for next iteration.

    Args:
        accumulated_content: Accumulated content from streaming
        tool_calls_to_execute: Tool calls to include
        tool_results: Results from tool execution
        accumulated_reasoning: The thinking this iteration produced

    Returns:
        Messages array for LLM API
    """
    assistant_message: Dict[str, Any] = {
        "role": "assistant",
        "content": accumulated_content if accumulated_content else None,
        "tool_calls": [
            {
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["name"],
                    "arguments": tc["arguments"]
                }
            }
            for tc in tool_calls_to_execute
        ] if tool_calls_to_execute else None
    }

    # THE REASONING REPLAY (2026-09-10, the poisoned-session fix): a
    # thinking-mode API wants the turn's reasoning back on the FOLLOW-UP
    # request too — a tool round trip is still a replayed assistant
    # message. Without it DeepSeek 400s on the iteration right after
    # the tool calls and the turn dies mid-investigation (same 400,
    # same empty completion). Attached only when this iteration
    # actually produced reasoning.
    assistant_message.update(
        reasoning_replay_field("", accumulated_reasoning)
    )

    return [assistant_message] + [result.to_message_dict() for result in tool_results]
