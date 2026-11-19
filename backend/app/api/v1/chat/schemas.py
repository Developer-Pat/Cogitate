"""
Data structures for chat streaming operations.

Provides type-safe data classes for streaming results, timing metrics,
and tool execution outcomes.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StreamTiming:
    """
    Timing metrics for streaming operations.

    Attributes:
        start_time: Unix timestamp when streaming started
        first_chunk_time: Unix timestamp when first chunk arrived
        last_chunk_time: Unix timestamp when last chunk arrived
        total_stream_ms: Total streaming duration in milliseconds
        time_to_first_chunk_ms: Time from request to first chunk in milliseconds
    """
    start_time: float
    first_chunk_time: Optional[float] = None
    last_chunk_time: Optional[float] = None
    total_stream_ms: float = 0.0
    time_to_first_chunk_ms: Optional[float] = None

    def __post_init__(self):
        """Calculate derived timing metrics."""
        if self.first_chunk_time and self.start_time:
            self.time_to_first_chunk_ms = (self.first_chunk_time - self.start_time) * 1000
        if self.first_chunk_time and self.last_chunk_time:
            self.total_stream_ms = (self.last_chunk_time - self.first_chunk_time) * 1000


@dataclass
class StreamResult:
    """
    Result of a streaming operation.

    Attributes:
        chunk_count: Number of chunks received
        accumulated_content: Accumulated text content from all chunks
        accumulated_reasoning: The thinking tokens (the chain-of-
            thought), segregated from the content (2026-08-24)
        tool_calls: List of tool calls to execute
        has_content: Whether any content was received
        timing: Timing metrics for the stream
        invalid_chunks: Number of invalid chunks received
        prompt_tokens: Number of prompt tokens used
        completion_tokens: Number of completion tokens used
        finish_reason: The provider's stop reason for the LAST chunk
            that carried one (''/'stop'/'length'/'tool_calls').
            'length' means the answer was CUT at the output budget —
            the one field that tells a truncated stream from a
            complete one.
    """
    chunk_count: int = 0
    accumulated_content: str = ""
    accumulated_reasoning: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    has_content: bool = False
    timing: Optional[StreamTiming] = None
    invalid_chunks: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    finish_reason: str = ""

    @property
    def is_empty(self) -> bool:
        """Check if response is empty (no chunks)."""
        return self.chunk_count == 0

    @property
    def is_truncated(self) -> bool:
        """True when the provider stopped on the output budget.

        ``finish_reason == "length"`` is the provider saying "I had
        more to write and hit max_tokens" — the stream ENDS mid-word
        and looks exactly like a clean stop to a content-only reader.
        """
        return self.finish_reason == "length"

    @property
    def has_no_content_or_tools(self) -> bool:
        """Check if response has neither content nor tool calls."""
        return len(self.accumulated_content) == 0 and len(self.tool_calls) == 0


