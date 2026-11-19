"""
Workflow versions validate the v-prefixed format and round-trip through the schemas.

Tests cover:
- Version schema validation
- Version service CRUD operations
- Version activation/deactivation
- Version comparison
- API endpoints

Run with:
    uv run pytest tests/workflows/test_versioning.py -v
"""

import pytest
import uuid

from app.domain.workflows.schemas.version_config import (
    VersionCreate,
    VersionUpdate,
    VersionCompare,
)
from app.domain.workflows.services.version_service import VersionService


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def version_service():
    """Create version service instance."""
    return VersionService()


@pytest.fixture
def test_template_id():
    """Generate unique template ID for testing."""
    return f"test-template-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def cleanup_versions(version_service, test_template_id):
    """Fixture to cleanup test versions after test."""
    created_versions = []

    yield lambda version: created_versions.append(version)

    # Cleanup
    for version in created_versions:
        try:
            version_service.delete_version(test_template_id, version)
        except Exception:
            pass


# =============================================================================
# Schema Validation Tests
# =============================================================================

class TestVersionSchemaValidation:
    """Test version schema validation."""

    def test_valid_version_format(self):
        """Test valid version formats."""
        valid_versions = ["v1.0", "v1.1", "v2.0", "v10.5", "v1.0.0", "v2.1.3"]
        
        for version in valid_versions:
            config = VersionCreate(
                version=version,
                config={"parallel": True},
                changelog="Test version"
            )
            assert config.version == version

    def test_invalid_version_format_no_v_prefix(self):
        """Test version format without 'v' prefix raises error."""
        with pytest.raises(ValueError) as exc_info:
            VersionCreate(
                version="1.0",
                config={"parallel": True},
                changelog="Test version"
            )
        assert "must start with 'v'" in str(exc_info.value)

    def test_invalid_version_format_too_short(self):
        """Test version format that is too short raises error."""
        with pytest.raises(ValueError) as exc_info:
            VersionCreate(
                version="v1",
                config={"parallel": True},
                changelog="Test version"
            )
        assert "must have format" in str(exc_info.value)

    def test_version_create_schema(self):
        """Test VersionCreate schema with all fields."""
        config = VersionCreate(
            version="v2.0",
            config={
                "parallel": True,
                "max_retries": 3,
                "timeout_ms": 30000
            },
            changelog="Added parallel execution support",
            created_by="admin"
        )
        
        assert config.version == "v2.0"
        assert config.config["parallel"] is True
        assert config.changelog == "Added parallel execution support"
        assert config.created_by == "admin"

    def test_version_update_schema_partial(self):
        """Test VersionUpdate with partial fields."""
        update = VersionUpdate(
            config={"parallel": False},
            is_active=False
        )
        
        assert update.config["parallel"] is False
        assert update.is_active is False
        assert update.changelog is None

    def test_version_compare_schema(self):
        """Test VersionCompare schema."""
        compare = VersionCompare(
            v1="v1.0",
            v2="v2.0",
            metrics=["execution_time", "tokens", "success_rate"]
        )
        
        assert compare.v1 == "v1.0"
        assert compare.v2 == "v2.0"
        assert len(compare.metrics) == 3


# =============================================================================
# Version Service Tests
# =============================================================================

class TestVersionService:
    """Test version service operations."""

    def test_create_version(self, version_service, test_template_id, cleanup_versions):
        """Test creating a workflow version."""
        config = VersionCreate(
            version="v1.0",
            config={"parallel": True, "max_retries": 3},
            changelog="Initial version",
            created_by="test-user"
        )
        
        version = version_service.create_version(test_template_id, config)
        cleanup_versions("v1.0")
        
        assert version.template_id == test_template_id
        assert version.version == "v1.0"
        assert version.is_active is True
        assert version.created_by == "test-user"
        assert version.config["parallel"] is True

    def test_get_version(self, version_service, test_template_id, cleanup_versions):
        """Test retrieving a specific version."""
        config = VersionCreate(
            version="v1.0",
            config={"parallel": True},
            changelog="Test version"
        )
        
        created = version_service.create_version(test_template_id, config)
        cleanup_versions("v1.0")
        
        retrieved = version_service.get_version(test_template_id, "v1.0")
        
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.version == "v1.0"

    def test_get_version_not_found(self, version_service, test_template_id):
        """Test retrieving a non-existent version."""
        version = version_service.get_version(test_template_id, "v99.0")
        assert version is None

    def test_list_versions(self, version_service, test_template_id, cleanup_versions):
        """Test listing all versions for a template."""
        # Create multiple versions
        for i, v in enumerate(["v1.0", "v1.1", "v2.0"]):
            config = VersionCreate(
                version=v,
                config={"version": i},
                changelog=f"Version {v}"
            )
            version_service.create_version(test_template_id, config)
            cleanup_versions(v)
        
        versions = version_service.list_versions(test_template_id)
        
        assert len(versions) == 3
        version_nums = [v.version for v in versions]
        assert "v1.0" in version_nums
        assert "v1.1" in version_nums
        assert "v2.0" in version_nums

    def test_list_versions_active_only(self, version_service, test_template_id, cleanup_versions):
        """Test listing only active versions."""
        # Create two versions
        for v in ["v1.0", "v2.0"]:
            config = VersionCreate(
                version=v,
                config={},
                changelog=f"Version {v}"
            )
            version_service.create_version(test_template_id, config)
            cleanup_versions(v)
        
        # Deactivate v1.0
        version_service.deactivate_version(test_template_id, "v1.0")
        
        active_versions = version_service.list_versions(test_template_id, active_only=True)
        
        assert len(active_versions) == 1
        assert active_versions[0].version == "v2.0"

    def test_update_version(self, version_service, test_template_id, cleanup_versions):
        """Test updating a version."""
        config = VersionCreate(
            version="v1.0",
            config={"parallel": True},
            changelog="Initial version"
        )
        
        version_service.create_version(test_template_id, config)
        cleanup_versions("v1.0")
        
        update = VersionUpdate(
            config={"parallel": False, "max_retries": 5},
            changelog="Updated configuration"
        )
        
        updated = version_service.update_version(test_template_id, "v1.0", update)
        
        assert updated is not None
        assert updated.config["parallel"] is False
        assert updated.config["max_retries"] == 5
        assert updated.changelog == "Updated configuration"

    def test_update_version_not_found(self, version_service, test_template_id):
        """Test updating a non-existent version."""
        update = VersionUpdate(config={"parallel": True})
        updated = version_service.update_version(test_template_id, "v99.0", update)
        assert updated is None

    def test_delete_version(self, version_service, test_template_id):
        """Test deleting a version."""
        config = VersionCreate(
            version="v1.0",
            config={},
            changelog="To be deleted"
        )
        
        version_service.create_version(test_template_id, config)
        
        deleted = version_service.delete_version(test_template_id, "v1.0")
        assert deleted is True
        
        # Verify deletion
        version = version_service.get_version(test_template_id, "v1.0")
        assert version is None

    def test_delete_version_not_found(self, version_service, test_template_id):
        """Test deleting a non-existent version."""
        deleted = version_service.delete_version(test_template_id, "v99.0")
        assert deleted is False


# =============================================================================
# Version Activation Tests
# =============================================================================

class TestVersionActivation:
    """Test version activation and deactivation."""

    def test_activate_version(self, version_service, test_template_id, cleanup_versions):
        """Test activating a version."""
        # Create two versions
        for v in ["v1.0", "v2.0"]:
            config = VersionCreate(
                version=v,
                config={},
                changelog=f"Version {v}"
            )
            version_service.create_version(test_template_id, config)
            cleanup_versions(v)
        
        # Activate v1.0 (v2.0 should be active by default as it was created last)
        success = version_service.activate_version(test_template_id, "v1.0")
        assert success is True
        
        # Verify v1.0 is active
        v1 = version_service.get_version(test_template_id, "v1.0")
        assert v1.is_active is True
        
        # Verify v2.0 is inactive
        v2 = version_service.get_version(test_template_id, "v2.0")
        assert v2.is_active is False

    def test_activate_version_not_found(self, version_service, test_template_id):
        """Test activating a non-existent version."""
        success = version_service.activate_version(test_template_id, "v99.0")
        assert success is False

    def test_deactivate_version(self, version_service, test_template_id, cleanup_versions):
        """Test deactivating a version."""
        config = VersionCreate(
            version="v1.0",
            config={},
            changelog="To deactivate"
        )
        
        version_service.create_version(test_template_id, config)
        cleanup_versions("v1.0")
        
        success = version_service.deactivate_version(test_template_id, "v1.0")
        assert success is True
        
        version = version_service.get_version(test_template_id, "v1.0")
        assert version.is_active is False

    def test_deactivate_version_not_found(self, version_service, test_template_id):
        """Test deactivating a non-existent version."""
        success = version_service.deactivate_version(test_template_id, "v99.0")
        assert success is False

    def test_get_active_version(self, version_service, test_template_id, cleanup_versions):
        """Test getting the active version."""
        # Create two versions
        for v in ["v1.0", "v2.0"]:
            config = VersionCreate(
                version=v,
                config={"version_name": v},
                changelog=f"Version {v}"
            )
            version_service.create_version(test_template_id, config)
            cleanup_versions(v)
        
        active = version_service.get_active_version(test_template_id)
        
        assert active is not None
        assert active.version == "v2.0"  # Last created should be active

    def test_get_active_version_none(self, version_service, test_template_id):
        """Test getting active version when none exist."""
        active = version_service.get_active_version(test_template_id)
        assert active is None


# =============================================================================
# Version Comparison Tests
# =============================================================================

class TestVersionComparison:
    """Test version comparison functionality."""

    def test_compare_versions(self, version_service, test_template_id, cleanup_versions):
        """Test comparing two versions."""
        # Create two versions
        for v in ["v1.0", "v2.0"]:
            config = VersionCreate(
                version=v,
                config={"version": v},
                changelog=f"Version {v}"
            )
            version_service.create_version(test_template_id, config)
            cleanup_versions(v)
        
        result = version_service.compare_versions(test_template_id, "v1.0", "v2.0")
        
        assert result is not None
        assert result.template_id == test_template_id
        assert result.v1["version"] == "v1.0"
        assert result.v2["version"] == "v2.0"

    def test_compare_versions_not_found(self, version_service, test_template_id):
        """Test comparing non-existent versions."""
        result = version_service.compare_versions(test_template_id, "v1.0", "v99.0")
        assert result is None


# =============================================================================
# Integration Tests
# =============================================================================

class TestVersioningIntegration:
    """Integration tests for workflow versioning."""

    def test_version_lifecycle(self, version_service, test_template_id):
        """Test complete version lifecycle."""
        # 1. Create v1.0
        v1_config = VersionCreate(
            version="v1.0",
            config={"parallel": False, "max_retries": 3},
            changelog="Initial sequential version",
            created_by="developer"
        )
        v1 = version_service.create_version(test_template_id, v1_config)
        assert v1.is_active is True
        
        # 2. Create v2.0 (should auto-deactivate v1.0)
        v2_config = VersionCreate(
            version="v2.0",
            config={"parallel": True, "max_retries": 3},
            changelog="Added parallel execution",
            created_by="developer"
        )
        v2 = version_service.create_version(test_template_id, v2_config)
        assert v2.is_active is True
        
        # Verify v1.0 is now inactive
        v1_updated = version_service.get_version(test_template_id, "v1.0")
        assert v1_updated.is_active is False
        
        # 3. List all versions
        versions = version_service.list_versions(test_template_id)
        assert len(versions) == 2
        
        # 4. Reactivate v1.0
        version_service.activate_version(test_template_id, "v1.0")
        v1_reactivated = version_service.get_version(test_template_id, "v1.0")
        v2_deactivated = version_service.get_version(test_template_id, "v2.0")
        assert v1_reactivated.is_active is True
        assert v2_deactivated.is_active is False
        
        # 5. Update v2.0
        update = VersionUpdate(
            config={"parallel": True, "max_retries": 5},
            changelog="Increased retry limit"
        )
        v2_updated = version_service.update_version(test_template_id, "v2.0", update)
        assert v2_updated.config["max_retries"] == 5
        
        # 6. Compare versions
        comparison = version_service.compare_versions(test_template_id, "v1.0", "v2.0")
        assert comparison is not None
        
        # 7. Cleanup
        version_service.delete_version(test_template_id, "v1.0")
        version_service.delete_version(test_template_id, "v2.0")
