"""
Agent Registry service.

DB-backed agent package registry with CRUD operations, lifecycle status
management, and versioning lineage via parent_version_id.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import FrontendAgentPackage
from app.domain.agent_registry.schemas import (
    AGENT_LIFECYCLE_STATUSES,
    AgentPackageCreate,
    AgentPackageUpdate,
    AgentPackageResponse,
    AgentPackageListResponse,
    AgentPackageVersionResponse,
    AgentPackageLineageResponse,
)

logger = logging.getLogger(__name__)


class AgentRegistryService:
    """
    Service for managing DB-backed agent packages.

    Provides CRUD operations, lifecycle status transitions,
    and versioning lineage tracking.
    """

    VALID_STATUS_TRANSITIONS = {
        "experimental": {"active", "archived", "deprecated"},
        "active": {"experimental", "archived", "deprecated"},
        "archived": {"active", "deprecated"},
        "deprecated": {"archived"},  # Can be archived but not reactivated
    }

    def __init__(self, db: AsyncSession):
        """
        Initialize the agent registry service.

        Args:
            db: Async database session
        """
        self.db = db

    # ── CRUD Operations ───────────────────────────────────────────────────

    async def create(self, data: AgentPackageCreate) -> FrontendAgentPackage:
        """
        Create a new agent package.

        Args:
            data: Package creation data

        Returns:
            Created FrontendAgentPackage

        Raises:
            ValueError: If status is invalid or name already exists
        """
        # Validate status
        if data.status not in AGENT_LIFECYCLE_STATUSES:
            raise ValueError(
                f"Invalid status '{data.status}'. "
                f"Must be one of: {', '.join(sorted(AGENT_LIFECYCLE_STATUSES))}"
            )

        # Check for duplicate name
        existing = await self._get_by_name(data.name)
        if existing:
            raise ValueError(
                f"Agent package with name '{data.name}' already exists (id={existing.id})"
            )

        # Validate parent_version_id if provided
        if data.parent_version_id is not None:
            parent = await self.get_by_id(data.parent_version_id)
            if not parent:
                raise ValueError(
                    f"Parent version with id={data.parent_version_id} not found"
                )

        package = FrontendAgentPackage(
            name=data.name,
            role=data.role,
            version=data.version,
            status=data.status,
            system_prompt=data.system_prompt,
            code=data.code,
            tools_schema=data.tools_schema,
            parent_version_id=data.parent_version_id,
            package_metadata=data.package_metadata or {},
        )

        self.db.add(package)
        await self.db.flush()
        await self.db.refresh(package)

        logger.info(
            "Created agent package: %s (id=%d, version=%s, status=%s)",
            package.name, package.id, package.version, package.status,
        )
        return package

    async def get_by_id(
        self, package_id: int
    ) -> Optional[FrontendAgentPackage]:
        """
        Get an agent package by ID.

        Args:
            package_id: Package ID

        Returns:
            FrontendAgentPackage if found, None otherwise
        """
        query = select(FrontendAgentPackage).where(
            FrontendAgentPackage.id == package_id
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_name(
        self, name: str
    ) -> Optional[FrontendAgentPackage]:
        """
        Get an agent package by name.

        Args:
            name: Package name

        Returns:
            FrontendAgentPackage if found, None otherwise
        """
        return await self._get_by_name(name)

    async def _get_by_name(
        self, name: str
    ) -> Optional[FrontendAgentPackage]:
        """Internal: get by name without logging."""
        query = select(FrontendAgentPackage).where(
            FrontendAgentPackage.name == name
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        search: Optional[str] = None,
        role: Optional[str] = None,
    ) -> AgentPackageListResponse:
        """
        List agent packages with filtering and pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum records to return
            status: Filter by lifecycle status
            search: Search in name and role (case-insensitive)
            role: Filter by role

        Returns:
            AgentPackageListResponse with items and total count
        """
        # Build base query
        base_query = select(FrontendAgentPackage)

        # Apply filters
        if status:
            if status not in AGENT_LIFECYCLE_STATUSES:
                raise ValueError(
                    f"Invalid status '{status}'. "
                    f"Must be one of: {', '.join(sorted(AGENT_LIFECYCLE_STATUSES))}"
                )
            base_query = base_query.where(
                FrontendAgentPackage.status == status
            )

        if search:
            like_pattern = f"%{search}%"
            base_query = base_query.where(
                or_(
                    FrontendAgentPackage.name.ilike(like_pattern),
                    FrontendAgentPackage.role.ilike(like_pattern),
                )
            )

        if role:
            base_query = base_query.where(
                FrontendAgentPackage.role == role
            )

        # Get total count
        count_query = select(func.count()).select_from(
            base_query.subquery()
        )
        total = await self.db.scalar(count_query) or 0

        # Get paginated results
        query = (
            base_query
            .offset(skip)
            .limit(limit)
            .order_by(FrontendAgentPackage.name)
        )
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return AgentPackageListResponse(
            items=[AgentPackageResponse.model_validate(pkg) for pkg in items],
            total=total,
            skip=skip,
            limit=limit,
        )

    async def update(
        self, package_id: int, data: AgentPackageUpdate
    ) -> Optional[FrontendAgentPackage]:
        """
        Update an existing agent package.

        Args:
            package_id: Package ID to update
            data: Update data (only provided fields are updated)

        Returns:
            Updated FrontendAgentPackage if found, None otherwise
        """
        package = await self.get_by_id(package_id)
        if not package:
            return None

        update_data = data.model_dump(exclude_unset=True)

        # Validate status transition
        if "status" in update_data:
            new_status = update_data["status"]
            if new_status not in AGENT_LIFECYCLE_STATUSES:
                raise ValueError(
                    f"Invalid status '{new_status}'. "
                    f"Must be one of: {', '.join(sorted(AGENT_LIFECYCLE_STATUSES))}"
                )
            allowed = self.VALID_STATUS_TRANSITIONS.get(package.status, set())
            if new_status not in allowed:
                raise ValueError(
                    f"Cannot transition from '{package.status}' to '{new_status}'. "
                    f"Allowed transitions: {', '.join(sorted(allowed)) if allowed else 'none'}"
                )

            # Set archived_at timestamp when archiving
            if new_status == "archived":
                package.archived_at = datetime.now(timezone.utc)

        # Validate name uniqueness if changing name
        if "name" in update_data and update_data["name"] != package.name:
            existing = await self._get_by_name(update_data["name"])
            if existing:
                raise ValueError(
                    f"Agent package with name '{update_data['name']}' "
                    f"already exists (id={existing.id})"
                )

        # Apply updates
        for field, value in update_data.items():
            setattr(package, field, value)

        await self.db.flush()
        await self.db.refresh(package)

        logger.info(
            "Updated agent package: %s (id=%d, status=%s)",
            package.name, package.id, package.status,
        )
        return package

    async def delete(self, package_id: int) -> bool:
        """
        Delete an agent package by ID.

        Args:
            package_id: Package ID to delete

        Returns:
            True if deleted, False if not found
        """
        package = await self.get_by_id(package_id)
        if not package:
            return False

        await self.db.delete(package)
        await self.db.flush()

        logger.info(
            "Deleted agent package: %s (id=%d)",
            package.name, package.id,
        )
        return True

    # ── Lifecycle Management ──────────────────────────────────────────────

    async def set_status(
        self, package_id: int, new_status: str
    ) -> Optional[FrontendAgentPackage]:
        """
        Change the lifecycle status of an agent package.

        Validates the transition is allowed.

        Args:
            package_id: Package ID
            new_status: Target status

        Returns:
            Updated FrontendAgentPackage if found, None otherwise
        """
        return await self.update(
            package_id,
            AgentPackageUpdate(status=new_status),
        )

    async def get_active_packages(
        self, limit: int = 100
    ) -> List[FrontendAgentPackage]:
        """
        Get all active agent packages.

        Args:
            limit: Maximum records to return

        Returns:
            List of active FrontendAgentPackage objects
        """
        query = (
            select(FrontendAgentPackage)
            .where(FrontendAgentPackage.status == "active")
            .limit(limit)
            .order_by(FrontendAgentPackage.name)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    # ── Versioning Lineage ────────────────────────────────────────────────

    async def get_lineage(
        self, package_id: int
    ) -> Optional[AgentPackageLineageResponse]:
        """
        Get the full lineage tree (ancestors + descendants) for a package.

        Args:
            package_id: Package ID

        Returns:
            AgentPackageLineageResponse if package found, None otherwise
        """
        package = await self.get_by_id(package_id)
        if not package:
            return None

        # Walk ancestors (parent chain)
        ancestors: List[AgentPackageVersionResponse] = []
        current_parent_id = package.parent_version_id
        while current_parent_id is not None:
            parent = await self.get_by_id(current_parent_id)
            if parent:
                ancestors.append(
                    AgentPackageVersionResponse.model_validate(parent)
                )
                current_parent_id = parent.parent_version_id
            else:
                break

        # Walk descendants (children chain)
        descendants: List[AgentPackageVersionResponse] = []
        await self._collect_descendants(package_id, descendants)

        return AgentPackageLineageResponse(
            package=AgentPackageResponse.model_validate(package),
            ancestors=ancestors,
            descendants=descendants,
        )

    async def _collect_descendants(
        self, parent_id: int, result: List[AgentPackageVersionResponse]
    ) -> None:
        """Recursively collect all descendants of a package."""
        query = select(FrontendAgentPackage).where(
            FrontendAgentPackage.parent_version_id == parent_id
        )
        rows = await self.db.execute(query)
        children = list(rows.scalars().all())

        for child in children:
            result.append(AgentPackageVersionResponse.model_validate(child))
            await self._collect_descendants(child.id, result)

    async def create_version(
        self,
        source_package_id: int,
        new_name: Optional[str] = None,
        new_version: Optional[str] = None,
        code: Optional[str] = None,
        system_prompt: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FrontendAgentPackage:
        """
        Create a new version derived from an existing package.

        The new package will have parent_version_id pointing to the source.

        Args:
            source_package_id: Source package ID to derive from
            new_name: Optional new name (defaults to source name + version)
            new_version: Version string for the new package
            code: Optional new code (inherits from source if not provided)
            system_prompt: Optional new system prompt (inherits from source)
            metadata: Optional metadata for the new version

        Returns:
            Created FrontendAgentPackage

        Raises:
            ValueError: If source package not found
        """
        source = await self.get_by_id(source_package_id)
        if not source:
            raise ValueError(f"Source package {source_package_id} not found")

        create_data = AgentPackageCreate(
            name=new_name or f"{source.name}-v{new_version or 'next'}",
            role=source.role,
            version=new_version or source.version,
            status="experimental",  # New versions start as experimental
            system_prompt=system_prompt or source.system_prompt,
            code=code or source.code,
            tools_schema=source.tools_schema,
            parent_version_id=source_package_id,
            metadata=metadata or {},
        )

        return await self.create(create_data)

    # ── Bulk Operations ───────────────────────────────────────────────────

    async def archive_all_by_role(self, role: str) -> int:
        """
        Archive all active/experimental packages with a given role.

        Args:
            role: Role to archive

        Returns:
            Number of packages archived
        """
        query = select(FrontendAgentPackage).where(
            FrontendAgentPackage.role == role,
            FrontendAgentPackage.status.in_(["active", "experimental"]),
        )
        result = await self.db.execute(query)
        packages = list(result.scalars().all())

        now = datetime.now(timezone.utc)
        count = 0
        for pkg in packages:
            pkg.status = "archived"
            pkg.archived_at = now
            count += 1

        if count > 0:
            await self.db.flush()
            logger.info("Archived %d packages with role '%s'", count, role)

        return count
