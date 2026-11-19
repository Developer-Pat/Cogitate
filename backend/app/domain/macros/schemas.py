"""
Macros domain schemas.

Pydantic schemas for macro sets and meta topics request/response validation.
"""

from datetime import datetime
from typing import Optional, Dict, List

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Macro Set Schemas
# =============================================================================


class MacroSetBase(BaseModel):
    """Base schema for macro sets."""

    model_config = {"from_attributes": True}

    namespace: str = Field("agent", description="Namespace discriminator ('system' or 'agent')")
    topic: str = Field(..., description="Topic category (e.g., 'Algebra', 'Geometry')")
    name: str = Field(..., description="Name of the macro set")
    mode_slug: Optional[str] = Field(None, description="Mode slug for System macros (optional)")
    description: Optional[str] = Field(None, description="Optional description")
    f1_macro: Optional[str] = Field(None, description="F1 macro definition")
    f2_macro: Optional[str] = Field(None, description="F2 macro definition")
    f3_macro: Optional[str] = Field(None, description="F3 macro definition")
    f4_macro: Optional[str] = Field(None, description="F4 macro definition")
    f5_macro: Optional[str] = Field(None, description="F5 macro definition")
    is_active: bool = Field(True, description="Whether the macro set is active")
    sort_order: int = Field(0, description="Sort order for display")


class MacroSetCreate(MacroSetBase):
    """Schema for creating a macro set."""

    user_key: str = Field(..., description="User identifier")


class SystemMacroSetCreate(BaseModel):
    """Schema for creating a system macro set (no user_key).

    Used by the mode API endpoint ``POST /modes/{mode_slug}/macros``.
    ``topic`` and ``name`` are required; all other fields are optional.
    ``namespace`` defaults to ``"system"`` for system macro sets.
    """

    model_config = {"from_attributes": True}

    # namespace removed — all macros are agent-scoped
    topic: str = Field(..., description="Topic category (e.g., 'Algebra', 'Geometry')")
    name: str = Field(..., description="Name of the macro set")
    description: Optional[str] = Field(None, description="Optional description")
    f1_macro: Optional[str] = Field(None, description="F1 macro definition")
    f2_macro: Optional[str] = Field(None, description="F2 macro definition")
    f3_macro: Optional[str] = Field(None, description="F3 macro definition")
    f4_macro: Optional[str] = Field(None, description="F4 macro definition")
    f5_macro: Optional[str] = Field(None, description="F5 macro definition")
    is_active: bool = Field(True, description="Whether the macro set is active")
    sort_order: int = Field(0, description="Sort order for display")


class MacroSetUpdate(BaseModel):
    """Schema for updating a macro set."""

    # namespace removed — all macros are agent-scoped
    topic: Optional[str] = Field(None, description="Topic category")
    name: Optional[str] = Field(None, description="Name of the macro set")
    mode_slug: Optional[str] = Field(None, description="Mode slug for System macros (optional)")
    description: Optional[str] = Field(None, description="Optional description")
    f1_macro: Optional[str] = Field(None, description="F1 macro definition")
    f2_macro: Optional[str] = Field(None, description="F2 macro definition")
    f3_macro: Optional[str] = Field(None, description="F3 macro definition")
    f4_macro: Optional[str] = Field(None, description="F4 macro definition")
    f5_macro: Optional[str] = Field(None, description="F5 macro definition")
    is_active: Optional[bool] = Field(None, description="Whether the macro set is active")
    sort_order: Optional[int] = Field(None, description="Sort order for display")


class MacroSetResponse(MacroSetBase):
    """Schema for macro set response."""

    id: int
    user_key: str
    created_at: datetime
    updated_at: datetime


class MacroSetListResponse(BaseModel):
    """Schema for listing macro sets."""

    macro_sets: List[MacroSetResponse]
    total: int


# =============================================================================
# Meta Topic Schemas
# =============================================================================


class TopicMapping(BaseModel):
    """Schema for a single topic mapping within a meta topic."""

    topic: str = Field(..., description="Topic name to map")
    slot_start: str = Field(..., description="Starting slot (e.g., 'F1', 'F6')")


class MetaTopicBase(BaseModel):
    """Base schema for meta topics."""

    model_config = {"from_attributes": True}

    name: str = Field(..., description="Name of the meta topic")
    mode_slug: Optional[str] = Field(None, description="Mode slug for meta topics (optional)")
    description: Optional[str] = Field(None, description="Optional description")
    topic_mappings: List[TopicMapping] = Field(
        default_factory=list,
        description="List of topic to slot mappings"
    )
    is_active: bool = Field(True, description="Whether the meta topic is active")

    @field_validator('topic_mappings', mode='before')
    @classmethod
    def parse_topic_mappings(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return []
        return v or []


class MetaTopicCreate(MetaTopicBase):
    """Schema for creating a meta topic."""

    user_key: str = Field(..., description="User identifier")


class MetaTopicUpdate(BaseModel):
    """Schema for updating a meta topic."""

    # namespace removed — all macros are agent-scoped
    name: Optional[str] = Field(None, description="Name of the meta topic")
    mode_slug: Optional[str] = Field(None, description="Mode slug for meta topics (optional)")
    description: Optional[str] = Field(None, description="Optional description")
    topic_mappings: Optional[List[TopicMapping]] = Field(
        None, description="List of topic to slot mappings"
    )
    is_active: Optional[bool] = Field(None, description="Whether the meta topic is active")


class MetaTopicResponse(MetaTopicBase):
    """Schema for meta topic response."""

    id: int
    user_key: str
    created_at: datetime
    updated_at: datetime


class MetaTopicListResponse(BaseModel):
    """Schema for listing meta topics."""

    meta_topics: List[MetaTopicResponse]
    total: int


class MetaTopicLoadResponse(BaseModel):
    """Schema for loaded meta topic with resolved macros."""

    meta_topic_id: int
    name: str
    extended_macros: Dict[str, str] = Field(
        ...,
        description="Mapping of function keys to macros (e.g., {'F1': '...', 'F2': '...'})"
    )
    slot_count: int = Field(..., description="Total number of slots populated")
    topic_mappings: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Topic mappings with slot ranges (e.g., [{'topic': 'algebra', 'slot_start': 'F1', 'slot_end': 'F5'}])"
    )


    @field_validator('topic_mappings', mode='before')
    @classmethod
    def parse_topic_mappings(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return []
        return v or []


# =============================================================================
# Topic List Response
# =============================================================================


class TopicListResponse(BaseModel):
    """Schema for listing available topics."""

    topics: List[str]
    total: int
