"""Base LangGraph workflow and skeleton graph definition."""

from typing import Any, Dict, Literal, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

from src.graph.state import AgentState
from src.agents.supervisor import supervisor_node
from src.agents.research_agent import research_agent_node
from src.agents.planning_agent import planning_agent_node

from src.graph.approval import approval_node, route_approval

from src.agents.action_agent import action_agent_node

from src.graph.summary import final_summary_node

# Keep aliases for backward compatibility
supervisor_placeholder = supervisor_node
research_placeholder = research_agent_node
planning_placeholder = planning_agent_node
approval_placeholder = approval_node
action_placeholder = action_agent_node
final_summary_placeholder = final_summary_node


def route_supervisor(state: AgentState) -> Literal["research_agent", "planning_agent"]:
    """Route from supervisor based on task_type."""
    task_type = state.get("task_type")
    if task_type == "schedule":
        return "planning_agent"
    return "research_agent"


def create_task_graph(checkpointer: Optional[Any] = None):
    """Create and compile the task executor LangGraph."""
    if checkpointer is None:
        checkpointer = MemorySaver()

    builder = StateGraph(AgentState)

    # Register nodes
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("research_agent", research_agent_node)
    builder.add_node("planning_agent", planning_agent_node)
    builder.add_node("approval_node", approval_node)
    builder.add_node("action_agent", action_agent_node)
    builder.add_node("final_summary", final_summary_node)

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
