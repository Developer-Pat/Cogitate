"""
Curated model service.

Business logic for the curated model list (the human-owned recommendation
layer, separate from provider_model_cache discovery).

Provides CRUD for /api/v1/curated-models and the default seed data used on
first load (mirrors the frontend curatedModels.ts config).
"""

import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update as sa_update

from app.infrastructure.database.models import CuratedModel, Provider, ProviderModelCache
from app.domain.providers.model_window import (
    cache_age_hours,
    cache_is_stale,
    needed_window_tokens,
    pairing_advice,
    provider_reasoning_claim,
    window_fit_warning,
)
from app.services.cognitive_pipeline.reasoning_support import level_from_claim

logger = logging.getLogger(__name__)


# The one-word descriptors a curated row can carry — WHAT THE MODEL IS FOR, one axis.
#
# The COST fact is deliberately NOT here: it is its own column (`is_free`, derived from the
# provider's cached pricing), and a word like "budget" only repeated it beside the badge. Nor
# is the retired editorial flag: the app does not privilege models (the cloud-providers arc's
# Phase 3). And a row may state NOTHING at all — `None` is the honest "nobody has described
# this row yet", which is why no layer anywhere defaults this field to a value.
# (matches frontend ModelCategory)
CURATED_CATEGORIES = {
    "chat",
    "code",
    "reasoning",
    "vision",
}

# The runtime homes a curated row can state — the column's own vocabulary
# (`models.py`: "Runtime home: local|cloud"). `any` is a SPEC-side value: the
# substitution matcher's `location: "any"` accepts every row, so a ROW carrying
# `any` could never be satisfied by a strict spec — a state with no meaning.
MODEL_LOCATIONS = ("local", "cloud")


# =========================================================================
# THE WINDOW VERIFICATION (the token-limit arc, E.4)
# =========================================================================
# A curated row's `context_length` is OUR statement; `provider_model_cache` holds
# the PROVIDER's own claim, captured by the app's discovery fetch. Verification is
# the comparison, and the fact wins: the row adopts the provider's number, and a
# disagreement is reported rather than quietly overwritten. **A stale claim
# verifies nothing** — it says what the provider said days ago — so a number can
# still be adopted where the row had none while `verified` stays False, which is
# the difference between "we recorded a number" and "we checked it".


@dataclass(frozen=True)
class WindowVerification:
    """What verifying one curated row against its provider found, and what it did."""

    curated_id: int
    provider: str
    model_id: str
    curated: Optional[int]          # what the row said before
    discovered: Optional[int]       # what the provider's own list says
    window: Optional[int]           # what the row says now
    verified: bool                  # does the row agree with a claim we stand behind?
    mismatch: bool                  # did the two numbers disagree?
    stale: bool                     # is the provider's claim past its TTL?
    age_hours: Optional[float]
    refreshed: bool                 # did we ask the provider again during this check?
    thinking_curated: str           # the row's declared level BEFORE this verification
    thinking_provider: Optional[str]  # the provider's own words, when it exposes any
    max_completion: Optional[int]   # the provider's own output cap, when it states one
    note: str
    # F.3: the level the row carries AFTER this verification (None = left unchanged)
    thinking_adopted: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        from dataclasses import asdict

        return asdict(self)


def provider_claim_from_raw(raw_data: Any) -> Tuple[Optional[str], Optional[int]]:
    """The provider's own THINKING signal and output cap, from its raw payload.

    Returns ``(thinking_signal, max_completion_tokens)``. The signal is the
    provider's own words — OpenRouter publishes ``reasoning: {mandatory,
    default_enabled}`` — and **deliberately not a level in our vocabulary**: mapping
    it to none/low/medium/high is F.3's ruling, because that level is what the
    reasoning FLOOR is keyed off. Reporting the provider's claim is E.4's job;
    deciding what it means for a budget is not.

    ``max_completion_tokens`` is the provider's own ceiling on an answer and is
    reported for the same reason: it is a number the app currently ignores, and F is
    where a ceiling is derived.
    """
    if not isinstance(raw_data, dict):
        return None, None
    payload = raw_data.get("_raw")
    if not isinstance(payload, dict):
        payload = raw_data

    signal: Optional[str] = None
    reasoning = payload.get("reasoning")
    if isinstance(reasoning, dict):
        parts = [
            f"{key}={value}"
            for key, value in reasoning.items()
            if isinstance(value, (bool, int, str))
        ]
        if parts:
            signal = "reasoning: " + ", ".join(sorted(parts))
    elif reasoning:
        signal = f"reasoning: {reasoning}"

    cap: Optional[int] = None
    top_provider = payload.get("top_provider")
    if isinstance(top_provider, dict):
        raw_cap = top_provider.get("max_completion_tokens")
        if isinstance(raw_cap, int) and raw_cap > 0:
            cap = raw_cap
    return signal, cap


def cost_from_raw(raw_data: Any, location: str = "cloud") -> Optional[bool]:
    """The provider's own COST verdict for one model, from its cached payload (Phase 4).

    Returns ``True`` (free to call), ``False`` (priced), or **``None`` — the honest
    unknown**, which is the reason this phase exists: the column used to be a
    non-nullable boolean defaulting to ``False``, so a model nobody had priced answered
    *paid* to a question no provider had answered. Two configured providers publish no
    price at all (deepseek's payload carries capabilities, ollama_cloud's carries
    neither) and 26 cached rows are unpriced, so the third state is not hypothetical.

    THE RULE, and where it reads: the prices live at ``_raw.pricing`` — NOT at
    ``pricing``, which no cached row carries — and a model is free when the payload
    prices it and **every** priced component is zero. Every component, not just
    ``prompt``/``completion``: a model that gives its tokens away but charges per
    request, per image or per cache write is not free to call. (Measured on the live
    catalog: no row distinguishes the two readings today — this is the one that stays
    true when one does.) A payload that prices nothing — no ``pricing`` key, an empty
    one, or entries that are not amounts — is the unknown.

    A **local** model with no price is FREE: calling it costs nothing, which is the
    question this column answers. The work was paid for once, in hardware, not per
    token. Everything else that is unpriced stores ``None`` rather than a verdict.
    """
    pricing: Any = None
    if isinstance(raw_data, dict):
        payload = raw_data.get("_raw")
        if not isinstance(payload, dict):
            payload = raw_data
        pricing = payload.get("pricing")

    if not isinstance(pricing, dict) or not pricing:
        return True if location == "local" else None

    amounts = [
        amount
        for amount in (_as_amount(value) for value in pricing.values())
        if amount is not None
    ]
    if not amounts:
        # A `pricing` dict whose entries are not amounts prices nothing, so it says
        # nothing: the catalog carries `overrides` as a nested object beside the numbers.
        return None
    return all(amount == 0 for amount in amounts)


def _as_amount(value: Any) -> Optional[float]:
    """One price component as a number, or ``None`` when the entry is not an amount.

    The catalog states prices as STRINGS (``"0"``, ``"0.00000003"``) next to entries that
    are not prices at all, so both have to survive the read.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def resolve_verification(
    curated: Optional[int],
    discovered: Optional[int],
    *,
    fresh: bool,
) -> Tuple[Optional[int], bool, bool, str]:
    """``(window_after, verified, mismatch, note)`` — the verification's decision.

    The provider's number is the fact; the curated row is a statement about it, so
    the row adopts what the provider says and a disagreement is REPORTED rather than
    quietly overwritten. ``verified`` is True only when the row agrees with a claim
    we can stand behind (``fresh``): a stale claim still fills a row that had no
    number, and still reports a disagreement, but it verifies nothing.
    """
    if discovered is None:
        return (
            curated,
            False,
            False,
            "the provider's own list carries no window for this model — "
            "nothing to verify against",
        )
    if curated is None:
        return (
            discovered,
            fresh,
            False,
            "no window was recorded; adopted the provider's number",
        )
    if int(curated) == int(discovered):
        return curated, fresh, False, "the row already carries the provider's number"
    return (
        discovered,
        fresh,
        True,
        f"the row said {int(curated)} and the provider says {int(discovered)} — the row "
        f"now carries the provider's number; a deliberately smaller curated window is "
        f"not 'verified'",
    )


def _no_endpoint(row_name: str, provider_type: str) -> str:
    """Why a refresh could not ask the provider: the row declares no endpoint.

    THE ROW IS THE DECISION (2026-10-10, the service-literals arc) — this path used to dial a
    literal (`localhost:11434`, `127.0.0.1:8080/v1`) when the row declared nothing, which is how a
    verification presents a dated claim as a fresh one.
    """
    return (
        f"the '{row_name}' row declares no endpoint, and the '{provider_type}' type has none — "
        "set base_url on the row"
    )


class CuratedModelService:
    """CRUD operations for curated models."""

    # =========================================================================
    # Read
    # =========================================================================

    async def list_models(
        self,
        db: AsyncSession,
        provider_name: Optional[str] = None,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        """List curated models, optionally filtered by provider name."""
        stmt = (
            select(CuratedModel, Provider.name)
            .join(Provider, CuratedModel.provider_id == Provider.id)
            .order_by(Provider.name, CuratedModel.model_id)
        )
        if provider_name:
            stmt = stmt.where(Provider.name == provider_name)
        if not include_inactive:
            stmt = stmt.where(CuratedModel.is_active.is_(True))

        rows = (await db.execute(stmt)).all()
        return [
            self._to_dict(cm, provider_name)
            for cm, provider_name in rows
        ]

    async def get_model(
        self, db: AsyncSession, curated_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get a single curated model by id."""
        row = (
            await db.execute(
                select(CuratedModel, Provider.name)
                .join(Provider, CuratedModel.provider_id == Provider.id)
                .where(CuratedModel.id == curated_id)
            )
        ).first()
        if row is None:
            return None
        cm, provider_name = row
        return self._to_dict(cm, provider_name)

    async def provider_for_model(
        self, db: AsyncSession, model_id: str
    ) -> Optional[str]:
        """The NAME of the active curated row that serves `model_id`, or None.

        THE ONE ANSWER for "which provider serves this model?", in the same
        vocabulary `match_spec` returns (the provider row's own name) — so a
        caller handed an explicit model names the provider exactly the way the
        matcher would have. A model no active row serves has NO provider: the
        caller refuses rather than guessing one from the spec's location.

        When several rows share a `model_id` the choice is deterministic and
        follows the house preference order — lowest `priority` first (the order
        the default-provider read uses), then name.
        """
        return (
            await db.execute(
                select(Provider.name)
                .join(CuratedModel, CuratedModel.provider_id == Provider.id)
                .where(
                    CuratedModel.model_id == model_id,
                    CuratedModel.is_active.is_(True),
                )
                .order_by(Provider.priority, Provider.name)
                .limit(1)
            )
        ).scalar_one_or_none()

    # =========================================================================
    # Write
    # =========================================================================

    async def create_model(
        self,
        db: AsyncSession,
        *,
        provider_name: str,
        model_id: str,
        model_name: str,
        category: Optional[str] = None,
        description: Optional[str] = None,
        context_length: Optional[int] = None,
        thinking: Optional[str] = None,
        location: str = "cloud",
    ) -> Dict[str, Any]:
        """Create a curated model entry for a provider.

        THE ROW IS VERIFIED BY CONSTRUCTION (G3). The provider's own cached claim is read
        once and the row is BORN carrying it:

        - the **window** the provider publishes is adopted, with the agreement or the
          disagreement REPORTED (E.4's rule: the provider's number is the fact, and a
          disagreement is logged rather than quietly overwritten);
        - the **reasoning level** the provider declares is adopted (F.3). A stated level
          is the fallback for a driver whose payload says nothing: when the two disagree
          the provider's record wins and the disagreement is logged, because the READ
          path resolves the claim first anyway (`model_window.resolve_model_thinking`) —
          a row stating the opposite would be a second truth nothing acts on;
        - `verified` says whether the claim we compared against was FRESH. A model nobody
          has fetched comes back unverified, with the note saying so;
        - the **cost** comes off the same claim (Phase 4): the provider's own pricing
          answers, so the request does not carry `is_free` at all any more. A cloud model
          whose payload prices nothing stores the honest UNKNOWN, and a local model with
          no price stores free — see `cost_from_raw`.

        `location` is written explicitly — a default that reaches the row on purpose.
        """
        provider = (
            await db.execute(
                select(Provider).where(Provider.name == provider_name)
            )
        ).scalar_one_or_none()
        if provider is None:
            raise ValueError(f"Provider not found: {provider_name}")

        if category is not None and category not in CURATED_CATEGORIES:
            raise ValueError(
                f"Invalid category: {category}. Valid: {sorted(CURATED_CATEGORIES)}"
            )

        # Enforce uniqueness (provider_id, model_id)
        existing = (
            await db.execute(
                select(CuratedModel).where(
                    CuratedModel.provider_id == provider.id,
                    CuratedModel.model_id == model_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ValueError(
                f"Model {model_id!r} already curated for provider {provider_name}"
            )

        # G3 — A ROW IS VERIFIED BY CONSTRUCTION. The claim is read once and both facts
        # come off it, the freshness recipe verbatim from the verification path
        # (`cache_is_stale` on `expires_at`), so a create and a verify cannot disagree
        # about whether a claim is worth standing behind. Nothing is overwritten here
        # because nothing is written yet: the row is BORN carrying the provider's
        # numbers, and a disagreement with what the caller stated is REPORTED below.
        claim = await self._cached_claim(db, provider.id, model_id)
        discovered = claim.context_length if claim is not None else None
        stale = cache_is_stale(claim.expires_at) if claim is not None else False
        age = cache_age_hours(claim.cached_at) if claim is not None else None
        fresh = claim is not None and not stale

        window, verified, mismatch, note = resolve_verification(
            context_length, discovered, fresh=fresh,
        )

        claimed_level, claim_words = self._claim_level(claim)
        if claimed_level is not None:
            if thinking is not None and thinking != claimed_level:
                logger.warning(
                    "⚠️ THINKING ADOPTED at create model=%s provider=%s stated=%s "
                    "provider_claims=%s -> thinking=%s — the stated level and the "
                    "provider's own record disagree, and the row says what the provider "
                    "says (F.3).",
                    model_id, provider_name, thinking, claim_words, claimed_level,
                )
            thinking = claimed_level
        elif thinking is None:
            thinking = "none"

        # PHASE 4 — the cost fact comes off the same claim, and the request no longer
        # answers it. `None` (nobody has priced this model) is a legal verdict.
        cost = cost_from_raw(claim.raw_data if claim is not None else None, location)

        if mismatch:
            logger.warning(
                "⚠️ WINDOW MISMATCH at create model=%s provider=%s stated=%s "
                "provider_says=%s — the row carries the provider's number (E.4).",
                model_id, provider_name, context_length, discovered,
            )
        if verified:
            aged = f" (from a claim aged {age:.0f}h)" if (stale and age) else ""
            logger.info(
                "✅ WINDOW VERIFIED at create model=%s provider=%s window=%s%s",
                model_id, provider_name, window, aged,
            )
        elif not mismatch:
            logger.warning(
                "⚠️ WINDOW UNVERIFIED at create model=%s provider=%s window=%s — %s",
                model_id, provider_name, window, note,
            )

        cm = CuratedModel(
            provider_id=provider.id,
            model_id=model_id,
            model_name=model_name,
            # THE DESCRIPTOR IS OPTIONAL AND NOTHING INVENTS ONE: an omitted category stores
            # NULL ("nobody has described this row yet"), which is the honest state — the
            # default that used to fill in the retired editorial word is gone.
            category=category,
            description=description,
            context_length=window,
            # DERIVED, never stated (Phase 4): the provider's own pricing answers, and
            # `None` — nobody has priced this model — is a state the row may hold.
            is_free=cost,
            verified=verified,  # earned HERE against the provider's own cached claim
            is_active=True,
            thinking=thinking,
            location=location,
        )
        db.add(cm)
        await db.commit()
        await db.refresh(cm)
        return self._to_dict(cm, provider_name)

    async def _cached_claim(
        self, db: AsyncSession, provider_id: int, model_id: str,
    ) -> Optional[ProviderModelCache]:
        """The provider's OWN cached payload for one model — the claim, and its age.

        One read, because a row is verified against BOTH facts in it: the window the
        provider publishes and the reasoning it declares.
        """
        return (
            await db.execute(
                select(ProviderModelCache)
                .where(
                    ProviderModelCache.provider_id == provider_id,
                    ProviderModelCache.model_id == model_id,
                )
                .limit(1)
            )
        ).scalar_one_or_none()

    @staticmethod
    def _claim_level(
        claim: Optional[ProviderModelCache],
    ) -> Tuple[Optional[str], Optional[str]]:
        """``(our level, the provider's own words)`` for a cached claim (F.3).

        The level is ``None`` when nothing is cached, when the payload states no
        reasoning, or when it says thinking is off by default — the honest unknown, which
        leaves the caller's own label standing. The parsing is the SAME pair the
        verification path uses (`provider_reasoning_claim` for the facts,
        `provider_claim_from_raw` for the provider's wording), so a create and a verify
        cannot read one payload two ways.
        """
        if claim is None:
            return None, None
        by_default, mandatory, effort = provider_reasoning_claim(claim.raw_data)
        words, _max_completion = provider_claim_from_raw(claim.raw_data)
        return level_from_claim(by_default, mandatory, effort), words

    async def update_model(
        self,
        db: AsyncSession,
        curated_id: int,
        *,
        model_name: Optional[str] = None,
        category: Optional[str] = None,
        clear_category: bool = False,
        description: Optional[str] = None,
        context_length: Optional[int] = None,
        is_active: Optional[bool] = None,
        thinking: Optional[str] = None,
        location: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update a curated model entry. Returns None if not found.

        OVERWRITE-ONLY: a field left as ``None`` (not sent) is not touched. The two
        capability dimensions follow the same rule as everything else here — there is no
        value meaning "reset to the default"; send the default explicitly.
        """
        cm = (
            await db.execute(
                select(CuratedModel).where(CuratedModel.id == curated_id)
            )
        ).scalar_one_or_none()
        if cm is None:
            return None

        if category is not None and category not in CURATED_CATEGORIES:
            raise ValueError(
                f"Invalid category: {category}. Valid: {sorted(CURATED_CATEGORIES)}"
            )

        if model_name is not None:
            cm.model_name = model_name
        # THE ONE FIELD THAT CAN BE CLEARED: `category` is an OPTIONAL descriptor, so "not
        # described" has to be expressible — an omitted field still means "leave it alone"
        # (the overwrite-only rule above), while an explicit null in the request clears it.
        # `clear_category` is how the router tells that apart; every other field has no empty
        # state to reach, which is why this is a flag rather than a new convention.
        if clear_category:
            cm.category = None
        elif category is not None:
            cm.category = category
        if description is not None:
            cm.description = description
        if context_length is not None:
            cm.context_length = context_length
        # `is_free` is NOT settable here (Phase 4): it is derived at intake from the
        # provider's own pricing, and a derived fact with a hand-set override would be two
        # truths for one value — which is the defect this arc keeps closing.
        if is_active is not None:
            cm.is_active = is_active
        if thinking is not None:
            cm.thinking = thinking
        if location is not None:
            cm.location = location

        await db.commit()
        await db.refresh(cm)

        provider = (
            await db.execute(
                select(Provider).where(Provider.id == cm.provider_id)
            )
        ).scalar_one()
        return self._to_dict(cm, provider.name)

    async def delete_model(
        self, db: AsyncSession, curated_id: int
    ) -> bool:
        """Delete a curated model entry. Returns True if deleted."""
        cm = (
            await db.execute(
                select(CuratedModel).where(CuratedModel.id == curated_id)
            )
        ).scalar_one_or_none()
        if cm is None:
            return False
        await db.delete(cm)
        await db.commit()
        return True

    # =========================================================================
    # Verified sync (called by cache_service after cache writes)
    # =========================================================================

    async def mark_verified_for_models(
        self, db: AsyncSession, provider_id: int, model_ids: List[str]
    ) -> int:
        """Mark curated entries verified when their model_id was just fetched.

        Called after provider_model_cache_service.cache_models — verified is
        earned by discovery, not chosen by hand.
        """
        if not model_ids:
            return 0
        result = await db.execute(
            sa_update(CuratedModel)
            .where(
                CuratedModel.provider_id == provider_id,
                CuratedModel.model_id.in_(model_ids),
            )
            .values(verified=True)
        )
        await db.commit()
        # CursorResult exposes rowcount for UPDATE statements
        return getattr(result, "rowcount", None) or 0

    # =========================================================================
    # THE SUBSTITUTION MATCHER (2026-08-24, the agent-package Phase 3)
    # =========================================================================

    async def _provider_grants(
        self, db: AsyncSession, keys: set,
    ) -> Dict[Tuple[str, str], Optional[int]]:
        """The provider's own output GRANT per (provider, model) — one read, not N.

        `top_provider.max_completion_tokens` lives inside the cached payload, so it is
        read from there rather than stored a second time: the cache is the fact's home,
        and a column would go stale on the next discovery fetch. Keyed by provider NAME
        because a model id can exist under more than one provider.
        """
        if not keys:
            return {}
        model_ids = {model_id for _provider, model_id in keys}
        rows = (
            await db.execute(
                select(Provider.name, ProviderModelCache.model_id, ProviderModelCache.raw_data)
                .join(Provider, ProviderModelCache.provider_id == Provider.id)
                .where(ProviderModelCache.model_id.in_(list(model_ids)))
            )
        ).all()
        grants: Dict[Tuple[str, str], Optional[int]] = {}
        for provider_name, model_id, raw_data in rows:
            _signal, cap = provider_claim_from_raw(raw_data)
            grants[(provider_name, model_id)] = cap
        return grants

    async def match_spec(
        self,
        db: AsyncSession,
        llm_spec: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """THE SUBSTITUTION HELPER: given an llm_spec (the agent's
        OWNED contract — kind/thinking/location/min_context), return
        the candidate models that satisfy it.

        THE RULE: substitution is a PROPOSAL, never automatic. This
        returns candidates (with cost surfaced via is_free); the
        user (or Exa, asking) confirms. An honest EMPTY when nothing
        matches — no fake picks.

        Matching:
        - thinking: the spec's level is a FLOOR — a 'low' spec
          accepts low/medium/high; 'none' accepts everything
        - location: exact ('local'/'cloud'); 'any' accepts all
        - min_context: the model's context_length >= the floor. A row whose window is
          NOT recorded is NOT offered — an unknown window cannot be shown to hold the
          floor (see the guard below).
        """
        thinking = (llm_spec or {}).get("thinking", "none") or "none"
        location = (llm_spec or {}).get("location", "any") or "any"
        min_context = (llm_spec or {}).get("min_context")

        stmt = (
            select(CuratedModel, Provider.name)
            .join(Provider, CuratedModel.provider_id == Provider.id)
            .where(CuratedModel.is_active.is_(True))
        )
        rows = (await db.execute(stmt)).all()

        # the thinking levels ranked (the floor semantics)
        # `mandatory` ranks above `high`: it is the strongest statement about a
        # driver's thinking (it cannot be told not to), so a model carrying it
        # satisfies every spec's floor (F.3).
        rank = {"none": 0, "low": 1, "medium": 2, "high": 3, "mandatory": 4}
        spec_rank = rank.get(thinking, 0)

        candidates = []
        unrecorded: List[str] = []
        for cm, provider_name in rows:
            # thinking: the model's level >= the spec's floor
            if rank.get(cm.thinking, 0) < spec_rank:
                continue
            # location: exact unless the spec is 'any'
            if location != "any" and cm.location != location:
                continue
            # min_context: the floor — and a window NOBODY RECORDED cannot satisfy it.
            #
            # The floor is a `>=` claim and NULL is not a number, so such a row is not
            # offered: the honest state is "unknown", not "meets it". The guard used to
            # read `and cm.context_length`, which let exactly those rows through and left
            # the window-fit warning to cover them — a REVERSAL, with the reasoning in the
            # commit and the rule stated in `wiki/dev-notes/deep-dives/token-limit-policy.md`.
            # The Model Browser's own context filter has always read unknown as 0 and
            # excluded it; the matcher now agrees with it.
            if min_context is not None:
                if cm.context_length is None:
                    unrecorded.append(cm.model_id)
                    continue
                if cm.context_length < min_context:
                    continue
            candidates.append(self._to_dict(cm, provider_name))

        # The exclusion is SAID, never silent: an operator who cannot see a model they
        # expected has to be able to tell "it does not fit" from "nobody measured it".
        if unrecorded:
            logger.warning(
                "⚠️ NOT OFFERED — %d row(s) whose context window is not recorded: %s — "
                "a stated floor of %d cannot be shown to hold without one (verify the "
                "row, or state its window)",
                len(unrecorded), ", ".join(sorted(unrecorded)), min_context,
            )

        # THE ADVISORY ORDERING: free first, then the model id.
        # Never filters — the user sees the tradeoffs.
        #
        # The editorial `featured` flag that used to sit between these two keys went with
        # the column (this arc's Phase 3): the app does not privilege models. `prefer_free`
        # went with it — the parameter documented itself as this ordering's control and was
        # passed by NOTHING (one hit tree-wide: its own signature), so it was a knob that
        # did nothing rather than a call site to fix.
        # THE RANKING, with the third state PLACED (Phase 4): free first, then a model the
        # provider actually prices, then one nobody has priced. An unknown is not a claim
        # about cost, so it does not outrank a stated one — and `not m["is_free"]`, the
        # shape this sort had through Phase 3, reads `None` as truthy and would have ranked
        # an unpriced row as PAID.
        candidates.sort(
            key=lambda m: (
                0 if m["is_free"] else 1 if m["is_free"] is False else 2,
                m["model_id"],
            )
        )

        # THE WINDOW FIT (the token-limit arc, E.3 — D9). REPORTED, never a filter:
        # a window too small for the agent's need is allowed (the runtime clamps the
        # budget to fit, `reason=window_clamp`), and the mismatch is said here, where
        # the choice is made, instead of being discovered as a cut-off answer later.
        # `min_context` above is the INPUT floor and does filter — that is a different
        # check (the driver cannot hold the prompt at all). What this adds is the
        # OUTPUT side, and the honest state of a window nobody recorded.
        needed = needed_window_tokens(
            prompt_floor=min_context,
            output_budget=(llm_spec or {}).get("max_output"),
        )
        too_small = []
        unknown = 0
        for candidate in candidates:
            window_value = candidate.get("context_length")
            if window_value is None:
                unknown += 1
                continue
            sentence = window_fit_warning(
                window_value, needed, who=f"Candidate {candidate['model_id']}",
            )
            if sentence:
                too_small.append(sentence)
        for sentence in too_small:
            logger.warning("⚠️ WINDOW FIT — %s", sentence)
        if unknown:
            logger.warning(
                "⚠️ WINDOW UNKNOWN for %d of %d candidates — no window is recorded "
                "for them, so nothing is clamped and nothing can promise they fit "
                "(E.4 is what fills those rows; a turn on one says the same)",
                unknown, len(candidates),
            )

        # THE PAIRING ADVICE (G4 + G5's residue) — the same moment and the same rule as
        # the window fit above: REPORTED, never a filter, because the numbers it names
        # are already decided elsewhere (the provider applies its own grant; the resolver
        # applies the floor). What it adds is knowing the outcome when the driver meets
        # the contract, rather than discovering it as a cut-off answer or as a surprise
        # on the profile page.
        declared_output = (llm_spec or {}).get("max_output")
        grants = await self._provider_grants(
            db, {(c["provider"], c["model_id"]) for c in candidates},
        )
        advice: List[str] = []
        for candidate in candidates:
            advice.extend(
                pairing_advice(
                    declared_output,
                    candidate.get("thinking"),
                    grants.get((candidate["provider"], candidate["model_id"])),
                    who=f"Candidate {candidate['model_id']}",
                )
            )
        for sentence in advice:
            logger.warning("⚠️ PAIRING ADVICE — %s", sentence)

        return candidates

    # =========================================================================
    # Helpers
    # =========================================================================

    def _to_dict(self, cm: CuratedModel, provider_name: str) -> Dict[str, Any]:
        """Convert ORM model to API dict."""
        return {
            "id": cm.id,
            "model_id": cm.model_id,
            "model_name": cm.model_name,
            "provider": provider_name,
            "category": cm.category,
            "description": cm.description,
            "context_length": cm.context_length,
            "is_free": cm.is_free,
            "verified": cm.verified,
            "is_active": cm.is_active,
            "thinking": cm.thinking,
            "location": cm.location,
            "created_at": cm.created_at.isoformat() if cm.created_at else None,
            "updated_at": cm.updated_at.isoformat() if cm.updated_at else None,
        }


    # =========================================================================
    # THE WINDOW VERIFICATION (the token-limit arc, E.4)
    # =========================================================================

    async def verify_window(
        self,
        db: AsyncSession,
        curated_id: int,
        *,
        refresh: bool = False,
    ) -> Optional[WindowVerification]:
        """Verify one curated row's window against the PROVIDER's own claim (E.4).

        The provider's list is the fact (`provider_model_cache`, filled by the app's
        own discovery fetch; ``refresh=True`` asks the provider again first). The row
        adopts the provider's number, `verified` records whether the claim we
        compared against was FRESH, and a disagreement is logged as a mismatch —
        never a silent overwrite.

        Returns ``None`` when no such curated row exists.
        """
        row = (
            await db.execute(
                select(CuratedModel, Provider)
                .join(Provider, CuratedModel.provider_id == Provider.id)
                .where(CuratedModel.id == curated_id)
                .limit(1)
            )
        ).first()
        if row is None:
            return None
        curated_row, provider = row

        refreshed = False
        refresh_note = ""
        if refresh:
            failure = await self._refresh_provider_models(db, provider)
            if failure:
                refresh_note = f" (the refresh could not run: {failure})"
                logger.warning(
                    "⚠️ WINDOW VERIFY could not refresh provider=%s model=%s — %s",
                    provider.name, curated_row.model_id, failure,
                )
            else:
                refreshed = True

        claim = (
            await db.execute(
                select(ProviderModelCache)
                .where(
                    ProviderModelCache.provider_id == provider.id,
                    ProviderModelCache.model_id == curated_row.model_id,
                )
                .limit(1)
            )
        ).scalar_one_or_none()

        discovered = claim.context_length if claim is not None else None
        stale = cache_is_stale(claim.expires_at) if claim is not None else False
        age = cache_age_hours(claim.cached_at) if claim is not None else None
        fresh = claim is not None and (refreshed or not stale)
        thinking_provider, max_completion = provider_claim_from_raw(
            claim.raw_data if claim is not None else None
        )

        window, verified, mismatch, note = resolve_verification(
            curated_row.context_length, discovered, fresh=fresh,
        )
        note = note + refresh_note

        previous_window = curated_row.context_length
        previous_verified = bool(curated_row.verified)
        changed = (previous_window != window) or (previous_verified != verified)
        curated_row.context_length = window
        curated_row.verified = verified

        if mismatch:
            logger.warning(
                "⚠️ WINDOW MISMATCH model=%s provider=%s curated=%s discovered=%s — "
                "the row now carries the provider's number%s",
                curated_row.model_id, provider.name, previous_window, discovered,
                "" if refreshed else " (the claim was not refreshed; it is dated)",
            )
        if verified:
            aged = f" (from a claim aged {age:.0f}h)" if (stale and age) else ""
            logger.info(
                "✅ WINDOW VERIFIED model=%s provider=%s window=%s%s",
                curated_row.model_id, provider.name, window, aged,
            )
        elif not mismatch:
            logger.warning(
                "⚠️ WINDOW UNVERIFIED model=%s provider=%s window=%s — %s",
                curated_row.model_id, provider.name, window, note,
            )

        thinking_curated = str(curated_row.thinking or "none")
        # F.3 — THE LABEL GETS A WRITE PATH. This is the one place that holds the
        # provider's own claim, so it is where our label stops being a hand-set value
        # no API can correct: the claim is projected onto our levels and ADOPTED onto
        # the row, the same shape as the window (E.4). A claim we cannot map leaves the
        # label alone and reports the disagreement instead of guessing.
        claim_thinking, claim_mandatory, claim_effort = provider_reasoning_claim(
            claim.raw_data if claim is not None else None
        )
        adopted_level = level_from_claim(claim_thinking, claim_mandatory, claim_effort)
        thinking_adopted: Optional[str] = None
        if adopted_level is not None and adopted_level != thinking_curated:
            logger.warning(
                "⚠️ THINKING ADOPTED model=%s provider=%s curated=%s provider_claims=%s "
                "-> thinking=%s — the row carried a hand-set level and the provider's own "
                "record disagrees; the row now says what the provider says (F.3).",
                curated_row.model_id, provider.name, thinking_curated, thinking_provider,
                adopted_level,
            )
            curated_row.thinking = adopted_level
            thinking_adopted = adopted_level
            changed = True
        elif thinking_provider and thinking_curated == "none":
            logger.warning(
                "⚠️ THINKING MISMATCH model=%s provider=%s curated=%s provider_claims=%s — "
                "the row says this driver does not think and the claim is not a level we "
                "can adopt; the mismatch stands (F.3)",
                curated_row.model_id, provider.name, thinking_curated, thinking_provider,
            )

        if changed:
            await db.flush()
            await db.commit()

        return WindowVerification(
            curated_id=curated_row.id,
            provider=provider.name,
            model_id=curated_row.model_id,
            curated=previous_window,
            discovered=discovered,
            window=window,
            verified=verified,
            mismatch=mismatch,
            stale=stale,
            age_hours=age,
            refreshed=refreshed,
            thinking_curated=thinking_curated,
            thinking_provider=thinking_provider,
            thinking_adopted=thinking_adopted,
            max_completion=max_completion,
            note=note,
        )

    async def _refresh_provider_models(self, db: AsyncSession, provider: Provider) -> Optional[str]:
        """Ask the provider for its model list again — the app's own discovery.

        Returns ``None`` when the refresh ran, or a sentence saying why it could not:
        a verification that could not ask the provider says so instead of presenting
        a dated claim as a fresh one. The dispatch mirrors the providers router's own
        (`api/v1/providers/management_router.py`); an unimplemented provider type is a
        stated reason, not an exception.
        """
        from app.domain.providers.discovery_service import provider_discovery_service
        from app.domain.providers.env_key_store import env_key_store
        from app.domain.providers.provider_endpoints import resolve_endpoint

        name = (provider.name or "").lower()
        ptype = str(getattr(provider, "provider_type", None) or name).lower()
        api_key = env_key_store.get_key(provider.name) or ""
        base_url = provider.base_url or ""
        try:
            if ptype == "openrouter":
                if not api_key:
                    return "no OpenRouter key is configured"
                await provider_discovery_service.discover_openrouter_models(
                    db, provider.id, api_key, force_refresh=True
                )
            elif ptype == "deepseek":
                if not api_key:
                    return "no Deepseek key is configured"
                await provider_discovery_service.discover_deepseek_models(
                    db, provider.id, api_key, force_refresh=True
                )
            elif ptype == "groq":
                if not api_key:
                    return "no Groq key is configured"
                await provider_discovery_service.discover_groq_models(
                    db, provider.id, api_key, force_refresh=True
                )
            elif ptype == "ollama":
                endpoint = resolve_endpoint(ptype, base_url, provider.name)
                if endpoint is None:
                    return _no_endpoint(provider.name, ptype)
                await provider_discovery_service.discover_ollama_models(
                    db, provider.id, endpoint, True
                )
            elif ptype == "ollama_cloud":
                if not api_key:
                    return "no Ollama Cloud key is configured"
                endpoint = resolve_endpoint(ptype, base_url, provider.name)
                if endpoint is None:
                    return _no_endpoint(provider.name, ptype)
                await provider_discovery_service.discover_ollama_cloud_models(
                    db, provider.id, api_key, endpoint, True
                )
            elif ptype == "openai":
                endpoint = resolve_endpoint(ptype, base_url, provider.name)
                if endpoint is None:
                    return _no_endpoint(provider.name, ptype)
                await provider_discovery_service.discover_openai_compat_models(
                    db, provider.id, endpoint, True
                )
            else:
                return f"no refresh path for provider type {ptype!r}"
        except Exception as e:
            return f"the provider fetch failed ({type(e).__name__}: {e})"
        return None


# Module-level singleton for dependency injection
curated_model_service = CuratedModelService()
