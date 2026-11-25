"""The shipped macro packs install onto an empty database, once, and never over a user's edits.

Pin the contract:
1. Every pack in the tree VALIDATES: five sets, one default and one action per
   surface, no two sets mapping the same topic.
2. Applying a pack CREATES its meta-topic + sets and MARKS the topic id.
3. It is IDEMPOTENT — a second run creates nothing new.
4. It NEVER clobbers a set the user has edited.
5. The bindings report ids the store can use, and drop a topic that is gone.
6. A manifest that names no surface is not a shipped pack; a broken one is
   reported, never silently dropped.
"""

import json
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.macros.packs import (
    FLAG_PREFIX,
    INVALID,
    PRESENT,
    PackOutcome,
    apply_pack,
    pack_bindings,
    read_pack,
    read_packs,
    seed_packs_from,
)
from app.core.config import Paths
from app.infrastructure.database.models import MacroSet, MetaTopic, SystemFlag

SHIPPED = ("agent-bob", "agent-lois", "a-key-macros", "about-cogitate", "exa-diagnostics")

# The harness re-roots paths at a temp dir, so the packs are named by the
# locator's canonical root — these tests are about the content that ships.
SHIPPED_ROOT = Paths.root / "macros"


def _pack(key: str):
    for pack in read_packs(SHIPPED_ROOT):
        if pack.key == key:
            return pack
    raise AssertionError(f"pack {key!r} not found under {SHIPPED_ROOT}")


# ---------------------------------------------------------------------------
# 1. The tree itself
# ---------------------------------------------------------------------------


def test_every_shipped_pack_validates() -> None:
    packs = {p.key: p for p in read_packs(SHIPPED_ROOT)}
    missing = [key for key in SHIPPED if key not in packs]
    assert not missing, f"shipped packs missing from {SHIPPED_ROOT}: {missing}"

    for pack in packs.values():
        assert 1 <= len(pack.sets) <= 5, f"{pack.key}: {len(pack.sets)} sets"
        for item in pack.sets:
            assert len(item.macros) == 5, f"{pack.key}/{item.topic}: f-slots"
        assert pack.prompt_count == 25, f"{pack.key}: {pack.prompt_count} prompts"


def test_one_default_and_one_action_per_surface() -> None:
    roles: dict[tuple[str, str], str] = {}
    for pack in read_packs(SHIPPED_ROOT):
        if pack.role is None:
            continue  # shipped but unassigned claims no key
        slot = (pack.surface, pack.role)
        assert slot not in roles, f"{slot} claimed by both {roles.get(slot)} and {pack.key}"
        roles[slot] = pack.key

    assert roles == {
        ("agent", "default"): "agent-bob",
        ("agent", "action"): "a-key-macros",
        ("exa", "default"): "about-cogitate",
        ("exa", "action"): "exa-diagnostics",
    }


def test_prompts_stay_short() -> None:
    """A macro is a key press, not a paragraph — the plan's 'written short'."""
    for pack in read_packs(SHIPPED_ROOT):
        for item in pack.sets:
            for prompt in item.macros:
                if prompt:
                    assert len(prompt) <= 95, f"{pack.key}/{item.topic}: {len(prompt)} chars — {prompt!r}"


# ---------------------------------------------------------------------------
# 2-6. Installing
# ---------------------------------------------------------------------------


async def _count(session: AsyncSession, model, **filters) -> int:  # noqa: ANN001
    stmt = select(model)
    for col, val in filters.items():
        stmt = stmt.where(getattr(model, col) == val)
    return len((await session.execute(stmt)).scalars().all())


async def test_apply_creates_the_topic_its_sets_and_the_mark(test_session: AsyncSession, auto_clean_tables) -> None:  # noqa: ANN001
    pack = _pack("agent-bob")
    outcome = await apply_pack(test_session, pack)

    assert outcome.status == "created"
    topic = (
        await test_session.execute(select(MetaTopic).where(MetaTopic.name == pack.name))
    ).scalar_one()
    mappings = json.loads(topic.topic_mappings) if isinstance(topic.topic_mappings, str) else topic.topic_mappings
    assert [m["topic"] for m in mappings] == [s.topic for s in pack.sets]
    assert mappings[0]["slot_start"] == "M1"

    for item in pack.sets:
        assert await _count(test_session, MacroSet, user_key="default", topic=item.topic, name=item.name) == 1

    flag = await test_session.get(SystemFlag, f"{FLAG_PREFIX}{pack.key}")
    assert flag is not None and flag.value == str(topic.id)


async def test_second_run_creates_nothing(test_session: AsyncSession, auto_clean_tables) -> None:  # noqa: ANN001
    pack = _pack("agent-lois")
    await apply_pack(test_session, pack)
    topics = await _count(test_session, MetaTopic)
    sets = await _count(test_session, MacroSet)

    again = await apply_pack(test_session, pack)
    assert again.status == PRESENT
    assert await _count(test_session, MetaTopic) == topics
    assert await _count(test_session, MacroSet) == sets


async def test_never_clobbers_a_user_edited_set(test_session: AsyncSession, auto_clean_tables) -> None:  # noqa: ANN001
    pack = _pack("agent-bob")
    await apply_pack(test_session, pack)

    first = pack.sets[0]
    row = (
        await test_session.execute(
            select(MacroSet).where(MacroSet.topic == first.topic, MacroSet.name == first.name)
        )
    ).scalar_one()
    row.f1_macro = "USER'S OWN PROMPT"
    await test_session.commit()

    await apply_pack(test_session, pack)
    row2 = (
        await test_session.execute(
            select(MacroSet).where(MacroSet.topic == first.topic, MacroSet.name == first.name)
        )
    ).scalar_one()
    assert row2.f1_macro == "USER'S OWN PROMPT"


async def test_the_a_key_pack_adopts_the_seed(test_session: AsyncSession, auto_clean_tables) -> None:  # noqa: ANN001
    """The seed runs first on a fresh install; the pack must not add a second bank."""
    from app.domain.macros.seeds import seed_akeys_macros

    await seed_akeys_macros(test_session)
    outcome = await apply_pack(test_session, _pack("a-key-macros"))

    assert outcome.status == "adopted"
    assert await _count(test_session, MetaTopic, name="A-Key Macros") == 1


async def test_the_seed_installs_every_pack_once(test_session: AsyncSession, auto_clean_tables) -> None:  # noqa: ANN001
    first = await seed_packs_from(test_session, SHIPPED_ROOT)
    assert [o.status for o in first] == ["created"] * len(SHIPPED)
    assert await _count(test_session, MetaTopic) == len(SHIPPED)

    second = await seed_packs_from(test_session, SHIPPED_ROOT)
    assert [o.status for o in second] == [PRESENT] * len(SHIPPED)


async def test_bindings_name_the_shipped_topics(test_session: AsyncSession, auto_clean_tables) -> None:  # noqa: ANN001
    for key in SHIPPED:
        await apply_pack(test_session, _pack(key))

    bindings = await pack_bindings(test_session, SHIPPED_ROOT)
    by_name = {
        name: topic_id
        for name, topic_id in (
            await test_session.execute(select(MetaTopic.name, MetaTopic.id))
        ).all()
    }
    # Names come from the packs, never from this file: a pack rename is a display
    # change and must not fail a test that is about BINDINGS.
    assert bindings == {
        "agent": {"f": by_name[_pack("agent-bob").name], "a": by_name[_pack("a-key-macros").name]},
        "exa": {"f": by_name[_pack("about-cogitate").name], "a": by_name[_pack("exa-diagnostics").name]},
    }


async def test_a_deleted_topic_binds_nothing(test_session: AsyncSession, auto_clean_tables) -> None:  # noqa: ANN001
    await apply_pack(test_session, _pack("agent-bob"))
    bob = (
        await test_session.execute(
            select(MetaTopic).where(MetaTopic.name == _pack("agent-bob").name)
        )
    ).scalar_one()
    await test_session.delete(bob)
    await test_session.commit()

    bindings = await pack_bindings(test_session, SHIPPED_ROOT)
    assert bindings["agent"]["f"] is None


def test_a_broken_pack_is_reported_not_dropped(tmp_path: Path) -> None:
    folder = tmp_path / "broken"
    (folder / "macro-sets").mkdir(parents=True)
    (folder / "meta-topic.json").write_text(
        json.dumps({"name": "Broken", "surface": "desktop", "macro_sets": ["one.json"]})
    )
    (folder / "macro-sets" / "one.json").write_text(
        json.dumps({"topic": "T", "name": "N", "macros": {"f1": "x"}})
    )

    with pytest.raises(ValueError, match="surface"):
        read_pack(folder)


def test_a_pack_without_a_surface_is_not_shipped(tmp_path: Path) -> None:
    folder = tmp_path / "legacy"
    (folder / "macro-sets").mkdir(parents=True)
    (folder / "meta-topic.json").write_text(json.dumps({"name": "Legacy", "macro_sets": []}))

    assert read_packs(tmp_path) == []


def test_outcomes_describe_themselves() -> None:
    assert PackOutcome("agent-bob", "created", "meta-topic #1").describe() == (
        "agent-bob: created — meta-topic #1"
    )
    assert INVALID == "invalid"
