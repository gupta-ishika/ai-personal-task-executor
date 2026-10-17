# Test Plan

## Supervisor / Routing
- Correctly classifies each of the three task-type variants
- Routes to Research → Planning → Action in the right order
- Unrecognized/ambiguous requests are handled gracefully (not crashed)

## Research Agent
- Returns structured findings for a valid query
- ReAct loop stops once sufficient information is gathered (doesn't loop forever)
- Handles empty/no-results case without crashing

## Planning Agent
- Produces a concrete, explicit action payload (not vague text) for each task-type variant
- Re-plans correctly when the previous proposal is rejected

## Human-in-the-Loop Approval
- Graph pauses (`interrupt()`) immediately before any side-effecting tool call
- No side-effecting tool executes without an approval step having occurred
- Approve path proceeds to execution
- Reject path returns to the Planning Agent, not execution
- Read-only tools (search, list events) never trigger an approval pause

## Action Agent
- Executes the approved action correctly via the right MCP tool
- On tool failure: retries once, then asks the user — does not crash the graph
- Does not execute any action that wasn't explicitly approved
- Approval payload integrity: the action actually executed matches, field for field, the payload shown to and approved by the user

## Checkpoint / Resume
- Graph state is preserved across the `interrupt()` pause
- Graph resumes correctly with the user's approval decision after a delay

## End-to-End
- Full "Research → Plan → Approval → Action" demo flow (e.g. find a cafe, approve, create calendar event) completes successfully
- Full flow with rejection at the approval step re-plans and re-prompts correctly
- Full flow with a simulated tool failure recovers per the failure-handling rule

## Responsive / Environment
Not applicable for v1 (no graphical frontend in scope).
