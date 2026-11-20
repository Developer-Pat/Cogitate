"""
Conversation Compactor — rolling summary compaction for long conversations.

When a conversation's message history exceeds a token threshold,
older messages are LLM-summarized into a condensed context block
while the most recent turns remain raw. This keeps the active
conversation within the provider's context window.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Sequence, Tuple

logger = logging.getLogger(__name__)

if TYPE_CHECKING:  # the chain's type, for the annotation only — the call imports it where it is used
    from app.domain.providers.capabilities import ServiceCandidate

# Which capability supplies the summarizer. The constant lives HERE because this module is the
# consumer — the same shape as `TITLE_CAPABILITY_KEY` in the title service — so the caller imports it
# rather than retyping the string.
SUMMARY_CAPABILITY_KEY = "summary"

# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------

# Default threshold: 80% of a typical 8K context window
DEFAULT_MAX_TOKENS = 6144

# Messages newer than this many turns are always kept raw
KEEP_LAST_N = 4


def _get_encoder():
    """Get a tiktoken encoder, falling back to a rough character estimate."""
    try:
        import tiktoken
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        logger.warning("tiktoken not available, using character-based estimate (~4 chars/token)")
        return None


def count_message_tokens(messages: List[Dict[str, Any]]) -> int:
    """Count the total tokens in a list of messages."""
    encoder = _get_encoder()
    if encoder:
        try:
            text = " ".join(
                str(m.get("content", "")) for m in messages
            )
            return len(encoder.encode(text))
        except Exception:
            pass

    # Fallback: rough character estimate
    total_chars = sum(len(str(m.get("content", ""))) for m in messages)
    return total_chars // 4


def should_compact(
    messages: List[Dict[str, Any]],
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> Tuple[bool, int]:
    """Decide whether compaction is needed.

    Returns (should_compact, current_token_count).
    """
    token_count = count_message_tokens(messages)
    needs = token_count > max_tokens
    if needs:
        logger.info(
            "Compaction check: %d tokens > %d threshold — compaction needed",
            token_count, max_tokens,
        )
    return needs, token_count


# ---------------------------------------------------------------------------
# Compaction
# ---------------------------------------------------------------------------


def _split_messages(
    messages: List[Dict[str, Any]],
    keep_last: int = KEEP_LAST_N,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Split messages into (old_summarizable, recent).

    Keeps the system prompt (if present) and the last N messages as recent.
    Everything in between is old and eligible for summarization.
    """
    if not messages:
        return [], []

    system_msgs = []
    body_msgs = []

    for m in messages:
        if m.get("role") == "system":
            system_msgs.append(m)
        else:
            body_msgs.append(m)

    if len(body_msgs) <= keep_last:
        # Not enough messages to compact
        return [], messages

    old = system_msgs + body_msgs[:-keep_last]
    recent = body_msgs[-keep_last:]
    return old, recent


async def compact_messages(
    messages: List[Dict[str, Any]],
    max_tokens: int = DEFAULT_MAX_TOKENS,
    candidates: Sequence[ServiceCandidate] = (),
) -> List[Dict[str, Any]]:
    """Compact conversation messages if they exceed the token threshold.

    Old messages are summarized via LLM and replaced with a condensed
    summary block. Recent messages (last KEEP_LAST_N) are kept raw.

    ``candidates`` is the ``summary`` capability's RESOLVED chain, in order. The CALLER resolves it,
    because this module holds no database session. It replaces ``summarization_model`` /
    ``summarization_provider``, which defaulted to ``llama3.2`` / ``ollama`` — a service written in
    code and aimed at a local engine that need not be running, which is also why the ``summary``
    capability had **no consumer at all** (found by the service-capability arc's phase-8 audit).

    The chain is walked by the shared ``capabilities.attempt_chain``, so a lost primary falls to its
    backup and **every** attempt's failure is logged — the backup's included (the arc's R3).

    Returns the compacted message list (or the original if no compaction
    was needed).
    """
    needs, token_count = should_compact(messages, max_tokens)
    if not needs:
        return messages

    old_msgs, recent_msgs = _split_messages(messages)
    if not old_msgs:
        return messages

    # Build a summary prompt from the old messages
    old_text = "\n".join(
        f"{m.get('role', 'unknown')}: {m.get('content', '')}"
        for m in old_msgs
        if m.get("content")
    )

    summary_prompt = (
        "Summarize the following conversation history concisently, "
        "preserving key facts, decisions, and context that would be needed "
        "to continue the conversation naturally.\n\n"
        f"{old_text[:8000]}"  # Limit input to avoid token issues
    )

    try:
        logger.info("Compaction: summarizing %d old messages (%d tokens)", len(old_msgs), token_count)

        # The chain: the primary first, then its backups (the R3 walk, in its one home).
        from app.domain.providers.capabilities import attempt_chain

        try:
            outcome = await attempt_chain(
                list(candidates),
                call=lambda candidate: _summarize_with(candidate, summary_prompt),
                capability=SUMMARY_CAPABILITY_KEY,
            )
            summary = outcome.response
        except Exception as exc:
            # The chain is exhausted (or nothing was configured for the capability). The last resort
            # is the truncation this module has always had: it compresses WITHOUT asking a service, so
            # the caller still gets a context that fits rather than one that is over-long.
            logger.error(
                "Compaction: no service in the '%s' chain answered (%s) — using the truncation fallback",
                SUMMARY_CAPABILITY_KEY,
                exc,
            )
            summary = summary_prompt[:2000] + "...[truncated]"

        # Build compacted message list
        compacted: List[Dict[str, Any]] = []
        for m in old_msgs:
            if m.get("role") == "system":
                compacted.append(m)  # Keep system prompt intact
                break

        # Insert the summary as a system message
        compacted.append({
            "role": "system",
            "content": (
                f"[Conversation history compacted at {len(messages)} messages, "
                f"{token_count} tokens]\n\n"
                f"Previous conversation summary:\n{summary}"
            ),
        })

        # Append recent messages
        compacted.extend(recent_msgs)

        new_count = count_message_tokens(compacted)
        logger.info(
            "Compaction: %d messages -> %d messages, %d tokens -> %d tokens (%.0f%% reduction)",
            len(messages), len(compacted), token_count, new_count,
            (1 - new_count / max(token_count, 1)) * 100,
        )

        return compacted

    except Exception as e:
        logger.error("Compaction failed: %s — returning original messages", e)
        return messages


async def _summarize_with(candidate: ServiceCandidate, prompt: str) -> str:
    """ONE attempt: summarize ``prompt`` through ``candidate``'s service.

    Raises on failure rather than papering over it — the chain's NEXT candidate is the remedy, and the
    shared walk logs this attempt (the service, its model, and which attempt it was).
    """
    from litellm import acompletion

    from app.domain.providers.litellm_route import api_base_for, litellm_model_string

    model = candidate.model
    if not model:
        raise ValueError(f"the '{candidate.describe()}' service names no model to summarize with")

    # THE ROUTE (2026-10-12, `litellm_route`) — the same one mapping the chat path uses. The
    # hand-rolled `{provider}/{model}` produced a string litellm REJECTS for either aliased provider
    # ("LLM Provider NOT provided", measured); a local row also needs its address.
    litellm_model = litellm_model_string(candidate.provider or "", model, candidate.provider_type)
    api_base = candidate.endpoint

    kwargs: dict = {
        "model": litellm_model,
        "messages": [
            {
                "role": "system",
                "content": "You are a conversation summarizer. Produce a concise summary "
                           "that preserves key facts, decisions, and context.",
            },
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 1024,
        "temperature": 0.3,
    }
    if api_base:
        kwargs["api_base"] = api_base_for(litellm_model, api_base)
        # Keyless LOCAL servers only — a cloud endpoint with no key must fail as missing.
        from app.domain.providers.llm_factory import placeholder_key_for
        _placeholder = placeholder_key_for(kwargs["api_base"], litellm_model)
        if _placeholder:
            kwargs["api_key"] = _placeholder


    response = await acompletion(**kwargs)
    return response.choices[0].message.content or "Summary not available."
