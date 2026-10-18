"""Action Agent for AI Personal Task Executor.

Responsible for:
1. Executing side-effecting external tools (Calendar MCP, Notes MCP) ONLY after human approval.
2. Preserving payload integrity: executes the exact approved action payload without modifying it.
3. Explicit failure handling per RULES.md and ADR-007:
   - Retries once upon tool failure.
   - If still failing, transitions to ask-user-guidance state without crashing the graph.
4. Action Agent node for LangGraph orchestration.
"""

import os
from typing import Any, Dict, Optional
from src.graph.state import (
    AgentState,
    LIFECYCLE_EXECUTING,
    LIFECYCLE_COMPLETED,
    LIFECYCLE_FAILED,
    LIFECYCLE_REJECTED,
)
from src.mcp.calendar_mcp import create_event, CalendarMCP
from src.mcp.notes_mcp import save_note, NotesMCP

MAX_RETRIES = 1


class ActionAgent:
    """Action Agent executing approved external side-effecting operations."""

    def __init__(
        self,
        calendar_client: Optional[CalendarMCP] = None,
        notes_client: Optional[NotesMCP] = None,
        max_retries: int = MAX_RETRIES,
    ):
        self.calendar_client = calendar_client
        self.notes_client = notes_client
        self.max_retries = max_retries

    def execute(self, state: AgentState) -> Dict[str, Any]:
        """Execute the approved action payload via corresponding MCP tool.

        Args:
            state: Current AgentState.

        Returns:
            Dictionary with 'execution_result', 'action_lifecycle', and optional 'error'.

        Raises:
            PermissionError: If approval_status is not 'approved'.
        """
        approval_status = state.get("approval_status")
        if approval_status != "approved":
            return {
                "execution_result": {
                    "status": "blocked",
                    "error": "Action execution blocked: Human approval required.",
                },
                "action_lifecycle": LIFECYCLE_REJECTED,
                "error": "Human approval required before executing external action.",
            }

        proposed_action = state.get("proposed_action") or {}
        approved_payload = state.get("approved_action_payload")

        # Verify approved-payload match: ensure Action Agent only executes the exact approved payload
        if approved_payload is not None:
            appr_type = approved_payload.get("action_type") or approved_payload.get("type")
            prop_type = proposed_action.get("action_type") or proposed_action.get("type")
            if appr_type != prop_type or approved_payload.get("details") != proposed_action.get("details"):
                error_msg = "Approved payload mismatch: Action payload was modified after receiving approval."
                return {
                    "execution_result": {
                        "status": "failed",
                        "error": error_msg,
                        "action": proposed_action,
                    },
                    "action_lifecycle": LIFECYCLE_FAILED,
                    "error": error_msg,
                }

        action_type = proposed_action.get("action_type") or proposed_action.get("type", "")
        details = proposed_action.get("details", {})

        # Execute with retry logic
        last_error: Optional[Exception] = None
        retries_used = 0

        for attempt in range(self.max_retries + 1):
            try:
                if action_type in {"create_calendar_event", "create_event"}:
                    result = self._execute_calendar(details)
                elif action_type in {"save_note"}:
                    result = self._execute_note(details)
                else:
                    return {
                        "execution_result": {
                            "status": "failed",
                            "error": f"Unsupported or unknown action type: '{action_type}'",
                            "action": proposed_action,
                        },
                        "action_lifecycle": LIFECYCLE_FAILED,
                        "error": f"Unsupported action type '{action_type}'",
                    }

                # Verify file writes physically succeeded on disk before confirming success
                if "ics_path" in result and not os.path.exists(result["ics_path"]):
                    raise IOError(f"Calendar .ics export file does not exist on disk: {result['ics_path']}")
                if "storage_path" in result and not os.path.exists(result["storage_path"]):
                    raise IOError(f"Calendar JSON storage file does not exist on disk: {result['storage_path']}")
                if "path" in result and not os.path.exists(result["path"]):
                    raise IOError(f"Note file does not exist on disk: {result['path']}")

                # Success
                return {
                    "execution_result": {
                        "status": "success",
                        "retries_used": retries_used,
                        "action": proposed_action,
                        "result": result,
                    },
                    "action_lifecycle": LIFECYCLE_COMPLETED,
                }

            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries:
                    retries_used += 1
                    continue

        # If failed after retries: handle gracefully without crashing graph
        error_msg = str(last_error) if last_error else "Unknown execution error"
        return {
            "execution_result": {
                "status": "failed",
                "error": error_msg,
                "retries_used": retries_used,
                "next_step": "ask_user_guidance",
                "action": proposed_action,
                "message": f"Tool execution failed after {retries_used} retry: {error_msg}. Awaiting user guidance.",
            },
            "action_lifecycle": LIFECYCLE_FAILED,
            "error": error_msg,
        }

    def _execute_calendar(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """Call Calendar MCP create_event using exact approved payload fields."""
        title = details.get("title", "Scheduled Event")
        date = details.get("date", "Tomorrow")
        time_slot = details.get("time", "18:00")
        description = details.get("description", "")
        location = details.get("location", "")

        if self.calendar_client:
            return self.calendar_client.create_event(
                title=title,
                date=date,
                time=time_slot,
                description=description,
                location=location,
            )
        return create_event(
            title=title,
            date=date,
            time=time_slot,
            description=description,
            location=location,
        )

    def _execute_note(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """Call Notes MCP save_note using exact approved payload fields."""
        title = details.get("title", "Note")
        content = details.get("content", "")
        filename = details.get("filename", "note.md")

        if self.notes_client:
            return self.notes_client.save_note(
                title=title,
                content=content,
                filename=filename,
            )
        return save_note(
            title=title,
            content=content,
            filename=filename,
        )


def action_agent_node(state: AgentState) -> Dict[str, Any]:
    """Action Agent node for LangGraph workflow."""
    agent = ActionAgent()
    return agent.execute(state)
