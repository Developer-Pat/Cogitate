"""
Tool Permission domain schemas.

Pydantic schemas for tool permission request/response validation.
"""

from datetime import datetime
from typing import Optional, List, Dict

from pydantic import BaseModel, Field, ConfigDict, field_validator


# =============================================================================
# Permission Level Constants
# =============================================================================

class PermissionLevel:
    """Valid permission levels for tool access."""
    READ = "read"
    EXECUTE = "execute"
    WRITE = "write"
    ADMIN = "admin"
    DENY = "deny"
    
    VALID_LEVELS = [READ, EXECUTE, WRITE, ADMIN, DENY]
    
    @classmethod
    def is_valid(cls, level: str) -> bool:
        """Check if a permission level is valid."""
        return level in cls.VALID_LEVELS
    
    @classmethod
    def get_icon(cls, level: str) -> str:
        """Get icon for permission level."""
        icons = {
            cls.READ: "👁️",
            cls.EXECUTE: "▶️",
            cls.WRITE: "✏️",
            cls.ADMIN: "🔒",
            cls.DENY: "🚫",
        }
        return icons.get(level, "❓")
    
    @classmethod
    def get_label(cls, level: str) -> str:
        """Get display label for permission level."""
        labels = {
            cls.READ: "Read",
            cls.EXECUTE: "Execute",
            cls.WRITE: "Write",
            cls.ADMIN: "Admin",
            cls.DENY: "Denied",
        }
        return labels.get(level, "Unknown")


# =============================================================================
# Tool Collection Permission Schemas
# =============================================================================


class ToolCollectionPermissionBase(BaseModel):
    """Base schema for tool collection permissions."""

    model_config = ConfigDict(from_attributes=True)

    permission_level: str = Field(
        ...,
        description="Permission level (read, execute, write, admin, deny)",
        max_length=20,
    )
    
    @field_validator('permission_level')
    @classmethod
    def validate_permission_level(cls, v: str) -> str:
        """Validate permission level is one of the allowed values."""
        if not PermissionLevel.is_valid(v):
            raise ValueError(
                f"Invalid permission level: {v}. "
                f"Must be one of: {', '.join(PermissionLevel.VALID_LEVELS)}"
            )
        return v


class ToolCollectionPermissionCreate(ToolCollectionPermissionBase):
    """Schema for creating a tool collection permission."""

    tool_id: str = Field(..., description="Tool ID (UUID)")
    collection_id: str = Field(..., description="Collection ID (UUID)")


class ToolCollectionPermissionUpdate(BaseModel):
    """Schema for updating a tool collection permission."""

    permission_level: Optional[str] = Field(
        None,
        description="Permission level (read, execute, write, admin, deny)",
        max_length=20,
    )
    
    @field_validator('permission_level')
    @classmethod
    def validate_permission_level(cls, v: Optional[str]) -> Optional[str]:
        """Validate permission level is one of the allowed values."""
        if v is not None and not PermissionLevel.is_valid(v):
            raise ValueError(
                f"Invalid permission level: {v}. "
                f"Must be one of: {', '.join(PermissionLevel.VALID_LEVELS)}"
            )
        return v


class CollectionSummary(BaseModel):
    """Summary of a collection for permission display."""

    id: str
    name: str
    entity_type: str
    icon: Optional[str] = None
    color: Optional[str] = None


class ToolCollectionPermissionResponse(ToolCollectionPermissionBase):
    """Schema for tool collection permission response."""

    id: str
    tool_id: str
    collection_id: str
    collection: Optional[CollectionSummary] = None
    created_at: datetime
    updated_at: datetime


class ToolPermissionSummary(BaseModel):
    """Summary of permissions for a tool."""

    collection_id: str
    collection_name: str
    permission_level: str
    member_count: int = Field(0, description="Number of items in collection")
    created_at: datetime
    updated_at: datetime


class ToolPermissionsResponse(BaseModel):
    """Schema for getting all permissions for a tool."""

    tool_id: str
    tool_name: str
    default_access: str = Field(..., description="Default permission for users without explicit access")
    permissions: List[ToolPermissionSummary] = Field(default_factory=list)
    total: int = Field(0, description="Total number of permission entries")


class ToolPermissionsUpdateRequest(BaseModel):
    """Schema for updating tool permissions."""

    default_access: Optional[str] = Field(
        None,
        description="Default permission for users without explicit access",
        max_length=20,
    )
    permissions: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of {collection_id: permission_level} mappings",
    )
    
    @field_validator('default_access')
    @classmethod
    def validate_default_access(cls, v: Optional[str]) -> Optional[str]:
        """Validate default access level."""
        if v is not None and not PermissionLevel.is_valid(v):
            raise ValueError(
                f"Invalid default access: {v}. "
                f"Must be one of: {', '.join(PermissionLevel.VALID_LEVELS)}"
            )
        return v


# =============================================================================
# Permission Check Schemas
# =============================================================================


class PermissionCheckResponse(BaseModel):
    """Schema for permission check response."""

    has_permission: bool = Field(..., description="Whether user has the required permission")
    permission_level: Optional[str] = Field(None, description="User's current permission level")
    required: Optional[str] = Field(None, description="Required permission level")
    source: Optional[str] = Field(None, description="Source of permission (e.g., 'collection:researchers')")
    message: Optional[str] = Field(None, description="Additional message (e.g., denial reason)")


# =============================================================================
# Accessible Tools Schemas
# =============================================================================


class AccessibleToolSummary(BaseModel):
    """Summary of an accessible tool."""

    id: str
    name: str
    slug: str
    description: str
    icon: Optional[str] = None
    color: Optional[str] = None
    type: Optional[str] = None
    provider: Optional[str] = None
    permission_level: str = Field(..., description="User's permission level for this tool")


class AccessibleToolsResponse(BaseModel):
    """Schema for listing accessible tools."""

    tools: List[AccessibleToolSummary] = Field(default_factory=list)
    total: int = Field(0, description="Total number of accessible tools")
    user_id: Optional[str] = Field(None, description="User ID for which tools were listed")
    permission_filter: Optional[str] = Field(None, description="Permission filter applied")


# =============================================================================
# Query Parameter Schemas
# =============================================================================


class PermissionListQuery(BaseModel):
    """Query parameters for listing permissions."""

    user_id: Optional[str] = Field(None, description="User ID to check permissions for")
    permission: Optional[str] = Field(None, description="Filter by minimum permission level")


class AccessibleToolsQuery(BaseModel):
    """Query parameters for listing accessible tools."""

    user_id: Optional[str] = Field(None, description="User ID to list tools for")
    permission: Optional[str] = Field(None, description="Minimum permission level required")
    limit: int = Field(100, ge=1, le=500, description="Maximum results per page")
    offset: int = Field(0, ge=0, description="Result offset for pagination")
