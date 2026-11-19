"""The cognitive-pipeline data models — defaults, totals, and serialisation."""

import asyncio

import pytest
from app.services.cognitive_pipeline.models import (
    CognitiveResult,
    CognitiveTrace,
    CognitiveMetrics,
    ComponentTrace,
    MemoryDelta,
    Context,
    AgentDescriptor,
    PipelineConfig,
    Timer,
)


class TestComponentTrace:
    def test_default_values(self):
        trace = ComponentTrace()
        assert trace.strategy == "unknown"
        assert trace.duration_ms == 0
        assert trace.tokens_used == 0
        assert trace.metadata == {}
        assert trace.error is None

    def test_with_values(self):
        trace = ComponentTrace(
            strategy="augmented",
            duration_ms=150,
            tokens_used=500,
            metadata={"sources": ["wiki"]},
        )
        assert trace.strategy == "augmented"
        assert trace.duration_ms == 150
        assert trace.tokens_used == 500
        assert trace.metadata == {"sources": ["wiki"]}


class TestCognitiveTrace:
    def test_default_values(self):
        trace = CognitiveTrace()
        assert trace.total_duration_ms == 0
        assert trace.total_tokens == 0

    def test_totals(self):
        trace = CognitiveTrace(
            context_builder=ComponentTrace(duration_ms=10, tokens_used=100),
            executor=ComponentTrace(duration_ms=200, tokens_used=300),
            memory_manager=ComponentTrace(duration_ms=5, tokens_used=0),
            response_formatter=ComponentTrace(duration_ms=2, tokens_used=50),
        )
        assert trace.total_duration_ms == 217
        assert trace.total_tokens == 450

    def test_to_dict(self):
        trace = CognitiveTrace(
            context_builder=ComponentTrace(strategy="default", duration_ms=10),
        )
        d = trace.to_dict()
        assert d["context_builder"]["strategy"] == "default"
        assert d["context_builder"]["duration_ms"] == 10
        assert d["total_duration_ms"] == 10
        assert d["total_tokens"] == 0


class TestCognitiveMetrics:
    def test_default_values(self):
        m = CognitiveMetrics()
        assert m.total_duration_ms == 0
        assert m.total_tokens == 0
        assert m.llm_calls == 0
        assert m.tool_calls == 0
        assert m.cache_hits == 0


class TestMemoryDelta:
    def test_default_values(self):
        d = MemoryDelta()
        assert d.stored_keys == []
        assert d.evicted_keys == []
        assert d.compaction_triggered is False
        assert d.summary is None

    def test_with_values(self):
        d = MemoryDelta(
            stored_keys=["turn_1", "turn_2"],
            evicted_keys=["turn_0"],
            compaction_triggered=True,
            summary="Summarized previous turns",
        )
        assert d.stored_keys == ["turn_1", "turn_2"]
        assert d.compaction_triggered is True
        assert d.summary == "Summarized previous turns"


class TestCognitiveResult:
    def test_required_fields(self):
        result = CognitiveResult(response="Hello, world!")
        assert result.response == "Hello, world!"
        assert result.error is None
        assert result.memory_delta is None

    def test_with_error(self):
        result = CognitiveResult(response="", error="Something went wrong")
        assert result.error == "Something went wrong"

    def test_full_result(self):
        result = CognitiveResult(
            response="Formatted response",
            trace=CognitiveTrace(
                executor=ComponentTrace(duration_ms=100, tokens_used=50)
            ),
            metrics=CognitiveMetrics(total_duration_ms=100, total_tokens=50),
            memory_delta=MemoryDelta(stored_keys=["turn_1"]),
        )
        assert result.trace.executor.duration_ms == 100
        assert result.metrics.total_tokens == 50
        assert result.memory_delta.stored_keys == ["turn_1"]


class TestContext:
    def test_default_values(self):
        ctx = Context(user_message="Hello")
        assert ctx.user_message == "Hello"
        assert ctx.system_prompt == ""
        assert ctx.session_history == []
        assert ctx.rag_results == []
        assert ctx.tool_results == []

    def test_with_history(self):
        ctx = Context(
            user_message="Tell me about X",
            system_prompt="You are a helpful assistant",
            session_history=[{"role": "user", "content": "Hi"}],
            agent_name="TestBot",
        )
        assert len(ctx.session_history) == 1
        assert ctx.agent_name == "TestBot"


class TestAgentDescriptor:
    def test_minimal(self):
        agent = AgentDescriptor(id=1, name="TestAgent")
        assert agent.id == 1
        assert agent.name == "TestAgent"
        assert agent.cognitive_config == {}

    def test_with_config(self):
        agent = AgentDescriptor(
            id=2,
            name="Researcher",
            provider="openai",
            model="gpt-4",
            system_prompt="Research mode",
            cognitive_config={"executor": "hybrid", "memory_manager": "kv_store"},
        )
        assert agent.cognitive_config["executor"] == "hybrid"


class TestPipelineConfig:
    def test_default_values(self):
        config = PipelineConfig()
        assert config.context_builder == "default"
        assert config.executor == "default"
        assert config.memory_manager == "default"
        assert config.response_formatter == "default"

    def test_from_dict(self):
        config = PipelineConfig.from_dict({
            "context_builder": "augmented",
            "executor": "hybrid",
        })
        assert config.context_builder == "augmented"
        assert config.executor == "hybrid"
        assert config.memory_manager == "default"  # not specified

    def test_from_dict_empty(self):
        config = PipelineConfig.from_dict({})
        assert config.context_builder == "default"

    def test_to_dict(self):
        config = PipelineConfig(
            context_builder="minimal",
            executor="direct",
            memory_manager="noop",
            response_formatter="template",
        )
        d = config.to_dict()
        assert d["context_builder"] == "minimal"
        assert d["executor"] == "direct"
        assert d["memory_manager"] == "noop"
        assert d["response_formatter"] == "template"


class TestTimer:
    @pytest.mark.asyncio
    async def test_timer_records_duration(self):
        timer = Timer()
        with timer:
            await asyncio.sleep(0.01)
        assert timer.duration_ms >= 10  # at least 10ms

    def test_timer_zero_for_no_op(self):
        timer = Timer()
        with timer:
            pass
        assert timer.duration_ms >= 0
