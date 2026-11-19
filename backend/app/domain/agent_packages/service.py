"""
Agent Packages domain service.

CRUD for the package blueprints (Phase 1 of the agent-package
roadmap). The ADOPT action (copying into an agent's OWN fields)
is Phase 2 — this service only manages the blueprints.
"""

import logging
import uuid
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.agent_packages.models import AgentPackage
from app.domain.agent_packages.schemas import (
    AgentPackageCreate,
    AgentPackageUpdate,
)

logger = logging.getLogger(__name__)


class AgentPackageService:
    """Service for managing agent package blueprints."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_package(self, data: AgentPackageCreate) -> AgentPackage:
        """Create a package blueprint (the id is client-assigned)."""
        pkg = AgentPackage(
            id=str(uuid.uuid4()),
            name=data.name,
            description=data.description,
            kit_id=data.kit_id,
            skills=data.skills or [],
            llm_spec=data.llm_spec.model_dump() if data.llm_spec else None,
        )
        self.db.add(pkg)
        await self.db.commit()
        await self.db.refresh(pkg)
        return pkg

    async def list_packages(self, include_inactive: bool = False) -> List[AgentPackage]:
        """List the packages (active by default)."""
        stmt = select(AgentPackage).order_by(AgentPackage.name)
        if not include_inactive:
            stmt = stmt.where(AgentPackage.is_active == True)  # noqa: E712
        rows = await self.db.execute(stmt)
        return list(rows.scalars().all())

    async def get_package(self, package_id: str) -> Optional[AgentPackage]:
        """Get one package by id."""
        row = await self.db.execute(
            select(AgentPackage).where(AgentPackage.id == package_id)
        )
        return row.scalar_one_or_none()

    async def get_package_by_name(self, name: str) -> Optional[AgentPackage]:
        """Get a package by name (the seed + Exa lookup path)."""
        row = await self.db.execute(
            select(AgentPackage).where(AgentPackage.name == name)
        )
        return row.scalar_one_or_none()

    async def update_package(
        self, package_id: str, data: AgentPackageUpdate
    ) -> Optional[AgentPackage]:
        """Update a package (partial)."""
        pkg = await self.get_package(package_id)
        if not pkg:
            return None
        if data.name is not None:
            pkg.name = data.name
        if data.description is not None:
            pkg.description = data.description
        if data.kit_id is not None:
            pkg.kit_id = data.kit_id
        if data.skills is not None:
            pkg.skills = data.skills
        if data.llm_spec is not None:
            pkg.llm_spec = data.llm_spec.model_dump()
        if data.is_active is not None:
            pkg.is_active = data.is_active
        await self.db.commit()
        await self.db.refresh(pkg)
        return pkg

    async def delete_package(self, package_id: str) -> bool:
        """Delete a package. The provisioned agents keep their OWN
        copies — the package is a blueprint, never a dependency."""
        pkg = await self.get_package(package_id)
        if not pkg:
            return False
        await self.db.delete(pkg)
        await self.db.commit()
        return True

    async def count(self) -> int:
        """Total package count (the seed check)."""
        row = await self.db.execute(select(func.count()).select_from(AgentPackage))
        return row.scalar_one()
