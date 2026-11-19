"""Tests for persistent memory (SQLite-backed KVStoreMemoryManager).

Tests DB creation, store/recall, session isolation, summary/fact recall,
and verifies the Researcher agent's per-agent DB exists and has content.

Can be run standalone or as part of the full test suite:
    uv run pytest tests/unit/cognitive_pipeline/test_memory_persistence.py -v
"""

import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from app.services.cognitive_pipeline.memory_manager import KVStoreMemoryManager
from app.services.cognitive_pipeline.models import AgentDescriptor, Context


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def agent():
    return AgentDescriptor(id=99, name="TestAgent")


@pytest_asyncio.fixture
async def manager(temp_db):
    mgr = KVStoreMemoryManager(db_path=temp_db)
    yield mgr


class TestKVStoreMemoryPersistence:
    """Tests for SQLite-backed persistent memory."""

    @pytest.mark.asyncio
    async def test_db_created(self, temp_db):
        """Verify DB file and cognitive_memory table are created on init."""
        mgr = KVStoreMemoryManager(db_path=temp_db)
        assert os.path.exists(temp_db)
        conn = sqlite3.connect(temp_db)
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        assert "cognitive_memory" in tables, f"tables={tables}"

    @pytest.mark.asyncio
    async def test_remember_returns_delta(self, manager, agent):
        """remember() returns a MemoryDelta with stored_keys."""
        ctx = Context(user_message="Test user message")
        delta = await manager.remember(context=ctx, response="Test response.", agent=agent, session_id="s1")
        assert delta is not None
        assert len(delta.stored_keys) > 0

    @pytest.mark.asyncio
    async def test_recall_retrieves_turns(self, manager, agent):
        """recall() retrieves stored turns."""
        await manager.remember(Context(user_message="Hello memory."), "Hi back.", agent, "s1")
        turns = await manager.recall(agent, "s1")
        assert len(turns) > 0

    @pytest.mark.asyncio
    async def test_multiple_turns_persist(self, manager, agent):
        """Multiple calls to remember() accumulate turns."""
        for i in range(3):
            await manager.remember(Context(user_message=f"User msg {i}"), f"Response {i}", agent, "s1")
        turns = await manager.recall(agent, "s1")
        assert len(turns) >= 3, f"expected >= 3 turns, got {len(turns)}"

    @pytest.mark.asyncio
    async def test_session_isolation(self, manager, agent):
        """Turns from different sessions are isolated."""
        await manager.remember(Context(user_message="Session A data"), "resp", agent, "sA")
        await manager.remember(Context(user_message="Session B data"), "resp", agent, "sB")
        ha = str(await manager.recall(agent, "sA"))
        hb = str(await manager.recall(agent, "sB"))
        assert "Session A data" in ha
        assert "Session B data" in hb
        assert "Session B data" not in ha
        assert "Session A data" not in hb

    @pytest.mark.asyncio
    async def test_recall_summaries_empty(self, manager, agent):
        """recall_summaries() returns empty list when no summaries exist."""
        summaries = await manager.recall_summaries(agent)
        assert isinstance(summaries, list)

    @pytest.mark.asyncio
    async def test_recall_facts_empty(self, manager, agent):
        """recall_facts() returns empty list when no facts exist."""
        facts = await manager.recall_facts(agent)
        assert isinstance(facts, list)

    @pytest.mark.asyncio
    async def test_recall_summaries_with_data(self, temp_db, agent):
        """recall_summaries() returns stored summaries."""
        mgr = KVStoreMemoryManager(db_path=temp_db)
        ts = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "INSERT OR REPLACE INTO cognitive_memory (key, value, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("summary:test-session", json.dumps({"summary": "Test summary content"}), ts, ts),
        )
        conn.commit()
        conn.close()
        summaries = await mgr.recall_summaries(agent)
        assert len(summaries) >= 1
        assert "Test summary" in summaries[0]

    @pytest.mark.asyncio
    async def test_recall_facts_with_data(self, temp_db, agent):
        """recall_facts() returns stored facts."""
        mgr = KVStoreMemoryManager(db_path=temp_db)
        ts = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "INSERT OR REPLACE INTO cognitive_memory (key, value, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("agent_99:facts", json.dumps(["User likes concise", "Python 3.12"]), ts, ts),
        )
        conn.commit()
        conn.close()
        facts = await mgr.recall_facts(agent)
        assert isinstance(facts, list)
        assert len(facts) > 0


def _researcher_db() -> str:
    """The Researcher's per-agent memory DB, from the resolver.

    Under test this is the TEMPORARY agents root, so the file is absent and the
    class skips - which is correct. Reaching a home path instead meant these
    tests asserted that the DEVELOPER'S installation happened to contain a file:
    a test of the machine, not of the code.
    """
    from app.core.config import Paths, get_settings

    return str(Paths.from_settings(get_settings()).agents_dir / "researcher" / "cognitive_memory.db")


@pytest.mark.skipif(
    not os.path.exists(_researcher_db()),
    reason="No per-agent Researcher DB in this installation (expected under test)",
)
class TestResearcherAgentDB:
    """Tests for the Researcher agent's per-agent memory database."""

    RESEARCHER_DB = property(lambda self: _researcher_db())

    def test_db_exists(self):
        assert os.path.exists(self.RESEARCHER_DB)

    def test_db_has_content(self):
        size = os.path.getsize(self.RESEARCHER_DB)
        assert size > 4096, f"DB only {size} bytes -- likely empty"

    def test_has_cognitive_memory_table(self):
        conn = sqlite3.connect(self.RESEARCHER_DB)
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        assert "cognitive_memory" in tables, f"tables={tables}"

    def test_has_entries(self):
        conn = sqlite3.connect(self.RESEARCHER_DB)
        count = conn.execute("SELECT COUNT(*) FROM cognitive_memory").fetchone()[0]
        conn.close()
        assert count > 0, "cognitive_memory table is empty"
