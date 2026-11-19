"""
Simple workflow graph definition.

Demonstrates basic LangGraph workflow composition with a linear
planner → executor pattern.
"""

from langgraph.graph import StateGraph, END
from ..state.workflow_state import WorkflowState
from ..nodes.simple_nodes import plan_node, execute_node


def create_simple_workflow() -> StateGraph:
    """
    Create a simple linear workflow: Planner → Executor → End
    
    This is the "Hello World" of LangGraph workflows for cogitate.
    It demonstrates:
    - Graph composition with StateGraph
    - Node addition
    - Edge wiring
    - Entry point configuration
    
    Returns:
        StateGraph ready for compilation with checkpointer
        
    Example:
        ```python
        from app.workflows.graphs.simple_workflow import create_simple_workflow
        from app.workflows.checkpointing import CheckpointerConfig
        
        graph = create_simple_workflow()
        
        with CheckpointerConfig.get_checkpointer() as checkpointer:
            compiled = graph.compile(checkpointer=checkpointer)
            
            initial_state = {
                "workflow_id": "wf-123",
                "template_id": "tpl-456",
                "messages": [],
                "current_step": None,
                "execution_result": None,
                "approval_required": False,
                "approval_status": None,
                "metadata": RunMetadata(
                    workflow_id="wf-123",
                    template_id="tpl-456"
                )
            }
            
            result = compiled.invoke(initial_state)
        ```
    """
    # Initialize graph with WorkflowState schema
    graph = StateGraph(WorkflowState)
    
    # Add nodes
    graph.add_node("planner", plan_node)
    graph.add_node("executor", execute_node)
    
    # Set entry point - workflow starts at planner
    graph.set_entry_point("planner")
    
    # Add edges - linear flow
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", END)
    
    return graph
