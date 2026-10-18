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
from src.graph.state import AgentState, LIFECYCLE_PROPOSED
from src.agents.supervisor import (
    TASK_TYPE_SCHEDULE,
    TASK_TYPE_RESEARCH_AND_SAVE,
    TASK_TYPE_RESEARCH_AND_ACTION,
)
from src.utils.llm import is_ollama_available, llm_generate_note_content


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


def resolve_reference_from_research(
    user_request: str, research_results: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Resolve ordinal or contextual venue references to a specific item from earlier research."""
    if not research_results or not user_request:
        return None
    req = user_request.lower()

    # Ordinal matching (1st, 2nd, 3rd, first, second, third, option 1, option 2...)
    if re.search(r"\b(first|1st|option\s*1|recommendation\s*1)\b", req):
        if len(research_results) >= 1:
            return research_results[0]
    if re.search(r"\b(second|2nd|option\s*2|recommendation\s*2)\b", req):
        if len(research_results) >= 2:
            return research_results[1]
    if re.search(r"\b(third|3rd|option\s*3|recommendation\s*3)\b", req):
        if len(research_results) >= 3:
            return research_results[2]

    # Substring matching against research titles
    for item in research_results:
        title = item.get("title", "")
        if title and len(title) > 3 and title.lower() in req:
            return item

    # Contextual reference ("at the cafe", "at that venue", "at the first option", "there")
    if re.search(r"\b(?:at\s+)?(?:the\s+)?(?:cafe|restaurant|venue|place|option|choice|there)\b", req):
        return research_results[0]

    return None


def apply_user_feedback(details: Dict[str, str], user_feedback: Optional[str]) -> Dict[str, str]:
    """Update scheduling details based on explicit user feedback string."""
    if not user_feedback:
        return details
    fb_lower = user_feedback.lower()

    # Check for time updates in feedback
    time_match = re.search(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm)|evening|morning|afternoon|night)\b", fb_lower)
    if time_match:
        details["time"] = time_match.group(1).upper()

    # Check for date updates in feedback
    date_match = re.search(
        r"\b(today|tomorrow|this\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|weekend)|next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|saturday|sunday|monday|tuesday|wednesday|thursday|friday)\b",
        fb_lower,
    )
    if date_match:
        details["date"] = date_match.group(1).title()

    return details


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
        user_feedback = state.get("user_feedback")

        current_revision = previous_action.get("revision", 1)
        next_revision = current_revision + 1 if was_rejected else 1

        # Track which alternative recommendation to select on re-planning
        option_index = (next_revision - 1) % max(len(research_results), 1)

        if task_type == TASK_TYPE_SCHEDULE:
            action_payload = self._plan_schedule(
                user_request, next_revision, was_rejected, research_results=research_results, user_feedback=user_feedback
            )
        elif task_type == TASK_TYPE_RESEARCH_AND_SAVE:
            action_payload = self._plan_research_and_save(user_request, research_results, next_revision, was_rejected)
        else:  # TASK_TYPE_RESEARCH_AND_ACTION
            action_payload = self._plan_research_and_action(
                user_request, research_results, option_index, next_revision, was_rejected, user_feedback=user_feedback
            )

        return {
            "proposed_action": action_payload,
            "approval_status": "pending",
            "action_lifecycle": LIFECYCLE_PROPOSED,
            "user_feedback": None,
        }

    def _plan_schedule(
        self,
        user_request: str,
        revision: int,
        was_rejected: bool,
        research_results: Optional[List[Dict[str, Any]]] = None,
        user_feedback: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Construct a calendar scheduling action payload, resolving any earlier research references."""
        details = extract_schedule_details(user_request)

        # Check if this scheduling request references an earlier research finding
        resolved_finding = resolve_reference_from_research(user_request, research_results or [])

        if user_feedback:
            details = apply_user_feedback(details, user_feedback)
        elif was_rejected:
            details["time"] = f"{details['time']} (alternative 30m offset)"

        time_slot = details["time"]
        date = details["date"]

        if resolved_finding:
            venue_title = resolved_finding.get("title", "Selected Venue")
            location = venue_title
            if "meeting with" in user_request.lower():
                title = f"{details['title']} at {venue_title}"
            else:
                title = f"Visit {venue_title}"
            description = (
                f"Scheduled from session research findings.\n"
                f"Venue: {venue_title}\n"
                f"Details: {resolved_finding.get('details', '')}\n"
                f"Source: {resolved_finding.get('url', resolved_finding.get('source', ''))}"
            )
            summary = f"Schedule calendar event: '{title}' on {date} at {time_slot} at {location} (referencing earlier research)"
        else:
            title = details["title"]
            location = "To be determined"
            description = f"Scheduled via AI Personal Task Executor based on request: '{user_request}'"
            summary = f"Schedule calendar event: '{title}' on {date} at {time_slot}"

        if was_rejected:
            summary += f" (Revision #{revision} following feedback)"

        return {
            "type": "create_event",
            "action_type": "create_calendar_event",
            "summary": summary,
            "revision": revision,
            "details": {
                "title": title,
                "date": date,
                "time": time_slot,
                "location": location,
                "description": description,
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

        # Enhance with Ollama AI executive analysis if available
        if research_results and is_ollama_available():
            ai_analysis = llm_generate_note_content(user_request, research_results)
            if ai_analysis:
                content += "\n\n## AI Executive Analysis\n\n" + ai_analysis

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
        user_feedback: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Construct a calendar event action payload synthesized from research findings."""
        sched_details = extract_schedule_details(user_request)
        if user_feedback:
            sched_details = apply_user_feedback(sched_details, user_feedback)

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
