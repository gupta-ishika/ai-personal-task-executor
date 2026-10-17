"""AgentState definition for LangGraph orchestration."""

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    """Shared state passed between agents in the graph.

    Fields defined according to docs/ARCHITECTURE.md:
    - user_request: Raw input string from the user
    - task_type: Classified task variant ('schedule', 'research_and_save', 'research_and_action')
    - research_results: Structured findings from research agent
    - proposed_action: Concrete action payload created by planning agent
    - approval_status: Current human approval status ('pending', 'approved', 'rejected')
    - execution_result: Output from action agent execution
    - error: Any error message encountered during execution or planning
    """

    user_request: str
    task_type: Optional[str]
    research_results: Optional[List[Dict[str, Any]]]
    proposed_action: Optional[Dict[str, Any]]
    approval_status: Optional[str]
    execution_result: Optional[Dict[str, Any]]
    error: Optional[str]
