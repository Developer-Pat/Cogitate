"""A duplicate is a scoped INSTANCE of the same character.

The 2026-10-12 ruling: the character's configuration travels, the instance's
workspace and state are its own, and the name carries an instance marker. The
CENSUS test is the point of the module it checks — a new `AgentCreate` field must
be classified, or the clone starts dropping it in silence, which is the defect
this replaced (`wiki/issues/resolved/embedded-service-literals/duplicated-agent-partial-clone.md`).
"""

import json

import pytest

from app.domain.agent_kits.service import AgentKitService
from app.domain.collections.models import Collection
from app.infrastructure.database.models import Agent


def _source(**overrides) -> Agent:
    base = dict(
        name="Bob", provider="deepseek", model="deepseek-v4-flash",
        system_prompt="You are Bob.", description="the reporter",
        skills=["greeting"], tags=["probe"], cognitive_profile_id=None,
        preferred_providers=["deepseek"], fallback_enabled=True,
        execution_mode="hybrid", profile_image_url="/static/alien-01.png",
        workspace_key="bob", is_active=True, allow_delegation=True,
    )
    base.update(overrides)
    return Agent(**base)


# ---------------------------------------------------------------------------
# 1. the census — every AgentCreate field is CLAIMED by a group
# ---------------------------------------------------------------------------

def test_every_create_field_is_classified():
    """A new schema field cannot arrive unclaimed and be dropped in silence."""
    from app.domain.agents.clone import unclassified_fields

    assert unclassified_fields() == set()


def test_the_groups_are_disjoint():
    from app.domain.agents.clone import CLONE_FIELDS, DERIVED_FIELDS, FRESH_FIELDS

    assert (CLONE_FIELDS & FRESH_FIELDS) == set()
    assert (CLONE_FIELDS & DERIVED_FIELDS) == set()
    assert (FRESH_FIELDS & DERIVED_FIELDS) == set()


def test_the_instance_name_marker():
    """`Bob-2`, numbered against every row the name ban would match."""
    from app.domain.agents.clone import next_instance_name

    assert next_instance_name("Bob", []) == "Bob-2"
    assert next_instance_name("Bob", ["Bob", "Bob-2"]) == "Bob-3"
    assert next_instance_name("Bob", ["bob-2", "BOB-3"]) == "Bob-4"  # case-insensitive
    assert next_instance_name("Bob", ["Bob-2 (kept)"]) == "Bob-2"  # a different name is free


def test_clone_character_travels_the_character_and_keeps_identity_fresh():
    from app.domain.agents.clone import clone_character

    src = _source()
    payload = clone_character(src, ["Bob"])
    dumped = payload.model_dump()

    assert payload.name == "Bob-2"
    for field in (
        "description", "provider", "model", "system_prompt", "is_active", "parameters",
        "template_id", "preferred_providers", "fallback_enabled", "allow_delegation",
        "execution_mode", "behavior_config", "cognitive_profile_id", "skills",
        "profile_image_url", "tags", "kit_id", "llm_spec", "package_id",
    ):
        assert dumped[field] == getattr(src, field), field

    # the instance's own identity: a marker, not a copy marker, and not a builtin
    assert payload.is_builtin is False
    assert payload.workspace_key is None  # the seam mints it


def test_a_null_row_value_is_absent_not_an_override():
    """A NULL on the source row lets the schema's own default stand (`is_active` and
    `allow_delegation` are non-optional bools, so a None would not validate)."""
    from app.domain.agents.clone import clone_character

    payload = clone_character(_source(is_active=None, allow_delegation=None), ["Bob"])

    assert payload.is_active is True
    assert payload.allow_delegation is True


# ---------------------------------------------------------------------------
# 2. the seam — the duplicate goes through it
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_duplicate_creates_an_instance_with_its_own_workspace(
    test_session, tmp_path, monkeypatch
):
    monkeypatch.setattr("app.domain.agents.workspace.AGENTS_ROOT", tmp_path)

    src = _source()
    test_session.add(src)
    await test_session.commit()
    await test_session.refresh(src)

    from app.domain.agents.repository import get_agent_repository

    repo = get_agent_repository(test_session)
    copy = await repo.duplicate_agent(src.id)

    assert copy is not None
    assert copy.id != src.id
    assert copy.name == "Bob-2"
    assert copy.workspace_key == "bob-2"
    assert copy.profile_image_url == src.profile_image_url  # an instance of Bob looks like Bob
    assert copy.skills == ["greeting"]  # the character's skill list travels
    assert copy.is_builtin is False

    ws = tmp_path / "bob-2"
    assert (ws / "agent.json").exists() and (ws / "skills").is_dir()
    assert json.loads((ws / "agent.json").read_text())["name"] == "Bob-2"  # derived from ITS row
    # the instance starts empty — state never travels
    assert json.loads((ws / "state.json").read_text()) == {"facts": {}, "sources": []}

    # and a second instance numbers itself against the rows, not against the parent
    second = await repo.duplicate_agent(src.id)
    assert second is not None and second.name == "Bob-3" and second.workspace_key == "bob-3"


@pytest.mark.asyncio
async def test_duplicate_copies_the_tool_surface(test_session, tmp_path, monkeypatch):
    """The kits live in agent_kits, not in a create field — they travel anyway."""
    monkeypatch.setattr("app.domain.agents.workspace.AGENTS_ROOT", tmp_path)

    src = _source(name="Kitty")
    kit = Collection(id="kit-workspace", user_key="default", name="Workspace", entity_type="tool")
    test_session.add_all([src, kit])
    await test_session.commit()
    await test_session.refresh(src)

    kits = AgentKitService(test_session)
    assert await kits.attach(src.id, kit.id) is True
    await test_session.commit()

    from app.domain.agents.repository import get_agent_repository

    copy = await get_agent_repository(test_session).duplicate_agent(src.id)

    assert copy is not None
    assert [k.id for k in await kits.kits_for_agent(copy.id)] == ["kit-workspace"]


@pytest.mark.asyncio
async def test_duplicate_of_a_missing_agent_is_none(test_session, tmp_path, monkeypatch):
    monkeypatch.setattr("app.domain.agents.workspace.AGENTS_ROOT", tmp_path)

    from app.domain.agents.repository import get_agent_repository

    assert await get_agent_repository(test_session).duplicate_agent(999999) is None
