"""THE PROMPT'S ACCOUNT — what a real turn sends, per contributor, measured.

The input-budget arc opened on a chat warning (*"this prompt is near the 16000-token input
budget"*) and its ground pass found that **the budget governs less than the prompt sends**: the
trim deducts the system prompt and counts each history message's ``content`` alone, while three
large things ride along — the **tool schemas** (a separate ``tools=[...]`` request field), the
**replayed ``reasoning_content``** (re-sent on every assistant message by the poisoned-session
fix) and the **turn's own tool results**, which grow the prompt on every round of the loop.

Nothing in production said any of that, so the finding had to be argued with hand-written probes
(`local/roadmaps/input-budget/probe-*.py`). This module is the reading instead: one
:class:`PromptAccount` per provider call and **one log line** carrying the measured parts beside
the ceiling in force and the soft's threshold. After one live turn the log answers *"does the
budget govern what the app sends?"* by itself.

**What this does NOT do** — deliberately, because it is Phase A and the phases are diffed
against each other:

- **it changes nothing.** The trim selects exactly what it selected before. Phase B is the
  change (the trim deducts the schemas and the replay); this table is what B is measured against.
- **it bounds nothing.** No line here trims, blocks or refuses a call. A limit that acts is a
  limit with a ruling behind it, and this arc has not ruled.
- **it invents no numbers.** Every value comes from the app's own estimator
  (:func:`token_budget.estimate_tokens`), the same one the budget and the window clamp use, so
  the account and the trim can only disagree by rounding.

It also counts what the app knows it counts: ``counted_by_trim`` is the number the trim's own
arithmetic sees, and the gap to ``total`` is exactly the arc's headline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from app.domain.chat.token_budget import (
    DEFAULT_INPUT_BUDGET,
    estimate_tokens,
    schemas_tokens,
)

logger = logging.getLogger(__name__)


def _content_of(message: Any) -> str:
    """A message's ``content`` — dict or object, whatever the caller holds."""
    if isinstance(message, Mapping):
        value = message.get("content")
    else:
        value = getattr(message, "content", None)
    return value if isinstance(value, str) else (str(value) if value else "")


def _role_of(message: Any) -> str:
    if isinstance(message, Mapping):
        role = message.get("role")
    else:
        role = getattr(message, "role", None)
    return role if isinstance(role, str) else ""


def _reasoning_of(message: Any) -> str:
    """The stored ``reasoning_content`` that rides back on an assistant message.

    Only assistant turns carry it, and only on a thinking model's session: the poisoned-session
    fix re-sends it because the API 400s without it. The trim counts none of it.
    """
    if isinstance(message, Mapping):
        value = message.get("reasoning_content")
    else:
        value = getattr(message, "reasoning_content", None)
    return value if isinstance(value, str) else ""


@dataclass(frozen=True)
class PromptAccount:
    """One provider call's prompt, by contributor — tokens, measured."""

    system: int = 0
    """The system prompt: persona, shared rules, the state/notebook blocks, the tools note."""

    history: int = 0
    """User/assistant message content — the conversation proper."""

    tool_results: int = 0
    """Tool results riding IN the prompt (``role="tool"`` messages) — the turn's own growth."""

    tool_schemas: int = 0
    """The serialized ``tools=[...]`` request field — a separate payload, never in the messages."""

    replayed_reasoning: int = 0
    """``reasoning_content`` re-sent on assistant messages (thinking sessions only)."""

    @property
    def total(self) -> int:
        """Everything this call sends, as far as the app can measure it."""
        return (
            self.system
            + self.history
            + self.tool_results
            + self.tool_schemas
            + self.replayed_reasoning
        )

    @property
    def counted_by_trim(self) -> int:
        """What the budget's own arithmetic sees: the system prompt plus message *content*.

        ``build_context_with_token_budget`` deducts the system prompt and then counts each kept
        message's ``content`` — so the tool results (which ARE message content) are inside this
        number, while the schemas and the replay ride outside it.
        """
        return self.system + self.history + self.tool_results

    @property
    def uncounted(self) -> int:
        """The part of the prompt the budget never sees — this arc's headline, per call."""
        return self.tool_schemas + self.replayed_reasoning


def account_prompt(
    messages: Optional[Sequence[Any]] = None,
    tools: Optional[Sequence[Any]] = None,
    system_prompt: Optional[str] = None,
) -> PromptAccount:
    """Measure a prompt by contributor.

    ``messages`` is the list about to go on the wire (a system message inside it is counted as
    the system part). ``system_prompt`` is for callers whose message list excludes it — passing
    both would count it twice, so it is only used when no system message is present.

    ``tools`` is the ``tools=[...]`` field (schemas), measured serialized, because that is how
    it travels.
    """
    system = 0
    history = 0
    tool_results = 0
    replayed = 0
    saw_system_message = False

    for message in messages or ():
        role = _role_of(message)
        content_tokens = estimate_tokens(_content_of(message))
        if role == "system":
            saw_system_message = True
            system += content_tokens
        elif role == "tool":
            tool_results += content_tokens
        else:
            history += content_tokens
            if role == "assistant":
                replayed += estimate_tokens(_reasoning_of(message))

    if not saw_system_message and system_prompt:
        system += estimate_tokens(system_prompt)

    # ONE HOME for the schemas' size (`token_budget.schemas_tokens` — the same measure the trim
    # deducts and the window clamp uses), so the account cannot disagree with the arithmetic.
    return PromptAccount(
        system=system,
        history=history,
        tool_results=tool_results,
        tool_schemas=schemas_tokens(tools),
        replayed_reasoning=replayed,
    )


def describe_account(account: PromptAccount) -> str:
    """The account's parts as a short phrase — for a note, a log line or a test.

    **One home for the part names**, so the composition the user reads in a warning and the
    composition in the log cannot drift apart.
    """
    return " · ".join(
        [
            f"system {account.system:,}",
            f"history {account.history:,}",
            f"tool results {account.tool_results:,}",
            f"tool schemas {account.tool_schemas:,}",
            f"replayed reasoning {account.replayed_reasoning:,}",
        ]
    )


def format_account(
    account: PromptAccount,
    input_budget: Optional[int] = None,
    soft_threshold: Optional[int] = None,
) -> str:
    """The account as ONE greppable line, with the ceiling in force beside it.

    ``input_budget`` is the assembly ceiling for this call (``input_budget_for()``); ``None``
    means the caller did not name one, and the app's own default is reported as such — never
    silently, because a limit whose threshold cannot be named is not a limit.
    """
    ceiling = DEFAULT_INPUT_BUDGET if input_budget is None else int(input_budget)
    parts = [
        f"📐 PROMPT ACCOUNT {account.total:,} measured",
        describe_account(account),
        f"the trim counts {account.counted_by_trim:,} of it (content alone)",
        f"ceiling {ceiling:,}",
    ]
    if soft_threshold is not None:
        parts.append(f"soft {int(soft_threshold):,}")
    return " · ".join(parts)


def log_prompt_account(
    messages: Optional[Sequence[Any]],
    tools: Optional[Sequence[Any]] = None,
    system_prompt: Optional[str] = None,
    input_budget: Optional[int] = None,
    soft_threshold: Optional[int] = None,
    target: Optional[logging.Logger] = None,
) -> PromptAccount:
    """Measure a prompt and say so — one line per provider call. Returns the account."""
    account = account_prompt(messages, tools, system_prompt)
    (target or logger).info(
        format_account(account, input_budget=input_budget, soft_threshold=soft_threshold)
    )
    return account
