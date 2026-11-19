"""
Human-in-the-Loop approval service layer.

Provides business logic for:
- Managing approval requests
- Processing approval decisions
- Tracking approval history
- Handling approval timeouts and escalations

Features:
- Approval CRUD operations
- Approval decision processing
- Pending approval queries
- Timeout and escalation handling
- Comprehensive logging for diagnostics
"""

import logging
import sqlite3
import json
import uuid
from typing import Dict, Any, Optional, List, Literal
from datetime import datetime, timedelta, UTC

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Database path - project root
from app.core.config import Paths, get_settings
from pathlib import Path
DB_PATH = Paths.from_settings(get_settings()).shared_db


class ApprovalRecord(BaseModel):
    """
    Approval record model.
    
    Attributes:
        id: Unique approval request ID
        workflow_execution_id: ID of workflow execution requiring approval
        composition_id: Optional composition ID if part of composition
        template_id: ID of workflow template
        status: Current status (pending, approved, rejected, changes_requested)
        requested_at: When approval was requested
        responded_at: When approval was responded to
        approver_id: ID of approver
        approver_email: Email of approver
        decision: Approval decision
        feedback: Feedback from approver
        timeout_at: When approval times out
        auto_escalate: Whether to auto-escalate on timeout
        metadata: Additional metadata
    """
    id: str
    workflow_execution_id: str
    composition_id: Optional[str] = None
    template_id: str
    status: Literal["pending", "approved", "rejected", "changes_requested"]
    requested_at: str
    responded_at: Optional[str] = None
    approver_id: Optional[str] = None
    approver_email: Optional[str] = None
    decision: Optional[str] = None
    feedback: Optional[str] = None
    timeout_at: Optional[str] = None
    auto_escalate: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ApprovalService:
    """
    Service for managing workflow approvals.
    
    This service handles:
    1. Creating approval requests
    2. Processing approval decisions (approve/reject/request changes)
    3. Querying pending approvals
    4. Handling timeouts and escalations
    5. Tracking approval history
    """
    
    @property
    def db_path(self) -> Path:
        """The shared database, resolved on EVERY read.

        This was a module-level constant captured at import. That cannot follow
        a redirected installation: under test the harness points DATABASE_URL at
        a copy of a migrated DB, and a path bound at import (or in __init__)
        keeps naming the original — producing "no such table" against the wrong
        file. The resolver was always correct; it was just applied too early.
        """
        from app.core.config import Paths, get_settings

        override: Path | None = getattr(self, "_db_path_override", None)
        if override is not None:
            return override
        return Paths.from_settings(get_settings()).shared_db

    @db_path.setter
    def db_path(self, value) -> None:
        """An explicit override — the test seam.

        Kept deliberately: tests point a service at their own database.
        The resolver above is the DEFAULT, not a cage.
        """
        self._db_path_override = value
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    # =========================================================================
    # Approval Request Management
    # =========================================================================
    
    def create_approval_request(
        self,
        workflow_execution_id: str,
        template_id: str,
        composition_id: Optional[str] = None,
        timeout_hours: int = 24,
        auto_escalate: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new approval request.
        
        Args:
            workflow_execution_id: ID of workflow execution
            template_id: ID of workflow template
            composition_id: Optional composition ID
            timeout_hours: Hours until timeout
            auto_escalate: Whether to auto-escalate on timeout
            metadata: Additional metadata
            
        Returns:
            Approval request ID
        """
        approval_id = str(uuid.uuid4())
        timeout_at = datetime.now(UTC) + timedelta(hours=timeout_hours)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                """
                INSERT INTO workflow_approvals (
                    id, workflow_execution_id, template_id, composition_id,
                    status, timeout_at, auto_escalate, metadata, requested_at
                ) VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?)
                """,
                (
                    approval_id,
                    workflow_execution_id,
                    template_id,
                    composition_id,
                    timeout_at.isoformat().replace("+00:00", "Z"),
                    1 if auto_escalate else 0,
                    json.dumps(metadata or {}),
                    datetime.now(UTC).isoformat().replace("+00:00", "Z")
                )
            )
            conn.commit()
            
            logger.info(f"✅ Created approval request: {approval_id} for {workflow_execution_id}")
            return approval_id
            
        except Exception as e:
            logger.error(f"❌ Failed to create approval request: {e}", exc_info=True)
            raise
            
        finally:
            conn.close()
    
    def get_approval(self, approval_id: str) -> Optional[ApprovalRecord]:
        """
        Get approval request by ID.
        
        Args:
            approval_id: ID of approval request
            
        Returns:
            ApprovalRecord or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "SELECT * FROM workflow_approvals WHERE id = ?",
                (approval_id,)
            )
            row = cursor.fetchone()
            
            if row:
                row_dict = dict(row)
                # Parse metadata JSON
                if isinstance(row_dict.get('metadata'), str):
                    row_dict['metadata'] = json.loads(row_dict['metadata'])
                
                logger.info(f"📄 Retrieved approval: {approval_id}")
                return ApprovalRecord.model_validate(row_dict)
            else:
                logger.debug(f"📄 Approval not found: {approval_id}")
                return None
                
        finally:
            conn.close()
    
    def get_approval_by_workflow(self, workflow_execution_id: str) -> Optional[ApprovalRecord]:
        """
        Get approval request by workflow execution ID.
        
        Args:
            workflow_execution_id: ID of workflow execution
            
        Returns:
            ApprovalRecord or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                """
                SELECT * FROM workflow_approvals 
                WHERE workflow_execution_id = ?
                ORDER BY requested_at DESC
                LIMIT 1
                """,
                (workflow_execution_id,)
            )
            row = cursor.fetchone()
            
            if row:
                row_dict = dict(row)
                if isinstance(row_dict.get('metadata'), str):
                    row_dict['metadata'] = json.loads(row_dict['metadata'])
                
                logger.info(f"📄 Retrieved approval for workflow {workflow_execution_id}")
                return ApprovalRecord.model_validate(row_dict)
            else:
                logger.debug(f"📄 No approval found for workflow {workflow_execution_id}")
                return None
                
        finally:
            conn.close()
    
    def list_pending_approvals(
        self,
        composition_id: Optional[str] = None,
        limit: int = 50
    ) -> List[ApprovalRecord]:
        """
        List all pending approvals.
        
        Args:
            composition_id: Optional filter by composition ID
            limit: Maximum number of results
            
        Returns:
            List of ApprovalRecord objects
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            if composition_id:
                cursor.execute(
                    """
                    SELECT * FROM workflow_approvals 
                    WHERE status = 'pending' AND composition_id = ?
                    ORDER BY requested_at ASC
                    LIMIT ?
                    """,
                    (composition_id, limit)
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM workflow_approvals 
                    WHERE status = 'pending'
                    ORDER BY requested_at ASC
                    LIMIT ?
                    """,
                    (limit,)
                )
            
            approvals = []
            for row in cursor.fetchall():
                row_dict = dict(row)
                if isinstance(row_dict.get('metadata'), str):
                    row_dict['metadata'] = json.loads(row_dict['metadata'])
                
                try:
                    approval = ApprovalRecord.model_validate(row_dict)
                    approvals.append(approval)
                except Exception as e:
                    logger.warning(f"⚠️  Invalid approval record {row_dict['id']}: {e}")
            
            logger.info(f"📋 Found {len(approvals)} pending approvals")
            return approvals
            
        finally:
            conn.close()
    
    # =========================================================================
    # Approval Decisions
    # =========================================================================
    
    def approve_workflow(
        self,
        approval_id: str,
        approver_id: Optional[str] = None,
        approver_email: Optional[str] = None,
        feedback: Optional[str] = None
    ) -> bool:
        """
        Approve a workflow execution.
        
        Args:
            approval_id: ID of approval request
            approver_id: ID of approver
            approver_email: Email of approver
            feedback: Optional feedback
            
        Returns:
            True if successful
        """
        return self._update_approval_status(
            approval_id=approval_id,
            decision="approved",
            approver_id=approver_id,
            approver_email=approver_email,
            feedback=feedback
        )
    
    def reject_workflow(
        self,
        approval_id: str,
        approver_id: Optional[str] = None,
        approver_email: Optional[str] = None,
        feedback: Optional[str] = None
    ) -> bool:
        """
        Reject a workflow execution.
        
        Args:
            approval_id: ID of approval request
            approver_id: ID of approver
            approver_email: Email of approver
            feedback: Optional feedback
            
        Returns:
            True if successful
        """
        return self._update_approval_status(
            approval_id=approval_id,
            decision="rejected",
            approver_id=approver_id,
            approver_email=approver_email,
            feedback=feedback
        )
    
    def request_changes(
        self,
        approval_id: str,
        approver_id: Optional[str] = None,
        approver_email: Optional[str] = None,
        feedback: Optional[str] = None
    ) -> bool:
        """
        Request changes for a workflow execution.
        
        Args:
            approval_id: ID of approval request
            approver_id: ID of approver
            approver_email: Email of approver
            feedback: Required feedback describing changes
            
        Returns:
            True if successful
        """
        return self._update_approval_status(
            approval_id=approval_id,
            decision="changes_requested",
            approver_id=approver_id,
            approver_email=approver_email,
            feedback=feedback
        )
    
    def _update_approval_status(
        self,
        approval_id: str,
        decision: Literal["approved", "rejected", "changes_requested"],
        approver_id: Optional[str] = None,
        approver_email: Optional[str] = None,
        feedback: Optional[str] = None
    ) -> bool:
        """
        Update approval status with decision.
        
        Args:
            approval_id: ID of approval request
            decision: Approval decision
            approver_id: ID of approver
            approver_email: Email of approver
            feedback: Optional feedback
            
        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                """
                UPDATE workflow_approvals
                SET 
                    status = ?,
                    decision = ?,
                    approver_id = ?,
                    approver_email = ?,
                    feedback = ?,
                    responded_at = ?
                WHERE id = ?
                """,
                (
                    decision,
                    decision,
                    approver_id,
                    approver_email,
                    feedback,
                    datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                    approval_id
                )
            )
            conn.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"✅ Updated approval {approval_id}: {decision}")
                return True
            else:
                logger.warning(f"⚠️  Approval not found: {approval_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to update approval: {e}", exc_info=True)
            return False
            
        finally:
            conn.close()
    
    # =========================================================================
    # Timeout and Escalation
    # =========================================================================
    
    def check_timeouts(self) -> List[str]:
        """
        Check for timed out approvals and escalate them.
        
        Returns:
            List of approval IDs that were escalated
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Find pending approvals past timeout
            cursor.execute(
                """
                SELECT id, workflow_execution_id FROM workflow_approvals
                WHERE status = 'pending' 
                AND timeout_at IS NOT NULL
                AND timeout_at < ?
                AND auto_escalate = 1
                """,
                (datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),)
            )
            
            timed_out = cursor.fetchall()
            escalated = []
            
            for approval_id, workflow_id in timed_out:
                logger.warning(f"⏰ Approval {approval_id} timed out, escalating...")
                
                # Mark as escalated (you could implement actual escalation logic here)
                cursor.execute(
                    """
                    UPDATE workflow_approvals
                    SET status = 'escalated', feedback = 'Auto-escalated due to timeout'
                    WHERE id = ?
                    """,
                    (approval_id,)
                )
                
                escalated.append(approval_id)
                logger.info(f"✅ Escalated approval: {approval_id}")
            
            conn.commit()
            logger.info(f"📋 Checked timeouts: {len(escalated)} escalated")
            return escalated
            
        except Exception as e:
            logger.error(f"❌ Failed to check timeouts: {e}", exc_info=True)
            return []
            
        finally:
            conn.close()
