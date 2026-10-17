"""MCP client wrappers package."""

from src.mcp.search_mcp import SearchMCP, search, fetch_page
from src.mcp.calendar_mcp import CalendarMCP, list_events, create_event
from src.mcp.notes_mcp import NotesMCP, save_note

__all__ = [
    "SearchMCP",
    "search",
    "fetch_page",
    "CalendarMCP",
    "list_events",
    "create_event",
    "NotesMCP",
    "save_note",
]
