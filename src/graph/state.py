"""AgentState definition for LangGraph orchestration."""

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


LIFECYCLE_PROPOSED = "proposed"
LIFECYCLE_APPROVED = "approved"
LIFECYCLE_REJECTED = "rejected"
LIFECYCLE_EXECUTING = "executing"
LIFECYCLE_COMPLETED = "completed"
LIFECYCLE_FAILED = "failed"

VALID_LIFECYCLE_STATES = {
    LIFECYCLE_PROPOSED,
    LIFECYCLE_APPROVED,
    LIFECYCLE_REJECTED,
    LIFECYCLE_EXECUTING,
    LIFECYCLE_COMPLETED,
    LIFECYCLE_FAILED,
}


class AgentState(TypedDict, total=False):
    """Shared state passed between agents in the graph.

    Fields defined according to docs/ARCHITECTURE.md:
    - user_request: Raw input string from the user
    - task_type: Classified task variant ('schedule', 'research_and_save', 'research_and_action')
    - research_results: Structured findings from research agent
    - proposed_action: Concrete action payload created by planning agent
    - approval_status: Current human approval status ('pending', 'approved', 'rejected')
    - action_lifecycle: Current lifecycle state ('proposed', 'approved', 'rejected', 'executing', 'completed', 'failed')
    - approved_action_payload: Snapshot of the exact action payload approved by the human
    - execution_result: Output from action agent execution
    - error: Any error message encountered during execution or planning
    """

    user_request: str
    task_type: Optional[str]
    research_results: Optional[List[Dict[str, Any]]]
    proposed_action: Optional[Dict[str, Any]]
    approval_status: Optional[str]
    action_lifecycle: Optional[str]
    approved_action_payload: Optional[Dict[str, Any]]
    execution_result: Optional[Dict[str, Any]]
    final_summary: Optional[Dict[str, Any]]
    error: Optional[str]
    user_feedback: Optional[str]
    conversation_history: Optional[List[Dict[str, Any]]]
