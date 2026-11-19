"""THE SERVICE RESOLVER — one answer to "which service should answer this?"

The service-capability arc, Phase 1.1. Before this module the app answered that question in FOUR
places that agreed only by luck (measured 2026-09-30):

1. ``DefaultProviderService.get_default_provider`` — ONE row, ``WHERE is_default AND is_active``;
2. an agent's own ``provider`` / ``model`` / ``preferred_providers`` declaration, honoured by the
   cognitive-pipeline executor and by nothing else;
3. the title service's own resolution over the default row;
4. eighteen direct LLM constructions that ask nobody.

What this module does NOT do: it builds no client. It answers *which* service, in what ORDER, and
**why** — so the caller can name the offender when an attempt fails (user, 2026-09-30: *"a failure
needs to be logged, including the backup service failure"*), and so one page can show what every
capability is using.

THE LADDER (first match wins; the RESULT always carries which rung answered):

1. ``override``  — an explicit per-request value ("provider/model"). It picks the PRIMARY, and the
   capability's configured chain still supplies the backups — an override changes who answers first,
   not whether a backup exists.
2. ``agent``     — the agent's own declaration, **only when the caller passes one**. A declaring
   agent supplies the backups too: its ``preferred_providers`` when it lists any, else the
   capability's configured chain. A caller that must not let an agent's model win simply does not
   pass an agent: the chat path does (its behaviour today IS "the agent's model first"), the title
   service does not (its behaviour today ignores the agent entirely).
3. the capability's configured candidates — ordinal 0 is the primary, the rest are the backups;
4. the global default provider row — an LLM rung, so a capability of ANOTHER kind skips it (an
   `embedding` capability's service is not the install's chat default; see `resolve`);
5. nothing — an empty result with ``reason='none'``. **It does not raise**: the caller surfaces the
   failure and this resolution supplies the statement (one wording, one place, every surface).

A capability switched OFF (``capabilities.enabled`` false) is NOT the ladder's last rung: it returns
an empty resolution with ``reason='disabled'`` BEFORE any rung is consulted — an override included.
"Off" must not quietly mean "use whichever row is the global default": that is the second answer
this arc exists to remove, and the availability ruling needs an off state a consumer can refuse on
(phase 6, G1-F3).

A candidate names its service in one of THREE forms, because the families are not all provider rows:

* ``provider_id``      — a specific provider row (the LLM case);
* ``require_location`` — a CLASS, 'local' | 'cloud': "prefer local" as configuration instead of the
  hardcoded ``DEFAULT_FALLBACK_CHAIN = ["openrouter", "deepseek", "ollama"]`` the executor used to
  carry (deleted in this arc's phase 3 — the order is rows now). It resolves against the live rows
  by ``provider_location``, ordered by
  ``(Provider.priority, Provider.name)`` — which is the first job ``priority`` has ever had, since
  nothing has ever SELECTED on it (2 writers, 2 list orderings, 0 selectors);
* ``service_name``     — a named engine/process that is not a provider row at all: the speech
  engines (``piper``, ``edge``, ``whisper``) and the external agent (``exa``).

A class candidate contributes EVERY matching row, in order, at its position — so a chain can read
"the local ones, best-first, then the cloud ones".
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, replace
from typing import Any, Awaitable, Callable, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.providers.provider_classes import provider_location
from app.domain.providers.provider_endpoints import resolve_endpoint
from app.infrastructure.database.models import Capability, CapabilityService, Provider
# The thinking vocabulary's ONE home — the write path validates against the same tuple the
# cognitive pipeline reads, rather than retyping its values into a second list (which the
# house rule against a second answer forbids, and which goes stale the day a level moves).
# NOTE: the reasoning vocabulary is imported INSIDE `_validate_candidate`, not
# here. `app.services.cognitive_pipeline` pulls in the vector store, which
# imports `domain.providers.embeddings`, which imports THIS module — so a
# module-level import closed a cycle the moment anything imported this module
# first (found 2026-11-18, importing the setup offers from a fresh process).

logger = logging.getLogger(__name__)

# ── The kinds — what a caller RECEIVES ───────────────────────────────────────────────────────────
KIND_LLM = "llm"                # a provider row → ProviderConfig → an LLM client
KIND_SPEECH = "speech"          # a speech engine (piper, edge, whisper)
KIND_PROCESS = "process"        # an external process (the Exa ACP agent)
# An embedding server AND the model it runs. The model belongs to the capability (see
# `EMBEDDINGS_CAPABILITY_KEY`), and this kind is what keeps the CHAT default row from answering for
# it: the ladder's last rung is an LLM rung (see `resolve`).
KIND_EMBEDDING = "embedding"
KINDS: tuple[str, ...] = (KIND_LLM, KIND_SPEECH, KIND_PROCESS, KIND_EMBEDDING)

# The capability the chat paths resolve — the key the seed created for it
# (`alembic/versions/z5a6b7c8d9e0_capabilities.py`; it carries NO candidates of its own, on purpose:
# its service is the AGENT's, which is the ladder's rung 2).
CHAT_CAPABILITY_KEY = "chat"

# The capability the workflow node factories resolve (phase 4). The seed backs it with the default
# row, so its first consumers get exactly what they got before — the point of the migration is the
# SOURCE of the answer, not a change in it.
WORKFLOW_CAPABILITY_KEY = "workflow-llm"

# The capability the RAG/vector-index family resolves — the SERVICE-LITERALS arc's ruled second half
# (`wiki/issues/resolved/embedded-service-literals/embedding-model-and-dims.md`, option C; the ADDRESS half landed separately).
#
# It answers THREE facts through `domain/providers/embeddings.py`: the address (its provider ROW's
# endpoint), the MODEL (its own candidate's model, else the row's default) and the DIMS (derived from
# the model — `EMBEDDING_DIMS_BY_MODEL`). Before it, `nomic-embed-text` and `768` were written into
# six places as two independent literals, so a model changed without its dims wrote the wrong width
# into an index that accepts it.
#
# IT CARRIES NO CANDIDATES IN THE SEED, on purpose, and that is the ruling rather than an oversight:
# *structure* belongs to a migration (an empty container is nobody's opinion), while a *value* — the
# model — is a setup offer the user or Exa accepts, declines or replaces (EXA'S
# INSTALLATION SKILL; the same principle the bare fresh-install provider row follows). An
# unconfigured install therefore REPORTS the gap and embeds nothing.
EMBEDDINGS_CAPABILITY_KEY = "embeddings"

# Which capabilities a REAL consumer resolves WITH an agent (the ladder's rung 2), so a read-out can
# say "what will this agent use" without inventing an answer for capabilities the agent never touches.
#
# The CONSUMERS are the source of truth and this set cites them: `services/cognitive_pipeline/
# chat_chain.py` and `domain/chat/services.py` both pass an agent for `CHAT_CAPABILITY_KEY`, and
# nothing else does — `title` resolves with no agent (its per-request preference rides rung 1, the
# override), `workflow-llm` resolves agent-free, and `stt`/`tts`/`exa` name an engine or a process
# rather than an LLM. So picking an agent on `/providers/capabilities` changes only the cards the
# agent actually drives; the rest keep their true answer, which is what the page's exit criterion
# ("which service is my title using") requires.
#
# It is kept BY HAND, which is the honest shape today: nothing in the data declares which consumers
# pass an agent. The deep dive that owns this question is still open (THE AGENT
# RUNG'S REACH) — until it rules, a consumer that starts passing an agent must add its capability
# HERE, or the read-out will under-report what the agent drives.
AGENT_INFLUENCED_CAPABILITIES: frozenset[str] = frozenset({CHAT_CAPABILITY_KEY})

# ── The rungs, as strings a log line and a payload can both carry ────────────────────────────────
REASON_OVERRIDE = "override"
REASON_AGENT = "agent profile"
REASON_CAPABILITY = "capability config"
REASON_GLOBAL_DEFAULT = "global default"
REASON_NONE = "none"
# A capability switched OFF answers NOTHING (phase 6, G1-F3). It is not a rung: it short-circuits
# every rung, an override included, because "off" is a statement about the capability rather than a
# preference about which service. Before this it fell THROUGH to the global default row, so a
# capability could read as disabled while still being served by whichever row happened to be default
# — a second answer wearing an off switch (the availability ruling's "the agent is disabled").
REASON_DISABLED = "disabled"

# Where a candidate came from (for the read-out and the log)
SOURCE_ROW = "row"
SOURCE_CLASS = "class"
SOURCE_NAMED = "named"
SOURCE_AGENT = "agent"
SOURCE_OVERRIDE = "override"
SOURCE_DEFAULT = "default"


class UnknownCapabilityError(ValueError):
    """The key names no capability row.

    A SUBCLASS of ``ValueError`` on purpose: every existing caller that catches ``ValueError``
    (the speech shim's contract) keeps working, while an HTTP route can tell "no such capability"
    (404, the read path's own answer) apart from "this candidate cannot be attempted" (400).
    Capabilities are vocabulary — a migration seeds them — so no write ever invents one.
    """


class NoProviderConfiguredError(Exception):
    """The capability resolved to NOTHING a consumer can use — the caller's loud refusal.

    `resolve()` deliberately does not raise: it returns an empty resolution with a `reason`
    ('none' / 'disabled') and the CALLER surfaces it — the arc's own rule, that the last rung
    failing is the caller's to report and the resolution supplies the statement. The workflow
    LLM factories are that caller, and this is their signal (raised by both of them).

    The message speaks the CAPABILITY world. It used to describe the old ladder's first rung —
    "No default LLM provider configured … Initialize Default … OPENAI_API_KEY" — which is no
    longer the first answer: a capability names its own service, and `/providers/capabilities`
    is the page that changes it. Register item #8 of the service-capability study.
    """

    def __init__(self, capability: Optional[str] = None):
        self.capability = capability
        if capability:
            message = (
                f"No service is configured for the '{capability}' capability. "
                f"Choose one on the Providers → Capabilities page (/providers/capabilities)."
            )
        else:
            # The caller resolved no capability at all (a factory that still asks the DEFAULT
            # provider row): the honest report is that nothing could be resolved either way.
            message = (
                "No service could be resolved for this workflow's LLM steps, and no default "
                "provider is configured. Choose a service on the Providers → Capabilities page "
                "(/providers/capabilities)."
            )
        super().__init__(message)


@dataclass(frozen=True)
class ServiceCandidate:
    """One attemptable service, as the resolver resolved it.

    ``provider`` is the provider row's NAME (``deepseek``, ``llama``) rather than its type — that is
    the handle a failure statement can name and a reader can act on.
    """

    ordinal: int
    provider: Optional[str] = None
    provider_id: Optional[int] = None
    provider_type: Optional[str] = None
    model: Optional[str] = None
    location: Optional[str] = None
    # THE ADDRESS this row resolves to — the row's own `base_url`, else its TYPE's canonical endpoint
    # (2026-10-12, the litellm-mapping ruling's stage 2). It is carried here because the resolver is
    # the one place that already holds the row; without it every consumer looked the address up again,
    # and the ones that could not reach a row carried their own copy of two of them.
    endpoint: Optional[str] = None
    # WHICH FORM the row was written as, for the class form — `source` says a candidate came from a
    # class, and this says WHICH class. Without it a read-out cannot be sent back as a write: the
    # class has already been expanded into rows, so `location` alone cannot tell "prefer local" from
    # "this one row that happens to be local" (and the two write differently).
    require_location: Optional[str] = None
    service_name: Optional[str] = None
    thinking: Optional[str] = None
    source: str = SOURCE_ROW

    def describe(self) -> str:
        """`deepseek/deepseek-v4-flash` · `piper` — one line for a log or a payload."""
        if self.provider:
            return f"{self.provider}/{self.model}" if self.model else self.provider
        return self.service_name or "(unnamed)"


@dataclass(frozen=True)
class ResolvedService:
    """The resolution: what was chosen, in what order, and which rung answered."""

    capability: str
    kind: str
    reason: str
    candidates: tuple[ServiceCandidate, ...] = ()

    @property
    def primary(self) -> Optional[ServiceCandidate]:
        """The service to try first, or None when nothing resolved."""
        return self.candidates[0] if self.candidates else None

    @property
    def backups(self) -> tuple[ServiceCandidate, ...]:
        """Everything after the primary, in order — what "the backup" means to a failure path."""
        return self.candidates[1:]

    @property
    def resolved(self) -> bool:
        """Whether anything can be attempted at all."""
        return bool(self.candidates)


def _model_from_config(provider: Provider) -> Optional[str]:
    """The row's own default model — the one thing ``config`` reliably carries."""
    config = provider.config if isinstance(provider.config, dict) else {}
    model = config.get("default_model")
    return str(model) if model else None


def _candidate_from_row(provider: Provider, ordinal: int, source: str) -> ServiceCandidate:
    """A provider row as an attemptable candidate."""
    return ServiceCandidate(
        ordinal=ordinal,
        provider=provider.name,
        provider_id=provider.id,
        provider_type=provider.provider_type,
        model=_model_from_config(provider),
        location=provider_location(provider.provider_type, provider.base_url),
        endpoint=resolve_endpoint(
            provider.provider_type or provider.name, provider.base_url, provider.name
        ),
        source=source,
    )


def _candidate_from_agent(agent: Any, ordinal: int) -> Optional[ServiceCandidate]:
    """The agent's own declaration, or None when it declares nothing to run."""
    name = getattr(agent, "provider", None)
    if not name:
        return None
    model = getattr(agent, "model", None)
    return ServiceCandidate(
        ordinal=ordinal,
        provider=str(name),
        model=str(model) if model else None,
        source=SOURCE_AGENT,
    )


def _agent_backup_candidates(agent: Any, start_ordinal: int) -> list[ServiceCandidate]:
    """The agent's `preferred_providers`, as the BACKUPS of its own primary.

    The agent's declaration is rung 2 of the ladder, and what it declares is an ORDER — its
    provider first, its preferred list after — so that order lives here rather than in whichever
    consumer walks it.

    Each backup carries the SAME model as the primary: that is what the executor's failover does
    today (it sends the agent's model to every provider in the chain), and changing it in the same
    commit that moves the chain would make the two indistinguishable.
    """
    model = getattr(agent, "model", None)
    preferred = list(getattr(agent, "preferred_providers", None) or [])
    seen = {getattr(agent, "provider", None)}
    candidates: list[ServiceCandidate] = []
    # The ordinal is the candidate's POSITION in the chain, so a skipped entry (the primary itself,
    # a repeat) leaves no gap: `backup #1` must be the first backup, not the second slot.
    next_ordinal = start_ordinal
    for name in preferred:
        if not name or name in seen:
            continue  # the primary is never its own backup, and a repeat adds nothing
        seen.add(name)
        candidates.append(
            ServiceCandidate(
                ordinal=next_ordinal,
                provider=str(name),
                model=str(model) if model else None,
                source=SOURCE_AGENT,
            )
        )
        next_ordinal += 1
    return candidates


def _candidate_from_override(override: str, ordinal: int) -> ServiceCandidate:
    """A ``provider/model`` override string as a candidate."""
    provider, _, model = override.partition("/")
    return ServiceCandidate(
        ordinal=ordinal,
        provider=provider or override,
        model=model or None,
        source=SOURCE_OVERRIDE,
    )


def override_candidate(override: str, ordinal: int = 0) -> ServiceCandidate:
    """Rung 1 of the ladder, standalone.

    A caller holding an explicit ``provider/model`` and NO session in hand (the title service's
    override path when no db was passed) still resolves that rung THROUGH this module: the
    override's ``provider/model`` split has exactly one definition here, and a caller that parsed
    the string itself would be the second answer this arc exists to remove.

    ``resolve(..., override=...)`` remains the way to ask when a session IS available — it reports
    the rung in the result. This is for the sessionless form only.
    """
    return _candidate_from_override(override, ordinal)


def _renumber(candidates: Sequence[ServiceCandidate], start: int) -> list[ServiceCandidate]:
    """The same candidates with ordinals renumbered from ``start`` — a chain's own positions.

    Used when one rung supplies the PRIMARY and a lower one supplies the backups: `backup #1` must
    be the first backup of THIS chain, not whatever ordinal the candidate carried in the chain it
    came from.
    """
    return [replace(candidate, ordinal=start + offset) for offset, candidate in enumerate(candidates)]


async def _load_capability(db: AsyncSession, key: str) -> Optional[Capability]:
    """The capability row and its candidates, or None when the key is not configured."""
    result = await db.execute(
        select(Capability)
        .options(selectinload(Capability.services))
        .where(Capability.key == key)
    )
    return result.scalar_one_or_none()


async def _class_candidates(
    db: AsyncSession, row: CapabilityService, location: str
) -> list[ServiceCandidate]:
    """Every active provider row OF THAT CLASS, best-first.

    ``(priority, name)`` — ``priority`` was written by two surfaces and read by no selector before
    this; here it finally orders a class. ``name`` breaks ties so the order is deterministic.
    """
    result = await db.execute(
        select(Provider).where(Provider.is_active).order_by(Provider.priority, Provider.name)
    )
    candidates: list[ServiceCandidate] = []
    for provider in result.scalars().all():
        if provider_location(provider.provider_type, provider.base_url) != location:
            continue
        candidate = _candidate_from_row(provider, row.ordinal, SOURCE_CLASS)
        candidates.append(
            ServiceCandidate(
                ordinal=candidate.ordinal,
                provider=candidate.provider,
                provider_id=candidate.provider_id,
                provider_type=candidate.provider_type,
                model=candidate.model,
                location=candidate.location,
                endpoint=candidate.endpoint,
                require_location=location,
                thinking=row.thinking,
                source=SOURCE_CLASS,
            )
        )
    return candidates


async def _candidates_for(
    db: AsyncSession, capability: Capability
) -> list[ServiceCandidate]:
    """The configured chain, in order, with anything unusable reported loudly."""
    ordered = sorted(
        (svc for svc in capability.services if svc.enabled), key=lambda s: (s.ordinal, s.id or 0)
    )
    candidates: list[ServiceCandidate] = []

    for row in ordered:
        if row.provider_id is not None:
            provider = (
                await db.execute(select(Provider).where(Provider.id == row.provider_id))
            ).scalar_one_or_none()
            if provider is None:
                # Cannot happen while the FK cascades — but a resolution that silently loses a
                # backup is the defect this arc exists to remove, so it says so.
                logger.error(
                    "capability '%s': candidate %s points at provider %s which does not exist — "
                    "SKIPPED",
                    capability.key,
                    row.id,
                    row.provider_id,
                )
                continue
            candidate = _candidate_from_row(provider, row.ordinal, SOURCE_ROW)
            candidates.append(
                ServiceCandidate(
                    ordinal=candidate.ordinal,
                    provider=candidate.provider,
                    provider_id=candidate.provider_id,
                    provider_type=candidate.provider_type,
                    # An explicit model on the row WINS over the provider's own default
                    model=row.model or candidate.model,
                    location=candidate.location,
                    endpoint=candidate.endpoint,
                    thinking=row.thinking,
                    source=SOURCE_ROW,
                )
            )
        elif row.require_location:
            found = await _class_candidates(db, row, row.require_location)
            if not found:
                logger.error(
                    "capability '%s': candidate %s wants a '%s' provider and none is active — "
                    "that slot resolves to nothing",
                    capability.key,
                    row.id,
                    row.require_location,
                )
            candidates.extend(found)
        elif row.service_name:
            candidates.append(
                ServiceCandidate(
                    ordinal=row.ordinal,
                    service_name=row.service_name,
                    model=row.model,
                    thinking=row.thinking,
                    source=SOURCE_NAMED,
                )
            )
        else:
            logger.error(
                "capability '%s': candidate %s names NO service (provider_id, require_location and "
                "service_name are all empty) — it can never be attempted",
                capability.key,
                row.id,
            )

    return candidates


async def resolve(
    db: AsyncSession,
    capability: str,
    *,
    agent: Any = None,
    override: Optional[str] = None,
) -> ResolvedService:
    """Resolve one capability to its ordered service chain — see the module docstring for the ladder.

    Args:
        db: database session (the capability rows and the provider rows are both read here).
        capability: the capability's slug ('title', 'chat', 'workflow-llm').
        agent: the agent asking, when the caller wants the per-agent rung — the chat path passes one.
        override: an explicit ``provider/model`` that beats everything.

    Returns:
        A :class:`ResolvedService`. Never raises for "nothing is configured": ``reason`` says which
        rung answered and ``candidates`` is empty only when there was nothing to answer with.
    """
    row = await _load_capability(db, capability)
    kind = row.kind if row is not None else KIND_LLM

    # OFF means OFF — checked BEFORE every rung (an override included). Falling through to the
    # global default row here would make "disabled" a comment rather than a state, and the
    # availability ruling needs a refusal a consumer can act on (phase 6, G1-F3).
    if row is not None and not row.enabled:
        logger.warning(
            "capability '%s' is DISABLED — nothing resolves. The caller must refuse; this is not "
            "a fall-through to the default row",
            capability,
        )
        return ResolvedService(capability=capability, kind=kind, reason=REASON_DISABLED)

    # What the capability's own configuration would offer as BACKUPS — read once, used by rungs 1
    # and 2: an explicit override or an agent's declaration picks the PRIMARY, and a configured
    # chain still supplies what to try after it. (An override is not a licence to forget the
    # backups, and an agent that declares no preferred list falls back to the configured order.)
    configured: list[ServiceCandidate] = []
    if row is not None and row.enabled:
        configured = await _candidates_for(db, row)

    if override:
        primary = _candidate_from_override(override, 0)
        backups = _renumber(
            [c for c in configured if c.provider != primary.provider], 1
        )
        return ResolvedService(
            capability=capability,
            kind=kind,
            reason=REASON_OVERRIDE,
            candidates=(primary, *backups),
        )

    if agent is not None:
        from_agent = _candidate_from_agent(agent, 0)
        if from_agent is not None:
            backups = _agent_backup_candidates(agent, 1)
            if not backups:
                backups = _renumber(
                    [c for c in configured if c.provider != from_agent.provider], 1
                )
            return ResolvedService(
                capability=capability,
                kind=kind,
                reason=REASON_AGENT,
                candidates=(from_agent, *backups),
            )

    if row is not None and row.enabled:
        if configured:
            return ResolvedService(
                capability=capability,
                kind=kind,
                reason=REASON_CAPABILITY,
                candidates=tuple(configured),
            )

    # The global default row — the rung every LLM consumer sits on today.
    #
    # **IT IS AN LLM RUNG, AND IT IS SKIPPED FOR AN EMBEDDING CAPABILITY.** The default row is the
    # install's CHAT default; letting it answer "which server runs my embedding model" would be the
    # app deciding that whatever chat model happens to be default can embed — the class of second
    # answer this arc removes, and a quiet one (the resolution would read as configured). The
    # embedding family reports the gap instead (`domain/providers/embeddings.py`; the ruling in
    # EXA'S INSTALLATION SKILL).
    if kind != KIND_EMBEDDING:
        from app.domain.providers.config_service import DefaultProviderService

        default = await DefaultProviderService().get_default_provider(db)
        if default is not None and default.id is not None:
            return ResolvedService(
                capability=capability,
                kind=kind,
                reason=REASON_GLOBAL_DEFAULT,
                candidates=(
                    ServiceCandidate(
                        ordinal=0,
                        provider=default.name,
                        provider_id=default.id,
                        provider_type=default.provider_type,
                        model=default.default_model or None,
                        endpoint=resolve_endpoint(
                            default.provider_type or default.name,
                            getattr(default, "base_url", None),
                            default.name,
                        ),
                        location=default.location,
                        source=SOURCE_DEFAULT,
                    ),
                ),
            )

    logger.warning(
        "capability '%s': nothing resolved — no enabled candidate and no default provider row. "
        "The caller is expected to fail loudly (this is the last rung)",
        capability,
    )
    return ResolvedService(capability=capability, kind=kind, reason=REASON_NONE)


async def list_capabilities(db: AsyncSession) -> Sequence[Capability]:
    """Every capability, candidates loaded and ordered — the read-out's source."""
    result = await db.execute(
        select(Capability).options(selectinload(Capability.services)).order_by(Capability.key)
    )
    return result.scalars().all()


# ── THE STRUCTURE SEED ──────────────────────────────────────────────────────
#
# The ruling's split (2026-10-10): capability KEYS and a row's SHELL are
# STRUCTURE — "an empty container is not an opinion" — so they ship with the
# install and need nobody's consent. Their VALUES (which model, which endpoint)
# are offered by the setup step, never seeded here.
#
# The nine consumers, in the order a surface lists them.
CAPABILITY_SEED: tuple[tuple[str, str, str], ...] = (
    ("title", "Title service", KIND_LLM),
    ("chat", "Chat", KIND_LLM),
    ("workflow-llm", "Workflow LLM steps", KIND_LLM),
    ("memory", "Memory manager", KIND_LLM),
    ("summary", "Conversation summary", KIND_LLM),
    ("stt", "Speech to text", KIND_SPEECH),
    ("tts", "Text to speech", KIND_SPEECH),
    ("exa", "Exa (external agent)", KIND_PROCESS),
    ("embeddings", "Embeddings", KIND_EMBEDDING),
)


async def ensure_capability_rows(db: AsyncSession) -> list[str]:
    """Create the capability rows that ship with the install. Idempotent.

    Returns the keys it created (empty on a warm install), so a caller can say
    what it did instead of assuming.

    WHY THIS EXISTS AT ALL: no production code ever created these rows — they
    were made by hand on a developer's install, so a FRESH one had none, and
    `resolve()` defaults a missing row's kind to ``llm``. An absent `embeddings`
    row therefore fell through to the global default CHAT provider — exactly the
    "whatever chat model happens to be default can embed" second answer the
    ruling forbids. The row is what makes that refusal possible.
    """
    existing = set((await db.execute(select(Capability.key))).scalars().all())
    created: list[str] = []
    for key, label, kind in CAPABILITY_SEED:
        if key in existing:
            continue
        db.add(Capability(key=key, label=label, kind=kind, enabled=True))
        created.append(key)
    if created:
        await db.commit()
        logger.info("capability rows created: %s", ", ".join(created))
    return created


def describe_chain(resolved: ResolvedService) -> str:
    """`deepseek/deepseek-v4-flash -> llama/local-model` — one line, for a log or a payload."""
    return " -> ".join(c.describe() for c in resolved.candidates) or "(nothing configured)"


async def resolve_named_service(
    db: AsyncSession, capability: str
) -> tuple[Optional[str], str]:
    """A NAMED-service capability's `service_name` and the reason that answered.

    The speech half of `resolve()` (and the Exa process half): `stt`/`tts`/`exa` name an engine or a
    process rather than a provider row, so a caller wants the NAME — plus the reason, for its own
    failure message — and not a client.

    `(None, REASON_NONE)` means nothing resolved. A caller must then fail LOUDLY; there is no name
    written in code to fall back to, which is the whole point of the capability.
    """
    resolved = await resolve(db, capability)
    primary = resolved.primary
    return (primary.service_name if primary is not None else None), resolved.reason


# ── The write path — replacing a capability's whole chain (phase 6, group 1) ─────────────────────
#
# The sub-area shipped READ-ONLY (phase 1.4): the speech pages' engine switch forced a
# one-candidate writer into existence — `set_speech_service`, whose own removal condition was
# *"retired when phase 6 exposes the general write API"*. That condition is met, so it is GONE (phase
# 6, G2-F4): the speech rows are edited like every other capability's, and `PUT /tts/config`'s
# retired `provider` is refused rather than written. Before this path existed the availability
# ruling's *"disabled or fallback, either of which can be configured"* had nowhere to be configured;
# this is that write path.
#
# The chain is written as a UNIT. The order is not decoration — it is what a failure path names
# ("attempt 1 (backup #1)") — so a per-candidate endpoint would have a window where two candidates
# share an ordinal, while the editor already holds the whole chain.

# The two values `provider_location` can answer, restated as the WRITE vocabulary: a candidate may
# ask for a CLASS rather than a row ("prefer local"), and a typo in that word would otherwise sit
# in the table resolving to nothing at every turn.
LOCATION_CLASSES: tuple[str, ...] = ("local", "cloud")

# Which capability keys name an ENGINE rather than a provider row, and which registry is the
# authority on those names. A name nothing can build is refused at the WRITE, where the writer can
# still read the message — never stored to fail at a turn. The speech keys are the ones with a
# registry today; a process key ('exa') names something this app does not enumerate, so it is
# refused only for being empty.
_NAMED_SERVICE_REGISTRIES: dict[str, tuple[str, str]] = {
    "tts": ("app.domain.tts.registry", "get_tts_provider"),
    "stt": ("app.domain.stt.registry", "get_stt_provider"),
}


@dataclass(frozen=True)
class CandidateSpec:
    """One candidate as a WRITE supplies it — the three forms, exactly one per candidate.

    Deliberately neither the ORM row nor a pydantic model: the domain's write path takes a plain
    value (a test can build one with no schema in play) and the router builds these from its own
    request model. ``ordinal`` is ABSENT on purpose — a candidate's position in the list IS its
    ordinal, so the order has one home rather than two that can disagree.
    """

    provider_id: Optional[int] = None
    require_location: Optional[str] = None
    service_name: Optional[str] = None
    model: Optional[str] = None
    thinking: Optional[str] = None
    enabled: bool = True

    def describe(self) -> str:
        """`provider #3/model` · `prefer local` · `edge` — one line for the write's log."""
        if self.provider_id is not None:
            return f"provider #{self.provider_id}" + (f"/{self.model}" if self.model else "")
        if self.require_location:
            return f"prefer {self.require_location}"
        return self.service_name or "(unnamed)"


def _thinking_levels() -> tuple[str, ...]:
    """The reasoning vocabulary — imported on FIRST USE, not at module load.

    The pipeline package that owns it imports the vector store, which imports
    `domain.providers.embeddings`, which imports this module: a module-level
    import here is a cycle waiting for the first process that imports this module
    before the pipeline (2026-11-18).
    """
    from app.services.cognitive_pipeline.reasoning_support import THINKING_LEVELS

    return tuple(THINKING_LEVELS)


def _validate_candidate(spec: CandidateSpec, index: int, capability_key: str) -> None:
    """Refuse a candidate the resolver could never attempt — naming which candidate and why.

    Raises ``ValueError``: the house code for a business-rule refusal (the router turns it into a
    **400**, where a schema-level refusal is a 422).
    """
    named = [
        spec.provider_id is not None,
        bool(spec.require_location),
        bool(spec.service_name),
    ]
    if sum(named) != 1:
        raise ValueError(
            f"candidate {index}: name exactly ONE of provider_id, require_location or "
            f"service_name ({sum(named)} were named)"
        )
    if spec.require_location and spec.require_location not in LOCATION_CLASSES:
        raise ValueError(
            f"candidate {index}: unknown location class '{spec.require_location}' "
            f"(expected one of {', '.join(LOCATION_CLASSES)})"
        )
    if spec.thinking is not None and spec.thinking not in _thinking_levels():
        raise ValueError(
            f"candidate {index}: unknown thinking '{spec.thinking}' "
            f"(expected one of {', '.join(_thinking_levels())})"
        )

    entry = _NAMED_SERVICE_REGISTRIES.get(capability_key)
    if entry is not None and spec.service_name:
        module_name, func_name = entry
        module = importlib.import_module(module_name)
        try:
            getattr(module, func_name)(spec.service_name)
        except ValueError as exc:
            # The registry's own message ("Unknown TTS provider: x") already names the
            # vocabulary; adding the candidate's index is what makes a multi-row PUT readable.
            raise ValueError(f"candidate {index}: {exc}") from exc


async def _validate_provider_exists(db: AsyncSession, spec: CandidateSpec, index: int) -> None:
    """A candidate naming a provider row gets an honest answer about whether that row exists."""
    if spec.provider_id is None:
        return
    found = (
        await db.execute(select(Provider.id).where(Provider.id == spec.provider_id))
    ).scalar_one_or_none()
    if found is None:
        raise ValueError(f"candidate {index}: no provider with id {spec.provider_id}")


async def replace_chain(
    db: AsyncSession,
    capability_key: str,
    candidates: Sequence[CandidateSpec],
    *,
    label: Optional[str] = None,
    enabled: Optional[bool] = None,
) -> Capability:
    """Replace a capability's WHOLE ordered chain — the general write path (phase 6, G1-F1/F2).

    Every candidate is validated BEFORE anything is written, so a refused request leaves the
    stored chain exactly as it was: the chain is replaced as a unit, never half-applied.

    **Zero candidates is LEGAL, and it is not the same state as "off".** An empty chain means *this
    capability configures nothing of its own*, so the resolver's ladder continues to the global
    default row; "off" is ``enabled=False``, which short-circuits every rung with
    ``reason='disabled'``. Both states are written here and they must not be confused — an empty
    chain that reads as "disabled" is the second answer this arc removes.

    Absence semantics: ``label`` and ``enabled`` are overwrite-only (the house shape) — a ``None``
    leaves the field alone. An explicit clear is not expressible yet and nothing needs it.

    Does NOT commit: the request's session dependency commits when the handler returns, and a
    service that commits too wedges the handler (the double-commit pitfall).

    Returns:
        The capability with its new chain loaded, so the caller can serialize what it wrote.

    Raises:
        ValueError: an unknown capability, or a candidate that cannot be attempted.
    """
    cap_row = await _load_capability(db, capability_key)
    if cap_row is None:
        raise UnknownCapabilityError(f"Unknown capability: {capability_key}")

    for index, spec in enumerate(candidates):
        _validate_candidate(spec, index, capability_key)
        await _validate_provider_exists(db, spec, index)

    # The relationship, not a bulk DELETE: `cascade="all, delete-orphan"` removes the old rows and
    # appending the new ones keeps `cap_row.services` correct for the caller in THIS session (a
    # bulk statement would leave the loaded collection stale, and an async lazy load raises).
    cap_row.services.clear()
    for ordinal, spec in enumerate(candidates):
        cap_row.services.append(
            CapabilityService(
                ordinal=ordinal,
                provider_id=spec.provider_id,
                require_location=spec.require_location,
                service_name=spec.service_name,
                model=spec.model,
                thinking=spec.thinking,
                enabled=spec.enabled,
            )
        )

    if label is not None:
        cap_row.label = label
    if enabled is not None:
        cap_row.enabled = enabled

    await db.flush()

    # THE SAVE THAT HAS TO REACH THE RUNNING PROCESS (option A of the embedding-configuration issue,
    # 2026-10-12). The two RAG vector stores are singletons whose embedding service is captured at
    # FIRST CONSTRUCTION, so before this call a model saved on the Capabilities page waited for a
    # restart. `replace_chain` is the capability CHOKE POINT — every caller of the one write path comes
    # through here, which is why the reset lives beside the write rather than in the router that
    # happens to call it today.
    if capability_key == _embeddings_capability_key():
        _drop_embedding_stores()

    logger.info(
        "✏️ capability '%s': chain replaced — %s%s",
        capability_key,
        " -> ".join(spec.describe() for spec in candidates) or "(nothing configured)",
        "" if enabled is None else f" | enabled={enabled}",
    )
    return cap_row


def _embeddings_capability_key() -> str:
    """The `embeddings` capability's key — imported HERE because `embeddings` imports this module."""
    from app.domain.providers.embeddings import EMBEDDINGS_CAPABILITY_KEY  # noqa: PLC0415

    return EMBEDDINGS_CAPABILITY_KEY


def _drop_embedding_stores() -> None:
    """Forget the RAG vector stores so the next use rebuilds them from what was just written.

    The imports are lazy for the same reason the handlers' are: `tools/builtin/__init__` reaches back
    into the app, and this module is imported by the embeddings vocabulary.

    **`close=False` is deliberate.** An ingest may be mid-flight on one of those connections; left
    open, that run finishes against the service it started with, into the table that existed then.
    Closing it would break the ingest, and the point of this call is to reach the NEXT use.
    """
    from app.domain.tools.builtin.code_vector_store import CodeVectorStore  # noqa: PLC0415
    from app.domain.tools.builtin.doc_vector_store import DocVectorStore  # noqa: PLC0415

    DocVectorStore.reset_instance(close=False)
    CodeVectorStore.reset_instance(close=False)
    logger.info("🧠 embedding stores dropped — the next use rebuilds from the new chain")


# ── The attempts — walking an ORDERED chain, one failure at a time ───────────────────────────────
#
# THE GENERALIZED FAILOVER (R3). Before this, each surface that failed over carried its own loop
# AND its own chain — the executor's walk plus a hardcoded list, the completion router's copy of it,
# and a second walker inside `provider_completion_service`. Now the ORDER comes from `resolve()` and
# the walking happens here, once, so what an attempt IS (and what a failed one logs) has one home.


@dataclass(frozen=True)
class Attempt:
    """One attempt the chain made: which service, and how it ended."""

    ordinal: int
    provider: Optional[str] = None
    model: Optional[str] = None
    service_name: Optional[str] = None
    succeeded: bool = False
    error: str = ""

    @property
    def label(self) -> str:
        """`deepseek/deepseek-v4-flash` · `piper` — the handle a log line or a statement names."""
        if self.provider:
            return f"{self.provider}/{self.model}" if self.model else self.provider
        return self.service_name or "(unnamed)"

    @property
    def role(self) -> str:
        """`primary` · `backup #2` — WHICH attempt this was, not only what it was."""
        return "primary" if self.ordinal == 0 else f"backup #{self.ordinal}"


@dataclass(frozen=True)
class AttemptOutcome:
    """The chain's result: what answered, and every attempt that led to it."""

    response: Any
    attempts: tuple[Attempt, ...] = ()

    @property
    def winner(self) -> Optional[Attempt]:
        """The attempt that answered."""
        return next((a for a in self.attempts if a.succeeded), None)

    @property
    def failed_over(self) -> bool:
        """True when something failed before an answer arrived — the degraded case."""
        return any(not a.succeeded for a in self.attempts)

    @property
    def fell_back_to(self) -> tuple[str, ...]:
        """The services tried AFTER the primary — what a caller's warning names."""
        return tuple(a.label for a in self.attempts[1:])

    def describe(self) -> str:
        """`primary` · `deepseek/x -> llama/x` — one line for the log or a statement."""
        return " -> ".join(a.label for a in self.attempts) or "(nothing attempted)"


async def attempt_chain(
    candidates: Sequence[ServiceCandidate],
    *,
    call: Callable[[ServiceCandidate], Awaitable[Any]],
    capability: str = "",
    fallbacks: bool = True,
) -> AttemptOutcome:
    """Drive an ORDERED chain: the primary first, then its backups.

    The order is the RESOLVER's; this function only walks it. It holds NO session — the caller
    resolved the chain (that is the db-side half, `resolve()`) and supplies `call`, which turns one
    candidate into one attempt, because what a call NEEDS (a client, a key, kwargs) differs per
    kind and per surface.

    Every failure is logged as it happens, naming the service, its model and WHICH attempt it was
    (the user, 2026-09-30: *"a failure needs to be logged, including the backup service failure"*),
    so a chain that degraded is diagnosable from the log alone.

    The LAST error is what the caller sees: a chain that runs out raises it, and a chain that was
    not allowed to fail over raises the primary's (the `fallback_enabled=False` semantics — fail
    visibly, never silently mask).

    Args:
        candidates: the ordered chain, primary first (`ordinal` 0).
        call: the caller's one-attempt function.
        capability: the capability's key, for the log line.
        fallbacks: False = the primary only, and its error propagates.

    Returns:
        An :class:`AttemptOutcome` — the response plus every attempt and how it ended.

    Raises:
        ValueError: an empty chain (nothing was resolved — the caller must not call this).
        Exception: the last attempt's error when no candidate answered.
    """
    if not candidates:
        raise ValueError("attempt_chain needs at least one candidate to attempt")

    attempts: list[Attempt] = []
    last_error: Optional[BaseException] = None

    for index, candidate in enumerate(candidates):
        attempt = Attempt(
            ordinal=candidate.ordinal,
            provider=candidate.provider,
            model=candidate.model,
            service_name=candidate.service_name,
        )
        try:
            response = await call(candidate)
        except Exception as exc:  # noqa: BLE001 — the NEXT candidate is the remedy
            last_error = exc
            attempts.append(replace(attempt, error=f"{type(exc).__name__}: {exc}"))
            logger.error(
                "capability '%s': attempt %d (%s) '%s' FAILED — %s",
                capability or "?",
                attempt.ordinal,
                attempt.role,
                attempt.label,
                exc,
                exc_info=True,
                extra={
                    "capability": capability,
                    "ordinal": attempt.ordinal,
                    "attempt_role": attempt.role,
                    "provider": attempt.provider,
                    "model": attempt.model,
                    "error_type": type(exc).__name__,
                },
            )
            if index == 0 and not fallbacks:
                raise  # fail visibly — never silently mask
            continue

        attempts.append(replace(attempt, succeeded=True))
        return AttemptOutcome(response=response, attempts=tuple(attempts))

    logger.error(
        "capability '%s': the whole chain failed (%s) — the last failure is what the caller reports",
        capability or "?",
        " -> ".join(a.label for a in attempts),
        extra={"capability": capability, "chain": [a.label for a in attempts]},
    )
    assert last_error is not None  # the loop cannot exit with no attempt and no error
    raise last_error

