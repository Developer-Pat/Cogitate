"""

Chat API endpoints.



Provides REST API for chat operations including streaming.

"""



import json

import logging

import time

from datetime import datetime

from pathlib import Path

from typing import Annotated, AsyncGenerator, Any, Callable, Dict, List, Optional, Tuple



from fastapi import APIRouter, Depends, HTTPException, status

from fastapi.responses import StreamingResponse

from pydantic import BaseModel, Field

from sqlalchemy.ext.asyncio import AsyncSession



from app.core.database import get_db_session

from app.core.dependencies import get_db

from app.domain.chat.services import ChatService



from .schemas import StreamResult, StreamTiming


from app.domain.tools.execution_service import ToolExecutionResult

from app.domain.tools.llm_schema import tool_to_llm_schema

from .logging_service import ChatLoggingService

from .context import prepare_chat_context, build_llm_request, ChatContext

from .tool_execution import execute_tool_calls

from .finalization import finalize_response, build_tool_messages

from app.services.cognitive_pipeline.memory_manager import create_default_registry as create_default_memory_registry

from app.services.cognitive_pipeline.reasoning_support import reasoning_replay_field

from app.services.cognitive_pipeline.output_budget import (
    PATH_DEFAULT,
    PATH_DEEP,
    PATH_FAST,
    PATH_PASS1,
    apply_output_budget,
    declared_output_budget,
    estimate_prompt_tokens,
)

from .error_handling import (
    handle_streaming_error, build_empty_completion_event, build_limit_stop_event,
    build_failure_statement, failure_sentence, model_subject, build_refusal_event,
)

from .tool_call_tracker import ToolCallTracker

from app.services.cognitive_pipeline.turn_state import (
    FALLBACK_PATH,
    RETRY_PATH,
    TurnState,
    report_turn_account,
    response_usage,
)

from app.services.cognitive_pipeline.limits import (
    CONTINUE_SENTENCE,
    STOP_ABORT,
    STOP_FINISH,
    call_soft_limits,
    check_limits,
    hard_turn_limits,
    inactive_limits_note,
    limits_in_force,
    nearly_complete,
    stop_message,
    turn_soft_limits,
    turn_stopped_line,
)

# THE TURN'S TWEAK POINTS (gap L, Stage 1) — read as calls from ONE home, the same way
# `Paths` resolves paths: what a number IS can change behind the call without a call site
# moving. The loop's rounds lived as two bare literals in this file until now.
from app.services.cognitive_pipeline import turn_config

from app.domain.messaging.services import publish, publish_warning

from .chat_events import (

    build_context_built,

    build_executor_started,

    build_executor_completed,

    build_memory_updated,

    build_response_formatted,

    build_trace_complete,

    sse_from_builder,

)

from app.services.cognitive_pipeline import (

    CognitivePipeline,

    PipelineConfig,

    CognitiveResult,

    CognitiveTrace,

    ComponentTrace,

)



logger = logging.getLogger(__name__)

def _populate_tool_calls_metric(
    cognitive_result: "CognitiveResult",
    tool_call_tracker: Optional["ToolCallTracker"] = None,
    executor_trace: Optional["ComponentTrace"] = None,
) -> None:
    """Fill metrics.tool_calls from REAL sources (2026-08-14).

    The cognitive pipeline itself never sets tool_calls (its
    executors call acompletion without tools=). The chat/stream
    path DOES execute tools — the ToolCallTracker counts every
    executed call. Lift that number into the persisted metric so
    the Debugging trace view stops showing 0 for tool-using
    conversations. Fallback: executor-trace tool_iterations (when
    no tracker exists — delegate/stub paths).
    """
    if not cognitive_result.metrics:
        return
    if tool_call_tracker:
        summary = tool_call_tracker.get_summary()
        cognitive_result.metrics.tool_calls = int(summary.get("total_calls") or 0)
    elif executor_trace is not None:
        cognitive_result.metrics.tool_calls = int(
            executor_trace.metadata.get("tool_iterations") or 0
        )


def _apply_output_budget(
    context: "ChatContext",
    request_kwargs: Dict[str, Any],
    path: str,
) -> None:
    """Decide this request's output budget, write it, and log why (C.1).

    The request log line used to print the agent's DECLARED budget
    (`parameters={'max_tokens': 2000}`) while a different number went on the
    wire — a hybrid pass 1 sent 1024. Every budget question asked from the log
    therefore started from a false number, which is what started the arc.

    THE DEEP PASS'S BUDGET gets the same treatment: `_apply_output_budget` is the
    one funnel, and it now carries the driver's window (E.1) and the prompt's size
    (E.2) — so a budget that cannot fit beside the prompt is clamped here as well.
    """
    budget_sent, reason = apply_output_budget(
        request_kwargs,
        context.agent,
        context.model,
        path,
        override=getattr(getattr(context, "runtime_config", None), "max_tokens", None),
        # THE WINDOW (E.1) — read once in `prepare_chat_context`; `None` when the
        # driver is unrecorded, and then nothing is clamped.
        window=getattr(getattr(context, "model_window", None), "value", None),
        # THE DRIVER'S THINKING SIGNAL (F.3) — read in the same place, from the
        # provider's claim first and our curated label second. `None` (a caller with
        # no database read) leaves the agent's own declaration and then the name
        # pattern to speak.
        thinking=getattr(context, "model_thinking", None),
        # THE PROMPT (E.2) — measured from the messages actually about to be sent
        # (tools included: their schemas are the part of a prompt that grows without
        # the conversation growing). An absent estimate means no clamp.
        prompt_tokens=estimate_prompt_tokens(
            request_kwargs.get("messages"), request_kwargs.get("tools")
        ),
        session_id=getattr(context, "session_id", None),
    )

    # THE OBSERVATION (G-A ii). `apply_output_budget` RETURNS the number it wrote and
    # the reason it wrote it — so the turn's account can hold what the wire carried,
    # recorded at the ONE funnel every path goes through. The row's number and the
    # sent number therefore cannot disagree: they are the same return value. The
    # declared value is the agent's own (the spec), named for the log's `declared=`.
    state = getattr(context, "turn_state", None)
    if state is not None and hasattr(state, "observe_budget"):
        state.observe_budget(
            budget_sent,
            declared_output_budget(getattr(context, "agent", None)),
            reason,
            path,
        )


def _output_budget_path(executor_strategy: Optional[str]) -> str:
    """The run path a turn's budget is resolved for (the executor strategies)."""
    if executor_strategy == "fast":
        return PATH_FAST
    if executor_strategy == "hybrid":
        return PATH_PASS1
    return PATH_DEFAULT


# ---------------------------------------------------------------------------
# THE TURN'S ACCOUNT (Phase D.1) — every provider call in the turn is counted
# ---------------------------------------------------------------------------
# `turn_state.TurnState` lives on the chat context beside the tool tracker; these
# helpers are the call sites' only way in. A provider call is counted BEFORE it is
# made (an attempt that fails or times out was still a call this turn made), and
# its tokens are added when it answers — measured when the provider reports usage,
# marked as estimated when it does not. `tests/unit/test_turn_accounting.py` reads
# this file as SOURCE and refuses a provider call that is not accounted here (the
# shape of the C.1 guard).


def _turn_state_of(context: Any) -> Optional["TurnState"]:
    """This turn's account, or None — the delegate paths and test stubs have none."""
    return getattr(context, "turn_state", None)


def _account_provider_call(context: Any, path: str = "") -> None:
    """Count one provider call in the turn's account, before it is made."""
    state = _turn_state_of(context)
    if state is not None:
        state.observe_provider_call(path)


def _account_tools_offered(context: Any, tools_sent: Any) -> None:
    """Count this call as one that OFFERED tools — the turn's denominator (F1).

    Called with the request's own `tools`, so the count describes what went on the
    wire. A call with no tools (the answer pass withholds them) counts nothing,
    which is the point: it is not a call where the model declined, it is a call
    where there was nothing to decline.
    """
    state = _turn_state_of(context)
    if state is not None:
        state.observe_tools_offered(tools_sent)


def _capture_gathered(context: Any, tool_results: Any) -> int:
    """Record what a turn's tools actually GATHERED into the run's notebook (2026-10-13).

    THE AUTOMATIC HALF of the notebook. The four notebook tools let an agent keep a record,
    and measured, it does not: the first live run of those tools fetched four pages (127,854
    characters) and wrote nothing — the same shape as `update-state`, 6 calls in 120 turns.
    So the fetch records itself here, at the boundary where the turn's request is known,
    which is also the only place that can name the assignment ("Check the local headlines").

    Cheap and inert: results that are not fetches are skipped, a capture that fails is logged
    and the turn carries on, and nothing is recorded when the agent has no workspace. Returns
    the number captured, for the one log line.
    """
    from app.domain.agents.assignments import capture_fetch, fetch_facts

    workspace_key = getattr(getattr(context, "agent", None), "workspace_key", None)
    if not workspace_key or not tool_results:
        return 0
    goal = getattr(context, "turn_goal", "") or ""
    captured = 0
    for result in tool_results:
        if not getattr(result, "success", False):
            continue
        facts = fetch_facts(getattr(result, "result", None))
        if not facts:
            continue
        if capture_fetch(workspace_key, goal, **facts):
            captured += 1
    if captured:
        logger.info(
            "📓 NOTEBOOK: captured %d fetch(es) for session=%s — %s",
            captured,
            getattr(context, "session_id", None),
            (goal or "(no goal)")[:70],
        )
    return captured


def _retry_observer(context: Any) -> Callable[[int], None]:
    """The retry wrapper's attempt callback: a RETRY is a provider call too (F2).

    The first attempt is the call the site itself counted; only the wrapper's
    later attempts are added here (the `retry` label), so the total reads as "how
    often this turn reached a provider" without counting one call twice.
    """
    def observe(attempt: int) -> None:
        if attempt:
            _account_provider_call(context, RETRY_PATH)
    return observe


def _prompt_text(messages: Any) -> str:
    """The prompt text as the app estimates it — the messages' contents joined."""
    try:
        return "".join(str(m.get("content") or "") for m in (messages or []))
    except Exception:
        return ""


def _estimate_text_tokens(service: Any, text: Any) -> int:
    """The service's own token estimate, best-effort (finalize estimates this way)."""
    try:
        return int(service._estimate_tokens(str(text or "")))
    except Exception:
        return 0


def _account_usage(
    context: Any,
    service: Any,
    *,
    prompt: str,
    content: str,
    usage: Optional[Tuple[int, int]] = None,
) -> None:
    """Add one call's tokens to the turn's account — or its estimate, marked as one.

    `usage` is what the provider reported, or None when it reported nothing; the
    None case is the app's own estimate, flagged so the account line can say
    `tokens=estimated` rather than presenting a guess as a measurement.
    """
    state = _turn_state_of(context)
    if state is None:
        return
    if usage is not None:
        state.observe_usage(usage[0], usage[1])
        return
    state.observe_usage(
        _estimate_text_tokens(service, prompt),
        _estimate_text_tokens(service, content),
        reported=False,
    )


def _measured_composition(context: Any) -> Optional[str]:
    """The measured composition of the prompt this call carried, as a short phrase — or ``None``.

    The input soft's note used to describe only the crossing ("history is being dropped"); its
    first version described a *cause* it had never measured, which is what opened this arc. The
    sentence now carries the parts — system · history · tool results · tool schemas · replayed
    reasoning — measured here from the same two things the request sends: the messages and the
    schemas on the context (`llm_tools`, the list that travels in ``tools=[...]``).

    Returns ``None`` rather than raising: a note that cannot measure its own prompt is still a note,
    and the sentence has a form for that case.
    """
    try:
        from app.services.cognitive_pipeline.prompt_accounting import (
            account_prompt,
            describe_account,
        )

        messages = getattr(context, "messages", None)
        if not messages:
            return None
        return describe_account(
            account_prompt(messages, tools=getattr(context, "llm_tools", None))
        )
    except Exception:  # noqa: BLE001 — bookkeeping must never break the warning it serves
        logger.debug("prompt composition unavailable for the limit note", exc_info=True)
        return None


def _check_turn_limits(
    context: Any,
    *,
    stage: str,
    call_tokens: Optional[int] = None,
    call_budget: Optional[int] = None,
    call_prompt_tokens: Optional[int] = None,
) -> Optional[Any]:
    """Judge the turn's lines — tell the soft ones, RETURN the hard one (D.2/D.3).

    Called at the boundaries where the numbers are freshest: after each streamed
    call (the call's own tokens against its budget, and the account's totals
    against the turn's lines), after the deep pass's stream, and once at the
    turn's end so the note on the message reflects the final state.

    The judge writes the log line (`⚠️ LIMIT SOFT …` / `🚫 LIMIT HARD STOP …`,
    `check_limits`). This only decides whether the USER is also told about a soft
    crossing — once per threshold per turn (F2: a 5-iteration turn must not toast
    five times) — and keeps it on the account, where the message's note reads it.

    **Returns the HARD verdict when a hard line is breached**, so the caller can
    do something about it (D.3's plug, `_stop_turn`). A turn that already hit its
    plug is not judged again — the first stop is the one the turn acted on.
    Nothing else here may stop the turn: an exception in the check is logged and
    swallowed, because a broken limit must never break a turn.
    """
    state = _turn_state_of(context)
    if state is None:
        return None
    try:
        # The tool count is the tracker's, mirrored before the judgement (one
        # owner per number — D.1's rule 1).
        state.observe_tool_calls(getattr(context, "tool_call_tracker", None))
        # THE CALL'S OWN STATE (D.2's rule, extended by E.6): the output soft is
        # judged against THIS call's tokens, and the input soft against THIS call's
        # prompt — never the turn's accumulated totals, which would fire on the
        # second call of every multi-call turn. A quantity the provider did not
        # report is left OUT of the state, and `check_limits` skips what it cannot
        # measure rather than reading it as a breach.
        call_state: Dict[str, Any] = {"output_tokens": call_tokens or 0}
        if call_prompt_tokens is not None:
            call_state["input_tokens"] = call_prompt_tokens
        # THE MEASURED COMPOSITION (D4). The note the user reads has to name the parts of the prompt
        # that crossed, and this is the one place where both halves are in hand — the messages this
        # call carried and the schemas it sent. Measuring is bookkeeping: if it fails, the sentence
        # falls back to stating what the budget counts and the crossing still warns.
        composition = _measured_composition(context)
        verdicts = [
            check_limits(state, turn_soft_limits()),
            check_limits(
                call_state,
                call_soft_limits(
                    call_budget,
                    input_budget=getattr(context, "input_budget", None),
                    composition=composition,
                ),
            ),
        ]
        for verdict in verdicts:
            if not verdict.warned or verdict.limit is None:
                continue
            if state.record_soft(verdict):
                publish_warning(
                    "This turn is running unusually",
                    verdict.reason,
                    kind="turn-soft-limit",
                )
                logger.warning(
                    "⚖️  TURN LIMIT told to the user at stage=%s key=%s value=%s "
                    "threshold=%s",
                    stage, verdict.limit.key, verdict.value, verdict.limit.threshold,
                )
        # THE HARD PLUGS (D.3), judged after the soft ones (the judge's own
        # ordering: a hard breach outranks a warning). A stopped turn is not
        # judged twice.
        if state.stopped_by_limit:
            return None
        hard = check_limits(state, hard_turn_limits())
        return hard if hard.stopped else None
    except Exception:
        logger.exception("turn limits: the check itself failed (stage=%s)", stage)
        return None


def _stop_outcome(
    verdict: Any,
    *,
    pending_work: bool,
    result: Any,
    call_budget: Optional[int],
) -> str:
    """Whether a fired plug ABORTS the turn or lets it finish (D7 (a)/(b), F1).

    FINISH when there is no further work to start — the turn was ending anyway —
    or when the last stream left a nearly-complete answer (`nearly_complete`):
    aborting there throws away an answer the turn has already paid for. Anything
    else aborts, and the partial answer is kept and the user told why.
    """
    if not pending_work:
        return STOP_FINISH
    if nearly_complete(
        getattr(result, "finish_reason", ""),
        getattr(result, "completion_tokens", 0),
        call_budget,
    ):
        return STOP_FINISH
    return STOP_ABORT


def _content_frame(text: str) -> str:
    """One CONTENT frame, in the ONLY shape the frontend renders.

    Measured live (2026-09-23): `{'content': text}` looks right and renders
    NOTHING — `StreamingService` accumulates from
    `parsed.choices[0].delta.content` and ignores every other shape, so a
    stand-in sentence sent the obvious way never reached the bubble. The same
    shape the stub path uses (`{'choices': [{'delta': {'content': …}}]}`).
    """
    return f"data: {json.dumps({'choices': [{'delta': {'content': text}}]})}\n\n"


def _replace_frame() -> str:
    """One REPLACE frame: the answer the client holds is SUPERSEDED — drop it before appending.

    Measured live (2026-11-20): one turn answered twice and the bubble showed both — `Ready.Ready.`
    beside a saved row of `Ready.` — because the server reassigns `accumulated_content` whenever a
    later pass answers (a deep round, a deep answer pass, the main loop's answer pass) and the client
    can only append. The server was right; the wire was silent.

    It rides `_content_frame`'s shape for that function's reason — a frame in any other shape renders
    NOTHING. The flag is a member of the same delta, so a reader that only looks for `content` sees an
    empty delta and appends nothing.

    LAZY BY DESIGN: it is emitted immediately before the FIRST content chunk of the pass that
    supersedes, never at the decision to run that pass. A deep pass that comes back empty therefore
    replaces nothing and the answer already on screen survives — which is the server's own rule
    ("an empty deep pass keeps the first pass", see the HYBRID branch below).
    """
    return f"data: {json.dumps({'choices': [{'delta': {'replace': True}}]})}\n\n"


def _nothing_to_show_sentence(
    context: Any, accumulated_content: str, tool_rounds: int
) -> Optional[str]:
    """Why this turn produced nothing, in the guard's tone — or None (D.3/D.4).

    A turn that stops without an answer must SAY so: the arc's own promise is
    "never silence, never a lost turn", and two of its own paths can end that way
    (a hard plug fired before any text arrived; the tool loop used every round it
    had). Returning a sentence here makes `finalize_response` persist it as the
    message instead of refusing an empty row — the turn is then on the transcript,
    and it survives a reload. None means the cause is unknown, and the
    empty-message guard keeps that case.
    """
    if (accumulated_content or "").strip():
        return None
    state = _turn_state_of(context)
    plug = getattr(state, "hard_stop", None) if state is not None else None
    if plug and plug.get("reason"):
        # The plug's own sentence (D.3), which already says what was crossed and
        # what became of the turn — the same words the toast showed.
        return f"{plug['reason']} {CONTINUE_SENTENCE}"
    if tool_rounds:
        return (
            f"This turn made {tool_rounds} tool calls and still produced no answer, "
            f"so it stopped here. {CONTINUE_SENTENCE}"
        )
    return None


async def _persist_refusal(service: Any, context: Any, statement: str) -> None:
    """Put the refusal on the transcript, so a reload shows it rather than a lone user message.

    A FAILED turn's statement is persisted by the `finalize_response` that follows it; a refusal
    returns BEFORE the pipeline, so there is no finalize and this is that half done directly. The
    row carries what is honestly known — the sentence, the model and the provider — and claims no
    tokens and no timing, because no provider call was made. Best-effort: a turn must not fail
    because its own refusal could not be written down.
    """
    try:
        from app.infrastructure.database.models import ChatMessage

        service.db.add(
            ChatMessage(
                session_id=context.session.id,
                role="assistant",
                content=statement,
                model=context.model,
                provider=context.provider,
                meta={"refusal": True},
            )
        )
        await service.db.commit()
    except Exception:  # noqa: BLE001 — the refusal is already on the wire
        logger.exception("refusal: could not persist the refused turn's sentence")


def _stop_turn(
    context: Any,
    verdict: Any,
    *,
    mode: str,
    stage: str,
    partial: str = "",
) -> Optional[str]:
    """Record and log a fired hard plug (F3); the SSE frame when the turn ABORTED.

    One place, so every boundary stops a turn the same way: the account records it
    (the note the message and a reloaded row read), the log names the plug and
    what became of the turn, and an ABORT returns the `event: error` frame
    (`limit_stop`) the frontend already toasts and routes to `onStreamError` (F2).
    The partial answer is saved by the finalize that follows — this only says what
    happened.
    """
    state = _turn_state_of(context)
    limit = getattr(verdict, "limit", None)
    if state is None or limit is None:
        return None
    # What the turn HAD when the plug fired: the note's outcome sentence (and the
    # frame's message) must not claim a partial that never arrived — a plug can
    # fire before the first token, when the crossing is a provider call.
    _kept = len(str(partial or ""))
    state.record_stop(verdict, mode, kept_chars=_kept)
    logger.error(
        "%s",
        turn_stopped_line(
            limit,
            getattr(verdict, "value", None),
            partial_chars=_kept,
            stage=stage,
            mode=mode,
        ),
    )
    if mode != STOP_ABORT:
        return None
    return build_limit_stop_event(context, stop_message(limit, mode, _kept))


def _report_turn_account(context: Any) -> None:
    """Log the turn's account, with the tool-call count MIRRORED from the tracker.

    Called from `generate_stream`'s `finally`: a turn that died, was aborted or was
    closed by the client still reports what it spent. Nothing here may raise into
    the stream.
    """
    state = _turn_state_of(context)
    if state is None:
        return
    try:
        state.observe_tool_calls(getattr(context, "tool_call_tracker", None))
        report_turn_account(
            state,
            session_id=getattr(context, "session_id", None),
            model=getattr(context, "model", None),
            provider=getattr(context, "provider", None),
        )
    except Exception:
        logger.exception("turn accounting: the report itself failed")




router = APIRouter(prefix="/chat", tags=["chat"])





def get_chat_service(db: Annotated[AsyncSession, Depends(get_db)]) -> ChatService:

    """Dependency to get chat service."""

    return ChatService(db)





# Text file extensions that can be read inline

TEXT_EXTENSIONS = {'.md', '.txt', '.py', '.json', '.csv', '.yaml', '.yml'}





async def _enhance_message_with_attachments(

    db: AsyncSession,

    session_id: int,

    message: str,

    attachment_ids: list[int] | None = None,

) -> str:

    """

    Check for attachments and enhance message with their content.

    

    For text files: reads content and prepends to message

    For binary files: adds file path reference

    

    Args:

        db: Database session

        session_id: Chat session ID

        message: Original user message

        attachment_ids: Specific attachment IDs to include (from stream request)

        

    Returns:

        Enhanced message with attachment content

    """

    from sqlalchemy import select

    from app.infrastructure.database.models import ChatAttachment

    

    attachments: list[Any] = []

    

    if attachment_ids:

        # Use specific attachment IDs from the request

        result = await db.execute(

            select(ChatAttachment)

            .where(

                ChatAttachment.id.in_(attachment_ids),

                ChatAttachment.session_id == session_id,

            )

        )

        attachments = list(result.scalars().all())

    

    if not attachments:

        return message

    

    # Build attachment content block

    attachment_blocks = []

    

    for attachment in attachments:

        file_ext = Path(attachment.file_path).suffix.lower()

        

        # For text files, read and include content

        if file_ext in TEXT_EXTENSIONS:

            try:

                file_path = Path(attachment.file_path)

                if file_path.exists():

                    content = file_path.read_text(encoding='utf-8')

                    # Truncate very large files (first 10KB)

                    if len(content) > 10240:

                        content = content[:10240] + "\n\n... [file truncated, first 10KB shown]"

                    

                    block = f"""--- FILE: {attachment.original_filename} ---

{content}

--- END FILE ---"""

                    attachment_blocks.append(block)

                    logger.info(f"📎 Included text file content: {attachment.original_filename} ({len(content)} chars)")

            except Exception as e:

                logger.warning(f"⚠️  Failed to read text file {attachment.original_filename}: {e}")

                # Fall back to reference-only

                attachment_blocks.append(f"[File: {attachment.original_filename} - could not read content]")

        else:

            # Binary files: just reference them

            attachment_blocks.append(

                f"[File: {attachment.original_filename} ({attachment.file_type.upper()}, {attachment.file_size} bytes) - binary file]"

            )

    

    # Prepend attachments to message

    enhanced_message = f"""[System: The following files are attached to this message:]



{chr(10).join(attachment_blocks)}



{message}"""

    

    logger.info(f"📎 Enhanced message with {len(attachments)} attachment(s)")

    return enhanced_message





class ChatRequestModel(BaseModel):

    """Request model for chat."""



    agent_id: int

    message: str

    session_id: int | None = None

    stream: bool = False

    generate_title: bool = Field(

        default=False,

        description="Auto-generate session title from first message"

    )

    attachment_ids: list[int] | None = Field(

        default=None,

        description="Attachment IDs to include in message context"

    )





class DelegateRequestModel(BaseModel):

    """Request model for delegation (read-only, no session)."""

    agent_id: int

    message: str

    context: str = ""
    """Accumulated session context to pass to the delegate agent."""







@router.post("/stream")

async def chat_stream(

    request: ChatRequestModel,

    service: Annotated[ChatService, Depends(get_chat_service)],

) -> StreamingResponse:

    """Send a message and get a streaming response with tracing."""

    async def _traced_stream():

        from app.workflows.observability.langfuse_config import LangfuseManager

        # ONE trace per chat turn, named by an id derived from the turn's own seed: the id is
        # recomputable with no client and no network, and every span the turn creates joins it.
        _trace_id = LangfuseManager.chat_trace_id(request.session_id, time.time())

        with LangfuseManager.create_trace(
            "agent-chat",
            session_id=request.session_id,
            trace_id=_trace_id,
            metadata={"agent_id": request.agent_id},
            # The ROOT's input/output is what the trace table, the session view and every evaluator
            # read first — so it is the user's message, deliberately, not the whole request object.
            input=request.message,
        ) as _lf_span:

            # The outcome is set where it is KNOWN, not assumed: a stream the client abandoned must
            # not be recorded as a completed turn.
            _outcome: dict = {"status": "interrupted"}

            try:
                async for chunk in generate_stream(request, service):
                    yield chunk
                _outcome = {"status": "completed"}
            except Exception as _exc:
                _outcome = {"status": "error", "error": str(_exc)[:300]}
                raise
            finally:
                LangfuseManager.update(_lf_span, output=_outcome)



    return StreamingResponse(

        _traced_stream(),

        media_type="text/event-stream",

        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},

    )





@router.post("/delegate")

async def chat_delegate(

    request: DelegateRequestModel,

    db: Annotated[AsyncSession, Depends(get_db_session)],

) -> Dict[str, Any]:

    """

    Delegate a task to an agent WITHOUT creating sessions or saving messages.



    This is a READ-ONLY endpoint.

    It reads agent info, tools, and provider config from the database,

    calls the LLM, and returns the response text.



    This avoids SQLite write lock contention that occurs when the standard

    /chat/stream endpoint is called from within another streaming chat's

    tool execution context (the outer stream holds a write transaction,

    blocking the inner stream's session/message INSERTs).

    """

    from app.api.v1.chat.context import _build_tools_section

    from app.api.v1.chat.llm_utils import acompletion_with_retry

    from app.domain.tools.services import AgentToolService


    from app.domain.tools.execution_service import ToolExecutionService

    from app.infrastructure.database.models import Agent, Provider

    from .tool_execution import execute_single_tool

    from .logging_service import ChatLoggingService

    from sqlalchemy import select



    logger.info(f"🔗 Delegate request: agent_id={request.agent_id}, message_preview={request.message[:100]}")



    # 1. Get agent (READ ONLY - no writes)

    agent_query = select(Agent).where(Agent.id == request.agent_id)

    agent_result = await db.execute(agent_query)

    agent = agent_result.scalar_one_or_none()

    if not agent:

        return {"success": False, "error": f"Agent {request.agent_id} not found"}



    # 2. Get enabled tools for the agent (READ ONLY - no writes)

    agent_tool_service = AgentToolService(db)

    enabled_tools = await agent_tool_service.list_agent_tools(

        str(agent.id), is_enabled=True

    )

    # THE TOOLKIT POLICY (2026-08-24, the kit IS the surface): an
    # agent that OWNS a kit (agents.kit_id -> a tool-typed collection)
    # gets ONLY the kit's granted tools — the GRAS default is
    # suppressed AND the stale agent_tools links are ignored. The
    # kit's tools come from the tools table BY SLUG (no agent_tools
    # row needed — the kit grant IS the surface).
    from app.domain.tools.execution_service import ToolExecutionService
    _toolkit_svc = ToolExecutionService(db)
    try:
        _kit_slugs = await _toolkit_svc._toolkit_slugs_for_agent(str(agent.id))
    except Exception:
        _kit_slugs = None
    if _kit_slugs is not None:
        from app.domain.tools.models import Tool as _ToolModel
        from sqlalchemy import select as _select
        _rows = await db.execute(
            _select(_ToolModel).where(_ToolModel.slug.in_(_kit_slugs))
        )
        _kit_tools = _rows.scalars().all()
        _slug_to_tool = {t.slug: t for t in _kit_tools}
        # keep the raw links that ARE in the kit (their config matters)
        # + wrap the kit-only tools (no agent_tools row) as bare links
        from types import SimpleNamespace as _NS
        _kept = [at for at in enabled_tools if at.tool and at.tool.slug in _slug_to_tool]
        _have = {at.tool.slug for at in _kept if at.tool}
        for _slug, _tool in _slug_to_tool.items():
            if _slug not in _have:
                _kept.append(_NS(tool=_tool, is_enabled=True, priority=0))  # type: ignore[arg-type]
        enabled_tools = _kept



    # 3. Convert tools to LLM function calling format

    llm_tools = []

    for agent_tool in enabled_tools:

        tool = agent_tool.tool

        if tool:

            llm_tool = tool_to_llm_schema(tool)

            if llm_tool:

                llm_tools.append(llm_tool)



    # 4. Build system prompt with tools section

    system_prompt = agent.system_prompt or ""

    if request.context:
        system_prompt = f"{system_prompt}\n\n## Previous Conversation Context\n\n{request.context}"

    tools_section = _build_tools_section(llm_tools)

    if tools_section:

        system_prompt = f"{system_prompt}\n\n{tools_section}"



    # 5. Determine model and provider

    model = agent.model
    provider_name = getattr(agent, 'provider', 'ollama')
    from app.domain.providers.litellm_route import api_base_for, litellm_model_string
    from app.domain.providers.provider_endpoints import resolve_endpoint
    litellm_model = litellm_model_string(provider_name, model)



    # 6. Resolve provider credentials from database (READ ONLY)

    api_base = None

    api_key = None

    try:

        provider_query = select(Provider).where(

            Provider.name == provider_name,

            Provider.is_active,

        ).limit(1)

        provider_result = await db.execute(provider_query)

        provider_row = provider_result.scalar_one_or_none()

        if provider_row:

            if provider_row.base_url:

                api_base = api_base_for(
                    litellm_model_string(provider_name, model, provider_row.provider_type),
                    resolve_endpoint(
                        provider_row.provider_type or provider_row.name,
                        provider_row.base_url,
                        provider_row.name,
                    ),
                )

            if not api_key:
                from app.domain.providers.env_key_store import env_key_store
                api_key = env_key_store.get_key(provider_name)

    except Exception as prov_err:

        logger.warning(f"Error loading provider credentials for '{provider_name}': {prov_err}")



    # 7. Build messages for LLM

    messages: list[dict[str, Any]] = []

    if system_prompt:

        messages.append({"role": "system", "content": system_prompt})

    messages.append({"role": "user", "content": request.message})



    # 8. Build LLM request kwargs

    # NOTE: Apply agent.parameters FIRST, then explicitly set our values

    # so agent.parameters cannot override model, messages, stream, etc.

    request_kwargs: Dict[str, Any] = {}

    if agent.parameters:

        request_kwargs.update(agent.parameters)

    # Now set our explicit values (overrides any conflicting agent.parameters keys)

    request_kwargs["model"] = litellm_model

    request_kwargs["messages"] = messages

    request_kwargs["stream"] = False

    # THE OUTPUT BUDGET (the token-limit arc, C.1): the delegated turn's budget
    # comes from the resolver like every other path. It used to arrive as
    # `agent.parameters` copied in verbatim — no floor — so a thinking delegate
    # ran its whole budget through the thinking phase and answered nothing. This
    # endpoint is READ-ONLY by design (no session, no runtime config), so there
    # is no per-session override to pass.
    apply_output_budget(request_kwargs, agent, litellm_model, PATH_DEFAULT)

    # THE DEBUG (2026-09-01, the Bonsai dig): the variables BEFORE
    # the ifs — the provider-lookup's result + the agent.parameters'
    # shadowing check.
    logger.info(
        "BUILD-DEBUG pre-if api_key=%r api_base=%r provider=%s",
        api_key,
        api_base,
        provider_name,
    )

    if api_base:

        request_kwargs["api_base"] = api_base

    if api_key:

        request_kwargs["api_key"] = api_key
    elif api_base:
        # The keyless local servers (the llama, 2026-09-01) still
        # need a NON-EMPTY key for the litellm's openai-adapter —
        # the 'Missing credentials' error otherwise.
        from app.domain.providers.llm_factory import placeholder_key_for
        _placeholder = placeholder_key_for(api_base)
        if _placeholder:
            request_kwargs["api_key"] = _placeholder
        logger.info("BUILD-DEBUG elif fired (api_base=%s api_key=%r)", bool(api_base), api_key)

    if provider_name == "ollama_cloud" and api_key:
        # THE OLLAMA CLOUD AUTH (2026-08-24, live): the ollama_chat
        # LiteLLM handler serves the LOCAL ollama (no auth) and does
        # NOT attach the Authorization header — but ollama.com's API
        # REQUIRES it. The api_key kwarg alone is not enough; the
        # explicit Bearer header is the guaranteed path.
        request_kwargs.setdefault("extra_headers", {})["Authorization"] = f"Bearer {api_key}"

    if llm_tools:

        request_kwargs["tools"] = llm_tools

        request_kwargs["tool_choice"] = "auto"



    # 9. Call LLM with tool execution loop

    # The delegate agent may have tools enabled, and the LLM may return

    # tool_calls instead of text. We execute tools and loop until we get

    # text content (max 5 iterations to prevent infinite loops).

    # No sessions or messages are saved to the database - this is READ-ONLY.

    logger.info(

        f"🔗 Calling LLM for delegate agent {agent.name}: "

        f"model={litellm_model}, "

        f"provider={provider_name}, "

        f"has_api_key={bool(api_key)}, "

        f"tools_count={len(llm_tools)}"

    )



    import asyncio



    max_iterations = turn_config.loop_rounds()

    _twu_ = False  # Track if any tool calls were made

    content = ""

    finish_reason = None



    for iteration in range(1, max_iterations + 1):

        try:

            response = await asyncio.wait_for(

                # the delegate's row rides along (the bridge's carrier, seam 3)
                acompletion_with_retry(**request_kwargs, provider=provider_name),

                timeout=turn_config.delegate_call_timeout_s(),

            )

        except asyncio.TimeoutError:

            logger.error(f"🔗 Delegate LLM call timed out for agent_id={request.agent_id} (iteration {iteration})")

            return {"success": False, "error": f"LLM call timed out after 120s (iteration {iteration})", "content": ""}

        except Exception as e:

            logger.error(f"🔗 Delegate LLM call failed: agent_id={request.agent_id}, error={e}")

            return {"success": False, "error": str(e), "content": ""}



        # Parse response

        if not hasattr(response, 'choices') or not response.choices:

            logger.warning(f"🔗 Delegate LLM returned no choices (iteration {iteration})")

            if isinstance(response, dict):

                content = response.get('choices', [{}])[0].get('message', {}).get('content', '')

            break



        choice = response.choices[0]

        finish_reason = getattr(choice, 'finish_reason', None)



        # --- Handle tool calls ---

        if finish_reason == "tool_calls":

            tool_calls = getattr(choice.message, 'tool_calls', [])

            if not tool_calls:

                logger.warning(f"🔗 finish_reason=tool_calls but no tool_calls in message (iteration {iteration})")

                break



            logger.info(

                f"🔗 Delegate LLM returned {len(tool_calls)} tool calls "

                f"(iteration {iteration}), executing..."

            )



            # Build assistant message with tool_calls for next LLM call

            assistant_msg = {

                "role": "assistant",

                "content": None,

                "tool_calls": [

                    {

                        "id": tc.id,

                        "type": "function",

                        "function": {

                            "name": tc.function.name,

                            "arguments": tc.function.arguments,

                        }

                    }

                    for tc in tool_calls

                ]

            }

            messages.append(assistant_msg)



            # Execute each tool

            tool_execution_service = ToolExecutionService(db)

            logger_service = ChatLoggingService()



            for tc in tool_calls:

                tc_dict = {

                    "name": tc.function.name,

                    "id": tc.id,

                    "arguments": tc.function.arguments,  # JSON string from LLM

                }

                result = await execute_single_tool(

                    tool_call=tc_dict,

                    agent_id=request.agent_id,

                    session_id=0,  # sentinel - no real session created

                    tool_execution_service=tool_execution_service,

                    logger_service=logger_service,

                )

                # Append tool result message for LLM consumption

                messages.append(result.to_llm_message())



            # Update request kwargs with updated messages for next iteration

            request_kwargs["messages"] = messages

            continue



        # --- Extract text content ---

        if hasattr(choice, 'message') and choice.message:

            content = getattr(choice.message, 'content', '') or ''

        elif hasattr(choice, 'text'):

            content = choice.text or ''



        logger.info(

            f"🔗 Delegate response received: "

            f"agent_id={request.agent_id}, "

            f"content_length={len(content)}, "

            f"finish_reason={finish_reason}, "

            f"iterations={iteration}"

        )

        break



    return {

        "success": bool(content.strip()),

        "content": content,

        "content_length": len(content),

    }





async def generate_stream(

    request: ChatRequestModel,

    service: ChatService,

) -> AsyncGenerator[str, None]:

    """

    Generate streaming response chunks.



    Orchestrates: context prep → cognitive pipeline → LLM streaming → tool execution → finalization

    """

    from app.services.cognitive_pipeline.models import AgentDescriptor, Context as PipelineContext
    from app.services.cognitive_pipeline.memory_manager import NoopMemoryManager, run_memory_manager

    logger_service = ChatLoggingService()

    start_time = time.time()

    context = None

    cognitive_result: CognitiveResult | None = None



    try:
        _twu_ = False  # Track if any tool calls were made  # UNIQUE_MARKER_1784929264


        # Enhance message with attachment content (if any)

        message = request.message

        if request.session_id:

            message = await _enhance_message_with_attachments(

                service.db, request.session_id, message, request.attachment_ids

            )

        

        # Prepare context with potentially enhanced message

        context = await prepare_chat_context(

            db=service.db, service=service,

            agent_id=request.agent_id, session_id=request.session_id,

            message=message,

        )

        logger_service.log_request_start(context)



        # Initialize tool call tracker to prevent loops and spam

        context.tool_call_tracker = ToolCallTracker(

            # 4, not 2: the verify pattern (read, write, read-back) makes
            # two identical reads legitimately — see the tracker's docstring
            max_consecutive_calls=4,

            dedup_window_seconds=30,

            # THE SINGLE SOURCE (the token-limit arc, C.4): the 10 that
            # used to sit here silently undid the tracker's own default —
            # a 12-call inventory turn was killed again after the 10 → 30
            # raise. The tracker's default IS the policy.
        )

        logger.info(f"🔒 Tool call tracker initialized for session {context.session_id}")

        # THE TURN'S ACCOUNT (Phase D.1): one object per turn, accumulated by
        # every provider call the main loop and the deep pass make, and reported
        # from a `finally` at the end of this generator — so a turn that died or
        # was closed mid-stream still says what it spent.
        context.turn_state = TurnState()

        # THE LIMIT SET IN FORCE (D.2's soft lines, D.3's hard plugs), said out
        # loud once per turn — the armed set AND the one left that cannot be judged
        # yet (D8's shape: an inactive limit must SAY it is inactive, so a reader can
        # tell "nothing is near a line" from "nothing is watching").
        #
        # The CALL-scoped softs are named too (E.6): the census used to list only the
        # turn-scoped set, which would read as "nothing else is watching" while two
        # call-scoped lines were armed. The input soft's threshold is known here (the
        # assembly ceiling is decided with the window); the output soft's is not —
        # it is a fraction of a budget the path decides later, and the per-call
        # EFFECTIVE OUTPUT BUDGET line is where that number is said.
        logger.info(
            "⚖️  TURN LIMITS %s · call-scoped: %s + output_tokens(soft call 90%% of the call's own budget) · %s",
            limits_in_force(turn_soft_limits() + hard_turn_limits()),
            # `limits_in_force` prefixes its own "limits: " — the census already
            # introduced the half, so one prefix is dropped rather than stuttered.
            limits_in_force(
                call_soft_limits(None, input_budget=getattr(context, "input_budget", None))
            ).removeprefix("limits: "),
            inactive_limits_note(),
        )



        # 2. Conversation compaction — keep within token window

        from app.domain.providers.capabilities import resolve
        from app.services.cognitive_pipeline.conversation_compactor import (
            SUMMARY_CAPABILITY_KEY,
            compact_messages,
        )

        if context and context.messages:
            # The summarizer's service comes from the `summary` capability — resolved HERE, where the
            # session is (the compactor holds none, and never invents one). This used to ride the
            # TURN's model and fall back to the literals `llama3.2`/`ollama`: a service named in code,
            # and the reason the `summary` capability had no consumer at all (phase-8's audit).
            # The resolution needs a session, and `service.db` is where it is (the same seam the
            # chat chain is attached through a few lines below).
            summary_chain = await resolve(service.db, SUMMARY_CAPABILITY_KEY)
            context.messages = await compact_messages(
                context.messages,
                max_tokens=6144,
                candidates=summary_chain.candidates,
            )

        # 3. Build LLM request

        request_kwargs = build_llm_request(context, stream=True)



        # Send session ID

        yield f"event: session_id\ndata: {json.dumps({'session_id': context.session_id})}\n\n"



        # ------------------------------------------------------------------

        # Cognitive Pipeline — Context Builder

        # ------------------------------------------------------------------

        # Build an AgentDescriptor from the chat context for the pipeline

        # system_prompt is embedded in context.messages[0] if role=="system"

        system_prompt = ""

        if context.messages and context.messages[0].get("role") == "system":

            system_prompt = context.messages[0].get("content", "")

        agent_desc = AgentDescriptor(

            id=context.agent_id,

            name=context.agent_name,

            description=(str(context.agent.description) if hasattr(context.agent, 'description') and context.agent.description is not None else ''),

            provider=context.provider,

            model=context.model,

            system_prompt=system_prompt,

            cognitive_profile_id=getattr(context.agent, 'cognitive_profile_id', None),

            fallback_enabled=bool(getattr(context.agent, 'fallback_enabled', False)),

            preferred_providers=list(getattr(context.agent, 'preferred_providers', None) or []),

        )



        # THE RESOLVER's chain on the descriptor (R3) — the same seam as the output budget:
        # the resolution needs a session, and this is where it is.
        from app.services.cognitive_pipeline.chat_chain import attach as attach_chat_chain

        agent_desc = await attach_chat_chain(agent_desc, service.db, path="chat")

        # ...and on the CONTEXT, because the turn's streaming call (`_stream_llm_response`) opens
        # its own request and must be able to fail over too — the chain reaches both call sites.
        context.candidates = list(agent_desc.candidates)

        # ── THE PRE-TURN REFUSAL (G5-F3/F4) ──────────────────────────────────────────────────
        # A turn that cannot run is refused HERE — the resolution is in hand and the pipeline has
        # not started — in the statement shape, over the SAME `event: error` frame a failed turn
        # uses, so the frontend needs no new path (G5-F4).
        #
        # The read is the availability CACHE only: a turn never pays a probe, and a service nobody
        # checked (`unknown`/cold) never refuses — the chain walk below stays the arbiter. The two
        # refusing states are the availability ruling's own: the capability is OFF, or its primary
        # is cached-`down` with nothing the walk is allowed to fail over to.
        from app.domain.providers.capabilities import CHAT_CAPABILITY_KEY
        from app.domain.providers.refusal import refusal_statement

        _refusal = refusal_statement(
            CHAT_CAPABILITY_KEY,
            resolution_reason=getattr(agent_desc, "chain_reason", None) or "",
            candidates=context.candidates,
            fallback_enabled=bool(getattr(context.agent, "fallback_enabled", False)),
        )
        if _refusal:
            logger.warning(
                "🚫 REFUSED before the pipeline session=%s agent=%s reason=%s: %s",
                context.session_id, context.agent_name,
                getattr(agent_desc, "chain_reason", None), _refusal,
            )
            # The sentence reaches the BUBBLE as well as the toast: the error frame ends the stream
            # before any content would, so the reader would otherwise be left with a toast only.
            yield _content_frame(_refusal)
            yield build_refusal_event(context, _refusal)
            await _persist_refusal(service, context, _refusal)
            return



        # Resolve effective pipeline config from agent's cognitive profile

        pipeline_config = await _resolve_pipeline_config(service.db, context)



        # Run the Context Builder (deterministic assembly — fast, no LLM)

        from app.services.cognitive_pipeline.context_builder import run_context_builder

        pipeline = CognitivePipeline()

        context_builder = pipeline.context_builders.get(pipeline_config.context_builder)

        pipeline_context, cb_trace = await run_context_builder(

            builder=context_builder,

            user_message=message,

            agent=agent_desc,

            session_history=[],

        )

        # Emit cognitive_context_built event

        _topic, _payload = build_context_built(str(request.session_id or ""), cb_trace)
        publish(_topic, {**_payload, "kind": "context_built"})
        yield sse_from_builder((_topic, _payload))



        # Initialize memory manager instance for this request

        memory_registry = create_default_memory_registry()

        try:

            memory_manager = memory_registry.get(pipeline_config.memory_manager)

        except KeyError:

            memory_manager = None

            logger.warning("Memory manager '%s' not found, memory disabled", pipeline_config.memory_manager)



        # Handle per-agent db_path for sqlite persistence

        if memory_manager and hasattr(memory_manager, '_db_path') and pipeline_config.memory_profile_persistence == "sqlite":
            # Resolve agent folder from provisioning data
            if not pipeline_config.agent_folder and hasattr(context, 'agent') and context.agent:
                _agent_id = getattr(context.agent, 'id', None)
                if _agent_id:
                    import glob as _glob
                    import json as _json
                    from app.core.config import Paths, get_settings
                    for _agent_json in _glob.glob(
                        str(Paths.from_settings(get_settings()).agents_dir / "*" / "agent.json")
                    ):
                        try:
                            with open(_agent_json) as _f:
                                _data = _json.load(_f)
                            if _data.get("db_id") == _agent_id:
                                pipeline_config.agent_folder = _data.get("folder", _data.get("name", "").lower().replace(" ", "-"))
                                break
                        except Exception:
                            continue


            agent_folder = pipeline_config.agent_folder or getattr(context.agent, 'folder', None)

            if agent_folder:

                from app.core.config import Paths, get_settings
                mem_db_path = str(Paths.from_settings(get_settings()).agents_dir / agent_folder / "cognitive_memory.db")

                memory_manager._db_path = mem_db_path

                memory_manager._is_deep = True

                memory_manager._init_db()

                logger.info("Memory manager using per-agent db: %s", mem_db_path)




            # Apply compaction and summarization settings from profile
            if pipeline_config.compaction_threshold is not None:
                memory_manager.summarization_threshold = pipeline_config.compaction_threshold
            memory_manager._summarization_enabled = pipeline_config.summarization_enabled


            # Cross-session memory recall — inject summaries and facts into system prompt
            _recall_agent = AgentDescriptor(
                id=context.agent_id,
                name=context.agent_name,
                description=getattr(context.agent, 'description', '') if hasattr(context.agent, 'description') else '',
            )
            try:
                summaries = await memory_manager.recall_summaries(
                    agent=_recall_agent, max_count=5
                )
                if summaries:
                    summary_text = "\n".join(
                        f"  - {s}" for s in summaries
                    )
                    request_kwargs["messages"][0]["content"] += (
                        "\n\n[From previous conversations:"
                        f"\n{summary_text}"
                        "\n]"
                    )
            except Exception:
                pass

            try:
                facts = await memory_manager.recall_facts(agent=_recall_agent)
                if facts:
                    facts_text = "\n".join(f"  - {f}" for f in facts)
                    request_kwargs["messages"][0]["content"] += (
                        "\n\n[Known facts about the user:"
                        f"\n{facts_text}"
                        "\n]"
                    )
            except Exception:
                pass

        # Emit executor_started before the LLM call

        _topic, _payload = build_executor_started(str(request.session_id or ""), pipeline_config.executor)
        publish(_topic, {**_payload, "kind": "executor_started"})
        yield sse_from_builder((_topic, _payload))



        # ------------------------------------------------------------------

        # Apply executor strategy to request_kwargs before the LLM call

        # ------------------------------------------------------------------

        executor_strategy = pipeline_config.executor

        if executor_strategy == "fast":

            # Fast strategy: minimal tokens, low temperature, no tools, no history

            # (the budget is the resolver's fast policy constant — see the
            # `_apply_output_budget` call after these branches).

            request_kwargs["temperature"] = 0.3

            # Strip tool instructions from system prompt

            if request_kwargs["messages"] and request_kwargs["messages"][0].get("role") == "system":

                sp = request_kwargs["messages"][0]["content"]

                # Remove any tools/function sections from system prompt

                import re as _re

                sp = _re.split(r"\n## Tools|\n## Available Tools|\n---\n", sp)[0]

                request_kwargs["messages"][0]["content"] = sp

            # Remove tool schemas from request

            request_kwargs.pop("tools", None)

            request_kwargs["tool_choice"] = "none"

            # Limit to just system + the CURRENT user message, drop history
            # The current turn is the LAST user message in context.messages
            # ([system, ...history..., user(current)]) — breaking at the
            # FIRST user message would answer the session's opening message
            # instead (the turn-2 wrong-response bug, fixed 2026-08-21).

            filtered = []

            for m in request_kwargs["messages"]:

                if m["role"] == "system":

                    filtered.append(m)

            for m in reversed(request_kwargs["messages"]):

                if m["role"] == "user":

                    filtered.append(m)

                    break

            request_kwargs["messages"] = filtered

            max_iterations = 1  # no tool iterations needed

            logger.info("FastExecutor: policy budget (the resolver), temp=0.3, no tools, 1 iteration")



        elif executor_strategy == "hybrid":

            # Hybrid strategy: first pass fast, then full pass if needed

            # (the pass-1 budget is the agent's DECLARED value — the resolver
            # runs pass 1 at the declaration, not at a quarter of it: see the
            # `_apply_output_budget` call after these branches.)

            request_kwargs["temperature"] = 0.3

            logger.info("HybridExecutor: pass 1 — the declared budget, temp=0.3")



        elif executor_strategy == "stub":

            # Stub strategy: no LLM call, return simulated response

            stub_text = (

                f"This is a simulated response from **{context.agent_name}**.\n\n"

                f"You said: \"{message}\"\n\n"

                f"*Cognitive profile active — executor strategy: stub*"

            )

            yield f"data: {json.dumps({'choices': [{'delta': {'content': stub_text}}]})}\n\n"

            yield f"data: [DONE]\n\n"

            executor_trace = ComponentTrace(

                strategy="stub",

                duration_ms=0,

                tokens_used=len(stub_text.split()),

                metadata={"stub": True},

            )

            _topic, _payload = build_executor_completed(str(request.session_id or ""), executor_trace)
            publish(_topic, {**_payload, "kind": "executor_completed"})
            yield sse_from_builder((_topic, _payload))

            # Skip the main execution loop entirely

            return



        # THE OUTPUT BUDGET (the token-limit arc): the ONE place this turn's
        # budget is decided, written and logged. The resolver applies the
        # agent's declaration, the per-session runtime override, this path's
        # policy and the reasoning floor — the floor because a thinking model
        # spends its whole budget thinking (the empty-completion dig:
        # chunks=1026 at the 1024 cap, 4098 at 4096, deterministic) and then
        # answers nothing. Placed AFTER the executor strategy is known, because
        # the path (fast / pass 1 / default) is what the resolver needs.
        _apply_output_budget(
            context, request_kwargs, _output_budget_path(executor_strategy)
        )

        # 3. Main tool execution loop

        max_iterations = turn_config.loop_rounds()

        accumulated_content = ""

        tool_calls_to_execute: list[dict[str, Any]] = []

        result_holder = {"result": None}  # Mutable container for result

        stream_result: StreamResult | None = None



        _twu_ = False  # Track if any tool calls were made

        # THE EMPTY-COMPLETION RETRY STATE (2026-09-02): the wrapper
        # flags an empty completion (chunks but zero tokens); the loop
        # retries ONCE per request before the visible fallback.
        _empty_retried = False

        # WHETHER THE TURN ALREADY SAID ITS STAND-IN SENTENCE IN THE STREAM
        # (2026-09-23): the reason a turn ended with nothing must reach the bubble
        # BEFORE the error frame that ends the stream — the frontend stops reading
        # there — so the stop site streams it and this flag keeps the end-of-turn
        # yield from saying it twice.
        _said_in_stream = False

        for iteration in range(max_iterations):

            logger.debug(f"🔄 Tool execution loop iteration {iteration + 1}/{max_iterations}")



            # Stream LLM response and yield chunks as they arrive

            async for chunk in _stream_llm_response(

                request_kwargs, context, logger_service, start_time, service, result_holder,

                path=_output_budget_path(executor_strategy),

                # ROUND 2 ONWARD SUPERSEDES ROUND 1 (the duplicate-answer fix): every round's result
                # becomes the turn's answer, so a narration round must not survive beside the answer
                # the row keeps. Round 1 has nothing on screen to replace.
                supersedes=iteration > 0,

            ):

                yield chunk



            # Get result from holder

            result = result_holder.get("result")

            if result is None:

                # THE EMPTY-COMPLETION RETRY (2026-09-02, the Bob
                # empty-bubble bug): the wrapper flagged an empty
                # completion (chunks but zero tokens — the model
                # streamed 15-42s and produced nothing usable). The
                # flag means NOTHING user-visible was emitted yet —
                # retry the SAME request once (tools intact, the
                # history untouched). Only when the retry ALSO comes
                # back empty do we fall through to the visible
                # fallback below (the warning toast + text answer —
                # no silent failure, no empty bubble).
                if result_holder.get("empty_completion") and not _empty_retried:
                    _empty_retried = True
                    logger.error(
                        "EMPTY COMPLETION RETRY session=%s model=%s provider=%s "
                        "(chunks=%d) — the first pass came back empty; retrying once",
                        context.session_id, context.model, context.provider,
                        result_holder.get("empty_chunk_count", 0),
                    )
                    continue

                # Streaming error occurred - check if we have accumulated content from tool iterations

                if accumulated_content:

                    logger.warning(f"⚠️ Stream failed but we have {len(accumulated_content)} chars from previous iterations - using that")

                    # Continue to finalize with what we have

                    break

                else:

                    # No content at all - generate a fallback response

                    logger.error("❌ Stream failed with no accumulated content - generating fallback")

                    # THE DEFINITIVE STATEMENT (2026-09-29, the Lois / Space Bunny dig): the app
                    # ALREADY knows where the failure is — `handle_streaming_error` classified it
                    # and said so in the error frame. Asking the MODEL to explain it instead
                    # produced a claim about the model's OWN limits ("I don't have live weather
                    # access in this response") for a turn whose tools had just fetched that very
                    # weather, and that claim is what the user was left with. When the failure is
                    # one the app can place, the STATEMENT IS THE ANSWER: no second call to the
                    # provider that just failed, and nothing for the model to guess at.
                    _statement = build_failure_statement(result_holder.get("stream_error"), context)
                    if _statement:
                        logger.warning(
                            "🛑 Provider-side failure — stating where the problem is rather than "
                            "asking the model to explain it: %s",
                            _statement,
                        )
                        accumulated_content = _statement
                        break

                    try:

                        from .llm_utils import acompletion_with_retry

                        import asyncio



                        # Build a fallback prompt

                        fallback_messages = request_kwargs["messages"] + [

                            {

                                "role": "system",

                                "content": (

                                    "The previous response stream failed. Please provide a direct text answer "

                                    "to the user's question without using any tools."

                                )

                            }

                        ]



                        # Add timeout to prevent hanging (30 seconds)

                        # THE FALLBACK INHERITS THE FULL REQUEST (2026-09-01,
                        # the Bonsai fix): the minimal kwargs (the model +
                        # messages only) dropped the api_base + the key —
                        # the fallback attempt hit the default OpenAI
                        # endpoint with no credentials.
                        fallback_kwargs = {
                            **request_kwargs,
                            "messages": fallback_messages,
                            "tools": None,
                            # THE STREAM=FALSE OVERRIDE (2026-09-05, the Bob
                            # 'CustomStreamWrapper has no attribute choices'
                            # dig): the full-request inheritance ALSO carried
                            # stream=True — acompletion returned a
                            # CustomStreamWrapper (a stream) and the code
                            # below read fallback_response.choices on it →
                            # AttributeError → the fallback crashed into the
                            # generic apology ('I apologize, but I
                            # encountered an error: ...'). The fallback is
                            # by design a NON-streamed direct answer —
                            # force the flag.
                            "stream": False,
                        }
                        # THE FALLBACK WARNING (2026-09-01, the user's
                        # 'silent fallbacks are bad'): the tool-path
                        # failed — the user sees the degradation.
                        # THE NAME, NOT "the agent" (2026-09-29): this toast lands in the Message
                        # Center where the turn's context is gone, so it says which agent, which
                        # model and which provider — the reader has to be able to act on it.
                        from app.domain.messaging.services import publish_warning

                        publish_warning(
                            f"{context.agent_name} fell back",
                            f"{model_subject(context.model, context.provider)} — the tool-calling "
                            f"failed; answering without tools.",
                            kind="tool-path-fallback",
                        )
                        _account_provider_call(context, FALLBACK_PATH)

                        fallback_response = await asyncio.wait_for(

                            acompletion_with_retry(
                                **fallback_kwargs,
                                on_attempt=_retry_observer(context),
                                # the turn's own row rides along (the bridge's carrier, seam 3)
                                provider=context.provider,
                            ),

                            timeout=turn_config.answer_timeout_s(),

                        )



                        if fallback_response.choices and len(fallback_response.choices) > 0:

                            accumulated_content = fallback_response.choices[0].message.content or ""

                            # D.1: the fallback is a provider call in THIS turn.
                            _account_usage(
                                context, service,
                                prompt=_prompt_text(fallback_kwargs.get("messages")),
                                content=accumulated_content,
                                usage=response_usage(fallback_response),
                            )

                            logger.info(f"✅ Generated fallback response: {len(accumulated_content)} chars")

                        else:

                            # THE NAME, NOT AN APOLOGY (2026-09-29): these three app-composed
                            # answers are the fallback's own failure modes, and the old copy
                            # ("I apologize, but I encountered an error…") named nothing — the
                            # reader could not tell WHICH model to change.
                            accumulated_content = failure_sentence(
                                context, "the response stream failed to complete. Try again."
                            )

                            logger.warning("⚠️ Fallback response had no choices, using default error message")



                    except asyncio.TimeoutError:

                        accumulated_content = failure_sentence(
                            context, "the answer took too long to arrive. Try again."
                        )

                        logger.error("❌ Fallback response timed out after 30 seconds")

                    except Exception as e:

                        accumulated_content = failure_sentence(
                            context, "the last attempt failed. Try again."
                        )

                        logger.error(f"❌ Fallback generation failed: {e}", exc_info=True)



                    # Break to finalize with fallback content

                    break



            # THE LINES (D.2/D.3): judged here, where this call's own numbers
            # and the turn's account are both freshest — the call's output
            # against its budget, the turn's totals against the turn's lines. A
            # breached HARD line comes back as `_stop`.
            _stop = _check_turn_limits(
                context,
                stage="call",
                call_tokens=getattr(result, "completion_tokens", 0),
                call_budget=request_kwargs.get("max_tokens"),
                # THE INPUT SOFT (E.6): this call's own prompt, from the provider's
                # usage. `None` when it reported none — then the input line is not
                # judged at all (no measurement is not a breach).
                call_prompt_tokens=getattr(result, "prompt_tokens", None),
            )

            accumulated_content = result.accumulated_content

            tool_calls_to_execute = result.tool_calls

            if tool_calls_to_execute:

                _twu_ = True

            stream_result = result

            # THE HARD PLUG (D.3): a breached hard line stops THIS turn here.
            # Nothing further is started, the answer so far is kept, and — unless
            # the turn was ending anyway (D.4 (b)) — the user is told why. The
            # partial is the point, so this sits AFTER the content is taken and
            # BEFORE any tool runs.
            if _stop is not None:

                _stop_frame = _stop_turn(
                    context,
                    _stop,
                    mode=_stop_outcome(
                        _stop,
                        pending_work=bool(tool_calls_to_execute),
                        result=result,
                        call_budget=request_kwargs.get("max_tokens"),
                    ),
                    stage="call",
                    partial=accumulated_content,
                )

                if _stop_frame:

                    # THE TURN SAYS SOMETHING BEFORE IT SAYS IT STOPPED
                    # (2026-09-23): the frontend STOPS READING the stream on the
                    # error frame, so a stand-in sentence streamed after it never
                    # reaches the bubble (measured live: an empty bubble next to a
                    # correct row). When nothing arrived, the reason IS the answer
                    # — it goes out FIRST, and `_said_in_stream` keeps the later
                    # yield from repeating it.
                    _say_first = _nothing_to_show_sentence(context, accumulated_content, 0)
                    if _say_first:
                        _said_in_stream = True
                        yield _content_frame(_say_first)

                    yield _stop_frame

                break



            # If no tool calls, we're done

            if not tool_calls_to_execute:

                logger.info("✅ No tool calls - conversation complete")

                break



            # Check tool calls for loops/spam before executing

            filtered_tool_calls = []

            blocked_calls = []



            for tool_call in tool_calls_to_execute:

                tool_name = tool_call["name"]

                arguments = tool_call.get("parsed_arguments", {})



                should_exec, warning_msg, error_msg = context.tool_call_tracker.should_execute(

                    tool_name=tool_name,

                    arguments=arguments,

                    iteration=iteration,

                )



                if error_msg:

                    # Blocked - add to blocked list

                    blocked_calls.append(tool_call)

                    logger.error(f"🚫 Blocked tool call: {tool_name} - {error_msg}")

                else:

                    filtered_tool_calls.append(tool_call)

                    if warning_msg:

                        logger.warning(f"⚠️  {warning_msg}")



            # If all calls blocked, break the loop

            if not filtered_tool_calls:

                # Build detailed error message

                blocked_details = [

                    f"{call['name']}({call.get('parsed_arguments', {})})"

                    for call in blocked_calls

                ]

                error_message = (

                    f"Tool call limit reached: {blocked_details[0] if len(blocked_details) == 1 else str(blocked_details)} "

                    f"was called repeatedly this turn and the safety guard "

                    f"stopped it. Say 'continue' and I'll carry on from what I have."

                )

                logger.error(f"🚫 All {len(tool_calls_to_execute)} tool calls blocked - breaking loop")

                logger.error(f"   Blocked calls: {blocked_details}")

                

                # Generate a text-only response from the LLM instead of returning empty

                logger.info("📝 Generating text-only response after tool loop blocking...")

                try:

                    from .llm_utils import acompletion_with_retry

                    

                    # Add system message to guide the LLM

                    fallback_messages = request_kwargs["messages"] + [

                        {

                            "role": "system",

                            "content": (

                                "Your tool calls were blocked by a safety guard. "

                                f"What was blocked: {blocked_details}. "

                                "The guard stops repeated calls and cannot tell a "

                                "stuck loop from a deliberate repeat (such as reading a "

                                "file back to verify a write). If that is what happened, "

                                "say so plainly — do not guess at a cause you cannot see. "

                                "Please respond directly with a helpful text answer to the user's question. "

                                "Explain what you were trying to do and why it couldn't be completed. "

                                "Do NOT attempt to call any tools in this response."

                            )

                        }

                    ]

                    

                    # Make a non-tool LLM call to generate text response

                    _account_provider_call(context, FALLBACK_PATH)

                    fallback_response = await acompletion_with_retry(

                        model=request_kwargs["model"],

                        messages=fallback_messages,

                        tools=None,

                        on_attempt=_retry_observer(context),

                        # the turn's own row rides along (the bridge's carrier, seam 3)
                        provider=context.provider,

                    )

                    

                    if fallback_response.choices and len(fallback_response.choices) > 0:

                        accumulated_content = fallback_response.choices[0].message.content or ""

                        # D.1: the fallback is a provider call in THIS turn.
                        _account_usage(
                            context, service,
                            prompt=_prompt_text(fallback_messages),
                            content=accumulated_content,
                            usage=response_usage(fallback_response),
                        )

                        logger.info(f"✅ Generated fallback response: {len(accumulated_content)} chars")

                    else:

                        logger.warning("⚠️ Fallback response had no choices, using error message")

                        accumulated_content = error_message

                        

                except Exception as e:

                    logger.error(f"❌ Failed to generate fallback response: {e}", exc_info=True)

                    accumulated_content = error_message

                

                # Send error to frontend for logging purposes

                yield f"data: {json.dumps({'error': error_message})}\n\n"

                break



            # Remove blocked calls from execution

            if blocked_calls:

                logger.warning(f"⚠️  {len(blocked_calls)} tool calls blocked, executing {len(filtered_tool_calls)}")



            # Execute tools and update messages

            tool_results = await _execute_tools(

                filtered_tool_calls, context, request_kwargs,

                accumulated_content, logger_service, service,

                accumulated_reasoning=getattr(result, "accumulated_reasoning", "") or "",

            )



            # Record tool execution in tracker

            for tool_call, tool_result in zip(filtered_tool_calls, tool_results):

                context.tool_call_tracker.record_call(

                    tool_name=tool_call["name"],

                    arguments=tool_call.get("parsed_arguments", {}),

                    iteration=iteration,

                    success=tool_result.success,

                    error=tool_result.error,

                    # THE CLASS (the tool-reliability arc, F2): the executor's label
                    # or the handler's declared one — dropped here until now, which
                    # is why failures could not be grouped.
                    error_type=tool_result.error_type,

                )

            # THE NOTEBOOK'S AUTOMATIC CAPTURE (2026-10-13): what this round fetched is
            # recorded into the run's notebook — the model is never asked to remember it.
            _capture_gathered(context, tool_results)



            # Yield tool result chunks

            for tr in tool_results:

                if tr.success:

                    yield f"data: {json.dumps({'tool_result': {'name': tr.tool_name, 'result': str(tr.result), 'success': True}})}\n\n"

                else:

                    # Check if this is a validation error

                    is_validation_error = "Invalid arguments:" in (tr.error or "")

                    

                    if is_validation_error:

                        yield f"data: {json.dumps({

                            'tool_result': {

                                'name': tr.tool_name,

                                'error': tr.error,

                                'success': False,

                                'error_type': 'validation_error'

                            },

                            'validation_notice': {

                                'message': f'Tool {tr.tool_name} received invalid arguments',

                                'action': 'LLM should retry with correct arguments'

                            }

                        })}\n\n"

                        logger.error(f"🚫 Validation error for tool '{tr.tool_name}': {tr.error}")

                    else:

                        yield f"data: {json.dumps({'tool_result': {'name': tr.tool_name, 'error': tr.error, 'success': False}})}\n\n"



            if not tool_results:

                break

        else:

            # THE ANSWER PASS (gap L). Every round went to tool calls: the round's results are in
            # the history and the model was never asked to write from them, so the turn used to end
            # with the stand-in sentence and nothing to show. One more call goes out with the tools
            # withheld, which converts work already paid for into a deliverable.
            #
            # It runs ONLY here. This is the for-loop's `else`, so a round that broke out (no tool
            # calls, every call blocked, a hard plug, a stream failure) never reaches it: an
            # EXHAUSTED loop is the one ending that has collected something to answer from and no
            # way left to say it.
            async for chunk in _stream_answer_pass(
                request_kwargs, context, logger_service, start_time, service,
                result_holder, _output_budget_path(executor_strategy), max_iterations,
            ):
                yield chunk

            _answer_result = result_holder.get("result")
            if _answer_result is None:
                # The withheld-tools call came back empty too. There is nothing to keep and
                # nothing further to try here — the empty-completion retry belongs to the loop,
                # and the loop is over. The stand-in sentence below is the honest ending.
                logger.warning(
                    "🔁 ANSWER PASS session=%s came back empty — the turn keeps what it has and "
                    "says why",
                    context.session_id,
                )
            else:
                accumulated_content = _answer_result.accumulated_content or accumulated_content
                stream_result = _answer_result
                _judge_answer_pass(context, _answer_result, request_kwargs, accumulated_content)

        # ------------------------------------------------------------------
        # Conduit Router — decide shallow / hybrid / delegate
        # ------------------------------------------------------------------
        from app.services.cognitive_pipeline.conduit import (
            DEEP_KEYWORDS, ConduitDecision, Route, conduit_route,
        )

        # A TURN THAT HIT ITS PLUG STARTS NOTHING FURTHER (D.3): the deep pass is
        # another provider call and a delegation is another turn, both for a turn
        # that has already been stopped. It is routed SHALLOW instead, so the
        # decision, the log line below and the branch structure stay exactly as
        # they are — a stopped turn finalises the answer it already has.
        _stopped_state = _turn_state_of(context)

        # THE MEASURED SHORTFALL (the duplicate-answer ruling, 2026-11-20): an answer the provider CUT
        # at the output budget is genuinely insufficient, and the deep pass is the remedy. This is the
        # second half of what replaced the old 500-character test — a fact about the turn, not a guess
        # about how long the text looks. Read from the answer on screen, so an answer pass's own cut
        # counts too.
        _answer_cut_at_budget = getattr(stream_result, "finish_reason", "") == "length"

        decision = (
            ConduitDecision(
                route=Route.SHALLOW,
                reason="the turn was stopped by a hard limit — nothing further started",
            )
            if _stopped_state is not None and _stopped_state.stopped_by_limit
            else conduit_route(
                message=message,
                executor_strategy=executor_strategy,
                accumulated_content=accumulated_content,
                tools_were_used=_twu_ if isinstance(_twu_, bool) else False,
                answer_truncated=_answer_cut_at_budget,
            )
        )
        logger.info(
            "Conduit decision: route=%s reason=%s target_agent=%s",
            decision.route.value, decision.reason, decision.target_agent_id,
        )

        if decision.route == Route.DELEGATE and decision.target_agent_id:
            import httpx
            yield f"data: {json.dumps({'cognitive_delegate_started': {'agent_id': decision.target_agent_id, 'reason': decision.reason}})}\n\n"
            delegate_url = f"http://localhost:8000/api/v1/chat/delegate"
            session_context = accumulated_content or ""
            if request_kwargs and request_kwargs.get("messages"):
                # Extract previous messages for context
                prev_msgs = []
                for m in request_kwargs["messages"][-4:]:  # last 4 messages
                    role = m.get("role", "")
                    text = m.get("content", "")[:200]
                    if text:
                        prev_msgs.append(f"{role}: {text}")
                if prev_msgs:
                    session_context = "\n".join(prev_msgs) + "\n\n" + (accumulated_content or "")
            delegate_payload = {
                "agent_id": decision.target_agent_id,
                "message": message,
                "context": session_context,
            }
            try:
                logger.info("Conduit: delegating to agent %d", decision.target_agent_id)
                async with httpx.AsyncClient(timeout=turn_config.delegate_timeout_s()) as client:
                    resp = await client.post(delegate_url, json=delegate_payload)
                    result = resp.json()
                    if result.get("success"):
                        text = result.get("response", "")
                        yield f"data: {json.dumps({'delegate': {'agent_id': decision.target_agent_id, 'response': text}})}\n\n"
                        yield f"data: {json.dumps({'content': text})}\n\n"
                        accumulated_content = text
                    else:
                        logger.error("Conduit: delegation failed — %s", result.get("error"))
                        yield f"data: {json.dumps({'error': f'Delegation failed: {result.get("error")}'})}\n\n"
            except Exception as e:
                logger.error("Conduit: delegation exception — %s", e)
                yield f"data: {json.dumps({'error': f'Delegation error: {e}'})}\n\n"

        elif decision.route == Route.HYBRID:
            # THE DEEP PASS — this branch IS the implementation. The
            # extracted module (`deep_pass_pipeline.py`) was removed in the
            # token-limit arc's A.3: it was an earlier snapshot, missing the
            # tool loop (the turn-death fix), the reasoning replay and the
            # replace-over-append semantics — adopting it would have
            # regressed all three. One copy, this one.
            #
            # The log names the keyword set from the ROUTER's own constant (`DEEP_KEYWORDS`), not a
            # second spelling of it: the old inline list carried 9 of the 15 words, so a turn routed on
            # "research" or "investigate" logged `matched=[]` — a line that argues with the decision
            # above it. The 500-character `is_short` read is gone with the brevity trigger.
            matched = [kw for kw in DEEP_KEYWORDS if kw in message.lower()]
            logger.info(
                "Conduit: HYBRID pass triggered — matched=%s, cut_at_budget=%s",
                matched, _answer_cut_at_budget,
            )
            accumulated_messages = list(request_kwargs.get("messages", []))
            first_pass_content = accumulated_content or ""
            request_kwargs = build_llm_request(context, stream=True)
            # THE DEBUG (2026-09-01, the Bonsai dig): the request's
            # actual shape — the keys + the api_base/api_key presence.
            logger.info(
                "STREAM-DEBUG kwargs keys=%s api_base=%s api_key=%s model=%s",
                sorted(request_kwargs.keys()),
                bool(request_kwargs.get("api_base")),
                bool(request_kwargs.get("api_key")),
                request_kwargs.get("model"),
            )
            request_kwargs["temperature"] = 0.7
            request_kwargs.pop("tool_choice", None)
            # THE DEEP PASS'S BUDGET (the token-limit arc): written and logged by
            # the resolver like every other path — `max(declared, DEEP_MIN)` and
            # then the reasoning floor (C.3). It used to force 4096 here over
            # both the declaration and the floor, so a thinking driver's deep
            # pass ran below its own floor and the log could not even say so
            # (the declared number was printed instead).
            _apply_output_budget(context, request_kwargs, PATH_DEEP)
            if len(accumulated_messages) > 2:
                request_kwargs["messages"] = accumulated_messages
            elif accumulated_content:
                fresh_msgs = list(request_kwargs["messages"])
                # THE REASONING REPLAY (2026-09-10): the first pass's
                # answer is replayed as an assistant turn — a
                # thinking-mode model wants its thinking back with it.
                _first_pass_turn: Dict[str, Any] = {
                    "role": "assistant", "content": accumulated_content,
                }
                _first_pass_turn.update(
                    reasoning_replay_field(
                        "", getattr(stream_result, "accumulated_reasoning", "") or ""
                    )
                )
                fresh_msgs.append(_first_pass_turn)
                request_kwargs["messages"] = fresh_msgs
            if request_kwargs["messages"] and request_kwargs["messages"][0].get("role") == "system":
                sp = request_kwargs["messages"][0]["content"]
                sp += (
                    "\n\n[Note: The previous answer was insufficient. "
                    "Please provide a thorough, well-reasoned response to the query below. "
                    "Be detailed and comprehensive.]"
                )
                request_kwargs["messages"][0]["content"] = sp
            # THE DEEP-PASS TOOL LOOP (2026-09-09, the Bob turn-death
            # fix): the deep pass's request still carries the agent's
            # tools, so the LLM can legitimately answer with another
            # round of tool calls (continuing an investigation). The
            # old code harvested only accumulated_content and SILENTLY
            # DROPPED those calls — the turn ended on a bare narration
            # ("Let me read his persona...") with nothing executed,
            # which read as a dying agent. Execute + loop, mirroring
            # the main tool loop (bounded by `turn_config.loop_rounds()`).
            deep_holder: dict[str, Any] = {"result": None}
            deep_content_seen = False
            for deep_iter in range(turn_config.loop_rounds()):
                deep_holder["result"] = None
                async for chunk in _stream_llm_response(
                    request_kwargs, context, logger_service, start_time, service, deep_holder,
                    path=PATH_DEEP,
                    # THE DEEP PASS SUPERSEDES THE FIRST (replace-over-append, 2761-2769): every
                    # round's answer is the answer, so the first pass's text goes as soon as this
                    # pass has one of its own.
                    supersedes=True,
                ):
                    yield chunk
                result = deep_holder.get("result")
                if not result:
                    break
                stream_result = result
                # THE LINES (D.2/D.3): the deep pass's own call — the same
                # account, so the turn's totals include both passes.
                _deep_stop = _check_turn_limits(
                    context,
                    stage="deep",
                    call_tokens=getattr(result, "completion_tokens", 0),
                    call_budget=request_kwargs.get("max_tokens"),
                    # THE INPUT SOFT (E.6), the deep pass's own prompt.
                    call_prompt_tokens=getattr(result, "prompt_tokens", None),
                )
                deep_content = getattr(result, "accumulated_content", "") or ""
                if deep_content.strip():
                    deep_content_seen = True
                    # THE REPLACE-OVER-APPEND semantics (2026-09-02,
                    # the Bob DOUBLE-glitch): the deep pass is
                    # prompted with "the previous answer was
                    # insufficient — provide a thorough, well-reasoned
                    # response" — REPLACEMENT semantics. The deep
                    # answer IS the answer; the first pass survives
                    # only as a fallback when the deep pass came back
                    # empty (the last non-empty deep content wins).
                    accumulated_content = deep_content
                # THE HARD PLUG (D.3) at the deep pass's boundary: the deep
                # content above is the newest answer, so a stop keeps THAT, and
                # nothing further is started for this turn.
                _deep_tools = getattr(result, "tool_calls", []) or []
                if _deep_stop is not None:
                    _deep_frame = _stop_turn(
                        context,
                        _deep_stop,
                        mode=_stop_outcome(
                            _deep_stop,
                            pending_work=bool(_deep_tools),
                            result=result,
                            call_budget=request_kwargs.get("max_tokens"),
                        ),
                        stage="deep",
                        partial=accumulated_content,
                    )
                    if _deep_frame:
                        # Same ordering rule as the call boundary above: the
                        # reason for an empty turn must reach the bubble BEFORE
                        # the frame that ends the stream.
                        _say_first = _nothing_to_show_sentence(context, accumulated_content, 0)
                        if _say_first:
                            _said_in_stream = True
                            yield _content_frame(_say_first)
                        yield _deep_frame
                    break
                deep_tools = _deep_tools
                if not deep_tools:
                    break
                # The deep pass wants more tools — guard through the
                # loop/spam tracker, then execute (the main-loop
                # pattern; the tracker covers the whole turn).
                filtered_tool_calls = []
                blocked_calls = []
                for tc in deep_tools:
                    _should_exec, warning_msg, error_msg = context.tool_call_tracker.should_execute(
                        tool_name=tc["name"],
                        arguments=tc.get("parsed_arguments", {}),
                        iteration=deep_iter,
                    )
                    if error_msg:
                        blocked_calls.append(tc)
                        logger.error(f"🚫 Blocked deep-pass tool call: {tc['name']} - {error_msg}")
                    else:
                        filtered_tool_calls.append(tc)
                        if warning_msg:
                            logger.warning(f"⚠️  {warning_msg}")
                if not filtered_tool_calls:
                    logger.error(f"🚫 All {len(deep_tools)} deep-pass tool calls blocked — breaking loop")
                    if blocked_calls:
                        logger.error(f"   Blocked calls: {blocked_calls}")
                    break
                tool_results = await _execute_tools(
                    filtered_tool_calls, context, request_kwargs,
                    accumulated_content, logger_service, service,
                    accumulated_reasoning=getattr(deep_holder.get("result"), "accumulated_reasoning", "") or "",
                )
                for tc, tr in zip(filtered_tool_calls, tool_results):
                    context.tool_call_tracker.record_call(
                        tool_name=tc["name"],
                        arguments=tc.get("parsed_arguments", {}),
                        iteration=deep_iter,
                        success=tr.success,
                        error=tr.error,
                        # The same class the main loop records (F2) — one account,
                        # both loops.
                        error_type=tr.error_type,
                    )

                # The deep pass's round records too — one notebook, both loops.
                _capture_gathered(context, tool_results)
                for tr in tool_results:
                    if tr.success:
                        yield f"data: {json.dumps({'tool_result': {'name': tr.tool_name, 'result': str(tr.result), 'success': True}})}\n\n"
                    else:
                        yield f"data: {json.dumps({'tool_result': {'name': tr.tool_name, 'error': tr.error, 'success': False}})}\n\n"
                if not tool_results:
                    break
            else:
                logger.warning(
                    "Conduit: HYBRID deep pass tool loop exhausted (%d rounds) — "
                    "finalizing with accumulated content (session=%s)",
                    turn_config.loop_rounds(),
                    context.session_id,
                )
                # THE ANSWER PASS (gap L) applies here for the same reason it applies to the main
                # loop: the deep pass's own rounds are collected work it never gets to write from,
                # and keeping the first pass's answer was the best the old code could do. This is
                # the deep pass's OWN request on its own budget path, and what it writes REPLACES
                # the first pass's answer — the deep pass's own semantics.
                async for chunk in _stream_answer_pass(
                    request_kwargs, context, logger_service, start_time, service,
                    deep_holder, PATH_DEEP, turn_config.loop_rounds(),
                ):
                    yield chunk
                _deep_answer = deep_holder.get("result")
                if _deep_answer is not None and (_deep_answer.accumulated_content or "").strip():
                    # The pass wrote, so the deep pass did NOT come back with nothing: the warning
                    # below must not claim it did, and this answer is the pass's.
                    deep_content_seen = True
                    accumulated_content = _deep_answer.accumulated_content
                    stream_result = _deep_answer
                    _judge_answer_pass(context, _deep_answer, request_kwargs, accumulated_content)
            if not deep_content_seen:
                logger.warning(
                    "Conduit: HYBRID deep pass empty — keeping first pass "
                    "(session=%s)", context.session_id,
                )
            logger.info("Conduit: HYBRID pass complete — content_len=%d", len(accumulated_content) or 0)

        else:
            logger.info("Conduit: SHALLOW route — continuing with first pass result")




        # ------------------------------------------------------------------

        # Memory Manager — Store conversation memory

        # ------------------------------------------------------------------

        memory_trace = None

        logger.info("=== MEMORY MANAGER CHECK: accumulated_content=%d chars, type=%s ===", 

                     len(accumulated_content) if accumulated_content else 0,

                     type(accumulated_content).__name__ if accumulated_content else "None")

        if accumulated_content:

            try:

                from app.services.cognitive_pipeline.memory_manager import NoopMemoryManager, run_memory_manager

                from app.services.cognitive_pipeline.models import AgentDescriptor

                

                # Build agent descriptor for memory manager

                mem_agent = AgentDescriptor(

                    id=context.agent_id,

                    name=context.agent_name,

                    description=getattr(context.agent, 'description', '') if hasattr(context.agent, 'description') else '',

                )

                

                # Build pipeline Context from chat context


                pipe_context = PipelineContext(

                    user_message=message,

                    system_prompt=request_kwargs["messages"][0]["content"] if request_kwargs["messages"] else "",

                    agent_name=context.agent_name,

                    agent_description=getattr(context.agent, 'description', '') if hasattr(context.agent, 'description') else '',

                    metadata={"session_id": context.session_id},

                )

                # The `memory` capability's chain — resolved HERE, where the session is. The memory
                # manager is a registered SINGLETON with no session, so the answer is CARRIED on this
                # turn's context (through the `resolve` import the compaction block above already
                # made). The manager used to be constructed with `llama3.2`/`ollama` literals — the
                # reason the `memory` capability had no consumer at all (phase-8's audit).
                from app.services.cognitive_pipeline.memory_manager import MEMORY_CAPABILITY_KEY

                pipe_context.capability_chains = {
                    MEMORY_CAPABILITY_KEY: (
                        await resolve(service.db, MEMORY_CAPABILITY_KEY)
                    ).candidates
                }

                

                # Call memory manager (kv_store) to store this turn

                memory_delta_result, memory_trace = await run_memory_manager(

                    manager=memory_manager if memory_manager is not None else NoopMemoryManager(),

                    context=pipe_context,

                    response=accumulated_content,

                    agent=mem_agent,

                    session_id=str(context.session_id),

                )

                logger.info(

                    f"Memory manager: stored={memory_delta_result.stored_keys}, "

                    f"compaction={memory_delta_result.compaction_triggered}"

                )

            except Exception as e:

                logger.error(f"Memory manager failed: {e}", exc_info=True)

                memory_trace = None



        # ------------------------------------------------------------------

        # Cognitive Pipeline — Executor completed (after LLM streaming)

        # ------------------------------------------------------------------

        # Build a synthetic ComponentTrace for the executor from the stream result

        executor_trace = ComponentTrace(

            strategy=pipeline_config.executor,

            duration_ms=int((time.time() - start_time) * 1000),

            tokens_used=(stream_result.prompt_tokens + stream_result.completion_tokens) if stream_result else 0,

            metadata={

                "chunk_count": stream_result.chunk_count if stream_result else 0,

                "tool_iterations": iteration + 1,

            },

        )

        _topic, _payload = build_executor_completed(str(request.session_id or ""), executor_trace)
        publish(_topic, {**_payload, "kind": "executor_completed"})
        yield sse_from_builder((_topic, _payload))



        # ------------------------------------------------------------------

        # Cognitive Pipeline — Memory Manager (simulated)

        # ------------------------------------------------------------------

        memory_trace = ComponentTrace(

            strategy=pipeline_config.memory_manager,

            duration_ms=0,

            tokens_used=0,

            metadata={

                "compaction_triggered": False,

                "stored_keys": [],

            },

        )

        _topic, _payload = build_memory_updated(str(request.session_id or ""), memory_trace)
        publish(_topic, {**_payload, "kind": "memory_updated"})
        yield sse_from_builder((_topic, _payload))



        # ------------------------------------------------------------------

        # Cognitive Pipeline — Response Formatter (simulated)

        # ------------------------------------------------------------------

        formatter_trace = ComponentTrace(

            strategy=pipeline_config.response_formatter,

            duration_ms=0,

            tokens_used=0,

        )

        _topic, _payload = build_response_formatted(str(request.session_id or ""), formatter_trace)
        publish(_topic, {**_payload, "kind": "response_formatted"})
        yield sse_from_builder((_topic, _payload))



        # 4. Finalize

        # THE TRUNCATION SIGNAL (2026-09-22, Bob's cut-off forecast
        # reports): WHICH stream ended the turn is the one whose stop
        # reason matters — the main loop's last pass, or the conduit's
        # deep pass (it replaces accumulated_content). Both assign
        # `stream_result`; the holder covers the main-loop path.
        _last_result = stream_result or (
            result_holder.get("result") if result_holder else None
        )
        _last_finish_reason = getattr(_last_result, "finish_reason", "") or ""

        # THE LINES (D.2/D.3), one last judgement at the turn's end: the tool
        # count and the clock can only have grown since the last boundary, and
        # the note on the message must reflect the final state. A hard line that
        # crosses HERE (the clock, usually) has nothing left to abort — the turn
        # is already ending — so it rides the note as a stop that kept the answer
        # (D.4: the plug is reported, the answer is not cut).
        _final_stop = _check_turn_limits(context, stage="final")
        _stop_turn(
            context,
            _final_stop,
            mode=STOP_FINISH,
            stage="final",
            partial=accumulated_content,
        )

        # THE SENTENCE FOR A TURN THAT PRODUCED NOTHING (2026-09-23). Two known
        # ways this turn ends with no answer, each with a reason worth persisting
        # — instead of the toast-only, transcript-empty ending the live runs
        # produced (sessions 125 and 127):
        #   * a HARD plug fired before any text arrived (a crossing at a provider
        #     call, so `accumulated_content` is still empty) — the plug's own
        #     sentence is the honest one, and it is already written for the note;
        #   * the tool loop used every round it had and the ANSWER PASS came back with
        #     nothing either (session 125: five rounds, tokens_out=0 — the answer
        #     pass is the call that loop was missing, so reaching here now means the
        #     withheld-tools call produced no answer too).
        # Anything else stays with the empty-message guard in `finalize_response`,
        # which is the honest place for an empty completion nobody can explain.
        _nothing_said: Optional[str] = None
        if not (accumulated_content or "").strip():
            _rounds = (
                len(getattr(context.tool_call_tracker, "call_history", []) or [])
                if context.tool_call_tracker is not None else 0
            )
            _nothing_said = _nothing_to_show_sentence(context, accumulated_content, _rounds)

        metadata = await finalize_response(

            context=context,

            result=StreamResult(

                chunk_count=1, accumulated_content=accumulated_content,

                # THE THINKING SEGREGATION (2026-08-24): carry the
                # last stream result's reasoning into the finalize —
                # the done-event metadata keeps the Thinking fold.
                accumulated_reasoning=(getattr(result_holder.get("result"), "accumulated_reasoning", "") if result_holder and result_holder.get("result") else "") or "",

                # THE TRUNCATION SIGNAL (2026-09-22): the LAST stream's
                # finish_reason — "length" means the provider cut the
                # answer at the output budget. Finalize turns it into
                # the done frame's `truncated` flag (the frontend's
                # truncation notice reads exactly that field).
                finish_reason=_last_finish_reason,

                tool_calls=tool_calls_to_execute, has_content=bool(accumulated_content),

            ),

            tool_results=[],

            request=request,

            service=service,

            db=service.db,

            logger_service=logger_service,

            start_time=start_time,

            final_content=accumulated_content,

            # THE NOTE ON THE MESSAGE (D.2): what the turn crossed rides the done
            # frame's metadata (the bubble reads it) and the saved row (a
            # reloaded turn still says it).
            turn_state=_turn_state_of(context),

            # THE TURN THAT PRODUCED NOTHING (2026-09-23): the sentence to persist
            # instead of an empty message — a turn that stopped and explains why
            # is not silence, and it survives the reload.
            nothing_said=_nothing_said,

            # THE TOOL NUMBERS (the tool-reliability arc, F5): the tracker's summary
            # rides the row's meta AND the done frame's metadata. Passed IN because
            # the row is written inside the finalize — a value added to the returned
            # dict afterwards (where this key used to live) never reached the row and
            # never had a reader.
            tool_summary=(
                context.tool_call_tracker.get_summary()
                if context.tool_call_tracker else None
            ),

        )



        # THE TOOL NUMBERS ride `metadata.metadata` now (the tool-reliability arc,
        # F5): passed into `finalize_response`, which puts them in the done frame's
        # metadata (where the frontend already reads `parsed.metadata`) AND in the
        # saved row. The old line here wrote `metadata["tool_call_summary"]` at this
        # frame's TOP level — a sibling of `metadata`, not a member of it — which no
        # reader ever looked at and which the row never received.

        # THE THINKING SEGREGATION (2026-08-24): the accumulated
        # reasoning rides the message metadata — the frontend renders
        # the collapsible Thinking fold from it (the reloaded
        # messages keep the fold too). The LAST stream result's
        # reasoning is the final turn's thinking.
        _reasoning = getattr(locals().get("result"), "accumulated_reasoning", "") or ""
        _reasoning = _reasoning if isinstance(_reasoning, str) else "" ""
        if _reasoning:
            metadata["reasoning"] = _reasoning



        # ------------------------------------------------------------------

        # Cognitive Pipeline — Full trace event at end

        # (Emitted BEFORE the final "done" event so the frontend

        #  can process cognitive_trace_complete before the stream ends)

        # ------------------------------------------------------------------

        cognitive_result = CognitiveResult(

            response=accumulated_content,

            trace=CognitiveTrace(

                context_builder=cb_trace,

                executor=executor_trace,

                memory_manager=memory_trace,

                response_formatter=formatter_trace,

            ),

        )

        # Fill metrics.tool_calls from REAL sources BEFORE emitting
        # and persisting, so both the SSE trace event and the DB
        # carry the truth. The cognitive pipeline's executors never
        # set tool_calls (acompletion without tools=); the
        # ToolCallTracker here counts every executed tool call.
        # tool_iterations is the fallback when no tracker exists
        # (delegate/stub paths). Before this (2026-08-14)
        # metrics.tool_calls was always 0 even for tool-using
        # conversations — the number existed but was never lifted.
        try:
            _populate_tool_calls_metric(
                cognitive_result, context.tool_call_tracker, executor_trace
            )
        except Exception:
            pass  # metric fill is best-effort

        _topic, _payload = build_trace_complete(str(request.session_id or ""), cognitive_result)
        publish(_topic, {**_payload, "kind": "trace_complete"})
        yield sse_from_builder((_topic, _payload))
        # Persist pipeline trace to dedicated database
        try:
            from app.services.cognitive_pipeline.trace_store import save_trace
            save_trace(cognitive_result, session_id=context.session_id)
        except Exception:
            pass  # Trace persistence is best-effort



        # THE EMPTY-GUARD NOTICE (2026-09-10, the user's "she died
        # again, no warning or messages"): finalize refused to persist
        # an empty assistant message — the refusal is correct, but a
        # turn that produces NOTHING must not end in silence. Emit the
        # `event: error` frame the frontend already renders (toast +
        # onStreamError) and carry the machine-readable
        # `empty_guard`/`notice` keys on the final payload. This MUST
        # precede the final done frame: the frontend stops reading the
        # stream on the error frame.
        if metadata.get("empty_guard"):
            yield build_empty_completion_event(context)

        # THE SENTENCE THE TURN STOOD IN FOR (2026-09-23): when the turn had no
        # answer and said why, the reason is already on the saved row (finalize
        # persisted it as the message) — but the bubble the user is LOOKING AT is
        # built from the streamed chunks, so a reason that only appears after a
        # reload is no answer to "what just happened?". Streamed here, before the
        # done frame, as an ordinary content chunk. A live run without this
        # showed an empty assistant bubble next to a correct row.
        if _nothing_said and not _said_in_stream:
            yield _content_frame(_nothing_said)

        yield f"data: {json.dumps(metadata)}\n\n"



    except Exception as e:

        async for chunk in handle_streaming_error(

            error=e, context=context, service=service,

            logger_service=logger_service, start_time=start_time,

        ):

            yield chunk

        # Emit trace complete on error so frontend indicators stop
        error_trace = CognitiveTrace()
        error_result = CognitiveResult(
            response="",
            trace=error_trace,
            error=str(e),
        )
        _topic, _payload = build_trace_complete(str(request.session_id or ""), error_result)
        publish(_topic, {**_payload, "kind": "trace_complete"})
        yield sse_from_builder((_topic, _payload))

    finally:
        # THE TURN'S ACCOUNT (Phase D.1): reported once, from the last thing
        # that always runs — a turn that died, was aborted mid-stream or was
        # closed by the client still says what it spent. The tool-call number
        # is MIRRORED from the tracker here (it is the tracker's count), and
        # nothing in this block may raise into the stream.
        _report_turn_account(context)






async def _resolve_pipeline_config(

    db: AsyncSession,

    context: ChatContext,

) -> PipelineConfig:

    """Resolve the effective PipelineConfig from the agent's cognitive profile.



    Resolution order:

    1. PipelineConfig code defaults

    2. Agent-level Cognitive Profile (from DB)

    """

    from sqlalchemy import select as _select

    config = PipelineConfig()

    agent = getattr(context, 'agent', None)

    if agent is None:

        return config



    cognitive_profile_id = getattr(agent, 'cognitive_profile_id', None)

    if cognitive_profile_id is not None:

        from app.infrastructure.database.models import CognitiveProfile

        from sqlalchemy.orm import selectinload

        stmt = (

            _select(CognitiveProfile)

            .options(selectinload(CognitiveProfile.memory_profile))

            .where(CognitiveProfile.id == cognitive_profile_id)

        )

        result = await db.execute(stmt)

        profile = result.scalar_one_or_none()

        if profile:

            config.context_builder = profile.context_builder

            config.executor = profile.executor

            config.memory_manager = (

                profile.memory_profile.strategy

                if profile.memory_profile else "default"

            )

            config.response_formatter = profile.response_formatter

            config.memory_profile_persistence = (

                profile.memory_profile.persistence

                if profile.memory_profile else "memory"

            )

            # Get agent folder for per-agent memory path

            agent_obj = getattr(context, 'agent', None)

            if agent_obj:

                config.agent_folder = getattr(agent_obj, 'folder', None)

            config.compaction_threshold = (
                profile.memory_profile.compaction_threshold
                if profile.memory_profile else None
            )
            config.summarization_enabled = (
                profile.memory_profile.summarization
                if profile.memory_profile else False
            )

    return config





# THE ANSWER PASS'S INSTRUCTION (gap L). It says the round budget is spent and the tool results
# above are everything, because a withheld-tools call is otherwise free to apologise for not being
# able to search again. The wording mirrors the blocked-tools path ("respond directly with a
# helpful text answer ... Do NOT attempt to call any tools") so a turn reads the same however it
# reached its limit.
ANSWER_PASS_PROMPT = (
    "You have used every tool round this turn had, so no further tool calls are possible. "
    "The tool results above are everything available. Answer the user's request now, in full, "
    "from what you have already collected."
)


def _judge_answer_pass(
    context: Any, result: Any, request_kwargs: Dict[str, Any], partial: str
) -> None:
    """Judge the answer pass's own call — and FINISH the turn if a hard line fell (gap L).

    The pass is the turn's LAST provider call, so a breach here has nothing further to start: the
    plug finishes the turn (D7 (b)) — the answer is kept whole, the crossing is recorded on the
    account (the note on the message and a reloaded row read it) and no frame is emitted, because
    only an ABORT has one (`_stop_turn`). Without this the crossing would be recorded a call later
    at the turn's end and this call's own soft lines (the output and input softs are CALL-scoped)
    would never be judged.
    """
    verdict = _check_turn_limits(
        context,
        stage="answer",
        call_tokens=getattr(result, "completion_tokens", 0),
        call_budget=request_kwargs.get("max_tokens"),
        call_prompt_tokens=getattr(result, "prompt_tokens", None),
    )
    if verdict is not None:
        _stop_turn(context, verdict, mode=STOP_FINISH, stage="answer", partial=partial)


async def _stream_answer_pass(
    request_kwargs: Dict[str, Any],
    context: ChatContext,
    logger_service: ChatLoggingService,
    start_time: float,
    service: ChatService,
    result_holder: Optional[Dict],
    path: str,
    rounds: int,
    # THE ANSWER PASS BY DEFINITION REPLACES WHAT THE LOOP HAD (gap L): the rounds were work, this
    # call is the deliverable. Default true because there is no other reason to run it.
    supersedes: bool = True,
) -> AsyncGenerator[str, None]:
    """Ask for the answer with the tools withheld — the loop's last round, given a voice (gap L).

    A tool loop can end with every round spent on tool calls: the results sit in the history and
    the model was never asked to write from them, so the turn used to end with the stand-in
    sentence and nothing to show (four live turns: 249,377 input tokens, 77 tool calls, no answer).
    This is the call that writes from work already paid for.

    The request is a COPY of the turn's, for two reasons: the appended instruction must not leak
    into the history the conduit's deep pass reuses, and the turn's own request must stay
    unchanged. `tools` and `tool_choice` are POPPED rather than set to `None` — the streamer names
    every tool it sends (`[t['function']['name'] for t in sent_tools]`) and raises on `None`.

    It streams through the ordinary helper, so the answer arrives in the bubble as it is written,
    the call is counted in the turn's account, and it runs on the budget path already resolved for
    this pass: the account's path label and the budget log must never name two paths (D.1).
    """
    answer_kwargs: Dict[str, Any] = {
        **request_kwargs,
        "messages": list(request_kwargs.get("messages") or []),
    }
    answer_kwargs.pop("tools", None)
    answer_kwargs.pop("tool_choice", None)
    answer_kwargs["messages"].append({"role": "system", "content": ANSWER_PASS_PROMPT})

    logger.info(
        "🔁 ANSWER PASS session=%s path=%s — the tool loop used all %d rounds without writing; "
        "asking for the answer with the tools withheld",
        context.session_id, path, rounds,
    )
    if result_holder is not None:
        result_holder["result"] = None
    async for chunk in _stream_llm_response(
        answer_kwargs, context, logger_service, start_time, service, result_holder, path=path,
        supersedes=supersedes,
    ):
        yield chunk


def _backup_request(request_kwargs: Dict[str, Any], candidate: Any) -> Dict[str, Any]:
    """The turn's request, rebuilt for a BACKUP candidate (R3).

    Everything the turn built stays — the messages (including the answer pass's appended
    instruction), the tools, the budget, `tool_choice`. Only what NAMES and AUTHENTICATES the
    provider is replaced:

    * the model string goes through the app's ONE mapping (`litellm_route.litellm_model_string`), so
      the ollama / llama remaps apply to a backup too;
    * the primary's `api_base` / `api_key` / `extra_headers` are DROPPED — a backup on another
      provider must never be handed the previous provider's endpoint or credentials;
    * an alias-mapped local server (the `llama` row) gets its own `api_base` and the keyless
      placeholder the openai adapter needs.

    NAMED GAP: a backup whose provider needs more than the alias map (the `ollama_cloud` Bearer
    header, keyed on the row's `ollama.com` base_url) is not rebuilt that far — `build_llm_request`
    is the one place that knows it, and it reads a prepared CONTEXT rather than a candidate. A cloud
    backup therefore rides litellm's own env lookup, exactly as the executor's fallbacks do.
    """
    from app.domain.providers.litellm_route import api_base_for, litellm_model_string

    provider = candidate.provider or ""
    model = candidate.model or ""
    kwargs = dict(request_kwargs)
    kwargs["model"] = litellm_model_string(provider, model, candidate.provider_type)
    for stale in ("api_base", "api_key", "extra_headers"):
        kwargs.pop(stale, None)
    # THE ROOT THE CANDIDATE ALREADY CARRIES (2026-10-12, stage 2): the resolver filled `endpoint`
    # from the row it held, so a backup needs no table and no lookup of its own.
    alias_base = candidate.endpoint
    if alias_base:
        # THE HANDLER's ROOT, not the alias's value verbatim (2026-10-11): this function's model
        # string may be the ollama family's `ollama_chat` handler, which composes `{api_base}/api/chat`
        # itself — so an alias carrying the compat root (`https://ollama.com/v1`) was dialled as
        # `https://ollama.com/v1/api/chat`, a measured 404, for every `ollama_cloud` BACKUP. The
        # alias stays the source of the endpoint; the root is derived from it.
        kwargs["api_base"] = api_base_for(kwargs["model"], alias_base)
        from app.domain.providers.llm_factory import placeholder_key_for
        _placeholder = placeholder_key_for(kwargs["api_base"], kwargs.get("model"))
        if _placeholder:
            kwargs["api_key"] = _placeholder

    return kwargs


async def _open_stream_with_failover(
    request_kwargs: Dict[str, Any],
    context: ChatContext,
    *,
    path: str,
    db: Any = None,
) -> Any:
    """Open the turn's stream, walking the turn's resolved chain while the attempt is OPENING (R3).

    A provider REFUSES at the open — a dead endpoint, a model the provider does not serve, a
    rejected key — so that is where the chain applies. Once a chunk has arrived there is nothing to
    fail over: the user has already read text, so the turn finishes (or fails) on the attempt that
    answered.

    The candidates ride the `ChatContext` (resolved in `generate_stream`, where the session is), and
    the walk itself is the shared `capabilities.attempt_chain` — so a failure is logged with its
    provider, its model and WHICH attempt it was, exactly as on the executor path.
    `fallback_enabled` keeps its meaning: OFF = the primary only, fail visibly. An empty chain means
    no resolver reading was supplied: the request is the single attempt, as before the arc.
    """
    import asyncio

    from .llm_utils import acompletion_with_retry
    from app.domain.providers.capabilities import SOURCE_AGENT, ServiceCandidate, attempt_chain

    candidates: tuple[Any, ...] = tuple(getattr(context, "candidates", None) or ())
    if not candidates:
        candidates = (
            ServiceCandidate(
                ordinal=0, provider=context.provider, model=context.model, source=SOURCE_AGENT
            ),
        )

    async def _open(candidate: Any) -> Any:
        kwargs = (
            dict(request_kwargs)
            if candidate.ordinal == 0  # the primary rides the request the turn already built
            else _backup_request(request_kwargs, candidate)
        )
        # THE TURN'S ACCOUNT (D.1): EVERY attempt is a provider call this turn made.
        _account_provider_call(context, path)
        logger.info(
            "🔁 stream open attempt %d (%s) model=%s",
            candidate.ordinal,
            "primary" if candidate.ordinal == 0 else f"backup #{candidate.ordinal}",
            kwargs.get("model"),
        )
        # THE PRICE RIDES THE ATTEMPT (2026-10-08): a fallback answers with ITS OWN model, so this is
        # resolved per candidate rather than once for the turn. `db` is None where the caller has no
        # session — a path that is not a turn has no price to look up, and none to claim.
        pricing = None
        if db is not None:
            from app.domain.providers.cache_service import ProviderModelCacheService

            pricing = await ProviderModelCacheService().pricing_for_model(
                db, candidate.provider or "", candidate.model or ""
            )

        return await asyncio.wait_for(
            acompletion_with_retry(
                **kwargs,
                on_attempt=_retry_observer(context),
                pricing=pricing,
                # THE ROW THIS ATTEMPT WENT TO (the bridge's carrier, seam 3): the chain walk knows
                # which candidate it is opening, so a failed attempt can name the service it failed on
                # instead of one inferred from an address.
                provider=candidate.provider,
            ),
            timeout=turn_config.stream_timeout_s(),
        )

    outcome = await attempt_chain(
        candidates,
        call=_open,
        capability="chat",
        fallbacks=bool(getattr(context.agent, "fallback_enabled", False)),
    )
    return outcome.response


async def _stream_llm_response(

    request_kwargs: Dict[str, Any],

    context: ChatContext,

    logger_service: ChatLoggingService,

    # REMOVAL CONDITION: delete once the call sites stop passing it. The call takes its own clock
    # (`call_start_time`, where the request is issued), so the turn's start is no longer read here
    # — it is kept only so this fix stayed inside one function, and the four call sites can drop
    # their argument together.
    start_time: float,

    service: ChatService,

    result_holder: Dict | None = None,

    # The run path this call's budget came from (`fast` / `pass1` / `deep` /
    # `default`) — reused as the accounting's path label, so the account and the
    # budget log can never name two different paths (Phase D.1).
    path: str = "",

    # WHETHER THIS CALL'S TEXT SUPERSEDES THE ANSWER ON SCREEN. Every one of these calls becomes the
    # turn's `accumulated_content`, so the row and the bubble part company unless the client is told to
    # drop what it holds. The frame is emitted below, lazily, before this call's first content chunk.
    supersedes: bool = False,

) -> AsyncGenerator[str, None]:

    """

    Stream LLM response and yield chunks in real-time.



    Args:

        result_holder: Optional dict to store StreamResult after streaming



    Yields:

        SSE-formatted chunk strings

    """

    try:

        # A STALE ERROR MUST NOT OUTLIVE ITS ATTEMPT (2026-09-29): the holder is reused across a
        # turn's calls (the empty-completion retry, the answer pass), and the fallback below reads
        # `stream_error` to decide whether the APP can name the failure. Clearing it here means a
        # successful call never leaves the previous failure behind to be reported as this one's.
        if result_holder is not None:
            result_holder.pop("stream_error", None)





        # Debug: log what tools are being sent

        sent_tools = request_kwargs.get("tools", [])

        # THE DENOMINATOR (the tool-reliability arc, F1): counted HERE, where the
        # offered list actually exists — the same list the log line below prints.
        _account_tools_offered(context, sent_tools)

        logger.info(f"🔍 Sending LLM request with {len(sent_tools)} tools: {[t['function']['name'] for t in sent_tools]}")

        logger.info(f"🔍 tool_choice: {request_kwargs.get('tool_choice', 'not set')}")



        # Add timeout to prevent hanging — THE REASONING-ERA RAISE
        # (2026-08-22, the ox sweep runs): 60s killed every mid-plan
        # run — a reasoning model thinks 20-140s+ before the first
        # token. 300s lets a slow first token arrive; the stream
        # timeout below guards the whole call.

        # THE CALL'S OWN CLOCK (2026-10-08). `start_time` is the TURN's start, and the first-chunk
        # wait used to be measured against it — so a turn's second call reported the whole elapsed
        # turn as its own "time to first chunk", which is neither what the field says nor something
        # a reader can act on. The wait is a property of THE CALL, so it starts where the request is
        # issued. (`stream_start_time` below is a third clock, bounding the ITERATION.)
        call_start_time = time.time()

        # THE CHAIN AT THE OPEN (R3, the service-capability arc's phase 3): a provider REFUSES
        # here — a dead endpoint, a model it does not serve, a rejected key — so the turn's
        # resolved chain is walked while the attempt is still opening. The shared loop logs every
        # failed attempt with its provider, model and ordinal, and the last failure is what the
        # caller reports (unchanged); `fallback_enabled=False` keeps it to one attempt.
        stream = await _open_stream_with_failover(
            request_kwargs, context, path=path, db=getattr(service, "db", None)
        )

        logger_service.log_stream_started(context, type(stream).__name__)



        accumulated_content = ""

        accumulated_reasoning = ""

        tool_calls_to_execute = []

        # Buffer for streaming tool call accumulation.

        # In streaming mode, tool call data arrives across many delta chunks:

        #   chunk 1: {index:0, id:"call_xyz", function:{name:"calculator", arguments:""}}

        #   chunk 2: {index:0, id:None,       function:{name:None,         arguments:'{"expression":'}}

        #   chunk 3: {index:0, id:None,       function:{name:None,         arguments:'"2+2"}'}}

        # We accumulate by index, then parse the full JSON once streaming ends.

        tool_call_buffer: Dict[int, Dict[str, Any]] = {}

        chunk_count = 0

        invalid_chunks = 0

        # THE TRUNCATION SIGNAL (2026-09-22, Bob's cut-off forecast
        # reports): the provider says WHY the stream ended in
        # choices[0].finish_reason — "length" is "I had more to write
        # and hit max_tokens", i.e. the answer was CUT MID-SENTENCE.
        # The streamer used to read only content/tool_calls, so a cut
        # answer was indistinguishable from a finished one: the saved
        # row, the done frame and the bubble all read as complete, and
        # the user had no way to tell (nor did the log). Capture the
        # LAST value the stream carries and hand it to the caller.
        finish_reason = ""

        has_content = False

        has_tool_calls = False

        prompt_tokens = 0

        completion_tokens = 0

        first_chunk_time = None

        last_chunk_time = None

        stream_start_time = time.time()



        # THE REPLACE, ARMED (the duplicate-answer fix): the flag is spent on this call's first
        # content chunk — see `_replace_frame`. A call that streams no content never spends it, so
        # nothing on screen is cleared for an answer that never arrived.
        _replace_pending = supersedes

        async for chunk in stream:

            chunk_count += 1

            chunk_time = time.time()



            # Check for stream timeout (300 seconds max — the
            # reasoning-era raise, 2026-08-22: 90s killed Ox streams
            # that legitimately take 2-5 min for a long reasoning turn)

            elapsed = chunk_time - stream_start_time

            if elapsed > 300.0:

                logger.error(f"❌ Stream timed out after {elapsed:.1f}s (>300s limit)")

                raise TimeoutError(f"Stream timed out after {elapsed:.1f} seconds")



            # Track first chunk

            if first_chunk_time is None:

                first_chunk_time = chunk_time

                # THE CALL'S WAIT, not the turn's — measured from where THIS call issued its
                # request, so the second and later calls of a turn report their own latency
                # instead of the elapsed turn wearing a per-call label.
                ttfc = (chunk_time - call_start_time) * 1000

                logger_service.log_first_chunk(context.session_id, ttfc, context.model, context.provider)



            last_chunk_time = chunk_time



            # Validate chunk

            # EXTRACT USAGE FIRST (2026-10-08): a provider that reports usage only when asked
            # (the funnel asks — `stream_options.include_usage`) sends it on a FINAL frame that
            # carries no choices, so reading it after the guard below would never see it.
            # Read whatever the chunk carries; then decide whether it is renderable.
            if hasattr(chunk, 'usage') and chunk.usage:

                prompt_tokens = getattr(chunk.usage, 'prompt_tokens', prompt_tokens)

                completion_tokens = getattr(chunk.usage, 'completion_tokens', completion_tokens)

            if not hasattr(chunk, 'choices') or not chunk.choices:

                # A USAGE-ONLY chunk is the provider's FINAL frame, not a malformed one: it
                # arrives on every streamed call now that the funnel asks for
                # `stream_options.include_usage` (llm_utils). Counting it as "invalid" would
                # both inflate a health field on every turn and hide a genuinely broken chunk.
                if getattr(chunk, 'usage', None):

                    continue

                invalid_chunks += 1

                continue



            delta = chunk.choices[0].delta

            # THE TRUNCATION SIGNAL (2026-09-22): the final chunk of a
            # budget-cut stream carries finish_reason="length" (a clean
            # stop carries "stop"). Keep the last non-empty value — the
            # stream's own verdict on whether it FINISHED or was CUT.
            _finish = getattr(chunk.choices[0], 'finish_reason', None)
            if _finish:
                finish_reason = str(_finish)

            # REASONING-SHAPE DEBUG (2026-08-22, the ox smoke test): the
            # deep-pass query on ox-alpha streams thinking + answers in
            # reasoning fields, but this streamer only reads content +
            # tool_calls -> has_content=False, empty replies. Capture the
            # real delta shape on the first chunk (evidence before patch).
            if chunk_count == 1:
                try:
                    _attrs = [a for a in dir(delta) if not a.startswith('_')]
                    logger.info("CHUNK-RAW: delta attrs=%s repr=%s", _attrs, repr(chunk)[:250])
                except Exception as _e:
                    logger.info("CHUNK-RAW log failed: %s", _e)



            # Detect tool calls — accumulate arguments across streaming chunks by index

            if hasattr(delta, 'tool_calls') and delta.tool_calls:

                has_tool_calls = True

                for tc in delta.tool_calls:

                    if hasattr(tc, 'function') and tc.function:

                        index = getattr(tc, 'index', 0) or 0

                        name = getattr(tc.function, 'name', None)

                        args_fragment = getattr(tc.function, 'arguments', None) or ""

                        tid = getattr(tc, 'id', None)



                        # Initialise buffer slot on first sight of this index

                        if index not in tool_call_buffer:

                            tool_call_buffer[index] = {"id": None, "name": None, "arguments": ""}



                        if tid:

                            tool_call_buffer[index]["id"] = tid

                        if name:

                            tool_call_buffer[index]["name"] = name

                            # Yield tool_call event to frontend when name first appears

                            logger.debug(f"🔧 Tool call started: {name} (index={index})")

                            yield f"data: {json.dumps({'tool_call': {'id': tid, 'name': name, 'arguments': ''}})}\n\n"

                        # Always accumulate argument fragments

                        tool_call_buffer[index]["arguments"] += args_fragment

                        logger.debug(f"🔧 Tool call args[{index}] fragment: {args_fragment!r}, cumulative: {tool_call_buffer[index]['arguments']!r}")



            # Accumulate content and yield in real-time

            if hasattr(delta, 'content') and delta.content:

                if _replace_pending:

                    _replace_pending = False

                    yield _replace_frame()

                accumulated_content += delta.content

                has_content = True

                # THE RESTORED CONTENT YIELD (2026-08-24, the user's
                # live catch): the timeout raise
                # DELETED this yield while adding the reasoning
                # yields — normal models (llama3.2 via ollama,
                # deepseek) stream delta.content, and without this
                # they accumulate but NEVER stream to the frontend
                # (the bubble stayed empty; 'Final response: N chars'
                # in the log was the accumulation only). The
                # reasoning branches yield below; the content branch
                # yields here — the same SSE shape.
                yield f"data: {json.dumps({'choices': [{'index': 0, 'delta': {'content': delta.content}, 'finish_reason': None}]})}\n\n"
            # REASONING-MODEL STREAMS (2026-08-22, the ox smoke test):
            # thinking-first models (ox-alpha, R-series) stream the
            # answer in delta.reasoning / delta.reasoning_content with
            # content='' — without this the stream yields ZERO text.
            # The reasoning text IS the visible answer for these
            # providers (the final content chunk, if any, appends on top).
            # THE SUMMARY FIX (2026-08-22, the user): the reasoning text
            # must YIELD as SSE chunks too — accumulation alone left the
            # frontend bubble empty (the text reached the DB but never
            # the stream).
            # THE THINKING SEGREGATION (2026-08-24, the user's ask):
            # the reasoning tokens accumulate SEPARATELY and yield
            # with their own field — the frontend renders them behind
            # the collapsible Thinking fold, the bubble carries only
            # the clean answer. (The pre-2026-08-24 behavior merged
            # them into the content — the narration leak.)
            elif hasattr(delta, 'reasoning') and delta.reasoning:
                accumulated_reasoning += str(delta.reasoning)
                yield f"data: {json.dumps({'choices': [{'index': 0, 'delta': {'content': '', 'reasoning': str(delta.reasoning)}, 'finish_reason': None}]})}\n\n"
            elif hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                accumulated_reasoning += str(delta.reasoning_content)
                yield f"data: {json.dumps({'choices': [{'index': 0, 'delta': {'content': '', 'reasoning': str(delta.reasoning_content)}, 'finish_reason': None}]})}\n\n"



        # THE CALL'S TOKENS (Phase D.1): the provider's own usage when it sent
        # any, otherwise the app's estimate, MARKED as an estimate — several
        # local servers omit streaming usage entirely.
        _account_usage(
            context, service,
            prompt=_prompt_text(request_kwargs.get("messages")),
            content=accumulated_content,
            usage=(
                (prompt_tokens, completion_tokens)
                if (prompt_tokens or completion_tokens) else None
            ),
        )

        # Finalise tool calls — parse accumulated argument strings from buffer

        for idx in sorted(tool_call_buffer.keys()):

            tc_data = tool_call_buffer[idx]

            tc_name = tc_data["name"]

            tc_args_str = tc_data["arguments"]

            tc_id = tc_data["id"]

            if tc_name:

                try:

                    parsed = json.loads(tc_args_str) if tc_args_str else {}

                except Exception:

                    logger.warning(f"⚠️  Could not parse tool call arguments for {tc_name!r}: {tc_args_str!r}")

                    parsed = {}

                tool_calls_to_execute.append({

                    "id": tc_id,

                    "name": tc_name,

                    "arguments": tc_args_str,

                    "parsed_arguments": parsed,

                })

                logger.debug(f"🔧 Tool call finalised: {tc_name} args={parsed}")



        # Debug: log streaming summary

        logger.info(f"🔍 Streaming summary: chunks={chunk_count}, has_content={has_content}, has_tool_calls={has_tool_calls}")

        logger.info(f"🔍 Tool buffer: {tool_call_buffer}")

        logger.info(f"🔍 Content accumulated: {accumulated_content[:200]!r}")

        # THE TRUNCATION WARNING (2026-09-22): a stream that ended on
        # the output budget is CUT, not finished — say so in the log
        # with the budget that cut it, so a truncated answer is
        # attributable from the log alone (it never was before).
        if finish_reason == "length":
            # THE TRUNCATION RECORD (2026-09-22): the log line carries the
            # whole comparison a designer needs — how much text arrived,
            # what the budget was, and which model spent it — so the
            # budget question can be answered from the log alone.
            from app.domain.chat.token_budget import estimate_tokens

            _content_tokens = estimate_tokens(accumulated_content)
            _budget = request_kwargs.get("max_tokens")
            logger.warning(
                "⚠️  OUTPUT TRUNCATED (finish_reason=length) session=%s model=%s "
                "provider=%s content=%d chars (~%d tokens) of max_tokens=%s chunks=%d "
                "— the answer was cut at the output budget; the done frame reports "
                "truncated=True and the user is told",
                context.session_id, context.model, context.provider,
                len(accumulated_content), _content_tokens, _budget, chunk_count,
            )
        elif not finish_reason and (accumulated_content or has_tool_calls):
            # THE OTHER HALF OF THE SIGNAL (2026-09-22): a well-behaved
            # provider always closes a stream with a stop reason. A
            # stream that produced content and then went quiet anyway
            # ended ABNORMALLY (provider closed the connection, or the
            # provider never sends finish_reason at all — some local
            # servers). Log-only, no user-visible claim: with no stop
            # reason there is no proof of a cut, but this is the line
            # that tells the next investigation which one happened.
            logger.warning(
                "STREAM ENDED WITHOUT A STOP REASON session=%s model=%s provider=%s "
                "content=%d chars chunks=%d — ended early (connection closed) or "
                "this provider omits finish_reason; a cut answer cannot be ruled out",
                context.session_id, context.model, context.provider,
                len(accumulated_content), chunk_count,
            )



        # Build timing

        # The CALL's clock, matching the TTFC logged above — the turn's own duration belongs to the
        # caller (`report()`'s `duration_ms`), not to this struct.

        timing = StreamTiming(start_time=call_start_time, first_chunk_time=first_chunk_time, last_chunk_time=last_chunk_time)



        # Build result

        result = StreamResult(

            chunk_count=chunk_count, accumulated_content=accumulated_content,

            accumulated_reasoning=accumulated_reasoning,

            tool_calls=tool_calls_to_execute, has_content=has_content,

            timing=timing, invalid_chunks=invalid_chunks,

            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,

            finish_reason=finish_reason,

        )



        logger_service.log_stream_completed(context, result)



                # Store result for caller
        if result_holder is not None:
            # THE EMPTY-COMPLETION FLAG (2026-09-02, the Bob empty-
            # bubble bug): an empty completion (chunks but NO content
            # and NO tool calls — the model returned zero tokens) is
            # NOT a usable result. The holder carries the flag; the
            # main loop RETRIES once (transparently — nothing
            # user-visible was streamed yet) and only surfaces the
            # no_content error when the retry also comes back empty.
            if accumulated_content or has_tool_calls:
                result_holder["result"] = result
                result_holder["empty_completion"] = False
            else:
                result_holder["result"] = None
                result_holder["empty_completion"] = True
                result_holder["empty_chunk_count"] = chunk_count
                result_holder["empty_invalid_chunks"] = invalid_chunks
                logger.error(
                    "EMPTY COMPLETION DETECTED session=%s model=%s provider=%s "
                    "chunks=%d invalid=%d content=%d reasoning=%d tool_calls=%d — "
                    "the main loop will retry once",
                    context.session_id, context.model, context.provider,
                    chunk_count, invalid_chunks, len(accumulated_content),
                    len(accumulated_reasoning), len(tool_calls_to_execute),
                )

        return

    except Exception as e:

        logger_service.log_stream_open_failed(context, e)

        # THE ERROR REACHES THE CALLER (2026-09-29): the frame yielded below tells the USER where
        # the failure is (a toast carrying the same sentence); the holder tells the LOOP, so it can
        # state it too instead of asking the model to explain a failure it cannot see.
        if result_holder is not None:
            result_holder["stream_error"] = e

        async for error_chunk in handle_streaming_error(e, context, service, logger_service, start_time):

            yield error_chunk





async def _execute_tools(

    tool_calls: List[Dict[str, Any]],

    context: ChatContext,

    request_kwargs: Dict[str, Any],

    accumulated_content: str,

    logger_service: ChatLoggingService,

    service: ChatService,

    accumulated_reasoning: str = "",

) -> List[ToolExecutionResult]:

    """Execute tool calls and update messages for next iteration.

    

    SMART TOOL EXECUTION:

    - Executes tools and captures results

    - If tool succeeds but LLM might not understand, adds explanatory message

    - Limits retries to prevent loops

    """

    logger_service.log_tool_execution_loop(len(tool_calls))



    tool_results = await execute_tool_calls(

        tool_calls=tool_calls, agent_id=context.agent_id,

        session_id=context.session_id, db=service.db, logger_service=logger_service,

    )



    # Build tool messages for next iteration
    # THE REASONING REPLAY (2026-09-10): the iteration's own thinking
    # rides the assistant tool-call message — the follow-up request of
    # a thinking-mode API must echo it back or DeepSeek 400s.
    tool_messages = build_tool_messages(
        accumulated_content, tool_calls, tool_results,
        accumulated_reasoning=accumulated_reasoning,
    )

    request_kwargs["messages"] = request_kwargs.get("messages", []) + tool_messages



    # SMART: Add explanatory message if tool was called with empty/wrong args

    # This helps LLM understand it already got the answer

    # Also handle tool failures explicitly including capability errors

    for tool_call, tool_result in zip(tool_calls, tool_results):

        tool_name = tool_call.get("name", "")

        args = tool_call.get("parsed_arguments", {})



        # HANDLE TOOL SUCCESS - Remind LLM of original task and prompt continuation

        if tool_result.success:

            # Find the original user message to restore context.

            # Scan reversed so we get the *most recent* user message

            # (the current request), not the first one from conversation history.

            original_user_msg = ""

            for msg in reversed(request_kwargs["messages"]):

                if msg.get("role") == "user" and not msg.get("content", "").startswith("[System:"):

                    original_user_msg = msg["content"]

                    break



            if original_user_msg:

                success_message = {

                    "role": "user",

                    "content": (

                        f"[System: The {tool_name} tool completed successfully. "

                        f"Your original request was: '{original_user_msg}'. "

                        f"Continue with the next step. Do not repeat the same tool call.]"

                    )

                }

            else:

                success_message = {

                    "role": "user",

                    "content": (

                        f"[System: The {tool_name} tool completed successfully. "

                        f"Continue with your task. Do not repeat the same tool call.]"

                    )

                }

            request_kwargs["messages"].append(success_message)

            logger.debug(f"📝 Added success hint to LLM: {success_message['content'][:100]}...")



        # If datetime tool was called with empty args, add a hint

        if tool_name == "datetime" and (not args or len(args) == 0):

            logger.info("🕐 DateTime tool called without args - result provided. Adding hint for LLM.")

            # Add a user-style hint message to help LLM understand

            hint_message = {

                "role": "user",

                "content": "[System: The datetime tool has provided the current time. Please use this information in your response. Do not call the datetime tool again for this request.]"

            }

            request_kwargs["messages"].append(hint_message)

            logger.debug(f"📝 Added hint message to LLM: {hint_message['content']}")

        

        # HANDLE TOOL FAILURE - Tell LLM explicitly what went wrong.

        # Use the structured error_type field rather

        # than searching the error string, so detection is reliable regardless of

        # how the error message is worded.

        if not tool_result.success:

            error_type = getattr(tool_result, "error_type", None) or ""

            is_capability_error = error_type == "CapabilityError"

            is_validation_error = error_type == "ValidationError"

            is_tool_not_enabled = error_type in ("ToolNotEnabled", "ToolNotFound")



            if is_capability_error:

                # Tool works but doesn't support this particular feature.

                user_msg = "This feature is not available."

                if hasattr(tool_result, 'result') and isinstance(tool_result.result, dict):

                    user_msg = tool_result.result.get('user_message', user_msg)

                logger.warning(

                    f"⚠️  Tool '{tool_name}' capability error: {tool_result.error}. "

                    f"Adding user-friendly message for LLM."

                )

                failure_message = {

                    "role": "user",

                    "content": (

                        f"[System: The {tool_name} tool doesn't support the requested feature. "

                        f"Error: {tool_result.error}. "

                        f"User message: '{user_msg}' "

                        f"Please explain this limitation to the user and suggest alternatives if available. "

                        f"This is a known limitation, not a bug.]"

                    )

                }

                request_kwargs["messages"].append(failure_message)

                logger.debug(f"📝 Added capability error notice to LLM: {failure_message['content']}")

            elif is_validation_error:

                # Arguments were invalid — prompt the LLM to retry with correct args.

                logger.warning(

                    f"⚠️  Tool '{tool_name}' validation error: {tool_result.error}. "

                    f"Adding validation error message for LLM."

                )

                failure_message = {

                    "role": "user",

                    "content": (

                        f"[System: The {tool_name} tool received invalid arguments. "

                        f"Error: {tool_result.error}. "

                        f"Please check the tool's documentation for correct argument format "

                        f"and try again with corrected arguments.]"

                    )

                }

                request_kwargs["messages"].append(failure_message)

                logger.debug(f"📝 Added validation error notice to LLM: {failure_message['content']}")

            elif is_tool_not_enabled:

                # Tool not available for this agent.

                logger.warning(

                    f"⚠️  Tool '{tool_name}' not available: {tool_result.error}. Informing LLM."

                )

                failure_message = {

                    "role": "user",

                    "content": (

                        f"[System: The {tool_name} tool is not available for this agent. "

                        f"Error: {tool_result.error}. "

                        f"Please select a different tool or ask the user to enable this tool "

                        f"in agent settings.]"

                    )

                }

                request_kwargs["messages"].append(failure_message)

                logger.debug(f"📝 Added tool availability notice to LLM: {failure_message['content']}")

            else:

                # Regular tool failure — bug, configuration issue, etc.

                logger.warning(

                    f"⚠️  Tool '{tool_name}' failed: {tool_result.error}. "

                    f"Adding failure notice for LLM."

                )

                failure_message = {

                    "role": "user",

                    "content": (

                        f"[System: The {tool_name} tool failed to execute. "

                        f"Error: {tool_result.error}. "

                        f"This issue has been logged for investigation. "

                        f"Please acknowledge this failure in your response and explain to the user "

                        f"that the requested operation could not be completed. "

                        f"Do not attempt to call this tool again for the same request.]"

                    )

                }

                request_kwargs["messages"].append(failure_message)

                logger.debug(f"📝 Added failure notice to LLM: {failure_message['content']}")



    logger_service.log_messages_updated(len(tool_results))



    return tool_results





@router.get("/sessions/{session_id}")

async def get_session(

    session_id: int,

    service: Annotated[ChatService, Depends(get_chat_service)],

):

    """Get chat session by ID with messages."""

    session = await service.get_session(session_id)

    if not session:

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session {session_id} not found")



    return {

        "id": session.id, "title": session.title, "agent_id": session.agent_id,

        "is_active": session.is_active,

        "created_at": session.created_at.isoformat(), "updated_at": session.updated_at.isoformat(),

        "messages": [

            {

                "id": msg.id, "role": msg.role, "content": msg.content,

                "created_at": msg.created_at.isoformat(),

                "metadata": {

                    "token_count": msg.token_count, "total_time_ms": msg.total_time_ms,

                    "tokens_per_second": msg.tokens_per_second, "model": msg.model, "provider": msg.provider,

                    # THE THINKING FOLD (2026-08-24): the reasoning
                    # rides the nested metadata — the fold survives
                    # the reload.
                    "reasoning": (msg.meta or {}).get("reasoning") if msg.meta else None,
                    # THE NOTE AND THE FLAGS (2026-09-23): the saved row carries
                    # what the turn crossed (`limits` + `limit_notice`, D.2/D.3)
                    # and the flags the bubble reads (`truncated`, the provider's
                    # cut). They were dropped HERE — this whitelist listed only
                    # the metrics — so the note the toast announced vanished at
                    # the next reload: the row had it, the endpoint did not
                    # return it. The note is the RECORD; the toast is the moment.
                    "limits": (msg.meta or {}).get("limits") if msg.meta else None,
                    "limit_notice": (msg.meta or {}).get("limit_notice") if msg.meta else None,
                    "truncated": (msg.meta or {}).get("truncated") if msg.meta else None,
                    # THE BUDGET THE TURN CARRIED (G-A ii): the row keeps what the
                    # resolver sent ({sent, declared, reason, path}), and this
                    # whitelist is what makes it survive a reload — the same lesson
                    # the `limits` key above records.
                    "budget": (msg.meta or {}).get("budget") if msg.meta else None,

                } if (
                    msg.token_count or msg.total_time_ms or msg.provider or msg.model
                    or (msg.meta and any(
                        msg.meta.get(key)
                        for key in ("reasoning", "limits", "limit_notice", "truncated", "budget")
                    ))
                ) else None

            }

            for msg in session.messages

        ],

    }





class CompletionRequestModel(BaseModel):

    """Request model for OpenAI-compatible completions."""

    model: str

    messages: list[dict]

    stream: bool = False

    profile: str | None = None

    session_id: int | None = None

    options: dict | None = None





@router.post("/completions")

async def chat_completion(

    request: CompletionRequestModel,

    service: Annotated[ChatService, Depends(get_chat_service)],

):

    """Create a chat completion (non-streaming)."""

    try:

        try:

            from .llm_utils import acompletion_with_retry

        except ImportError:

            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="LLM utils not available")



        request_kwargs: dict[str, Any] = {"model": request.model, "messages": request.messages, "stream": False}



        if request.options:

            if request.options.get('temperature') is not None:

                request_kwargs["temperature"] = request.options['temperature']

            # THE OUTPUT BUDGET (the token-limit arc, C.1): the CALLER's number is
            # the declaration on this surface — there is no agent and no run path
            # here — and it routes through the same resolver as every other
            # writer, so it is logged and, from F.2, bounded. Nothing declared
            # stays nothing sent: this surface's absolute ceiling (D3) is F.2's,
            # and inventing a number here would change what an external caller
            # gets today.
            if request.options.get('max_tokens') is not None:

                apply_output_budget(
                    request_kwargs,
                    None,
                    request.model,
                    PATH_DEFAULT,
                    override=request.options['max_tokens'],
                )

            if request.options.get('top_p') is not None:

                request_kwargs["top_p"] = request.options['top_p']



        response = await acompletion_with_retry(**request_kwargs)



        content = ""

        if response.choices and len(response.choices) > 0:

            content = response.choices[0].message.content or ""



        return {

            "id": response.id if hasattr(response, 'id') else f"completion-{datetime.now().timestamp()}",

            "object": "chat.completion",

            "created": int(datetime.now().timestamp()),

            "model": request.model,

            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],

            "usage": {

                "prompt_tokens": getattr(response, 'usage', {}).get('prompt_tokens', 0) if hasattr(response, 'usage') else 0,

                "completion_tokens": getattr(response, 'usage', {}).get('completion_tokens', 0) if hasattr(response, 'usage') else 0,

                "total_tokens": getattr(response, 'usage', {}).get('total_tokens', 0) if hasattr(response, 'usage') else 0,

            }

        }



    except HTTPException:

        raise

    except Exception as e:

        logger.error(f"Chat completion failed: {e}", exc_info=True)

        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
