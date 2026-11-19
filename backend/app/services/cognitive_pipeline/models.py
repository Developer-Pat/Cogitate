"""
Data models for the Cognitive Pipeline Service.

Defines the structured output format produced by the pipeline and consumed
by output adapters (SSE for humans, JSON for agents).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:  # the resolver's answer type — annotation only, so the pipeline stays light
    from app.domain.providers.capabilities import ServiceCandidate


# ---------------------------------------------------------------------------
# Component-level trace
# ---------------------------------------------------------------------------

@dataclass
class ComponentTrace:
    """Timing and metadata for a single pipeline component execution."""

    strategy: str = "unknown"
    """Which implementation was used (e.g. 'augmented', 'noop', 'hybrid')."""

    duration_ms: int = 0
    """Wall-clock duration of the component in milliseconds."""

    tokens_used: int = 0
    """Approximate total token count consumed by this component."""

    input_tokens: int = 0
    """Tokens consumed as input (prompt) by this component."""

    output_tokens: int = 0
    """Tokens generated as output (completion) by this component."""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Component-specific details (e.g. sources used, compaction triggered)."""

    error: Optional[str] = None
    """Error message if this component failed (None = success)."""


# ---------------------------------------------------------------------------
# Full pipeline trace
# ---------------------------------------------------------------------------

@dataclass
class CognitiveTrace:
    """Aggregated trace across all pipeline components."""

    context_builder: ComponentTrace = field(default_factory=ComponentTrace)
    executor: ComponentTrace = field(default_factory=ComponentTrace)
    memory_manager: ComponentTrace = field(default_factory=ComponentTrace)
    response_formatter: ComponentTrace = field(default_factory=ComponentTrace)

    @property
    def total_duration_ms(self) -> int:
        return (
            self.context_builder.duration_ms
            + self.executor.duration_ms
            + self.memory_manager.duration_ms
            + self.response_formatter.duration_ms
        )

    @property
    def total_tokens(self) -> int:
        return (
            self.context_builder.tokens_used
            + self.executor.tokens_used
            + self.memory_manager.tokens_used
            + self.response_formatter.tokens_used
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "context_builder": _component_to_dict(self.context_builder),
            "executor": _component_to_dict(self.executor),
            "memory_manager": _component_to_dict(self.memory_manager),
            "response_formatter": _component_to_dict(self.response_formatter),
            "total_duration_ms": self.total_duration_ms,
            "total_tokens": self.total_tokens,
        }


def _component_to_dict(c: ComponentTrace) -> Dict[str, Any]:
    return {
        "strategy": c.strategy,
        "duration_ms": c.duration_ms,
        "tokens_used": c.tokens_used,
        "input_tokens": c.input_tokens,
        "output_tokens": c.output_tokens,
        "metadata": c.metadata,
        "error": c.error,
    }


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

@dataclass
class CognitiveMetrics:
    """Aggregate performance metrics for a pipeline run."""

    total_duration_ms: int = 0
    total_tokens: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    cache_hits: int = 0


# ---------------------------------------------------------------------------
# Memory delta
# ---------------------------------------------------------------------------

@dataclass
class MemoryDelta:
    """What changed in memory as a result of this pipeline run."""

    stored_keys: List[str] = field(default_factory=list)
    """Keys that were added or updated in memory."""

    evicted_keys: List[str] = field(default_factory=list)
    """Keys that were removed from memory."""

    compaction_triggered: bool = False
    """Whether memory compaction was triggered."""

    summary: Optional[str] = None
    """Optional summary text if LLM summarization was used."""


# ---------------------------------------------------------------------------
# Pipeline result
# ---------------------------------------------------------------------------

@dataclass
class CognitiveResult:
    """The structured output of a full cognitive pipeline run."""

    response: str
    """Final formatted response text."""

    trace: CognitiveTrace = field(default_factory=CognitiveTrace)
    """Per-component timing and metadata."""

    metrics: CognitiveMetrics = field(default_factory=CognitiveMetrics)
    """Aggregate performance metrics."""

    memory_delta: Optional[MemoryDelta] = None
    """What changed in memory this turn (None = no change)."""

    error: Optional[str] = None
    """Error message if the pipeline failed (None = success)."""


# ---------------------------------------------------------------------------
# Pipeline input types
# ---------------------------------------------------------------------------

@dataclass
class Context:
    """The assembled context passed through the pipeline."""

    user_message: str
    """The raw user message."""

    system_prompt: str = ""
    """The agent's system prompt."""

    session_history: List[Dict[str, Any]] = field(default_factory=list)
    """Previous turns in the session."""

    agent_name: str = ""
    """Name of the agent being executed."""

    agent_description: str = ""
    """Description of the agent."""

    rag_results: List[str] = field(default_factory=list)
    """RAG retrieval results if applicable."""

    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    """Results from tool executions."""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional context metadata."""

    capability_chains: Dict[str, Tuple["ServiceCandidate", ...]] = field(default_factory=dict)
    """The RESOLVER's ordered chains for this turn, KEYED BY CAPABILITY slug (`chat`, `summary`,
    `memory`) — resolved where the session is and carried here because the components that need one
    hold NO session (the memory manager is a registered singleton built at import, and logs usage over
    a raw sqlite3 connection). Empty = nothing was resolved, and a consumer that needs a chain must
    SKIP and say so rather than fall back to a service name written in code."""


@dataclass
class AgentDescriptor:
    """Describes an agent for the pipeline."""

    id: int
    name: str
    description: str = ""
    provider: str = ""
    model: str = ""
    system_prompt: str = ""
    cognitive_config: Dict[str, str] = field(default_factory=dict)
    """Mapping of component name to strategy name (e.g. {'executor': 'hybrid'})."""
    cognitive_profile_id: Optional[int] = None
    """FK to CognitiveProfile for agent-level pipeline configuration."""
    fallback_enabled: bool = False
    """If True, on provider failure try preferred_providers (or the
    default chain) before surfacing the error. Default False — fail
    visibly (F4: opt-in so fallback never silently masks failures)."""
    preferred_providers: List[str] = field(default_factory=list)
    """Ordered provider names to try on failure (fallback chain). Empty
    = use the built-in default chain (openrouter → deepseek → ollama)."""
    output_budget: Optional[int] = None
    """The RESOLVER's decision for this run, when whoever built the descriptor
    resolved it (G-F: `/agent-chat`). None = no resolver answer was supplied, and
    the executor's own default speaks — the pre-G-F behaviour, preserved for every
    caller that has no resolver reading to give."""

    candidates: Tuple["ServiceCandidate", ...] = ()
    """The RESOLVER's ordered CHAIN for this run — the lead candidate first, its
    backups after — when whoever built the descriptor resolved it (R3, the same
    seam as `output_budget`: the resolution belongs where the session is).
    Empty = no reading was supplied, and the executor's own single attempt
    (`provider`/`model` above) speaks, which is the pre-resolution behaviour."""

    chain_reason: Optional[str] = None
    """WHICH RUNG of the resolver's ladder answered for `candidates` — `capability config`,
    `agent profile`, `global default`, `none`, or `disabled` (phase 6, G5). `disabled` is the one a
    consumer must ACT on rather than walk: it means the capability is switched off, so there is no
    chain to try. Carried here because the consumer holding the descriptor (the chat router) is the
    one that must refuse, and it must not re-resolve to find out."""


@dataclass
class PipelineConfig:
    """Configuration for a pipeline run."""

    context_builder: str = "default"
    executor: str = "default"
    memory_manager: str = "default"
    response_formatter: str = "default"
    memory_profile_persistence: str = "memory"
    compaction_threshold: int | None = None
    summarization_enabled: bool = False
    agent_folder: str | None = None
    vector_store: str | None = None

    @classmethod
    def from_dict(cls, config: Dict[str, str]) -> "PipelineConfig":
        return cls(
            context_builder=config.get("context_builder", "default"),
            executor=config.get("executor", "default"),
            memory_manager=config.get("memory_manager", "default"),
            response_formatter=config.get("response_formatter", "default"),
        )

    def to_dict(self) -> Dict[str, str]:
        return {
            "context_builder": self.context_builder,
            "executor": self.executor,
            "memory_manager": self.memory_manager,
            "response_formatter": self.response_formatter,
        }


# ---------------------------------------------------------------------------
# Utility: timing context manager
# ---------------------------------------------------------------------------

class Timer:
    """Simple context manager for measuring wall-clock duration."""

    def __init__(self) -> None:
        self.start: float = 0.0
        self.duration_ms: int = 0

    def __enter__(self) -> "Timer":
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        self.duration_ms = int((time.perf_counter() - self.start) * 1000)
