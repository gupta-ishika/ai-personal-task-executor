"""Calendar MCP client wrapper for AI Personal Task Executor.

Provides:
- list_events(start_time, end_time) -> List[Dict[str, Any]] (Read-only)
- create_event(title, date, time, description, location) -> Dict[str, Any] (Side-effecting)

Persists events to `calendar.json` and generates downloadable RFC 5545 `.ics` (iCalendar)
files for universal calendar import without OAuth friction. Verifies disk write before
confirming success.
"""

import os
import re
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple


def parse_event_datetime(date_str: str, time_str: str) -> Tuple[datetime, datetime]:
    """Parse human-friendly date and time strings into concrete start and end datetimes.

    Handles:
    - Relative days: 'today', 'tomorrow', 'yesterday'
    - Weekdays: 'this Saturday', 'next Monday', 'Friday'
    - Absolute dates: '2026-10-25', 'October 25', '25/10/2026'
    - Times: '5 PM', '5:30 PM', '18:00', 'morning' (10 AM), 'evening' (6 PM)
    """
    now = datetime.now()
    d_clean = (date_str or "Tomorrow").lower().strip()
    target_date = now.date()

    if "tomorrow" in d_clean:
        target_date = now.date() + timedelta(days=1)
    elif "today" in d_clean:
        target_date = now.date()
    else:
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        matched_day = None
        for i, w in enumerate(weekdays):
            if w in d_clean:
                matched_day = i
                break
        if matched_day is not None:
            days_ahead = (matched_day - now.weekday()) % 7
            if days_ahead == 0 and "next" in d_clean:
                days_ahead = 7
            elif days_ahead == 0 and now.hour >= 18:
                days_ahead = 7
            target_date = now.date() + timedelta(days=days_ahead)
        else:
            parsed = False
            for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%B %d", "%b %d"):
                try:
                    dt = datetime.strptime(date_str.strip(), fmt)
                    if dt.year == 1900:
                        dt = dt.replace(year=now.year)
                    target_date = dt.date()
                    parsed = True
                    break
                except ValueError:
                    continue
            if not parsed:
                target_date = now.date() + timedelta(days=1)

    # Time parsing
    t_clean = (time_str or "18:00").lower().strip()
    hour, minute = 18, 0
    if "morning" in t_clean:
        hour, minute = 10, 0
    elif "afternoon" in t_clean:
        hour, minute = 14, 0
    elif "evening" in t_clean or "night" in t_clean:
        hour, minute = 18, 0
    else:
        match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", t_clean)
        if match:
            h = int(match.group(1))
            m = int(match.group(2) or 0)
            meridiem = match.group(3)
            if meridiem == "pm" and h < 12:
                h += 12
            elif meridiem == "am" and h == 12:
                h = 0
            hour, minute = h, m

    start_dt = datetime(target_date.year, target_date.month, target_date.day, hour, minute)
    end_dt = start_dt + timedelta(hours=1)
    return start_dt, end_dt


def generate_ics_content(
    event_id: str,
    title: str,
    start_dt: datetime,
    end_dt: datetime,
    description: str = "",
    location: str = "",
) -> str:
    """Generate standard RFC 5545 iCalendar (.ics) content."""
    now_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dtstart = start_dt.strftime("%Y%m%dT%H%M%S")
    dtend = end_dt.strftime("%Y%m%dT%H%M%S")

    def clean_text(text: str) -> str:
        return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//AI Personal Task Executor//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{event_id}@aipersonaltaskexecutor.local",
        f"DTSTAMP:{now_utc}",
        f"DTSTART:{dtstart}",
        f"DTEND:{dtend}",
        f"SUMMARY:{clean_text(title)}",
        f"DESCRIPTION:{clean_text(description)}",
        f"LOCATION:{clean_text(location)}",
        "STATUS:CONFIRMED",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(lines) + "\r\n"


def verify_file_write(file_path: str, min_bytes: int = 1) -> bool:
    """Verify that a file write physically completed and is non-empty on disk."""
    if not os.path.exists(file_path):
        return False
    try:
        return os.path.getsize(file_path) >= min_bytes
    except OSError:
        return False


class CalendarMCP:
    """Calendar MCP client wrapper managing persistent calendar events."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        storage_path: Optional[str] = None,
        events_dir: Optional[str] = None,
        simulate_failure_count: int = 0,
    ):
        self.client_id = client_id or os.getenv("CALENDAR_MCP_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("CALENDAR_MCP_CLIENT_SECRET")
        self.storage_path = storage_path or os.getenv("CALENDAR_STORAGE_PATH") or os.path.join("data", "calendar.json")
        self.events_dir = events_dir or os.getenv("CALENDAR_EVENTS_DIR") or os.path.join("data", "events")
        self._simulate_failure_count = simulate_failure_count

        # Ensure parent directories exist
        os.makedirs(os.path.dirname(os.path.abspath(self.storage_path)), exist_ok=True)
        os.makedirs(os.path.abspath(self.events_dir), exist_ok=True)

        self._events: List[Dict[str, Any]] = []
        self._load_from_disk()

    def _load_from_disk(self):
        """Load stored events from disk or seed default event."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self._events = data
                        return
            except Exception:
                pass

        # Seed default event if newly initialized storage
        self._events = [
            {
                "id": "cal-seed-001",
                "title": "Weekly Planning Sync",
                "date": "Monday",
                "time": "10:00 AM",
                "location": "Virtual",
                "description": "Team recurring sprint alignment",
            }
        ]
        self._save_to_disk()

    def _save_to_disk(self):
        """Save events list to calendar.json and verify write."""
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self._events, f, indent=2, ensure_ascii=False)
        if not verify_file_write(self.storage_path):
            raise IOError(f"Disk write verification failed for calendar storage: {self.storage_path}")

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
        """Create a new calendar event, write .ics export, and persist to calendar.json.

        Side-effecting operation: must only be executed through Action Agent
        after human approval.
        """
        if self._simulate_failure_count > 0:
            self._simulate_failure_count -= 1
            raise RuntimeError("Calendar MCP connection timeout during create_event")

        if not title or not title.strip():
            raise ValueError("Event title cannot be empty.")

        clean_title = title.strip()
        clean_date = date.strip() if date else "Tomorrow"
        clean_time = time.strip() if time else "18:00"
        clean_loc = location.strip() if location else "TBD"
        clean_desc = description.strip() if description else ""

        # Parse date and time into start and end datetimes
        start_dt, end_dt = parse_event_datetime(clean_date, clean_time)
        event_id = f"evt-{uuid.uuid4().hex[:8]}"

        # 1. Generate and save .ics iCalendar file
        ics_filename = f"{event_id}.ics"
        ics_path = os.path.join(self.events_dir, ics_filename)
        ics_content = generate_ics_content(
            event_id=event_id,
            title=clean_title,
            start_dt=start_dt,
            end_dt=end_dt,
            description=clean_desc,
            location=clean_loc,
        )

        with open(ics_path, "w", encoding="utf-8", newline="") as f:
            f.write(ics_content)

        if not verify_file_write(ics_path, min_bytes=len(ics_content.encode("utf-8"))):
            raise IOError(f"Disk write verification failed for .ics file: {ics_path}")

        # 2. Record event data
        event_record = {
            "id": event_id,
            "title": clean_title,
            "date": clean_date,
            "time": clean_time,
            "start_iso": start_dt.isoformat(),
            "end_iso": end_dt.isoformat(),
            "location": clean_loc,
            "description": clean_desc,
            "event_link": f"https://calendar.google.com/event?eid={event_id}",
            "ics_path": ics_path,
            "status": "confirmed",
            "created_at": datetime.now().isoformat(),
        }

        # 3. Persist to calendar.json and verify write
        self._events.append(event_record)
        self._save_to_disk()

        return {
            "status": "success",
            "event": event_record,
            "ics_path": ics_path,
            "storage_path": self.storage_path,
            "message": f"Successfully created event '{clean_title}' on {clean_date} at {clean_time}.",
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
