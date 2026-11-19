"""THE FAILURE STATEMENT — the ONE wording that fingers the offending LLM.

The rule (user, 2026-09-29), and it is a rule about a SENTENCE:

    an error condition is an opportunity to find gaps in the application before the end
    user does. Naming the provider + LLM is essential to identify the issue. A conclusive
    diagnosis is not needed at the initial stage — we need to finger the offending LLM so
    the user can take action.

Its corollaries are enforced by these functions and by nothing else: the app **never recommends a
model** ("just tell them this one is not functioning properly"), it mentions *no fallback is
configured* where that is the missing lever (the caller's business — it knows the agent), and it
offers the external agent for the deeper look.

WHY THIS MODULE EXISTS SEPARATELY FROM `api/v1/chat/error_handling.py`, WHICH USED TO HOLD IT —
the service-capability arc's phase 6, group 3. The title service (`domain/title/services.py`) is the
second consumer of this wording: the AUTO title's failure had no surface at all, and the fix has to
reach a toast. But a **domain module may not import from `api/`** (measured: zero `from app.api`
imports anywhere under `app/domain`), and the chat path's home is an API module. So the wording
moved to the domain, where both callers can reach it, and `error_handling.py` imports it and keeps
its own public names bound — existing importers (`api/v1/chat/router.py`,
`tests/unit/test_failure_statement.py`) are untouched.

It is also where the roadmap's decision 3 lands: *"the last rung failing → the caller surfaces it and
the resolution supplies the statement — one wording, one place, every surface."* The chat path, the
title path and (phase 6 group 4) the workflow path all render through `failure_sentence_for`.

The functions take a MODEL and a PROVIDER rather than a caller-shaped context object on purpose:
that is the whole of what a statement needs to name the offender, and it is what lets a consumer
that has no `ChatContext` — a background title task, a workflow run — build the same sentence.

`FailureSubject` is the phase-6 group-4 generalisation (G4-F3): the four things a statement is made
of — WHO failed (`model` + `provider`) and what is known (`reason` + `category`) — as ONE value that
every path builds and `failure_sentence_for_subject` renders. `failure_sentence_for` is the
positional form over it, kept for the callers that already speak model/provider/reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# THE DIAGNOSIS OFFER (user, 2026-09-29). The app names WHAT broke and stops there — the deeper
# "why" is the external agent's job. An OFFER, not a claim that Exa is running.
EXA_DIAGNOSIS_OFFER = "You can have Exa attempt diagnosis (ask Exa)."


def model_label(model: Optional[str]) -> str:
    """The model as a PERSON reads it: the slug's last segment, humanized.

    `openrouter/stealth/space-bunny-alpha` → `Space Bunny Alpha`. Everything before the
    last `/` is routing, and a `:free` suffix is a variant marker — neither belongs in a
    sentence shown to the user.
    """
    raw = (model or "").split("/")[-1].split(":")[0]
    words = [w for w in raw.replace("_", "-").split("-") if w]
    return " ".join(w.capitalize() for w in words) if words else "The model"


def model_subject(model: Optional[str], provider: Optional[str] = None) -> str:
    """The offender as a NAME: `Space Bunny Alpha (openrouter)`.

    BOTH halves matter — the model alone leaves "on which provider?" open for a model that is
    served by more than one, the provider alone leaves "which model?", and a turn runs a model.
    A half that is missing is left out rather than printed as empty brackets.
    """
    label = model_label(model)
    provider = (provider or "").strip()
    return f"{label} ({provider})" if provider else label


def provider_reason(error: Exception, limit: int = 160) -> str:
    """The provider's own words, one line and trimmed — for a failure nothing classified.

    All we know about an unclassified failure is what arrived with it, and the reader is better
    served by that than by a model's guess at what went wrong.
    """
    text = " ".join(str(error).split()).rstrip(".")
    if not text:
        return "the provider reported nothing"
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def provider_reported(error: Exception) -> str:
    """`the provider reported: <its own words>` — the UNCLASSIFIED reason clause.

    A clause, not a sentence: the caller composes it into one via `failure_sentence_for`. It lives
    here so the "these are the provider's words, not ours" labelling has one home — the chat path
    and the title path both use it.
    """
    return f"the provider reported: {provider_reason(error)}"


# THE CATEGORIES WHERE THE MODEL ITSELF FAILED — the ones a configured fallback would have carried,
# which is exactly why these are the ones that mention the setting. The value is DATA: the chat
# classifier (`api/v1/chat/error_handling.py`) owns the NAMES; this is the set of them a STATEMENT
# acts on, so it lives with the statement rather than with the code that produces the names.
PROVIDER_FAILURE_CATEGORIES: frozenset[str] = frozenset(
    {"provider_unavailable", "mid_stream_fallback", "rate_limit", "server_error"}
)


# ── WHOSE FAILURE IS IT? — the workflow path's question (G4-F5) ─────────────────────────────────

# THE PROVIDER LAYER's own exception families. Measured 2026-10-04 against the pinned litellm:
# every provider error it raises lives in `litellm.exceptions` (APIConnectionError,
# AuthenticationError, RateLimitError, NotFoundError, ServiceUnavailableError,
# InternalServerError, BadRequestError) AND carries `llm_provider` — so the two signals below
# agree on every one of them. The bare clients are here for a client built without litellm.
_PROVIDER_CLIENT_MODULES: frozenset[str] = frozenset({"litellm", "openai", "anthropic"})


def is_provider_failure(error: Exception) -> bool:
    """Whether an exception came from the PROVIDER LAYER — not from the app.

    WHY THE WORKFLOW PATH ASKS THIS AND THE CHAT PATH DOES NOT. A chat turn IS the LLM call, so
    every failure in it belongs to the model and the statement names it — that is what
    `build_failure_statement` does, classified or not. A workflow RUN can fail for anything (a
    node's bug, a closed database) **and** it already carries the service it resolved, so naming
    that service for an unrelated failure is a FALSE NAME — the thing G4-F5 forbids, and the
    reason the run-level statement asks this question before it names anybody.

    The signal is the provider layer's own, deliberately narrow: an `httpx` failure in a monitor
    node is a network failure, not the model's, and naming the model for it would be the same
    false name one layer down. `llm_provider` is litellm's own attribute (measured), so no
    unrelated exception family carries it by accident.
    """
    if (type(error).__module__ or "").split(".")[0] in _PROVIDER_CLIENT_MODULES:
        return True
    return hasattr(error, "llm_provider")


@dataclass(frozen=True)
class FailureSubject:
    """WHO failed and what the app knows about WHY — the ONE shape every surface builds (G4-F3).

    The chat path fills it from its classifier (`category` = the classifier's category, `reason` =
    its short summary); the workflow path fills it from the run's carried resolution and the
    exception (`reason` = the provider's own words, `category` = None); the title path fills the
    same two halves from its own failure.

    `reason` is a CLAUSE, not a pre-punctuated sentence — `failure_sentence_for_subject` terminates
    it, so no caller has to agree with any other caller about punctuation.
    """

    model: Optional[str] = None
    provider: Optional[str] = None
    reason: str = ""
    category: Optional[str] = None


def failure_sentence_for_subject(
    subject: FailureSubject, *, fallback_configured: bool = True
) -> str:
    """The ONE wording, rendered from a subject — name the offender, offer Exa, stop there.

    `fallback_configured` defaults True so a caller with NO such lever (the workflow path, the title
    path) says nothing about it; the chat path passes its agent's setting, and the note appears only
    where a fallback would have carried the turn (a `category` in `PROVIDER_FAILURE_CATEGORIES`).
    """
    reason = subject.reason.strip()
    sentence = f"{model_subject(subject.model, subject.provider)} is not functioning properly — {reason}"
    if reason and not reason.endswith((".", "!", "?")):
        sentence += "."
    if subject.category in PROVIDER_FAILURE_CATEGORIES and not fallback_configured:
        sentence += " No fallback is configured for this agent."
    return f"{sentence} {EXA_DIAGNOSIS_OFFER}"


def failure_sentence_for(
    model: Optional[str],
    provider: Optional[str],
    reason: str,
) -> str:
    """A failure sentence that FINGERS THE LLM — the positional form over `FailureSubject`.

    Kept for the callers that already speak model/provider/reason (the chat façade, the title
    service). It IS the subject renderer, so every surface terminates the clause the same way.

    A caller with NO model to name (a capability that resolved to nothing) gets `The model` as the
    subject rather than an invented name — `model_label(None)`'s deliberate answer, and the honest
    one: there is no offender to finger, only the fact that nothing was configured.
    """
    return failure_sentence_for_subject(
        FailureSubject(model=model, provider=provider, reason=reason)
    )
