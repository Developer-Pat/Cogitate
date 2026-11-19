"""
The human-in-the-loop approval workflow — the request lifecycle and its transitions.

Validates ApprovalService, approval nodes, and API endpoints.
"""

import pytest
import sqlite3
from datetime import datetime, timedelta, UTC

from app.domain.workflows.services.approval_service import ApprovalService, ApprovalRecord

# Database path for tests - project root
from app.core.config import Paths, get_settings

# THE ONE-RESOLVER DOCTRINE: the shared-db path comes from the app's `Paths`,
# never a literal or a parent-walk. Reaching `cogitate.db` directly meant these
# tests wrote to the PRODUCTION database, and passed only because the code under
# test read the same production file. Under test, `Paths` resolves to the
# temporary copy — so test and code agree on the same database.
DB_PATH = str(Paths.from_settings(get_settings()).shared_db)


class TestApprovalService:
    """Test ApprovalService CRUD operations."""

    @pytest.fixture
    def service(self):
        """Create approval service instance."""
        return ApprovalService()

    @pytest.fixture(autouse=True)
    def cleanup(self, service):
        """Clean up test approvals after each test."""
        yield
        # Clean up test approvals
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM workflow_approvals WHERE workflow_execution_id LIKE ?",
                ("test-workflow-%",)
            )
            conn.commit()
        finally:
            conn.close()

    def test_create_approval_request(self, service):
        """Test creating an approval request."""
        approval_id = service.create_approval_request(
            workflow_execution_id="test-workflow-001",
            template_id="test-template",
            timeout_hours=24,
            metadata={"test": "data"},
        )

        assert approval_id is not None
        assert len(approval_id) > 0

        # Verify it was created
        approval = service.get_approval(approval_id)
        assert approval is not None
        assert approval.workflow_execution_id == "test-workflow-001"
        assert approval.status == "pending"

    def test_get_approval_by_workflow(self, service):
        """Test getting approval by workflow execution ID."""
        # Create approval
        approval_id = service.create_approval_request(
            workflow_execution_id="test-workflow-002",
            template_id="test-template",
        )

        # Get by workflow ID
        approval = service.get_approval_by_workflow("test-workflow-002")
        assert approval is not None
        assert approval.id == approval_id

    def test_approve_workflow(self, service):
        """Test approving a workflow."""
        # Create approval
        approval_id = service.create_approval_request(
            workflow_execution_id="test-workflow-003",
            template_id="test-template",
        )

        # Approve
        success = service.approve_workflow(
            approval_id=approval_id,
            approver_id="user-123",
            approver_email="approver@example.com",
            feedback="Looks good!",
        )
        assert success is True

        # Verify approval status
        approval = service.get_approval(approval_id)
        assert approval.status == "approved"
        assert approval.decision == "approved"
        assert approval.approver_id == "user-123"
        assert approval.feedback == "Looks good!"

    def test_reject_workflow(self, service):
        """Test rejecting a workflow."""
        # Create approval
        approval_id = service.create_approval_request(
            workflow_execution_id="test-workflow-004",
            template_id="test-template",
        )

        # Reject
        success = service.reject_workflow(
            approval_id=approval_id,
            approver_id="user-456",
            feedback="Needs more work",
        )
        assert success is True

        # Verify rejection
        approval = service.get_approval(approval_id)
        assert approval.status == "rejected"
        assert approval.decision == "rejected"
        assert approval.feedback == "Needs more work"

    def test_request_changes(self, service):
        """Test requesting changes for a workflow."""
        # Create approval
        approval_id = service.create_approval_request(
            workflow_execution_id="test-workflow-005",
            template_id="test-template",
        )

        # Request changes
        success = service.request_changes(
            approval_id=approval_id,
            approver_id="user-789",
            feedback="Please revise section 2",
        )
        assert success is True

        # Verify status
        approval = service.get_approval(approval_id)
        assert approval.status == "changes_requested"
        assert approval.decision == "changes_requested"

    def test_list_pending_approvals(self, service):
        """Test listing pending approvals."""
        # Create multiple approvals
        service.create_approval_request(
            workflow_execution_id="test-workflow-006",
            template_id="test-template",
        )
        service.create_approval_request(
            workflow_execution_id="test-workflow-007",
            template_id="test-template",
        )

        # Approve one
        approvals = service.list_pending_approvals()
        if len(approvals) >= 2:
            service.approve_workflow(approvals[0].id, approver_id="test-user")

        # List pending
        pending = service.list_pending_approvals()
        
        # Should not include approved ones
        for approval in pending:
            assert approval.status == "pending"

    def test_list_pending_approvals_by_composition(self, service):
        """Test listing pending approvals filtered by composition."""
        # Create approvals with composition IDs
        service.create_approval_request(
            workflow_execution_id="test-workflow-008",
            template_id="test-template",
            composition_id="test-composition-1",
        )
        service.create_approval_request(
            workflow_execution_id="test-workflow-009",
            template_id="test-template",
            composition_id="test-composition-2",
        )

        # Filter by composition
        pending = service.list_pending_approvals(composition_id="test-composition-1")
        
        # Should only include matching composition
        for approval in pending:
            assert approval.composition_id == "test-composition-1"

    def test_get_nonexistent_approval(self, service):
        """Test getting an approval that doesn't exist."""
        result = service.get_approval("nonexistent-id")
        assert result is None

    def test_approval_with_timeout(self, service):
        """Test approval request with timeout."""
        approval_id = service.create_approval_request(
            workflow_execution_id="test-workflow-010",
            template_id="test-template",
            timeout_hours=1,
        )

        approval = service.get_approval(approval_id)
        assert approval.timeout_at is not None
        
        # Verify timeout is approximately 1 hour from now
        timeout = datetime.fromisoformat(approval.timeout_at.replace("Z", "+00:00"))
        now = datetime.now(UTC)
        diff = (timeout - now).total_seconds()
        assert 3500 < diff < 3700  # Within 10 minutes of 1 hour

    def test_approval_metadata(self, service):
        """Test approval with metadata."""
        metadata = {
            "workflow_name": "Test Workflow",
            "user_id": "user-123",
            "priority": "high",
        }

        approval_id = service.create_approval_request(
            workflow_execution_id="test-workflow-011",
            template_id="test-template",
            metadata=metadata,
        )

        approval = service.get_approval(approval_id)
        assert approval.metadata == metadata


class TestApprovalRecord:
    """Test ApprovalRecord schema validation."""

    def test_approval_record_minimal(self):
        """Test ApprovalRecord with minimal fields."""
        record = ApprovalRecord(
            id="test-approval-1",
            workflow_execution_id="wf-123",
            template_id="tpl-456",
            status="pending",
            requested_at="2026-03-30T12:00:00Z",
        )

        assert record.id == "test-approval-1"
        assert record.status == "pending"
        assert record.auto_escalate is False
        assert record.metadata == {}

    def test_approval_record_full(self):
        """Test ApprovalRecord with all fields."""
        record = ApprovalRecord(
            id="test-approval-2",
            workflow_execution_id="wf-123",
            composition_id="comp-789",
            template_id="tpl-456",
            status="approved",
            requested_at="2026-03-30T12:00:00Z",
            responded_at="2026-03-30T14:00:00Z",
            approver_id="user-123",
            approver_email="user@example.com",
            decision="approved",
            feedback="Looks good!",
            timeout_at="2026-03-31T12:00:00Z",
            auto_escalate=True,
            metadata={"priority": "high"},
        )

        assert record.composition_id == "comp-789"
        assert record.approver_email == "user@example.com"
        assert record.auto_escalate is True

    def test_approval_record_status_values(self):
        """Test valid approval status values."""
        valid_statuses = ["pending", "approved", "rejected", "changes_requested"]
        
        for status in valid_statuses:
            record = ApprovalRecord(
                id=f"test-{status}",
                workflow_execution_id="wf-123",
                template_id="tpl-456",
                status=status,
                requested_at="2026-03-30T12:00:00Z",
            )
            assert record.status == status


class TestApprovalTimeout:
    """Test approval timeout and escalation."""

    @pytest.fixture
    def service(self):
        """Create approval service instance."""
        return ApprovalService()

    @pytest.fixture(autouse=True)
    def cleanup(self, service):
        """Clean up test approvals after each test."""
        yield
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM workflow_approvals WHERE workflow_execution_id LIKE ?",
                ("test-timeout-%",)
            )
            conn.commit()
        finally:
            conn.close()

    def test_check_timeouts_no_timeouts(self, service):
        """Test checking timeouts when none have expired."""
        # Create approval that expires in the future
        service.create_approval_request(
            workflow_execution_id="test-timeout-001",
            template_id="test-template",
            timeout_hours=24,
            auto_escalate=True,
        )

        # Check timeouts
        escalated = service.check_timeouts()
        
        # Should not escalate anything
        assert len(escalated) == 0

    def test_check_timeouts_with_expired(self, service):
        """Test checking timeouts with expired approvals."""
        import uuid
        test_id = f"manual-expired-{uuid.uuid4().hex[:8]}"
        
        # Manually create an expired approval
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            past_timeout = (datetime.now(UTC) - timedelta(hours=2)).isoformat() + "Z"
            cursor.execute(
                """
                INSERT INTO workflow_approvals
                (id, workflow_execution_id, template_id, status, timeout_at, auto_escalate, requested_at)
                VALUES (?, ?, ?, 'pending', ?, 1, ?)
                """,
                (
                    test_id,
                    f"test-timeout-{uuid.uuid4().hex[:8]}",
                    "test-template",
                    past_timeout,
                    datetime.now(UTC).isoformat() + "Z",
                )
            )
            conn.commit()
        finally:
            conn.close()

        # Check timeouts
        escalated = service.check_timeouts()

        # Should escalate expired approval
        assert test_id in escalated
        
        # Clean up manually inserted record
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM workflow_approvals WHERE id = ?", (test_id,))
            conn.commit()
        finally:
            conn.close()
