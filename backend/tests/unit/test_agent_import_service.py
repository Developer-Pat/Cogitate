"""An IMPORTED agent's service AND workspace.

One import call, two defects — the second found while landing the first:

* the SERVICE — `wiki/issues/resolved/embedded-service-literals/agent-import-service.md`, option A, the user: *"the import always yields
  a working agent; the only refusal is for an install that has no default row to answer with."* The
  import used to fall back to `provider="ollama"` / `model="llama3.2"` for a bundle that named
  nothing;
* the WORKSPACE — AN IMPORTED AGENT'S WORKSPACE IS NEVER LINKED. The import wrote
  a folder but left `workspace_key` NULL, so the folder was invisible to every folder-side reader (an
  export of the freshly imported agent came back with **no** agent_json, skills or memory) and a hard
  delete removed the row while **orphaning** the folder.

The second one's root cause is that the import hand-rolled what `domain/agents/workspace` owns, so the
fix routes it through the module: one minted key on the row, the folder scaffolded from the row, the
bundle's payload written on top. What is asserted below is what a reader of the folder notices — the
row knows where its folder is, the folder names the ROW's service rather than the bundle's stale one,
the round trip carries the folder half, and the bundle's name cannot aim the write.

What must NOT change: a bundle that states both halves is copied through untouched — the resolution
may never override the snapshot of an agent that already had a service.
"""

import inspect
import json
import shutil

import pytest
from sqlalchemy import select

from app.core.config import Paths, get_settings
from app.domain.agents.export_service import (
    SERVICE_FROM_BUNDLE,
    SERVICE_FROM_DEFAULT_ROW,
    export_agent,
    import_agent,
)
from app.infrastructure.database.models import Agent, Provider

SCRATCH_NAME = "scratch-import-default"
SCRATCH_MODEL = "scratch-import-model:latest"


def _bundle(name: str = "TestImportSvc", **agent_config) -> dict:
    """A bundle as the export route writes one — `agent_config` with whatever the test is about."""
    return {
        "format_version": "1.0",
        "agent_config": {"name": name, "description": "", **agent_config},
    }


async def _scratch_default_row(session) -> None:
    """Put ONE `is_default` provider row in this session, whatever the seed did.

    Created rather than assumed, and the live default is explicitly cleared first: the test database
    is a copy of the operator's REAL one, so a test that just asserted "a default row exists" would
    be measuring the fixture. The session fixture rolls the scratch row back.
    """
    for row in (await session.execute(select(Provider).where(Provider.is_default))).scalars().all():
        row.is_default = False

    session.add(
        Provider(
            name=SCRATCH_NAME,
            provider_type="ollama",
            is_active=True,
            is_default=True,
            priority=99,
            config={"default_model": SCRATCH_MODEL},
        )
    )
    await session.flush()


async def _no_default_row(session) -> None:
    """The other install: rows exist, none is the default. This is the refusal's one case."""
    for row in (await session.execute(select(Provider).where(Provider.is_default))).scalars().all():
        row.is_default = False
    await session.flush()


async def _imported(session, bundle) -> tuple:
    """Import and read the row back — the row is what the folder is supposed to manifest."""
    result = await import_agent(bundle, session)
    row = (await session.execute(select(Agent).where(Agent.id == result.agent_id))).scalar_one()
    return result, row


def _agents_root():
    return Paths.from_settings(get_settings()).agents_dir


def _remove_workspace(*rows) -> None:
    """Delete exactly the folders these imports wrote, addressed the way the APP addresses them:
    `agents_dir / row.workspace_key`. Nothing is globbed by name — when the key is missing, the
    cleanup has nothing to point at, which is the defect itself."""
    for row in rows:
        if row.workspace_key:
            shutil.rmtree(_agents_root() / row.workspace_key, ignore_errors=True)


# ── the service: stated → else the default row → else refuse ────────────────────────────────────


def test_no_service_literal_remains_in_the_import_path():
    """The literals cannot come back by accident — they were the whole of this issue."""
    from app.domain.agents import export_service

    src = inspect.getsource(export_service.import_agent)
    assert "agent_config.get(\"provider\", \"ollama\")" not in src
    assert "agent_config.get(\"model\", \"llama3.2\")" not in src


@pytest.mark.asyncio
async def test_a_stated_service_is_copied_through(test_session):
    result, row = await _imported(
        test_session, _bundle(provider="groq", model="llama3-8b-8192")
    )

    assert (result.provider, result.model) == ("groq", "llama3-8b-8192")
    assert result.service_source == SERVICE_FROM_BUNDLE
    assert (row.provider, row.model) == ("groq", "llama3-8b-8192")
    _remove_workspace(row)


@pytest.mark.asyncio
async def test_a_silent_bundle_resolves_from_the_default_provider_row(test_session):
    """Neither half named: the answer is the row marked `is_default`, and the result SAYS so."""
    await _scratch_default_row(test_session)

    result, row = await _imported(test_session, _bundle())

    assert (result.provider, result.model) == (SCRATCH_NAME, SCRATCH_MODEL)
    assert result.service_source == SERVICE_FROM_DEFAULT_ROW, "the substitution must be reported"
    assert (row.provider, row.model) == (SCRATCH_NAME, SCRATCH_MODEL)
    _remove_workspace(row)


@pytest.mark.asyncio
async def test_an_empty_string_is_silence_too(test_session):
    """The second door: `""` used to reach a `nullable=False` column instead of the literal."""
    await _scratch_default_row(test_session)

    result, row = await _imported(test_session, _bundle(provider="", model=""))

    assert (result.provider, result.model) == (SCRATCH_NAME, SCRATCH_MODEL)
    assert result.service_source == SERVICE_FROM_DEFAULT_ROW
    _remove_workspace(row)


@pytest.mark.asyncio
async def test_a_partially_stated_bundle_keeps_what_it_states(test_session):
    """A stated provider survives; only the missing half is resolved."""
    await _scratch_default_row(test_session)

    result, row = await _imported(test_session, _bundle(provider="groq"))

    assert (result.provider, result.model) == ("groq", SCRATCH_MODEL)
    assert result.service_source == SERVICE_FROM_DEFAULT_ROW
    _remove_workspace(row)


@pytest.mark.asyncio
async def test_an_install_with_no_default_row_refuses_the_import(test_session):
    """The one case the ruling keeps a refusal for: nothing to resolve from."""
    await _no_default_row(test_session)

    with pytest.raises(ValueError, match="no default provider row"):
        await import_agent(_bundle(), test_session)


@pytest.mark.asyncio
async def test_the_refusal_creates_no_agent_and_no_folder(test_session):
    """A refusal that had already written the row would be worse than the literal it replaced."""
    await _no_default_row(test_session)
    before = len((await test_session.execute(select(Agent))).scalars().all())

    with pytest.raises(ValueError):
        await import_agent(_bundle(name="TestImportRefused"), test_session)

    after = len((await test_session.execute(select(Agent))).scalars().all())
    assert after == before, "the refusal must land before anything is written"
    assert not list(_agents_root().glob("*testimportrefused*"))


# ── the workspace: the row carries the key, the folder manifests the row ─────────────────────────


@pytest.mark.asyncio
async def test_the_row_knows_where_its_folder_is(test_session):
    """The filed defect: `workspace_key` was NULL, so no folder-side reader could find the folder."""
    _result, row = await _imported(test_session, _bundle(provider="groq", model="m"))

    assert row.workspace_key, "an imported agent's folder must be addressable from its row"
    folder = _agents_root() / row.workspace_key
    assert folder.is_dir(), f"the key must name the folder the import wrote ({folder})"

    # …and through the seam every folder-side reader uses (export, archive, delete).
    from app.domain.agents.repository import get_agent_repository

    resolved = await get_agent_repository(test_session).agent_workspace(row.id)
    assert resolved == str(folder)
    _remove_workspace(row)


@pytest.mark.asyncio
async def test_a_bundles_name_cannot_aim_the_folder(test_session):
    """`make_workspace_key` SLUGIFIES: the bundle's name is data, and `../../` in it used to be a
    write path (the folder was named straight from the name, with no validation)."""
    _result, row = await _imported(
        test_session, _bundle(name="../../pwned-import", provider="groq", model="m")
    )

    assert "/" not in row.workspace_key and ".." not in row.workspace_key
    folder = _agents_root() / row.workspace_key
    assert folder.parent == _agents_root(), "the folder must stay inside agents/"
    assert folder.is_dir()
    _remove_workspace(row)


@pytest.mark.asyncio
async def test_the_folder_manifests_the_rows_service_not_the_bundles(test_session):
    """A bundle whose manifest still names the service the resolution replaced must not leave the
    folder disagreeing with the database — the row is authoritative."""
    await _scratch_default_row(test_session)
    bundle = _bundle()
    bundle["agent_json"] = {
        "name": "TestImportSvc",
        "provider": "ollama",
        "model": "llama3.2",
    }

    _result, row = await _imported(test_session, bundle)

    manifest = json.loads((_agents_root() / row.workspace_key / "agent.json").read_text())
    assert (manifest["provider"], manifest["model"]) == (SCRATCH_NAME, SCRATCH_MODEL)
    assert manifest["db_id"] == row.id
    assert manifest["name"] == row.name
    _remove_workspace(row)


@pytest.mark.asyncio
async def test_a_bundle_with_no_manifest_still_gets_one_from_the_row(test_session):
    """The scaffold's half: the disk manifests the row, so a bundle that carried no agent.json does
    not leave a folder with no identity at all."""
    _result, row = await _imported(
        test_session, _bundle(provider="groq", model="llama3-8b-8192")
    )

    folder = _agents_root() / row.workspace_key
    manifest = json.loads((folder / "agent.json").read_text())
    assert manifest["provider"] == "groq" and manifest["model"] == "llama3-8b-8192"
    assert manifest.get("workspace_key") == row.workspace_key
    # the rest of what the workspace module scaffolds, which the import used to skip
    assert (folder / "state.json").is_file()
    _remove_workspace(row)


@pytest.mark.asyncio
async def test_the_round_trip_keeps_the_folder_half(test_session):
    """The symptom the finding was filed from: import → export lost agent_json, skills and memory."""
    bundle = _bundle(name="TestImportSvc", provider="groq", model="llama3-8b-8192")
    bundle["agent_json"] = {"name": "TestImportSvc", "provider": "groq", "model": "llama3-8b-8192"}
    bundle["skills"] = [{"filename": "probe-skill.md", "content": "# a grown skill"}]
    bundle["cognitive_memory"] = [
        {"key": "fact", "value": "[\"one\"]", "created_at": "2026-01-01", "updated_at": "2026-01-01"}
    ]

    _result, row = await _imported(test_session, bundle)
    exported = await export_agent(row.id, test_session)

    assert exported.get("agent_json", {}).get("name") == row.name, "the manifest must come back"
    assert [s["filename"] for s in exported.get("skills", [])] == ["probe-skill.md"]
    assert [m["key"] for m in exported.get("cognitive_memory", [])] == ["fact"]
    _remove_workspace(row)
