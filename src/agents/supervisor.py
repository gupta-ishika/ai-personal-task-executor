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


# Schedule idioms where "find" refers to finding open slots/calendar time rather than web research
FIND_TIME_PATTERNS = [
    r"\bfind\s+(?:me\s+)?(?:a\s+)?(?:free\s+)?(?:\d+[-\s]*(?:min|minute|hour)\s+)?(?:slot|time|opening|window)\b",
    r"\bfind\s+time\s+to\b",
]

# Negative action constraints where calendar scheduling is explicitly negated/forbidden
NEGATIVE_CALENDAR_PATTERNS = [
    r"\b(?:don'?t|do\s+not|never|without)\s+(?:schedule|book|put|add)\b",
    r"\b(?:no\s+need\s+to\s+schedule|not\s+on\s+(?:my\s+)?calendar)\b",
]

# Calendar as a research subject/topic rather than an action destination
CALENDAR_AS_TOPIC_PATTERNS = [
    r"\b(?:history|origin|evolution|concept|about)\s+(?:of\s+)?(?:the\s+)?(?:\w+\s+)?calendar\b",
    r"\bcalendar\s+(?:app|software|system|history|features?|types?)\b",
]

# References to earlier research findings in multi-turn conversations
EARLIER_RESEARCH_REF_PATTERNS = [
    r"\b(?:first|second|third|1st|2nd|3rd)\s+(?:one|option|venue|cafe|choice|recommendation)\b",
    r"\b(?:from\s+)?earlier\s+research\b",
    r"\bprevious\s+option\b",
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

    has_find_time = any(re.search(pat, req) for pat in FIND_TIME_PATTERNS)
    has_negative_calendar = any(re.search(pat, req) for pat in NEGATIVE_CALENDAR_PATTERNS)
    is_calendar_topic = any(re.search(pat, req) for pat in CALENDAR_AS_TOPIC_PATTERNS)
    is_earlier_ref = any(re.search(pat, req) for pat in EARLIER_RESEARCH_REF_PATTERNS)

    has_research = any(re.search(pat, req) for pat in RESEARCH_PATTERNS)
    has_action = any(re.search(pat, req) for pat in ACTION_PATTERNS)
    has_calendar_action = any(re.search(pat, req) for pat in CALENDAR_ACTION_PATTERNS)
    has_save = any(re.search(pat, req) for pat in SAVE_PATTERNS)

    # Disambiguate tricky edge cases
    if has_find_time:
        has_research = False
        has_action = True
        has_calendar_action = True

    if has_negative_calendar:
        has_action = False
        has_calendar_action = False

    if is_calendar_topic and not any(re.search(pat, req) for pat in DATETIME_PATTERNS):
        has_action = False
        has_calendar_action = False

    if is_earlier_ref and has_action:
        # Refers to earlier findings without asking to perform a new search
        has_research = False

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
        "You are an intent classifier for a personal assistant. "
        "Classify the following user request into exactly ONE of these three task types:\n\n"
        "- 'schedule': Direct calendar event or meeting scheduling without needing web research.\n"
        "  (Includes finding a time slot, booking a meeting, adding an event, or scheduling a venue from earlier conversation)\n\n"
        "- 'research_and_save': Researching information, comparing options, or looking up topics, and saving or presenting notes.\n"
        "  (Includes researching history of calendars, comparing products, or when the user says not to schedule anything)\n\n"
        "- 'research_and_action': First performing external web research to find options, AND THEN scheduling a selected option on the calendar.\n"
        "  (Example: 'Find 3 Italian restaurants and book a table for Saturday 8 PM')\n\n"
        f"Request: \"{user_request}\"\n\n"
        "Respond with ONLY the exact task type string: 'schedule', 'research_and_save', or 'research_and_action'."
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
