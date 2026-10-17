"""Tests for Action Agent and tool execution with failure handling."""

import os
import shutil
import pytest
from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver

from src.agents.action_agent import ActionAgent, action_agent_node
from src.mcp.calendar_mcp import CalendarMCP
from src.mcp.notes_mcp import NotesMCP
from src.graph.graph import create_task_graph
from src.graph.state import AgentState

TEST_NOTES_DIR = "test_scratch_action_notes"


class TestActionAgentExecution:
    """Test suite for Action Agent execution and boundary enforcement."""

    @classmethod
    def teardown_class(cls):
        if os.path.exists(TEST_NOTES_DIR):
            shutil.rmtree(TEST_NOTES_DIR, ignore_errors=True)

    def test_execution_blocked_without_human_approval(self):
        agent = ActionAgent()
        unapproved_state: AgentState = {
            "user_request": "Schedule a meeting with Rahul",
            "task_type": "schedule",
            "approval_status": "pending",
            "proposed_action": {
                "action_type": "create_calendar_event",
                "details": {"title": "Meeting with Rahul", "date": "Tomorrow", "time": "5 PM"},
            },
        }
        result = agent.execute(unapproved_state)
        assert result["execution_result"]["status"] == "blocked"
        assert "error" in result

    def test_execute_calendar_event_success(self):
        cal_client = CalendarMCP()
        agent = ActionAgent(calendar_client=cal_client)

        approved_state: AgentState = {
            "user_request": "Schedule a meeting with Rahul tomorrow at 5 PM",
            "task_type": "schedule",
            "approval_status": "approved",
            "proposed_action": {
                "action_type": "create_calendar_event",
                "details": {
                    "title": "Meeting with Rahul",
                    "date": "Tomorrow",
                    "time": "5 PM",
                    "description": "Discuss project sprint",
                    "location": "Virtual",
                },
            },
        }

        output = agent.execute(approved_state)
        exec_res = output["execution_result"]
        assert exec_res["status"] == "success"
        assert exec_res["retries_used"] == 0
        assert exec_res["result"]["event"]["title"] == "Meeting with Rahul"

    def test_execute_save_note_success(self):
        notes_client = NotesMCP(storage_path=TEST_NOTES_DIR)
        agent = ActionAgent(notes_client=notes_client)

        approved_state: AgentState = {
            "user_request": "Find cafes and save",
            "task_type": "research_and_save",
            "approval_status": "approved",
            "proposed_action": {
                "action_type": "save_note",
                "details": {
                    "title": "Indiranagar Cafes",
                    "filename": "action_test_cafes.md",
                    "content": "# Cafes\n\n- Third Wave Coffee\n- Araku Coffee",
                },
            },
        }

        output = agent.execute(approved_state)
        exec_res = output["execution_result"]
        assert exec_res["status"] == "success"
        assert exec_res["retries_used"] == 0
        assert os.path.exists(exec_res["result"]["path"])

    def test_retry_once_on_tool_failure_then_succeeds(self):
        # Simulates 1 transient failure; retry should succeed
        cal_client = CalendarMCP(simulate_failure_count=1)
        agent = ActionAgent(calendar_client=cal_client, max_retries=1)

        approved_state: AgentState = {
            "approval_status": "approved",
            "proposed_action": {
                "action_type": "create_calendar_event",
                "details": {"title": "Retry Test Meeting", "date": "Tomorrow", "time": "2 PM"},
            },
        }

        output = agent.execute(approved_state)
        exec_res = output["execution_result"]
        assert exec_res["status"] == "success"
        assert exec_res["retries_used"] == 1

    def test_failure_handling_persistent_failure_asks_user(self):
        # Simulates 2 failures (exceeds max_retries=1)
        cal_client = CalendarMCP(simulate_failure_count=3)
        agent = ActionAgent(calendar_client=cal_client, max_retries=1)

        approved_state: AgentState = {
            "approval_status": "approved",
            "proposed_action": {
                "action_type": "create_calendar_event",
                "details": {"title": "Persistent Failing Meeting", "date": "Tomorrow", "time": "2 PM"},
            },
        }

        # Must not crash the graph; returns failure with ask_user_guidance
        output = agent.execute(approved_state)
        exec_res = output["execution_result"]
        assert exec_res["status"] == "failed"
        assert exec_res["retries_used"] == 1
        assert exec_res["next_step"] == "ask_user_guidance"
        assert "error" in output

    def test_action_agent_node_in_graph(self):
        graph = create_task_graph(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "test_action_graph_flow"}}

        # Run until approval interrupt
        graph.invoke(
            {"user_request": "Schedule a meeting with Rahul tomorrow at 5 PM"},
            config=config,
        )

        # Resume with approved decision
        graph.invoke(
            Command(resume="approved"),
            config=config,
        )

        final_state = graph.get_state(config)
        assert final_state.next == ()  # Reached END
        exec_res = final_state.values.get("execution_result")
        assert exec_res is not None
        assert exec_res["status"] == "success"
        assert "event" in exec_res["result"]
        assert "Rahul" in exec_res["result"]["event"]["title"]
