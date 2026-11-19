"""
Workflow composition configuration schemas.

Pydantic schemas for defining and validating workflow compositions,
enabling chaining of multiple workflow templates together.
"""

import logging
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal, List, Optional, Dict, Any

logger = logging.getLogger(__name__)


class WorkflowReference(BaseModel):
    """
    Reference to a workflow template within a composition.

    Attributes:
        workflow_id: ID of the workflow template to execute
        order: Execution order in the composition (1, 2, 3...)
        input_mapping: Mapping from previous workflow outputs to this workflow's inputs
            - Keys: Input keys expected by this workflow
            - Values: Output keys from previous workflows
        output_mapping: Mapping from this workflow's outputs to composition outputs
            - Keys: Composition-level output keys
            - Values: This workflow's output keys
        condition: Optional condition for executing this workflow
            - If provided, workflow only executes if condition is met
            - Condition references previous workflow outputs
    """
    workflow_id: str = Field(
        ...,
        description="ID of workflow template to execute",
        examples=["parallel-research-analysis", "creative-review"]
    )
    order: int = Field(
        ...,
        ge=1,
        description="Execution order in composition (1, 2, 3...)"
    )
    input_mapping: Dict[str, str] = Field(
        default_factory=dict,
        description="Map workflow inputs to previous outputs (input_key: previous_output_key)",
        examples=[{"user_input": "final_report"}]
    )
    output_mapping: Dict[str, str] = Field(
        default_factory=dict,
        description="Map workflow outputs to composition outputs (composition_key: workflow_output_key)",
        examples=[{"research": "raw_data", "review_summary": "final_output"}]
    )
    condition: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional condition for conditional execution",
        examples=[{"field": "quality_score", "operator": "gte", "value": 0.8}]
    )

    model_config = ConfigDict(json_schema_extra={ "example": { "workflow_id": "parallel-research-analysis", "order": 1, "input_mapping": {"user_input": "initial_query"}, "output_mapping": {"research_output": "final_output"} } })


class WorkflowComposition(BaseModel):
    """
    Workflow composition configuration.

    Enables chaining multiple workflow templates together with
    input/output mapping between them.

    Attributes:
        id: Unique identifier for this composition
        name: Human-readable name
        description: Detailed description of the composition
        workflows: Ordered list of workflow references
        initial_input_mapping: Mapping from initial input to first workflow's inputs
            - Keys: First workflow's input keys
            - Values: "initial_input" (special key for user-provided input)
        final_output_key: Key for final composition output (default: "composition_output")
        config: Additional composition configuration
        tags: Optional tags for categorization
        version: Schema version for future compatibility
    """
    id: str = Field(
        ...,
        description="Unique identifier for this composition",
        examples=["content-pipeline", "code-review-pipeline"]
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Human-readable name",
        examples=["Content Production Pipeline", "Code Review Workflow"]
    )
    description: str = Field(
        default="",
        description="Detailed description of the composition",
        examples=["Research topic, review content, and publish final output"]
    )
    workflows: List[WorkflowReference] = Field(
        ...,
        min_length=2,
        description="Ordered list of workflow references (minimum 2 workflows)"
    )
    initial_input_mapping: Dict[str, str] = Field(
        default_factory=dict,
        description="Map initial input to first workflow inputs",
        examples=[{"user_input": "initial_query"}]
    )
    final_output_key: str = Field(
        default="composition_output",
        description="Key for final composition output"
    )
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional composition configuration"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorization",
        examples=["content", "research", "production"]
    )
    version: str = Field(
        default="1.0",
        description="Schema version for compatibility tracking"
    )

    @field_validator('workflows')
    @classmethod
    def validate_workflow_orders(cls, v):
        """Validate that workflow orders are sequential and unique."""
        if not v:
            return v

        orders = [w.order for w in v]
        
        # Check for duplicates
        if len(orders) != len(set(orders)):
            raise ValueError("Workflow orders must be unique")
        
        # Check for sequential ordering (1, 2, 3...)
        sorted_orders = sorted(orders)
        expected = list(range(1, len(orders) + 1))
        if sorted_orders != expected:
            raise ValueError(f"Workflow orders must be sequential starting from 1, got {sorted_orders}")

        return v

    @field_validator('workflows')
    @classmethod
    def validate_input_mappings(cls, v):
        """Validate that input mappings reference available outputs."""
        if not v:
            return v

        # Collect all available outputs from previous workflows
        available_outputs = {"initial_input"}  # Special key for user input
        
        errors = []
        for i, workflow in enumerate(v):
            # Check input mappings reference available outputs
            for input_key, source_output in workflow.input_mapping.items():
                if source_output not in available_outputs:
                    errors.append(
                        f"Workflow {i+1} ({workflow.workflow_id}) input '{input_key}' "
                        f"references unavailable output '{source_output}'. "
                        f"Available: {available_outputs}"
                    )
            
            # Add this workflow's potential outputs (for next workflows)
            # A workflow can output to any key, but we track mapped outputs
            for comp_key, wf_output in workflow.output_mapping.items():
                available_outputs.add(wf_output)
            
            # Also add common output keys
            available_outputs.add("final_output")
            available_outputs.add("composition_output")

        if errors:
            raise ValueError("; ".join(errors))

        return v

    model_config = ConfigDict(json_schema_extra={ "example": { "id": "content-pipeline", "name": "Content Production Pipeline", "description": "Research topic, review content, and publish", "workflows": [ { "workflow_id": "parallel-research-analysis", "order": 1, "input_mapping": {"user_input": "initial_query"}, "output_mapping": {"research_output": "final_output"} }, { "workflow_id": "creative-review", "order": 2, "input_mapping": {"user_input": "research_output"}, "output_mapping": {"reviewed_content": "final_output"} } ], "initial_input_mapping": {"user_input": "initial_query"}, "tags": ["content", "research"] } })


class CompositionExecutionResult(BaseModel):
    """
    Result of executing a workflow composition.

    Attributes:
        composition_id: ID of the executed composition
        status: Execution status (completed, error, cancelled, pending_approval)
        outputs: Final outputs from the composition
        workflow_results: Results from each individual workflow
        error: Error message if status is 'error'
        started_at: ISO timestamp when execution started
        completed_at: ISO timestamp when execution completed
        elapsed_seconds: Total execution time in seconds
    """
    composition_id: str = Field(..., description="ID of executed composition")
    status: Literal["completed", "error", "cancelled", "pending_approval"] = Field(
        ...,
        description="Execution status"
    )
    outputs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Final outputs from composition"
    )
    workflow_results: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Results from each workflow execution"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if status is 'error'"
    )
    started_at: str = Field(..., description="ISO timestamp when started")
    completed_at: Optional[str] = Field(
        default=None,
        description="ISO timestamp when completed"
    )
    elapsed_seconds: float = Field(
        default=0.0,
        description="Total execution time in seconds"
    )

    model_config = ConfigDict(json_schema_extra={ "example": { "composition_id": "content-pipeline", "status": "completed", "outputs": {"reviewed_content": "Final article about AI..."}, "workflow_results": [ {"workflow_id": "parallel-research-analysis", "status": "completed"}, {"workflow_id": "creative-review", "status": "completed"} ], "started_at": "2026-03-30T12:00:00Z", "completed_at": "2026-03-30T12:05:30Z", "elapsed_seconds": 330.0 } })
