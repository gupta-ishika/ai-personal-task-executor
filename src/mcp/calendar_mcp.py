"""Calendar MCP client wrapper for AI Personal Task Executor.

Provides:
- list_events(start_time, end_time) -> List[Dict[str, Any]] (Read-only)
- create_event(title, date, time, description, location) -> Dict[str, Any] (Side-effecting)

Adheres to:
- PRD.md & ARCHITECTURE.md: MCP tool access for calendar integration.
- RULES.md: Side-effecting operations only execute via Action Agent after human approval.
"""

import os
import uuid
from typing import Any, Dict, List, Optional


class CalendarMCP:
    """Calendar MCP client wrapper managing calendar events."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        simulate_failure_count: int = 0,
    ):
        self.client_id = client_id or os.getenv("CALENDAR_MCP_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("CALENDAR_MCP_CLIENT_SECRET")
        self._events: List[Dict[str, Any]] = [
            {
                "id": "cal-seed-001",
                "title": "Weekly Planning Sync",
                "date": "Monday",
                "time": "10:00 AM",
                "location": "Virtual",
                "description": "Team recurring sprint alignment",
            }
        ]
        self._simulate_failure_count = simulate_failure_count

    def list_events(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List calendar events within an optional time range.

        Read-only operation: safe to call without human approval.
        """
        return list(self._events)

    def create_event(
        self,
        title: str,
        date: str,
        time: str,
        description: Optional[str] = "",
        location: Optional[str] = "",
    ) -> Dict[str, Any]:
        """Create a new calendar event.

        Side-effecting operation: must only be executed through Action Agent
        after human approval.
        """
        if self._simulate_failure_count > 0:
            self._simulate_failure_count -= 1
            raise RuntimeError("Calendar MCP connection timeout during create_event")

        if not title or not title.strip():
            raise ValueError("Event title cannot be empty.")

        event_id = f"evt-{uuid.uuid4().hex[:8]}"
        event_record = {
            "id": event_id,
            "title": title.strip(),
            "date": date.strip() if date else "Tomorrow",
            "time": time.strip() if time else "18:00",
            "location": location.strip() if location else "TBD",
            "description": description.strip() if description else "",
            "event_link": f"https://calendar.google.com/event?eid={event_id}",
            "status": "confirmed",
        }

        self._events.append(event_record)
        return {
            "status": "success",
            "event": event_record,
            "message": f"Successfully created event '{title.strip()}' on {date} at {time}.",
        }


# Default module-level client
_default_calendar_client = CalendarMCP()


def list_events(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Module-level list_events helper."""
    return _default_calendar_client.list_events(start_time=start_time, end_time=end_time)


def create_event(
    title: str,
    date: str,
    time: str,
    description: Optional[str] = "",
    location: Optional[str] = "",
) -> Dict[str, Any]:
    """Module-level create_event helper."""
    return _default_calendar_client.create_event(
        title=title,
        date=date,
        time=time,
        description=description,
        location=location,
    )
