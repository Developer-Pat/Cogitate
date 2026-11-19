"""
Logging service for chat operations.

Provides centralized, structured logging for chat streaming,
tool execution, and error handling.
"""

import logging
import traceback
from typing import Any, Dict, List, Optional, Union

from .schemas import StreamResult
from app.domain.tools.execution_service import ToolExecutionResult
from .context import ChatContext


class ChatLoggingService:
    """
    Centralized logging service for chat operations.

    Provides consistent logging methods with structured data
    for filtering and analysis.
    """

    def __init__(self):
        """Initialize the logging service."""
        self.logger = logging.getLogger(__name__)

    def _get_context_value(self, context: Union[ChatContext, Dict], key: str, default=None):
        """Get value from context (supports both ChatContext and dict)."""
        if isinstance(context, ChatContext):
            return getattr(context, key, default)
        return context.get(key, default)

    def log_request_start(self, context: Union[ChatContext, Dict[str, Any]]) -> None:
        """
        Log the start of a chat request.

        Args:
            context: Chat context with request details

        THE BUDGET FIELD IS LABELLED (the token-limit arc, B.4): this line used
        to print `parameters={'max_tokens': 2000}` — the DECLARED number —
        while a different one went on the wire (a hybrid pass 1 sent 1024), and
        every budget question asked from the log started from that false
        number. The declared value is now named as declared and the rest of the
        parameters (temperature, top_p) are logged without it, so nothing here
        can be mistaken for the sent budget. The EFFECTIVE value and its reason
        are logged where the request is built
        (`output_budget.log_effective_budget`, via `router._log_effective_output_budget`).
        """
        parameters = self._get_context_value(context, 'parameters') or {}
        if not isinstance(parameters, dict):
            parameters = {}
        # THE DECLARATION (G-I): it lives in the agent's `llm_spec.max_output` — the
        # one field the resolver reads — so this line names that number, and the
        # parameters below are logged as sampling settings only. Nothing here can be
        # mistaken for the SENT value, which is the EFFECTIVE line's business.
        spec = getattr(self._get_context_value(context, 'agent'), 'llm_spec', None)
        declared_max_tokens = (
            spec.get('max_output') if isinstance(spec, dict) else None
        )
        other_parameters = parameters
        self.logger.info("📡 LLM REQUEST START", extra={
            'event_type': 'llm_request_start',
            'session_id': self._get_context_value(context, 'session_id'),
            'agent_id': self._get_context_value(context, 'agent_id'),
            'agent_name': self._get_context_value(context, 'agent_name'),
            'provider': self._get_context_value(context, 'provider'),
            'model': self._get_context_value(context, 'model'),
            'messages_count': self._get_context_value(context, 'messages_count'),
            'messages_preview': self._get_context_value(context, 'messages_preview'),
            'tools_count': self._get_context_value(context, 'tools_count'),
            'tools': self._get_context_value(context, 'tools'),
            # NOT what is sent — the sent value is the EFFECTIVE line's.
            'declared_max_tokens': declared_max_tokens,
            'parameters': other_parameters,
        })

    def log_stream_started(self, context: Union[ChatContext, Dict[str, Any]], stream_type: str) -> None:
        """
        Log that streaming has started.

        Args:
            context: Chat context
            stream_type: Type of stream object
        """
        self.logger.info("✅ LLM STREAM OPENED", extra={
            'event_type': 'llm_stream_opened',
            'session_id': self._get_context_value(context, 'session_id'),
            'model': self._get_context_value(context, 'model'),
            'provider': self._get_context_value(context, 'provider'),
            'stream_type': stream_type,
        })

    def log_stream_open_failed(
        self,
        context: Union[ChatContext, Dict[str, Any]],
        error: Exception
    ) -> None:
        """
        Log that streaming failed to start.

        Args:
            context: Chat context
            error: The exception that occurred
        """
        self.logger.error("❌ LLM STREAM FAILED TO OPEN", extra={
            'event_type': 'llm_stream_open_failed',
            'severity': 'critical',
            'session_id': self._get_context_value(context, 'session_id'),
            'agent_id': self._get_context_value(context, 'agent_id'),
            'provider': self._get_context_value(context, 'provider'),
            'model': self._get_context_value(context, 'model'),
            'error': str(error),
            'error_type': type(error).__name__,
            'traceback': traceback.format_exc(),
        }, exc_info=True)

    def log_first_chunk(
        self,
        session_id: int,
        time_to_first_chunk_ms: float,
        model: str,
        provider: str
    ) -> None:
        """
        Log arrival of first chunk.

        Args:
            session_id: Session identifier
            time_to_first_chunk_ms: Time to first chunk in milliseconds
            model: Model name
            provider: Provider name
        """
        self.logger.info("📦 FIRST CHUNK RECEIVED", extra={
            'event_type': 'llm_first_chunk',
            'session_id': session_id,
            'time_to_first_chunk_ms': round(time_to_first_chunk_ms, 2),
            'model': model,
            'provider': provider,
        })

    def log_chunk_invalid(
        self,
        session_id: int,
        chunk_index: int,
        chunk_attrs: List[str]
    ) -> None:
        """
        Log an invalid chunk.

        Args:
            session_id: Session identifier
            chunk_index: Index of the invalid chunk
            chunk_attrs: Attributes present on the chunk
        """
        self.logger.warning("⚠️ CHUNK MISSING CHOICES", extra={
            'event_type': 'llm_chunk_invalid',
            'session_id': session_id,
            'chunk_index': chunk_index,
            'chunk_attrs': chunk_attrs,
        })

    def log_stream_completed(
        self,
        context: Union[ChatContext, Dict[str, Any]],
        result: StreamResult
    ) -> None:
        """
        Log completion of streaming.

        Args:
            context: Chat context
            result: Stream result with metrics
        """
        timing = result.timing
        self.logger.info("📊 STREAM COMPLETED", extra={
            'event_type': 'llm_stream_completed',
            'session_id': self._get_context_value(context, 'session_id'),
            'agent_id': self._get_context_value(context, 'agent_id'),
            'model': self._get_context_value(context, 'model'),
            'provider': self._get_context_value(context, 'provider'),
            'chunk_count': result.chunk_count,
            'accumulated_chars': len(result.accumulated_content),
            'has_tool_calls': len(result.tool_calls) > 0,
            'tool_calls_count': len(result.tool_calls),
            'invalid_chunks': result.invalid_chunks,
            'total_stream_time_ms': round(timing.total_stream_ms if timing else 0, 2),
            'time_to_first_chunk_ms': round(timing.time_to_first_chunk_ms, 2) if timing and timing.time_to_first_chunk_ms else None,
            # THE STOP REASON (2026-09-22): every stream now records WHY it
            # ended — 'stop'/'tool_calls' are normal, 'length' is the
            # provider cutting the answer at the output budget, and None
            # is a stream that closed without a verdict (a dropped
            # connection, or a provider that never sends one). Without
            # this field a cut answer and a finished one logged
            # identically, which is what made Bob's truncation
            # unattributable.
            'finish_reason': result.finish_reason or None,
            'truncated': result.is_truncated,
            # THE CALL'S TOKENS (the bench): the usage THIS call reported, on the per-call line.
            # `StreamResult` has carried both numbers since the stream asked for
            # `include_usage`, and this line dropped them — so the only token figure the log held
            # was the turn account's SUM across calls, and the per-call prompt size had to be
            # estimated. `None` (not 0) when nobody reported, the app's own `usage or None`
            # idiom: a 0 printed for a provider that sends nothing reads as a free call.
            'prompt_tokens': result.prompt_tokens or None,
            'completion_tokens': result.completion_tokens or None,
        })

    def log_empty_response(
        self,
        context: Union[ChatContext, Dict[str, Any]],
        total_time_ms: float
    ) -> None:
        """
        Log that no chunks were received.

        Args:
            context: Chat context
            total_time_ms: Total time elapsed
        """
        self.logger.error("❌ CRITICAL: NO CHUNKS RECEIVED", extra={
            'event_type': 'llm_stream_empty',
            'severity': 'critical',
            'session_id': self._get_context_value(context, 'session_id'),
            'agent_id': self._get_context_value(context, 'agent_id'),
            'provider': self._get_context_value(context, 'provider'),
            'model': self._get_context_value(context, 'model'),
            'messages_sent': self._get_context_value(context, 'messages_count'),
            'tools_available': self._get_context_value(context, 'tools_count'),
            'total_time_ms': round(total_time_ms, 2),
        }, exc_info=True)

    def log_no_content(
        self,
        context: Union[ChatContext, Dict[str, Any]],
        chunk_count: int,
        invalid_chunks: int,
        total_time_ms: float
    ) -> None:
        """
        Log that no content was received.

        Args:
            context: Chat context
            chunk_count: Number of chunks received
            invalid_chunks: Number of invalid chunks
            total_time_ms: Total time elapsed
        """
        self.logger.error("❌ CRITICAL: NO CONTENT AND NO TOOL CALLS", extra={
            'event_type': 'llm_stream_no_content',
            'severity': 'critical',
            'session_id': self._get_context_value(context, 'session_id'),
            'agent_id': self._get_context_value(context, 'agent_id'),
            'provider': self._get_context_value(context, 'provider'),
            'model': self._get_context_value(context, 'model'),
            'chunk_count': chunk_count,
            'invalid_chunks': invalid_chunks,
            'total_time_ms': round(total_time_ms, 2),
        }, exc_info=True)

    def log_tool_call_start(
        self,
        session_id: int,
        agent_id: int,
        tool_name: str,
        tool_call_id: str,
        arguments_raw: str
    ) -> None:
        """
        Log start of tool execution.

        Args:
            session_id: Session identifier
            agent_id: Agent identifier
            tool_name: Name of the tool
            tool_call_id: Tool call identifier
            arguments_raw: Raw arguments string
        """
        self.logger.info("🔧 TOOL CALL START", extra={
            'event_type': 'tool_call_start',
            'session_id': session_id,
            'agent_id': agent_id,
            'tool_name': tool_name,
            'tool_call_id': tool_call_id,
            'arguments_raw': arguments_raw[:200] if arguments_raw else None,
        })

    def log_tool_arguments_parsed(
        self,
        session_id: int,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> None:
        """
        Log parsed tool arguments.

        Args:
            session_id: Session identifier
            tool_name: Name of the tool
            arguments: Parsed arguments dict
        """
        self.logger.info("📋 TOOL ARGUMENTS PARSED", extra={
            'event_type': 'tool_arguments_parsed',
            'session_id': session_id,
            'tool_name': tool_name,
            'arguments': arguments,
            'argument_keys': list(arguments.keys()) if arguments else [],
        })

    def log_tool_call_completed(
        self,
        session_id: int,
        agent_id: int,
        result: ToolExecutionResult
    ) -> None:
        """
        Log completion of tool execution.

        Args:
            session_id: Session identifier
            agent_id: Agent identifier
            result: Tool execution result
        """
        if result.success:
            self.logger.info("✅ TOOL EXECUTION SUCCESS", extra={
                'event_type': 'tool_execution_success',
                'session_id': session_id,
                'agent_id': agent_id,
                'tool_name': result.tool_name,
                'tool_call_id': result.tool_call_id,
                'result_preview': str(result.result)[:200] if result.result else None,
                'execution_time_ms': result.execution_time_ms,
            })
        else:
            self.logger.error("❌ TOOL EXECUTION FAILED", extra={
                'event_type': 'tool_execution_failure',
                'session_id': session_id,
                'agent_id': agent_id,
                'tool_name': result.tool_name,
                'tool_call_id': result.tool_call_id,
                'error': result.error,
                'error_type': getattr(result, 'error_type', None),
                'execution_time_ms': result.execution_time_ms,
            })

    def log_tool_execution_exception(
        self,
        session_id: int,
        agent_id: int,
        tool_name: str,
        tool_call_id: str,
        error: Exception,
        execution_time_ms: int
    ) -> None:
        """
        Log exception during tool execution.

        Args:
            session_id: Session identifier
            agent_id: Agent identifier
            tool_name: Name of the tool
            tool_call_id: Tool call identifier
            error: The exception
            execution_time_ms: Execution time
        """
        self.logger.error("❌ TOOL EXECUTION EXCEPTION", extra={
            'event_type': 'tool_execution_exception',
            'session_id': session_id,
            'agent_id': agent_id,
            'tool_name': tool_name,
            'tool_call_id': tool_call_id,
            'error': str(error),
            'error_type': type(error).__name__,
            'traceback': traceback.format_exc(),
            'execution_time_ms': execution_time_ms,
        }, exc_info=True)

    def log_error(
        self,
        error: Exception,
        context: Union[ChatContext, Dict[str, Any]],
        chunk_count: int = 0,
        accumulated_content: str = "",
        has_tool_calls: bool = False,
        tool_calls_count: int = 0
    ) -> None:
        """
        Log a streaming error with full context.

        Args:
            error: The exception
            context: Chat context
            chunk_count: Number of chunks received
            accumulated_content: Content accumulated
            has_tool_calls: Whether tool calls were made
            tool_calls_count: Number of tool calls
        """
        self.logger.error("❌ STREAMING EXCEPTION", extra={
            'event_type': 'llm_streaming_exception',
            'severity': 'critical',
            'session_id': self._get_context_value(context, 'session_id'),
            'agent_id': self._get_context_value(context, 'agent_id'),
            'agent_name': self._get_context_value(context, 'agent_name'),
            'provider': self._get_context_value(context, 'provider'),
            'model': self._get_context_value(context, 'model'),
            'error': str(error),
            'error_type': type(error).__name__,
            'traceback': traceback.format_exc(),
            'chunks_received': chunk_count,
            'content_accumulated': len(accumulated_content),
            'has_tool_calls': has_tool_calls,
            'tool_calls_count': tool_calls_count,
            'time_elapsed_ms': round(self._get_context_value(context, 'elapsed_ms', 0), 2),
            'messages_sent': self._get_context_value(context, 'messages_count'),
            'tools_available': self._get_context_value(context, 'tools_count'),
        }, exc_info=True)

    def log_value_error(
        self,
        error: Exception,
        session_id: Optional[int]
    ) -> None:
        """
        Log a value error.

        Args:
            error: The exception
            session_id: Session identifier
        """
        self.logger.error("❌ VALUE ERROR", extra={
            'event_type': 'llm_value_error',
            'session_id': session_id,
            'error': str(error),
            'traceback': traceback.format_exc(),
        }, exc_info=True)

    def log_final_response(
        self,
        session_id: int,
        content_length: int
    ) -> None:
        """
        Log final response summary.

        Args:
            session_id: Session identifier
            content_length: Length of response content
        """
        self.logger.info(f"Final response: {content_length} chars")

    def log_tool_execution_loop(
        self,
        tool_count: int
    ) -> None:
        """
        Log start of tool execution loop.

        Args:
            tool_count: Number of tools to execute
        """
        self.logger.info(f"🔧 Executing {tool_count} tool calls")

    def log_messages_updated(
        self,
        tool_results_count: int
    ) -> None:
        """
        Log that messages were updated with tool results.

        Args:
            tool_results_count: Number of tool results added
        """
        self.logger.info(f"🔄 Added {tool_results_count} tool results to messages, continuing...")

    def log_title_generation(
        self,
        session_id: int,
        title: str
    ) -> None:
        """
        Log successful title generation.

        Args:
            session_id: Session identifier
            title: Generated title
        """
        self.logger.info(f"Generated session title: '{title}'")

    def log_title_generation_failed(
        self,
        session_id: int,
        error: Exception
    ) -> None:
        """
        Log title generation failure.

        Args:
            session_id: Session identifier
            error: The exception
        """
        self.logger.error(
            f"Title generation failed: {error}",
            exc_info=True,
            extra={
                "session_id": session_id,
                "error_type": type(error).__name__,
            }
        )
