"""
FastAPI router for agent registry and versioning.

Provides REST API endpoints for:
- Agent configuration CRUD
- Version management
- A/B test management
- Agent routing

Usage:
    Include router in FastAPI app:
    ```python
    from app.workflows.agent_versioning.api.router import router as agents_router

    app.include_router(agents_router, prefix="/api/v1")
    ```
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Optional, Dict, List

from ..registry import AgentRegistry, AgentConfig
from ..ab_testing import ABTestManager, ABTestConfig, ABTestVariant

router = APIRouter(prefix="/agents", tags=["agents"])


# ============== Request/Response Models ==============

class CreateAgentRequest(BaseModel):
    """Request to create a new agent."""
    name: str = Field(..., description="Human-readable name")
    version: str = Field(..., description="Semantic version")
    description: str = Field(..., description="Agent purpose")
    role: Optional[str] = Field(None, description="Agent role/persona")
    goal: Optional[str] = Field(None, description="Primary objective")
    backstory: Optional[str] = Field(None, description="Context/personality")
    llm_model: str = Field(default="gpt-4o-mini", description="LLM model")
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    # REMOVED (G-I, 2026-09-25): `max_tokens` — nothing read it (see the note in
    # `registry.AgentConfig`). A budget nobody reads is a number that decides nothing.
    tools: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreateAgentResponse(BaseModel):
    """Response after creating agent."""
    agent_id: str
    version: str
    name: str
    status: str
    message: str = "Agent created successfully"


class AgentDetailResponse(BaseModel):
    """Detailed agent information."""
    id: str
    name: str
    version: str
    description: str
    role: Optional[str]
    goal: Optional[str]
    backstory: Optional[str]
    llm_model: str
    temperature: float
    tools: List[str]
    metadata: Dict[str, Any]
    created_at: str
    updated_at: str


class AgentVersionResponse(BaseModel):
    """Agent version information."""
    version: str
    agent_id: str
    status: str
    changelog: Optional[str]
    is_ab_testable: bool
    traffic_percentage: int


class UpdateAgentStatusRequest(BaseModel):
    """Request to update agent version status."""
    status: str = Field(..., description="New status (draft, active, archived, deprecated)")


class CreateABTestRequest(BaseModel):
    """Request to create A/B test."""
    name: str = Field(..., description="Test name")
    description: str = Field(..., description="Test purpose")
    variants: List[ABTestVariant] = Field(..., description="Test variants")


class CreateABTestResponse(BaseModel):
    """Response after creating A/B test."""
    test_id: str
    name: str
    status: str
    message: str = "A/B test created successfully"


class ABTestDetailResponse(BaseModel):
    """Detailed A/B test information."""
    id: str
    name: str
    description: str
    variants: List[ABTestVariant]
    status: str
    start_time: Optional[str]
    end_time: Optional[str]


class RouteAgentRequest(BaseModel):
    """Request to route agent via A/B test."""
    test_id: str = Field(..., description="A/B test ID")
    user_id: Optional[str] = Field(None, description="User ID for sticky routing")


class RouteAgentResponse(BaseModel):
    """Response with routed agent."""
    agent_id: str
    test_id: str
    variant_name: Optional[str]
    message: str = "Agent routed successfully"


# ============== Helper Functions ==============

def generate_agent_id(name: str) -> str:
    """Generate agent ID from name."""
    import re
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return f"agent-{slug}"


# ============== Agent Registry Endpoints ==============

@router.post("", response_model=CreateAgentResponse)
async def create_agent(request: CreateAgentRequest):
    """
    Create a new agent configuration.

    Registers agent in the registry with specified version.
    Auto-generates agent ID from name.

    **Example**:
    ```python
    POST /api/v1/agents
    {
        "name": "Research Assistant",
        "version": "1.0.0",
        "description": "Helps with research",
        "role": "Research Analyst",
        "llm_model": "gpt-4o-mini"
    }

    Response:
    {
        "agent_id": "agent-research-assistant",
        "version": "1.0.0",
        "status": "active"
    }
    ```
    """
    # Generate agent ID
    agent_id = generate_agent_id(request.name)

    # Check if version already exists
    existing = AgentRegistry.get(agent_id, request.version)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Agent {agent_id} version {request.version} already exists"
        )

    # Create agent configuration
    config = AgentConfig(
        id=agent_id,
        name=request.name,
        version=request.version,
        description=request.description,
        role=request.role,
        goal=request.goal,
        backstory=request.backstory,
        llm_model=request.llm_model,
        temperature=request.temperature,
        tools=request.tools,
        metadata=request.metadata,
    )

    # Register agent
    try:
        AgentRegistry.register(config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return CreateAgentResponse(
        agent_id=agent_id,
        version=request.version,
        name=request.name,
        status="active"
    )


@router.get("/{agent_id}", response_model=AgentDetailResponse)
async def get_agent(agent_id: str, version: Optional[str] = None):
    """
    Get agent configuration.

    Returns latest active version if version not specified.

    **Example**:
    ```python
    GET /api/v1/agents/agent-research-assistant
    GET /api/v1/agents/agent-research-assistant?version=1.0.0
    ```
    """
    config = AgentRegistry.get(agent_id, version)

    if not config:
        version_msg = f" version {version}" if version else ""
        raise HTTPException(
            status_code=404,
            detail=f"Agent {agent_id}{version_msg} not found"
        )

    return AgentDetailResponse(
        id=config.id,
        name=config.name,
        version=config.version,
        description=config.description,
        role=config.role,
        goal=config.goal,
        backstory=config.backstory,
        llm_model=config.llm_model,
        temperature=config.temperature,
        tools=config.tools,
        metadata=config.metadata,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.get("/{agent_id}/versions", response_model=List[AgentVersionResponse])
async def get_agent_versions(agent_id: str):
    """
    Get all versions of an agent.

    Returns version history with status and metadata.

    **Example**:
    ```python
    GET /api/v1/agents/agent-research-assistant/versions
    ```
    """
    versions = AgentRegistry.get_all_versions(agent_id)

    if not versions:
        # Check if agent exists at all
        if not AgentRegistry.get(agent_id):
            raise HTTPException(
                status_code=404,
                detail=f"Agent {agent_id} not found"
            )

    return [
        AgentVersionResponse(
            version=v.version,
            agent_id=v.agent_id,
            status=v.status,
            changelog=v.changelog,
            is_ab_testable=v.is_ab_testable,
            traffic_percentage=v.traffic_percentage,
        )
        for v in versions
    ]


@router.patch("/{agent_id}/versions/{version}/status", response_model=Dict[str, Any])
async def update_agent_version_status(
    agent_id: str,
    version: str,
    request: UpdateAgentStatusRequest,
):
    """
    Update agent version status.

    Statuses: draft, active, archived, deprecated

    **Example**:
    ```python
    PATCH /api/v1/agents/agent-research-assistant/versions/1.0.0/status
    {
        "status": "archived"
    }
    ```
    """
    success = AgentRegistry.update_status(agent_id, version, request.status)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Agent {agent_id} version {version} not found"
        )

    return {
        "agent_id": agent_id,
        "version": version,
        "status": request.status,
        "message": f"Status updated to {request.status}"
    }


@router.post("/{agent_id}/set-default", response_model=Dict[str, Any])
async def set_default_agent_version(agent_id: str, version: str):
    """
    Set default version for an agent.

    This version will be used when no version is specified.

    **Example**:
    ```python
    POST /api/v1/agents/agent-research-assistant/set-default
    {
        "version": "2.0.0"
    }
    ```
    """
    success = AgentRegistry.set_default(agent_id, version)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Agent {agent_id} version {version} not found"
        )

    return {
        "agent_id": agent_id,
        "version": version,
        "message": "Default version updated"
    }


@router.get("", response_model=List[Dict[str, str]])
async def list_agents():
    """
    List all registered agents.

    Returns agent IDs. Use /{agent_id} for details.

    **Example**:
    ```python
    GET /api/v1/agents
    ```
    """
    agents = AgentRegistry.list_agents()
    return [{"agent_id": agent_id} for agent_id in agents]


# ============== A/B Testing Endpoints ==============

@router.post("/ab-tests", response_model=CreateABTestResponse)
async def create_ab_test(request: CreateABTestRequest):
    """
    Create a new A/B test.

    Defines experiment with variants and traffic distribution.
    Traffic percentages must sum to 100.

    **Example**:
    ```python
    POST /api/v1/agents/ab-tests
    {
        "name": "Agent Performance Test",
        "description": "Test v2 vs v1",
        "variants": [
            {
                "agent_id": "agent-assistant-v1",
                "traffic_percentage": 50,
                "name": "Control"
            },
            {
                "agent_id": "agent-assistant-v2",
                "traffic_percentage": 50,
                "name": "Treatment"
            }
        ]
    }
    ```
    """
    import uuid

    test_id = f"ab-{uuid.uuid4().hex[:8]}"

    config = ABTestConfig.model_construct(
        id=test_id,
        name=request.name,
        description=request.description,
        variants=request.variants,
        status="draft",
    )

    try:
        ABTestManager.create_test(config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return CreateABTestResponse(
        test_id=test_id,
        name=request.name,
        status="draft"
    )


@router.get("/ab-tests/{test_id}", response_model=ABTestDetailResponse)
async def get_ab_test(test_id: str):
    """
    Get A/B test details.

    Returns test configuration and current status.

    **Example**:
    ```python
    GET /api/v1/agents/ab-tests/ab-12345678
    ```
    """
    test = ABTestManager.get_test(test_id)

    if not test:
        raise HTTPException(
            status_code=404,
            detail=f"A/B test {test_id} not found"
        )

    return ABTestDetailResponse(
        id=test.id,
        name=test.name,
        description=test.description,
        variants=test.variants,
        status=test.status,
        start_time=test.start_time,
        end_time=test.end_time,
    )


@router.post("/ab-tests/{test_id}/start", response_model=Dict[str, Any])
async def start_ab_test(test_id: str):
    """
    Start an A/B test.

    Changes status to 'running' and records start time.

    **Example**:
    ```python
    POST /api/v1/agents/ab-tests/ab-12345678/start
    ```
    """
    success = ABTestManager.start_test(test_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"A/B test {test_id} not found"
        )

    return {
        "test_id": test_id,
        "status": "running",
        "message": "A/B test started"
    }


@router.post("/ab-tests/{test_id}/pause", response_model=Dict[str, Any])
async def pause_ab_test(test_id: str):
    """
    Pause an A/B test.

    Temporarily stops routing.

    **Example**:
    ```python
    POST /api/v1/agents/ab-tests/ab-12345678/pause
    ```
    """
    success = ABTestManager.pause_test(test_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"A/B test {test_id} not found"
        )

    return {
        "test_id": test_id,
        "status": "paused",
        "message": "A/B test paused"
    }


@router.post("/ab-tests/{test_id}/complete", response_model=Dict[str, Any])
async def complete_ab_test(test_id: str):
    """
    Complete an A/B test.

    Marks test as completed and records end time.

    **Example**:
    ```python
    POST /api/v1/agents/ab-tests/ab-12345678/complete
    ```
    """
    success = ABTestManager.complete_test(test_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"A/B test {test_id} not found"
        )

    return {
        "test_id": test_id,
        "status": "completed",
        "message": "A/B test completed"
    }


@router.get("/ab-tests", response_model=List[Dict[str, Any]])
async def list_ab_tests(status: Optional[str] = None):
    """
    List A/B tests.

    Optional status filter: draft, running, paused, completed

    **Example**:
    ```python
    GET /api/v1/agents/ab-tests
    GET /api/v1/agents/ab-tests?status=running
    ```
    """
    tests = ABTestManager.list_tests(status)
    return [
        {
            "id": test.id,
            "name": test.name,
            "status": test.status,
        }
        for test in tests
    ]


@router.post("/route", response_model=RouteAgentResponse)
async def route_agent(request: RouteAgentRequest):
    """
    Route to agent via A/B test.

    Returns agent ID based on test configuration and user ID.
    Uses consistent hashing for sticky sessions.

    **Example**:
    ```python
    POST /api/v1/agents/route
    {
        "test_id": "ab-12345678",
        "user_id": "user-456"
    }

    Response:
    {
        "agent_id": "agent-assistant-v2",
        "test_id": "ab-12345678"
    }
    ```
    """
    agent_id = ABTestManager.get_routed_agent(request.test_id, request.user_id)

    if not agent_id:
        test = ABTestManager.get_test(request.test_id)
        if not test:
            raise HTTPException(
                status_code=404,
                detail=f"A/B test {request.test_id} not found"
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"A/B test {request.test_id} is not running"
            )

    # Find variant name
    test = ABTestManager.get_test(request.test_id)
    variant_name = None
    if test:
        for variant in test.variants:
            if variant.agent_id == agent_id:
                variant_name = variant.name
                break

    return RouteAgentResponse(
        agent_id=agent_id,
        test_id=request.test_id,
        variant_name=variant_name,
    )
