"""Unit tests for Phase 2: Shared State & Graph Skeleton."""

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from src.graph.state import AgentState
from src.graph.graph import create_task_graph


def test_agent_state_schema():
    """Test AgentState TypedDict schema."""
    state: AgentState = {
        "user_request": "Schedule a meeting with Rahul tomorrow at 5 PM",
        "task_type": "schedule",
        "research_results": None,
        "proposed_action": {"type": "create_event", "title": "Meeting with Rahul"},
        "approval_status": "pending",
        "execution_result": None,
        "error": None,
    }
    assert state["user_request"] == "Schedule a meeting with Rahul tomorrow at 5 PM"
    assert state["task_type"] == "schedule"
    assert state["proposed_action"]["type"] == "create_event"


def test_graph_compilation_and_checkpointer():
    """Verify that graph compiles with MemorySaver checkpointer."""
    memory = MemorySaver()
    app = create_task_graph(checkpointer=memory)
    assert app is not None
    assert app.checkpointer is memory


def test_graph_interrupt_at_approval_gate():
    """Verify that graph execution pauses at approval gate with interrupt."""
    memory = MemorySaver()
    app = create_task_graph(checkpointer=memory)
    config = {"configurable": {"thread_id": "thread-1"}}

    # Initial invoke
    initial_input: AgentState = {
        "user_request": "Find a cafe and schedule it",
        "task_type": "research_and_action",
    }

    # Stream or invoke until interrupt
    events = []
    for event in app.stream(initial_input, config=config):
        events.append(event)

    # Get state from checkpointer
    state = app.get_state(config)
    assert state.next == ("approval_node",)
    assert len(state.tasks) > 0
    assert len(state.tasks[0].interrupts) > 0
    interrupt_value = state.tasks[0].interrupts[0].value
    assert "proposed_action" in interrupt_value
    assert interrupt_value["proposed_action"]["type"] == "create_event"


def test_graph_resume_on_approval():
    """Verify that resuming with 'approved' executes action agent and reaches final summary."""
    memory = MemorySaver()
    app = create_task_graph(checkpointer=memory)
    config = {"configurable": {"thread_id": "thread-2"}}

    initial_input: AgentState = {
        "user_request": "Find a cafe and schedule it",
        "task_type": "research_and_action",
    }

    # Run until interrupt
    for _ in app.stream(initial_input, config=config):
        pass

    # Resume with approval
    resume_command = Command(resume="approved")
    final_events = []
    for event in app.stream(resume_command, config=config):
        final_events.append(event)

    final_state = app.get_state(config)
    assert final_state.next == ()  # Reached END
    assert final_state.values.get("approval_status") == "approved"
    assert final_state.values.get("execution_result") is not None
    assert final_state.values.get("execution_result")["status"] == "success"


def test_graph_resume_on_rejection():
    """Verify that resuming with 'rejected' routes back to planning agent."""
    memory = MemorySaver()
    app = create_task_graph(checkpointer=memory)
    config = {"configurable": {"thread_id": "thread-3"}}

    initial_input: AgentState = {
        "user_request": "Find a cafe and schedule it",
        "task_type": "research_and_action",
    }

    # Run until interrupt
    for _ in app.stream(initial_input, config=config):
        pass

    # Resume with rejection
    resume_command = Command(resume="rejected")
    for _ in app.stream(resume_command, config=config):
        pass

    # After rejection, it goes back to planning_agent -> approval_node -> interrupts again
    state = app.get_state(config)
    assert state.next == ("approval_node",)
    assert state.values.get("approval_status") == "pending"


def test_schedule_task_bypasses_research():
    """Verify that a 'schedule' task routes directly from supervisor to planning agent."""
    memory = MemorySaver()
    app = create_task_graph(checkpointer=memory)
    config = {"configurable": {"thread_id": "thread-4"}}

    initial_input: AgentState = {
        "user_request": "Schedule a meeting tomorrow at 5 PM",
        "task_type": "schedule",
    }

    visited_nodes = []
    for event in app.stream(initial_input, config=config):
        visited_nodes.extend(event.keys())

    assert "supervisor" in visited_nodes
    assert "research_agent" not in visited_nodes
    assert "planning_agent" in visited_nodes
