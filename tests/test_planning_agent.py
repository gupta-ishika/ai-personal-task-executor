"""Tests for Phase 5: Planning Agent and re-planning."""

import pytest
from src.agents.planning_agent import (
    PlanningAgent,
    extract_schedule_details,
    planning_agent_node,
)
from src.graph.graph import create_task_graph
from src.graph.state import AgentState
from langgraph.types import Command


class TestSchedulePlanning:
    """Test planning for direct 'schedule' task variant."""

    def test_extract_schedule_details(self):
        details = extract_schedule_details("Schedule a meeting with Rahul tomorrow at 5 PM")
        assert "Rahul" in details["title"]
        assert "Tomorrow" in details["date"]
        assert "5 PM" in details["time"]

    def test_plan_schedule_payload(self):
        agent = PlanningAgent()
        state: AgentState = {
            "user_request": "Schedule a meeting with Rahul tomorrow at 5 PM",
            "task_type": "schedule",
        }
        result = agent.plan(state)
        assert result["approval_status"] == "pending"
        action = result["proposed_action"]
        assert action["action_type"] == "create_calendar_event"
        assert "summary" in action
        assert action["revision"] == 1

        details = action["details"]
        assert "Meeting with Rahul" in details["title"]
        assert "Tomorrow" in details["date"]
        assert "5 PM" in details["time"]
        assert "description" in details


class TestResearchAndSavePlanning:
    """Test planning for 'research_and_save' task variant."""

    def test_plan_save_note_with_findings(self):
        agent = PlanningAgent()
        findings = [
            {
                "title": "Third Wave Coffee",
                "details": "Artisanal coffee on 12th Main Indiranagar",
                "url": "https://example.com/third-wave",
                "source": "Search MCP",
            },
            {
                "title": "Araku Coffee",
                "details": "Specialty cafe with roastery",
                "url": "https://example.com/araku",
                "source": "Search MCP",
            },
        ]
        state: AgentState = {
            "user_request": "Find 2 good cafes in Indiranagar and save the options",
            "task_type": "research_and_save",
            "research_results": findings,
        }
        result = agent.plan(state)
        assert result["approval_status"] == "pending"
        action = result["proposed_action"]
        assert action["action_type"] == "save_note"
        assert "summary" in action

        details = action["details"]
        assert details["format"] == "markdown"
        assert "Third Wave Coffee" in details["content"]
        assert "Araku Coffee" in details["content"]
        assert details["item_count"] == 2
        assert details["filename"].endswith(".md")

    def test_plan_save_note_with_empty_findings(self):
        agent = PlanningAgent()
        state: AgentState = {
            "user_request": "Search for obscure unindexed term and save",
            "task_type": "research_and_save",
            "research_results": [],
        }
        result = agent.plan(state)
        assert result["approval_status"] == "pending"
        action = result["proposed_action"]
        assert action["action_type"] == "save_note"
        assert "No specific research findings" in action["details"]["content"]


class TestResearchAndActionPlanning:
    """Test planning for 'research_and_action' task variant."""

    def test_plan_research_and_action_synthesizes_venue(self):
        agent = PlanningAgent()
        findings = [
            {
                "title": "Glen's Bakehouse - Indiranagar",
                "details": "Spacious casual bakehouse cafe for 4-6 people, budget under ₹2000",
                "url": "https://example.com/glens",
                "source": "Search MCP",
            },
            {
                "title": "Third Wave Coffee",
                "details": "Group friendly cafe",
                "url": "https://example.com/twc",
                "source": "Search MCP",
            },
        ]
        state: AgentState = {
            "user_request": "Find a cafe for 4 people this Saturday evening and schedule it",
            "task_type": "research_and_action",
            "research_results": findings,
        }
        result = agent.plan(state)
        action = result["proposed_action"]
        assert action["action_type"] == "create_calendar_event"
        assert "Glen's Bakehouse" in action["details"]["title"]
        assert "Saturday" in action["details"]["date"]
        assert action["details"]["location"] == "Glen's Bakehouse - Indiranagar"
        assert result["approval_status"] == "pending"


class TestRePlanningOnRejection:
    """Test re-planning when approval status is rejected."""

    def test_replanning_selects_alternative_option(self):
        agent = PlanningAgent()
        findings = [
            {
                "title": "Option A - First Cafe",
                "details": "First cafe details",
                "url": "https://example.com/a",
            },
            {
                "title": "Option B - Second Cafe",
                "details": "Second cafe details",
                "url": "https://example.com/b",
            },
        ]

        # Initial proposal: Option A
        initial_state: AgentState = {
            "user_request": "Find a cafe and schedule it",
            "task_type": "research_and_action",
            "research_results": findings,
        }
        initial_result = agent.plan(initial_state)
        assert "Option A" in initial_result["proposed_action"]["details"]["title"]
        assert initial_result["proposed_action"]["revision"] == 1

        # User rejects proposal -> Re-planning state
        rejected_state: AgentState = {
            "user_request": "Find a cafe and schedule it",
            "task_type": "research_and_action",
            "research_results": findings,
            "proposed_action": initial_result["proposed_action"],
            "approval_status": "rejected",
        }
        revised_result = agent.plan(rejected_state)
        # Should now propose Option B
        assert "Option B" in revised_result["proposed_action"]["details"]["title"]
        assert revised_result["proposed_action"]["revision"] == 2
        assert revised_result["approval_status"] == "pending"
        assert "revised following rejection" in revised_result["proposed_action"]["summary"]


class TestPlanningAgentNodeAndGraph:
    """Test planning agent node and full graph pause/resume execution."""

    def test_planning_agent_node_updates_state(self):
        state: AgentState = {
            "user_request": "Schedule call with Priya tomorrow at 3 pm",
            "task_type": "schedule",
        }
        updates = planning_agent_node(state)
        assert "proposed_action" in updates
        assert updates["approval_status"] == "pending"

    def test_graph_pauses_with_concrete_proposed_action(self):
        graph = create_task_graph()
        config = {"configurable": {"thread_id": "test_plan_graph_pause"}}

        # Run until interrupt at approval_node
        graph.invoke(
            {"user_request": "Schedule a meeting with Rahul tomorrow at 5 PM"},
            config=config,
        )

        state = graph.get_state(config)
        assert len(state.tasks) > 0
        interrupt_val = state.tasks[0].interrupts[0].value
        assert "proposed_action" in interrupt_val
        proposed = interrupt_val["proposed_action"]
        assert proposed["action_type"] == "create_calendar_event"
        assert "Meeting with Rahul" in proposed["details"]["title"]

    def test_graph_replan_cycle_on_rejection(self):
        graph = create_task_graph()
        config = {"configurable": {"thread_id": "test_plan_graph_replan"}}

        # Initial run pauses at approval gate
        graph.invoke(
            {"user_request": "Find 3 good cafes in Indiranagar and save the options"},
            config=config,
        )
        state_1 = graph.get_state(config)
        first_action = state_1.values.get("proposed_action")
        assert first_action["revision"] == 1

        # Resume with rejection decision -> LangGraph routes back to planning_agent then interrupts again
        graph.invoke(
            Command(resume={"approval_status": "rejected"}),
            config=config,
        )

        state_2 = graph.get_state(config)
        second_action = state_2.values.get("proposed_action")
        assert second_action["revision"] == 2
        assert second_action["action_type"] == "save_note"
