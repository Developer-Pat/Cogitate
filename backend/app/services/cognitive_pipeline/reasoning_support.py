"""Reasoning-model support for the executors (2026-08-21).

Reasoning models (the "thinking" families: deepseek R1, the -r
variants, the deepseek-v4 family, gpt-5's reasoning mode...)
behave differently from chatty models in TWO ways the executors
must handle:

1. SIZE: they stream/think BEFORE answering — a small max_tokens
   (the 512/1024/4096 executor defaults) is consumed entirely by
   the thinking phase, the call finishes with finish_reason=length
   and ZERO content -> the 'no_content' toaster + empty reply
   (the ox-alpha incident, fixed 2026-08-21).
2. FORMAT: the answer can arrive in message.reasoning /
   message.reasoning_content (or delta.reasoning when streaming)
   instead of content, depending on the provider's response shape.

The detection here is NAME-PATTERN based — a cheap guard, not a
curated list. It deliberately matches the families that exhibit
the behavior regardless of vendor (the pattern "thinks before it
answers" is the signal, not the brand). OpenRouter also exposes a
`reasoning` metadata field on the catalog (mandatory/efforts) —
the DB-backed discovery catalog is the long-term source; the
name patterns are the zero-config floor.
"""
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# The output-budget floor for reasoning models. Reasoning models
# spend thousands of tokens thinking; 16000 leaves room for a
# real answer after the thinking (ox-alpha's cron answer needed
# ~28k thinking + ~6k answer; 16k is the pragmatic floor).
REASONING_MAX_TOKENS_FLOOR = 16000

# ── THE THINKING VOCABULARY (F.3) ──────────────────────────────────────────────
# The levels a curated row or a package's `llm_spec` can state. `mandatory` is NOT a
# fourth degree of effort — it is a different FACT: the provider says the driver
# cannot be told not to think, so there is nothing for the user to lower, and the floor
# is not a policy being applied but a property of the driver.
THINKING_LEVELS = ("none", "low", "medium", "high", "mandatory")

# Where a signal came from — carried so the log names the source instead of implying
# the name pattern spoke when a provider's own claim did.
SOURCE_DECLARATION = "declaration"        # the agent's own llm_spec.thinking
SOURCE_CURATED = "curated"                # the curated model row's label
SOURCE_PROVIDER_CLAIM = "provider_claim"  # the provider's own model payload
SOURCE_NAME_PATTERN = "name_pattern"      # the fallback list (r1 / -r / deepseek-v4)
SOURCE_UNKNOWN = "unknown"


@dataclass(frozen=True)
class ThinkingSignal:
    """Whether a driver thinks, on whose word, and whether it can be turned off."""

    thinking: bool = False
    mandatory: bool = False
    source: str = SOURCE_UNKNOWN

    def __bool__(self) -> bool:
        return self.thinking


def as_signal(value: Any) -> ThinkingSignal:
    """Normalize what a caller passed: a bool (the old shape), a signal, or None."""
    if isinstance(value, ThinkingSignal):
        return value
    if value is None:
        return ThinkingSignal()
    return ThinkingSignal(thinking=bool(value), source=SOURCE_UNKNOWN)


def signal_from_level(level: Any, source: str) -> Optional[ThinkingSignal]:
    """The signal a declared LEVEL states — ``None`` when it states nothing.

    ``none`` (and anything unreadable) returns ``None`` rather than a "does not think"
    signal, because the chain is built so a SILENT source lets the next one speak. That
    is what stops a curated row reading `none` from hiding a provider claim that says
    the driver thinks — the live case that produced this phase.
    """
    text = str(level or "none").strip().lower()
    if text == "mandatory":
        return ThinkingSignal(thinking=True, mandatory=True, source=source)
    if text in ("low", "medium", "high"):
        return ThinkingSignal(thinking=True, source=source)
    return None


def level_from_claim(
    thinking: bool, mandatory: bool, effort: Optional[str],
) -> Optional[str]:
    """Project a provider's reasoning claim onto OUR levels (F.3's ruling).

    The provider states an EFFORT (`max`/`xhigh`/`high`/`medium`/`low`/`minimal`) plus
    two facts: whether thinking is on by default, and whether it is mandatory. The
    projection is deliberately CONSERVATIVE — an effort we cannot express, or none
    stated, maps UP rather than down, because under-declaring thinking is the
    empty-answer failure (the ox-alpha class) and nothing in the app can send an effort
    today anyway (the completions path carries temperature/max_tokens/top_p only).
    """
    if mandatory:
        return "mandatory"
    if not thinking:
        return None
    effort_text = str(effort or "").strip().lower()
    if effort_text == "none":
        return None          # the provider states thinking is off by default
    if effort_text in ("", "max", "xhigh", "high"):
        return "high"
    if effort_text == "medium":
        return "medium"
    return "low"

# THE REASONING REPLAY (2026-09-10, the poisoned-session fix).
# A thinking-mode API requires the assistant turn's thinking to be
# passed BACK on every replayed assistant message. DeepSeek rejects
# the whole request otherwise (400):
#   "The `reasoning_content` in the thinking mode must be passed
#    back to the API."
# LiteLLM retries that 400 three times, the completion comes back
# empty, the empty-message guard refuses to persist it — and the
# session is dead for every following turn (a fresh session on the
# same agent replies fine). The persisted reasoning lives in the
# chat message's `meta` column; the helpers below carry it back.
REASONING_CONTENT_FIELD = "reasoning_content"

# The metadata keys the persisted reasoning may live under.
REASONING_META_KEYS = ("reasoning", "reasoning_content")


def reasoning_from_metadata(meta: Any) -> str:
    """The stored thinking text from a persisted message's ``meta`` dict.

    The assistant row's metadata column carries the reasoning the
    streamer accumulated (finalization writes
    ``meta={"reasoning": <accumulated>}``). Returns ``""`` when the row
    has none — an EMPTY ``reasoning_content`` must never be sent back
    (the APIs reject it the same as a missing one).
    """
    if not isinstance(meta, dict):
        return ""
    for key in REASONING_META_KEYS:
        value = meta.get(key)
        if value is None:
            continue
        text = str(value)
        if text.strip():
            return text
    return ""


def reasoning_replay_field(model_str: str, reasoning: str) -> Dict[str, str]:
    """The ``{reasoning_content: ...}`` field to attach to a replayed turn.

    Empty when the turn has no stored reasoning, and empty for
    non-reasoning models — the field is a thinking-mode requirement,
    so a provider that never asks for it must not receive it (some
    OpenAI-compatible servers reject unknown message fields). The gate
    is the shared name-pattern detection, not a vendor string, so a
    newly-shipped thinking family is covered by the same rule that
    floors its output budget.

    Pass ``model_str=""`` to skip the model gate (used where the
    reasoning came from the live response of this very request).
    """
    if not reasoning or not str(reasoning).strip():
        return {}
    if model_str and not is_reasoning_model(model_str):
        return {}
    return {REASONING_CONTENT_FIELD: str(reasoning)}


def history_message(row: Any, model_str: str = "") -> Dict[str, Any]:
    """One persisted chat row as an LLM history message.

    ``{"role", "content"}`` exactly as before, PLUS the stored
    reasoning as ``reasoning_content`` on assistant turns that have
    it. The visible ``content`` is untouched — the Thinking fold
    renders from the metadata, so nothing is duplicated into the
    bubble. Rows without stored reasoning (every pre-thinking row)
    produce the plain ``{role, content}`` shape, which is the graceful
    degradation: those turns stay unreplayable for thinking-mode APIs
    and only a NEW session can avoid them.
    """
    message: Dict[str, Any] = {
        "role": getattr(row, "role", None),
        "content": getattr(row, "content", None),
    }
    if message["role"] == "assistant":
        message.update(
            reasoning_replay_field(
                model_str,
                reasoning_from_metadata(getattr(row, "meta", None)),
            )
        )
    return message


def is_reasoning_model(model_str: str) -> bool:
    """True for the thinking-first model families.

    **F.3: this is the FALLBACK, not the trigger.** The verified provider claim
    (`provider_model_cache.raw_data.reasoning`) and the agent's own declaration
    (`llm_spec.thinking`) speak first — see `output_budget.thinking_in_force` — and this
    list covers only the driver nobody has recorded. It is kept because a fresh
    install with an empty catalog still gets the floor for the known families.

    Name patterns only — the cheap, zero-config guard. Matches the
    families that exhibit the behavior regardless of vendor:
    - 'r1' (deepseek-r1, etc.)
    - '-r' / 'r-' style reasoning variants
    - 'deepseek-v4' (the v4 family emits reasoning_content before
      answering — observed on deepseek-v4-flash, 2026-09-05: the
      thinking phase consumed the whole 1024/4096 budget and the
      call ended with zero content/tool-calls)
    The OpenRouter catalog's `reasoning` metadata field is the
    long-term signal (DB-backed); these patterns are the floor.
    (The 'ox-alpha' stealth model pattern was removed 2026-09-07 —
    OpenRouter pulled the model; the detection list is for LIVE
    families only.)
    """
    m = (model_str or "").lower()
    return (
        "r1" in m
        or "-r" in m
        or "deepseek-v4" in m
    )


def extract_response_text(response: Any, model_str: str = "") -> str:
    """The answer text from a NON-streaming completion response.

    Reads message.content first (the standard shape); falls back to
    message.reasoning / message.reasoning_content for providers that
    surface the thinking in those fields. Returns "" when nothing is
    usable (the caller decides how to handle it).
    """
    try:
        if not response or not response.choices or not response.choices[0]:
            return ""
        message = response.choices[0].message
        if message is None:
            return ""
        content = getattr(message, "content", None)
        if content:
            return str(content)
        # reasoning-shaped answers (thinking-first providers)
        for attr in ("reasoning", "reasoning_content"):
            v = getattr(message, attr, None)
            if v:
                logger.info("Reasoning model %s: answer read from message.%s", model_str or "?", attr)
                return str(v)
    except Exception:
        logger.exception("extract_response_text failed")
    return ""
