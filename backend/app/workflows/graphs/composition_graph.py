"""
Workflow composition graph builder.

Builds LangGraph workflows from composition configurations,
enabling chaining of multiple workflow templates together.

Features:
- Load workflow templates from database
- Connect workflow outputs to next workflow inputs
- Build composite graph with multiple workflow executions
- Support for conditional workflow execution
- Comprehensive logging for diagnostics
"""

import logging
import sqlite3
import json
from typing import Dict, Any, Optional, cast
from datetime import datetime, UTC

from langgraph.graph import StateGraph, END

from app.domain.workflows.schemas.composition_config import (
    WorkflowComposition,
    WorkflowReference,
)
from app.workflows.state.workflow_state import WorkflowState

logger = logging.getLogger(__name__)

# Database path - project root
from app.core.config import Paths, get_settings
DB_PATH = Paths.from_settings(get_settings()).shared_db


def _load_workflow_template(template_id: str) -> Optional[Dict[str, Any]]:
    """
    Load workflow template from database.
    
    Args:
        template_id: ID of template to load
        
    Returns:
        Template configuration dict or None if not found
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "SELECT * FROM workflow_templates WHERE id = ?",
            (template_id,)
        )
        row = cursor.fetchone()
        
        if row:
            template_dict = dict(row)
            logger.info(f"📄 Loaded workflow template: {template_id}")
            return template_dict
        else:
            logger.warning(f"⚠️  Workflow template not found: {template_id}")
            return None
    finally:
        conn.close()


def _load_composition_config(composition_id: str) -> Optional[Dict[str, Any]]:
    """
    Load composition configuration from database.
    
    Args:
        composition_id: ID of composition to load
        
    Returns:
        Composition configuration dict or None if not found
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "SELECT * FROM workflow_compositions WHERE id = ?",
            (composition_id,)
        )
        row = cursor.fetchone()
        
        if row:
            template_dict = dict(row)
            # Parse config_json
            if isinstance(template_dict.get('config_json'), str):
                template_dict['config'] = json.loads(template_dict['config_json'])
            else:
                template_dict['config'] = template_dict.get('config_json', {})
            logger.info(f"📄 Loaded composition config: {composition_id}")
            return template_dict
        else:
            logger.warning(f"⚠️  Composition config not found: {composition_id}")
            return None
    finally:
        conn.close()


def create_workflow_execution_node(workflow_ref: WorkflowReference, order: int):
    """
    Create a node that executes a single workflow in the composition.
    
    This node:
    1. Loads the workflow template
    2. Maps inputs from previous workflow outputs
    3. Executes the workflow
    4. Maps outputs to composition-level keys
    5. Logs execution details for diagnostics
    
    Args:
        workflow_ref: Workflow reference configuration
        order: Execution order in composition
        
    Returns:
        Node function for LangGraph
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    
    def workflow_execution_node(state: WorkflowState) -> Dict[str, Any]:
        """
        Execute a single workflow in the composition.
        
        Args:
            state: Current workflow state
            
        Returns:
            State updates with workflow outputs
        """
        async def run_workflow():
            try:
                logger.info(f"🚀 Executing workflow {order}: {workflow_ref.workflow_id}")
                
                # Load workflow template
                template = _load_workflow_template(workflow_ref.workflow_id)
                if not template:
                    raise ValueError(f"Workflow template not found: {workflow_ref.workflow_id}")
                
                # Parse template config
                config_json = template.get('config_json', {})
                if isinstance(config_json, str):
                    json.loads(config_json)
                else:
                    pass
                
                # Map inputs from previous outputs
                inputs = state.get("outputs", {})
                mapped_inputs = {}
                
                for input_key, source_output in workflow_ref.input_mapping.items():
                    if source_output in inputs:
                        source_value = inputs[source_output]
                        # Extract content if it's a dict structure
                        if isinstance(source_value, dict):
                            mapped_inputs[input_key] = source_value.get("content", str(source_value))
                        else:
                            mapped_inputs[input_key] = str(source_value)
                    elif source_output == "initial_input":
                        # Special case: use initial input from state
                        mapped_inputs[input_key] = state.get("inputs", {}).get(input_key, "")
                    else:
                        logger.warning(f"⚠️  Input mapping source not found: {source_output}")
                        mapped_inputs[input_key] = ""
                
                logger.info(f"📥 Mapped inputs for workflow {workflow_ref.workflow_id}: {list(mapped_inputs.keys())}")
                
                # Execute workflow
                # Phase G: dispatch through the GENERAL workflow
                # executor — any template (monitor, simple, chain,
                # multi-agent) compiles + runs, not just multi-agent
                # configs (the old path failed on monitor templates:
                # their config is {feeds, max_items}, not a
                # MultiAgentConfig).
                from app.workflows.api.workflow_router import (
                    compile_workflow,
                )
                initial_message = mapped_inputs.get("user_input", "")
                if not initial_message:
                    for key in ["input", "query", "message"]:
                        if key in mapped_inputs:
                            initial_message = mapped_inputs[key]
                            break

                logger.info(f"📤 Executing workflow {workflow_ref.workflow_id} with input: {initial_message[:100]}...")

                compiled = compile_workflow(workflow_ref.workflow_id)
                sub_state = {
                    "messages": [],
                    "workflow_id": f"sub-{workflow_ref.workflow_id}",
                    "template_id": workflow_ref.workflow_id,
                    "inputs": mapped_inputs,
                    "current_step": None,
                    "execution_result": None,
                    "outputs": {},
                    "approval_required": False,
                    "approval_status": None,
                    "metadata": {"composition_parent": True},
                    "tool_calls_history": [],
                    "tool_loop_count": 0,
                    "pending_tool_calls": None,
                    "current_agent_step": None,
                }
                result_state = await asyncio.to_thread(
                    compiled.invoke, sub_state,
                    {"configurable": {"thread_id": f"sub-{workflow_ref.workflow_id}"}},
                )
                output = result_state.get("outputs", {}).get("final_output") \
                    or result_state.get("execution_result", {}).get("result") \
                    or ""
                result_status = "completed"

                class _InnerResult:
                    pass
                result = _InnerResult()
                result.status = result_status
                result.output = output if isinstance(output, str) else str(output)

                logger.info(f"✅ Workflow {workflow_ref.workflow_id} completed: {result_status}")
                
                # Map outputs to composition-level keys
                outputs = state.get("outputs", {}).copy()
                
                # Store workflow result
                workflow_output_key = f"workflow_{order}_output"
                outputs[workflow_output_key] = {
                    "content": result.output,
                    "workflow_id": workflow_ref.workflow_id,
                    "order": order,
                    "status": result.status,
                }
                
                # Apply output mappings
                for comp_key, wf_output_key in workflow_ref.output_mapping.items():
                    if wf_output_key == "final_output" and result.output:
                        outputs[comp_key] = result.output
                    elif wf_output_key in outputs:
                        outputs[comp_key] = outputs[wf_output_key]
                    else:
                        # Try to get from workflow result
                        outputs[comp_key] = result.output
                
                # Store final_output as well for next workflow
                if result.output:
                    outputs["final_output"] = result.output
                
                # Update composition execution history
                composition_history = state.get("composition_execution_history", [])
                composition_history.append({
                    "workflow_id": workflow_ref.workflow_id,
                    "order": order,
                    "status": result.status,
                    "output_preview": str(result.output)[:200] if result.output else "",
                    "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                })
                
                return {
                    "outputs": outputs,
                    "composition_execution_history": composition_history,
                    "current_step": f"workflow_{order}",
                }
                
            except Exception as e:
                logger.error(f"❌ Workflow {order} ({workflow_ref.workflow_id}) failed: {str(e)}", exc_info=True)
                
                return {
                    "outputs": {
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "failed_workflow_order": order,
                        "failed_workflow_id": workflow_ref.workflow_id,
                    },
                    "execution_result": {
                        "result": "Composition workflow failed",
                        "error": str(e),
                    },
                }
        
        # Run async in thread pool
        with ThreadPoolExecutor() as executor:
            future = executor.submit(lambda: asyncio.run(run_workflow()))
            return cast(Dict[str, Any], future.result())
    
    return workflow_execution_node


def should_continue_composition(state: WorkflowState) -> str:
    """
    Conditional edge to determine if composition should continue.
    
    Checks:
    - If there was an error, stop
    - If all workflows executed, end
    - Otherwise, continue to next workflow
    
    Args:
        state: Current workflow state
        
    Returns:
        "continue" to execute next workflow, "end" to finish
    """
    # Check for errors
    outputs = state.get("outputs", {})
    if outputs and "error" in outputs:
        logger.warning(f"⚠️  Composition stopping due to error: {outputs.get('error')}")
        return "end"
    
    # Check current step
    current_step = state.get("current_step")
    if not current_step:
        return "end"
    
    # Extract workflow order from step name
    if current_step.startswith("workflow_"):
        try:
            current_order = int(current_step.split("_")[1])
            # Continue if we have more workflows (max will be checked in graph builder)
            logger.info(f"🔀 Composition at step {current_order}, checking if should continue")
            return "continue"
        except (IndexError, ValueError):
            logger.warning(f"⚠️  Could not parse workflow order from step: {current_step}")
            return "end"
    
    return "end"


def build_composition_graph(config: WorkflowComposition) -> StateGraph:
    """
    Build LangGraph workflow from composition configuration.
    
    This function:
    1. Creates a node for each workflow reference
    2. Chains nodes based on execution order
    3. Configures input/output mapping between workflows
    4. Supports conditional execution
    5. Sets up proper entry and exit points
    
    Args:
        config: Validated workflow composition configuration
        
    Returns:
        Compiled StateGraph ready for execution
        
    Example:
        ```python
        from app.domain.workflows.schemas.composition_config import WorkflowComposition
        from app.workflows.graphs.composition_graph import build_composition_graph
        
        config = WorkflowComposition(
            id="content-pipeline",
            workflows=[
                WorkflowReference(workflow_id="parallel-research-analysis", order=1),
                WorkflowReference(workflow_id="creative-review", order=2),
            ]
        )
        
        graph = build_composition_graph(config)
        result = graph.invoke(initial_state)
        ```
    """
    # Sort workflows by order
    sorted_workflows = sorted(config.workflows, key=lambda w: w.order)
    
    logger.info(f"🏗️  Building composition graph: {config.id} ({config.name})")
    logger.info(f"   Workflows: {len(sorted_workflows)}")
    for wf in sorted_workflows:
        logger.info(f"   Order {wf.order}: {wf.workflow_id}")
        if wf.input_mapping:
            logger.info(f"      Input mapping: {wf.input_mapping}")
        if wf.output_mapping:
            logger.info(f"      Output mapping: {wf.output_mapping}")
    
    # Initialize graph with WorkflowState schema
    graph = StateGraph(WorkflowState)
    
    # Create and add node for each workflow
    workflow_nodes = {}
    for workflow_ref in sorted_workflows:
        node_name = f"workflow_{workflow_ref.order}"
        node_func = create_workflow_execution_node(workflow_ref, workflow_ref.order)
        graph.add_node(node_name, node_func)
        workflow_nodes[workflow_ref.order] = node_name
        logger.info(f"✅ Added workflow node '{node_name}' for {workflow_ref.workflow_id}")
    
    # Set entry point (first workflow)
    if sorted_workflows:
        first_order = sorted_workflows[0].order
        graph.set_entry_point(workflow_nodes[first_order])
        logger.info(f"✅ Set entry point: {workflow_nodes[first_order]}")
    
    # Build edges between workflows
    for i, workflow_ref in enumerate(sorted_workflows):
        current_order = workflow_ref.order
        current_node = workflow_nodes[current_order]
        
        # Check if there's a next workflow
        if i < len(sorted_workflows) - 1:
            next_order = sorted_workflows[i + 1].order
            next_node = workflow_nodes[next_order]
            
            # Add conditional edge for continuation
            graph.add_conditional_edges(
                current_node,
                should_continue_composition,
                {
                    "continue": next_node,
                    "end": END,
                }
            )
            logger.info(f"✅ Edge: {current_node} → {next_node} (if continue) OR → END")
        else:
            # Last workflow goes to END
            graph.add_edge(current_node, END)
            logger.info(f"✅ Final: {current_node} → END")
    
    logger.info(f"✅ Composition graph build complete: {config.id}")
    return graph


def create_composition_workflow(composition_id: str) -> Optional[StateGraph]:
    """
    Create a composition workflow from database config.
    
    This is the main entry point for creating composition workflows.
    It loads the config from database, validates it, and builds the graph.
    
    Args:
        composition_id: ID of composition to create
        
    Returns:
        Compiled StateGraph or None if config not found
        
    Raises:
        ValidationError: If config is invalid
    """
    from pydantic import ValidationError
    
    # Load composition config from database
    config_dict = _load_composition_config(composition_id)
    if not config_dict:
        return None
    
    # Extract config from the loaded dict
    inner_config = config_dict.get('config', {})
    if not inner_config:
        logger.error(f"❌ No config found in composition: {composition_id}")
        return None
    
    try:
        # Validate and create WorkflowComposition object
        config = WorkflowComposition.model_validate(inner_config)
        
        logger.info(f"🔧 Building composition workflow: {config.name}")
        logger.info(f"   ID: {config.id}")
        logger.info(f"   Workflows: {len(config.workflows)}")
        logger.info(f"   Tags: {config.tags}")
        
        return build_composition_graph(config)
        
    except ValidationError as e:
        logger.error(f"❌ Invalid composition config: {e}")
        return None
