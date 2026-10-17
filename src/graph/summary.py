"""Final Summary generation for AI Personal Task Executor.

Responsible for:
1. Generating a concise 3-part end-of-run summary:
   - Researched: What was discovered (or note of direct scheduling)
   - Planned: What was proposed (action details)
   - Done: What external action was executed or status (success, retry/fail, rejected)
2. Handling edge cases:
   - Empty or missing research results
   - Unapproved or rejected actions
   - Tool execution failures (retry / ask user)
3. Final Summary node for LangGraph orchestration.
"""

from typing import Any, Dict, List, Optional
from src.graph.state import AgentState
from src.agents.supervisor import TASK_TYPE_SCHEDULE


def generate_final_summary(state: AgentState) -> Dict[str, Any]:
    """Generate structured and text representations of the end-of-run summary.

    Args:
        state: The final state of the task execution workflow.

    Returns:
        Dictionary containing 'researched', 'planned', 'done', and combined 'text'.
    """
    task_type = state.get("task_type")
    research_results = state.get("research_results") or []
    proposed_action = state.get("proposed_action") or {}
    approval_status = state.get("approval_status")
    execution_result = state.get("execution_result") or {}
    error = state.get("error")

    # 1. Researched
    if task_type == TASK_TYPE_SCHEDULE:
        researched_text = "Direct scheduling; no prior research required."
    elif research_results:
        titles = [r.get("title", "Finding") for r in research_results[:3]]
        researched_text = f"Discovered {len(research_results)} options: {', '.join(titles)}."
    else:
        researched_text = "No findings discovered for query."

    # 2. Planned
    planned_text = proposed_action.get("summary")
    if not planned_text:
        details = proposed_action.get("details", {})
        if details.get("title"):
            planned_text = f"Proposed {details.get('title')} ({details.get('date', '')} {details.get('time', '')})."
        else:
            planned_text = "No concrete action plan was proposed."

    # 3. Done
    exec_status = execution_result.get("status")
    if exec_status == "success":
        action_type = proposed_action.get("action_type") or proposed_action.get("type", "")
        res_payload = execution_result.get("result", {})
        if "create" in action_type:
            event = res_payload.get("event", {})
            event_title = event.get("title", "Event")
            event_link = event.get("event_link", "")
            done_text = f"Created calendar event '{event_title}'" + (f" ({event_link})." if event_link else ".")
        elif "note" in action_type:
            filename = res_payload.get("filename", "note.md")
            done_text = f"Saved research findings to note file '{filename}'."
        else:
            done_text = "External action successfully executed."
    elif exec_status == "failed":
        retries = execution_result.get("retries_used", 1)
        err = execution_result.get("error") or error or "Unknown tool error"
        done_text = f"Execution failed after {retries} retry: {err}. Awaiting user guidance."
    elif exec_status == "blocked":
        done_text = "Action execution was blocked: Human approval was not granted."
    elif approval_status == "rejected":
        done_text = "Action proposal was rejected by user; no external changes were made."
    elif approval_status == "pending":
        done_text = "Execution paused: Awaiting human approval."
    else:
        done_text = "Workflow completed without external execution."

    combined_text = (
        f"Researched: {researched_text}\n"
        f"Planned: {planned_text}\n"
        f"Done: {done_text}"
    )

    return {
        "researched": researched_text,
        "planned": planned_text,
        "done": done_text,
        "text": combined_text,
    }


def final_summary_node(state: AgentState) -> Dict[str, Any]:
    """Final summary node for LangGraph workflow."""
    summary = generate_final_summary(state)
    return {"final_summary": summary}
