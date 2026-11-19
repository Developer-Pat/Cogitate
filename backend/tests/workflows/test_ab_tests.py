"""
A/B test schemas: the traffic split must sum to 100, and partial updates validate.

Tests cover:
- A/B test schema validation
- A/B test service CRUD operations
- Traffic splitting
- Result recording and aggregation
- Test lifecycle management
- API endpoints

Run with:
    uv run pytest tests/workflows/test_ab_tests.py -v
"""

import pytest
import uuid

from app.domain.workflows.schemas.version_config import (
    ABTestCreate,
    ABTestUpdate,
    ABTestResultRecord,
)
from app.domain.workflows.services.ab_test_service import ABTestService


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def ab_test_service():
    """Create A/B test service instance."""
    return ABTestService()


@pytest.fixture
def test_template_id():
    """Generate unique template ID for testing."""
    return f"test-template-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def cleanup_tests(ab_test_service):
    """Fixture to cleanup test A/B tests after test."""
    created_ids = []

    yield lambda test_id: created_ids.append(test_id)

    # Cleanup
    for test_id in created_ids:
        try:
            ab_test_service.delete_test(test_id)
        except Exception:
            pass


# =============================================================================
# Schema Validation Tests
# =============================================================================

class TestABTestSchemaValidation:
    """Test A/B test schema validation."""

    def test_valid_traffic_split(self):
        """Test valid traffic split configurations."""
        valid_splits = [
            {"v1.0": 50.0, "v2.0": 50.0},
            {"v1.0": 70.0, "v2.0": 30.0},
            {"v1.0": 33.33, "v2.0": 33.33, "v3.0": 33.34},
            {"v1.0": 100.0},  # Single version (edge case)
        ]
        
        for split in valid_splits:
            config = ABTestCreate(
                id=f"test-{uuid.uuid4().hex[:8]}",
                template_id="test-template",
                name="Test A/B",
                versions=list(split.keys()),
                traffic_split=split
            )
            assert config.traffic_split == split

    def test_invalid_traffic_split_not_sum_to_100(self):
        """Test traffic split that doesn't sum to 100 raises error."""
        with pytest.raises(ValueError) as exc_info:
            ABTestCreate(
                id="test-123",
                template_id="test-template",
                name="Test A/B",
                versions=["v1.0", "v2.0"],
                traffic_split={"v1.0": 60.0, "v2.0": 60.0}  # Sums to 120
            )
        assert "must sum to 100" in str(exc_info.value)

    def test_invalid_traffic_split_empty(self):
        """Test empty traffic split raises error."""
        with pytest.raises(ValueError) as exc_info:
            ABTestCreate(
                id="test-123",
                template_id="test-template",
                name="Test A/B",
                versions=["v1.0"],
                traffic_split={}
            )
        assert "cannot be empty" in str(exc_info.value)

    def test_ab_test_create_schema(self):
        """Test ABTestCreate schema with all fields."""
        config = ABTestCreate(
            id="parallel-vs-sequential",
            template_id="content-pipeline",
            name="Parallel vs Sequential Execution",
            description="Compare parallel (v2.0) vs sequential (v1.0)",
            versions=["v1.0", "v2.0"],
            traffic_split={"v1.0": 50.0, "v2.0": 50.0},
            metrics=["execution_time", "tokens", "success_rate"],
            is_active=True
        )
        
        assert config.id == "parallel-vs-sequential"
        assert config.template_id == "content-pipeline"
        assert len(config.versions) == 2
        assert config.traffic_split["v1.0"] == 50.0
        assert len(config.metrics) == 3

    def test_ab_test_update_schema_partial(self):
        """Test ABTestUpdate with partial fields."""
        update = ABTestUpdate(
            name="Updated Test Name",
            is_active=False
        )
        
        assert update.name == "Updated Test Name"
        assert update.is_active is False
        assert update.traffic_split is None

    def test_ab_test_update_traffic_split_validation(self):
        """Test ABTestUpdate validates traffic split."""
        with pytest.raises(ValueError) as exc_info:
            ABTestUpdate(
                traffic_split={"v1.0": 60.0, "v2.0": 60.0}
            )
        assert "must sum to 100" in str(exc_info.value)


# =============================================================================
# A/B Test Service CRUD Tests
# =============================================================================

class TestABTestServiceCRUD:
    """Test A/B test service CRUD operations."""

    def test_create_test(self, ab_test_service, cleanup_tests):
        """Test creating an A/B test."""
        config = ABTestCreate(
            id=f"test-{uuid.uuid4().hex[:8]}",
            template_id="test-template",
            name="Test A/B Test",
            versions=["v1.0", "v2.0"],
            traffic_split={"v1.0": 50.0, "v2.0": 50.0},
            metrics=["execution_time", "tokens"],
            is_active=True
        )
        
        test = ab_test_service.create_test(config)
        cleanup_tests(test.id)
        
        assert test.id == config.id
        assert test.template_id == "test-template"
        assert len(test.versions) == 2
        assert test.is_active is True

    def test_get_test(self, ab_test_service, cleanup_tests):
        """Test retrieving an A/B test."""
        config = ABTestCreate(
            id=f"test-{uuid.uuid4().hex[:8]}",
            template_id="test-template",
            name="Test A/B",
            versions=["v1.0", "v2.0"],
            traffic_split={"v1.0": 50.0, "v2.0": 50.0}
        )
        
        created = ab_test_service.create_test(config)
        cleanup_tests(created.id)
        
        retrieved = ab_test_service.get_test(created.id)
        
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == "Test A/B"

    def test_get_test_not_found(self, ab_test_service):
        """Test retrieving a non-existent A/B test."""
        test = ab_test_service.get_test("non-existent-id")
        assert test is None

    def test_list_tests(self, ab_test_service, cleanup_tests):
        """Test listing all A/B tests."""
        # Create multiple tests
        for i in range(3):
            config = ABTestCreate(
                id=f"test-{uuid.uuid4().hex[:8]}",
                template_id="test-template",
                name=f"Test {i}",
                versions=["v1.0", "v2.0"],
                traffic_split={"v1.0": 50.0, "v2.0": 50.0}
            )
            test = ab_test_service.create_test(config)
            cleanup_tests(test.id)
        
        tests = ab_test_service.list_tests()
        
        assert len(tests) >= 3

    def test_list_tests_active_only(self, ab_test_service, cleanup_tests):
        """Test listing only active A/B tests."""
        # Create two tests
        config1 = ABTestCreate(
            id=f"test-{uuid.uuid4().hex[:8]}",
            template_id="test-template",
            name="Active Test",
            versions=["v1.0", "v2.0"],
            traffic_split={"v1.0": 50.0, "v2.0": 50.0},
            is_active=True
        )
        config2 = ABTestCreate(
            id=f"test-{uuid.uuid4().hex[:8]}",
            template_id="test-template",
            name="Inactive Test",
            versions=["v1.0", "v2.0"],
            traffic_split={"v1.0": 50.0, "v2.0": 50.0},
            is_active=False
        )
        
        test1 = ab_test_service.create_test(config1)
        test2 = ab_test_service.create_test(config2)
        cleanup_tests(test1.id)
        cleanup_tests(test2.id)
        
        active_tests = ab_test_service.list_tests(active_only=True)
        
        # At least test1 should be in active list
        assert any(t.id == test1.id for t in active_tests)

    def test_update_test(self, ab_test_service, cleanup_tests):
        """Test updating an A/B test."""
        config = ABTestCreate(
            id=f"test-{uuid.uuid4().hex[:8]}",
            template_id="test-template",
            name="Original Name",
            versions=["v1.0", "v2.0"],
            traffic_split={"v1.0": 50.0, "v2.0": 50.0}
        )
        
        created = ab_test_service.create_test(config)
        cleanup_tests(created.id)
        
        update = ABTestUpdate(
            name="Updated Name",
            description="New description"
        )
        
        updated = ab_test_service.update_test(created.id, update)
        
        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.description == "New description"

    def test_update_test_not_found(self, ab_test_service):
        """Test updating a non-existent A/B test."""
        update = ABTestUpdate(name="New Name")
        updated = ab_test_service.update_test("non-existent-id", update)
        assert updated is None

    def test_delete_test(self, ab_test_service):
        """Test deleting an A/B test."""
        config = ABTestCreate(
            id=f"test-{uuid.uuid4().hex[:8]}",
            template_id="test-template",
            name="To Delete",
            versions=["v1.0", "v2.0"],
            traffic_split={"v1.0": 50.0, "v2.0": 50.0}
        )
        
        created = ab_test_service.create_test(config)
        
        deleted = ab_test_service.delete_test(created.id)
        assert deleted is True
        
        # Verify deletion
        test = ab_test_service.get_test(created.id)
        assert test is None

    def test_delete_test_not_found(self, ab_test_service):
        """Test deleting a non-existent A/B test."""
        deleted = ab_test_service.delete_test("non-existent-id")
        assert deleted is False


# =============================================================================
# Test Lifecycle Management Tests
# =============================================================================

class TestLifecycleManagement:
    """Test A/B test lifecycle management."""

    def test_start_test(self, ab_test_service, cleanup_tests):
        """Test starting an A/B test."""
        config = ABTestCreate(
            id=f"test-{uuid.uuid4().hex[:8]}",
            template_id="test-template",
            name="Test Start",
            versions=["v1.0", "v2.0"],
            traffic_split={"v1.0": 50.0, "v2.0": 50.0},
            is_active=False
        )
        
        created = ab_test_service.create_test(config)
        cleanup_tests(created.id)
        
        success = ab_test_service.start_test(created.id)
        assert success is True
        
        test = ab_test_service.get_test(created.id)
        assert test.is_active is True

    def test_start_test_not_found(self, ab_test_service):
        """Test starting a non-existent A/B test."""
        success = ab_test_service.start_test("non-existent-id")
        assert success is False

    def test_pause_test(self, ab_test_service, cleanup_tests):
        """Test pausing an A/B test."""
        config = ABTestCreate(
            id=f"test-{uuid.uuid4().hex[:8]}",
            template_id="test-template",
            name="Test Pause",
            versions=["v1.0", "v2.0"],
            traffic_split={"v1.0": 50.0, "v2.0": 50.0},
            is_active=True
        )
        
        created = ab_test_service.create_test(config)
        cleanup_tests(created.id)
        
        success = ab_test_service.pause_test(created.id)
        assert success is True
        
        test = ab_test_service.get_test(created.id)
        assert test.is_active is False

    def test_stop_test(self, ab_test_service, cleanup_tests):
        """Test stopping an A/B test."""
        config = ABTestCreate(
            id=f"test-{uuid.uuid4().hex[:8]}",
            template_id="test-template",
            name="Test Stop",
            versions=["v1.0", "v2.0"],
            traffic_split={"v1.0": 50.0, "v2.0": 50.0},
            is_active=True
        )
        
        created = ab_test_service.create_test(config)
        cleanup_tests(created.id)
        
        success = ab_test_service.stop_test(created.id)
        assert success is True
        
        test = ab_test_service.get_test(created.id)
        assert test.is_active is False


# =============================================================================
# Traffic Splitting Tests
# =============================================================================

class TestTrafficSplitting:
    """Test traffic splitting functionality."""

    def test_assign_version(self, ab_test_service, cleanup_tests):
        """Test assigning a version based on traffic split."""
        config = ABTestCreate(
            id=f"test-{uuid.uuid4().hex[:8]}",
            template_id="test-template",
            name="Traffic Split Test",
            versions=["v1.0", "v2.0"],
            traffic_split={"v1.0": 50.0, "v2.0": 50.0},
            is_active=True
        )
        
        created = ab_test_service.create_test(config)
        cleanup_tests(created.id)
        
        assigned = ab_test_service.assign_version(created.id)
        
        assert assigned in ["v1.0", "v2.0"]

    def test_assign_version_inactive_test(self, ab_test_service, cleanup_tests):
        """Test assigning version for inactive test."""
        config = ABTestCreate(
            id=f"test-{uuid.uuid4().hex[:8]}",
            template_id="test-template",
            name="Inactive Test",
            versions=["v1.0", "v2.0"],
            traffic_split={"v1.0": 50.0, "v2.0": 50.0},
            is_active=False
        )
        
        created = ab_test_service.create_test(config)
        cleanup_tests(created.id)
        
        assigned = ab_test_service.assign_version(created.id)
        assert assigned is None

    def test_assign_version_not_found(self, ab_test_service):
        """Test assigning version for non-existent test."""
        assigned = ab_test_service.assign_version("non-existent-id")
        assert assigned is None

    def test_traffic_split_distribution(self, ab_test_service, cleanup_tests):
        """Test traffic split distribution approximates configuration."""
        config = ABTestCreate(
            id=f"test-{uuid.uuid4().hex[:8]}",
            template_id="test-template",
            name="Distribution Test",
            versions=["v1.0", "v2.0"],
            traffic_split={"v1.0": 70.0, "v2.0": 30.0},
            is_active=True
        )
        
        created = ab_test_service.create_test(config)
        cleanup_tests(created.id)
        
        # Assign 1000 times
        assignments = {"v1.0": 0, "v2.0": 0}
        for _ in range(1000):
            assigned = ab_test_service.assign_version(created.id)
            assignments[assigned] += 1
        
        # Check distribution is within reasonable range (±10%)
        v1_percentage = assignments["v1.0"] / 1000 * 100
        v2_percentage = assignments["v2.0"] / 1000 * 100
        
        assert 60 <= v1_percentage <= 80  # Expected ~70%
        assert 20 <= v2_percentage <= 40  # Expected ~30%


# =============================================================================
# Result Recording Tests
# =============================================================================

class TestResultRecording:
    """Test A/B test result recording."""

    def test_record_result(self, ab_test_service, cleanup_tests):
        """Test recording an A/B test result."""
        config = ABTestCreate(
            id=f"test-{uuid.uuid4().hex[:8]}",
            template_id="test-template",
            name="Result Recording Test",
            versions=["v1.0", "v2.0"],
            traffic_split={"v1.0": 50.0, "v2.0": 50.0}
        )
        
        created = ab_test_service.create_test(config)
        cleanup_tests(created.id)
        
        result = ABTestResultRecord(
            version="v1.0",
            execution_id=f"exec-{uuid.uuid4().hex[:8]}",
            execution_time_ms=1500,
            tokens_used=2500,
            quality_score=0.92,
            success=True
        )
        
        recorded = ab_test_service.record_result(created.id, result)
        
        assert recorded.ab_test_id == created.id
        assert recorded.version == "v1.0"
        assert recorded.execution_time_ms == 1500
        assert recorded.tokens_used == 2500
        assert recorded.success is True

    def test_record_result_test_not_found(self, ab_test_service):
        """Test recording result for non-existent test."""
        result = ABTestResultRecord(
            version="v1.0",
            execution_id="exec-123"
        )
        
        with pytest.raises(ValueError) as exc_info:
            ab_test_service.record_result("non-existent-id", result)
        assert "not found" in str(exc_info.value)

    def test_get_results(self, ab_test_service, cleanup_tests):
        """Test getting aggregated results."""
        config = ABTestCreate(
            id=f"test-{uuid.uuid4().hex[:8]}",
            template_id="test-template",
            name="Results Test",
            versions=["v1.0", "v2.0"],
            traffic_split={"v1.0": 50.0, "v2.0": 50.0}
        )
        
        created = ab_test_service.create_test(config)
        cleanup_tests(created.id)
        
        # Record some results
        for i in range(5):
            result = ABTestResultRecord(
                version="v1.0",
                execution_id=f"exec-{i}",
                execution_time_ms=2000,
                tokens_used=3000,
                success=True
            )
            ab_test_service.record_result(created.id, result)
        
        results = ab_test_service.get_results(created.id)
        
        assert results.ab_test_id == created.id
        assert results.total_executions == 5
        assert "v1.0" in results.version_results
        assert results.version_results["v1.0"]["total_executions"] == 5

    def test_get_results_empty(self, ab_test_service, cleanup_tests):
        """Test getting results with no data."""
        config = ABTestCreate(
            id=f"test-{uuid.uuid4().hex[:8]}",
            template_id="test-template",
            name="Empty Results Test",
            versions=["v1.0", "v2.0"],
            traffic_split={"v1.0": 50.0, "v2.0": 50.0}
        )
        
        created = ab_test_service.create_test(config)
        cleanup_tests(created.id)
        
        results = ab_test_service.get_results(created.id)
        
        assert results.ab_test_id == created.id
        assert results.total_executions == 0


# =============================================================================
# Version Comparison Tests
# =============================================================================

class TestVersionComparison:
    """Test A/B test version comparison."""

    def test_compare_versions(self, ab_test_service, cleanup_tests):
        """Test comparing versions in an A/B test."""
        config = ABTestCreate(
            id=f"test-{uuid.uuid4().hex[:8]}",
            template_id="test-template",
            name="Comparison Test",
            versions=["v1.0", "v2.0"],
            traffic_split={"v1.0": 50.0, "v2.0": 50.0}
        )
        
        created = ab_test_service.create_test(config)
        cleanup_tests(created.id)
        
        # Record results for both versions
        for i in range(10):
            result_v1 = ABTestResultRecord(
                version="v1.0",
                execution_id=f"exec-v1-{i}",
                execution_time_ms=2500,
                tokens_used=3000,
                success=True
            )
            ab_test_service.record_result(created.id, result_v1)
            
            result_v2 = ABTestResultRecord(
                version="v2.0",
                execution_id=f"exec-v2-{i}",
                execution_time_ms=1800,
                tokens_used=2800,
                success=True
            )
            ab_test_service.record_result(created.id, result_v2)
        
        comparison = ab_test_service.compare_versions(created.id)
        
        assert comparison is not None
        assert comparison.ab_test_id == created.id
        assert len(comparison.versions) == 2
        assert comparison.recommendation == "v2.0"  # v2.0 is faster


# =============================================================================
# Integration Tests
# =============================================================================

class TestABTestIntegration:
    """Integration tests for A/B testing."""

    def test_ab_test_lifecycle(self, ab_test_service):
        """Test complete A/B test lifecycle."""
        test_id = f"test-{uuid.uuid4().hex[:8]}"
        
        # 1. Create test
        config = ABTestCreate(
            id=test_id,
            template_id="test-template",
            name="Lifecycle Test",
            versions=["v1.0", "v2.0"],
            traffic_split={"v1.0": 50.0, "v2.0": 50.0},
            metrics=["execution_time", "tokens"]
        )
        ab_test_service.create_test(config)
        
        # 2. Start test
        ab_test_service.start_test(test_id)
        
        # 3. Assign versions (simulate traffic)
        for _ in range(20):
            assigned = ab_test_service.assign_version(test_id)
            assert assigned in ["v1.0", "v2.0"]
        
        # 4. Record results
        for i in range(10):
            result_v1 = ABTestResultRecord(
                version="v1.0",
                execution_id=f"exec-v1-{i}",
                execution_time_ms=2500,
                tokens_used=3000,
                success=True
            )
            ab_test_service.record_result(test_id, result_v1)
            
            result_v2 = ABTestResultRecord(
                version="v2.0",
                execution_id=f"exec-v2-{i}",
                execution_time_ms=1800,
                tokens_used=2800,
                success=True
            )
            ab_test_service.record_result(test_id, result_v2)
        
        # 5. Get results
        results = ab_test_service.get_results(test_id)
        assert results.total_executions == 20
        
        # 6. Compare versions
        comparison = ab_test_service.compare_versions(test_id)
        assert comparison is not None
        
        # 7. Pause test
        ab_test_service.pause_test(test_id)
        test = ab_test_service.get_test(test_id)
        assert test.is_active is False
        
        # 8. Stop test
        ab_test_service.stop_test(test_id)
        
        # 9. Cleanup
        ab_test_service.delete_test(test_id)
