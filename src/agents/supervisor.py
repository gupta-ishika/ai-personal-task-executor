"""Supervisor agent for AI Personal Task Executor.

Responsible for:
1. Request parsing and task-type classification into one of the three MVP variants:
   - 'schedule': Direct scheduling without prior research required
   - 'research_and_save': Researching information and saving as a local note
   - 'research_and_action': Researching and performing an external calendar action
2. Graceful fallback for unrecognized/ambiguous requests without crashing
3. Supervisor node for LangGraph orchestration
"""

import re
from typing import Any, Dict, List, Optional
from src.graph.state import AgentState

TASK_TYPE_SCHEDULE = "schedule"
TASK_TYPE_RESEARCH_AND_SAVE = "research_and_save"
TASK_TYPE_RESEARCH_AND_ACTION = "research_and_action"

VALID_TASK_TYPES = {
    TASK_TYPE_SCHEDULE,
    TASK_TYPE_RESEARCH_AND_SAVE,
    TASK_TYPE_RESEARCH_AND_ACTION,
}

DEFAULT_TASK_TYPE = TASK_TYPE_RESEARCH_AND_ACTION

# Research intent keywords
RESEARCH_PATTERNS = [
    r"\bfind\b",
    r"\bsearch\b",
    r"\bresearch\b",
    r"\blook\s*up\b",
    r"\bexplore\b",
    r"\brecommend(ation)?s?\b",
    r"\bcompare\b",
    r"\boptions?\b",
    r"\bwhere\s+can\s+i\b",
    r"\bwhat\s+(is|are)\b",
    r"\btop\s+\d+\b",
]

# Action / calendar intent keywords
ACTION_PATTERNS = [
    r"\bschedule\b",
    r"\bcalendar\b",
    r"\bmeeting\b",
    r"\bappointment\b",
    r"\bevent\b",
    r"\binvite\b",
    r"\bremind(er)?\b",
    r"\bput\s+on\s+(my\s+)?calendar\b",
    r"\badd\s+to\s+(my\s+)?calendar\b",
    r"\bbook\b",
    r"\breserve\b",
    r"\bcall\b",
]

# Save / note intent keywords
SAVE_PATTERNS = [
    r"\bsave\b",
    r"\bnote\b",
    r"\bnotes\b",
    r"\bwrite\s+down\b",
    r"\brecord\b",
    r"\bstore\b",
    r"\blist\b",
]

# Temporal expression hints
DATETIME_PATTERNS = [
    r"\b(today|tomorrow|yesterday)\b",
    r"\b(this|next)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday|weekend|week|month)\b",
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b",
    r"\b(morning|afternoon|evening|night)\b",
]

CALENDAR_ACTION_PATTERNS = [
    r"\bschedule\b",
    r"\bcalendar\b",
    r"\bappointment\b",
    r"\binvite\b",
    r"\bput\s+on\s+(my\s+)?calendar\b",
    r"\badd\s+to\s+(my\s+)?calendar\b",
    r"\bbook\b",
    r"\breserve\b",
]


def classify_task_type(user_request: Optional[str]) -> str:
    """Classify the user request into one of the three task-type variants.

    Args:
        user_request: The raw user input string.

    Returns:
        One of 'schedule', 'research_and_save', or 'research_and_action'.
        Defaults gracefully to 'research_and_action' if unrecognized or ambiguous.
    """
    if not user_request or not isinstance(user_request, str):
        return DEFAULT_TASK_TYPE

    req = user_request.strip().lower()
    if not req:
        return DEFAULT_TASK_TYPE

    has_research = any(re.search(pat, req) for pat in RESEARCH_PATTERNS)
    has_action = any(re.search(pat, req) for pat in ACTION_PATTERNS)
    has_calendar_action = any(re.search(pat, req) for pat in CALENDAR_ACTION_PATTERNS)
    has_save = any(re.search(pat, req) for pat in SAVE_PATTERNS)

    # 1. Research + Action (e.g., "Find a cafe ... and schedule it on my calendar")
    if has_research and has_action:
        return TASK_TYPE_RESEARCH_AND_ACTION

    # 2. Save note intent without explicit calendar scheduling
    if has_save and not has_calendar_action:
        return TASK_TYPE_RESEARCH_AND_SAVE

    # 3. Action without research (e.g., "Schedule a meeting with Rahul tomorrow at 5 PM")
    if has_action and not has_research:
        return TASK_TYPE_SCHEDULE

    # 4. Research only (e.g., "Find 3 good cafes in Indiranagar")
    if has_research:
        return TASK_TYPE_RESEARCH_AND_SAVE

    # Fallback gracefully for unrecognized/ambiguous requests
    return DEFAULT_TASK_TYPE


def parse_user_request(user_request: Optional[str]) -> Dict[str, Any]:
    """Parse raw user request and extract intent flags and metadata hints.

    Args:
        user_request: Raw request string from user.

    Returns:
        Structured dictionary with task_type, intent flags, and extracted hints.
    """
    req = (user_request or "").strip()
    req_lower = req.lower()

    task_type = classify_task_type(req)

    datetime_hints: List[str] = []
    for pat in DATETIME_PATTERNS:
        for match in re.finditer(pat, req_lower):
            datetime_hints.append(match.group(0))

    return {
        "raw_request": req,
        "task_type": task_type,
        "is_empty": len(req) == 0,
        "datetime_hints": list(set(datetime_hints)),
    }


from src.utils.llm import is_ollama_available, query_ollama


def classify_task_with_llm(user_request: str) -> Optional[str]:
    """Classify user request using local Ollama model if available."""
    if not is_ollama_available():
        return None
    prompt = (
        "Classify the following user request into one of these exact three task types:\n"
        "- 'schedule': Direct calendar event scheduling without needing prior research\n"
        "- 'research_and_save': Researching information and saving as notes/file\n"
        "- 'research_and_action': Researching options first and then scheduling on calendar\n\n"
        f"Request: \"{user_request}\"\n"
        "Return ONLY the task type name."
    )
    ans = query_ollama(prompt=prompt, timeout=10.0)
    if ans:
        ans_clean = ans.strip().lower().replace("'", "").replace('"', "")
        for valid in VALID_TASK_TYPES:
            if valid in ans_clean:
                return valid
    return None


def supervisor_node(state: AgentState) -> Dict[str, Any]:
    """Supervisor agent node for LangGraph workflow.

    Classifies the user request and routes into the graph state.
    Preserves explicitly pre-configured valid task_type if already provided.
    Does not crash on missing, invalid, or ambiguous input.
    """
    existing_type = state.get("task_type")
    if existing_type in VALID_TASK_TYPES:
        return {"task_type": existing_type}

    user_request = state.get("user_request")
    parsed = parse_user_request(user_request)
    task_type = parsed["task_type"]

    # If heuristic hit generic fallback, try LLM classification if available
    if task_type == DEFAULT_TASK_TYPE and user_request and len(user_request.strip()) > 8:
        llm_type = classify_task_with_llm(user_request)
        if llm_type:
            task_type = llm_type

    updates: Dict[str, Any] = {"task_type": task_type}

    if parsed["is_empty"] and not state.get("error"):
        updates["error"] = "Empty or missing user_request"

    return updates
