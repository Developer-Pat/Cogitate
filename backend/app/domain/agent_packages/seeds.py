"""
Agent package seeds (Phase 1 — the canned blueprints).

The shallow-agent package: the policy the user described — "a new
shallow agent gets a toolkit/skillset designed for new shallow
agents." The seed is IDEMPOTENT (startup-safe): it creates the
kit + the package only when missing.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.collections.models import Collection
from app.domain.agent_packages.models import AgentPackage

logger = logging.getLogger(__name__)

SHALLOW_KIT_NAME = "Shallow Agent Kit"
SHALLOW_PACKAGE_NAME = "shallow-agent"

# THE SHALLOW SPEC: a chat bot — non-thinking, local, small context.
SHALLOW_LLM_SPEC = {
    "kind": "chat",
    "thinking": "none",
    "location": "local",
    "min_context": 4096,
    # THE TYPE DEFAULT (F.1): the number an agent adopted from this package inherits
    # when its own row declares no budget — the ladder's shallow class (F.2's table).
    "max_output": 8192,
}

SHALLOW_SKILLS = ["greeting"]


async def seed_agent_packages(db: AsyncSession) -> None:
    """Create the canned packages (idempotent). Called at startup."""
    # 1. the shallow kit: an EMPTY tool-typed collection — the
    #    toolkit policy gives its owner ZERO tools (the Bob fix: a
    #    shallow bot has nothing to hallucinate).
    kit_row = await db.execute(
        select(Collection).where(Collection.name == SHALLOW_KIT_NAME)
    )
    kit = kit_row.scalar_one_or_none()
    if not kit:
        kit = Collection(
            id=str(uuid.uuid4()),
            user_key="default",
            name=SHALLOW_KIT_NAME,
            description="The empty toolkit for shallow agents — the surface is deliberately minimal.",
            entity_type="tool",
        )
        db.add(kit)
        await db.flush()
        logger.info("Seeded the shallow-agent kit (%s)", kit.id)

    # 2. the shallow-agent package referencing the kit
    pkg_row = await db.execute(
        select(AgentPackage).where(AgentPackage.name == SHALLOW_PACKAGE_NAME)
    )
    pkg = pkg_row.scalar_one_or_none()
    if not pkg:
        pkg = AgentPackage(
            id=str(uuid.uuid4()),
            name=SHALLOW_PACKAGE_NAME,
            description="The shallow-agent package: a chat bot with a deliberately minimal surface.",
            kit_id=kit.id,
            skills=SHALLOW_SKILLS,
            llm_spec=SHALLOW_LLM_SPEC,
        )
        db.add(pkg)
        await db.flush()
        logger.info("Seeded the shallow-agent package (%s)", pkg.id)

    await db.commit()
