"""Unit tests for multi-turn conversational workflows and interactive REPL mode.

Tests:
1. Multi-turn conversational follow-up referencing earlier research results.
2. Sequential independent tasks in the same session thread.
3. Plan revision at Human Approval Gate using explicit user feedback.
4. Conversation history and session state tracking.
5. REPL command helpers (/help, /status, /history).
"""

import io
import sys
from unittest.mock import patch
from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver

from src.graph.graph import create_task_graph
from src.agents.planning_agent import resolve_reference_from_research, apply_user_feedback
from main import execute_turn, print_help, print_status, print_history


class TestMultiTurnConversations:
    """Test multi-turn conversational flows across sequential turns."""

    def test_resolve_reference_from_research_ordinals(self):
        """Test ordinal resolution (first, second, third, 1st, 2nd, option 1...)."""
        findings = [
            {"title": "Third Wave Coffee", "details": "Great espresso", "url": "https://twc.in"},
            {"title": "Blue Tokai Coffee", "details": "Artisanal roastery", "url": "https://bluetokai.com"},
            {"title": "Matteo Coffea", "details": "Classic vibe", "url": "https://matteo.in"},
        ]

        ref1 = resolve_reference_from_research("Schedule a meeting at the first one this Saturday", findings)
        assert ref1 is not None
        assert ref1["title"] == "Third Wave Coffee"

        ref2 = resolve_reference_from_research("Book the 2nd option tomorrow at 4 PM", findings)
        assert ref2 is not None
        assert ref2["title"] == "Blue Tokai Coffee"

        ref3 = resolve_reference_from_research("Let's go to option 3 for coffee", findings)
        assert ref3 is not None
        assert ref3["title"] == "Matteo Coffea"

    def test_resolve_reference_from_research_title_substring(self):
        """Test substring title resolution from previous research."""
        findings = [
            {"title": "Third Wave Coffee Roasters", "details": "Coffee shop"},
            {"title": "Glen's Bakehouse", "details": "Bakery and cafe"},
        ]
        ref = resolve_reference_from_research("Schedule a lunch at Glen's Bakehouse tomorrow at 1 PM", findings)
        assert ref is not None
        assert ref["title"] == "Glen's Bakehouse"

    def test_apply_user_feedback_updates_time_and_date(self):
        """Test that user feedback updates scheduling time and date details."""
        details = {"title": "Team Standup", "date": "Tomorrow", "time": "10:00 AM"}

        # Update time
        updated = apply_user_feedback(details.copy(), "change time to 6:30 PM")
        assert updated["time"] == "6:30 PM"

        # Update date
        updated2 = apply_user_feedback(details.copy(), "make it this Saturday at 4 PM")
        assert "Saturday" in updated2["date"]
        assert updated2["time"] == "4 PM"

    def test_multi_turn_followup_referencing_earlier_research_end_to_end(self):
        """Turn 1: Research cafes and save notes.
        Turn 2: Follow-up request to schedule meeting at the first cafe.
        Verify: Event is scheduled with the venue and details from turn 1.
        """
        checkpointer = MemorySaver()
        graph = create_task_graph(checkpointer=checkpointer)
        thread_id = "test-session-multi-turn-1"
        config = {"configurable": {"thread_id": thread_id}}

        # --- Turn 1: Research and save note ---
        t1_input = {
            "user_request": "Find 3 good cafes in Indiranagar and save the options",
            "task_type": None,
            "approval_status": "pending",
        }
        graph.invoke(t1_input, config=config)

        # Pause at approval node and approve
        state_t1 = graph.get_state(config)
        assert state_t1.next and state_t1.next[0] == "approval_node"
        graph.invoke(Command(resume="approved"), config=config)

        final_t1 = graph.get_state(config)
        research_findings = final_t1.values.get("research_results")
        assert len(research_findings) > 0
        first_cafe_title = research_findings[0]["title"]

        # --- Turn 2: Follow-up referencing first option ---
        t2_input = {
            "user_request": "Now schedule a meeting at the first one this Saturday at 5 PM",
            "task_type": None,
            "approval_status": "pending",
            "proposed_action": None,
            "execution_result": None,
            "final_summary": None,
            "error": None,
        }
        graph.invoke(t2_input, config=config)

        # Pause at approval node for Turn 2
        state_t2 = graph.get_state(config)
        assert state_t2.next and state_t2.next[0] == "approval_node"
        proposed = state_t2.tasks[0].interrupts[0].value.get("proposed_action", {})
        details = proposed.get("details", {})

        # Verify that Turn 2 resolved the venue from Turn 1's research results
        assert first_cafe_title in details.get("title") or first_cafe_title in details.get("location")
        assert "Saturday" in details.get("date")

        # Approve and execute
        graph.invoke(Command(resume="approved"), config=config)
        final_t2 = graph.get_state(config)

        exec_res = final_t2.values.get("execution_result", {})
        assert exec_res.get("status") == "success"

        # Check history contains both turns
        history = final_t2.values.get("conversation_history", [])
        assert len(history) == 2
        assert "Find 3 good cafes" in history[0]["user_request"]
        assert "Now schedule a meeting" in history[1]["user_request"]

    def test_plan_revision_with_feedback_at_approval_gate(self):
        """Test human rejection providing specific feedback to revise proposal."""
        checkpointer = MemorySaver()
        graph = create_task_graph(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": "test-session-revision-1"}}

        # Start task
        graph.invoke({
            "user_request": "Schedule a meeting with Rahul tomorrow at 5 PM",
            "task_type": None,
            "approval_status": "pending",
        }, config=config)

        # First pause at approval gate -> reject with feedback to change time
        state_1 = graph.get_state(config)
        assert state_1.next and state_1.next[0] == "approval_node"

        graph.invoke(Command(resume={"decision": "rejected", "feedback": "Change the time to 6:30 PM"}), config=config)

        # Re-paused at approval gate with revised action
        state_2 = graph.get_state(config)
        assert state_2.next and state_2.next[0] == "approval_node"
        proposed_rev = state_2.tasks[0].interrupts[0].value.get("proposed_action", {})
        rev_details = proposed_rev.get("details", {})

        assert rev_details.get("time") == "6:30 PM"
        assert proposed_rev.get("revision") == 2

        # Now approve revised action
        graph.invoke(Command(resume="approved"), config=config)
        final_state = graph.get_state(config)
        assert final_state.values.get("execution_result", {}).get("status") == "success"

    def test_repl_command_helpers(self, capsys):
        """Test that /help, /status, and /history helpers render cleanly."""
        checkpointer = MemorySaver()
        graph = create_task_graph(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": "test-repl-helpers"}}

        # Run print_help
        print_help()
        captured = capsys.readouterr().out
        assert "/help" in captured
        assert "/history" in captured
        assert "/status" in captured
        assert "/exit" in captured

        # Run print_status before turns
        print_status(graph, config)
        captured = capsys.readouterr().out
        assert "test-repl-helpers" in captured
        assert "Total Turns Run     : 0" in captured

        # Run print_history before turns
        print_history(graph, config)
        captured = capsys.readouterr().out
        assert "No conversation turns completed yet" in captured
