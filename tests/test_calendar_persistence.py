"""Tests for Calendar persistence, .ics generation, payload integrity, and disk write validation.

Covers:
1. Event persistence to calendar.json across process/client restarts.
2. Standard RFC 5545 iCalendar (.ics) generation and formatting.
3. Action lifecycle states progression: proposed -> approved -> completed (or rejected / failed).
4. Approved-payload integrity verification: prevents execution of tampered payloads.
5. Disk write physical validation before confirming success.
"""

import os
import json
import shutil
import pytest
from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver

from src.mcp.calendar_mcp import (
    CalendarMCP,
    parse_event_datetime,
    generate_ics_content,
    verify_file_write,
)
from src.agents.action_agent import ActionAgent
from src.graph.graph import create_task_graph
from src.graph.state import (
    AgentState,
    LIFECYCLE_PROPOSED,
    LIFECYCLE_APPROVED,
    LIFECYCLE_REJECTED,
    LIFECYCLE_COMPLETED,
    LIFECYCLE_FAILED,
)

TEST_DIR = "test_scratch_cal_persistence"


@pytest.fixture(autouse=True)
def setup_teardown_test_dir():
    """Ensure clean test directory for persistence tests."""
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR, ignore_errors=True)
    os.makedirs(TEST_DIR, exist_ok=True)
    yield
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR, ignore_errors=True)


class TestCalendarPersistence:
    """Test calendar storage persistence and recovery."""

    def test_calendar_persists_across_client_reloads(self):
        storage_file = os.path.join(TEST_DIR, "calendar.json")
        events_dir = os.path.join(TEST_DIR, "events")

        # 1. Initialize first client instance and create 2 events
        client1 = CalendarMCP(storage_path=storage_file, events_dir=events_dir)
        initial_events_count = len(client1.list_events())

        res1 = client1.create_event(
            title="Dentist Checkup",
            date="Tomorrow",
            time="11:00 AM",
            location="Dental Clinic",
            description="Routine cleaning",
        )
        assert res1["status"] == "success"
        assert os.path.exists(storage_file)
        assert os.path.exists(res1["ics_path"])

        res2 = client1.create_event(
            title="Design Review",
            date="Friday",
            time="4:00 PM",
            location="Room 3B",
            description="Sprint 4 retrospective",
        )
        assert res2["status"] == "success"

        # 2. Simulate process exit / new process startup with fresh instance
        client2 = CalendarMCP(storage_path=storage_file, events_dir=events_dir)
        loaded_events = client2.list_events()

        # Should contain all initial seeded events + the 2 newly created events
        assert len(loaded_events) == initial_events_count + 2
        titles = [e["title"] for e in loaded_events]
        assert "Dentist Checkup" in titles
        assert "Design Review" in titles


class TestICSExport:
    """Test RFC 5545 iCalendar generation."""

    def test_ics_generation_standard_headers_and_fields(self):
        start_dt, end_dt = parse_event_datetime("Tomorrow", "5:30 PM")
        event_id = "evt-test-123"
        ics_text = generate_ics_content(
            event_id=event_id,
            title="Sprint Planning Meeting",
            start_dt=start_dt,
            end_dt=end_dt,
            description="Discuss backlog & deliverables",
            location="Virtual / Meet",
        )

        assert "BEGIN:VCALENDAR" in ics_text
        assert "VERSION:2.0" in ics_text
        assert "PRODID:-//AI Personal Task Executor//EN" in ics_text
        assert "CALSCALE:GREGORIAN" in ics_text
        assert "BEGIN:VEVENT" in ics_text
        assert f"UID:{event_id}@aipersonaltaskexecutor.local" in ics_text
        assert "DTSTART:" in ics_text
        assert "DTEND:" in ics_text
        assert "SUMMARY:Sprint Planning Meeting" in ics_text
        assert "LOCATION:Virtual / Meet" in ics_text
        assert "STATUS:CONFIRMED" in ics_text
        assert "END:VEVENT" in ics_text
        assert "END:VCALENDAR" in ics_text

    def test_verify_file_write_helper(self):
        non_existent = os.path.join(TEST_DIR, "non_existent.txt")
        assert verify_file_write(non_existent) is False

        sample_file = os.path.join(TEST_DIR, "sample.txt")
        with open(sample_file, "w", encoding="utf-8") as f:
            f.write("test content")

        assert verify_file_write(sample_file, min_bytes=5) is True
        assert verify_file_write(sample_file, min_bytes=500) is False


class TestActionLifecycleAndPayloadIntegrity:
    """Test action lifecycle state progression and tamper detection."""

    def test_lifecycle_state_progression_in_graph(self):
        checkpointer = MemorySaver()
        graph = create_task_graph(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": "test-lifecycle-1"}}

        # Start task
        graph.invoke({
            "user_request": "Schedule a meeting with Rahul tomorrow at 5 PM",
            "task_type": None,
            "approval_status": "pending",
        }, config=config)

        # Paused at approval node -> verify state was 'proposed'
        state_pause = graph.get_state(config)
        assert state_pause.next and state_pause.next[0] == "approval_node"
        assert state_pause.values.get("action_lifecycle") == LIFECYCLE_PROPOSED

        # Resume with rejection
        graph.invoke(Command(resume="rejected"), config=config)
        state_replan = graph.get_state(config)
        # Upon rejection, it routes to planning_agent which re-proposes an alternative
        assert state_replan.next and state_replan.next[0] == "approval_node"
        assert state_replan.values.get("action_lifecycle") == LIFECYCLE_PROPOSED

        # Resume with approval
        graph.invoke(Command(resume="approved"), config=config)
        state_final = graph.get_state(config)
        # Should complete and reach final state with LIFECYCLE_COMPLETED
        assert state_final.values.get("action_lifecycle") == LIFECYCLE_COMPLETED
        assert state_final.values.get("approval_status") == "approved"
        assert state_final.values.get("execution_result", {}).get("status") == "success"

    def test_approved_payload_tamper_detection(self):
        """Action Agent must detect and reject any tampering of the approved payload."""
        agent = ActionAgent()

        original_action = {
            "action_type": "create_calendar_event",
            "summary": "Schedule meeting with Rahul",
            "details": {
                "title": "Meeting with Rahul",
                "date": "Tomorrow",
                "time": "5 PM",
                "location": "Office",
            },
        }

        # Simulate tamper: proposed_action has time altered after approval
        tampered_action = {
            "action_type": "create_calendar_event",
            "summary": "Schedule meeting with Rahul",
            "details": {
                "title": "Meeting with Rahul",
                "date": "Tomorrow",
                "time": "11:00 PM (TAMPERED)",
                "location": "Office",
            },
        }

        state: AgentState = {
            "approval_status": "approved",
            "action_lifecycle": LIFECYCLE_APPROVED,
            "approved_action_payload": original_action,
            "proposed_action": tampered_action,
        }

        result = agent.execute(state)
        assert result["execution_result"]["status"] == "failed"
        assert result["action_lifecycle"] == LIFECYCLE_FAILED
        assert "Approved payload mismatch" in result["execution_result"]["error"]

    def test_disk_write_validation_failure_handling(self, monkeypatch):
        """Simulate disk write failure to verify ActionAgent reports failure."""
        storage_file = os.path.join(TEST_DIR, "calendar.json")
        events_dir = os.path.join(TEST_DIR, "events")
        cal_client = CalendarMCP(storage_path=storage_file, events_dir=events_dir)
        agent = ActionAgent(calendar_client=cal_client)

        # Monkeypatch verify_file_write to return False
        monkeypatch.setattr("src.mcp.calendar_mcp.verify_file_write", lambda path, min_bytes=1: False)

        action = {
            "action_type": "create_calendar_event",
            "details": {
                "title": "Disk Failure Test",
                "date": "Tomorrow",
                "time": "10:00 AM",
            },
        }

        state: AgentState = {
            "approval_status": "approved",
            "action_lifecycle": LIFECYCLE_APPROVED,
            "approved_action_payload": action,
            "proposed_action": action,
        }

        output = agent.execute(state)
        assert output["execution_result"]["status"] == "failed"
        assert output["action_lifecycle"] == LIFECYCLE_FAILED
        assert "Disk write verification failed" in output["execution_result"]["error"]
