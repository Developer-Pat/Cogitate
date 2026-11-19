"""
Agent API endpoints.

Provides REST API for agent CRUD operations.
"""

import logging
import uuid
from pathlib import Path
from typing import Annotated, Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.agents.templates_router import router as templates_router
from app.core.config import get_settings
from app.core.dependencies import get_db
from app.domain.assets import dedup_upload, strip_metadata
from app.domain.agent_kits.schemas import AgentKitAttach, AgentKitsResponse
from app.domain.agents.schemas import (
    AgentCard,
    AgentCreate,
    AgentListResponse,
    AgentResponse,
    AgentSelectRequest,
    AgentSelectResponse,
    AgentStatsResponse,
    AgentUpdate,
    DuplicatesResponse,
    SystemPromptTemplate,
    TemplateApplyRequest,
    TemplateApplyResponse,
)
from app.domain.agents.services import AgentService
from app.domain.providers.refusal import chat_readiness

logger = logging.getLogger(__name__)


def _availability_out(readiness: Any) -> Any:
    """The domain verdict as the wire shape — `None` in, `None` out.

    Kept explicit rather than duck-typed on the field: the domain value (`refusal.RunReadiness`) and
    the schema are deliberately different types, so a field the schema does not know about cannot
    be smuggled onto the response by a `model_validate` over the whole object.
    """
    from app.domain.agents.schemas import AgentServiceAvailability

    if readiness is None:
        return None
    return AgentServiceAvailability(
        state=readiness.state,
        available=readiness.available,
        reason=readiness.reason,
        checked_at=readiness.checked_at,
        provider=readiness.provider,
        model=readiness.model,
    )


def _announce(event: str, payload: dict) -> None:
    """THE CROSS-WINDOW AGENT SYNC (2026-08-25, the roadmap Phase 2):
    the adopt announced; the delete/rename/update didn't. The
    mutations now publish agent:<id>:<event> — the frontend's
    useAgentSync applies them to every open tab's store."""
    try:
        from app.domain.messaging.services import publish
        publish(f"agent:{payload.get('agent_id')}:{event}", payload)
    except Exception as e:  # pragma: no cover
        logger.error(f"  ❌ agent:{event} publish failed: {e}")

router = APIRouter(prefix="/agents", tags=["agents"])

# Include version management routes
# Include template management routes
router.include_router(templates_router)


def get_agent_service(db: Annotated[AsyncSession, Depends(get_db)]) -> AgentService:
    """Dependency to get agent service."""
    return AgentService(db)


def _validate_image_file(file: UploadFile) -> None:
    """
    Validate uploaded image file.

    Args:
        file: Uploaded file

    Raises:
        HTTPException: If file is invalid
    """
    settings = get_settings()

    # Check file type
    if file.content_type not in settings.allowed_image_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {settings.allowed_image_types}",
        )

    # Check file size (read first chunk to verify)
    # Note: Full size check happens during save


def _save_image(file: UploadFile, agent_id: int, strip: bool = False) -> str:
    """
    Save uploaded image to disk.

    Args:
        file: Uploaded file
        agent_id: Agent ID for filename
        strip: strip PNG metadata (EXIF/ComfyUI workflow) before
            storing — opt-in, never silent (2026-08-11)

    Returns:
        Path to saved image
    """
    settings = get_settings()

    # Ensure directory exists
    upload_dir = Path(settings.profile_images_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Read + size check
    content = file.file.read()
    if strip:
        content, _ = strip_metadata(content)
    if len(content) > settings.max_upload_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Max size: {settings.max_upload_size} bytes",
        )

    # Dedup by pixels: re-uploading the same image reuses the
    # existing file instead of creating another uuid copy.
    ext = Path(file.filename).suffix if file.filename else ".jpg"
    filename, _ = dedup_upload(
        upload_dir,
        content,
        name_for_new=f"agent_{agent_id}_{uuid.uuid4().hex}{ext}",
    )
    return str(upload_dir / filename)


@router.get("", response_model=AgentListResponse)
async def list_agents(
    page: Annotated[Optional[int], Query(ge=1, description="Page number (opt-in pagination)")] = None,
    page_size: Annotated[Optional[int], Query(ge=1, le=500, description="Items per page (opt-in pagination)")] = None,
    q: Annotated[Optional[str], Query(description="Search term to filter agents by name (case-insensitive)")] = None,
    service: Annotated[AgentService, Depends(get_agent_service)] = None,  # type: ignore[assignment]
) -> AgentListResponse:
    """
    List agents. FULL LIST BY DEFAULT — pagination is UI opt-in.

    The agents registry is a BOUNDED collection (the 2026-08-17
    pagination-trap fix: Exa's probe got 10 of 14 agents because
    the default page_size=10 truncated the list with `total` sitting
    right there). Clients now get the complete registry by default;
    the UI passes page/page_size when it wants to render pages.

    Args:
        page: Page number (only when paginating)
        page_size: Items per page (only when paginating)
        q: Optional search term to filter agents by name
        service: Agent service (injected)

    Returns:
        The full agent list (or the requested page when paging)
    """
    if page is not None and page_size is not None:
        skip = (page - 1) * page_size
        agents, total = await service.list_all(skip=skip, limit=page_size, search=q)
    else:
        agents, total = await service.list_all_agents(search=q)

    # Attach provider health (from usage_logs) so UI badges match the
    # check_agent_health.py scan (F3).
    health_map = await service.health_for_agents([a.id for a in agents])
    profile_map = await service.cognitive_profile_readouts(
        [a.cognitive_profile_id for a in agents]
    )
    # ...and the declared-vs-sent read (G.1): the same resolver the chat path
    # runs, per distinct driver, so the profile page shows the number that goes
    # out beside the one the row declares — and the reason they differ.
    budget_map = await service.output_budget_for_agents(agents)

    # ...and the CURRENT question (phase 6, G5-F2's agent half): can each agent run RIGHT NOW?
    # One availability pass over every service these agents' chains name, then the SAME predicate
    # the pre-turn refusal applies — so this badge and a refused turn cannot disagree.
    readiness_map = await chat_readiness(service.db, agents)

    responses = []
    for a in agents:
        resp = AgentResponse.model_validate(a)
        resp.health = health_map.get(a.id)
        resp.output_budget = budget_map.get(a.id)
        resp.service_availability = _availability_out(readiness_map.get(a.id))
        prof = profile_map.get(a.cognitive_profile_id) if a.cognitive_profile_id is not None else None
        if prof:
            resp.cognitive_profile_name = prof["name"]
            resp.cognitive_profile_depth = prof["depth"]
        responses.append(resp)

    # when not paginating, the response reports the full-list shape
    # (page=1, page_size=total) so clients can distinguish a complete
    # registry from a page (the 2026-08-17 pagination-trap fix)
    return AgentListResponse(
        agents=responses,
        total=total,
        page=page if page is not None else 1,
        page_size=page_size if page_size is not None else total,
    )


@router.get("/stats", response_model=AgentStatsResponse)
async def get_agent_stats(
    service: Annotated[AgentService, Depends(get_agent_service)] = None,  # type: ignore[assignment]
) -> AgentStatsResponse:
    """
    Get aggregate agent statistics for system management.

    Returns counts, provider/model distribution, delegation status,
    and tool assignment stats.
    introspection capabilities (action="stats", domain="agent").

    Returns:
        AgentStatsResponse with aggregate statistics
    """
    return await service.get_agent_stats()


@router.get("/duplicates", response_model=DuplicatesResponse)
async def find_agent_duplicates(
    criteria: Annotated[str, Query(description="Duplicate criteria: 'direct_copy', 'config_twin', 'functional_twin', 'name_similar', or 'all'")] = "all",
    min_confidence: Annotated[float, Query(ge=0.0, le=1.0, description="Minimum confidence threshold (0.0-1.0)")] = 0.5,
    service: Annotated[AgentService, Depends(get_agent_service)] = None,  # type: ignore[assignment]
) -> DuplicatesResponse:
    """
    Find duplicate agents based on configuration comparison.

    Analyzes all agents and groups them by similarity using four levels of detection:
    - direct_copy: Agents with "(Copy)" suffix derived from the same original
    - config_twin: Agents sharing identical (provider, model, system_prompt) configuration
    - functional_twin: Agents sharing identical (provider, model, system_prompt, tool_set) configuration
    - name_similar: Agents with similar names and same provider

    Args:
        criteria: Detection level ('direct_copy', 'config_twin', 'functional_twin', 'name_similar', or 'all')
        min_confidence: Minimum confidence threshold (0.0-1.0)
        service: Agent service (injected)

    Returns:
        Groups of duplicate agents with match criteria and confidence scores
    """
    return await service.find_duplicates(criteria=criteria, min_confidence=min_confidence)


# Template endpoints (must be before /{agent_id} to avoid route conflicts)
@router.get("/system-templates", response_model=list[SystemPromptTemplate])
async def list_system_templates(
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> list[SystemPromptTemplate]:
    """
    List all available system prompt templates.

    Returns:
        List of available templates
    """
    return await service.list_system_prompt_templates()


@router.get("/system-templates/{template_id}", response_model=SystemPromptTemplate)
async def get_system_template(
    template_id: str,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> SystemPromptTemplate:
    """
    Get a specific system template by ID.

    Args:
        template_id: Template identifier

    Returns:
        Template details

    Raises:
        HTTPException: 404 if template not found
    """
    template = await service.get_template(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with id '{template_id}' not found",
        )
    return template


@router.post("/system-templates/apply", response_model=TemplateApplyResponse)
async def apply_system_template(
    request: TemplateApplyRequest,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> TemplateApplyResponse:
    """
    Apply a system template with variables to generate a system prompt.

    Args:
        request: Template apply request with template_id and variables
        service: Agent service

    Returns:
        Rendered prompt

    Raises:
        HTTPException: 404 if template not found
    """
    prompt = await service.apply_template(request.template_id, request.variables)

    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with id '{request.template_id}' not found",
        )

    return TemplateApplyResponse(
        template_id=request.template_id,
        prompt=prompt,
    )


@router.get("/deleted")
async def list_deleted_agents(
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> Dict[str, Any]:
    """Soft-deleted agents + their archive paths — the restore
    view's data (recovery is DB-discoverable, Phase D)."""
    from app.domain.agents.repository import get_agent_repository
    repo = get_agent_repository(service.db)
    return {"deleted": await repo.list_deleted()}


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: int,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentResponse:
    """
    Get agent by ID.

    Args:
        agent_id: Agent ID
        service: Agent service

    Returns:
        Agent details

    Raises:
        HTTPException: 404 if agent not found
    """
    agent = await service.get_by_id(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with id {agent_id} not found",
        )
    resp = AgentResponse.model_validate(agent)
    health_map = await service.health_for_agents([agent.id])
    resp.health = health_map.get(agent.id)
    # The same declared-vs-sent read the list carries (G.1).
    resp.output_budget = (await service.output_budget_for_agents([agent])).get(agent.id)
    # ...and the same current-availability read (G5-F2) — the detail view answers it too.
    resp.service_availability = _availability_out(
        (await chat_readiness(service.db, [agent])).get(agent.id)
    )
    # The column is nullable; a None key would look up an id that cannot exist.
    _pid = agent.cognitive_profile_id
    prof = (await service.cognitive_profile_readouts([_pid])).get(_pid) if _pid is not None else None
    if prof:
        resp.cognitive_profile_name = prof["name"]
        resp.cognitive_profile_depth = prof["depth"]
    return resp


@router.post("/{agent_id}/health/dismiss")
async def dismiss_agent_health(
    agent_id: int,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> dict:
    """
    Dismiss an agent's health warning (F6).

    Acknowledges all failures up to now — the badge clears until the
    NEXT failure occurs (which re-flags the agent).

    Args:
        agent_id: Agent ID
        service: Agent service

    Returns:
        Success message

    Raises:
        HTTPException: 404 if agent not found
    """
    updated = await service.dismiss_health(agent_id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with id {agent_id} not found",
        )
    return {"status": "dismissed", "agent_id": agent_id}


@router.delete("/{agent_id}/health/dismiss")
async def undismiss_agent_health(
    agent_id: int,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> dict:
    """
    Clear an agent's health dismissal — warnings re-evaluate fully.

    Args:
        agent_id: Agent ID
        service: Agent service

    Returns:
        Success message

    Raises:
        HTTPException: 404 if agent not found
    """
    updated = await service.undismiss_health(agent_id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with id {agent_id} not found",
        )
    return {"status": "undismissed", "agent_id": agent_id}


@router.get("/{agent_id}/card", response_model=AgentCard)
async def get_agent_card(
    agent_id: int,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentCard:
    """
    Get the A2A AgentCard for a specific agent.

    Returns a standardized agent discovery document following the A2A
    protocol's AgentCard specification, including agent name, description,
    skills (derived from system prompt and enabled tools), and capabilities.

    Args:
        agent_id: Agent ID
        service: Agent service (injected)

    Returns:
        AgentCard with agent capabilities and skills

    Raises:
        HTTPException: 404 if agent not found
    """
    card = await service.get_agent_card(agent_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with id {agent_id} not found",
        )
    return card


@router.post("/select", response_model=AgentSelectResponse)
async def select_agents(
    body: AgentSelectRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AgentSelectResponse:
    """The yellow pages (ARM Phase B): filter + rank the pool.

    Exa calls this to choose agents when composing orchestration
    workflows. GRAS — selection is information, access is the
    grant (the tooling upgrade's Phase C); this never grants.
    """
    from app.domain.agents.selection_service import select_agents
    agents = await select_agents(db, body.model_dump())
    return AgentSelectResponse(agents=agents, total=len(agents))


@router.get("/by-name/{name}", response_model=AgentResponse)
async def get_agent_by_name(
    name: str,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentResponse:
    """The white pages (ARM Phase A): resolve a unique name to an
    agent. STRICT — 404 on a missing name (the registry is the
    source of truth; workflows address recipients by identity).
    """
    try:
        agent = await service.resolve_agent(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    resp = AgentResponse.model_validate(agent)
    # The column is nullable; a None key would look up an id that cannot exist.
    _pid = agent.cognitive_profile_id
    prof = (await service.cognitive_profile_readouts([_pid])).get(_pid) if _pid is not None else None
    if prof:
        resp.cognitive_profile_name = prof["name"]
        resp.cognitive_profile_depth = prof["depth"]
    return resp


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_data: AgentCreate,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentResponse:
    """
    Create a new agent.

    Args:
        agent_data: Agent creation data
        service: Agent service

    Returns:
        Created agent
    """
    try:
        # through the repository seam — the row + the workspace
        # scaffold (agent-lifecycle Phase B). The repository owns
        # the transaction (row first, rollback on folder failure).
        from app.domain.agents.repository import get_agent_repository
        repo = get_agent_repository(service.db)
        agent = await repo.create_agent(agent_data.model_dump())
    except ValueError as e:
        # the name ban (and other validation) → a clean 400, not a 500
        raise HTTPException(status_code=400, detail=str(e))
    _announce("created", {"agent_id": agent.id, "agent_name": getattr(agent, "name", None), "event": "created"})
    return AgentResponse.model_validate(agent)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: int,
    agent_data: AgentUpdate,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentResponse:
    """
    Update an existing agent.

    Args:
        agent_id: Agent ID
        agent_data: Agent update data
        service: Agent service

    Returns:
        Updated agent

    Raises:
        HTTPException: 404 if agent not found
    """
    try:
        agent = await service.update(agent_id, agent_data)
    except ValueError as e:
        # the rename BAN (2026-08-19): a duplicate name → a clean 400
        raise HTTPException(status_code=400, detail=str(e))
    _announce("updated", {"agent_id": agent_id, "agent_name": getattr(agent, "name", None), "event": "updated"})
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with id {agent_id} not found",
        )
    resp = AgentResponse.model_validate(agent)
    health_map = await service.health_for_agents([agent.id])
    resp.health = health_map.get(agent.id)
    # The save that just changed the declaration returns what it now resolves to
    # (G.1) — so the edit loop shows the new declared-vs-sent pair without a refetch.
    resp.output_budget = (await service.output_budget_for_agents([agent])).get(agent.id)
    # ...and the availability the save just changed (G5-F2): pointing an agent at a service
    # that is down must show up on the very response that did it.
    resp.service_availability = _availability_out(
        (await chat_readiness(service.db, [agent])).get(agent.id)
    )

    # THE CROSS-WINDOW SYNC (2026-08-24, the user's use case): the
    # agent changed — publish the event so EVERY open tab/window
    # (each with its own SSE connection) hears it and refreshes its
    # view. The chat page in another window updates when this
    # config changes here.
    try:
        from app.domain.messaging.services import publish
        publish(f"agent:{agent.id}:updated", {
            "agent_id": agent.id,
            "agent_name": getattr(agent, "name", None),
            "event": "updated",
        })
    except Exception as _e:
        logger.error(f"  ❌ agent:updated publish failed: {_e}")

    return resp


@router.post("/{agent_id}/adopt-package", response_model=AgentResponse)
async def adopt_package(
    agent_id: int,
    body: dict,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentResponse:
    """
    THE ADOPT ACTION (the agent-package Phase 2): provision this
    agent FROM a package blueprint — copy the package's kit_id +
    skills + llm_spec into the agent's OWN fields + set package_id
    (provenance). The agent owns its copies; the package never
    owns the agent.

    Body: {"package_id": "..."}
    """
    package_id = (body or {}).get("package_id")
    if not package_id:
        raise HTTPException(status_code=400, detail="package_id is required")
    try:
        agent = await service.adopt_package(agent_id, package_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not agent:
        raise HTTPException(
            status_code=404,
            detail=f"Agent {agent_id} or package {package_id} not found",
        )
    resp = AgentResponse.model_validate(agent)
    health_map = await service.health_for_agents([agent.id])
    resp.health = health_map.get(agent.id)
    # THE WINDOW FIT (the token-limit arc, E.3 — D9): the agent has just taken on a
    # package's copies and points at a driver. What it NEEDS (the spec's prompt floor
    # plus its declared output budget) is compared with the driver's recorded window —
    # reported, never a refusal: the runtime clamps the budget to fit (`window_clamp`).
    # A reporting check must not break the adopt, so a failure here is logged, not
    # raised.
    try:
        from app.domain.providers.model_window import (
            log_window_fit,
            needed_window_tokens,
            resolve_model_window,
        )

        spec: dict = agent.llm_spec or {}
        window_row = await resolve_model_window(
            service.db, getattr(agent, "provider", None), getattr(agent, "model", None)
        )
        log_window_fit(
            getattr(agent, "provider", None),
            getattr(agent, "model", None),
            window_row.value,
            needed_window_tokens(
                prompt_floor=spec.get("min_context"),
                # THE DECLARATION (G-I): `llm_spec.max_output`, the one slot. This
                # read used to consult BOTH homes (`params.get("max_tokens") or
                # spec.get("max_output")`) — a line that could not be right about
                # which number the turn would send.
                output_budget=spec.get("max_output"),
            ),
            who=f"Agent '{agent.name}'",
        )
    except Exception as _e:  # pragma: no cover — a report must never fail the action
        logger.warning("  ⚠️ window-fit check failed for agent %s: %s", agent_id, _e)
    # the cross-window sync: an adopted agent changed — announce it
    try:
        from app.domain.messaging.services import publish
        publish(f"agent:{agent.id}:updated", {
            "agent_id": agent.id,
            "agent_name": getattr(agent, "name", None),
        })
    except Exception as _e:
        logger.error(f"  ❌ agent:updated publish failed: {_e}")
    return resp


@router.post("/{agent_id}/duplicate", response_model=AgentResponse)
async def duplicate_agent(
    agent_id: int,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentResponse:
    """
    Create a scoped INSTANCE of an existing agent.

    The character's configuration travels — provider, model, prompt, skills, kits,
    cognitive profile, tags, settings, and its FACE (an instance of Bob looks like
    Bob) — while the instance gets its own workspace, its own state and a name
    marker (`Bob-2`). The field sort lives in `domain/agents/clone.py`, and the
    whole operation goes through the repository seam.

    Args:
        agent_id: Agent ID to duplicate
        service: Agent service

    Returns:
        The new instance

    Raises:
        HTTPException: 404 if original agent not found
    """
    from app.domain.agents.repository import get_agent_repository

    repo = get_agent_repository(service.db)
    duplicated = await repo.duplicate_agent(agent_id)
    if duplicated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with id {agent_id} not found",
        )
    return AgentResponse.model_validate(duplicated)


@router.get("/{agent_id}/export")
async def export_agent(
    agent_id: int,
    service: Annotated[AgentService, Depends(get_agent_service)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Export an agent's config, memory, and skills as a JSON bundle."""
    from app.domain.agents.export_service import export_agent as do_export
    try:
        bundle = await do_export(agent_id, db)
        return bundle
    except ValueError as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": str(e)})


@router.post("/import", status_code=201)
async def import_agent(
    bundle: dict,
    service: Annotated[AgentService, Depends(get_agent_service)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Import an agent from an export bundle."""
    from app.domain.agents.export_service import SERVICE_FROM_BUNDLE, import_agent as do_import
    logger.info(
        "Agent import: received bundle — format=%s, name=%s, has_json=%s, skills=%d, mem_entries=%d",
        bundle.get("format_version"),
        bundle.get("agent_config", {}).get("name", "?"),
        "agent_json" in bundle,
        len(bundle.get("skills", [])),
        len(bundle.get("cognitive_memory", [])),
    )
    try:
        result = await do_import(bundle, db)
        await db.commit()
        logger.info(
            "Agent import: success — new_id=%d, name=%s, service=%s/%s (from %s)",
            result.agent_id,
            bundle.get("agent_config", {}).get("name", "?"),
            result.provider,
            result.model,
            result.service_source,
        )
        body: Dict[str, Any] = {
            "message": "Agent imported successfully",
            "agent_id": result.agent_id,
        }
        if result.service_source != SERVICE_FROM_BUNDLE:
            # REPORTED, never silent (the ruling): the bundle named no service, so the response says
            # which service answered and where it came from — the user learns it here, not by opening
            # the imported agent to find out.
            body["service"] = f"{result.provider}/{result.model}"
            body["service_source"] = result.service_source
            body["message"] = (
                f"Agent imported — the bundle named no service, so it uses "
                f"{result.provider}/{result.model} ({result.service_source})"
            )
        return body
    except ValueError as e:
        logger.error("Agent import: validation failed — %s", e)
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        logger.error("Agent import: unexpected error — %s", e, exc_info=True)
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"error": f"Import failed: {e}"})

@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: int,
    service: Annotated[AgentService, Depends(get_agent_service)],
    hard: bool = Query(False, description="Permanently scrub the agent (IRREVERSIBLE)"),
) -> Dict[str, Any]:
    """
    Delete an agent — the recoverable delete (agent-lifecycle
    Phase C), or the permanent scrub (hard=True, 2026-08-19).

    Soft (default): the workspace MOVES onto the trash's agents
    shelf (`trash/agents/`, never hard-deleted), the row is
    SOFT-deleted (deleted_at + archived_path — history keeps its
    reference), relational rows (tool links, grants, collections,
    chat sessions) are removed. Recoverable via Restore.

    Hard (hard=True): EVERYTHING is removed — the row, all
    references (tool links, grants, collections, sessions,
    messages, usage logs, versions, runtime configs), the
    workspace (archived or live), and the cognitive-memory file.
    IRREVERSIBLE — nothing can restore it.

    Args:
        agent_id: Agent ID
        service: Agent service
        hard: True = permanent scrub, False = recoverable delete

    Returns:
        The delete report (deleted, agent_name, bom, archived_path)

    Raises:
        HTTPException: 404 if agent not found
        HTTPException: 403 if agent is a built-in system agent
    """
    from app.domain.agents.repository import get_agent_repository
    repo = get_agent_repository(service.db)
    try:
        if hard:
            report = await repo.hard_delete_agent(agent_id)
        else:
            report = await repo.delete_agent(agent_id)
    except ValueError as e:
        # Built-in agent protection
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    _announce("deleted", {"agent_id": agent_id, "event": "deleted", "agent_name": report.get("agent_name")})

    if not report.get("deleted"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with id {agent_id} not found",
        )
    return report


@router.post("/{agent_id}/reset-memory")
async def reset_agent_memory(
    agent_id: int,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> Dict[str, Any]:
    """
    Reset an agent's learned state (2026-08-19): the cognitive-
    memory DB is cleared (the deep agent's watch-it-learn demo
    restarts fresh) + the chat sessions are removed. The agent
    SURVIVES — the row, workspace, skills, and identity stay.
    Destructive-ish (memory is lost) but not deletion — the UI
    confirms explicitly.

    Args:
        agent_id: Agent ID
        service: Agent service

    Returns:
        The reset report (what was cleared)

    Raises:
        HTTPException: 404 if agent not found
    """
    from app.domain.agents.repository import get_agent_repository
    repo = get_agent_repository(service.db)
    report = await repo.reset_agent_memory(agent_id)
    if not report.get("reset"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with id {agent_id} not found",
        )
    return report


@router.post("/{agent_id}/restore", response_model=AgentResponse)
async def restore_agent(
    agent_id: int,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentResponse:
    """Restore a soft-deleted agent — ADDITIVE recovery (Phase D):
    the archived workspace moves back, the delete markers clear.
    Explicit, never automatic (the destructive-UX rule).

    Raises HTTPException 400 if the agent is not soft-deleted."""
    from app.domain.agents.repository import get_agent_repository
    repo = get_agent_repository(service.db)
    try:
        agent = await repo.restore_agent(agent_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return AgentResponse.model_validate(agent)


@router.post("/{agent_id}/image", response_model=AgentResponse)
async def upload_agent_image(
    agent_id: int,
    file: UploadFile,
    service: Annotated[AgentService, Depends(get_agent_service)],
    strip: Annotated[bool, Query()] = False,
) -> AgentResponse:
    """
    Upload profile image for an agent.

    Args:
        agent_id: Agent ID
        file: Image file to upload
        service: Agent service

    Returns:
        Updated agent with image URL

    Raises:
        HTTPException: 404 if agent not found, 400 if file invalid
    """
    # Verify agent exists
    agent = await service.get_by_id(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with id {agent_id} not found",
        )

    # Validate and save image
    _validate_image_file(file)
    image_path = _save_image(file, agent_id, strip=strip)

    # Convert file path to URL for frontend
    # Extract just the filename since static files are mounted at /static/
    # pointing to the profile_images_dir
    filename = Path(image_path).name
    image_url = f"/static/{filename}"

    # Update agent with image URL
    updated_agent = await service.update_profile_image(agent_id, image_url)

    return AgentResponse.model_validate(updated_agent)


# =============================================================================
# THE KITS (2026-09-04, the agent-kits build P4) — the agent-side of the
# agent_kits JOIN: list the agent's toolkits, attach one, detach one.
# =============================================================================


async def _get_agent_or_404(db: AsyncSession, agent_id: int) -> None:
    from sqlalchemy import select

    from app.infrastructure.database.models import Agent

    agent = (
        await db.execute(select(Agent.id).where(Agent.id == agent_id))
    ).scalar_one_or_none()
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with id {agent_id} not found",
        )


def _kit_summary(kit) -> dict:
    return {
        "id": kit.id,
        "name": kit.name,
        "description": kit.description,
        "color": kit.color,
        "icon": kit.icon,
    }


@router.get("/{agent_id}/kits", response_model=AgentKitsResponse)
async def list_agent_kits(
    agent_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AgentKitsResponse:
    """The agent's toolkits (the join direction: what does Bob own?)."""
    from app.domain.agent_kits.service import AgentKitService

    svc = AgentKitService(db)
    kits = await svc.kits_for_agent(agent_id)
    return AgentKitsResponse(agent_id=agent_id, kits=[_kit_summary(k) for k in kits])


@router.post("/{agent_id}/kits", response_model=AgentKitsResponse, status_code=status.HTTP_201_CREATED)
async def attach_agent_kit(
    agent_id: int,
    body: AgentKitAttach,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AgentKitsResponse:
    """Attach a toolkit to the agent (idempotent — a repeat attach is a no-op)."""
    from app.domain.agent_kits.service import AgentKitService

    await _get_agent_or_404(db, agent_id)
    svc = AgentKitService(db)
    await svc.attach(agent_id, body.kit_id)
    await db.commit()
    kits = await svc.kits_for_agent(agent_id)
    return AgentKitsResponse(agent_id=agent_id, kits=[_kit_summary(k) for k in kits])


@router.delete("/{agent_id}/kits/{kit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def detach_agent_kit(
    agent_id: int,
    kit_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Detach a toolkit from the agent (idempotent)."""
    from app.domain.agent_kits.service import AgentKitService

    await _get_agent_or_404(db, agent_id)
    svc = AgentKitService(db)
    await svc.detach(agent_id, kit_id)
    await db.commit()
