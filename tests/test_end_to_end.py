"""End-to-end integration tests across all three task-type variants and error flows."""

import os
import shutil
import pytest
from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver

from src.graph.graph import create_task_graph
from src.agents.supervisor import (
    TASK_TYPE_SCHEDULE,
    TASK_TYPE_RESEARCH_AND_SAVE,
    TASK_TYPE_RESEARCH_AND_ACTION,
)

E2E_NOTES_DIR = "test_e2e_notes"


class TestEndToEndWorkflows:
    """End-to-End integration test suite."""

    @classmethod
    def teardown_class(cls):
        if os.path.exists(E2E_NOTES_DIR):
            shutil.rmtree(E2E_NOTES_DIR, ignore_errors=True)

    def test_e2e_variant_1_schedule_workflow(self):
        """Variant 1: Schedule -> Planning -> Approval -> Action -> Final Summary."""
        graph = create_task_graph(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "e2e_var1_sched"}}

        # 1. Run until approval interrupt
        graph.invoke(
            {"user_request": "Schedule a meeting with Rahul tomorrow at 5 PM"},
            config=config,
        )

        state = graph.get_state(config)
        assert state.next == ("approval_node",)
        assert state.values["task_type"] == TASK_TYPE_SCHEDULE
        assert state.values.get("research_results") is None  # Skipped research step!

        # 2. Approve action
        graph.invoke(
            Command(resume="approve"),
            config=config,
        )

        final_state = graph.get_state(config)
        assert final_state.next == ()  # Reached END
        assert final_state.values["approval_status"] == "approved"
        assert final_state.values["execution_result"]["status"] == "success"
        summary = final_state.values["final_summary"]
        assert "Direct scheduling" in summary["researched"]
        assert "Meeting with Rahul" in summary["planned"]
        assert "Created calendar event 'Meeting with Rahul'" in summary["done"]

    def test_e2e_variant_2_research_and_save_workflow(self):
        """Variant 2: Research & Save -> Research -> Planning -> Approval -> Action (Notes MCP) -> Final Summary."""
        graph = create_task_graph(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "e2e_var2_save"}}

        # 1. Run until approval interrupt
        graph.invoke(
            {"user_request": "Find 3 good cafes in Indiranagar and save the options"},
            config=config,
        )

        state = graph.get_state(config)
        assert state.next == ("approval_node",)
        assert state.values["task_type"] == TASK_TYPE_RESEARCH_AND_SAVE
        assert len(state.values["research_results"]) > 0

        # 2. Approve action
        graph.invoke(
            Command(resume="approve"),
            config=config,
        )

        final_state = graph.get_state(config)
        assert final_state.next == ()  # Reached END
        assert final_state.values["execution_result"]["status"] == "success"
        summary = final_state.values["final_summary"]
        assert "Discovered" in summary["researched"]
        assert "Save" in summary["planned"]
        assert "Saved research findings to note file" in summary["done"]

    def test_e2e_variant_3_research_and_action_workflow(self):
        """Variant 3: Primary Demo flow (Research -> Plan -> Approve -> Action -> Summary)."""
        graph = create_task_graph(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "e2e_var3_res_act"}}

        # 1. Run until approval interrupt
        graph.invoke(
            {
                "user_request": "Find a cafe for 4 people this Saturday evening, under ₹3000, and schedule it on my calendar"
            },
            config=config,
        )

        state = graph.get_state(config)
        assert state.next == ("approval_node",)
        assert state.values["task_type"] == TASK_TYPE_RESEARCH_AND_ACTION
        assert len(state.values["research_results"]) > 0
        proposed = state.values["proposed_action"]
        assert proposed["action_type"] == "create_calendar_event"

        # 2. Approve action
        graph.invoke(
            Command(resume="approve"),
            config=config,
        )

        final_state = graph.get_state(config)
        assert final_state.next == ()
        assert final_state.values["execution_result"]["status"] == "success"
        summary = final_state.values["final_summary"]
        assert "Discovered" in summary["researched"]
        assert "Create calendar event" in summary["planned"]
        assert "Created calendar event" in summary["done"]

    def test_e2e_reject_replan_then_approve_workflow(self):
        """Rejection at approval step routes to Planning, re-plans alternative, then succeeds on approval."""
        graph = create_task_graph(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "e2e_replan_approve"}}

        # 1. Run until approval interrupt
        graph.invoke(
            {"user_request": "Find 3 good cafes in Indiranagar and schedule it on my calendar"},
            config=config,
        )
        state_1 = graph.get_state(config)
        assert state_1.values["proposed_action"]["revision"] == 1

        # 2. Reject proposal
        graph.invoke(
            Command(resume="reject"),
            config=config,
        )

        # Pauses again at approval_node with revised plan
        state_2 = graph.get_state(config)
        assert state_2.next == ("approval_node",)
        assert state_2.values["proposed_action"]["revision"] == 2

        # 3. Approve revised plan
        graph.invoke(
            Command(resume="approve"),
            config=config,
        )

        final_state = graph.get_state(config)
        assert final_state.next == ()
        assert final_state.values["execution_result"]["status"] == "success"
        assert "Created calendar event" in final_state.values["final_summary"]["done"]
