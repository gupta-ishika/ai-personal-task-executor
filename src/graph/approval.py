"""Human-in-the-Loop Approval gate for AI Personal Task Executor.

Responsible for:
1. Enforcing human approval before any external side-effecting action is executed.
2. Presenting an approval prompt with the exact action payload and clear Approve/Reject decision.
3. Normalizing user approval decisions ('approved' vs 'rejected') with safe defaults.
4. Routing approved actions to Action Agent and rejected proposals back to Planning Agent.
"""

from typing import Any, Dict, Literal, Optional
from langgraph.types import interrupt
from src.graph.state import AgentState

APPROVAL_STATUS_PENDING = "pending"
APPROVAL_STATUS_APPROVED = "approved"
APPROVAL_STATUS_REJECTED = "rejected"

VALID_APPROVAL_STATUSES = {
    APPROVAL_STATUS_PENDING,
    APPROVAL_STATUS_APPROVED,
    APPROVAL_STATUS_REJECTED,
}


def build_approval_prompt(proposed_action: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Construct a clean, explicit approval interrupt payload.

    Args:
        proposed_action: The proposed action dictionary created by Planning Agent.

    Returns:
        Structured interrupt payload with prompt, action payload, and options.
    """
    action = proposed_action or {}
    summary = action.get("summary", "No action summary provided.")

    return {
        "type": "human_approval_required",
        "prompt": "Approval required before executing external action. Approve or Reject?",
        "summary": summary,
        "action_type": action.get("action_type") or action.get("type", "unknown"),
        "proposed_action": action,
        "options": ["Approve", "Reject"],
    }


def parse_approval_decision(decision: Any) -> str:
    """Parse and normalize human approval decision into 'approved' or 'rejected'.

    Safe by default: unrecognized or ambiguous responses default to 'rejected'.

    Args:
        decision: Raw decision received on resume (str, dict, bool, etc.).

    Returns:
        'approved' or 'rejected'.
    """
    if decision is None:
        return APPROVAL_STATUS_REJECTED

    if isinstance(decision, dict):
        status = (
            decision.get("approval_status")
            or decision.get("decision")
            or decision.get("action")
            or decision.get("status")
        )
        return parse_approval_decision(status)

    if isinstance(decision, bool):
        return APPROVAL_STATUS_APPROVED if decision else APPROVAL_STATUS_REJECTED

    if isinstance(decision, str):
        val = decision.strip().lower()
        if val in {"approved", "approve", "yes", "y", "confirm", "proceed", "accept"}:
            return APPROVAL_STATUS_APPROVED
        if val in {"rejected", "reject", "no", "n", "cancel", "deny", "decline"}:
            return APPROVAL_STATUS_REJECTED

    # Fallback safely to rejection if ambiguous
    return APPROVAL_STATUS_REJECTED


def approval_node(state: AgentState) -> Dict[str, Any]:
    """Human approval gate node using LangGraph interrupt.

    Pauses graph execution before any external side-effecting action.
    """
    status = state.get("approval_status")

    # If pending or unset, trigger interrupt
    if status == APPROVAL_STATUS_PENDING or not status:
        proposed_action = state.get("proposed_action")
        prompt_payload = build_approval_prompt(proposed_action)

        decision = interrupt(prompt_payload)
        status = parse_approval_decision(decision)

    return {"approval_status": status}


def route_approval(state: AgentState) -> Literal["action_agent", "planning_agent", "final_summary"]:
    """Conditional edge routing from approval gate.

    - 'approved' -> Action Agent (proceed to external action execution)
    - 'rejected' -> Planning Agent (re-plan an alternative proposal)
    - other -> Final Summary
    """
    status = state.get("approval_status")
    if status == APPROVAL_STATUS_APPROVED:
        return "action_agent"
    elif status == APPROVAL_STATUS_REJECTED:
        return "planning_agent"
    return "final_summary"
