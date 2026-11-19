"""The a-key seed creates the meta-topic, stays idempotent, and never clobbers user edits.

Pin the seed's contract:
1. It CREATES the 'A-Key Macros' meta-topic + the 5 starter sets
   when they are missing.
2. It is IDEMPOTENT — a second run creates nothing new.
3. It NEVER clobbers user edits (a pre-existing meta-topic or set
   is left exactly as-is).
"""
import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.macros.seeds import (
    AKEYS_META_TOPIC_NAME,
    AKEYS_SETS,
    seed_akeys_macros,
)
from app.infrastructure.database.models import MacroSet, MetaTopic


@pytest.fixture
async def seeded(test_session: AsyncSession, auto_clean_tables) -> None:  # noqa: ANN001
    await seed_akeys_macros(test_session)


async def _count(session: AsyncSession, model, **filters) -> int:  # noqa: ANN001
    stmt = select(model)
    for col, val in filters.items():
        stmt = stmt.where(getattr(model, col) == val)
    rows = await session.execute(stmt)
    return len(rows.scalars().all())


async def test_seed_creates_the_meta_topic_and_sets(seeded, test_session: AsyncSession) -> None:  # noqa: ANN001
    assert await _count(test_session, MetaTopic, name=AKEYS_META_TOPIC_NAME) == 1
    mt = (await test_session.execute(select(MetaTopic).where(MetaTopic.name == AKEYS_META_TOPIC_NAME))).scalar_one()
    mappings = json.loads(mt.topic_mappings) if isinstance(mt.topic_mappings, str) else mt.topic_mappings
    assert len(mappings) == 5  # A1-A5
    assert mappings[0]["slot_start"] == "A1"
    for data in AKEYS_SETS:
        assert await _count(test_session, MacroSet, user_key="default", topic=data["topic"], name=data["name"]) == 1


async def test_seed_is_idempotent(seeded, test_session: AsyncSession) -> None:  # noqa: ANN001
    await seed_akeys_macros(test_session)
    assert await _count(test_session, MetaTopic, name=AKEYS_META_TOPIC_NAME) == 1
    for data in AKEYS_SETS:
        assert await _count(test_session, MacroSet, user_key="default", topic=data["topic"], name=data["name"]) == 1


async def test_seed_never_clobbers_user_edits(seeded, test_session: AsyncSession) -> None:  # noqa: ANN001
    modes = (await test_session.execute(
        select(MacroSet).where(MacroSet.topic == "Modes", MacroSet.name == "Mode switches")
    )).scalar_one()
    modes.f1_macro = "USER'S CUSTOM MODE PROMPT"
    await test_session.commit()

    await seed_akeys_macros(test_session)
    modes2 = (await test_session.execute(
        select(MacroSet).where(MacroSet.topic == "Modes", MacroSet.name == "Mode switches")
    )).scalar_one()
    assert modes2.f1_macro == "USER'S CUSTOM MODE PROMPT"
