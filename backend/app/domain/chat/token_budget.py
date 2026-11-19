"""
Token-budget utilities for context window management.

These are pure functions (no DB access) extracted from ChatService so that
both the regular chat path and agent paths can apply the same trimming
algorithm without duplicating code.

Previously the logic lived only in ChatService._build_context_with_token_budget
and ChatService._estimate_tokens, which meant the router had no token
trimming at all and could silently overflow the model's context window on long
conversations.

THE VOCABULARY (the token-limit arc, Phase E.1) — three numbers, never mixed:

1. **the model's context window** — a FACT about the driver (`262144` for the
   working driver, `8192` for a small one, unknown for a model nobody has
   recorded). Nobody here sets it; `app/domain/providers/model_window.py` READS
   it, and it is used only to LOWER the number below.
2. **the output budget** — our policy (`max_tokens`), resolved in
   `services/cognitive_pipeline/output_budget.py`.
3. **the input budget** (this module's `DEFAULT_INPUT_BUDGET`) — the app's own
   ceiling on how much conversation history goes into a prompt. It is NOT the
   window; its old name (`DEFAULT_MAX_CONTEXT_TOKENS`) read as one, which is
   exactly how "the window" and "the input budget" got mixed up. When the window
   is known, `input_budget_for()` lowers this ceiling to fit it.
"""

import json
import logging
from typing import List, Dict, Optional, Sequence, Tuple, Any

logger = logging.getLogger(__name__)

# ── Defaults ──────────────────────────────────────────────────────────────────

# THE ASSEMBLY CEILING — how much history this app will put in a prompt when
# nothing constrains it. See the module docstring: this is NOT the model's
# context window, and a window smaller than this LOWERS it (never raises it). The
# ceiling is a policy number; the window is physics (roadmap §2).
DEFAULT_INPUT_BUDGET: int = 16000

# Deprecated alias — the same number under the name that read as "the model's
# context window", kept for the importers that still use it
# (`domain/chat/services.py` re-exports both). Retire it when nothing reads it.
DEFAULT_MAX_CONTEXT_TOKENS: int = DEFAULT_INPUT_BUDGET

TOKENS_PER_MESSAGE_OVERHEAD: int = 4   # Role markers, formatting, etc.
TOKENS_RESPONSE_HEADROOM: int = 512    # Reserve for the model's reply


# ── Helpers ───────────────────────────────────────────────────────────────────

def estimate_tokens(text: str) -> int:
    """Estimate token count for a piece of text.

    Tries tiktoken (cl100k_base) for an accurate count; falls back to the
    rule of thumb ``len(text) // 4`` (~4 characters per token for English).

    Args:
        text: Text to estimate.

    Returns:
        Estimated token count.  Returns 0 for falsy input.
    """
    if not text:
        return 0

    try:
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except (ImportError, KeyError):
        return len(text) // 4


def schemas_tokens(tools: Optional[Sequence[Any]]) -> int:
    """The weight of a request's ``tools=[...]`` field, serialized as it travels.

    **One home for the schemas' size.** The input trim deducts this number (Phase B of the
    input-budget arc) and ``output_budget.estimate_prompt_tokens`` measures the same field for the
    window clamp — so both read the schemas' serialized size the same way and can only disagree by
    rounding. A serialization failure returns 0 rather than raising: an unmeasurable fixed part
    must not turn a working call into a dead one.
    """
    if not tools:
        return 0
    try:
        return estimate_tokens(json.dumps(list(tools), default=str))
    except (TypeError, ValueError):
        return 0


def input_budget_for(
    window: Optional[int] = None,
    reserved_output: Optional[int] = None,
) -> int:
    """The assembly ceiling for this turn — the constant, LOWERED by the window.

    The window is the only limit allowed to lower a declared number (roadmap §2),
    and this is the input side of that rule: ``prompt + output ≤ window``. The
    window is therefore a CEILING over today's assembly constant, never a new
    basis for it (the phase's F2 ruling) — a large-window driver's assembly is
    untouched, and only a driver too small to hold the constant pulls it down.

    ``reserved_output`` is the largest output budget this turn could send (the
    reservation is made once, before the routing decides which pass runs), so a
    driver whose window is entirely consumed by its own output budget returns 0:
    "this prompt has no room for history", stated rather than left to overflow.
    The caller still sends the system prompt and the user's message — the trim
    only selects HISTORY (`build_context_with_token_budget` always keeps at least
    one pair), and `TOKENS_RESPONSE_HEADROOM` is deducted there, once.

    An unknown window (``None``) leaves the constant alone — §2.4: an unknown
    window must not clamp blindly.
    """
    ceiling = DEFAULT_INPUT_BUDGET
    if window is None:
        return ceiling
    try:
        usable = int(window) - int(reserved_output or 0)
    except (TypeError, ValueError):
        return ceiling
    return max(0, min(ceiling, usable))


def build_context_with_token_budget(
    messages: List[Dict[str, Any]],
    system_prompt: Optional[str],
    input_budget: Optional[int] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """Select conversation history that fits within a token budget.

    Walks the message list newest-to-oldest, accumulating messages until the
    remaining budget is exhausted.  Always keeps at least one user/assistant
    pair so the LLM has minimal context to work from.

    The system prompt is accounted for but is NOT included in the returned
    list — callers prepend it themselves.

    **THE FIXED PART IS DEDUCTED, NOT JUST THE SYSTEM PROMPT** (Phase B of the input-budget arc).
    Two large contributors used to ride outside this arithmetic entirely, so the *declared* budget
    and the *sent* prompt disagreed by their weight (measured: the schemas are 2,540-3,496 tokens
    on the live agents, and a thinking session's replayed ``reasoning_content`` added 10,030 tokens
    across all its history — +54 % over the counted content):

    - the **tool schemas** — a separate ``tools=[...]`` request field that grows with the tool
      count, never with the conversation. Passed here as ``tools`` (the LLM-ready dicts); the same
      serialized measure the window clamp uses (``output_budget.estimate_prompt_tokens``).
    - the **replayed ``reasoning_content``** — re-sent on every assistant message by the
      poisoned-session fix, counted per message as it is selected.

    The consequence is deliberate and is the one behaviour change in the arc so far: **history is
    dropped earlier**, by exactly those two weights. It is the difference between a budget that
    describes the prompt and a budget that describes part of it.

    The ≥1-pair rule stands, so a fixed part that exceeds the budget by itself still cannot empty
    the history — ``reason=fixed_exceeds_budget`` is logged when that happens (D5: report, do not
    clamp; a budget that can be blown by design should say so rather than fail quietly).

    Args:
        messages: Ordered list of ``{role, content}`` dicts representing the
            conversation history (excluding the current user turn and the
            system prompt).
        system_prompt: The system prompt that will be prepended to the final
            message list.  Its token cost is deducted from the budget before
            history messages are selected.
        input_budget: The assembly ceiling for this turn — ``input_budget_for()``
            when the caller knows the model's window, else ``None`` for
            ``DEFAULT_INPUT_BUDGET``.
        tools: The tool schemas in LLM function-calling format — what actually
            travels in the request's ``tools=[...]`` field. ``None``/empty means
            this call sends no tools, so nothing is deducted for them (the
            honest reading: no tools, no schema weight).

    Returns:
        ``(selected_messages, total_tokens_used)`` where *selected_messages*
        is a chronologically ordered subset of *messages* and
        *total_tokens_used* includes the system prompt cost.
    """
    if input_budget is None:
        input_budget = DEFAULT_INPUT_BUDGET

    system_tokens = estimate_tokens(system_prompt) if system_prompt else 0
    # NOT named `schemas_tokens`: that would shadow the module-level function of the same name,
    # and the shadowing bug (a local called `list` once bit this codebase) is silent until a call
    # site reaches for the function inside the shadowed scope.
    schemas_weight = schemas_tokens(tools)
    budget = input_budget - system_tokens - schemas_weight - TOKENS_RESPONSE_HEADROOM
    fixed_exceeds_budget = budget < 0

    selected: List[Dict[str, Any]] = []
    total_tokens = system_tokens + schemas_weight
    replayed_tokens = 0

    for msg in reversed(messages):
        msg_tokens = estimate_tokens(msg.get("content", "")) + TOKENS_PER_MESSAGE_OVERHEAD
        # The replay rides with the assistant message it belongs to, so it is counted when that
        # message is KEPT — a dropped message's reasoning costs nothing.
        replay = msg.get("reasoning_content")
        if replay:
            msg_tokens += estimate_tokens(replay)

        # Stop once the budget is exhausted, but always keep ≥ 1 pair
        if budget - msg_tokens < 0 and len(selected) >= 2:
            break

        selected.insert(0, msg)
        budget -= msg_tokens
        total_tokens += msg_tokens
        if replay:
            replayed_tokens += estimate_tokens(replay)

    kept, dropped = len(selected), len(messages) - len(selected)
    logger.info(
        "📚 Context built: %d/%d messages, ~%d tokens (input budget: %d, "
        "dropped: %d, fixed: %d = system %d + tool schemas %d, replayed reasoning: %d)%s",
        kept,
        len(messages),
        total_tokens,
        input_budget,
        dropped,
        system_tokens + schemas_weight,
        system_tokens,
        schemas_weight,
        replayed_tokens,
        " reason=fixed_exceeds_budget" if fixed_exceeds_budget else "",
    )

    return selected, total_tokens
