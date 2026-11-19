"""
Default Provider Test Nodes

Nodes that actually call the LLM to test connectivity, chaining and other functionality.

WHAT THEY TEST (capability arc, phase 4): the `workflow-llm` CAPABILITY — the same
resolution a workflow's LLM steps use — rather than the default provider row. The
template family keeps its name; the answer it exercises is the one a workflow gets,
with the rung that decided it (`llm_factory.get_llm_for_capability` logs it).
"""

import logging
from datetime import datetime, UTC
from typing import Dict, Any, cast
from langchain_core.messages import HumanMessage, AIMessage

from app.workflows.state.workflow_state import WorkflowState, RunMetadata
from app.domain.providers.capabilities import WORKFLOW_CAPABILITY_KEY
from app.domain.providers.llm_factory import get_llm_for_capability
from app.core.database import AsyncSessionLocal
from app.workflows.error_handling.grades import absorb, node_grade

logger = logging.getLogger(__name__)


async def _get_default_llm():
    """Build the LLM these template nodes exercise.

    IT ASKS THE CAPABILITY RESOLVER — for `workflow-llm`, the same capability a workflow's LLM
    steps resolve through — and builds from the row that answer NAMES. What these templates
    report is therefore the service a workflow actually uses, with the rung that decided it
    (`get_llm_for_capability` logs `capability 'workflow-llm' -> <provider>/<model> (reason=...)`),
    which is the question a user diagnosing a failed run is asking. The env-var
    `ChatOpenAI(model="gpt-4o-mini")` fallback that used to sit here was a hardwired provider AND
    model — the hardwiring this arc removes.

    Returns:
        A LangChain client, or None when the capability resolves to no provider row (the nodes
        report the missing service rather than substituting a model written in code).
    """
    async with AsyncSessionLocal() as db:
        return await get_llm_for_capability(
            db,
            WORKFLOW_CAPABILITY_KEY,
            temperature=0.1,  # Low temperature for deterministic output
            top_p=0.5,        # Low top_p to reduce hallucination
            max_tokens=2000,
        )


@node_grade("fatal")
def test_llm_connection_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Test basic LLM connectivity.
    
    This node:
    1. Gets the default LLM
    2. Sends a test message
    3. Returns the response
    
    Args:
        state: Current workflow state
        
    Returns:
        State updates with LLM response
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    
    async def run_test():
        """Run the async test in a new event loop."""
        try:
            # Get the LLM with low temperature for deterministic instruction following
            llm = await _get_default_llm()
            
            # Get test message from config or use default
            test_message = "Hello! Please respond with just the word 'OK' to confirm you're working."
            if state.get("metadata") and hasattr(state["metadata"], "config"):
                test_message = state["metadata"].config.get("test_message", test_message)
            
            logger.info(f"📤 Sending test message to LLM: {test_message[:50]}...")
            
            # Invoke the LLM
            response = await llm.ainvoke([HumanMessage(content=test_message)])
            
            logger.info(f"📥 Received LLM response: {response.content[:100]}...")
            
            # Check if response contains OK or similar
            response_text = response.content.lower()
            success = "ok" in response_text or "hello" in response_text or len(response_text.strip()) > 0
            
            return {
                "messages": state["messages"] + [
                    HumanMessage(content=test_message),
                    AIMessage(content=response.content)
                ],
                "current_step": None,
                "execution_result": {
                    "result": "Connection test successful" if success else "Connection test completed",
                    "llm_response": response.content,
                    "connection_status": "success" if success else "completed",
                    "completed_at": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
                },
                "outputs": {
                    "llm_response": response.content,
                    "connection_status": "success" if success else "completed"
                },
                "metadata": RunMetadata(
                    workflow_id=state["workflow_id"],
                    template_id=state["template_id"],
                    started_at=state["metadata"].started_at if hasattr(state["metadata"], "started_at") else state["metadata"].get("started_at"),
                    completed_at=datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                    status="completed",
                    config=state["metadata"].config if hasattr(state["metadata"], "config") else state["metadata"].get("config"),
                    tags=state["metadata"].tags if hasattr(state["metadata"], "tags") else state["metadata"].get("tags")
                )
            }
            
        except Exception as e:
            # FATAL (the @node_grade above): the call IS this node's purpose, so this
            # failure is the RUN's. absorb() re-raises — the frame's failed branch
            # records it, names the offender (from initial_state.metadata, where the
            # resolved service is still intact) and fires the toast. The error state
            # below is what a non-fatal grade returns, so the grade stays a one-line flip.
            absorb(test_llm_connection_node, state, e)
            logger.error(f"❌ LLM connection test failed: {str(e)}")
            return {
                "current_step": None,
                "execution_result": {
                    "error": f"LLM connection test failed: {str(e)}",
                    "error_type": "llm_connection_error",
                    "connection_status": "failed",
                    "completed_at": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
                },
                "outputs": {
                    "llm_response": f"Error: {str(e)}",
                    "connection_status": "failed"
                },
                "metadata": RunMetadata(
                    workflow_id=state["workflow_id"],
                    template_id=state["template_id"],
                    started_at=state["metadata"].started_at if hasattr(state["metadata"], "started_at") else state["metadata"].get("started_at"),
                    completed_at=datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                    status="error",
                    error=str(e),
                    config=state["metadata"].config if hasattr(state["metadata"], "config") else state["metadata"].get("config"),
                    tags=state["metadata"].tags if hasattr(state["metadata"], "tags") else state["metadata"].get("tags")
                )
            }
    
    # Run async in thread pool to avoid event loop issues
    with ThreadPoolExecutor() as executor:
        future = executor.submit(lambda: asyncio.run(run_test()))
        return cast(Dict[str, Any], future.result())


@node_grade("fatal")
def test_llm_chain_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Test LLM output chaining with multi-step reasoning.
    
    This node executes a chain of LLM calls where each step
    uses the output from the previous step.
    
    Args:
        state: Current workflow state
        
    Returns:
        State updates with chain results
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    import re
    
    async def run_chain_test():
        """Run the async chain test."""
        try:
            llm = await _get_default_llm()
            
            # Define the chain steps
            chain_steps = [
                {"prompt": "What is 2+2? Answer with just the number.", "extract_number": True},
                {"prompt": "Multiply {previous_result} by 3. Answer with just the number.", "extract_number": True},
                {"prompt": "Add 10 to {previous_result}. Answer with just the number.", "extract_number": True}
            ]
            
            results = []
            previous_result = None
            messages = state.get("messages", [])
            
            for i, step in enumerate(chain_steps):
                # Build prompt with previous result if needed
                prompt = step["prompt"]
                if previous_result is not None:
                    prompt = prompt.replace("{previous_result}", str(previous_result))
                
                logger.info(f"📤 Step {i+1}: Sending prompt: {prompt[:50]}...")
                
                # Invoke LLM
                response = await llm.ainvoke([HumanMessage(content=prompt)])
                response_text = response.content.strip()
                
                logger.info(f"📥 Step {i+1}: Received response: {response_text}")
                
                # Extract number if requested
                if step.get("extract_number"):
                    # Extract first number from response
                    match = re.search(r'\d+', response_text)
                    if match:
                        previous_result = int(match.group())
                    else:
                        # Try to evaluate the response as a number
                        try:
                            previous_result = int(float(response_text))
                        except Exception:
                            raise ValueError(f"Could not extract number from: {response_text}")
                else:
                    previous_result = response_text
                
                results.append(previous_result)
                messages.extend([
                    HumanMessage(content=prompt),
                    AIMessage(content=response_text)
                ])
            
            # Verify final result
            expected = 22  # (2+2)*3+10 = 4*3+10 = 12+10 = 22
            success = results[-1] == expected if isinstance(results[-1], (int, float)) else False
            
            logger.info(f"✅ Chain test complete. Final result: {results[-1]}, Expected: {expected}, Success: {success}")
            
            return {
                "messages": messages,
                "current_step": None,
                "execution_result": {
                    "result": "Chain test successful" if success else "Chain test completed",
                    "step1_result": str(results[0]),
                    "step2_result": str(results[1]),
                    "final_result": str(results[2]),
                    "chain_success": success,
                    "expected_result": expected,
                    "completed_at": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
                },
                "outputs": {
                    "step1_result": str(results[0]),
                    "step2_result": str(results[1]),
                    "final_result": str(results[2]),
                    "chain_success": success
                },
                "metadata": RunMetadata(
                    workflow_id=state["workflow_id"],
                    template_id=state["template_id"],
                    started_at=state["metadata"].started_at if hasattr(state["metadata"], "started_at") else state["metadata"].get("started_at"),
                    completed_at=datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                    status="completed",
                    config=state["metadata"].config if hasattr(state["metadata"], "config") else state["metadata"].get("config"),
                    tags=state["metadata"].tags if hasattr(state["metadata"], "tags") else state["metadata"].get("tags")
                )
            }

        except Exception as e:
            # FATAL (the @node_grade above): the call IS this node's purpose, so this
            # failure is the RUN's. absorb() re-raises — the frame's failed branch
            # records it, names the offender (from initial_state.metadata, where the
            # resolved service is still intact) and fires the toast. The error state
            # below is what a non-fatal grade returns, so the grade stays a one-line flip.
            absorb(test_llm_chain_node, state, e)
            logger.error(f"❌ LLM chain test failed: {str(e)}")
            return {
                "current_step": None,
                "execution_result": {
                    "error": f"LLM chain test failed: {str(e)}",
                    "error_type": "llm_chain_error",
                    "chain_success": False,
                    "completed_at": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
                },
                "outputs": {
                    "step1_result": "Error",
                    "step2_result": "Error",
                    "final_result": "Error",
                    "chain_success": False
                },
                "metadata": RunMetadata(
                    workflow_id=state["workflow_id"],
                    template_id=state["template_id"],
                    started_at=state["metadata"].started_at if hasattr(state["metadata"], "started_at") else state["metadata"].get("started_at"),
                    completed_at=datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                    status="error",
                    error=str(e),
                    config=state["metadata"].config if hasattr(state["metadata"], "config") else state["metadata"].get("config"),
                    tags=state["metadata"].tags if hasattr(state["metadata"], "tags") else state["metadata"].get("tags")
                )
            }
    
    # Run async in thread pool
    with ThreadPoolExecutor() as executor:
        future = executor.submit(lambda: asyncio.run(run_chain_test()))
        return cast(Dict[str, Any], future.result())


@node_grade("fatal")
def test_llm_summary_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Test LLM text summarization.
    
    Args:
        state: Current workflow state
        
    Returns:
        State updates with summary results
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    
    async def run_summary_test():
        """Run the async summary test."""
        try:
            llm = await _get_default_llm()
            
            # Get input text and instruction
            input_text = """
                Artificial intelligence (AI) is intelligence demonstrated by machines, 
                in contrast to the natural intelligence displayed by humans and animals. 
                Leading AI textbooks define the field as the study of intelligent agents: 
                any device that perceives its environment and takes actions that maximize 
                its chance of successfully achieving its goals.
            """
            summary_instruction = "Summarize the above text in exactly one sentence."
            
            if state.get("metadata") and hasattr(state["metadata"], "config"):
                input_text = state["metadata"].config.get("input_text", input_text)
                summary_instruction = state["metadata"].config.get("summary_instruction", summary_instruction)
            
            # Build prompt
            prompt = f"{input_text}\n\n{summary_instruction}"
            
            logger.info(f"📤 Sending text for summarization ({len(input_text)} chars)...")
            
            # Invoke LLM
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            summary = response.content.strip()
            
            logger.info(f"📥 Received summary: {summary[:100]}...")
            
            # Calculate stats
            original_length = len(input_text.strip())
            summary_length = len(summary)
            compression_ratio = round(original_length / summary_length, 2) if summary_length > 0 else 0
            
            return {
                "messages": state.get("messages", []) + [
                    HumanMessage(content=prompt),
                    AIMessage(content=summary)
                ],
                "current_step": None,
                "execution_result": {
                    "result": "Summary generated successfully",
                    "original_length": original_length,
                    "summary": summary,
                    "summary_length": summary_length,
                    "compression_ratio": compression_ratio,
                    "completed_at": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
                },
                "outputs": {
                    "original_length": original_length,
                    "summary": summary,
                    "summary_length": summary_length,
                    "compression_ratio": compression_ratio
                },
                "metadata": RunMetadata(
                    workflow_id=state["workflow_id"],
                    template_id=state["template_id"],
                    started_at=state["metadata"].started_at if hasattr(state["metadata"], "started_at") else state["metadata"].get("started_at"),
                    completed_at=datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                    status="completed",
                    config=state["metadata"].config if hasattr(state["metadata"], "config") else state["metadata"].get("config"),
                    tags=state["metadata"].tags if hasattr(state["metadata"], "tags") else state["metadata"].get("tags")
                )
            }

        except Exception as e:
            # FATAL (the @node_grade above): the call IS this node's purpose, so this
            # failure is the RUN's. absorb() re-raises — the frame's failed branch
            # records it, names the offender (from initial_state.metadata, where the
            # resolved service is still intact) and fires the toast. The error state
            # below is what a non-fatal grade returns, so the grade stays a one-line flip.
            absorb(test_llm_summary_node, state, e)
            logger.error(f"❌ LLM summary test failed: {str(e)}")
            return {
                "current_step": None,
                "execution_result": {
                    "error": f"LLM summary test failed: {str(e)}",
                    "error_type": "llm_summary_error",
                    "completed_at": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
                },
                "outputs": {
                    "original_length": 0,
                    "summary": f"Error: {str(e)}",
                    "summary_length": 0,
                    "compression_ratio": 0
                },
                "metadata": RunMetadata(
                    workflow_id=state["workflow_id"],
                    template_id=state["template_id"],
                    started_at=state["metadata"].started_at if hasattr(state["metadata"], "started_at") else state["metadata"].get("started_at"),
                    completed_at=datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                    status="error",
                    error=str(e),
                    config=state["metadata"].config if hasattr(state["metadata"], "config") else state["metadata"].get("config"),
                    tags=state["metadata"].tags if hasattr(state["metadata"], "tags") else state["metadata"].get("tags")
                )
            }
    
    # Run async in thread pool
    with ThreadPoolExecutor() as executor:
        future = executor.submit(lambda: asyncio.run(run_summary_test()))
        return cast(Dict[str, Any], future.result())


@node_grade("fatal")
def test_llm_comparison_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Test LLM with multiple prompts and compare responses.
    
    Args:
        state: Current workflow state
        
    Returns:
        State updates with comparison results
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    
    async def run_comparison_test():
        """Run the async comparison test."""
        try:
            llm = await _get_default_llm()
            
            # Define the prompts
            prompts = [
                "What is the capital of France?",
                "Name the capital city of France.",
                "Which city serves as the capital of France?"
            ]
            
            responses = []
            messages = state.get("messages", [])
            
            for i, prompt in enumerate(prompts):
                logger.info(f"📤 Prompt {i+1}: {prompt}")
                
                # Invoke LLM
                response = await llm.ainvoke([HumanMessage(content=prompt)])
                response_text = response.content.strip()
                
                logger.info(f"📥 Response {i+1}: {response_text}")
                
                responses.append(response_text)
                messages.extend([
                    HumanMessage(content=prompt),
                    AIMessage(content=response_text)
                ])
            
            # Check if all responses contain "Paris"
            all_match = all("paris" in r.lower() for r in responses)
            
            logger.info(f"✅ Comparison test complete. All match: {all_match}")
            
            return {
                "messages": messages,
                "current_step": None,
                "execution_result": {
                    "result": "Comparison test successful" if all_match else "Comparison test completed",
                    "response_1": responses[0],
                    "response_2": responses[1],
                    "response_3": responses[2],
                    "all_match": all_match,
                    "completed_at": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
                },
                "outputs": {
                    "response_1": responses[0],
                    "response_2": responses[1],
                    "response_3": responses[2],
                    "all_match": all_match
                },
                "metadata": RunMetadata(
                    workflow_id=state["workflow_id"],
                    template_id=state["template_id"],
                    started_at=state["metadata"].started_at if hasattr(state["metadata"], "started_at") else state["metadata"].get("started_at"),
                    completed_at=datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                    status="completed",
                    config=state["metadata"].config if hasattr(state["metadata"], "config") else state["metadata"].get("config"),
                    tags=state["metadata"].tags if hasattr(state["metadata"], "tags") else state["metadata"].get("tags")
                )
            }

        except Exception as e:
            # FATAL (the @node_grade above): the call IS this node's purpose, so this
            # failure is the RUN's. absorb() re-raises — the frame's failed branch
            # records it, names the offender (from initial_state.metadata, where the
            # resolved service is still intact) and fires the toast. The error state
            # below is what a non-fatal grade returns, so the grade stays a one-line flip.
            absorb(test_llm_comparison_node, state, e)
            logger.error(f"❌ LLM comparison test failed: {str(e)}")
            return {
                "current_step": None,
                "execution_result": {
                    "error": f"LLM comparison test failed: {str(e)}",
                    "error_type": "llm_comparison_error",
                    "all_match": False,
                    "completed_at": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
                },
                "outputs": {
                    "response_1": "Error",
                    "response_2": "Error",
                    "response_3": "Error",
                    "all_match": False
                },
                "metadata": RunMetadata(
                    workflow_id=state["workflow_id"],
                    template_id=state["template_id"],
                    started_at=state["metadata"].started_at if hasattr(state["metadata"], "started_at") else state["metadata"].get("started_at"),
                    completed_at=datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                    status="error",
                    error=str(e),
                    config=state["metadata"].config if hasattr(state["metadata"], "config") else state["metadata"].get("config"),
                    tags=state["metadata"].tags if hasattr(state["metadata"], "tags") else state["metadata"].get("tags")
                )
            }

    # Run async in thread pool
    with ThreadPoolExecutor() as executor:
        future = executor.submit(lambda: asyncio.run(run_comparison_test()))
        return cast(Dict[str, Any], future.result())
