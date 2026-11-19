"""
Enhanced workflow nodes with LLM integration and tool execution.

These nodes demonstrate production-ready patterns for:
- LLM-based planning with prompt engineering
- Tool execution with dependency injection
- Human-in-the-loop interrupts for approval workflows
"""

import logging
from datetime import datetime, UTC
from typing import Any, cast
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from app.workflows.state.workflow_state import WorkflowState, RunMetadata
from ..error_handling.grades import absorb, node_grade

logger = logging.getLogger(__name__)


def _check_cancellation(state: WorkflowState) -> bool:
    """
    Check if workflow has been cancelled.

    Args:
        state: Current workflow state

    Returns:
        True if cancelled, False otherwise
    """
    try:
        from ..utils.cancellation import is_workflow_cancelled
        return is_workflow_cancelled(state["workflow_id"])
    except Exception as e:
        logger.warning(f"Failed to check cancellation | workflow_id={state['workflow_id']} | error={str(e)}")
        return False


def _create_cancelled_response(state: WorkflowState, elapsed: int = 0) -> dict:
    """
    Create response for cancelled workflow.

    Args:
        state: Current workflow state
        elapsed: Elapsed time in seconds

    Returns:
        State updates with cancelled status
    """
    now = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    incoming_metadata = state.get("metadata")
    config = incoming_metadata.config if incoming_metadata and hasattr(incoming_metadata, "config") else None
    tags = incoming_metadata.tags if incoming_metadata and hasattr(incoming_metadata, "tags") else None

    return {
        "execution_result": {
            "result": "Cancelled",
            "elapsed_seconds": elapsed,
            "completed_at": now
        },
        "current_step": None,
        "approval_status": None,
        "metadata": RunMetadata(
            workflow_id=state["workflow_id"],
            template_id=state["template_id"],
            started_at=getattr(state["metadata"], "started_at", None),
            completed_at=now,
            status="cancelled",
            error="Cancelled by user",
            config=config,
            tags=tags
        )
    }


# System prompt for planning
PLANNING_SYSTEM_PROMPT = """You are a workflow planner for the cogitate platform.

Your task is to:
1. Analyze the user's request
2. Break it down into clear, executable steps
3. Identify if any steps require human approval
4. Return a structured plan

Be concise and practical. Focus on actionable steps."""


def get_llm() -> BaseChatModel:
    """
    Get LLM instance for workflow execution.

    THE CAPABILITY RESOLVER ANSWERS THIS. The app has ONE answer to "which service should answer
    this?" (`domain/providers/capabilities.py`), and this node asks it for the `workflow-llm`
    capability, then builds the client from the row that answer NAMES — the shape the title service
    already uses. There is NO model written in code here: the `ChatOpenAI(model="gpt-4o-mini")`
    environment fallback that used to sit below was a hardwired provider AND model, which is the
    hardwiring this arc removes, and it was unreachable while a default row existed anyway.

    NAMED GAP — the capability's BACKUPS are not walked. This hands back a CLIENT and the node
    calls it later, so `capabilities.attempt_chain` (which wraps the call) does not fit it yet;
    `workflow-llm` resolves to one candidate today, so nothing is skipped yet. A backup configured
    for this capability will not be tried here until the walk lands for this family (owner: the
    phase that teaches these factories the chain).

    Returns:
        BaseChatModel instance for LLM calls

    Raises:
        NoProviderConfiguredError: If the capability resolves to no provider row
    """
    from app.domain.providers.capabilities import WORKFLOW_CAPABILITY_KEY, NoProviderConfiguredError
    from app.domain.providers.llm_factory import get_llm_for_capability
    from app.core.database import AsyncSessionLocal
    import asyncio

    try:
        # Resolve the capability and build the client from the row its answer names
        async def _resolve_workflow_llm():
            async with AsyncSessionLocal() as db:
                return await get_llm_for_capability(
                    db, WORKFLOW_CAPABILITY_KEY, temperature=0.0, max_tokens=2000
                )

        # Run async code in sync context, handling both running and non-running event loops
        try:
            # Try to get the current event loop
            asyncio.get_running_loop()
            # If we're in a running loop, we need to await or use a different approach
            # For this case, we'll create a future and run it synchronously
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _resolve_workflow_llm())
                llm = future.result()
        except RuntimeError:
            # No running event loop, safe to use asyncio.run()
            llm = asyncio.run(_resolve_workflow_llm())

        if llm is None:
            logger.error(
                "❌ No service resolved for the '%s' capability — nothing to plan with "
                "(no fallback model is written in code)",
                WORKFLOW_CAPABILITY_KEY,
            )
            raise NoProviderConfiguredError(WORKFLOW_CAPABILITY_KEY)

        # Log successful initialization — the CAPABILITY that answered, not the client's class
        # name (`ChatOpenAI` names an integration, not the row a reader can act on).
        logger.info("✅ LLM initialized for the '%s' capability", WORKFLOW_CAPABILITY_KEY)
        return cast(BaseChatModel, llm)

    except NoProviderConfiguredError:
        # Re-raise our custom error
        raise
    except Exception as e:
        # No categorization here: the honest report is the exception itself. Naming a provider
        # from the client's class name is the second organ this phase retires.
        logger.error(f"❌ Failed to initialize LLM | error={e}")
        raise


@node_grade("fatal")
def plan_node(state: WorkflowState) -> dict:
    """
    Enhanced planner node with LLM-based plan generation.

    This node:
    1. Extracts user intent from messages
    2. Uses LLM to create step-by-step plan
    3. Determines if approval is required
    4. Sets current_step for executor

    Note: This is a SYNCHRONOUS wrapper around async LLM call.
    For production, use async nodes with async workflow execution.

    Args:
        state: Current workflow state with user messages

    Returns:
        State updates with generated plan and metadata
    """
    from concurrent.futures import ThreadPoolExecutor
    from ..error_handling.taxonomy import is_retryable
    from ..utils.run_failure import run_failure_statement

    # Run async LLM call in thread pool
    async def run_plan():
        now = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")

        # Preserve config and tags from incoming metadata
        incoming_metadata = state.get("metadata")
        config = incoming_metadata.config if incoming_metadata and hasattr(incoming_metadata, "config") else None
        tags = incoming_metadata.tags if incoming_metadata and hasattr(incoming_metadata, "tags") else None

        # Check for user message first
        if not state["messages"]:
            error_msg = "No user message found"
            logger.error(f"❌ Plan node failed | workflow_id={state['workflow_id']} | error={error_msg}")
            return {
                "messages": state["messages"],
                "current_step": None,
                "execution_result": {"error": error_msg},
                "approval_required": False,
                "metadata": RunMetadata(
                    workflow_id=state["workflow_id"],
                    template_id=state["template_id"],
                    started_at=now,
                    status="error",
                    error=error_msg,
                    config=config,
                    tags=tags
                )
            }

        try:
            # Get LLM
            llm = get_llm()
            user_message = state["messages"][-1]

            # Build prompt
            planning_prompt = f"""
User Request: {user_message.content}

Create a plan to accomplish this task. Include:
1. Main objective
2. Key steps (2-5 steps)
3. Whether human approval is needed (if high-stakes decision)

Return your response in this format:
OBJECTIVE: [clear statement]
STEPS:
1. [step 1]
2. [step 2]
...
APPROVAL_REQUIRED: [YES/NO]
"""

            # Generate plan
            response = await llm.ainvoke([
                SystemMessage(content=PLANNING_SYSTEM_PROMPT),
                HumanMessage(content=planning_prompt)
            ])

            # Parse response
            plan_text = response.content
            approval_required = "APPROVAL_REQUIRED: YES" in plan_text.upper()

            # Add plan to messages
            plan_message = AIMessage(content=plan_text)

            return {
                "messages": state["messages"] + [plan_message],
                "current_step": "executor",
                "execution_result": {
                    "plan": plan_text,
                    "steps_extracted": True
                },
                "approval_required": approval_required,
                "metadata": RunMetadata(
                    workflow_id=state["workflow_id"],
                    template_id=state["template_id"],
                    started_at=now,
                    status="running",
                    config=config,
                    tags=tags
                )
            }

        except Exception as e:
            # FATAL (the @node_grade above): the plan IS this node's purpose — an LLM
            # failure here leaves the run with nothing to execute, which used to be
            # recorded as a completed run. absorb() re-raises so the run fails, and the
            # frame names the offender from initial_state.metadata for free.
            absorb(plan_node, state, e)
            # THE ONE WORDING (G4-F3), through the SAME gate the run-level statement uses (G4-F5):
            # a run carries a resolution either way, so this names the offender ONLY when the
            # failure came from the provider layer — a node's own bug names nobody, and the raw
            # exception is the honest answer then.
            statement = run_failure_statement(state.get("metadata"), e)
            message = statement or str(e)

            logger.error(
                "❌ Plan node failed | workflow_id=%s | error=%s",
                state["workflow_id"], message,
            )

            # CRITICAL: Set current_step to None to prevent further execution
            # This tells LangGraph the workflow is complete (even though it failed)
            return {
                "messages": state["messages"],
                "current_step": None,  # CRITICAL: Clear current_step to stop execution
                "execution_result": {
                    "error": message,
                    "error_type": type(e).__name__,
                    "error_details": {"message": message},
                    # The RETRYABLE decision is the SHARED taxonomy's (error_handling/taxonomy.py) —
                    # not a second list kept beside it in this node.
                    "retryable": is_retryable(e),
                },
                "approval_required": False,
                "metadata": RunMetadata(
                    workflow_id=state["workflow_id"],
                    template_id=state["template_id"],
                    started_at=now,
                    completed_at=now,  # Mark as completed (even though failed)
                    status="error",
                    error=message,
                    config=config,
                    tags=tags
                )
            }

    # Run async function in thread pool to handle nested event loop issues
    with ThreadPoolExecutor() as executor:
        def run_async_in_new_loop():
            """Run async code in a fresh event loop to avoid nested loop issues"""
            import asyncio
            return asyncio.run(run_plan())
        
        future = executor.submit(run_async_in_new_loop)
        return cast(dict[Any, Any], future.result())


def execute_node(state: WorkflowState) -> dict:
    """
    Enhanced executor node with tool integration placeholder.

    This node:
    1. Reads current_step from state
    2. Executes appropriate tool/action
    3. Returns result in execution_result
    4. Updates metadata
    5. Checks for cancellation during long-running operations

    Args:
        state: Current workflow state with plan

    Returns:
        State updates with execution results

    Note:
        This is a placeholder for real tool integration.
        In Session 44+, this will integrate with cogitate's tool system.
    """
    now = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    # CRITICAL: Check if planner already failed - preserve original error
    metadata = state.get("metadata")
    if metadata and hasattr(metadata, 'status') and metadata.status == "error":
        # Planner already failed - preserve the original error
        logger.warning(f"⚠️  Executor skipped - planner failed | workflow_id={state['workflow_id']} | error={metadata.error if hasattr(metadata, 'error') else 'Unknown'}")
        return {
            "execution_result": state.get("execution_result"),  # Preserve planner's error
            "current_step": None,
            "metadata": metadata  # Preserve original error metadata
        }

    # Get the plan from previous messages
    plan_message = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage):
            plan_message = msg
            break

    # Preserve config and tags from incoming metadata
    incoming_metadata = state.get("metadata")
    config = incoming_metadata.config if incoming_metadata and hasattr(incoming_metadata, "config") else None
    tags = incoming_metadata.tags if incoming_metadata and hasattr(incoming_metadata, "tags") else None

    if not plan_message:
        return {
            "execution_result": {"error": "No plan found"},
            "metadata": RunMetadata(
                workflow_id=state["workflow_id"],
                template_id=state["template_id"],
                started_at=state["metadata"].started_at,
                completed_at=now,
                status="error",
                error="No plan found",
                config=config,
                tags=tags
            )
        }

    # Check for cancellation before executing
    if _check_cancellation(state):
        logger.warning(f"⏹️ Workflow cancelled before execution | workflow_id={state['workflow_id']}")
        return _create_cancelled_response(state, 0)

    # Execute the plan (placeholder - in production, this would call tools)
    execution_result: dict[str, Any] = {
        "result": "Plan executed successfully",
        "plan_summary": (plan_message.content[:200] if isinstance(plan_message.content, str) else str(plan_message.content)[:200]) + "...",
        "executed_at": now,
        "tools_used": [],  # Will be populated in Session 44+
    }

    return {
        "execution_result": execution_result,
        "current_step": None,
        "metadata": RunMetadata(
            workflow_id=state["workflow_id"],
            template_id=state["template_id"],
            started_at=state["metadata"].started_at,
            completed_at=now,
            status="completed",
            config=config,
            tags=tags
        )
    }


def review_node(state: WorkflowState) -> dict:
    """
    Human review node with interrupt for approval.
    
    This node:
    1. Prepares approval request with context
    2. Calls interrupt() to pause execution
    3. State persists automatically via checkpointer
    4. Resumes when graph.invoke(None, config) is called
    5. Returns approval status based on user input
    
    Note: SYNCHRONOUS version for use with sync workflow execution.
    
    Args:
        state: Current workflow state requiring approval
        
    Returns:
        State updates with approval decision
    """
    from langgraph.types import interrupt
    
    now = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    
    # Prepare approval request
    approval_payload = {
        "workflow_id": state["workflow_id"],
        "template_id": state["template_id"],
        "current_step": state["current_step"],
        "plan": (state.get("execution_result") or {}).get("plan", "No plan available"),
        "message": "Approval required before proceeding with execution",
        "requested_at": now
    }
    
    # Preserve config from incoming metadata
    incoming_metadata = state.get("metadata")
    config = incoming_metadata.config if incoming_metadata and hasattr(incoming_metadata, "config") else None

    # Pause execution - this is where the magic happens
    # State persists automatically via checkpointer
    # Execution resumes when graph.invoke(None, config) is called
    approval_response = interrupt(value=approval_payload)

    # Process approval response
    # approval_response should be a dict with 'status' and optionally 'comment'
    status = approval_response.get("status", "rejected")  # Default to rejected
    comment = approval_response.get("comment", "")

    # Create response message
    if status == "approved":
        response_message = AIMessage(content=f"Plan approved. {comment}")
    else:
        response_message = AIMessage(content=f"Plan rejected. {comment}")

    return {
        "messages": state["messages"] + [response_message],
        "approval_status": status,
        "current_step": "executor" if status == "approved" else None,
        "metadata": RunMetadata(
            workflow_id=state["workflow_id"],
            template_id=state["template_id"],
            started_at=state["metadata"].started_at,
            status="completed" if status == "rejected" else "running",
            config=config
        )
    }
