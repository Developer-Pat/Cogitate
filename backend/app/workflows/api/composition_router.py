"""
FastAPI router for workflow composition operations.

Provides REST API endpoints for:
- Creating and managing workflow compositions
- Executing compositions
- Listing available compositions
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from app.domain.workflows.services.composition_service import CompositionService

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/compositions", tags=["workflow-compositions"])


# ============== Request/Response Models ==============

class CompositionCreateRequest(BaseModel):
    """Request to create a workflow composition."""
    id: str = Field(
        ...,
        description="Unique identifier for this composition",
        examples=["content-pipeline"]
    )
    name: str = Field(
        ...,
        description="Human-readable name",
        examples=["Content Production Pipeline"]
    )
    description: str = Field(
        default="",
        description="Detailed description",
        examples=["Research topic, review content, and publish final output"]
    )
    workflows: List[Dict[str, Any]] = Field(
        ...,
        description="List of workflow references",
        examples=[[
            {
                "workflow_id": "parallel-research-analysis",
                "order": 1,
                "input_mapping": {"user_input": "initial_query"},
                "output_mapping": {"research_output": "final_output"}
            },
            {
                "workflow_id": "creative-review",
                "order": 2,
                "input_mapping": {"user_input": "research_output"},
                "output_mapping": {"reviewed_content": "final_output"}
            }
        ]]
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorization"
    )


class CompositionExecuteRequest(BaseModel):
    """Request to execute a workflow composition."""
    composition_id: str = Field(
        ...,
        description="ID of composition to execute",
        examples=["content-pipeline"]
    )
    initial_input: Dict[str, Any] = Field(
        ...,
        description="Initial input data for the composition",
        examples=[{"initial_query": "AI trends in 2026"}]
    )
    workflow_id: Optional[str] = Field(
        None,
        description="Optional custom workflow execution ID"
    )


class CompositionExecuteResponse(BaseModel):
    """Response after executing composition."""
    composition_id: str
    status: str
    outputs: Optional[Dict[str, Any]] = None
    workflow_results: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None
    elapsed_seconds: float = 0.0


class CompositionInfo(BaseModel):
    """Information about a composition."""
    id: str
    name: str
    description: str
    tags: List[str]
    workflow_count: int
    workflows: List[Dict[str, Any]]


# ============== Service Instance ==============

def get_service() -> "CompositionService":
    """Get composition service instance."""
    from app.domain.workflows.services.composition_service import CompositionService
    return CompositionService()


# ============== API Endpoints ==============

@router.post("", response_model=CompositionInfo)
async def create_composition(request: CompositionCreateRequest):
    """
    Create a new workflow composition.
    
    Creates a composition configuration that chains multiple workflows together
    with input/output mapping.
    """
    service = get_service()
    
    # Build composition config
    from app.domain.workflows.schemas.composition_config import WorkflowComposition, WorkflowReference
    
    try:
        workflow_refs = [
            WorkflowReference(**wf) for wf in request.workflows
        ]
        
        config = WorkflowComposition(
            id=request.id,
            name=request.name,
            description=request.description,
            workflows=workflow_refs,
            tags=request.tags,
        )
        
    except Exception as e:
        logger.error(f"❌ Invalid composition config: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid composition config: {str(e)}")
    
    # Create composition
    success = service.create_composition(config)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to create composition (may already exist)")
    
    logger.info(f"✅ Created composition: {config.id}")
    
    return CompositionInfo(
        id=config.id,
        name=config.name,
        description=config.description,
        tags=config.tags,
        workflow_count=len(config.workflows),
        workflows=[wf.model_dump() for wf in config.workflows],
    )


@router.get("", response_model=List[CompositionInfo])
async def list_compositions(active_only: bool = True):
    """
    List all workflow compositions.
    
    Returns compositions with their configurations.
    """
    service = get_service()
    
    compositions = service.list_compositions(active_only=active_only)
    
    return [
        CompositionInfo(
            id=comp.id,
            name=comp.name,
            description=comp.description,
            tags=comp.tags or [],
            workflow_count=len(comp.workflows),
            workflows=[wf.model_dump() for wf in comp.workflows],
        )
        for comp in compositions
    ]


@router.get("/{composition_id}", response_model=CompositionInfo)
async def get_composition(composition_id: str):
    """
    Get composition details.
    
    Returns full composition configuration.
    """
    service = get_service()
    
    composition = service.get_composition(composition_id)
    
    if not composition:
        raise HTTPException(status_code=404, detail="Composition not found")
    
    return CompositionInfo(
        id=composition.id,
        name=composition.name,
        description=composition.description,
        tags=composition.tags or [],
        workflow_count=len(composition.workflows),
        workflows=[wf.model_dump() for wf in composition.workflows],
    )


@router.post("/{composition_id}/execute", response_model=CompositionExecuteResponse)
async def execute_composition(
    composition_id: str,
    request: CompositionExecuteRequest,
    background_tasks: BackgroundTasks
):
    """
    Execute a workflow composition.
    
    Executes all workflows in the composition in order, with input/output mapping.
    """
    service = get_service()
    
    # Verify composition exists
    composition = service.get_composition(composition_id)
    if not composition:
        raise HTTPException(status_code=404, detail="Composition not found")
    
    logger.info(f"🚀 Executing composition: {composition_id}")
    
    try:
        # Execute composition
        result = service.execute_composition(
            composition_id=composition_id,
            initial_input=request.initial_input,
            workflow_id=request.workflow_id
        )
        
        return CompositionExecuteResponse(
            composition_id=result.composition_id,
            status=result.status,
            outputs=result.outputs,
            workflow_results=result.workflow_results,
            error=result.error,
            started_at=result.started_at,
            completed_at=result.completed_at,
            elapsed_seconds=result.elapsed_seconds,
        )
        
    except Exception as e:
        logger.error(f"❌ Composition execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")


@router.delete("/{composition_id}")
async def delete_composition(composition_id: str):
    """
    Delete a workflow composition (soft delete).
    
    Marks composition as inactive.
    """
    service = get_service()
    
    success = service.delete_composition(composition_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Composition not found")
    
    return {"message": f"Composition {composition_id} deleted successfully"}


@router.put("/{composition_id}")
async def update_composition(composition_id: str, updates: Dict[str, Any]):
    """
    Update a workflow composition.
    
    Updates composition configuration.
    """
    service = get_service()
    
    # Verify composition exists
    composition = service.get_composition(composition_id)
    if not composition:
        raise HTTPException(status_code=404, detail="Composition not found")
    
    success = service.update_composition(composition_id, updates)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to update composition")
    
    return {"message": f"Composition {composition_id} updated successfully"}
