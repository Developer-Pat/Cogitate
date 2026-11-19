"""The response formatter — pass-through, and the trace and metrics decoration."""

import pytest
from app.services.cognitive_pipeline.response_formatter import (
    ResponseFormatterRegistry,
    DefaultResponseFormatter,
    create_default_registry,
    run_response_formatter,
)
from app.services.cognitive_pipeline.models import (
    AgentDescriptor,
    Context,
    CognitiveTrace,
    CognitiveMetrics,
    MemoryDelta,
)


class TestDefaultResponseFormatter:
    @pytest.mark.asyncio
    async def test_format_passthrough(self):
        formatter = DefaultResponseFormatter()
        agent = AgentDescriptor(id=1, name="TestBot")
        context = Context(user_message="Hello", agent_name="TestBot")

        formatted = await formatter.format(
            response="Raw response text",
            context=context,
            agent=agent,
        )
        assert formatted == "Raw response text"

    @pytest.mark.asyncio
    async def test_format_with_trace_and_metrics(self):
        formatter = DefaultResponseFormatter()
        agent = AgentDescriptor(id=1, name="TestBot")
        context = Context(user_message="Hello", agent_name="TestBot")
        trace = CognitiveTrace()
        metrics = CognitiveMetrics(total_tokens=100)
        memory_delta = MemoryDelta(stored_keys=["turn_1"])

        formatted = await formatter.format(
            response="Response with context",
            context=context,
            agent=agent,
            trace=trace,
            metrics=metrics,
            memory_delta=memory_delta,
        )
        # Default formatter ignores extra params
        assert formatted == "Response with context"


class TestResponseFormatterRegistry:
    def test_default_registry_has_default(self):
        registry = create_default_registry()
        assert "default" in registry
        assert registry.list() == ["default", "direct_yield", "structured"]

    def test_register_custom_formatter(self):
        registry = ResponseFormatterRegistry()
        formatter = DefaultResponseFormatter()
        registry.register("custom", formatter)
        assert registry.get("custom") is formatter

    def test_get_missing_raises_key_error(self):
        registry = ResponseFormatterRegistry()
        with pytest.raises(KeyError):
            registry.get("nonexistent")


class TestRunResponseFormatter:
    @pytest.mark.asyncio
    async def test_run_with_tracing(self):
        formatter = DefaultResponseFormatter()
        agent = AgentDescriptor(id=1, name="TestBot")
        context = Context(user_message="Hello", agent_name="TestBot")

        formatted, trace = await run_response_formatter(
            formatter=formatter,
            response="Raw output",
            context=context,
            agent=agent,
        )
        assert formatted == "Raw output"
        assert trace.strategy == "default"
        assert trace.duration_ms >= 0
        assert trace.metadata["was_modified"] is False

    @pytest.mark.asyncio
    async def test_run_propagates_exception(self):
        class FailingFormatter(DefaultResponseFormatter):
            async def format(self, **kwargs):
                msg = "Format failure"
                raise RuntimeError(msg)

        with pytest.raises(RuntimeError, match="Format failure"):
            await run_response_formatter(
                formatter=FailingFormatter(),
                response="test",
                context=Context(user_message="Hi", agent_name="Test"),
                agent=AgentDescriptor(id=1, name="Test"),
            )
