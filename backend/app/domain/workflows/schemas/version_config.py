"""
Workflow version configuration schemas.

Pydantic schemas for defining and validating workflow versions,
enabling version management, comparison, and A/B testing.
"""

import logging
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class WorkflowVersion(BaseModel):
    """
    Workflow version configuration.

    Enables tracking and managing different versions of workflow templates,
    supporting versioned execution and A/B testing.

    Attributes:
        id: Unique identifier for this version record
        template_id: ID of the workflow template
        version: Version string (e.g., 'v1.0', 'v1.1', 'v2.0')
        config: Workflow configuration for this version
        changelog: Description of changes in this version
        is_active: Whether this version is currently active
        created_by: Optional user/service identifier
    """
    id: str = Field(
        ...,
        description="Unique identifier for this version record",
        examples=["version-123", "v1.0-content-pipeline"]
    )
    template_id: str = Field(
        ...,
        description="ID of the workflow template",
        examples=["content-pipeline", "daily-briefing"]
    )
    version: str = Field(
        ...,
        description="Version string (semver-style)",
        examples=["v1.0", "v1.1", "v2.0"]
    )
    config: Dict[str, Any] = Field(
        ...,
        description="Workflow configuration for this version"
    )
    changelog: Optional[str] = Field(
        None,
        description="Description of changes in this version"
    )
    is_active: bool = Field(
        default=True,
        description="Whether this version is currently active"
    )
    created_by: Optional[str] = Field(
        None,
        description="User/service identifier who created this version",
        max_length=100
    )

    @field_validator('version')
    @classmethod
    def validate_version_format(cls, v):
        """Validate version string format."""
        if not v.startswith('v'):
            raise ValueError("Version must start with 'v' (e.g., 'v1.0', 'v2.1')")
        if len(v) < 3:
            raise ValueError("Version must have format 'vX.Y' or 'vX.Y.Z'")
        return v

    model_config = ConfigDict(json_schema_extra={ "example": { "id": "version-123", "template_id": "content-pipeline", "version": "v2.0", "config": { "parallel": True, "max_retries": 3, "timeout_ms": 30000 }, "changelog": "Added parallel execution support", "is_active": True, "created_by": "admin" } })


class VersionCreate(BaseModel):
    """
    Request to create a new workflow version.

    Attributes:
        version: Version string (e.g., 'v1.0', 'v1.1', 'v2.0')
        config: Workflow configuration for this version
        changelog: Description of changes in this version
        created_by: Optional user/service identifier
    """
    version: str = Field(
        ...,
        description="Version string (semver-style)",
        examples=["v1.0", "v1.1", "v2.0"]
    )
    config: Dict[str, Any] = Field(
        ...,
        description="Workflow configuration for this version"
    )
    changelog: str = Field(
        ...,
        description="Description of changes in this version",
        min_length=1,
        max_length=2000
    )
    created_by: Optional[str] = Field(
        None,
        description="User/service identifier who created this version",
        max_length=100
    )

    @field_validator('version')
    @classmethod
    def validate_version_format(cls, v):
        """Validate version string format."""
        if not v.startswith('v'):
            raise ValueError("Version must start with 'v' (e.g., 'v1.0', 'v2.1')")
        if len(v) < 3:
            raise ValueError("Version must have format 'vX.Y' or 'vX.Y.Z'")
        return v

    model_config = ConfigDict(json_schema_extra={ "example": { "version": "v2.0", "config": { "parallel": True, "max_retries": 3, "timeout_ms": 30000 }, "changelog": "Added parallel execution support", "created_by": "admin" } })


class VersionUpdate(BaseModel):
    """
    Request to update an existing workflow version.

    All fields are optional for partial updates.
    """
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Workflow configuration for this version"
    )
    changelog: Optional[str] = Field(
        None,
        description="Description of changes in this version"
    )
    is_active: Optional[bool] = Field(
        None,
        description="Whether this version is currently active"
    )

    model_config = ConfigDict(json_schema_extra={ "example": { "config": { "parallel": True, "max_retries": 5 }, "changelog": "Updated retry limit", "is_active": True } })


class VersionCompare(BaseModel):
    """
    Request to compare two workflow versions.

    Attributes:
        v1: First version to compare
        v2: Second version to compare
        metrics: List of metrics to compare (optional)
    """
    v1: str = Field(
        ...,
        description="First version to compare",
        examples=["v1.0", "v1.1"]
    )
    v2: str = Field(
        ...,
        description="Second version to compare",
        examples=["v1.1", "v2.0"]
    )
    metrics: Optional[List[str]] = Field(
        None,
        description="List of metrics to compare",
        examples=[["execution_time", "tokens", "success_rate"]]
    )

    @field_validator('v1', 'v2')
    @classmethod
    def validate_version_format(cls, v):
        """Validate version string format."""
        if not v.startswith('v'):
            raise ValueError("Version must start with 'v' (e.g., 'v1.0', 'v2.1')")
        return v

    model_config = ConfigDict(json_schema_extra={ "example": { "v1": "v1.0", "v2": "v2.0", "metrics": ["execution_time", "tokens", "success_rate"] } })


class VersionResponse(BaseModel):
    """
    Response containing workflow version information.
    """
    id: str
    template_id: str
    version: str
    config: Dict[str, Any]
    changelog: Optional[str]
    is_active: bool
    created_by: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, json_schema_extra={ "example": { "id": "version-123", "template_id": "content-pipeline", "version": "v2.0", "config": { "parallel": True, "max_retries": 3 }, "changelog": "Added parallel execution support", "is_active": True, "created_by": "admin", "created_at": "2026-03-30T10:00:00Z" } })


class VersionListResponse(BaseModel):
    """
    Response containing a list of workflow versions.
    """
    versions: List[VersionResponse]
    total: int = Field(..., description="Total number of versions")

    model_config = ConfigDict(json_schema_extra={ "example": { "versions": [ { "id": "version-123", "template_id": "content-pipeline", "version": "v2.0", "config": {"parallel": True}, "changelog": "Added parallel execution", "is_active": True, "created_by": "admin", "created_at": "2026-03-30T10:00:00Z" }, { "id": "version-122", "template_id": "content-pipeline", "version": "v1.0", "config": {"parallel": False}, "changelog": "Initial version", "is_active": False, "created_by": "admin", "created_at": "2026-03-29T10:00:00Z" } ], "total": 2 } })


class VersionComparisonResult(BaseModel):
    """
    Result of comparing two workflow versions.

    Attributes:
        template_id: Workflow template ID
        v1: First version information
        v2: Second version information
        recommendation: Suggested version based on metrics
    """
    template_id: str
    v1: Dict[str, Any] = Field(..., description="Version 1 metrics")
    v2: Dict[str, Any] = Field(..., description="Version 2 metrics")
    recommendation: Optional[str] = Field(
        None,
        description="Suggested version based on metrics"
    )

    model_config = ConfigDict(json_schema_extra={ "example": { "template_id": "content-pipeline", "v1": { "version": "v1.0", "avg_execution_time_ms": 2500, "avg_tokens_used": 3000, "success_rate": 0.95, "total_executions": 100 }, "v2": { "version": "v2.0", "avg_execution_time_ms": 1800, "avg_tokens_used": 2800, "success_rate": 0.97, "total_executions": 50 }, "recommendation": "v2.0" } })


# ===========================================================================
# A/B Testing Schemas
# ===========================================================================

class ABTestConfig(BaseModel):
    """
    A/B test configuration.

    Enables comparing multiple workflow versions by splitting
    traffic between them and collecting performance metrics.

    Attributes:
        id: Unique identifier for this A/B test
        template_id: ID of the workflow template
        name: Human-readable name for the test
        description: Detailed description
        versions: List of version IDs to test
        traffic_split: Mapping of version -> traffic percentage
        metrics: List of metrics to track
        is_active: Whether the test is currently running
    """
    id: str = Field(
        ...,
        description="Unique identifier for this A/B test",
        examples=["ab-test-123", "parallel-vs-sequential"]
    )
    template_id: str = Field(
        ...,
        description="ID of the workflow template",
        examples=["content-pipeline", "daily-briefing"]
    )
    name: str = Field(
        ...,
        description="Human-readable name for the test",
        min_length=1,
        max_length=200,
        examples=["Parallel vs Sequential", "v1.0 vs v2.0"]
    )
    description: Optional[str] = Field(
        None,
        description="Detailed description"
    )
    versions: List[str] = Field(
        ...,
        description="List of version IDs to test",
        min_length=2,
        examples=[["v1.0", "v2.0"]]
    )
    traffic_split: Dict[str, float] = Field(
        ...,
        description="Mapping of version -> traffic percentage (must sum to 100)"
    )
    metrics: Optional[List[str]] = Field(
        None,
        description="List of metrics to track",
        examples=[["execution_time", "tokens", "success_rate"]]
    )
    is_active: bool = Field(
        default=True,
        description="Whether the test is currently running"
    )

    @field_validator('traffic_split')
    @classmethod
    def validate_traffic_split(cls, v, info):
        """Validate traffic split percentages sum to 100."""
        if not v:
            raise ValueError("Traffic split cannot be empty")
        total = sum(v.values())
        if abs(total - 100.0) > 0.01:
            raise ValueError(f"Traffic split must sum to 100, got {total}")
        return v

    model_config = ConfigDict(json_schema_extra={ "example": { "id": "parallel-vs-sequential", "template_id": "content-pipeline", "name": "Parallel vs Sequential Execution", "description": "Compare parallel execution (v2.0) vs sequential (v1.0)", "versions": ["v1.0", "v2.0"], "traffic_split": {"v1.0": 50.0, "v2.0": 50.0}, "metrics": ["execution_time", "tokens", "success_rate"], "is_active": True } })


class ABTestCreate(BaseModel):
    """
    Request to create a new A/B test.

    Same as ABTestConfig but without defaults.
    """
    id: str = Field(..., description="Unique identifier for this A/B test")
    template_id: str = Field(..., description="ID of the workflow template")
    name: str = Field(..., description="Human-readable name for the test")
    description: Optional[str] = Field(None, description="Detailed description")
    versions: List[str] = Field(..., description="List of version IDs to test")
    traffic_split: Dict[str, float] = Field(..., description="Traffic percentage mapping")
    metrics: Optional[List[str]] = Field(None, description="Metrics to track")
    is_active: bool = Field(default=True, description="Whether the test is active")

    @field_validator('traffic_split')
    @classmethod
    def validate_traffic_split(cls, v):
        """Validate traffic split percentages sum to 100."""
        if not v:
            raise ValueError("Traffic split cannot be empty")
        total = sum(v.values())
        if abs(total - 100.0) > 0.01:
            raise ValueError(f"Traffic split must sum to 100, got {total}")
        return v


class ABTestUpdate(BaseModel):
    """
    Request to update an existing A/B test.

    All fields are optional for partial updates.
    """
    name: Optional[str] = Field(None, description="Human-readable name")
    description: Optional[str] = Field(None, description="Detailed description")
    traffic_split: Optional[Dict[str, float]] = Field(None, description="Traffic split")
    metrics: Optional[List[str]] = Field(None, description="Metrics to track")
    is_active: Optional[bool] = Field(None, description="Whether the test is active")

    @field_validator('traffic_split')
    @classmethod
    def validate_traffic_split(cls, v):
        """Validate traffic split percentages sum to 100."""
        if v is not None:
            total = sum(v.values())
            if abs(total - 100.0) > 0.01:
                raise ValueError(f"Traffic split must sum to 100, got {total}")
        return v


class ABTestResult(BaseModel):
    """
    A/B test execution result.

    Records metrics for a single workflow execution during an A/B test.

    Attributes:
        ab_test_id: ID of the A/B test
        template_id: ID of the workflow template
        version: Version that was executed
        execution_id: ID of the workflow execution
        execution_time_ms: Execution time in milliseconds
        tokens_used: Number of tokens consumed
        quality_score: Optional quality metric (0.0-1.0)
        success: Whether execution succeeded
        error_message: Error message if execution failed
    """
    ab_test_id: str = Field(..., description="ID of the A/B test")
    template_id: str = Field(..., description="ID of the workflow template")
    version: str = Field(..., description="Version that was executed")
    execution_id: str = Field(..., description="ID of the workflow execution")
    execution_time_ms: Optional[int] = Field(None, description="Execution time in ms")
    tokens_used: Optional[int] = Field(None, description="Number of tokens consumed")
    quality_score: Optional[float] = Field(None, description="Quality metric (0.0-1.0)")
    success: Optional[bool] = Field(None, description="Whether execution succeeded")
    error_message: Optional[str] = Field(None, description="Error message if failed")

    # Joined fields from workflow_execution_history (LEFT JOIN; None
    # when the execution record doesn't exist — e.g. pre-identity rows)
    execution_status: Optional[str] = Field(None, description="Execution record status (started/completed/error)")
    execution_agent_id: Optional[str] = Field(None, description="Agent that triggered the execution (from record metadata)")
    execution_started_at: Optional[str] = Field(None, description="Execution start timestamp")

    model_config = ConfigDict(json_schema_extra={ "example": { "ab_test_id": "parallel-vs-sequential", "template_id": "content-pipeline", "version": "v2.0", "execution_id": "exec-456", "execution_time_ms": 1800, "tokens_used": 2500, "quality_score": 0.92, "success": True } })


class ABTestResultRecord(BaseModel):
    """
    Request to record an A/B test result.
    """
    version: str = Field(..., description="Version that was executed")
    execution_id: str = Field(..., description="ID of the workflow execution")
    execution_time_ms: Optional[int] = Field(None, description="Execution time in ms")
    tokens_used: Optional[int] = Field(None, description="Number of tokens consumed")
    quality_score: Optional[float] = Field(None, description="Quality metric (0.0-1.0)")
    success: Optional[bool] = Field(None, description="Whether execution succeeded")
    error_message: Optional[str] = Field(None, description="Error message if failed")


class ABTestResponse(BaseModel):
    """
    Response containing A/B test information.
    """
    id: str
    template_id: str
    name: str
    description: Optional[str]
    versions: List[str]
    traffic_split: Dict[str, float]
    metrics: Optional[List[str]]
    is_active: bool
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ABTestListResponse(BaseModel):
    """
    Response containing a list of A/B tests.
    """
    tests: List[ABTestResponse]
    total: int

    model_config = ConfigDict(json_schema_extra={ "example": { "tests": [ { "id": "parallel-vs-sequential", "template_id": "content-pipeline", "name": "Parallel vs Sequential", "description": "Compare execution strategies", "versions": ["v1.0", "v2.0"], "traffic_split": {"v1.0": 50.0, "v2.0": 50.0}, "metrics": ["execution_time", "tokens"], "is_active": True, "started_at": "2026-03-30T10:00:00Z", "created_at": "2026-03-30T09:00:00Z" } ], "total": 1 } })


class ABTestResultsSummary(BaseModel):
    """
    Summary of A/B test results.

    Attributes:
        ab_test_id: ID of the A/B test
        version_results: Metrics aggregated by version
        total_executions: Total number of executions recorded
        recommendation: Suggested winning version
    """
    ab_test_id: str
    version_results: Dict[str, Dict[str, Any]] = Field(
        ...,
        description="Metrics aggregated by version"
    )
    total_executions: int
    recommendation: Optional[str] = Field(
        None,
        description="Suggested winning version based on metrics"
    )

    model_config = ConfigDict(json_schema_extra={ "example": { "ab_test_id": "parallel-vs-sequential", "version_results": { "v1.0": { "avg_execution_time_ms": 2500, "avg_tokens_used": 3000, "success_rate": 0.95, "total_executions": 100 }, "v2.0": { "avg_execution_time_ms": 1800, "avg_tokens_used": 2800, "success_rate": 0.97, "total_executions": 98 } }, "total_executions": 198, "recommendation": "v2.0" } })


class ABTestComparison(BaseModel):
    """
    Detailed comparison of A/B test versions.
    """
    ab_test_id: str
    name: str
    versions: List[str]
    comparison: Dict[str, Dict[str, Any]]
    statistical_significance: Optional[Dict[str, Any]] = Field(
        None,
        description="Statistical analysis results"
    )
    recommendation: Optional[str]

    model_config = ConfigDict(json_schema_extra={ "example": { "ab_test_id": "parallel-vs-sequential", "name": "Parallel vs Sequential", "versions": ["v1.0", "v2.0"], "comparison": { "v1.0": { "avg_execution_time_ms": 2500, "improvement": "baseline" }, "v2.0": { "avg_execution_time_ms": 1800, "improvement": "-28% faster" } }, "recommendation": "v2.0" } })
