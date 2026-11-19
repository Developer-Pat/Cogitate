"""Provision the expertise tools to the Cogitate agents.

The repurpose: the capabilities built for Exa serve the framework's OWN agents — one capability, two
consumers. The registry is the shared surface; this script assigns the read/verify tools to the active
agents.

EXCLUDED: restart-backend (admin-tier — the Exa-only gate; the
Cogitate agents don't get raw restart power).

Idempotent: re-running is safe (enable_tool_for_agent updates).
"""

from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent.parent))

from sqlalchemy import select

from app.core.dependencies import get_db
from app.domain.tools.services import AgentToolService
from app.domain.tools.models import Tool
from app.infrastructure.database.models import Agent

# the expertise tool slugs the agents get (restart-backend excluded)
EXPERTISE_TOOLS = [
    "graph-query",
    "search-knowledge",
    "verify-backend-health",
    "verify-trigger-config",
    "set-trigger-schedule",
]


async def main() -> int:
    async for db in get_db():
        tool_svc = AgentToolService(db)
        # the active agents
        agents = (
            (await db.execute(
                select(Agent).where(Agent.is_active == True).order_by(Agent.id)  # noqa: E712
            )).scalars().all()
        )
        # the tool ids
        tools = {}
        for slug in EXPERTISE_TOOLS:
            tool = (
                (await db.execute(select(Tool).where(Tool.slug == slug))).scalars().first()
            )
            if tool is not None:
                tools[slug] = tool.id
        if not tools:
            print("⚠ no expertise tools found in the registry")
            return 1

        print(f"Assigning {len(tools)} expertise tools to {len(agents)} active agents...")
        for agent in agents:
            for slug, tool_id in tools.items():
                try:
                    await tool_svc.enable_tool_for_agent(agent.id, tool_id)
                except Exception as e:  # noqa: BLE001
                    print(f"  ⚠ {agent.name} + {slug}: {e}")
            print(f"  ✅ {agent.name} (id {agent.id})")
        print("✅ the expertise tools are provisioned to the agents")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
