"""The context builder — assembling history and memory, and the builder registry."""

import pytest
from app.services.cognitive_pipeline.context_builder import (
    ContextBuilderRegistry,
    DefaultContextBuilder,
    create_default_registry,
    run_context_builder,
)
from app.services.cognitive_pipeline.models import (
    AgentDescriptor,
    MemoryDelta,
)


class TestDefaultContextBuilder:
    @pytest.mark.asyncio
    async def test_build_basic_context(self):
        builder = DefaultContextBuilder()
        agent = AgentDescriptor(
            id=1,
            name="TestBot",
            description="A test agent",
            provider="ollama",
            model="llama3.2",
            system_prompt="You are a test assistant.",
        )
        context = await builder.build(
            user_message="Hello!",
            agent=agent,
            session_history=[],
        )
        assert context.user_message == "Hello!"
        assert context.system_prompt == "You are a test assistant."
        assert context.agent_name == "TestBot"
        assert context.agent_description == "A test agent"
        assert context.session_history == []
        assert context.metadata["agent_id"] == 1
        assert context.metadata["history_turns_used"] == 0

    @pytest.mark.asyncio
    async def test_build_with_history(self):
        builder = DefaultContextBuilder(max_history_turns=5)
        agent = AgentDescriptor(id=1, name="TestBot", system_prompt="Assistant.")
        history = [
            {"role": "user", "content": f"Message {i}"}
            for i in range(10)
        ]
        context = await builder.build(
            user_message="Next turn",
            agent=agent,
            session_history=history,
        )
        # Should only include last 5 turns
        assert len(context.session_history) == 5
        assert context.metadata["history_turns_used"] == 5
        assert context.metadata["total_history_available"] == 10

    @pytest.mark.asyncio
    async def test_build_with_memory_delta(self):
        builder = DefaultContextBuilder()
        agent = AgentDescriptor(id=1, name="TestBot", system_prompt="Assistant.")
        memory_delta = MemoryDelta(
            stored_keys=["turn_1"],
            compaction_triggered=True,
            summary="Previous conversation was about Python.",
        )
        context = await builder.build(
            user_message="Continue",
            agent=agent,
            session_history=[],
            memory_delta=memory_delta,
        )
        assert context.metadata["memory_summary"] == "Previous conversation was about Python."


class TestContextBuilderRegistry:
    def test_default_registry_has_default(self):
        registry = create_default_registry()
        assert "default" in registry
        assert registry.list() == ["augmented", "default", "minimal", "skill_aware"]

    def test_register_custom_builder(self):
        registry = ContextBuilderRegistry()
        builder = DefaultContextBuilder()
        registry.register("custom", builder)
        assert "custom" in registry
        assert registry.get("custom") is builder

    def test_get_missing_raises_key_error(self):
        registry = ContextBuilderRegistry()
        with pytest.raises(KeyError):
            registry.get("nonexistent")


class TestRunContextBuilder:
    @pytest.mark.asyncio
    async def test_run_with_tracing(self):
        builder = DefaultContextBuilder()
        agent = AgentDescriptor(id=1, name="TestBot", system_prompt="Assistant.")
        context, trace = await run_context_builder(
            builder=builder,
            user_message="Hello",
            agent=agent,
            session_history=[],
        )
        assert context.user_message == "Hello"
        assert trace.strategy == "default"
        assert trace.duration_ms >= 0
        assert trace.metadata["history_turns"] == 0

    @pytest.mark.asyncio
    async def test_run_propagates_exception(self):
        class FailingBuilder(DefaultContextBuilder):
            async def build(self, **kwargs):
                msg = "Intentional failure"
                raise ValueError(msg)

        with pytest.raises(ValueError, match="Intentional failure"):
            await run_context_builder(
                builder=FailingBuilder(),
                user_message="Hello",
                agent=AgentDescriptor(id=1, name="TestBot"),
                session_history=[],
            )
