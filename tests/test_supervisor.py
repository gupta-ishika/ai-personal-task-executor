"""Tests for Phase 3: Supervisor Agent and routing."""

import pytest
from src.agents.supervisor import (
    TASK_TYPE_SCHEDULE,
    TASK_TYPE_RESEARCH_AND_SAVE,
    TASK_TYPE_RESEARCH_AND_ACTION,
    classify_task_type,
    parse_user_request,
    supervisor_node,
)
from src.graph.graph import create_task_graph, route_supervisor
from src.graph.state import AgentState


class TestTaskClassification:
    """Test request classification across all three MVP variants and edge cases."""

    def test_classify_schedule_variant(self):
        requests = [
            "Schedule a meeting with Rahul tomorrow at 5 PM",
            "Add dental appointment to my calendar next Monday",
            "Put team sync on my calendar for Friday at 10 am",
            "Schedule call with client tomorrow afternoon",
        ]
        for req in requests:
            assert classify_task_type(req) == TASK_TYPE_SCHEDULE, f"Failed for: {req}"

    def test_classify_research_and_save_variant(self):
        requests = [
            "Find 3 good cafes in Indiranagar and save the options",
            "Research best noise-cancelling headphones and note them down",
            "Search for top Python libraries for data analysis",
            "Explore budget hotels in Goa and save",
        ]
        for req in requests:
            assert classify_task_type(req) == TASK_TYPE_RESEARCH_AND_SAVE, f"Failed for: {req}"

    def test_classify_research_and_action_variant(self):
        requests = [
            "Find a cafe for 4 people this Saturday evening, under ₹3000, and schedule it on my calendar",
            "Research quiet coworking spaces nearby and book a calendar event for tomorrow 2 pm",
            "Look up Indian restaurants in Koramangala and put it on my calendar",
        ]
        for req in requests:
            assert classify_task_type(req) == TASK_TYPE_RESEARCH_AND_ACTION, f"Failed for: {req}"

    def test_fallback_unrecognized_or_empty(self):
        assert classify_task_type("") == TASK_TYPE_RESEARCH_AND_ACTION
        assert classify_task_type("   ") == TASK_TYPE_RESEARCH_AND_ACTION
        assert classify_task_type(None) == TASK_TYPE_RESEARCH_AND_ACTION
        assert classify_task_type("Hello there!") == TASK_TYPE_RESEARCH_AND_ACTION


class TestParseUserRequest:
    """Test user request parsing and hint extraction."""

    def test_parse_valid_request_with_hints(self):
        result = parse_user_request("Schedule sync with Priya tomorrow at 3 pm")
        assert result["task_type"] == TASK_TYPE_SCHEDULE
        assert result["is_empty"] is False
        assert any("tomorrow" in hint for hint in result["datetime_hints"])
        assert any("3 pm" in hint for hint in result["datetime_hints"])

    def test_parse_empty_request(self):
        result = parse_user_request("")
        assert result["is_empty"] is True
        assert result["task_type"] == TASK_TYPE_RESEARCH_AND_ACTION
        assert result["datetime_hints"] == []


class TestSupervisorNode:
    """Test supervisor node in LangGraph state context."""

    def test_supervisor_node_classifies_request(self):
        state: AgentState = {
            "user_request": "Schedule a meeting with Rahul tomorrow at 5 PM",
        }
        updates = supervisor_node(state)
        assert updates["task_type"] == TASK_TYPE_SCHEDULE

    def test_supervisor_node_preserves_preconfigured_task_type(self):
        state: AgentState = {
            "user_request": "Schedule a meeting with Rahul tomorrow at 5 PM",
            "task_type": TASK_TYPE_RESEARCH_AND_ACTION,
        }
        updates = supervisor_node(state)
        assert updates["task_type"] == TASK_TYPE_RESEARCH_AND_ACTION

    def test_supervisor_node_handles_empty_request_gracefully(self):
        state: AgentState = {"user_request": ""}
        updates = supervisor_node(state)
        assert updates["task_type"] == TASK_TYPE_RESEARCH_AND_ACTION
        assert "error" in updates


class TestSupervisorRouting:
    """Test supervisor conditional routing in the workflow."""

    def test_route_schedule_goes_to_planning(self):
        state: AgentState = {"task_type": TASK_TYPE_SCHEDULE}
        assert route_supervisor(state) == "planning_agent"

    def test_route_research_and_save_goes_to_research(self):
        state: AgentState = {"task_type": TASK_TYPE_RESEARCH_AND_SAVE}
        assert route_supervisor(state) == "research_agent"

    def test_route_research_and_action_goes_to_research(self):
        state: AgentState = {"task_type": TASK_TYPE_RESEARCH_AND_ACTION}
        assert route_supervisor(state) == "research_agent"

    def test_full_graph_supervisor_execution_schedule(self):
        graph = create_task_graph()
        config = {"configurable": {"thread_id": "test_sup_sched"}}
        result = graph.invoke(
            {"user_request": "Schedule a call with Priya tomorrow at 4 pm"},
            config=config,
        )
        assert result["task_type"] == TASK_TYPE_SCHEDULE

    def test_full_graph_supervisor_execution_research_and_action(self):
        graph = create_task_graph()
        config = {"configurable": {"thread_id": "test_sup_res_act"}}
        result = graph.invoke(
            {"user_request": "Find a good cafe in Indiranagar and schedule it on my calendar"},
            config=config,
        )
        assert result["task_type"] == TASK_TYPE_RESEARCH_AND_ACTION
