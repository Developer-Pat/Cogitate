import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.agent_kits.model import AgentKit
from app.domain.collections.models import Collection
from app.infrastructure.database.models import Agent

logger = logging.getLogger(__name__)


class AgentKitService:
    """THE KIT-OWNERSHIP REPOSITORY (2026-09-04, the agent-kits
    build P1): the agent_kits JOIN operations — attach/detach,
    both directions (kits-for-agent / agents-for-kit), and the
    SLOT SYNC (the migration from the singular agents.kit_id).
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def attach(self, agent_id: int, kit_id: str) -> bool:
        """Idempotently attach a KIT (a tool-typed collection) to
        an agent. Returns True when the row was created (False = it
        already existed or the kit is not a tool-typed collection).
        """
        # the kit must be a real tool-typed collection
        kit = await self.db.get(Collection, kit_id)
        if kit is None or kit.entity_type != "tool":
            logger.warning("AgentKitService.attach: %s is not a tool-typed collection", kit_id)
            return False
        existing = await self.db.get(AgentKit, {"agent_id": agent_id, "kit_id": kit_id})
        if existing is not None:
            return False
        self.db.add(AgentKit(agent_id=agent_id, kit_id=kit_id))
        await self.db.flush()
        return True

    async def detach(self, agent_id: int, kit_id: str) -> bool:
        """Remove the kit from the agent. Returns True when a row
        was removed.
        """
        result = await self.db.execute(
            delete(AgentKit).where(AgentKit.agent_id == agent_id, AgentKit.kit_id == kit_id)
        )
        await self.db.flush()
        # `rowcount` lives on CursorResult, not on the Result base the async
        # execute() is declared to return.
        return (getattr(result, "rowcount", 0) or 0) > 0

    async def kits_for_agent(self, agent_id: int) -> list[Collection]:
        """The toolkits the agent owns (the Collection rows)."""
        rows = await self.db.execute(
            select(Collection)
            .join(AgentKit, AgentKit.kit_id == Collection.id)
            .where(AgentKit.agent_id == agent_id, Collection.entity_type == "tool")
            .order_by(Collection.name)
        )
        return list(rows.scalars().all())

    async def agents_for_kit(self, kit_id: str) -> list[int]:
        """The agent ids that own the kit."""
        rows = await self.db.execute(
            select(AgentKit.agent_id).where(AgentKit.kit_id == kit_id).order_by(AgentKit.agent_id)
        )
        return list(rows.scalars().all())

    async def sync_from_agent_slots(self) -> int:
        """THE SLOT MIGRATION (the agent-kits build P1): every
        agent with the singular kit_id set gains a JOIN row
        (idempotent — missing rows only). Returns the count of
        rows created. Runs at the app boot (main.py lifespan)
        and in tests — the join converges from the old slot.
        """
        rows = await self.db.execute(
            select(Agent.id, Agent.kit_id).where(Agent.kit_id.is_not(None))
        )
        created = 0
        for agent_id, kit_id in rows.all():
            existing = await self.db.get(AgentKit, {"agent_id": agent_id, "kit_id": kit_id})
            if existing is None:
                kit = await self.db.get(Collection, kit_id)
                if kit is None or kit.entity_type != "tool":
                    continue  # a dangling/non-tool reference — leave it for the slot
                self.db.add(AgentKit(agent_id=agent_id, kit_id=kit_id))
                created += 1
        if created:
            await self.db.flush()
            logger.info("AgentKitService: %d agent-kit row(s) synced from the kit slots", created)
        return created
