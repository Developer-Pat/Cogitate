"""
Tool execution logic for chat operations.

Handles execution of tool calls detected in LLM responses.
Includes comprehensive error handling, logging, and failure recovery.
"""

import json
import logging
import time
from typing import Any, Dict, List, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.tools.execution_service import ToolExecutionResult
from .logging_service import ChatLoggingService

logger = logging.getLogger(__name__)


async def execute_tool_calls(
    tool_calls: List[Dict[str, Any]],
    agent_id: int,
    session_id: int,
    db: AsyncSession,
    logger_service: ChatLoggingService,
) -> List[ToolExecutionResult]:
    """
    Execute multiple tool calls.

    Args:
        tool_calls: List of tool calls to execute
        agent_id: Agent identifier
        session_id: Session identifier
        db: Database session
        logger_service: Logging service

    Returns:
        List of tool execution results
    """
    from app.domain.tools.execution_service import ToolExecutionService
    tool_execution_service = ToolExecutionService(db)

    results = []
    for tool_call in tool_calls:
        result = await execute_single_tool(
            tool_call=tool_call,
            agent_id=agent_id,
            session_id=session_id,
            tool_execution_service=tool_execution_service,
            logger_service=logger_service,
        )
        results.append(result)

    return results


async def execute_single_tool(
    tool_call: Dict[str, Any],
    agent_id: int,
    session_id: int,
    tool_execution_service: Any,
    logger_service: ChatLoggingService,
) -> ToolExecutionResult:
    """
    Execute a single tool call with comprehensive error handling.

    Argument validation is performed inside ``execute_tool_for_agent`` via the
    ``ToolRegistry`` (which validates against ``arguments_schema``).  The
    redundant pre-validation DB query that was previously here has been removed
    to avoid fetching all agent tools twice per call.

    Args:
        tool_call: Tool call data from the LLM (keys: name, id, arguments)
        agent_id: Agent identifier
        session_id: Session identifier
        tool_execution_service: Domain-layer ToolExecutionService
        logger_service: Logging service

    Returns:
        Domain-layer ToolExecutionResult with call_id set to the LLM call ID
    """
    tool_exec_start = time.time()
    tool_name: str = ""
    tool_id: str = ""

    try:
        tool_name = tool_call["name"]
        tool_id = tool_call["id"]
        raw_args = tool_call["arguments"]

        # PHASE 6: Pre-execution logging
        logger_service.log_tool_call_start(
            session_id=session_id,
            agent_id=agent_id,
            tool_name=tool_name,
            tool_call_id=tool_id,
            arguments_raw=raw_args,
        )

        # Parse arguments
        try:
            arguments = json.loads(raw_args) if raw_args else {}
        except Exception as parse_err:
            logger.error(f"❌ Failed to parse tool arguments: {parse_err}")
            arguments = {}

        # PHASE 7: Argument validation logging
        logger_service.log_tool_arguments_parsed(
            session_id=session_id,
            tool_name=tool_name,
            arguments=arguments,
        )

        logger.info(f"🔧 Executing tool: {tool_name} with args: {arguments}")

        # Execute tool — validation is handled inside execute_tool_for_agent
        result = await tool_execution_service.execute_tool_for_agent(
            agent_id=agent_id,
            tool_slug=tool_name,
            arguments=arguments,
            session_id=str(session_id)
        )

        tool_exec_time_ms = int((time.time() - tool_exec_start) * 1000)

        # Stamp the LLM-assigned call ID and outer timing onto the domain result
        result.call_id = tool_id
        result.execution_time_ms = tool_exec_time_ms

        # PHASE 8: Outcome logging with timing
        logger_service.log_tool_call_completed(
            session_id=session_id,
            agent_id=agent_id,
            result=result,
        )

        if result.success:
            logger.info(f"✅ Tool '{tool_name}' executed successfully in {tool_exec_time_ms}ms")
        else:
            # TOOL FAILED - Log as WARNING (not ERROR - failures are expected)
            logger.warning(
                f"⚠️  Tool '{tool_name}' execution failed: {result.error} "
                f"(execution time: {tool_exec_time_ms}ms)"
            )

        return cast(ToolExecutionResult, result)

    except Exception as e:
        tool_exec_time_ms = int((time.time() - tool_exec_start) * 1000)

        logger.error(
            f"❌ Tool '{tool_name}' threw exception: {e} "
            f"(execution time: {tool_exec_time_ms}ms)",
            exc_info=True,
        )

        logger_service.log_tool_execution_exception(
            session_id=session_id,
            agent_id=agent_id,
            tool_name=tool_name,
            tool_call_id=tool_id,
            error=e,
            execution_time_ms=tool_exec_time_ms,
        )

        return ToolExecutionResult(
            success=False,
            tool_slug=tool_name,
            tool_name=tool_name,
            error=str(e),
            execution_time_ms=tool_exec_time_ms,
            call_id=tool_id,
        )
