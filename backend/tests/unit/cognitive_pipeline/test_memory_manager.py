"""The memory manager — storing turns, compaction at the limit, and per-agent recall."""

import pytest
from app.services.cognitive_pipeline.memory_manager import (
    MemoryManagerRegistry,
    DefaultMemoryManager,
    create_default_registry,
    run_memory_manager,
)
from app.services.cognitive_pipeline.models import (
    AgentDescriptor,
    Context,
)


class TestDefaultMemoryManager:
    @pytest.mark.asyncio
    async def test_remember_stores_turn(self):
        manager = DefaultMemoryManager()
        agent = AgentDescriptor(id=1, name="TestBot")
        context = Context(
            user_message="Hello",
            agent_name="TestBot",
        )
        delta = await manager.remember(
            context=context,
            response="Hi there!",
            agent=agent,
        )
        assert len(delta.stored_keys) >= 1
        assert delta.compaction_triggered is False

        # Verify recall works
        memories = await manager.recall(agent=agent)
        assert len(memories) == 2  # user + assistant
        assert memories[0]["role"] == "user"
        assert memories[0]["content"] == "Hello"
        assert memories[1]["role"] == "assistant"
        assert memories[1]["content"] == "Hi there!"

    @pytest.mark.asyncio
    async def test_remember_multiple_turns(self):
        manager = DefaultMemoryManager()
        agent = AgentDescriptor(id=1, name="TestBot")
        context = Context(user_message="Turn 1", agent_name="TestBot")

        for i in range(3):
            await manager.remember(
                context=Context(user_message=f"Turn {i+1}", agent_name="TestBot"),
                response=f"Response {i+1}",
                agent=agent,
            )

        memories = await manager.recall(agent=agent)
        assert len(memories) == 6  # 3 turns × 2 messages

    @pytest.mark.asyncio
    async def test_compaction_triggers_at_limit(self):
        manager = DefaultMemoryManager(max_turns=2)
        agent = AgentDescriptor(id=1, name="TestBot")

        # First 2 turns should not trigger compaction
        for i in range(2):
            delta = await manager.remember(
                context=Context(user_message=f"Turn {i+1}", agent_name="TestBot"),
                response=f"Response {i+1}",
                agent=agent,
            )
            assert delta.compaction_triggered is False

        # Third turn should trigger compaction (exceeds 2 turns × 2 messages = 4)
        delta = await manager.remember(
            context=Context(user_message="Turn 3", agent_name="TestBot"),
            response="Response 3",
            agent=agent,
        )
        assert delta.compaction_triggered is True
        assert len(delta.evicted_keys) > 0

    @pytest.mark.asyncio
    async def test_recall_empty_returns_empty_list(self):
        manager = DefaultMemoryManager()
        agent = AgentDescriptor(id=1, name="NewBot")
        memories = await manager.recall(agent=agent)
        assert memories == []

    @pytest.mark.asyncio
    async def test_different_agents_have_separate_memory(self):
        manager = DefaultMemoryManager()
        agent_a = AgentDescriptor(id=1, name="AgentA")
        agent_b = AgentDescriptor(id=2, name="AgentB")

        await manager.remember(
            context=Context(user_message="Hello A", agent_name="AgentA"),
            response="Hi from A",
            agent=agent_a,
        )

        memories_a = await manager.recall(agent=agent_a)
        memories_b = await manager.recall(agent=agent_b)
        assert len(memories_a) == 2
        assert len(memories_b) == 0


class TestMemoryManagerRegistry:
    def test_default_registry_has_default(self):
        registry = create_default_registry()
        assert "default" in registry
        assert registry.list() == ["default", "kv_store", "noop"]

    def test_register_custom_manager(self):
        registry = MemoryManagerRegistry()
        manager = DefaultMemoryManager()
        registry.register("custom", manager)
        assert registry.get("custom") is manager

    def test_get_missing_raises_key_error(self):
        registry = MemoryManagerRegistry()
        with pytest.raises(KeyError):
            registry.get("nonexistent")


class TestRunMemoryManager:
    @pytest.mark.asyncio
    async def test_run_with_tracing(self):
        manager = DefaultMemoryManager()
        agent = AgentDescriptor(id=1, name="TestBot")
        context = Context(user_message="Hello", agent_name="TestBot")

        delta, trace = await run_memory_manager(
            manager=manager,
            context=context,
            response="Hi!",
            agent=agent,
        )
        assert delta.stored_keys
        assert trace.strategy == "default"
        assert trace.duration_ms >= 0
        assert trace.metadata["stored_keys"] == delta.stored_keys

    @pytest.mark.asyncio
    async def test_run_propagates_exception(self):
        class FailingManager(DefaultMemoryManager):
            async def remember(self, **kwargs):
                msg = "Memory failure"
                raise RuntimeError(msg)

        with pytest.raises(RuntimeError, match="Memory failure"):
            await run_memory_manager(
                manager=FailingManager(),
                context=Context(user_message="Hi", agent_name="Test"),
                response="Hello",
                agent=AgentDescriptor(id=1, name="Test"),
            )
