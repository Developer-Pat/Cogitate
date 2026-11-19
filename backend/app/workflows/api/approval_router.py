"""
FastAPI router for human-in-the-loop approval operations.

Provides REST API endpoints for:
- Listing pending approvals
- Approving workflows
- Rejecting workflows
- Requesting changes
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from app.domain.workflows.services.approval_service import ApprovalService

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/approvals", tags=["human-in-the-loop"])


# ============== Request/Response Models ==============

class ApprovalResponse(BaseModel):
    """Response for approval operations."""
    approval_id: str
    workflow_execution_id: str
    status: str
    message: str


class ApproveRequest(BaseModel):
    """Request to approve a workflow."""
    approver_id: Optional[str] = Field(
        None,
        description="ID of the approver",
        examples=["user-123"]
    )
    approver_email: Optional[str] = Field(
        None,
        description="Email of the approver",
        examples=["approver@example.com"]
    )
    feedback: Optional[str] = Field(
        None,
        description="Optional feedback from approver",
        examples=["Looks good, ready to publish"]
    )


class RejectRequest(BaseModel):
    """Request to reject a workflow."""
    approver_id: Optional[str] = Field(
        None,
        description="ID of the approver"
    )
    approver_email: Optional[str] = Field(
        None,
        description="Email of the approver"
    )
    feedback: Optional[str] = Field(
        ...,
        description="Required feedback explaining rejection",
        examples=["Needs more research on topic X"]
    )


class RequestChangesRequest(BaseModel):
    """Request to request changes for a workflow."""
    approver_id: Optional[str] = Field(
        None,
        description="ID of the approver"
    )
    approver_email: Optional[str] = Field(
        None,
        description="Email of the approver"
    )
    feedback: Optional[str] = Field(
        ...,
        description="Required feedback describing changes needed",
        examples=["Please add more examples and clarify section 2"]
    )


class ApprovalInfo(BaseModel):
    """Information about an approval request."""
    id: str
    workflow_execution_id: str
    composition_id: Optional[str] = None
    template_id: str
    status: str
    requested_at: str
    responded_at: Optional[str] = None
    approver_id: Optional[str] = None
    approver_email: Optional[str] = None
    decision: Optional[str] = None
    feedback: Optional[str] = None
    timeout_at: Optional[str] = None


# ============== Service Instance ==============

def get_service() -> "ApprovalService":
    """Get approval service instance."""
    from app.domain.workflows.services.approval_service import ApprovalService
    return ApprovalService()


# ============== API Endpoints ==============

@router.get("/pending", response_model=List[ApprovalInfo])
async def list_pending_approvals(
    composition_id: Optional[str] = None,
    limit: int = 50
):
    """
    List all pending approvals.
    
    Returns workflows waiting for human approval.
    """
    service = get_service()
    
    approvals = service.list_pending_approvals(
        composition_id=composition_id,
        limit=limit
    )
    
    return [
        ApprovalInfo(
            id=approval.id,
            workflow_execution_id=approval.workflow_execution_id,
            composition_id=approval.composition_id,
            template_id=approval.template_id,
            status=approval.status,
            requested_at=approval.requested_at,
            responded_at=approval.responded_at,
            approver_id=approval.approver_id,
            approver_email=approval.approver_email,
            decision=approval.decision,
            feedback=approval.feedback,
            timeout_at=approval.timeout_at,
        )
        for approval in approvals
    ]


@router.get("/{approval_id}", response_model=ApprovalInfo)
async def get_approval(approval_id: str):
    """
    Get approval request details.
    
    Returns full approval information.
    """
    service = get_service()
    
    approval = service.get_approval(approval_id)
    
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    
    return ApprovalInfo(
        id=approval.id,
        workflow_execution_id=approval.workflow_execution_id,
        composition_id=approval.composition_id,
        template_id=approval.template_id,
        status=approval.status,
        requested_at=approval.requested_at,
        responded_at=approval.responded_at,
        approver_id=approval.approver_id,
        approver_email=approval.approver_email,
        decision=approval.decision,
        feedback=approval.feedback,
        timeout_at=approval.timeout_at,
    )


@router.get("/workflow/{workflow_execution_id}", response_model=ApprovalInfo)
async def get_approval_by_workflow(workflow_execution_id: str):
    """
    Get approval request by workflow execution ID.
    
    Returns approval information for a specific workflow.
    """
    service = get_service()
    
    approval = service.get_approval_by_workflow(workflow_execution_id)
    
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found for workflow")
    
    return ApprovalInfo(
        id=approval.id,
        workflow_execution_id=approval.workflow_execution_id,
        composition_id=approval.composition_id,
        template_id=approval.template_id,
        status=approval.status,
        requested_at=approval.requested_at,
        responded_at=approval.responded_at,
        approver_id=approval.approver_id,
        approver_email=approval.approver_email,
        decision=approval.decision,
        feedback=approval.feedback,
        timeout_at=approval.timeout_at,
    )


@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
async def approve_workflow(approval_id: str, request: ApproveRequest):
    """
    Approve a workflow execution.
    
    Resumes workflow execution after human approval.
    """
    service = get_service()
    
    # Verify approval exists
    approval = service.get_approval(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    
    # Approve workflow
    success = service.approve_workflow(
        approval_id=approval_id,
        approver_id=request.approver_id,
        approver_email=request.approver_email,
        feedback=request.feedback
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to approve workflow")
    
    logger.info(f"✅ Approved workflow {approval.workflow_execution_id}")
    
    return ApprovalResponse(
        approval_id=approval_id,
        workflow_execution_id=approval.workflow_execution_id,
        status="approved",
        message="Workflow approved successfully"
    )


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
async def reject_workflow(approval_id: str, request: RejectRequest):
    """
    Reject a workflow execution.
    
    Terminates workflow with feedback.
    """
    service = get_service()
    
    # Verify approval exists
    approval = service.get_approval(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    
    # Reject workflow
    success = service.reject_workflow(
        approval_id=approval_id,
        approver_id=request.approver_id,
        approver_email=request.approver_email,
        feedback=request.feedback
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to reject workflow")
    
    logger.info(f"❌ Rejected workflow {approval.workflow_execution_id}")
    
    return ApprovalResponse(
        approval_id=approval_id,
        workflow_execution_id=approval.workflow_execution_id,
        status="rejected",
        message="Workflow rejected"
    )


@router.post("/{approval_id}/request-changes", response_model=ApprovalResponse)
async def request_changes(approval_id: str, request: RequestChangesRequest):
    """
    Request changes for a workflow execution.
    
    Puts workflow on hold until changes are made.
    """
    service = get_service()
    
    # Verify approval exists
    approval = service.get_approval(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    
    # Request changes
    success = service.request_changes(
        approval_id=approval_id,
        approver_id=request.approver_id,
        approver_email=request.approver_email,
        feedback=request.feedback
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to request changes")
    
    logger.info(f"🔄 Changes requested for workflow {approval.workflow_execution_id}")
    
    return ApprovalResponse(
        approval_id=approval_id,
        workflow_execution_id=approval.workflow_execution_id,
        status="changes_requested",
        message="Changes requested"
    )


@router.post("/check-timeouts")
async def check_timeouts():
    """
    Check for timed out approvals and escalate them.
    
    Background task that can be triggered manually or via scheduler.
    """
    service = get_service()
    
    escalated = service.check_timeouts()
    
    return {
        "message": f"Checked timeouts, escalated {len(escalated)} approvals",
        "escalated_count": len(escalated),
        "escalated_ids": escalated
    }
