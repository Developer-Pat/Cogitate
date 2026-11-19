"""The capabilities sub-area — "what does each part of the app actually use?"

The service-capability arc, Phase 1.4. The user's ruling (2026-09-30): *"a unified provider service
locator that exposes the different llm providers as sub areas inside the api — so you can fetch the
llm provider for TTS or title service or system agent as needed."* This is that sub-area. It answers
the question the app could not answer before, per capability —

* **which service** answers it right now,
* **what the backups are**, in the order they would be tried,
* and **why** (which rung of the ladder resolved it: capability config, the global default, an
  agent's own profile, or an explicit override).

`PUT /providers/capabilities/{key}` is the EDIT half (phase 6, group 1): it replaces a capability's
whole ordered chain, which is what lets the availability ruling's *"the agent is either disabled or
uses a fallback, either of which can be configured"* be configured at all. Its refusals are **400**
(a candidate that cannot be attempted) and **404** (a key that is not a capability), and no write
ever invents a capability — those are seeded vocabulary.

The READ half takes an optional `agent_id` (phase 6, G2-F2), which resolves each capability through
the ladder's agent rung — *"what will this agent use?"*. It applies **only** to the capabilities a
live consumer actually passes an agent for (`AGENT_INFLUENCED_CAPABILITIES`, today `chat` alone), so
the read-out can never show a chain a capability would not use; every other card answers exactly as
the sessionless view does.

That reason is not decoration: a failure statement can only finger the offending LLM if the
resolution that chose it is in one place (user, 2026-09-30), and a reader can only act on "the title
service is using X" if X was chosen deliberately rather than by whichever default row happened to be
set.

Registered BEFORE ``providers_router`` in ``api/v1/router.py`` — that router owns the dynamic
``/{provider_id}`` route and must stay last (the house ordering rule).
"""

import logging
from typing import Any, Dict, List, Optional, Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Paths
from app.core.database import get_db_session
from app.domain.providers.embeddings import (
    EMBEDDINGS_CAPABILITY_KEY,
    configuration_note,
    resolve_embedding_service,
)
from app.domain.rag.service import declared_index_width
from app.domain.providers.availability import (
    STATE_UNKNOWN,
    Availability,
    read_availability_for,
)
from app.domain.providers.capabilities import (
    AGENT_INFLUENCED_CAPABILITIES,
    KIND_LLM,
    KINDS,
    CandidateSpec,
    ResolvedService,
    ServiceCandidate,
    UnknownCapabilityError,
    describe_chain,
    list_capabilities,
    replace_chain,
    resolve,
)
from app.infrastructure.database.models import Agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/providers/capabilities", tags=["provider-capabilities"])


class CandidateOut(BaseModel):
    """One attemptable service in the chain.

    Mirrors `CandidateIn` so a chain can be READ and sent straight back — `provider_id`,
    `require_location` and `service_name` are the three forms a write accepts, `enabled` is the
    row's own switch, and `source` says which rung produced this candidate (`row` / `class` /
    `named` on a configured chain; `agent`, `override`, `default` when a rung above answered).
    """

    ordinal: int
    provider: Optional[str] = None
    provider_id: Optional[int] = None
    provider_type: Optional[str] = None
    model: Optional[str] = None
    # Which form this candidate was WRITTEN as — the class form is the one a write must send back
    # to keep "prefer local" configuration rather than a row that happens to be local today.
    require_location: Optional[str] = None
    location: Optional[str] = None
    service_name: Optional[str] = None
    thinking: Optional[str] = None
    enabled: bool = True
    source: str = "row"
    # ── AVAILABILITY (phase 6, group 5) ──────────────────────────────────────────────────────────
    # The state the ONE availability read last found for this candidate's service:
    # `available` | `down-by-occupancy` | `down` | `unconfigured` | `unknown`. `available` is the
    # derived boolean a surface keys on — **None means "never checked"**, deliberately NOT False,
    # so a page can say so instead of calling an unprobed service broken. `checked_at` rides with
    # it because the copy must own the staleness window.
    availability_state: str = STATE_UNKNOWN
    available: Optional[bool] = None
    availability_reason: Optional[str] = None
    checked_at: Optional[str] = None


class CapabilityOut(BaseModel):
    """A capability and what it resolves to right now."""

    key: str
    label: Optional[str] = None
    kind: str = KIND_LLM
    enabled: bool = True
    # Which rung answered: 'capability config' | 'global default' | 'agent profile' | 'override' | 'none'
    reason: str
    # `deepseek/deepseek-v4-flash -> llama/qwen3` — one line, for a log or a tooltip
    chain: str
    primary: Optional[CandidateOut] = None
    backups: List[CandidateOut] = []
    # THE CAPABILITY'S OWN STORED ROWS, in order — what the EDIT path reads and writes.
    #
    # This is NOT the resolution above, and an editor fed by the resolution would be wrong: the
    # ladder can answer with an AGENT's declaration (rung 2), a class candidate expands into every
    # matching row, and a candidate switched OFF is filtered out of the resolution entirely. So a
    # chain read from `primary`/`backups` cannot be written back — it would drop a disabled row and
    # rewrite expanded rows as if they were the stored ones.
    configured: List[CandidateOut] = []
    # WHAT TO SAY WHEN THE SAVE DOES NOT REACH THE RUNNING PROCESS — null unless it does.
    #
    # The `embeddings` capability is the one whose answer the RAG vector stores CAPTURE at first
    # construction (they are singletons), so a save here is the one save that the process will not
    # read. The field carries the sentence that says so — the app reports rather than pretends, and
    # the surface that shows it is the page the unconfigured report already points at.
    note: Optional[str] = None


class CapabilitiesResponse(BaseModel):
    """The whole read-out, plus the kinds this revision understands."""

    capabilities: List[CapabilityOut]
    kinds: List[str]
    total: int


class CandidateIn(BaseModel):
    """One candidate as the EDIT path accepts it — exactly one of the three forms.

    Mirrors `CandidateOut` so a client can read a chain and send it back, minus the resolved
    fields (`provider`, `provider_type`, `location`, `source`) which the resolver derives rather
    than accepts. `ordinal` is absent: a candidate's position in the list IS its ordinal.
    """

    provider_id: Optional[int] = None
    require_location: Optional[str] = None
    service_name: Optional[str] = None
    model: Optional[str] = None
    thinking: Optional[str] = None
    enabled: bool = True


class CapabilityUpdate(BaseModel):
    """A capability's whole chain, plus its own two editable fields.

    `candidates` is REQUIRED — this is a replace, not a patch. Sending the full ordered list is
    what makes the order unambiguous (the chain is what a failure path names), and a client with
    a chain in hand — the editor — always has it.
    """

    label: Optional[str] = None
    enabled: Optional[bool] = None
    candidates: List[CandidateIn]


def _candidate_out(
    candidate: ServiceCandidate, availability: Optional[Availability] = None
) -> CandidateOut:
    """One candidate as the wire shape, with its availability when one was read.

    A candidate with NO availability is left `unknown` rather than stamped False: a named engine
    (a speech engine, the external process) is a different question this read does not answer, and
    an unprobed row is not a broken one.
    """
    return CandidateOut(
        ordinal=candidate.ordinal,
        provider=candidate.provider,
        provider_id=candidate.provider_id,
        provider_type=candidate.provider_type,
        model=candidate.model,
        require_location=candidate.require_location,
        location=candidate.location,
        service_name=candidate.service_name,
        thinking=candidate.thinking,
        source=candidate.source,
        availability_state=availability.state if availability else STATE_UNKNOWN,
        available=availability.available if availability else None,
        availability_reason=availability.reason if availability else None,
        checked_at=availability.checked_at if availability else None,
    )


def _capability_out(
    key: str,
    label: Optional[str],
    kind: str,
    enabled: bool,
    resolved: ResolvedService,
    configured: List[CandidateOut],
    availability: Optional[Dict[str, Availability]] = None,
    note: Optional[str] = None,
) -> CapabilityOut:
    """A capability plus its resolution as the wire shape, stamped with what is up right now."""
    av_map: Dict[str, Availability] = availability or {}
    return CapabilityOut(
        key=key,
        label=label,
        kind=kind,
        enabled=enabled,
        reason=resolved.reason,
        chain=describe_chain(resolved),
        primary=(
            _candidate_out(resolved.primary, av_map.get(resolved.primary.provider or ""))
            if resolved.primary
            else None
        ),
        backups=[
            _candidate_out(candidate, av_map.get(candidate.provider or ""))
            for candidate in resolved.backups
        ],
        configured=configured,
        note=note,
    )


def _configured_out(capability: Any) -> List[CandidateOut]:
    """The capability's OWN stored rows, in order — the EDIT path's read.

    Built from the rows rather than from a resolution, and that is the whole point: the three forms
    are kept AS WRITTEN (a class candidate is not expanded into the rows it happens to match today),
    a switched-OFF row is INCLUDED (it is a row somebody stored, and an editor must be able to see
    it to keep or remove it — a resolution filters it out), and no rung above the capability can
    change what this list says. `source='stored'` keeps it distinguishable from a resolved candidate.
    """
    rows = sorted(capability.services, key=lambda service: (service.ordinal, service.id or 0))
    return [
        CandidateOut(
            ordinal=row.ordinal,
            provider_id=row.provider_id,
            require_location=row.require_location,
            service_name=row.service_name,
            model=row.model,
            thinking=row.thinking,
            enabled=row.enabled,
            source="stored",
        )
        for row in rows
    ]


async def _availability_for(
    db: AsyncSession, resolved: Sequence[ResolvedService]
) -> Dict[str, Availability]:
    """ONE cached, concurrent availability pass over the services the shown chains name.

    The pass itself lives in the DOMAIN (`availability.read_availability_for`), because a second
    surface now makes the same one — the agent profiles' own "cannot run now" badge — and two
    implementations could answer "is llama up?" differently. This is the thin, session-holding
    caller.
    """
    return await read_availability_for(db, resolved)


async def _load_agent(db: AsyncSession, agent_id: Optional[int]) -> Optional[Agent]:
    """The agent whose declaration the caller asked to resolve for, or None for the sessionless view.

    An unknown id is a **404** rather than a silent sessionless answer: 'no such agent' and 'no agent
    asked for' are different facts, and a page that fell back quietly would show the sessionless
    chain under the agent's name — the second answer this arc exists to remove.
    """
    if agent_id is None:
        return None
    agent = (await db.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No agent with id {agent_id}",
        )
    return agent


@router.get("", response_model=CapabilitiesResponse)
async def get_capabilities(
    agent_id: Optional[int] = Query(
        None,
        description=(
            "Resolve for the agent with this id — the ladder's agent rung (the agent's own "
            "declaration). It applies only to the capabilities a live consumer passes an agent for "
            "(`AGENT_INFLUENCED_CAPABILITIES`), so a card never shows a chain the capability would "
            "not use. Omit it for the sessionless view."
        ),
    ),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """Every capability and the service chain each one resolves to right now.

    With `agent_id`, each capability whose consumer really passes an agent resolves through rung 2
    instead — so the page can answer *"what will this agent use?"* without claiming the agent drives
    capabilities it never touches (an agent's declaration is its LLM; the title service, for one,
    resolves with no agent at all). Everything else answers exactly as the sessionless view does.
    """
    agent = await _load_agent(db, agent_id)
    rows = await list_capabilities(db)
    resolved_rows: List[Any] = []
    for row in rows:
        resolved = await resolve(
            db,
            row.key,
            agent=agent if row.key in AGENT_INFLUENCED_CAPABILITIES else None,
        )
        resolved_rows.append((row, resolved))
    availability_map = await _availability_for(db, [r for _, r in resolved_rows])
    out: List[CapabilityOut] = []
    for row, resolved in resolved_rows:
        out.append(
            _capability_out(
                row.key,
                row.label,
                row.kind,
                row.enabled,
                resolved,
                configured=_configured_out(row),
                availability=availability_map,
            )
        )
    return CapabilitiesResponse(capabilities=out, kinds=list(KINDS), total=len(out))


@router.get("/{key}", response_model=CapabilityOut)
async def get_capability(key: str, db: AsyncSession = Depends(get_db_session)) -> Any:
    """One capability's resolution.

    An unknown key is a 404 rather than an empty answer: 'not configured' and 'configured to
    nothing' are different facts, and the resolver already distinguishes them in ``reason``.
    """
    rows = await list_capabilities(db)
    row = next((r for r in rows if r.key == key), None)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No capability named '{key}'",
        )
    resolved = await resolve(db, row.key)
    availability_map = await _availability_for(db, [resolved])
    return _capability_out(
        row.key,
        row.label,
        row.kind,
        row.enabled,
        resolved,
        configured=_configured_out(row),
        availability=availability_map,
    )


@router.put("/{key}", response_model=CapabilityOut)
async def update_capability(
    key: str,
    payload: CapabilityUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """Replace a capability's ordered chain — the EDIT path.

    **The chain is written as a UNIT** (`candidates` is required): a candidate's position in the
    list IS its ordinal, so no request can leave two candidates sharing one, and a refused request
    leaves the stored chain untouched.

    **Zero candidates is legal, and it is NOT the same state as "off".** An empty chain means this
    capability configures nothing of its own, so the ladder continues to the global default row;
    `enabled=false` switches the capability OFF, where the resolver answers `reason='disabled'` and
    a consumer must refuse rather than fall through.

    `label` and `enabled` are overwrite-only: a field left out of the request is left ALONE, and
    there is no way to express "clear the label" yet (nothing needs it).

    Refusals: **404** when the key is not a capability (the read path's own answer); **400** for a
    candidate that cannot be attempted — not exactly one of the three forms, an unknown provider
    id, an unknown location class, a thinking level outside the vocabulary, or a speech engine no
    registry can build.
    """
    try:
        row = await replace_chain(
            db,
            key,
            [
                CandidateSpec(
                    provider_id=candidate.provider_id,
                    require_location=candidate.require_location,
                    service_name=candidate.service_name,
                    model=candidate.model,
                    thinking=candidate.thinking,
                    enabled=candidate.enabled,
                )
                for candidate in payload.candidates
            ],
            label=payload.label,
            enabled=payload.enabled,
        )
    except UnknownCapabilityError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    resolved = await resolve(db, row.key)
    availability_map = await _availability_for(db, [resolved])
    # WHAT A SAVE CANNOT FIX (2026-10-12). The stores are now RESET by the write itself
    # (`replace_chain` → `_drop_embedding_stores`), so a saved model reaches the process on its next
    # use — the restart sentence this used to send is retired because it is no longer true. What no
    # reset repairs is the INDEX's width: `init_db` declares the vec table with `IF NOT EXISTS`, so it
    # keeps the width it was born with, and a model of another width leaves it behind. Say THAT here,
    # where the model is chosen.
    note: Optional[str] = None
    if row.key == EMBEDDINGS_CAPABILITY_KEY:
        note = configuration_note(
            await resolve_embedding_service(db), declared_index_width(Paths.rag_index_path)
        )
    return _capability_out(
        row.key,
        row.label,
        row.kind,
        row.enabled,
        resolved,
        configured=_configured_out(row),
        availability=availability_map,
        note=note,
    )
