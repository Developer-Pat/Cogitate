"""
Agent Packages API router.

The package blueprints (Phase 1 of the agent-package roadmap):
CRUD for the canned, reusable agent specs. The provisioner
(Exa, Phase 4) reads these; the ADOPT action (Phase 2) copies
them into an agent's OWN fields.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.domain.agent_packages.schemas import (
    AgentPackageCreate,
    AgentPackageUpdate,
    AgentPackageResponse,
    AgentPackageListResponse,
)
from app.domain.agent_packages.service import AgentPackageService

logger = logging.getLogger(__name__)


def _announce(event: str, payload: dict) -> None:
    """THE CROSS-WINDOW SYNC (2026-08-25, the roadmap Phase 6):
    agent-package:<id>:<event> — the frontend's sync reloads the open
    pages in every tab."""
    try:
        from app.domain.messaging.services import publish
        publish(f"agent-package:{payload.get('package_id')}:{event}", payload)
    except Exception as e:  # pragma: no cover
        logger.error(f"  ❌ agent-package:{event} publish failed: {e}")

router = APIRouter(prefix="/agent-packages", tags=["agent-packages"])


class AgentPackageProvisionResponse(BaseModel):
    """The provision outcome (never silent)."""

    agent_id: int
    agent_name: str
    package_id: str
    package_name: str
    model: str
    location: str
    kit_id: Optional[str] = None
    skills: list[str] = []
    # THE WINDOW FIT (E.3, D9): the sentence to show when the chosen driver's window
    # is too small for what this agent needs, or is not recorded at all. `None` when
    # there is nothing to say — a driver that fits says nothing. The agent is created
    # either way: a small window is allowed, and the runtime clamps the budget to fit.
    window_note: Optional[str] = None


def get_service(db: AsyncSession = Depends(get_db_session)) -> AgentPackageService:
    return AgentPackageService(db)


@router.post("", response_model=AgentPackageResponse, status_code=status.HTTP_201_CREATED)
async def create_package(
    data: AgentPackageCreate,
    service: AgentPackageService = Depends(get_service),
) -> AgentPackageResponse:
    """Create a package blueprint."""
    existing = await service.get_package_by_name(data.name)
    if existing:
        raise HTTPException(status_code=409, detail=f"Package '{data.name}' already exists")
    pkg = await service.create_package(data)
    _announce("created", {"package_id": pkg.id, "name": getattr(pkg, "name", None), "event": "created"})
    return AgentPackageResponse.model_validate(pkg)


@router.get("", response_model=AgentPackageListResponse)
async def list_packages(
    include_inactive: bool = Query(False),
    service: AgentPackageService = Depends(get_service),
) -> AgentPackageListResponse:
    """List the packages."""
    packages = await service.list_packages(include_inactive=include_inactive)
    return AgentPackageListResponse(
        packages=[AgentPackageResponse.model_validate(p) for p in packages],
        total=len(packages),
    )


@router.get("/{package_id}", response_model=AgentPackageResponse)
async def get_package(
    package_id: str,
    service: AgentPackageService = Depends(get_service),
) -> AgentPackageResponse:
    """Get one package."""
    pkg = await service.get_package(package_id)
    if not pkg:
        raise HTTPException(status_code=404, detail=f"Package {package_id} not found")
    return AgentPackageResponse.model_validate(pkg)


@router.put("/{package_id}", response_model=AgentPackageResponse)
async def update_package(
    package_id: str,
    data: AgentPackageUpdate,
    service: AgentPackageService = Depends(get_service),
) -> AgentPackageResponse:
    """Update a package (partial)."""
    pkg = await service.update_package(package_id, data)
    if not pkg:
        raise HTTPException(status_code=404, detail=f"Package {package_id} not found")
    _announce("updated", {"package_id": package_id, "name": getattr(pkg, "name", None), "event": "updated"})
    return AgentPackageResponse.model_validate(pkg)


# =========================================================================
# THE PROVISION ACTION (the agent-package Phase 4 — the consumer path)
# =========================================================================


class ProvisionBody(BaseModel):
    """The provision request — the wizard answers the questions the
    package doesn't (the package's values are the defaults)."""

    name: str = Field(..., min_length=1, max_length=100)
    location: Optional[str] = Field(
        None, description="local|cloud — the wizard answer; defaults to the package's spec"
    )
    model: Optional[str] = Field(
        None, description="An explicit model override; else the matcher picks"
    )
    description: Optional[str] = None


@router.post("/{package_id}/provision", response_model=AgentPackageProvisionResponse)
async def provision_agent_from_package(
    package_id: str,
    body: ProvisionBody,
    db: AsyncSession = Depends(get_db_session),
):
    """THE EXA PROVISIONING PATH: create an agent FROM a package.

    The flow (the design's consumer):
    1. read the package (the blueprint)
    2. the wizard answers what the package doesn't (location) —
       the package's spec is the default
    3. create the agent: COPY the package's kit_id + skills +
       llm_spec into the agent's OWN fields + set package_id
       (provenance) + pick a model matching the llm_spec (the
       matcher; an explicit model wins)
    4. REPORT the outcome (never silent): the agent + the package
       + the chosen model

    THE RULE: when the matcher finds NO candidate, this is an
    HONEST 400 — no fake model pick.
    """
    from app.domain.agent_packages.service import AgentPackageService
    from app.domain.agents.services import AgentService
    from app.domain.agents.schemas import AgentCreate
    from app.domain.providers.curated_models_service import curated_model_service

    pkg_svc = AgentPackageService(db)
    pkg = await pkg_svc.get_package(package_id)
    if not pkg:
        raise HTTPException(status_code=404, detail=f"Package {package_id} not found")
    if not pkg.is_active:
        raise HTTPException(status_code=400, detail=f"Package '{pkg.name}' is inactive")

    # 2. the wizard answers: location defaults to the package's spec
    spec = dict(pkg.llm_spec or {})
    if body.location:
        spec["location"] = body.location

    # 3a. the MODEL and the PROVIDER that serves it — one answer, from the
    # registry. An explicit override wins; else the matcher picks.
    #
    # THE PROVIDER IS LOOKED UP, NEVER GUESSED (B2/B2a, the capability arc's
    # phase 4). This used to read `"openrouter" if location == "cloud" else
    # "ollama"` — a guess from the SPEC's location that ignored which row
    # actually serves the chosen model, and could write a provider that is not
    # running (both live packages declare `location: "local"` while the live
    # local server is `llama`, not `ollama`).
    chosen_model = body.model
    if not chosen_model:
        candidates = await curated_model_service.match_spec(db, spec)
        if not candidates:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"No model in the registry matches the package's llm_spec "
                    f"({spec}) — specify a model explicitly."
                ),
            )
        chosen_model = candidates[0]["model_id"]
        provider_name = candidates[0]["provider"]
    else:
        # The override path has no candidate list, so the row that SERVES the
        # named model supplies the provider. A model no active curated row owns
        # is REFUSED: an agent may not declare a provider that does not serve
        # its model.
        provider_name = await curated_model_service.provider_for_model(db, chosen_model)
        if not provider_name:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"No provider in the registry serves the model "
                    f"'{chosen_model}' — pick a model from the Model Browser, "
                    f"or add its row first."
                ),
            )

    # 3b. create the agent with the OWNED copies + the provenance
    agent_svc = AgentService(db)
    try:
        agent = await agent_svc.create(AgentCreate(
            name=body.name,
            description=body.description or pkg.description or "",
            provider=provider_name,
            model=chosen_model,
            kit_id=pkg.kit_id,
            skills=list(pkg.skills or []),
            llm_spec=spec,
            package_id=pkg.id,
        ))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # THE WINDOW FIT (the token-limit arc, E.3 — D9). The model is chosen; the
    # driver's window is READ and compared with what this agent needs (the spec's
    # prompt floor + the spec's declared output budget, F.1's `max_output` when the
    # package declares it). Too small or unknown is ALLOWED — the runtime clamps the
    # budget to fit and logs `window_clamp` — but it is reported here, in the
    # response and the log, rather than discovered as a cut-off answer later.
    from app.domain.providers.model_window import (
        needed_window_tokens as _needed,
        resolve_model_window as _window_for,
        window_fit_warning as _fit,
    )

    window_row = await _window_for(
        db,
        provider_name,
        chosen_model,
    )
    window_note = _fit(
        window_row.value,
        _needed(
            prompt_floor=spec.get("min_context"),
            output_budget=spec.get("max_output"),
        ),
        who=f"Agent '{agent.name}'",
    )
    if window_note:
        logger.warning(
            "⚠️ WINDOW FIT provision package=%s model=%s — %s",
            pkg.name, chosen_model, window_note,
        )

    # 4. REPORT the outcome (never silent)
    logger.info(
        f"Provisioned agent '{agent.name}' (id={agent.id}) from package "
        f"'{pkg.name}' — provider={provider_name}, model={chosen_model}, "
        f"location={spec.get('location')}"
    )
    return AgentPackageProvisionResponse(
        agent_id=agent.id,
        agent_name=agent.name,
        package_id=pkg.id,
        package_name=pkg.name,
        model=chosen_model,
        location=spec.get("location", "any"),
        kit_id=pkg.kit_id,
        skills=list(pkg.skills or []),
        window_note=window_note,
    )


@router.delete("/{package_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_package(
    package_id: str,
    service: AgentPackageService = Depends(get_service),
) -> None:
    """Delete a package. Provisioned agents keep their OWN copies."""
    deleted = await service.delete_package(package_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Package {package_id} not found")
    _announce("deleted", {"package_id": package_id, "event": "deleted"})
