"""
Cognitive Pipeline Service.

A 4-component backend pipeline that produces structured cognitive results.
Consumed by SSE (human UI) and JSON (agent API) output adapters.

Components:
    - Context Builder: Assembles context from session, agent, and memory
    - Agent Executor: Executes the agent's logic (LLM call + tool execution)
    - Memory Manager: Manages conversation memory (storage, compaction)
    - Response Formatter: Formats the final response for the consumer
"""

from .models import (
    CognitiveResult,
    CognitiveTrace,
    CognitiveMetrics,
    ComponentTrace,
    MemoryDelta,
    Context,
    AgentDescriptor,
    PipelineConfig,
)
from .registry import Registry
from .context_builder import (
    ContextBuilder,
    ContextBuilderRegistry,
    DefaultContextBuilder,
)
from .executor import (
    AgentExecutor,
    ExecutorRegistry,
    DefaultExecutor,
    LiteLLMExecutor,
)
from .memory_manager import (
    MemoryManager,
    MemoryManagerRegistry,
    DefaultMemoryManager,
)
from .response_formatter import (
    ResponseFormatter,
    ResponseFormatterRegistry,
    DefaultResponseFormatter,
)
from .pipeline import CognitivePipeline

__all__ = [
    # Models
    "CognitiveResult",
    "CognitiveTrace",
    "CognitiveMetrics",
    "ComponentTrace",
    "MemoryDelta",
    "Context",
    "AgentDescriptor",
    "PipelineConfig",
    # Registry
    "Registry",
    # Context Builder
    "ContextBuilder",
    "ContextBuilderRegistry",
    "DefaultContextBuilder",
    # Executor
    "AgentExecutor",
    "ExecutorRegistry",
    "DefaultExecutor",
    "LiteLLMExecutor",
    # Memory Manager
    "MemoryManager",
    "MemoryManagerRegistry",
    "DefaultMemoryManager",
    # Response Formatter
    "ResponseFormatter",
    "ResponseFormatterRegistry",
    "DefaultResponseFormatter",
    # Pipeline
    "CognitivePipeline",
]
