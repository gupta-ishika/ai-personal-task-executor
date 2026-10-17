"""Base LangGraph workflow and skeleton graph definition."""

from typing import Any, Dict, Literal, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

from src.graph.state import AgentState
from src.agents.supervisor import supervisor_node

# Keep alias for backward compatibility
supervisor_placeholder = supervisor_node


def research_placeholder(state: AgentState) -> Dict[str, Any]:
    """Placeholder research agent node."""
    return {"research_results": [{"title": "Sample Finding", "source": "search"}]}


def planning_placeholder(state: AgentState) -> Dict[str, Any]:
    """Placeholder planning agent node."""
    return {
        "proposed_action": {
            "type": "create_event",
            "title": "Proposed Event",
            "time": "2026-10-01T18:00:00",
        },
        "approval_status": "pending",
    }


def approval_placeholder(state: AgentState) -> Dict[str, Any]:
    """Human approval gate node using LangGraph interrupt."""
    status = state.get("approval_status")
    if status == "pending" or not status:
        # Trigger human-in-the-loop interrupt with proposed action payload
        decision = interrupt({
            "prompt": "Approval required before executing external action.",
            "proposed_action": state.get("proposed_action"),
        })
        # If resumed with a string or dict decision
        if isinstance(decision, dict):
            status = decision.get("approval_status", "rejected")
        elif isinstance(decision, str):
            status = decision
        else:
            status = "rejected"
    return {"approval_status": status}


def action_placeholder(state: AgentState) -> Dict[str, Any]:
    """Placeholder action agent node."""
    return {"execution_result": {"status": "success", "action": state.get("proposed_action")}}


def final_summary_placeholder(state: AgentState) -> Dict[str, Any]:
    """Placeholder final summary node."""
    return state


def route_supervisor(state: AgentState) -> Literal["research_agent", "planning_agent"]:
    """Route from supervisor based on task_type."""
    task_type = state.get("task_type")
    if task_type == "schedule":
        return "planning_agent"
    return "research_agent"


def route_approval(state: AgentState) -> Literal["action_agent", "planning_agent", "final_summary"]:
    """Route from approval gate based on approval_status."""
    status = state.get("approval_status")
    if status == "approved":
        return "action_agent"
    elif status == "rejected":
        return "planning_agent"
    return "final_summary"


def create_task_graph(checkpointer: Optional[Any] = None):
    """Create and compile the task executor LangGraph."""
    if checkpointer is None:
        checkpointer = MemorySaver()

    builder = StateGraph(AgentState)

    # Register nodes
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("research_agent", research_placeholder)
    builder.add_node("planning_agent", planning_placeholder)
    builder.add_node("approval_node", approval_placeholder)
    builder.add_node("action_agent", action_placeholder)
    builder.add_node("final_summary", final_summary_placeholder)

    # Connect edges
    builder.add_edge(START, "supervisor")

    builder.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {
            "research_agent": "research_agent",
            "planning_agent": "planning_agent",
        },
    )

    builder.add_edge("research_agent", "planning_agent")
    builder.add_edge("planning_agent", "approval_node")

    builder.add_conditional_edges(
        "approval_node",
        route_approval,
        {
            "action_agent": "action_agent",
            "planning_agent": "planning_agent",
            "final_summary": "final_summary",
        },
    )

    builder.add_edge("action_agent", "final_summary")
    builder.add_edge("final_summary", END)

    return builder.compile(checkpointer=checkpointer)
