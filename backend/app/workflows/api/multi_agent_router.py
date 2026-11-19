"""
FastAPI router for multi-agent workflow execution.

Provides REST API endpoints for:
- Executing multi-agent workflows
- Listing available multi-agent templates
- Getting template details
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from app.domain.workflows.services.orchestration_service import MultiAgentOrchestrationService

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/multi-agent", tags=["multi-agent-workflows"])


# ============== Request/Response Models ==============

class MultiAgentExecuteRequestModel(BaseModel):
    """Request to execute a multi-agent workflow."""
    template_id: str = Field(
        ...,
        description="ID of multi-agent template to execute",
        examples=["story-collab-hunter-editor"]
    )
    initial_message: str = Field(
        ...,
        description="Initial user input/message",
        examples=["Write a sci-fi story about a time traveler"]
    )
    workflow_id: Optional[str] = Field(
        None,
        description="Optional custom workflow ID (generated if not provided)",
        examples=["wf-custom-123"]
    )


class AgentOutput(BaseModel):
    """Output from a single agent in the chain."""
    agent_name: str
    agent_id: int
    content: str


class MultiAgentExecuteResponse(BaseModel):
    """Response after executing multi-agent workflow."""
    workflow_id: str
    template_id: str
    status: str
    output: Any
    agent_outputs: Optional[Dict[str, AgentOutput]] = None
    error: Optional[str] = None
    started_at: str
    completed_at: str
    elapsed_seconds: float


class MultiAgentTemplateInfo(BaseModel):
    """Information about a multi-agent template."""
    id: str
    name: str
    description: str
    tags: List[str]
    workflow_type: str


class MultiAgentTemplateDetail(BaseModel):
    """Detailed information about a multi-agent template."""
    id: str
    name: str
    description: str
    workflow_type: str
    tags: List[str]
    category: str
    agent_count: int
    context_mode: str
    final_output_key: str
    agents: List[Dict[str, Any]]


# ============== Service Instance ==============

def get_service() -> "MultiAgentOrchestrationService":
    """Get orchestration service instance."""
    # Lazy import to avoid circular dependency
    from app.domain.workflows.services.orchestration_service import MultiAgentOrchestrationService
    return MultiAgentOrchestrationService()


# ============== API Endpoints ==============

@router.post("/execute", response_model=MultiAgentExecuteResponse)
async def execute_multi_agent_workflow(
    request: MultiAgentExecuteRequestModel,
    background_tasks: BackgroundTasks,
):
    """
    Execute a multi-agent workflow.

    This endpoint:
    1. Loads the multi-agent template from database
    2. Validates the configuration
    3. Builds the LangGraph workflow
    4. Executes all agents in sequence
    5. Returns the final output and all agent contributions

    **Example**:
    ```bash
    curl -X POST http://localhost:8000/api/v1/workflows/multi-agent/execute \\
      -H "Content-Type: application/json" \\
      -d '{
        "template_id": "story-collab-hunter-editor",
        "initial_message": "Write a sci-fi story about a time traveler"
      }'
    ```

    **Response**:
    - `workflow_id`: Unique execution ID
    - `status`: "completed" or "error"
    - `output`: Final output (e.g., complete story)
    - `agent_outputs`: Individual agent contributions
    - `elapsed_seconds`: Execution time

    **Errors**:
    - 404: Template not found
    - 400: Invalid template (not multi-agent)
    - 500: Execution failed
    """
    service = get_service()

    try:
        # Check if template exists and is multi-agent type
        template = service.get_template_info(request.template_id)
        
        logger.info(f"🚀 Executing multi-agent workflow: {request.template_id}")
        logger.info(f"   Agents: {len(template['validated_config']['agents'])}")
        logger.info(f"   Input: {request.initial_message[:100]}...")

        # Execute workflow
        result = await service.execute_multi_agent(
            template_id=request.template_id,
            initial_message=request.initial_message,
            workflow_id=request.workflow_id
        )

        logger.info(f"✅ Multi-agent workflow completed: {result.status}")
        logger.info(f"   Elapsed: {result.elapsed_seconds:.2f}s")

        # Convert agent outputs to response model
        agent_outputs_response = None
        if result.agent_outputs:
            agent_outputs_response = {}
            for key, value in result.agent_outputs.items():
                agent_outputs_response[key] = AgentOutput(**value)

        return MultiAgentExecuteResponse(
            workflow_id=result.workflow_id,
            template_id=result.template_id,
            status=result.status,
            output=result.output,
            agent_outputs=agent_outputs_response,
            error=result.error,
            started_at=result.started_at,
            completed_at=result.completed_at,
            elapsed_seconds=result.elapsed_seconds
        )

    except ValueError as e:
        logger.warning(f"⚠️ Multi-agent workflow request invalid: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"❌ Multi-agent workflow execution failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")


@router.get("/templates", response_model=List[MultiAgentTemplateInfo])
async def list_multi_agent_templates():
    """
    List all available multi-agent templates.

    Returns a list of multi-agent workflow templates that can be executed.

    **Example**:
    ```bash
    curl http://localhost:8000/api/v1/workflows/multi-agent/templates
    ```

    **Response**:
    - List of templates with id, name, description, tags
    """
    service = get_service()
    
    try:
        templates = service.list_multi_agent_templates()
        
        return [
            MultiAgentTemplateInfo(
                id=t["id"],
                name=t["name"],
                description=t["description"],
                tags=t["tags"],
                workflow_type=t["workflow_type"]
            )
            for t in templates
        ]
    
    except Exception as e:
        logger.error(f"Failed to list multi-agent templates: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates/{template_id}", response_model=MultiAgentTemplateDetail)
async def get_multi_agent_template(template_id: str):
    """
    Get detailed information about a multi-agent template.

    Returns full template configuration including agent chain.

    **Example**:
    ```bash
    curl http://localhost:8000/api/v1/workflows/multi-agent/templates/story-collab-hunter-editor
    ```

    **Response**:
    - Template metadata (name, description, tags)
    - Agent chain configuration
    - Context mode and output keys

    **Errors**:
    - 404: Template not found
    - 400: Not a multi-agent template
    """
    service = get_service()
    
    try:
        template = service.get_template_info(template_id)
        config = template["validated_config"]
        
        return MultiAgentTemplateDetail(
            id=template["id"],
            name=template["name"],
            description=template["description"],
            workflow_type=template["workflow_type"],
            tags=template["tags"],
            category=template["category"],
            agent_count=len(config["agents"]),
            context_mode=config["context_mode"],
            final_output_key=config["final_output_key"],
            agents=config["agents"]
        )
    
    except ValueError as e:
        logger.warning(f"Template request invalid: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"Failed to get template: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def multi_agent_health_check():
    """
    Health check for multi-agent workflow service.

    Verifies database connectivity and template availability.
    """
    service = get_service()
    
    try:
        templates = service.list_multi_agent_templates()
        
        return {
            "status": "healthy",
            "service": "multi-agent-orchestration",
            "templates_available": len(templates),
            "database": "connected"
        }
    
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "multi-agent-orchestration",
            "error": str(e)
        }
