"""Agent export and import — the bundle, the folder lookup, and the re-import."""

import json
import os
import tempfile

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.domain.agents.export_service import export_agent, import_agent, _agent_folder_path


@pytest.mark.asyncio
async def test_export_researcher_returns_bundle():
    """Exporting a deep agent returns a bundle with its workspace.

    Self-contained: creates its own agent + workspace (so the test
    never depends on the live Researcher's pre-existing state —
    the workspace_key column is the seam, not a fixture).
    """
    from app.domain.agents.export_service import export_agent as do_export
    from app.domain.agents.services import AgentService
    from app.domain.agents.schemas import AgentCreate
    from sqlalchemy import select

    # The resolver's database - under test that is the TEMPORARY copy, which is
    # the whole point. This reached the LIVE database by home path, which is
    # why the suite's writes landed in production.
    from app.core.config import Paths, get_settings
    db_path = str(Paths.from_settings(get_settings()).shared_db)
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # The PROJECT root, from the resolver — this test appends "agents" to it.
    # (Pointing at agents_dir directly doubles the segment: root/agents/agents.)
    from app.core.config import Paths, get_settings

    root = Paths.from_settings(get_settings()).root

    async with session_factory() as session:
        from app.infrastructure.database.models import Agent
        # clean any leftover from a prior run — the ROW and the
        # workspace folder (a stale agent.json with a different
        # db_id is what silently breaks the export)
        old = (await session.execute(
            select(Agent).where(Agent.name == "Export Test Agent")
        )).scalar_one_or_none()
        if old:
            await session.delete(old)
            await session.commit()
        import shutil
        _stale_ws = root / "agents" / "export-test-agent"
        if _stale_ws.exists():
            shutil.rmtree(_stale_ws)

        svc = AgentService(session)
        agent = await svc.create(AgentCreate(
            name="Export Test Agent", description="export test",
            provider="deepseek", model="deepseek-v4-flash",
        ))
        agent.workspace_key = "export-test-agent"
        await session.commit()

        # scaffold a minimal workspace (absolute, project-anchored)
        ws = root / "agents" / "export-test-agent"
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "skills").mkdir(exist_ok=True)
        (ws / "agent.json").write_text(
            '{"format_version": "1.0", "name": "Export Test Agent", '
            '"db_id": %d}' % agent.id, encoding="utf-8",
        )

        bundle = await do_export(agent.id, session)
        assert bundle["format_version"] == "1.0"
        assert bundle["agent_config"]["name"] == "Export Test Agent"
        assert "agent_json" in bundle

        # cleanup: the agent + its workspace
        await session.delete(agent)
        await session.commit()
        import shutil
        shutil.rmtree(ws, ignore_errors=True)
        await engine.dispose()


@pytest.mark.asyncio
async def test_agent_folder_path_found():
    """_agent_folder_path finds a workspace-bearing agent's folder
    by column. Researcher 45 was hard-deleted 2026-08-19 — no active
    agent keeps a workspace; create one via the repository (the
    scaffold) so the path-resolver is exercised against a real
    folder."""
    import sqlite3
    # The resolver's database - under test that is the TEMPORARY copy, which is
    # the whole point. This reached the LIVE database by home path, which is
    # why the suite's writes landed in production.
    from app.core.config import Paths, get_settings
    db_path = str(Paths.from_settings(get_settings()).shared_db)
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        from app.domain.agents.repository import get_agent_repository
        repo = get_agent_repository(session)
        created = await repo.create_agent({
            "name": "export-path-probe",
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
        })
        assert created is not None
        agent_id = created.id if hasattr(created, "id") else created.get("id")
        path = await _agent_folder_path(agent_id, session)
        assert path is not None
        assert os.path.exists(path)
        assert os.path.exists(os.path.join(path, "agent.json"))
        # cleanup: hard-delete the probe (the row + the folder)
        await repo.hard_delete_agent(agent_id)
        await engine.dispose()


@pytest.mark.asyncio
async def test_agent_folder_path_not_found():
    """_agent_folder_path returns None for unknown agents."""
    # The resolver's database - under test that is the TEMPORARY copy, which is
    # the whole point. This reached the LIVE database by home path, which is
    # why the suite's writes landed in production.
    from app.core.config import Paths, get_settings
    db_path = str(Paths.from_settings(get_settings()).shared_db)
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        path = await _agent_folder_path(99999, session)
        assert path is None
        await engine.dispose()


@pytest.mark.asyncio
async def test_import_creates_agent():
    """Importing a bundle creates a new agent with restored data."""
    from app.infrastructure.database.models import Agent
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker

    # Create a test bundle
    bundle = {
        "format_version": "1.0",
        "agent_config": {
            "name": "TestImportAgent",
            "description": "Imported for testing",
            "provider": "ollama",
            "model": "llama3.2",
        },
        "skills": [
            {"filename": "test-skill.md", "content": "# Test Skill\n\nA test skill."}
        ],
        "cognitive_memory": [
            {"key": "fact", "value": "[\"Test fact\"]", "created_at": "2026-01-01", "updated_at": "2026-01-01"}
        ],
    }

    # The resolver's database - under test that is the TEMPORARY copy, which is
    # the whole point. This reached the LIVE database by home path, which is
    # why the suite's writes landed in production.
    from app.core.config import Paths, get_settings
    db_path = str(Paths.from_settings(get_settings()).shared_db)
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        imported = await import_agent(bundle, session)
        await session.flush()
        new_id = imported.agent_id

        # Verify agent was created
        query = select(Agent).where(Agent.id == new_id)
        row = (await session.execute(query)).scalar_one_or_none()
        assert row is not None
        assert row.name.startswith("TestImportAgent-imported-")
        assert row.provider == "ollama"
        # …and the row names the folder it owns (an import used to leave this NULL, so the folder
        # was invisible to every folder-side reader)
        assert row.workspace_key
        ws_key = row.workspace_key

        # Cleanup
        await session.delete(row)
        await session.flush()
        await engine.dispose()

    # Cleanup filesystem — addressed through the key, exactly as the app addresses it
    import shutil
    from app.core.config import Paths, get_settings

    shutil.rmtree(Paths.from_settings(get_settings()).agents_dir / ws_key, ignore_errors=True)
