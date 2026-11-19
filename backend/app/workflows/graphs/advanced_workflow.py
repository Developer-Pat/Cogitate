"""
Advanced workflow graph with conditional routing and interrupt support.

Demonstrates:
- Conditional edges based on state
- Human-in-the-loop interrupts
- Reflection cycles for plan refinement
"""

from typing import Literal
from langgraph.graph import StateGraph, END
from ..state.workflow_state import WorkflowState
from ..nodes.enhanced_nodes import plan_node as enhanced_plan_node
from ..nodes.enhanced_nodes import execute_node as enhanced_execute_node
from ..nodes.enhanced_nodes import review_node


def should_approve(state: WorkflowState) -> Literal["review", "execute"]:
    """
    Conditional edge function: route based on approval requirement.
    
    This function examines the workflow state and determines
    whether the workflow should go to human review or proceed
    directly to execution.
    
    Args:
        state: Current workflow state
        
    Returns:
        "review" if approval required, "execute" otherwise
    """
    if state.get("approval_required", False):
        return "review"
    else:
        return "execute"


def execution_result_router(state: WorkflowState) -> Literal["finalize", "refine"]:
    """
    Conditional edge: route based on execution result quality.
    
    This enables reflection cycles - if execution fails or produces
    poor results, we can loop back to planning for refinement.
    
    Args:
        state: Current workflow state
        
    Returns:
        "finalize" if successful, "refine" if needs improvement
    """
    execution_result = state.get("execution_result") or {}

    # Check for errors
    if "error" in execution_result:
        return "refine"

    # Check for successful completion
    if execution_result.get("result") == "Plan executed successfully":
        return "finalize"
    
    # Default to finalize
    return "finalize"


def refiner_node(state: WorkflowState) -> dict:
    """
    Refiner node for plan improvement cycles.
    
    This node is called when execution fails or produces
    unsatisfactory results. It prepares the state for
    re-planning.
    
    Args:
        state: Current workflow state
        
    Returns:
        State updates to trigger re-planning
    """
    from langchain_core.messages import HumanMessage
    
    execution_result = state.get("execution_result") or {}
    error_message = execution_result.get("error", "Unknown issue")
    
    # Add refinement request to messages
    refinement_message = HumanMessage(
        content=f"Previous execution failed: {error_message}. Please refine the plan."
    )
    
    return {
        "messages": state["messages"] + [refinement_message],
        "current_step": "planner",
        "execution_result": None,
    }


def create_advanced_workflow() -> StateGraph:
    """
    Create an advanced workflow with conditional routing and reflection.
    
    Workflow structure:
    ```
    [Entry] → [Planner] → [Conditional]
                          ├─→ [Review] ─┐
                          └─→ [Executor] → [Result Check]
                                            ├─→ [Refiner] ─┐
                                            └─→ [END] ←────┘
    ```
    
    Features:
    - LLM-based planning
    - Human-in-the-loop approval (interrupt)
    - Conditional routing based on approval requirement
    - Reflection cycle for plan refinement
    - Checkpoint-based persistence
    
    Returns:
        StateGraph ready for compilation with checkpointer
        
    Example:
        ```python
        from app.workflows.graphs.advanced_workflow import create_advanced_workflow
        from app.workflows.checkpointing import CheckpointerConfig
        
        graph = create_advanced_workflow()
        
        with CheckpointerConfig.get_checkpointer() as checkpointer:
            compiled = graph.compile(checkpointer=checkpointer)
            
            # Execute with interrupt support
            config = {"configurable": {"thread_id": "workflow-123"}}
            result = compiled.invoke(initial_state, config)
        ```
    """
    # Initialize graph with WorkflowState schema
    graph = StateGraph(WorkflowState)
    
    # Add nodes
    graph.add_node("planner", enhanced_plan_node)
    graph.add_node("reviewer", review_node)
    graph.add_node("executor", enhanced_execute_node)
    graph.add_node("refiner", refiner_node)
    
    # Set entry point - workflow starts at planner
    graph.set_entry_point("planner")
    
    # Add conditional edge after planning
    # Routes to reviewer or executor based on approval_required
    graph.add_conditional_edges(
        "planner",
        should_approve,
        {
            "review": "reviewer",
            "execute": "executor"
        }
    )
    
    # Add edge from reviewer to executor (if approved)
    # or to refiner (if rejected)
    graph.add_conditional_edges(
        "reviewer",
        lambda state: "executor" if state["approval_status"] == "approved" else "refiner",
        {
            "executor": "executor",
            "refiner": "refiner"
        }
    )
    
    # Add conditional edge after execution
    # Routes to refiner or END based on result quality
    graph.add_conditional_edges(
        "executor",
        execution_result_router,
        {
            "refine": "refiner",
            "finalize": END
        }
    )
    
    # Add edge from refiner back to planner (reflection cycle)
    graph.add_edge("refiner", "planner")
    
    return graph
