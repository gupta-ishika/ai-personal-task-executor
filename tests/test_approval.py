"""Tests for Phase 6: Human-in-the-Loop Approval gate."""

import pytest
from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver

from src.graph.graph import create_task_graph
from src.graph.state import AgentState
from src.graph.approval import (
    build_approval_prompt,
    parse_approval_decision,
    route_approval,
    approval_node,
    APPROVAL_STATUS_APPROVED,
    APPROVAL_STATUS_REJECTED,
    APPROVAL_STATUS_PENDING,
)


class TestApprovalPromptAndParsing:
    """Test approval prompt creation and decision normalization."""

    def test_build_approval_prompt_structure(self):
        action = {
            "type": "create_event",
            "action_type": "create_calendar_event",
            "summary": "Schedule meeting with Rahul tomorrow at 5 PM",
            "details": {
                "title": "Meeting with Rahul",
                "date": "Tomorrow",
                "time": "5 PM",
            },
        }
        prompt = build_approval_prompt(action)
        assert prompt["type"] == "human_approval_required"
        assert "Approve or Reject" in prompt["prompt"]
        assert prompt["options"] == ["Approve", "Reject"]
        assert prompt["summary"] == action["summary"]
        assert prompt["proposed_action"] == action

    def test_parse_approval_decision_approved_variants(self):
        assert parse_approval_decision("approve") == APPROVAL_STATUS_APPROVED
        assert parse_approval_decision("Approved") == APPROVAL_STATUS_APPROVED
        assert parse_approval_decision("YES") == APPROVAL_STATUS_APPROVED
        assert parse_approval_decision("y") == APPROVAL_STATUS_APPROVED
        assert parse_approval_decision(True) == APPROVAL_STATUS_APPROVED
        assert parse_approval_decision({"approval_status": "approved"}) == APPROVAL_STATUS_APPROVED
        assert parse_approval_decision({"decision": "approve"}) == APPROVAL_STATUS_APPROVED
        assert parse_approval_decision({"status": "confirm"}) == APPROVAL_STATUS_APPROVED

    def test_parse_approval_decision_rejected_variants(self):
        assert parse_approval_decision("reject") == APPROVAL_STATUS_REJECTED
        assert parse_approval_decision("Rejected") == APPROVAL_STATUS_REJECTED
        assert parse_approval_decision("no") == APPROVAL_STATUS_REJECTED
        assert parse_approval_decision("n") == APPROVAL_STATUS_REJECTED
        assert parse_approval_decision(False) == APPROVAL_STATUS_REJECTED
        assert parse_approval_decision({"approval_status": "rejected"}) == APPROVAL_STATUS_REJECTED
        assert parse_approval_decision({"decision": "reject"}) == APPROVAL_STATUS_REJECTED

    def test_parse_approval_decision_safe_fallback_on_ambiguous(self):
        # Safety rule: ambiguous decisions must default to rejected
        assert parse_approval_decision(None) == APPROVAL_STATUS_REJECTED
        assert parse_approval_decision("") == APPROVAL_STATUS_REJECTED
        assert parse_approval_decision("maybe later") == APPROVAL_STATUS_REJECTED
        assert parse_approval_decision(12345) == APPROVAL_STATUS_REJECTED
        assert parse_approval_decision({"unknown_key": "xyz"}) == APPROVAL_STATUS_REJECTED


class TestApprovalRouting:
    """Test conditional edge routing based on approval_status."""

    def test_route_approval_to_action_agent(self):
        state: AgentState = {"approval_status": APPROVAL_STATUS_APPROVED}
        assert route_approval(state) == "action_agent"

    def test_route_approval_to_planning_agent_on_reject(self):
        state: AgentState = {"approval_status": APPROVAL_STATUS_REJECTED}
        assert route_approval(state) == "planning_agent"

    def test_route_approval_fallback_to_final_summary(self):
        state: AgentState = {"approval_status": "other_status"}
        assert route_approval(state) == "final_summary"


class TestApprovalGateGraphFlow:
    """Test full LangGraph human-in-the-loop approval workflows."""

    def test_graph_interrupt_presents_exact_payload_and_options(self):
        graph = create_task_graph(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "test_hitl_prompt"}}

        graph.invoke(
            {"user_request": "Schedule a call with Priya tomorrow at 3 pm"},
            config=config,
        )

        state = graph.get_state(config)
        assert state.next == ("approval_node",)
        assert len(state.tasks) > 0
        assert len(state.tasks[0].interrupts) > 0

        interrupt_data = state.tasks[0].interrupts[0].value
        assert interrupt_data["type"] == "human_approval_required"
        assert interrupt_data["options"] == ["Approve", "Reject"]
        assert "proposed_action" in interrupt_data
        details = interrupt_data["proposed_action"]["details"]
        assert "Priya" in details["title"]
        assert "3 PM" in details["time"]

    def test_graph_approve_path_proceeds_to_execution(self):
        graph = create_task_graph(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "test_hitl_approve"}}

        # Run until approval interrupt
        graph.invoke(
            {"user_request": "Schedule sync tomorrow at 10 am"},
            config=config,
        )

        # Resume with approval decision
        graph.invoke(
            Command(resume={"approval_status": "approved"}),
            config=config,
        )

        final_state = graph.get_state(config)
        assert final_state.next == ()  # Reached END
        assert final_state.values.get("approval_status") == APPROVAL_STATUS_APPROVED
        assert "execution_result" in final_state.values

    def test_graph_reject_path_routes_back_to_planning_then_can_be_approved(self):
        graph = create_task_graph(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "test_hitl_reject_replan"}}

        # Initial run: pauses before first execution
        graph.invoke(
            {"user_request": "Find a cafe for 4 people this Saturday evening and schedule it"},
            config=config,
        )
        state_1 = graph.get_state(config)
        assert state_1.next == ("approval_node",)
        first_action = state_1.values.get("proposed_action")
        assert first_action["revision"] == 1

        # User rejects proposal -> routes back to planning_agent -> pauses again at approval_node
        graph.invoke(
            Command(resume="reject"),
            config=config,
        )

        state_2 = graph.get_state(config)
        assert state_2.next == ("approval_node",)
        second_action = state_2.values.get("proposed_action")
        assert second_action["revision"] == 2
        assert "revised following rejection" in second_action["summary"]

        # User approves second revised proposal -> proceeds to action_agent and completes
        graph.invoke(
            Command(resume="approve"),
            config=config,
        )

        state_3 = graph.get_state(config)
        assert state_3.next == ()  # Reached END
        assert state_3.values.get("approval_status") == APPROVAL_STATUS_APPROVED
        assert "execution_result" in state_3.values
