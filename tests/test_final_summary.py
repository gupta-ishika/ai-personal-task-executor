"""Tests for Phase 8: Final Summary generation and edge cases."""

import pytest
from src.graph.summary import generate_final_summary, final_summary_node
from src.graph.state import AgentState


class TestFinalSummary:
    """Test suite for 3-part final summary generation."""

    def test_summary_schedule_variant_success(self):
        state: AgentState = {
            "user_request": "Schedule a meeting with Rahul tomorrow at 5 PM",
            "task_type": "schedule",
            "proposed_action": {
                "action_type": "create_calendar_event",
                "summary": "Schedule calendar event: 'Meeting with Rahul' on Tomorrow at 5 PM",
                "details": {"title": "Meeting with Rahul", "date": "Tomorrow", "time": "5 PM"},
            },
            "approval_status": "approved",
            "execution_result": {
                "status": "success",
                "result": {
                    "event": {
                        "id": "evt-123",
                        "title": "Meeting with Rahul",
                        "event_link": "https://calendar.google.com/event?eid=evt-123",
                    }
                },
            },
        }

        summary = generate_final_summary(state)
        assert "Direct scheduling" in summary["researched"]
        assert "Meeting with Rahul" in summary["planned"]
        assert "Created calendar event 'Meeting with Rahul'" in summary["done"]
        assert "https://calendar.google.com/event?eid=evt-123" in summary["done"]
        assert "Researched:" in summary["text"]
        assert "Planned:" in summary["text"]
        assert "Done:" in summary["text"]

    def test_summary_research_and_save_success(self):
        state: AgentState = {
            "user_request": "Find 2 cafes and save",
            "task_type": "research_and_save",
            "research_results": [
                {"title": "Third Wave Coffee", "source": "Search MCP"},
                {"title": "Araku Coffee", "source": "Search MCP"},
            ],
            "proposed_action": {
                "action_type": "save_note",
                "summary": "Save 2 research findings as local Markdown note to 'notes_cafes.md'",
            },
            "approval_status": "approved",
            "execution_result": {
                "status": "success",
                "result": {"filename": "notes_cafes.md", "path": "notes/notes_cafes.md"},
            },
        }

        summary = generate_final_summary(state)
        assert "Discovered 2 options" in summary["researched"]
        assert "Save 2 research findings" in summary["planned"]
        assert "Saved research findings to note file 'notes_cafes.md'" in summary["done"]

    def test_summary_empty_research_edge_case(self):
        state: AgentState = {
            "user_request": "Find obscure topic and save",
            "task_type": "research_and_save",
            "research_results": [],
            "proposed_action": {
                "action_type": "save_note",
                "summary": "Save 0 research findings as local Markdown note",
            },
            "approval_status": "approved",
            "execution_result": {
                "status": "success",
                "result": {"filename": "note.md"},
            },
        }

        summary = generate_final_summary(state)
        assert "No findings discovered" in summary["researched"]

    def test_summary_rejected_proposal_edge_case(self):
        state: AgentState = {
            "user_request": "Schedule meeting",
            "task_type": "schedule",
            "proposed_action": {
                "summary": "Schedule meeting at 5 PM",
            },
            "approval_status": "rejected",
        }

        summary = generate_final_summary(state)
        assert "rejected by user" in summary["done"]

    def test_summary_tool_failure_edge_case(self):
        state: AgentState = {
            "user_request": "Schedule meeting",
            "task_type": "schedule",
            "proposed_action": {
                "summary": "Schedule meeting at 5 PM",
            },
            "approval_status": "approved",
            "execution_result": {
                "status": "failed",
                "error": "Connection timeout to calendar provider",
                "retries_used": 1,
                "next_step": "ask_user_guidance",
            },
        }

        summary = generate_final_summary(state)
        assert "failed after 1 retry" in summary["done"]
        assert "Awaiting user guidance" in summary["done"]

    def test_final_summary_node_updates_state(self):
        state: AgentState = {
            "user_request": "Schedule call tomorrow at 10 am",
            "task_type": "schedule",
            "proposed_action": {"summary": "Schedule call tomorrow at 10 am"},
            "approval_status": "approved",
            "execution_result": {"status": "success", "result": {"event": {"title": "Call"}}},
        }
        updates = final_summary_node(state)
        assert "final_summary" in updates
        assert "researched" in updates["final_summary"]
        assert "planned" in updates["final_summary"]
        assert "done" in updates["final_summary"]
