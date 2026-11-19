"""
The workflow-composition schemas — references, mappings, conditions, and their validation.

Validates WorkflowComposition, WorkflowReference, and CompositionService behavior.
"""

import pytest
import uuid

from pydantic import ValidationError

from app.domain.workflows.schemas.composition_config import (
    WorkflowComposition,
    WorkflowReference,
    CompositionExecutionResult,
)
from app.domain.workflows.services.composition_service import CompositionService

# The CompositionService writes to the project DB by default — the
# CRUD tests previously polluted the LIVE database with ~1650
# test-comp-* rows (known issue: test pollution of the live data
# store). Each service-fixture now uses a throwaway DB file and
# creates the table it needs (the columns the model declares).
import sqlite3
from pathlib import Path


def _make_test_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test_compositions.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_compositions (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            config_json TEXT NOT NULL,
            version TEXT NOT NULL DEFAULT '1.0.0',
            tags TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()
    return db_path


class TestWorkflowReference:
    """Test WorkflowReference schema validation."""

    def test_workflow_reference_minimal(self):
        """Test WorkflowReference with minimal required fields."""
        ref = WorkflowReference(
            workflow_id="parallel-research-analysis",
            order=1,
        )

        assert ref.workflow_id == "parallel-research-analysis"
        assert ref.order == 1
        assert ref.input_mapping == {}
        assert ref.output_mapping == {}
        assert ref.condition is None

    def test_workflow_reference_with_mappings(self):
        """Test WorkflowReference with input/output mappings."""
        ref = WorkflowReference(
            workflow_id="creative-review",
            order=2,
            input_mapping={"user_input": "final_output"},
            output_mapping={"reviewed_content": "final_output"},
        )

        assert ref.input_mapping == {"user_input": "final_output"}
        assert ref.output_mapping == {"reviewed_content": "final_output"}

    def test_workflow_reference_with_condition(self):
        """Test WorkflowReference with conditional execution."""
        ref = WorkflowReference(
            workflow_id="publish-workflow",
            order=3,
            condition={"field": "quality_score", "operator": "gte", "value": 0.8},
        )

        assert ref.condition == {"field": "quality_score", "operator": "gte", "value": 0.8}

    def test_workflow_reference_invalid_order(self):
        """Test that order must be >= 1."""
        with pytest.raises(ValidationError) as exc_info:
            WorkflowReference(
                workflow_id="test",
                order=0,
            )

        assert "greater than or equal to 1" in str(exc_info.value)


class TestWorkflowComposition:
    """Test WorkflowComposition schema validation."""

    def test_workflow_composition_minimal(self):
        """Test WorkflowComposition with minimal required fields."""
        comp = WorkflowComposition(
            id="test-composition",
            name="Test Composition",
            workflows=[
                WorkflowReference(workflow_id="workflow-1", order=1),
                WorkflowReference(workflow_id="workflow-2", order=2),
            ],
        )

        assert comp.id == "test-composition"
        assert comp.name == "Test Composition"
        assert len(comp.workflows) == 2
        assert comp.tags == []
        assert comp.version == "1.0"

    def test_workflow_composition_with_tags(self):
        """Test WorkflowComposition with tags."""
        comp = WorkflowComposition(
            id="content-pipeline",
            name="Content Pipeline",
            workflows=[
                WorkflowReference(workflow_id="research", order=1),
                WorkflowReference(workflow_id="review", order=2),
            ],
            tags=["content", "research"],
        )

        assert comp.tags == ["content", "research"]

    def test_workflow_composition_duplicate_orders(self):
        """Test that workflow orders must be unique."""
        with pytest.raises(ValidationError) as exc_info:
            WorkflowComposition(
                id="test",
                name="Test",
                workflows=[
                    WorkflowReference(workflow_id="wf1", order=1),
                    WorkflowReference(workflow_id="wf2", order=1),  # Duplicate
                ],
            )

        assert "unique" in str(exc_info.value).lower()

    def test_workflow_composition_non_sequential_orders(self):
        """Test that workflow orders must be sequential."""
        with pytest.raises(ValidationError) as exc_info:
            WorkflowComposition(
                id="test",
                name="Test",
                workflows=[
                    WorkflowReference(workflow_id="wf1", order=1),
                    WorkflowReference(workflow_id="wf2", order=3),  # Skip 2
                ],
            )

        assert "sequential" in str(exc_info.value).lower()

    def test_workflow_composition_input_mapping_validation(self):
        """Test that input mappings reference available outputs."""
        # This should fail - referencing non-existent output
        with pytest.raises(ValidationError) as exc_info:
            WorkflowComposition(
                id="test",
                name="Test",
                workflows=[
                    WorkflowReference(
                        workflow_id="wf1",
                        order=1,
                        input_mapping={"user_input": "non_existent"},
                    ),
                    WorkflowReference(workflow_id="wf2", order=2),
                ],
            )

        assert "unavailable output" in str(exc_info.value)

    def test_workflow_composition_chained_mapping(self):
        """Test valid chained input/output mappings."""
        # This should succeed - proper chaining
        comp = WorkflowComposition(
            id="chained-pipeline",
            name="Chained Pipeline",
            workflows=[
                WorkflowReference(
                    workflow_id="wf1",
                    order=1,
                    input_mapping={"user_input": "initial_input"},
                    output_mapping={"output1": "final_output"},
                ),
                WorkflowReference(
                    workflow_id="wf2",
                    order=2,
                    input_mapping={"user_input": "final_output"},
                ),
            ],
        )

        assert len(comp.workflows) == 2
        assert comp.workflows[0].output_mapping == {"output1": "final_output"}


class TestCompositionService:
    """Test CompositionService CRUD operations."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create composition service on a throwaway DB (no live
        pollution — see the known-issues record)."""
        svc = CompositionService()
        svc.db_path = _make_test_db(tmp_path)
        return svc

    def test_create_composition(self, service):
        """Test creating a composition."""
        import uuid
        test_id = f"test-comp-create-{uuid.uuid4().hex[:8]}"
        
        comp = WorkflowComposition(
            id=test_id,
            name=f"Test Composition {test_id}",
            description="Test description",
            workflows=[
                WorkflowReference(workflow_id="wf1", order=1),
                WorkflowReference(workflow_id="wf2", order=2),
            ],
            tags=["test"],
        )

        success = service.create_composition(comp)
        assert success is True

        # Verify it was created
        retrieved = service.get_composition(test_id)
        assert retrieved is not None
        assert retrieved.name == f"Test Composition {test_id}"

    def test_get_nonexistent_composition(self, service):
        """Test getting a composition that doesn't exist."""
        result = service.get_composition("nonexistent-id")
        assert result is None

    def test_list_compositions(self, service):
        """Test listing compositions."""
        # Create test compositions with unique IDs to avoid conflicts
        test_id1 = f"test-comp-list-1-{uuid.uuid4().hex[:8]}"
        test_id2 = f"test-comp-list-2-{uuid.uuid4().hex[:8]}"
        
        comp1 = WorkflowComposition(
            id=test_id1,
            name="Test Composition List 1",
            workflows=[
                WorkflowReference(workflow_id="wf1", order=1),
                WorkflowReference(workflow_id="wf2", order=2),
            ],
        )
        comp2 = WorkflowComposition(
            id=test_id2,
            name="Test Composition List 2",
            workflows=[
                WorkflowReference(workflow_id="wf1", order=1),
                WorkflowReference(workflow_id="wf3", order=2),
            ],
        )

        service.create_composition(comp1)
        service.create_composition(comp2)

        # List compositions
        compositions = service.list_compositions(active_only=True)

        # Should include our test compositions
        test_comps = [c for c in compositions if c.id.startswith("test-comp-list-")]
        assert len(test_comps) >= 2

        # Cleanup
        for comp in test_comps:
            service.delete_composition(comp.id)

    def test_update_composition(self, service):
        """Test updating a composition."""
        import uuid
        test_id = f"test-comp-update-{uuid.uuid4().hex[:8]}"
        
        # Create composition with unique ID
        comp = WorkflowComposition(
            id=test_id,
            name="Test Pipeline Update",
            workflows=[
                WorkflowReference(workflow_id="wf1", order=1),
                WorkflowReference(workflow_id="wf2", order=2),
            ],
        )
        service.create_composition(comp)

        # Update
        success = service.update_composition(test_id, {
            "name": "Updated Pipeline",
            "description": "Updated description",
        })
        assert success is True

        # Verify update
        updated = service.get_composition(test_id)
        assert updated is not None
        assert updated.name == "Updated Pipeline"
        assert updated.description == "Updated description"

    def test_delete_composition(self, service):
        """Test soft deleting a composition."""
        import uuid
        test_id = f"test-comp-delete-{uuid.uuid4().hex[:8]}"
        
        # Create composition with unique ID
        comp = WorkflowComposition(
            id=test_id,
            name="To Delete",
            workflows=[
                WorkflowReference(workflow_id="wf1", order=1),
                WorkflowReference(workflow_id="wf2", order=2),
            ],
        )
        service.create_composition(comp)

        # Delete
        success = service.delete_composition(test_id)
        assert success is True

        # Should not appear in active list
        compositions = service.list_compositions(active_only=True)
        deleted = [c for c in compositions if c.id == test_id]
        assert len(deleted) == 0


class TestCompositionExecutionResult:
    """Test CompositionExecutionResult schema."""

    def test_execution_result_completed(self):
        """Test result for completed execution."""
        result = CompositionExecutionResult(
            composition_id="test-comp",
            status="completed",
            outputs={"final_output": "result"},
            workflow_results=[
                {"workflow_id": "wf1", "status": "completed"},
            ],
            started_at="2026-03-30T12:00:00Z",
            completed_at="2026-03-30T12:05:00Z",
            elapsed_seconds=300.0,
        )

        assert result.status == "completed"
        assert result.elapsed_seconds == 300.0

    def test_execution_result_error(self):
        """Test result for failed execution."""
        result = CompositionExecutionResult(
            composition_id="test-comp",
            status="error",
            error="Workflow not found",
            started_at="2026-03-30T12:00:00Z",
        )

        assert result.status == "error"
        assert result.error == "Workflow not found"
        assert result.completed_at is None
