"""Macro meta-topic creation — regression tests for two live bugs."""

import pytest

from app.api.v1.macros.router import create_meta_topic
from app.domain.macros.schemas import MetaTopicCreate, TopicMapping


@pytest.mark.asyncio
async def test_create_meta_topic_persists_mappings_json(test_session):
    """topic_mappings must be JSON-serialized into the Text column —
    passing the raw list crashed SQLite binding (type list not
    supported)."""
    created = await create_meta_topic(
        MetaTopicCreate(
            user_key="default",
            name="Exa Test Topic",
            description="test",
            topic_mappings=[TopicMapping(topic="Exa Diagnostics", slot_start="F1")],
            is_active=True,
        ),
        test_session,
    )
    assert created.name == "Exa Test Topic"
    # the stored value must be a JSON string, not a list
    from sqlalchemy import select
    from app.infrastructure.database.models import MetaTopic
    result = await test_session.execute(
        select(MetaTopic).where(MetaTopic.name == "Exa Test Topic")
    )
    row = result.scalars().first()
    assert row is not None
    assert isinstance(row.topic_mappings, str)
    import json
    parsed = json.loads(row.topic_mappings)
    assert parsed == [{"topic": "Exa Diagnostics", "slot_start": "F1"}]


@pytest.mark.asyncio
async def test_create_meta_topic_sets_user_key(test_session):
    """user_key is NOT NULL — omitting it crashed with a misleading
    409 IntegrityError instead of a clear 422."""
    created = await create_meta_topic(
        MetaTopicCreate(
            user_key="default",
            name="Exa Key Topic",
            description="test",
            topic_mappings=[],
        ),
        test_session,
    )
    assert created.user_key  # default applied


@pytest.mark.asyncio
async def test_parse_slot_number_f_and_m_slots():
    """_parse_slot_number must accept both F-slots (F1 -> 1) and the
    legacy M-slots (M1 -> 1, M2 -> 6, ...) — M{n} occupies F-slots
    5*(n-1)+1 .. +5, matching the extended keyboard layout."""
    from app.domain.macros.services import AgentMacroService

    parse = AgentMacroService._parse_slot_number

    # F-slots (unchanged behavior)
    assert parse("F1") == 1
    assert parse("F5") == 5
    assert parse("F21") == 21

    # M-slots (legacy topic-position convention)
    assert parse("M1") == 1
    assert parse("M2") == 6
    assert parse("M3") == 11
    assert parse("M4") == 16
    assert parse("M5") == 21

    # Garbage stays None
    assert parse("X1") is None
    assert parse("") is None
    assert parse("F") is None
    assert parse(None) is None


@pytest.mark.asyncio
async def test_update_meta_topic_serializes_topic_mappings(test_session):
    """PUT with topic_mappings must JSON-serialize into the Text column —
    the dict-list form crashed SQLite binding (type 'list' not
    supported), breaking reorder/add/remove-topic in the UI."""
    from app.api.v1.macros.router import update_meta_topic
    from app.domain.macros.schemas import MetaTopicUpdate, TopicMapping

    created = await create_meta_topic(
        MetaTopicCreate(
            user_key="default",
            name="Update Serialization Test",
            description="test",
            topic_mappings=[TopicMapping(topic="Exa Diagnostics", slot_start="F1")],
            is_active=True,
        ),
        test_session,
    )

    updated = await update_meta_topic(
        created.id,
        MetaTopicUpdate(
            topic_mappings=[
                TopicMapping(topic="Exa Diagnostics", slot_start="F6"),
                TopicMapping(topic="Debugging", slot_start="M2"),
            ]
        ),
        test_session,
    )

    # MetaTopicResponse deserializes to TopicMapping models — compare
    # against the models (not raw dicts; the API layer does the
    # JSON->model conversion)
    assert updated.topic_mappings == [
        TopicMapping(topic="Exa Diagnostics", slot_start="F6"),
        TopicMapping(topic="Debugging", slot_start="M2"),
    ]

    # Stored value must be a JSON string, not a list
    from sqlalchemy import select
    from app.infrastructure.database.models import MetaTopic
    result = await test_session.execute(
        select(MetaTopic).where(MetaTopic.id == created.id)
    )
    row = result.scalars().first()
    assert isinstance(row.topic_mappings, str)
    import json
    assert json.loads(row.topic_mappings)[0]["slot_start"] == "F6"


@pytest.mark.asyncio
async def test_renaming_a_macro_set_topic_repoints_meta_topic_mappings(test_session):
    """The meta-topic <-> macro-set link is a NAME on BOTH sides.

    A meta-topic's ``topic_mappings`` hold the macro set's ``topic`` string — there is no
    id column tying the two — and the UI resolves a slot with
    ``macroSets.find(m => m.topic === mapping.topic)``. Renaming a macro set therefore
    changed only one side of the pair: the slot silently resolved to nothing and the macro
    set vanished from its meta-topic. Live case: 'Omaha News Desk' renamed to 'Local News
    Desk' orphaned meta-topic 26's M1 slot, and the slot rendered as empty.

    Renaming is a supported action, so the reference has to survive it.
    """
    from app.api.v1.macros.router import create_macro_set, update_macro_set
    from app.domain.macros.schemas import MacroSetCreate, MacroSetUpdate
    from app.infrastructure.database.models import MetaTopic
    from sqlalchemy import select
    import json

    meta = await create_meta_topic(
        MetaTopicCreate(
            user_key="default",
            name="Rename Repoint Test",
            description="test",
            topic_mappings=[TopicMapping(topic="Old Topic", slot_start="M1")],
            is_active=True,
        ),
        test_session,
    )

    macro_set = await create_macro_set(
        MacroSetCreate(
            user_key="default",
            topic="Old Topic",
            name="A macro set",
            f1_macro="hello",
        ),
        test_session,
    )

    await update_macro_set(
        macro_set.id,
        MacroSetUpdate(topic="New Topic"),
        test_session,
    )

    result = await test_session.execute(
        select(MetaTopic).where(MetaTopic.id == meta.id)
    )
    row = result.scalars().first()
    assert json.loads(row.topic_mappings) == [
        {"topic": "New Topic", "slot_start": "M1"}
    ], "the mapping must follow the rename, or the slot is orphaned"
