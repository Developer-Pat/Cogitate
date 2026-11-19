"""The AGENTS shelf — a trashed agent, the residue beside it, and the way back.

What is worth testing here is the ROW-BACKED distinction the shelf exists to
make: an entry the database names is an agent that can be restored; an entry no
row names is residue that can only be purged. The old shape could not tell them
apart because it had no shelf to read — deleted workspaces sat under
`agents/.archived/`, reachable only through the row that had just been
soft-deleted.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Paths
from app.domain.agents.workspace import AGENTS_ROOT
from app.infrastructure.database.models import Agent
from app.domain.trash.services import TrashService

SHELF = "agents"


@pytest.fixture
def trash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A trash inside a temp dir. A test must never touch the real one."""
    target = tmp_path / "trash"
    monkeypatch.setattr(Paths, "trash_dir", target)
    return target


async def _a_trashed_agent(session: AsyncSession) -> tuple[int, Path]:
    """Create an agent, delete it, and return (id, where its workspace landed)."""
    from app.domain.agents.repository import get_agent_repository

    repo = get_agent_repository(session)
    agent = await repo.create_agent({
        "name": "Shelf Test Agent",
        "description": "x",
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
    })
    report = await repo.delete_agent(agent.id)
    return agent.id, Path(report["archived_path"])


async def test_deleting_an_agent_lands_it_on_the_SHELF_as_restorable(
    test_session: AsyncSession, trash: Path,
) -> None:
    """The move is the delete: the workspace is ON THE SHELF, and the row is
    what makes it restorable — the page has to be able to say which is which."""
    agent_id, landed = await _a_trashed_agent(test_session)

    assert landed.parent == trash / SHELF          # on the shelf, not in .archived
    assert landed.is_dir()

    listing = await TrashService().listing(SHELF, test_session)
    entry = next(e for e in listing["entries"] if e["name"] == landed.name)
    assert entry["restorable"] is True
    assert "Shelf Test Agent" in entry["note"]
    # the LIVE workspace is gone — read through the same root the code uses
    assert not (AGENTS_ROOT / "shelf-test-agent").exists()


async def test_RESTORE_through_the_shelf_puts_the_agent_back(
    test_session: AsyncSession, trash: Path,
) -> None:
    """A row-backed entry is the whole point of the `restorable` flag: the shelf
    is a way back, not just a place things sit."""
    from app.domain.agents.repository import get_agent_repository

    agent_id, landed = await _a_trashed_agent(test_session)
    service = TrashService()

    result = await service.restore(SHELF, landed.name, test_session)

    assert result["restored"] is True
    assert result["agent_id"] == agent_id
    assert not landed.exists()                       # the shelf entry is gone
    row = (await test_session.execute(
        select(Agent).where(Agent.id == agent_id)
    )).scalar_one()
    assert row.deleted_at is None
    assert row.archived_path is None
    assert (AGENTS_ROOT / str(row.workspace_key)).is_dir()


async def test_PURGE_of_a_trashed_agent_scrubs_row_and_folder(
    test_session: AsyncSession, trash: Path,
) -> None:
    """Purging a trashed agent is the hard delete, reached from the shelf: the
    row, its references and the folder all go."""
    agent_id, landed = await _a_trashed_agent(test_session)

    purged = await TrashService().purge(SHELF, landed.name, test_session)

    assert purged is True
    assert not landed.exists()
    gone = (await test_session.execute(
        select(Agent).where(Agent.id == agent_id)
    )).scalars().first()
    assert gone is None


async def test_a_FOLDER_WITH_NO_ROW_is_residue_and_says_so(
    test_session: AsyncSession, trash: Path,
) -> None:
    """The class that used to be invisible. It is listed, it is NOT offered a
    way back (there is nowhere to put it), and it can be purged."""
    orphan = trash / SHELF / "ghost-agent-20260101_000000"
    orphan.mkdir(parents=True)
    (orphan / "agent.json").write_text("{}")
    service = TrashService()

    listing = await service.listing(SHELF, test_session)
    entry = next(e for e in listing["entries"] if e["name"] == orphan.name)

    assert entry["restorable"] is False
    assert "residue" in entry["note"]

    with pytest.raises(ValueError) as caught:
        await service.restore(SHELF, orphan.name, test_session)
    assert "residue cannot be restored" in str(caught.value)
    assert orphan.is_dir()

    assert await service.purge(SHELF, orphan.name, test_session) is True
    assert not orphan.exists()


async def test_EMPTY_clears_both_kinds(
    test_session: AsyncSession, trash: Path,
) -> None:
    """Emptying the agent shelf takes the agents AND the residue — the row-backed
    cleanup and the folder removal in one act, with nothing asked of the caller."""
    agent_id, landed = await _a_trashed_agent(test_session)
    orphan = trash / SHELF / "ghost-agent-20260101_000001"
    orphan.mkdir(parents=True)
    service = TrashService()

    answer = await service.empty(SHELF, test_session)

    assert answer["deleted"] == 2
    assert not landed.exists()
    assert not orphan.exists()
    gone = (await test_session.execute(
        select(Agent).where(Agent.id == agent_id)
    )).scalars().first()
    assert gone is None
