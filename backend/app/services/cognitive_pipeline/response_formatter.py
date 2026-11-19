"""
Response Formatter — pipeline component that formats the agent's output.

The Response Formatter takes the raw response from the Executor and
transforms it into the final output. Strategies include direct yield
(pass-through), LLM synthesis, template filling, and error formatting.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List

from .models import (
    AgentDescriptor,
    CognitiveMetrics,
    CognitiveTrace,
    ComponentTrace,
    Context,
    MemoryDelta,
    Timer,
)
from .registry import Registry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class ResponseFormatter(ABC):
    """Interface for response formatting strategies."""

    @abstractmethod
    async def format(
        self,
        response: str,
        context: Context,
        agent: AgentDescriptor,
        trace: CognitiveTrace | None = None,
        metrics: CognitiveMetrics | None = None,
        memory_delta: MemoryDelta | None = None,
    ) -> str:
        """Format the raw response into the final output.

        Args:
            response: The raw response text from the executor.
            context: The context used for this turn.
            agent: Descriptor of the agent.
            trace: Optional full pipeline trace (for debug/verbose modes).
            metrics: Optional pipeline metrics.
            memory_delta: Optional memory changes.

        Returns:
            The formatted response string.
        """
        ...


# ---------------------------------------------------------------------------
# Default implementation
# ---------------------------------------------------------------------------

class DefaultResponseFormatter(ResponseFormatter):
    """Default response formatter — direct yield (pass-through).

    Returns the raw response as-is. No LLM synthesis or template filling.
    """

    async def format(
        self,
        response: str,
        context: Context,
        agent: AgentDescriptor,
        trace: CognitiveTrace | None = None,
        metrics: CognitiveMetrics | None = None,
        memory_delta: MemoryDelta | None = None,
    ) -> str:
        return response



class DirectYieldFormatter(ResponseFormatter):
    """Direct-yield response formatter.

    Returns the raw LLM output with no post-processing or formatting.
    Useful when the LLM output is already in the desired format
    (e.g., structured JSON, code blocks).
    """

    async def format(
        self,
        response: str,
        context: Context,
        agent: AgentDescriptor,
        trace: CognitiveTrace | None = None,
        metrics: CognitiveMetrics | None = None,
        memory_delta: MemoryDelta | None = None,
    ) -> str:
        return response



class StructuredFormatter(ResponseFormatter):
    """Structured response formatter.

    Attempts to parse the LLM response as JSON and validate it against
    an optional schema. If the response is valid JSON it is returned
    as-is (pretty-printed). If parsing fails, the raw text is returned
    with an error note in metadata.

    Useful for agent-to-agent communication where structured output
    is required, or for forcing JSON responses from the LLM.
    """

    def __init__(self, require_valid_json: bool = False) -> None:
        self.require_valid_json = require_valid_json

    async def format(
        self,
        response: str,
        context: Context,
        agent: AgentDescriptor,
        trace: CognitiveTrace | None = None,
        metrics: CognitiveMetrics | None = None,
        memory_delta: MemoryDelta | None = None,
    ) -> str:
        import json as _json

        # Try to parse as JSON
        stripped = response.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                parsed = _json.loads(stripped)
                return _json.dumps(parsed, indent=2)
            except _json.JSONDecodeError as e:
                if self.require_valid_json:
                    # Return an error JSON instead
                    return _json.dumps({
                        "error": "Response was not valid JSON",
                        "parse_error": str(e),
                        "raw_response_preview": response[:500],
                    }, indent=2)

        return response


def _json_depth(obj) -> int:
    """Return the nesting depth of a JSON object."""
    if isinstance(obj, dict):
        return 1 + max((_json_depth(v) for v in obj.values()), default=0)
    if isinstance(obj, list):
        return 1 + max((_json_depth(item) for item in obj), default=0)
    return 0

# ---------------------------------------------------------------------------
# Registry wrapper
# ---------------------------------------------------------------------------

class ResponseFormatterRegistry:
    """Typed registry wrapper for ResponseFormatter implementations."""

    def __init__(self) -> None:
        self._registry = Registry[ResponseFormatter]()

    def register(self, name: str, formatter: ResponseFormatter, overwrite: bool = False) -> None:
        self._registry.register(name, formatter, overwrite=overwrite)

    def get(self, name: str) -> ResponseFormatter:
        return self._registry.get(name)

    def list(self) -> List[str]:
        return self._registry.list()

    def __contains__(self, name: str) -> bool:
        return name in self._registry


def create_default_registry() -> ResponseFormatterRegistry:
    """Create a registry pre-populated with the default implementation."""
    registry = ResponseFormatterRegistry()
    registry.register("default", DefaultResponseFormatter())
    registry.register("direct_yield", DirectYieldFormatter())
    registry.register("structured", StructuredFormatter())
    return registry


# ---------------------------------------------------------------------------
# Convenience: run with tracing
# ---------------------------------------------------------------------------

async def run_response_formatter(
    formatter: ResponseFormatter,
    response: str,
    context: Context,
    agent: AgentDescriptor,
    trace: CognitiveTrace | None = None,
    metrics: CognitiveMetrics | None = None,
    memory_delta: MemoryDelta | None = None,
) -> tuple[str, ComponentTrace]:
    """Run response formatting and return (formatted_text, trace)."""
    comp_trace = ComponentTrace(strategy=_strategy_name(formatter))
    timer = Timer()

    try:
        with timer:
            formatted = await formatter.format(
                response=response,
                context=context,
                agent=agent,
                trace=trace,
                metrics=metrics,
                memory_delta=memory_delta,
            )
        comp_trace.duration_ms = timer.duration_ms
        comp_trace.tokens_used = len(formatted.split())
        comp_trace.metadata = {
            "input_length": len(response),
            "output_length": len(formatted),
            "was_modified": formatted != response,
        }
    except Exception as exc:
        comp_trace.duration_ms = timer.duration_ms
        comp_trace.error = str(exc)
        logger.exception("ResponseFormatter failed: %s", exc)
        raise

    return formatted, comp_trace


def _strategy_name(formatter: ResponseFormatter) -> str:
    return type(formatter).__name__.replace("ResponseFormatter", "").lower() or "custom"
