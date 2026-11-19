"""The pipeline orchestrator — the run paths, and what a step failure records."""

import pytest
from app.services.cognitive_pipeline.pipeline import CognitivePipeline
from app.services.cognitive_pipeline.models import (
    AgentDescriptor,
    CognitiveResult,
    PipelineConfig,
)
from app.services.cognitive_pipeline.context_builder import (
    ContextBuilder,
    ContextBuilderRegistry,
    DefaultContextBuilder,
    run_context_builder,
)
from app.services.cognitive_pipeline.executor import (
    AgentExecutor,
    ExecutorRegistry,
)
from app.services.cognitive_pipeline.memory_manager import (
    MemoryManager,
    MemoryManagerRegistry,
)
from app.services.cognitive_pipeline.response_formatter import (
    ResponseFormatter,
    ResponseFormatterRegistry,
    DefaultResponseFormatter,
)
from app.services.cognitive_pipeline.models import Context, MemoryDelta, ComponentTrace


class MockExecutor(AgentExecutor):
    """Mock executor that returns a canned response without hitting any LLM."""
    async def execute(self, context: Context, agent: AgentDescriptor) -> str:
        return f"Hello, I am {agent.name}! How can I help you?"


class MockMemoryManager(MemoryManager):
    """Simplified memory manager for tests."""
    def __init__(self):
        self._store = {}
    async def remember(self, context, response, agent, session_id=None):
        return MemoryDelta(stored_keys=["turn_1"])
    async def recall(self, agent, session_id=None):
        return []


def make_mock_registries():
    """Create registries with mock components for testing."""
    ctx_reg = ContextBuilderRegistry()
    ctx_reg.register("default", DefaultContextBuilder())
    exec_reg = ExecutorRegistry()
    exec_reg.register("default", MockExecutor())
    mem_reg = MemoryManagerRegistry()
    mem_reg.register("default", MockMemoryManager())
    fmt_reg = ResponseFormatterRegistry()
    fmt_reg.register("default", DefaultResponseFormatter())
    return ctx_reg, exec_reg, mem_reg, fmt_reg


def make_mock_pipeline():
    """Create a CognitivePipeline with mock registries."""
    ctx_reg, exec_reg, mem_reg, fmt_reg = make_mock_registries()
    return CognitivePipeline(
        context_builders=ctx_reg,
        executors=exec_reg,
        memory_managers=mem_reg,
        response_formatters=fmt_reg,
    )


class TestCognitivePipeline:
    @pytest.mark.asyncio
    async def test_run_with_defaults(self):
        pipeline = make_mock_pipeline()
        agent = AgentDescriptor(
            id=1,
            name="TestBot",
            description="A test agent",
            provider="ollama",
            model="llama3.2",
            system_prompt="You are a helpful assistant.",
        )
        result = await pipeline.run(
            user_message="Tell me about Python",
            agent=agent,
        )
        assert isinstance(result, CognitiveResult)
        assert result.response
        assert "TestBot" in result.response
        assert result.error is None
        assert result.trace.context_builder.strategy == "default"
        assert result.trace.executor.strategy == "mock"
        assert result.trace.memory_manager.strategy == "mock"
        assert result.trace.response_formatter.strategy == "default"
        assert result.metrics.total_duration_ms >= 0
        assert result.memory_delta is not None

    @pytest.mark.asyncio
    async def test_run_with_session_history(self):
        pipeline = make_mock_pipeline()
        agent = AgentDescriptor(id=1, name="ChatBot", system_prompt="Assistant.")
        history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ]
        result = await pipeline.run(
            user_message="Follow up",
            agent=agent,
            session_history=history,
        )
        assert result.error is None
        assert result.response

    @pytest.mark.asyncio
    async def test_run_with_custom_config(self):
        pipeline = make_mock_pipeline()
        agent = AgentDescriptor(id=1, name="TestBot", system_prompt="Assistant.")
        config = PipelineConfig(
            context_builder="default",
            executor="default",
            memory_manager="default",
            response_formatter="default",
        )
        result = await pipeline.run(
            user_message="Hello",
            agent=agent,
            config=config,
        )
        assert result.error is None

    @pytest.mark.asyncio
    async def test_early_return_finalizes_metrics(self):
        """Dead-trace fix (2026-08-13): an EARLY return (invalid
        formatter, after the executor ran) must still carry metrics —
        duration/tokens from whatever components completed, and
        llm_calls=1 because the executor made an LLM call."""
        pipeline = make_mock_pipeline()
        agent = AgentDescriptor(id=1, name="TestBot")
        config = PipelineConfig(response_formatter="nonexistent")
        result = await pipeline.run(
            user_message="Hello",
            agent=agent,
            config=config,
        )
        assert result.error is not None
        assert result.metrics is not None
        # the mock executor ran -> one LLM call + tokens aggregated
        # from the trace (mocks run in <1ms so duration may round to
        # 0 — the SIGNAL is that metrics were finalized at all: before
        # the fix this early return had llm_calls=0 AND tokens=0)
        assert result.metrics.llm_calls == 1
        assert result.metrics.total_tokens == 10  # mock executor tokens
        assert result.metrics.total_tokens > 0

    @pytest.mark.asyncio
    async def test_executor_failure_records_attempted_call(self):
        """A FAILED executor is still an LLM call — metrics must count
        it (strategy set + error on the component trace), and duration/
        tokens must not be all-zeros."""
        from app.services.cognitive_pipeline.executor import AgentExecutor

        class FailingExecutor(AgentExecutor):
            async def execute(self, context, agent):
                raise RuntimeError("boom")

        pipeline = make_mock_pipeline()
        pipeline.executors.register("failing", FailingExecutor())
        agent = AgentDescriptor(id=1, name="TestBot")
        config = PipelineConfig(executor="failing")
        result = await pipeline.run(
            user_message="Hello",
            agent=agent,
            config=config,
        )
        assert result.error is not None
        assert "boom" in result.error
        assert result.metrics.llm_calls == 1  # attempted
        assert result.trace.executor.error == "boom"
        assert result.trace.executor.strategy == "FailingExecutor"

    @pytest.mark.asyncio
    async def test_run_with_invalid_context_builder(self):
        pipeline = make_mock_pipeline()
        agent = AgentDescriptor(id=1, name="TestBot")
        config = PipelineConfig(context_builder="nonexistent")
        result = await pipeline.run(
            user_message="Hello",
            agent=agent,
            config=config,
        )
        assert result.error is not None
        assert "nonexistent" in result.error
        assert "not registered" in result.error

    @pytest.mark.asyncio
    async def test_run_with_invalid_executor(self):
        pipeline = make_mock_pipeline()
        agent = AgentDescriptor(id=1, name="TestBot")
        config = PipelineConfig(executor="nonexistent")
        result = await pipeline.run(
            user_message="Hello",
            agent=agent,
            config=config,
        )
        assert result.error is not None
        assert "nonexistent" in result.error

    @pytest.mark.asyncio
    async def test_run_with_invalid_memory_manager(self):
        pipeline = make_mock_pipeline()
        agent = AgentDescriptor(id=1, name="TestBot")
        config = PipelineConfig(memory_manager="nonexistent")
        result = await pipeline.run(
            user_message="Hello",
            agent=agent,
            config=config,
        )
        assert result.error is not None
        assert "nonexistent" in result.error

    @pytest.mark.asyncio
    async def test_run_with_invalid_formatter(self):
        pipeline = make_mock_pipeline()
        agent = AgentDescriptor(id=1, name="TestBot")
        config = PipelineConfig(response_formatter="nonexistent")
        result = await pipeline.run(
            user_message="Hello",
            agent=agent,
            config=config,
        )
        assert result.error is not None
        assert "nonexistent" in result.error

    @pytest.mark.asyncio
    async def test_run_with_custom_registries(self):
        """Test that custom registries are used when provided."""

        class CustomContextBuilder(ContextBuilder):
            async def build(self, user_message, agent, session_history, memory_delta=None):
                return Context(
                    user_message=user_message,
                    system_prompt="Custom context",
                    agent_name=agent.name,
                    metadata={"custom": True},
                )

        class CustomExecutor(AgentExecutor):
            async def execute(self, context, agent):
                return f"Custom execution for: {context.user_message}"

        class CustomMemoryManager(MemoryManager):
            async def remember(self, context, response, agent, session_id=None):
                return MemoryDelta(stored_keys=["custom_key"])
            async def recall(self, agent, session_id=None):
                return []

        class CustomFormatter(ResponseFormatter):
            async def format(self, response, context, agent, **kwargs):
                return f"[CUSTOM] {response}"

        ctx_reg = ContextBuilderRegistry()
        ctx_reg.register("custom", CustomContextBuilder())
        exec_reg = ExecutorRegistry()
        exec_reg.register("custom", CustomExecutor())
        mem_reg = MemoryManagerRegistry()
        mem_reg.register("custom", CustomMemoryManager())
        fmt_reg = ResponseFormatterRegistry()
        fmt_reg.register("custom", CustomFormatter())

        pipeline = CognitivePipeline(
            context_builders=ctx_reg,
            executors=exec_reg,
            memory_managers=mem_reg,
            response_formatters=fmt_reg,
        )
        agent = AgentDescriptor(id=1, name="CustomBot")
        config = PipelineConfig(
            context_builder="custom",
            executor="custom",
            memory_manager="custom",
            response_formatter="custom",
        )
        result = await pipeline.run(
            user_message="Test message",
            agent=agent,
            config=config,
        )
        assert result.error is None
        assert "[CUSTOM]" in result.response
        assert "Custom execution" in result.response
        assert result.trace.context_builder.strategy != "default"

    @pytest.mark.asyncio
    async def test_run_returns_trace_with_all_components(self):
        pipeline = make_mock_pipeline()
        agent = AgentDescriptor(id=1, name="TestBot", system_prompt="Assistant.")
        result = await pipeline.run(
            user_message="Trace test",
            agent=agent,
        )
        trace = result.trace
        assert trace.context_builder.duration_ms >= 0
        assert trace.executor.duration_ms >= 0
        assert trace.memory_manager.duration_ms >= 0
        assert trace.response_formatter.duration_ms >= 0
        assert trace.total_duration_ms >= 0

    @pytest.mark.asyncio
    async def test_run_returns_metrics(self):
        pipeline = make_mock_pipeline()
        agent = AgentDescriptor(id=1, name="TestBot", system_prompt="Assistant.")
        result = await pipeline.run(
            user_message="Metrics test",
            agent=agent,
        )
        assert result.metrics.total_duration_ms >= 0
        assert result.metrics.llm_calls == 1  # Mock executor counts as 1 call
