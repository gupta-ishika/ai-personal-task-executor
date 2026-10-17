"""Tests for Calendar MCP client wrapper."""

import pytest
from src.mcp.calendar_mcp import CalendarMCP, list_events, create_event


class TestCalendarMCP:
    """Test suite for Calendar MCP operations."""

    def test_list_events(self):
        client = CalendarMCP()
        events = client.list_events()
        assert isinstance(events, list)
        assert len(events) >= 1
        assert "title" in events[0]
        assert "date" in events[0]

    def test_create_event_success(self):
        client = CalendarMCP()
        result = client.create_event(
            title="Team Architecture Review",
            date="Tomorrow",
            time="3:00 PM",
            location="Room A",
            description="Discuss LangGraph pipeline",
        )
        assert result["status"] == "success"
        event = result["event"]
        assert event["title"] == "Team Architecture Review"
        assert event["date"] == "Tomorrow"
        assert event["time"] == "3:00 PM"
        assert "event_link" in event
        assert event["status"] == "confirmed"

    def test_create_event_empty_title_raises_value_error(self):
        client = CalendarMCP()
        with pytest.raises(ValueError):
            client.create_event(title="", date="Tomorrow", time="18:00")

    def test_calendar_mcp_simulated_failure(self):
        client = CalendarMCP(simulate_failure_count=1)
        with pytest.raises(RuntimeError):
            client.create_event(title="Failing Meeting", date="Today", time="12:00")
        # Second call succeeds
        res = client.create_event(title="Failing Meeting", date="Today", time="12:00")
        assert res["status"] == "success"
