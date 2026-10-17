"""Planning Agent for AI Personal Task Executor.

Responsible for:
1. Converting research findings and request parameters into concrete proposed action payloads:
   - 'schedule': Concrete calendar event payload (title, date, time, description)
   - 'research_and_save': Structured markdown note payload (title, filename, content)
   - 'research_and_action': Synthesized calendar event from research recommendations
2. Providing an explicit, plain-language action summary before approval.
3. Handling re-planning upon rejection by selecting alternative options.
4. Planning Agent node for LangGraph orchestration.
"""

import re
from typing import Any, Dict, List, Optional
from src.graph.state import AgentState
from src.agents.supervisor import (
    TASK_TYPE_SCHEDULE,
    TASK_TYPE_RESEARCH_AND_SAVE,
    TASK_TYPE_RESEARCH_AND_ACTION,
)


def extract_schedule_details(user_request: Optional[str]) -> Dict[str, str]:
    """Extract scheduling details (title, date, time) from a request string."""
    req = (user_request or "").strip()
    req_lower = req.lower()

    # Extract time
    time_match = re.search(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm)|evening|morning|afternoon|night)\b", req_lower)
    time_str = time_match.group(1).upper() if time_match else "18:00"

    # Extract date hints
    date_match = re.search(
        r"\b(today|tomorrow|this\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|weekend)|next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|saturday|sunday|monday|tuesday|wednesday|thursday|friday)\b",
        req_lower,
    )
    date_str = date_match.group(1).title() if date_match else "Tomorrow"

    # Extract meeting title/purpose
    title = "Personal Productivity Task"
    if "meeting with" in req_lower:
        match = re.search(r"meeting\s+with\s+([a-zA-Z0-9\s]+?)(?:\s+(?:tomorrow|today|at|on|this)|$)", req, re.IGNORECASE)
        if match:
            title = f"Meeting with {match.group(1).strip()}"
    elif "call with" in req_lower:
        match = re.search(r"call\s+with\s+([a-zA-Z0-9\s]+?)(?:\s+(?:tomorrow|today|at|on|this)|$)", req, re.IGNORECASE)
        if match:
            title = f"Call with {match.group(1).strip()}"
    elif "appointment" in req_lower:
        match = re.search(r"([a-zA-Z\s]+appointment)", req, re.IGNORECASE)
        if match:
            title = match.group(1).strip().capitalize()
    elif "sync" in req_lower:
        match = re.search(r"([a-zA-Z0-9\s]+sync)", req, re.IGNORECASE)
        if match:
            title = match.group(1).strip().capitalize()
    else:
        title = "Scheduled Task Event"

    return {
        "title": title,
        "date": date_str,
        "time": time_str,
    }


class PlanningAgent:
    """Planning Agent that constructs explicit action payloads and handles re-planning."""

    def plan(self, state: AgentState) -> Dict[str, Any]:
        """Generate a proposed action payload based on task type and research results.

        Args:
            state: Current AgentState.

        Returns:
            Dictionary with 'proposed_action' and reset 'approval_status' ('pending').
        """
        task_type = state.get("task_type") or TASK_TYPE_RESEARCH_AND_ACTION
        user_request = state.get("user_request") or ""
        research_results = state.get("research_results") or []
        previous_action = state.get("proposed_action") or {}
        was_rejected = state.get("approval_status") == "rejected"

        current_revision = previous_action.get("revision", 1)
        next_revision = current_revision + 1 if was_rejected else 1

        # Track which alternative recommendation to select on re-planning
        option_index = (next_revision - 1) % max(len(research_results), 1)

        if task_type == TASK_TYPE_SCHEDULE:
            action_payload = self._plan_schedule(user_request, next_revision, was_rejected)
        elif task_type == TASK_TYPE_RESEARCH_AND_SAVE:
            action_payload = self._plan_research_and_save(user_request, research_results, next_revision, was_rejected)
        else:  # TASK_TYPE_RESEARCH_AND_ACTION
            action_payload = self._plan_research_and_action(
                user_request, research_results, option_index, next_revision, was_rejected
            )

        return {
            "proposed_action": action_payload,
            "approval_status": "pending",
        }

    def _plan_schedule(self, user_request: str, revision: int, was_rejected: bool) -> Dict[str, Any]:
        """Construct a calendar scheduling action payload."""
        details = extract_schedule_details(user_request)

        # On rejection, adjust time slightly as an alternative proposal
        time_slot = details["time"]
        if was_rejected:
            time_slot = f"{details['time']} (alternative 30m offset)"

        title = details["title"]
        date = details["date"]

        summary = f"Schedule calendar event: '{title}' on {date} at {time_slot}"
        if was_rejected:
            summary += " (Revised proposal following rejection)"

        return {
            "type": "create_event",
            "action_type": "create_calendar_event",
            "summary": summary,
            "revision": revision,
            "details": {
                "title": title,
                "date": date,
                "time": time_slot,
                "description": f"Scheduled via AI Personal Task Executor based on request: '{user_request}'",
            },
        }

    def _plan_research_and_save(
        self,
        user_request: str,
        research_results: List[Dict[str, Any]],
        revision: int,
        was_rejected: bool,
    ) -> Dict[str, Any]:
        """Construct a save note action payload containing research findings."""
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", user_request[:30].strip().lower()).strip("_")
        filename = f"notes_{slug or 'research'}.md"

        # Format markdown content
        content_lines = [
            f"# Research Summary: {user_request.strip()}",
            "",
            "## Discovered Options",
        ]

        if research_results:
            for idx, item in enumerate(research_results, 1):
                title = item.get("title", f"Option {idx}")
                details = item.get("details", "")
                url = item.get("url", "")
                source = item.get("source", "Search MCP")
                content_lines.append(f"### {idx}. {title}")
                if details:
                    content_lines.append(f"- Details: {details}")
                if url:
                    content_lines.append(f"- URL: {url}")
                content_lines.append(f"- Source: {source}")
                content_lines.append("")
        else:
            content_lines.append("No specific research findings discovered for this query.")
            content_lines.append("")

        content = "\n".join(content_lines)
        summary = f"Save {len(research_results)} research findings as local Markdown note to '{filename}'"
        if was_rejected:
            summary += " (Revised format following rejection)"

        return {
            "type": "save_note",
            "action_type": "save_note",
            "summary": summary,
            "revision": revision,
            "details": {
                "title": f"Research Notes: {user_request.strip()}",
                "filename": filename,
                "format": "markdown",
                "content": content,
                "item_count": len(research_results),
            },
        }

    def _plan_research_and_action(
        self,
        user_request: str,
        research_results: List[Dict[str, Any]],
        option_index: int,
        revision: int,
        was_rejected: bool,
    ) -> Dict[str, Any]:
        """Construct a calendar event action payload synthesized from research findings."""
        sched_details = extract_schedule_details(user_request)

        # Select option based on index (cycles to next alternative if rejected)
        selected_finding: Optional[Dict[str, Any]] = None
        if research_results:
            safe_idx = min(option_index, len(research_results) - 1)
            selected_finding = research_results[safe_idx]

        if selected_finding:
            finding_title = selected_finding.get("title", "Selected Venue")
            event_title = f"Visit {finding_title}"
            location = selected_finding.get("title", "")
            description = (
                f"Selected option from research: {selected_finding.get('details', '')}\n"
                f"Source: {selected_finding.get('url', selected_finding.get('source', ''))}"
            )
        else:
            event_title = sched_details["title"]
            location = "To be determined"
            description = f"Event planned based on request: '{user_request}'"

        date = sched_details["date"]
        time_slot = sched_details["time"]

        summary = f"Create calendar event: '{event_title}' on {date} at {time_slot} at {location}"
        if was_rejected:
            summary += f" (Option #{option_index + 1} revised following rejection)"

        return {
            "type": "create_event",
            "action_type": "create_calendar_event",
            "summary": summary,
            "revision": revision,
            "details": {
                "title": event_title,
                "date": date,
                "time": time_slot,
                "location": location,
                "description": description,
            },
        }


def planning_agent_node(state: AgentState) -> Dict[str, Any]:
    """Planning Agent node for LangGraph orchestration.

    Reads current state, generates concrete proposed action payload,
    resets approval_status to 'pending', and returns state updates.
    """
    agent = PlanningAgent()
    return agent.plan(state)
