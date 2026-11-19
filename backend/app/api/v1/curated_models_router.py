"""
Curated Models API endpoints.

CRUD for the curated model list (human-owned recommendations), separate
from provider model discovery (/providers/{id}/models/browse).
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.domain.providers.curated_models_service import (
    CURATED_CATEGORIES,
    MODEL_LOCATIONS,
    curated_model_service,
)
from app.services.cognitive_pipeline.reasoning_support import THINKING_LEVELS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/curated-models", tags=["curated-models"])


# =========================================================================
# Schemas
# =========================================================================


def _refuse_unknown(
    value: Optional[str], vocabulary: tuple[str, ...], label: str
) -> Optional[str]:
    """Refuse a value outside a closed vocabulary — the check both schemas share.

    ``None`` passes through: on the UPDATE schema that is "not sent", which leaves the
    row's field alone. Both vocabularies come from their ONE home (`THINKING_LEVELS`,
    `MODEL_LOCATIONS`), so a vocabulary change moves this check with it.
    """
    if value is None:
        return None
    if value not in vocabulary:
        raise ValueError(f"Unknown {label}: {value!r}. Valid: {', '.join(vocabulary)}")
    return value


def _refuse_retired_sort_order(data: Any) -> Any:
    """Refuse a request still carrying ``sort_order`` — LOUDLY, naming the replacement.

    The column is gone (the cloud-providers arc's Phase 2): display order is the
    READER's choice, so this API carries no ordering number at all.

    Silently ignoring the key would be the worse option — that writer keeps succeeding
    while its value goes nowhere, which is indistinguishable from a working save. So the
    request is refused with the reason instead.

    REMOVAL CONDITION: delete this guard once no producer can send the shape — the
    manager no longer sends it (``curatedModelsService.ts``) **and** no built frontend
    bundle still in use does. It is a transition guard, not an API policy.
    """
    if isinstance(data, dict) and "sort_order" in data:
        raise ValueError(
            "`sort_order` is retired: display order is the reader's choice, and this "
            "API no longer carries an ordering number. Remove the field from the "
            "request — clients sort what they show."
        )
    return data


def _refuse_retired_featured(data: Any) -> Any:
    """Refuse a request still carrying ``featured`` — LOUDLY, naming what became of it.

    The flag is gone (the cloud-providers arc's Phase 3): the app does not privilege models.
    Nothing on a curated row ranks or promotes one — the substitution matcher orders by cost
    and model id, and the table shows what is true rather than what is favoured. The word
    survives only as a CATEGORY value, which is a label a person chooses.

    Silently ignoring the key would be the worse option — that writer keeps succeeding while
    its value goes nowhere, which is indistinguishable from a working save. So the request is
    refused with the reason instead.

    REMOVAL CONDITION: delete this guard once no producer can send the shape — the manager no
    longer sends it (``curatedModelsService.ts``, whose create payload carried it on EVERY
    call) **and** no built frontend bundle still in use does. A TRANSITION guard, not policy.
    """
    if isinstance(data, dict) and "featured" in data:
        raise ValueError(
            "`featured` is retired: the app does not feature models, and this API no longer "
            "carries the flag. Remove the field from the request — a row states what a model "
            "costs and what it can do, and nothing ranks it."
        )
    return data


def _refuse_retired_is_free(data: Any) -> Any:
    """Refuse a request that still states `is_free` — the cost is DERIVED now (Phase 4).

    THE COST IS READ, NOT SET. A row's `is_free` comes off the provider's own cached
    pricing as the row is created (`curated_models_service.cost_from_raw`), so a request
    offering it would be a second truth for a value the API already answers — and its
    writer would keep succeeding while the value went nowhere.

    An explicit ``null`` is refused too: the value is not the client's to clear either.
    The provider's catalog answers, or the row says UNKNOWN because nobody priced it.

    REMOVAL CONDITION: delete this guard once no producer can send the key — the manager's
    create AND update payloads no longer carry it (they did on every save), and no built
    frontend bundle still in use does. A TRANSITION guard, not policy.
    """
    if isinstance(data, dict) and "is_free" in data:
        raise ValueError(
            "`is_free` is derived: a curated row's cost comes from the provider's own "
            "cached pricing when the row is created, so this API does not accept the "
            "field. Remove it from the request — the catalog decides, and a model the "
            "catalog does not price reads as unpriced rather than as a guess."
        )
    return data


class CuratedModelCreate(BaseModel):
    """Request body for creating a curated model entry."""

    provider: str = Field(..., description="Provider name (e.g. 'openrouter')")
    model_id: str = Field(..., min_length=1, description="Model ID as the provider knows it")
    model_name: str = Field(..., min_length=1, description="Display name")
    category: Optional[str] = Field(
        None, description=f"Category: {sorted(CURATED_CATEGORIES)}"
    )
    description: Optional[str] = None
    context_length: Optional[int] = None

    # THE CAPABILITY DIMENSIONS (the substitution matcher's axes; `thinking` is F.3's
    # label). Both are LOAD-BEARING, which is why the vocabulary is closed and checked
    # HERE, before a row exists: `thinking` ranks the matcher
    # (`curated_models_service.match_spec`) and feeds the output-budget floor
    # (`domain.providers.model_window.resolve_model_thinking`, SOURCE_CURATED), so an
    # unreadable level does
    # not merely sit on the row — it ranks as 0 and reads as "this driver does not think".
    # A refusal is a 422; nothing is stored.
    # `location` describes the row's runtime home, NOT the matcher's tolerance: "any" is a
    # SPEC-side value (SpecMatchBody) meaning "accept every row", and a ROW saying "any"
    # could never be matched by a strict spec, so it is not in this vocabulary.
    thinking: Optional[str] = Field(
        None,
        description=(
            f"Declared thinking level: {'|'.join(THINKING_LEVELS)}. The row is verified "
            "against the provider's own cached claim AS IT IS CREATED: when the payload "
            "states a reasoning level the provider's record wins, and a disagreement with "
            "this field is logged rather than dropped. State a value for a driver whose "
            "payload says nothing; omit it and the row takes the honest default."
        ),
    )
    location: str = Field(
        "cloud", description=f"Runtime home: {'|'.join(MODEL_LOCATIONS)}"
    )

    @field_validator("thinking")
    @classmethod
    def _thinking_is_known(cls, value: Optional[str]) -> Optional[str]:
        # `None` is NOT coerced: it means "derive from the provider's claim" and has to
        # reach the service as `None`. A default filled in here would decide the label
        # twice and make the derivation unreachable.
        return _refuse_unknown(value, THINKING_LEVELS, "thinking level")

    @field_validator("location")
    @classmethod
    def _location_is_known(cls, value: str) -> str:
        return _refuse_unknown(value, MODEL_LOCATIONS, "location") or "cloud"

    @model_validator(mode="before")
    @classmethod
    def _no_retired_sort_order(cls, data: Any) -> Any:
        return _refuse_retired_sort_order(data)

    @model_validator(mode="before")
    @classmethod
    def _no_retired_featured(cls, data: Any) -> Any:
        return _refuse_retired_featured(data)

    @model_validator(mode="before")
    @classmethod
    def _no_stated_cost(cls, data: Any) -> Any:
        return _refuse_retired_is_free(data)


class CuratedModelUpdate(BaseModel):
    """Request body for updating a curated model entry (all optional)."""

    model_name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    context_length: Optional[int] = None
    is_active: Optional[bool] = None
    thinking: Optional[str] = None
    location: Optional[str] = None

    @field_validator("thinking")
    @classmethod
    def _thinking_is_known(cls, value: Optional[str]) -> Optional[str]:
        return _refuse_unknown(value, THINKING_LEVELS, "thinking level")

    @field_validator("location")
    @classmethod
    def _location_is_known(cls, value: Optional[str]) -> Optional[str]:
        return _refuse_unknown(value, MODEL_LOCATIONS, "location")

    @model_validator(mode="before")
    @classmethod
    def _no_retired_sort_order(cls, data: Any) -> Any:
        return _refuse_retired_sort_order(data)

    @model_validator(mode="before")
    @classmethod
    def _no_retired_featured(cls, data: Any) -> Any:
        return _refuse_retired_featured(data)

    @model_validator(mode="before")
    @classmethod
    def _no_stated_cost(cls, data: Any) -> Any:
        return _refuse_retired_is_free(data)


# =========================================================================
# Endpoints
# =========================================================================


@router.get("", response_model=list)
async def list_curated_models(
    provider: Optional[str] = Query(None, description="Filter by provider name"),
    include_inactive: bool = Query(False, description="Include inactive entries"),
    db: AsyncSession = Depends(get_db_session),
):
    """List curated models, optionally filtered by provider.

    THE ORDER IS THE SERVER'S GUARANTEE to a client that does not sort: `(provider,
    model_id)`. The page sorts what it shows itself, so this is the wire's order only.
    """
    return await curated_model_service.list_models(
        db, provider_name=provider, include_inactive=include_inactive
    )


@router.get("/{curated_id}", response_model=dict)
async def get_curated_model(
    curated_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """Get a single curated model by id."""
    model = await curated_model_service.get_model(db, curated_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Curated model not found")
    return model


@router.post("", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_curated_model(
    body: CuratedModelCreate,
    db: AsyncSession = Depends(get_db_session),
):
    """Add a model to the curated list.

    The row's `thinking` and `location` are set HERE rather than left to the column
    defaults: the deliberate setter is what the verification path was standing in for
    (F.3 adopts a provider's claim onto the row, but only when somebody runs it).
    """
    try:
        return await curated_model_service.create_model(
            db,
            provider_name=body.provider,
            model_id=body.model_id,
            model_name=body.model_name,
            category=body.category,
            description=body.description,
            context_length=body.context_length,
            thinking=body.thinking,
            location=body.location,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{curated_id}", response_model=dict)
async def update_curated_model(
    curated_id: int,
    body: CuratedModelUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """Update a curated model entry (category, active, labels, etc.).

    THE ABSENCE SEMANTICS, stated because they are otherwise invisible: every field is
    OVERWRITE-ONLY. A field you do not send is left alone, and no value means "clear this
    back to its default" — `thinking` and `location` are non-nullable on the row, so
    "clear" could only mean "reset to the default the create path writes", which this
    endpoint does not offer.

    THE ONE EXCEPTION is `category`, the row's optional one-word descriptor: a client that
    sends it as an explicit **null** CLEARS it ("not described"), because an optional field
    whose empty state cannot be reached is a field you can only ever fill in.
    """
    try:
        model = await curated_model_service.update_model(
            db,
            curated_id,
            model_name=body.model_name,
            category=body.category,
            # A null the client SENT is "clear the descriptor"; an absent field stays
            # "leave it alone", which is this endpoint's overwrite-only rule.
            clear_category=("category" in body.model_fields_set and body.category is None),
            description=body.description,
            context_length=body.context_length,
            is_active=body.is_active,
            thinking=body.thinking,
            location=body.location,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if model is None:
        raise HTTPException(status_code=404, detail="Curated model not found")
    return model


@router.delete("/{curated_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_curated_model(
    curated_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """Remove a model from the curated list."""
    deleted = await curated_model_service.delete_model(db, curated_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Curated model not found")


# =========================================================================
# THE SUBSTITUTION MATCHER (the agent-package Phase 3)
# =========================================================================


class VerifyWindowBody(BaseModel):
    """The verification request: ask the provider again, or read our own record."""

    refresh: bool = Field(
        False,
        description=(
            "Ask the provider for its model list again before comparing. Without it "
            "the check reads the claim our discovery fetch already recorded — which "
            "may be dated, and the response says so."
        ),
    )


@router.post("/{curated_id}/verify-window")
async def verify_window(
    curated_id: int,
    body: Optional[VerifyWindowBody] = None,
    db: AsyncSession = Depends(get_db_session),
):
    """VERIFY ONE ROW'S WINDOW against the provider's own claim (the arc, E.4).

    The provider's list is the fact (`provider_model_cache`, written by the app's
    discovery fetch); ``refresh`` asks the provider again first. The row adopts the
    number, `verified` says whether the claim it agreed with was fresh, and a
    disagreement comes back as `mismatch` — reported, never a silent overwrite. A
    refresh that cannot run is a NOTE in the response, not a failure: a verification
    that could not ask the provider must not present a dated claim as a fresh one.

    This path also ADOPTS the provider's reasoning claim onto the row's `thinking`
    (F.3) — the one writer that existed before the CRUD path could set the label.
    """
    result = await curated_model_service.verify_window(
        db, curated_id, refresh=bool(body.refresh) if body else False,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Curated model not found")
    return result.as_dict()


class SpecMatchBody(BaseModel):
    """The llm_spec to match (the agent's OWNED contract)."""

    kind: str = Field("chat", description="chat|workflow")
    thinking: str = Field(
        "none", description=f"Thinking floor: {'|'.join(THINKING_LEVELS)}"
    )
    location: str = Field(
        "any", description=f"Runtime home to accept: {'|'.join(MODEL_LOCATIONS)}|any"
    )
    min_context: Optional[int] = Field(None, description="The context floor")
    # THE DECLARED OUTPUT BUDGET (E.3). The package's `llm_spec.max_output` is F.1's
    # key; the matcher reads it TODAY when it is present, so the window-fit warning
    # (D9) speaks about the OUTPUT side the moment a spec declares one — and says
    # nothing when nobody declared anything (an unknown need is not a finding).
    max_output: Optional[int] = Field(
        None, description="The declared output budget, for the window-fit warning"
    )


@router.post("/match")
async def match_spec(
    body: SpecMatchBody,
    db: AsyncSession = Depends(get_db_session),
):
    """THE SUBSTITUTION HELPER: candidate models for an llm_spec.

    THE RULE: a PROPOSAL, never automatic. Returns the candidates
    (free-first); the user (or Exa, asking) confirms. An honest
    EMPTY when nothing matches.
    """
    candidates = await curated_model_service.match_spec(
        db, body.model_dump()
    )
    return {"candidates": candidates, "total": len(candidates)}
