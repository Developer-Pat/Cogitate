"""
Collections domain.

Provides curated collections of entities (agents, tools, providers, macros, templates).
"""

from app.domain.collections.models import Collection, CollectionItem
from app.domain.collections.schemas import (
    CollectionCreate,
    CollectionUpdate,
    CollectionResponse,
    CollectionListResponse,
    CollectionItemCreate,
    CollectionItemResponse,
)
from app.domain.collections.service import CollectionService

__all__ = [
    "Collection",
    "CollectionItem",
    "CollectionCreate",
    "CollectionUpdate",
    "CollectionResponse",
    "CollectionListResponse",
    "CollectionItemCreate",
    "CollectionItemResponse",
    "CollectionService",
]
