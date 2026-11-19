"""
Collections domain schemas.

Pydantic schemas for collections request/response validation.
"""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict, field_validator, computed_field


# =============================================================================
# Collection Schemas
# =============================================================================


class CollectionBase(BaseModel):
    """Base schema for collections."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Collection name", max_length=200)
    description: Optional[str] = Field(None, description="Collection description")
    entity_type: str = Field(..., description="Entity type filter (agent, tool, provider, macro_set, template, workflow_list)")
    color: str = Field("#3B82F6", description="Color for UI", max_length=20)
    icon: str = Field("folder", description="Icon name", max_length=50)


class CollectionCreate(CollectionBase):
    """Schema for creating a collection."""

    user_key: Optional[str] = Field("default", description="User identifier")


class CollectionUpdate(BaseModel):
    """Schema for updating a collection."""

    name: Optional[str] = Field(None, description="Collection name", max_length=200)
    description: Optional[str] = Field(None, description="Collection description")
    color: Optional[str] = Field(None, description="Color for UI", max_length=20)
    icon: Optional[str] = Field(None, description="Icon name", max_length=50)
    is_active: Optional[bool] = Field(None, description="Whether collection is active")


class CollectionItemSummary(BaseModel):
    """Summary of a collection item."""

    id: str
    entity_id: str
    entity_type: str
    entity_name: str
    added_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CollectionResponse(CollectionBase):
    """Schema for collection response."""

    id: str
    user_key: str
    is_active: bool
    items: List[CollectionItemSummary] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @field_validator('items', mode='before')
    @classmethod
    def get_items(cls, v):
        """Handle items relationship."""
        if v is None:
            return []
        # Convert SQLAlchemy relationship result to list of dicts
        items_list = list(v) if hasattr(v, '__iter__') and not isinstance(v, (str, bytes)) else v
        if not items_list:
            return []
        # If items are already CollectionItemSummary objects, return as list
        if isinstance(items_list[0], CollectionItemSummary):
            return items_list
        # Otherwise, return as-is and let Pydantic handle conversion
        return items_list

    @computed_field  # type: ignore[prop-decorator]
    @property
    def item_count(self) -> int:
        """Get the number of items in the collection."""
        return len(self.items) if self.items else 0


class CollectionListResponse(BaseModel):
    """Schema for listing collections."""

    collections: List[CollectionResponse]
    total: int


# =============================================================================
# Collection Item Schemas
# =============================================================================


class CollectionItemCreate(BaseModel):
    """Schema for adding an item to a collection."""

    entity_id: str = Field(..., description="Entity ID to add")
    entity_type: str = Field(..., description="Entity type (agent, tool, provider, macro_set, template, workflow_list)")
    entity_name: str = Field(..., description="Entity name for display")


class CollectionItemResponse(BaseModel):
    """Schema for collection item response."""

    id: str
    collection_id: str
    entity_id: str
    entity_type: str
    entity_name: str
    added_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CollectionContainsResponse(BaseModel):
    """Schema for checking if entity is in collections."""

    collections: List[CollectionResponse]
    total: int


# =============================================================================
# Query Parameter Schemas
# =============================================================================


class CollectionListQuery(BaseModel):
    """Query parameters for listing collections."""

    entity_type: Optional[str] = Field(None, description="Filter by entity type")
    search: Optional[str] = Field(None, description="Search by name or description")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    limit: int = Field(100, ge=1, le=500, description="Maximum results per page")
    offset: int = Field(0, ge=0, description="Result offset for pagination")
