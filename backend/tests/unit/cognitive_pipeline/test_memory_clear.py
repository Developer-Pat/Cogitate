"""Memory clearing — per-session, per-agent, and the isolation between agents."""

import pytest
from unittest.mock import AsyncMock, patch

from app.services.cognitive_pipeline.memory_manager import KVStoreMemoryManager
from app.services.cognitive_pipeline.models import AgentDescriptor


class TestClearMethods:
    """Tests for KVStoreMemoryManager clear methods."""

    @pytest.mark.asyncio
    async def test_clear_session(self):
        """clear_session removes a specific session's memory."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db = f.name
        try:
            mgr = KVStoreMemoryManager(db_path=db)
            agent = AgentDescriptor(id=99, name="TestAgent")
            from app.services.cognitive_pipeline.models import Context
            ctx = Context(user_message="Hello")
            await mgr.remember(ctx, "Hi", agent, "s1")
            await mgr.remember(ctx, "Hola", agent, "s2")

            turns_before = await mgr.recall(agent, "s1")
            assert len(turns_before) > 0

            await mgr.clear_session(agent, "s1")
            turns_after = await mgr.recall(agent, "s1")
            assert len(turns_after) == 0

            # Other sessions should be untouched
            s2_turns = await mgr.recall(agent, "s2")
            assert len(s2_turns) > 0
        finally:
            import os
            if os.path.exists(db): os.unlink(db)

    @pytest.mark.asyncio
    async def test_clear_agent(self):
        """clear_agent removes ALL memory for an agent."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db = f.name
        try:
            mgr = KVStoreMemoryManager(db_path=db)
            agent = AgentDescriptor(id=99, name="TestAgent")
            from app.services.cognitive_pipeline.models import Context
            ctx = Context(user_message="Hello")
            await mgr.remember(ctx, "Hi", agent, "s1")
            await mgr.remember(ctx, "Hola", agent, "s2")

            await mgr.clear_agent(agent)
            s1 = await mgr.recall(agent, "s1")
            s2 = await mgr.recall(agent, "s2")
            assert len(s1) == 0
            assert len(s2) == 0
        finally:
            import os
            if os.path.exists(db): os.unlink(db)

    @pytest.mark.asyncio
    async def test_clear_all(self):
        """clear_all removes ALL memory across all agents."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db = f.name
        try:
            mgr = KVStoreMemoryManager(db_path=db)
            from app.services.cognitive_pipeline.models import Context
            ctx = Context(user_message="Hello")
            await mgr.remember(ctx, "Hi", AgentDescriptor(id=1, name="A"), "s1")
            await mgr.remember(ctx, "Hola", AgentDescriptor(id=2, name="B"), "s2")

            await mgr.clear_all()
            a1 = await mgr.recall(AgentDescriptor(id=1, name="A"), "s1")
            b2 = await mgr.recall(AgentDescriptor(id=2, name="B"), "s2")
            assert len(a1) == 0
            assert len(b2) == 0
        finally:
            import os
            if os.path.exists(db): os.unlink(db)

    @pytest.mark.asyncio
    async def test_clear_agent_isolation(self):
        """clear_agent only clears the specified agent's memory."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db = f.name
        try:
            mgr = KVStoreMemoryManager(db_path=db)
            from app.services.cognitive_pipeline.models import Context
            ctx = Context(user_message="Hello")
            agent_a = AgentDescriptor(id=1, name="A")
            agent_b = AgentDescriptor(id=2, name="B")
            await mgr.remember(ctx, "Agent A data", agent_a, "s1")
            await mgr.remember(ctx, "Agent B data", agent_b, "s1")

            await mgr.clear_agent(agent_a)
            a1 = await mgr.recall(agent_a, "s1")
            b1 = await mgr.recall(agent_b, "s1")
            assert len(a1) == 0
            assert len(b1) > 0
            assert "Agent B data" in str(b1)
        finally:
            import os
            if os.path.exists(db): os.unlink(db)
