# Development Rules

## General
- Use Python with type hints.
- Reuse existing agents/tools; do not duplicate logic across agents.
- Keep functions and agent nodes small and single-purpose.
- Do not modify unrelated files.

## Before Coding
- Read the relevant project documentation (docs/PRD.md, docs/ARCHITECTURE.md, docs/DECISIONS.md, MEMORY.md).
- Inspect existing implementation before adding new code.
- Reuse existing agents, MCP tool wrappers, or state fields where possible.
- Make a plan for any change that touches more than one agent or the shared state schema.

## Human-in-the-Loop (project-specific)
- No external side-effecting tool (create, modify, delete) may execute before human approval.
- Read-only tools (search, fetch, list) never require approval.
- Every side-effecting tool call goes through the Action Agent, never directly from another agent.
- The approval prompt must show the exact action payload, not a vague description.

## Agent Boundaries
- The Supervisor only routes; it does not call MCP tools itself.
- The Research Agent only reads; it never proposes or executes an action.
- The Planning Agent only proposes; it never calls an execution tool.
- The Action Agent selects the MCP tool that corresponds to the approved action payload; it cannot modify the payload or invent a different action.

## Graph & State
- All data passed between agents goes through `AgentState` — no hidden per-agent state.
- Every new capability should map to an existing state field before adding a new one.

## Failure Handling
- A failed tool call must not crash the graph.
- On failure, the Action Agent retries once; if it still fails, it asks the user — never silently drop the error.

## Testing
- Add tests for each agent's core behavior and for the approve/reject/failure paths.
- Run tests after implementation.
- Fix failing tests before continuing to the next task.

## Memory
- After completing any task from TASKS.md, update MEMORY.md: move the task to Completed, update Current Task to the next one, and note anything relevant under Known Issues or Next Step.
- Do this before moving on to the next task — MEMORY.md should always reflect the true current state, not lag behind it.

## Git
- Make small commits.
- Use descriptive commit messages.
