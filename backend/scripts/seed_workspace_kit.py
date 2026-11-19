#!/usr/bin/env python3
"""The Workspace Kit seed: the SECOND toolkit (the write/state surface).

Creates the workspace kit, MOVES the 3 write tools out of the Search Kit's permissions (the
functional split — the user's intent), and grants file-info + datetime too. Attaches BOTH kits to
Bob (agent 19, the agent_kits join). Idempotent — safe to re-run.

Usage:
    cd backend && python scripts/seed_workspace_kit.py
"""

import asyncio
import logging
import uuid

from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal, init_db
from app.domain.collections.models import Collection, CollectionItem
from app.domain.tools.models import Tool
from app.domain.tools.tool_permission_models import ToolCollectionPermission
from app.infrastructure.database.models import Agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_workspace_kit")

WORKSPACE_KIT_NAME = "Workspace Kit"
SEARCH_KIT_NAME = "Search Kit"
# the tools that MOVE (out of the Search Kit, into the Workspace Kit)
WRITE_TOOLS = ["file-manager", "update-sources", "update-state"]
# the extras approved at the build (the roadmap candidates)
WORKSPACE_TOOLS = WRITE_TOOLS + ["file-info", "datetime"]
BOB_NAME = "Bob"


async def run() -> None:
    await init_db()
    async with AsyncSessionLocal() as db:
        # ---- 1. find-or-create the Workspace Kit ----
        kit = (
            await db.execute(
                select(Collection).where(
                    Collection.name == WORKSPACE_KIT_NAME, Collection.entity_type == "tool"
                )
            )
        ).scalar_one_or_none()
        if kit is None:
            kit = Collection(
                id=str(uuid.uuid4()),
                user_key="default",
                name=WORKSPACE_KIT_NAME,
                entity_type="tool",
                description="The write/state toolkit — the agent's folder, beats, and facts",
                is_active=True,
            )
            db.add(kit)
            await db.flush()
            logger.info("created the Workspace Kit (%s)", kit.id)

        search_kit = (
            await db.execute(
                select(Collection).where(
                    Collection.name == SEARCH_KIT_NAME, Collection.entity_type == "tool"
                )
            )
        ).scalar_one_or_none()

        # ---- 2. grant the workspace tools (idempotent) ----
        tools = {
            (await db.execute(select(Tool).where(Tool.slug == slug))).scalar_one_or_none(): slug
            for slug in WORKSPACE_TOOLS
        }
        for tool_row, slug in tools.items():
            if tool_row is None:
                logger.warning("tool %s missing — skipped", slug)
                continue
            # THE UUID CONVENTION: tools.id is stored as uuid4().hex
            # (NO dashes — the seeded records) while the ORM's Uuid
            # type reads it back DASHED. The permissions' String(36)
            # tool_id must match the STORED form or the FK fails.
            tool_id = tool_row.id.replace("-", "")
            existing = (
                await db.execute(
                    select(ToolCollectionPermission).where(
                        ToolCollectionPermission.collection_id == kit.id,
                        ToolCollectionPermission.tool_id == tool_id,
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                db.add(
                    ToolCollectionPermission(
                        id=str(uuid.uuid4()),
                        collection_id=kit.id,
                        tool_id=tool_id,
                        permission_level="read",
                    )
                )
                logger.info("granted %s -> Workspace Kit", slug)

        # ---- 2b. the visible ITEMS (mirror the Search Kit's pattern:
        # the toolkit page shows the tools as collection items; the
        # execution surface reads the permissions above). ----
        from app.domain.collections.models import CollectionItem as _CI

        for tool_row, slug in tools.items():
            if tool_row is None:
                continue
            entity_id = tool_row.id.replace("-", "")
            existing_item = (
                await db.execute(
                    select(_CI).where(
                        _CI.collection_id == kit.id,
                        _CI.entity_type == "tool",
                        _CI.entity_id == entity_id,
                    )
                )
            ).scalar_one_or_none()
            if existing_item is None:
                db.add(
                    _CI(
                        id=str(uuid.uuid4()),
                        collection_id=kit.id,
                        entity_id=entity_id,
                        entity_type="tool",
                        entity_name=tool_row.name or slug,
                    )
                )
                logger.info("item %s -> Workspace Kit (the visible list)", slug)

        # ---- 3. MOVE: remove the 3 write tools from the Search Kit ----
        if search_kit is not None:
            write_ids = [t.id.replace("-", "") for t, _ in tools.items() if t is not None]
            removed = await db.execute(
                delete(ToolCollectionPermission).where(
                    ToolCollectionPermission.collection_id == search_kit.id,
                    ToolCollectionPermission.tool_id.in_(write_ids),
                )
            )
            if removed.rowcount:
                logger.info("MOVED %d write tool(s) out of the Search Kit", removed.rowcount)

        # ---- 4. attach BOTH kits to Bob (the join) ----
        from app.domain.agent_kits.service import AgentKitService

        svc = AgentKitService(db)
        bob = (await db.execute(select(Agent).where(Agent.name == BOB_NAME))).scalar_one_or_none()
        if bob is None:
            logger.warning("agent %s not found — attach skipped (add the kit rows manually)", BOB_NAME)
        else:
            for owned_kit in (search_kit, kit):
                if owned_kit is None:
                    continue
                if await svc.attach(bob.id, owned_kit.id):
                    logger.info("attached %s -> Bob (%s)", owned_kit.name, bob.id)

        await db.commit()

        # ---- 5. the summary ----
        print()
        print(f"Workspace Kit: {kit.id}")
        print(f"Search Kit:    {search_kit.id if search_kit else 'MISSING'}")
        print(f"Bob (id {bob.id if bob else '?'}): {BOB_NAME}")
        if bob is not None:
            owned = await svc.kits_for_agent(bob.id)
            for k in owned:
                print(f"  owns {k.name}")
        print("re-run safe (idempotent)")


if __name__ == "__main__":
    asyncio.run(run())
