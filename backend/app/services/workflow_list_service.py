"""
Workflow List service.

Business logic for workflow list management.
"""

import uuid
import logging
import sqlite3
import json
from datetime import datetime, UTC
from typing import Optional, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from app.infrastructure.database.models import WorkflowList
from app.domain.workflow_lists.schemas import (
    WorkflowListCreate,
    WorkflowListUpdate,
    WorkflowListResponse,
)

logger = logging.getLogger(__name__)

# Database path for workflow templates - project root
from app.core.config import Paths, get_settings
DB_PATH = Paths.from_settings(get_settings()).shared_db


def get_db_connection():
    """Get SQLite database connection for workflow templates."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class WorkflowListService:
    """Service for managing workflow lists."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_workflow_lists(
        self,
        user_key: str = "default",
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[List[WorkflowList], int]:
        """
        List all workflow lists for a user.

        Args:
            user_key: User identifier
            tags: Optional list of tags to filter by
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            Tuple of (workflow lists, total count)
        """
        # Build base query
        query = select(WorkflowList).where(WorkflowList.user_key == user_key)

        # Add tag filtering if specified
        if tags:
            # Filter lists that contain any of the specified tags
            # Use JSON_CONTAINS for SQLite compatibility
            from sqlalchemy import text
            tag_conditions = []
            for tag in tags:
                tag_conditions.append(
                    text(f"json_each(value) = :tag_{tag.replace('-', '_')}")
                )
            # Simple approach: filter in Python after fetching
            pass

        # Get total count
        count_query = select(WorkflowList).where(WorkflowList.user_key == user_key)
        count_result = await self.db.execute(count_query)
        total = len(count_result.scalars().all())

        # Get lists
        query = query.order_by(
            WorkflowList.is_default.desc(),
            WorkflowList.name
        ).offset(offset).limit(limit)
        result = await self.db.execute(query)
        workflow_lists = list(result.scalars().all())

        # Filter by tags in Python if needed (for SQLite compatibility)
        if tags:
            workflow_lists = [
                wl for wl in workflow_lists
                if any(tag in (wl.tags or []) for tag in tags)
            ]
            total = len(workflow_lists)

        return workflow_lists, total

    async def search_workflow_lists(
        self,
        query: str,
        user_key: str = "default",
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[List[WorkflowList], int]:
        """
        Search workflow lists by name or description (case-insensitive).

        Args:
            query: Search string to match against name or description
            user_key: User identifier
            tags: Optional list of tags to filter by
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            Tuple of (matching workflow lists, total count)
        """
        search_pattern = f"%{query}%"

        # Build query with search filter
        query_stmt = (
            select(WorkflowList)
            .where(WorkflowList.user_key == user_key)
            .where(
                WorkflowList.name.ilike(search_pattern)
                | WorkflowList.description.ilike(search_pattern)
            )
        )

        # Get total count
        count_result = await self.db.execute(query_stmt)
        all_matching = list(count_result.scalars().all())

        # Filter by tags in Python if needed
        if tags:
            all_matching = [
                wl for wl in all_matching
                if any(tag in (wl.tags or []) for tag in tags)
            ]

        total = len(all_matching)

        # Apply pagination
        workflow_lists = all_matching[offset:offset + limit]
        workflow_lists.sort(
            key=lambda wl: (not wl.is_default, wl.name or "")
        )

        return workflow_lists, total

    async def get_workflow_list(self, list_id: str) -> Optional[WorkflowList]:
        """
        Get a single workflow list by ID.

        Args:
            list_id: Workflow list ID

        Returns:
            WorkflowList or None
        """
        query = select(WorkflowList).where(WorkflowList.id == list_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_default_workflow_list(self, user_key: str = "default") -> Optional[WorkflowList]:
        """
        Get the default workflow list for a user.

        Args:
            user_key: User identifier

        Returns:
            Default WorkflowList or None
        """
        query = select(WorkflowList).where(
            WorkflowList.user_key == user_key,
            WorkflowList.is_default
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_workflows_in_list(self, list_id: str) -> List[Dict[str, Any]]:
        """
        Get all workflows in a workflow list.

        Args:
            list_id: Workflow list ID

        Returns:
            List of workflow template dictionaries
        """
        workflow_list = await self.get_workflow_list(list_id)
        if not workflow_list or not workflow_list.workflow_ids:
            return []

        # Query SQLite for workflow templates
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            placeholders = ','.join('?' * len(workflow_list.workflow_ids))
            cursor.execute(f"""
                SELECT id, name, description, version, tags
                FROM workflow_templates
                WHERE id IN ({placeholders})
            """, workflow_list.workflow_ids)
            
            rows = cursor.fetchall()
            workflows = []
            
            for row in rows:
                workflows.append({
                    "template_id": row["id"],
                    "name": row["name"],
                    "description": row["description"],
                    "version": row["version"],
                    "tags": json.loads(row["tags"]) if row["tags"] else [],
                })
            
            return workflows
        finally:
            conn.close()

    async def create_workflow_list(self, data: WorkflowListCreate) -> WorkflowList:
        """
        Create a new workflow list.

        Args:
            data: Workflow list creation data

        Returns:
            Created WorkflowList
        """
        # If this is set as default, unset other defaults
        if data.is_default:
            await self.db.execute(
                update(WorkflowList)
                .where(WorkflowList.user_key == data.user_key)
                .values(is_default=False)
            )

        workflow_list = WorkflowList(
            id=str(uuid.uuid4()),
            name=data.name,
            description=data.description,
            user_key=data.user_key,
            workflow_ids=data.workflow_ids,
            is_default=data.is_default,
            tags=data.tags or [],
        )

        self.db.add(workflow_list)
        await self.db.commit()
        await self.db.refresh(workflow_list)

        logger.info(f"Created workflow list: {workflow_list.name} ({workflow_list.id})")
        return workflow_list

    async def update_workflow_list(
        self,
        list_id: str,
        data: WorkflowListUpdate
    ) -> Optional[WorkflowList]:
        """
        Update an existing workflow list.

        Args:
            list_id: Workflow list ID
            data: Workflow list update data

        Returns:
            Updated WorkflowList or None
        """
        # Check if list exists
        existing = await self.get_workflow_list(list_id)
        if not existing:
            return None

        # If setting as default, unset other defaults
        if data.is_default and not existing.is_default:
            await self.db.execute(
                update(WorkflowList)
                .where(WorkflowList.user_key == existing.user_key)
                .where(WorkflowList.id != list_id)
                .values(is_default=False)
            )

        # Update fields
        update_data = {
            k: v for k, v in data.model_dump().items()
            if v is not None
        }

        if update_data:
            await self.db.execute(
                update(WorkflowList)
                .where(WorkflowList.id == list_id)
                .values(**update_data)
            )
            await self.db.commit()

        # Refresh and return
        await self.db.refresh(existing)
        return existing

    async def delete_workflow_list(self, list_id: str) -> bool:
        """
        Delete a workflow list.

        Args:
            list_id: Workflow list ID

        Returns:
            True if deleted, False if not found
        """
        workflow_list = await self.get_workflow_list(list_id)
        if not workflow_list:
            return False

        # Don't allow deleting the last default list
        if workflow_list.is_default:
            count_query = select(WorkflowList).where(
                WorkflowList.user_key == workflow_list.user_key,
                WorkflowList.is_default
            )
            count_result = await self.db.execute(count_query)
            if len(count_result.scalars().all()) <= 1:
                raise ValueError("Cannot delete the last default workflow list")

        await self.db.execute(
            delete(WorkflowList).where(WorkflowList.id == list_id)
        )
        await self.db.commit()

        logger.info(f"Deleted workflow list: {list_id}")
        return True

    async def add_workflow_to_list(
        self,
        list_id: str,
        workflow_id: str,
        position: Optional[int] = None
    ) -> Optional[WorkflowList]:
        """
        Add a workflow to a workflow list.

        Args:
            list_id: Workflow list ID
            workflow_id: Workflow template ID to add
            position: Position to insert (None for append)

        Returns:
            Updated WorkflowList or None
        """
        workflow_list = await self.get_workflow_list(list_id)
        if not workflow_list:
            return None

        # Don't add duplicates
        if workflow_id in (workflow_list.workflow_ids or []):
            return workflow_list

        workflow_ids = list(workflow_list.workflow_ids or [])  # Copy to trigger change detection
        if position is not None and 0 <= position <= len(workflow_ids):
            workflow_ids.insert(position, workflow_id)
        else:
            workflow_ids.append(workflow_id)

        workflow_list.workflow_ids = workflow_ids
        workflow_list.updated_at = datetime.now(UTC)

        await self.db.commit()
        await self.db.refresh(workflow_list)

        logger.info(f"Added workflow {workflow_id} to list {list_id}")
        return workflow_list

    async def remove_workflow_from_list(
        self,
        list_id: str,
        workflow_id: str
    ) -> Optional[WorkflowList]:
        """
        Remove a workflow from a workflow list.

        Args:
            list_id: Workflow list ID
            workflow_id: Workflow template ID to remove

        Returns:
            Updated WorkflowList or None
        """
        workflow_list = await self.get_workflow_list(list_id)
        if not workflow_list:
            return None

        if workflow_id not in (workflow_list.workflow_ids or []):
            return workflow_list

        assert workflow_list.workflow_ids is not None
        workflow_list.workflow_ids = [
            wid for wid in workflow_list.workflow_ids if wid != workflow_id
        ]
        workflow_list.updated_at = datetime.now(UTC)

        await self.db.commit()
        await self.db.refresh(workflow_list)

        logger.info(f"Removed workflow {workflow_id} from list {list_id}")
        return workflow_list

    def to_response(self, workflow_list: WorkflowList) -> WorkflowListResponse:
        """Convert WorkflowList to response schema."""
        return WorkflowListResponse(
            id=workflow_list.id,
            name=workflow_list.name,
            description=workflow_list.description,
            user_key=workflow_list.user_key,
            workflow_ids=workflow_list.workflow_ids or [],
            workflow_count=len(workflow_list.workflow_ids or []),
            is_default=workflow_list.is_default,
            tags=workflow_list.tags or [],
            created_at=workflow_list.created_at,
            updated_at=workflow_list.updated_at,
        )

    def workflow_to_response(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Convert workflow template dict to response schema."""
        return {
            "template_id": workflow.get("template_id", ""),
            "name": workflow.get("name", ""),
            "description": workflow.get("description"),
            "version": workflow.get("version", "1.0.0"),
            "tags": workflow.get("tags", []),
        }
