"""The shipped agents — the news desk's first two reporters.

The release needs an install to carry its agents, and a fresh clone carries none: `agents/`
is per-install workspaces (gitignored), and the two folders on a developer's machine are
`_derived` snapshots of DB rows. So the source is a tracked PACKAGE and this is the seed
that reads it.

What is asserted here is the split the seed exists to keep:

* a package with nothing to deploy it onto is DEFERRED and says why — never an invented
  service, and never a half-created agent;
* a package that can be deployed is created ONCE, with the install's own chat answer, its
  workspace, its skills, its kits and its face;
* a person who deletes a shipped agent keeps him deleted.

Everything is written inside the test installation (the conftest re-roots it).
"""

import json
from pathlib import Path
from typing import Iterator

import pytest
from sqlalchemy import select

from app.core.config import Paths, get_settings
from app.domain.agent_kits.model import AgentKit
from app.domain.collections.models import CollectionItem
from app.domain.agents.shipped import (
    CREATED,
    DEFERRED,
    INVALID,
    PRESENT,
    seed_shipped_agents,
)
from app.domain.tools.models import Tool
from app.infrastructure.database.models import Agent, Provider, SystemFlag


def _png_bytes() -> bytes:
    """The smallest valid PNG (1x1, 8-bit grayscale)."""
    import base64

    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8AAAwAB/wD/1wAAAABJRU5ErkJggg=="
    )


def _clear(folder: Path) -> None:
    if folder.is_dir():
        import shutil

        for child in sorted(folder.iterdir()):
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()


@pytest.fixture
def seed_dir() -> Iterator[Path]:
    """The installation's package dir, empty before and after."""
    root = Paths.from_settings(get_settings()).agent_seed_dir
    _clear(root)
    root.mkdir(parents=True, exist_ok=True)
    yield root
    _clear(root)



def write_package(
    root: Path,
    key: str,
    *,
    name: str | None = None,
    persona: str = "You are a test reporter for the desk.",
    skills: list[str] | None = None,
    kits: list[dict] | None = None,
    face: str | None = None,
) -> Path:
    folder = root / key
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "persona.md").write_text(persona, encoding="utf-8")
    (folder / "package.json").write_text(
        json.dumps(
            {
                "format_version": "1.0",
                "key": key,
                "name": name or key.title(),
                "description": f"{key} on the desk",
                "persona": "persona.md",
                "skills": skills if skills is not None else ["basic-search"],
                "kits": kits or [],
                "tags": ["news"],
                "parameters": {"temperature": 0.4},
                "llm_spec": {"max_output": 4096},
                "execution_mode": "llm",
                "face": face,
            }
        ),
        encoding="utf-8",
    )
    return folder


async def _default_row(session, name: str = "scratch-chat", model: str = "scratch-model") -> None:
    session.add(
        Provider(
            name=name,
            provider_type="ollama",
            is_active=True,
            is_default=True,
            priority=1,
            config={"default_model": model},
        )
    )
    await session.flush()


async def _clear_providers(session) -> None:
    for row in (await session.execute(select(Provider))).scalars().all():
        await session.delete(row)
    await session.flush()


async def test_a_reader_rejects_a_package_whose_key_does_not_match_its_folder(seed_dir):
    """Two names for one agent drift — the folder IS the workspace key."""
    from app.domain.agents.shipped import read_package

    folder = write_package(seed_dir, "wrong-key")
    manifest = json.loads((folder / "package.json").read_text())
    manifest["key"] = "somebody-else"
    (folder / "package.json").write_text(json.dumps(manifest))

    with pytest.raises(ValueError, match="does not match its folder"):
        read_package(folder)


async def test_a_package_with_no_chat_service_defers_and_says_why(seed_dir, test_session):
    """Nothing answers chat yet: no row, no marker, and the next call tries again."""
    await _clear_providers(test_session)
    write_package(seed_dir, "deferred-reporter", name="Deferred")

    outcomes = await seed_shipped_agents(test_session)

    assert [o.status for o in outcomes] == [DEFERRED]
    assert outcomes[0].detail, "a deferral with no reason is a silent failure"
    assert (await test_session.execute(select(Agent))).scalars().all() == []
    assert await test_session.get(SystemFlag, "shipped-agent:deferred-reporter") is None
    assert (await test_session.execute(select(AgentKit))).scalars().all() == []


async def test_a_package_is_seeded_once_with_the_installs_chat_answer(seed_dir, test_session):
    """The row, the folder, the skills, the kits and the face — from the install's answer."""
    await _clear_providers(test_session)
    await _default_row(test_session, model="scratch-model:7b")

    # a tool the kit names, and a curated face to copy
    test_session.add(
        Tool(
            name="DateTime",
            slug="datetime",
            description="the clock",
            provider="System",
            type="builtin",
        )
    )
    await test_session.flush()
    pool = Paths.from_settings(get_settings()).agent_images_dir
    pool.mkdir(parents=True, exist_ok=True)
    (pool / "face-test.png").write_bytes(_png_bytes())

    write_package(
        seed_dir,
        "test-reporter",
        name="Test Reporter",
        persona="You are Test Reporter, a scout.",
        skills=["basic-search"],
        kits=[{"name": "Workspace", "description": "the desk", "tools": ["DateTime", "No Such Tool"]}],
        face="face-test.png",
    )

    outcomes = await seed_shipped_agents(test_session)

    assert [o.status for o in outcomes] == [CREATED], outcomes[0].detail
    agent = (await test_session.execute(select(Agent))).scalars().one()
    assert (agent.name, agent.workspace_key) == ("Test Reporter", "test-reporter")
    assert (agent.provider, agent.model) == ("scratch-chat", "scratch-model:7b")
    assert agent.system_prompt == "You are Test Reporter, a scout."
    assert agent.skills == ["basic-search"]
    assert agent.profile_image_url == "/static/face-test.png"
    assert (Path(get_settings().profile_images_dir) / "face-test.png").is_file(), (
        "the face must be in the store /static serves, not only in the curated pool"
    )

    # the workspace manifests the row: folder, derived manifest, empty state, persona, skill
    workspace = Paths.from_settings(get_settings()).agents_dir / "test-reporter"
    assert (workspace / "agent.json").is_file()
    assert json.loads((workspace / "agent.json").read_text())["db_id"] == agent.id
    assert (workspace / "persona.md").read_text() == "You are Test Reporter, a scout."
    assert json.loads((workspace / "state.json").read_text()) == {"facts": {}, "sources": []}
    assert (workspace / "skills" / "basic-search.skill.md").is_file()

    # the kit: created by name, the tool it could resolve is in it, the ghost is not
    kit = (await test_session.execute(select(AgentKit))).scalars().one()
    assert kit.agent_id == agent.id
    assert await test_session.get(SystemFlag, "shipped-agent:test-reporter") is not None

    # idempotent: the second run reports it present and creates nothing
    outcomes = await seed_shipped_agents(test_session)
    assert [o.status for o in outcomes] == [PRESENT]
    assert len((await test_session.execute(select(Agent))).scalars().all()) == 1


async def test_an_agent_that_already_carries_the_name_is_adopted_not_duplicated(
    seed_dir, test_session
):
    """A hand-made Bob (or a renamed key) must not gain a second Bob on the next boot."""
    await _clear_providers(test_session)
    await _default_row(test_session)
    test_session.add(
        Agent(
            name="Handmade",
            description="made by hand",
            provider="scratch-chat",
            model="scratch-model",
            workspace_key="a-different-key",
            is_active=True,
        )
    )
    await test_session.flush()
    write_package(seed_dir, "handmade", name="Handmade")

    outcomes = await seed_shipped_agents(test_session)

    assert [o.status for o in outcomes] == [PRESENT]
    assert len((await test_session.execute(select(Agent))).scalars().all()) == 1
    assert await test_session.get(SystemFlag, "shipped-agent:handmade") is not None


async def test_a_deleted_shipped_agent_stays_deleted(seed_dir, test_session):
    """The marker is the difference between a seed and a resurrection loop."""
    await _clear_providers(test_session)
    await _default_row(test_session)
    write_package(seed_dir, "gone-reporter", name="Gone")
    assert [o.status for o in await seed_shipped_agents(test_session)] == [CREATED]

    agent = (await test_session.execute(select(Agent))).scalars().one()
    await test_session.delete(agent)
    await test_session.flush()
    await test_session.commit()

    outcomes = await seed_shipped_agents(test_session)

    assert [o.status for o in outcomes] == [PRESENT]
    assert (await test_session.execute(select(Agent))).scalars().all() == []


async def test_a_broken_package_is_reported_and_costs_the_other_nothing(seed_dir, test_session):
    """One bad folder in the tree must not take the desk down with it."""
    await _clear_providers(test_session)
    await _default_row(test_session)
    good = write_package(seed_dir, "good-reporter", name="Good")
    broken = seed_dir / "broken-reporter"
    broken.mkdir(parents=True, exist_ok=True)
    (broken / "package.json").write_text(json.dumps({"format_version": "1.0", "key": "broken-reporter"}))

    outcomes = await seed_shipped_agents(test_session)
    by_key = {o.key: o.status for o in outcomes}

    assert by_key == {"broken-reporter": INVALID, "good-reporter": CREATED}
    assert good.is_dir()
    names = [a.name for a in (await test_session.execute(select(Agent))).scalars().all()]
    assert names == ["Good"]


async def test_a_kit_member_joins_to_the_tool_row_it_names(seed_dir, test_session):
    """THE JOIN, not a name match — the query the chat path uses to build `llm_tools`.

    Measured on a fresh install (2026-11-19): the seed wrote the tool id through a
    UUID-typed attribute (dashed) into a plain String column that stores 32 hex characters,
    so the join returned NULL for all 12 members of the reporters' three kits,
    `tools_offered` was 0, and the model invented a textual `<tool_call>` block.
    """
    await _clear_providers(test_session)
    await _default_row(test_session, model="scratch-model:7b")
    test_session.add(
        Tool(name="DateTime", slug="datetime", description="the clock", provider="System", type="builtin")
    )
    await test_session.flush()

    write_package(
        seed_dir,
        "join-check",
        name="Join Check",
        kits=[{"name": "Workspace", "description": "the desk", "tools": ["DateTime"]}],
    )
    await seed_shipped_agents(test_session)

    joined = (
        await test_session.execute(
            select(CollectionItem)
            .join(Tool, Tool.id == CollectionItem.entity_id)
            .where(CollectionItem.entity_type == "tool")
        )
    ).scalars().all()
    assert len(joined) == 1, (
        "the kit member must join to its tool row — an id in a form the tools table does not "
        "store resolves to nothing, and the agent is offered zero tools"
    )
    assert joined[0].entity_name == "DateTime"

    # THE GRANT — the half that actually broke the chat path: the surface is built from
    # `tool_collection_permissions`, so a kit that only LISTS its members grants nothing and
    # `_toolkit_slugs_for_agent` returns an EMPTY set ("owns kits ⇒ no GRAS default").
    from app.domain.tools.execution_service import ToolExecutionService
    from app.domain.tools.tool_permission_models import ToolCollectionPermission

    grants = (await test_session.execute(select(ToolCollectionPermission))).scalars().all()
    assert len(grants) == 1, "membership without a grant is a kit that grants nothing"
    assert grants[0].tool_id == joined[0].entity_id

    agent = (await test_session.execute(select(Agent))).scalars().one()
    slugs = await ToolExecutionService(test_session)._toolkit_slugs_for_agent(str(agent.id))
    assert slugs == {"datetime"}, (
        "the agent's surface must resolve to the kit's granted tools — an empty set means "
        "tools_offered=0 and the model invents a textual <tool_call>"
    )
