# Architecture

## Language & Runtime
Python

## Orchestration
LangGraph — manages agent routing, shared state, conditional edges, and checkpoint/resume across the `interrupt()` for human approval.

## Interface
Simple CLI/chat-based interface for the MVP (a request goes in as text, a summary comes out as text). No web frontend in scope for v1.

## Agents

**Supervisor**
- Understands the incoming request
- Determines the task type (schedule / research & save / research→action)
- Routes to the appropriate agents in sequence

**Research Agent**
- Gathers external information using the Search MCP tools
- Runs a ReAct-style loop: reason about whether more information is needed, call a tool, observe the result, repeat until sufficient
- Returns structured findings to the graph state

**Planning Agent**
- Converts findings into a concrete proposed action (an explicit action payload, not vague text)
- Hands the proposed action to the approval gate

**Action Agent**
- Receives the approved action payload only
- Selects the MCP tool that corresponds to that exact payload — it cannot modify the payload or invent a different action
- Executes it and returns the result
- On failure, retries once; if it still fails, asks the user for guidance

## MCP Servers

**Search MCP**
- `search()`
- `fetch_page()`

**Calendar MCP**
- `list_events()`
- `create_event()`

**Notes MCP (optional)**
- `save_note()`

No other integrations are in scope for v1.

## Human-in-the-Loop Boundary
All side-effecting operations pass through a single approval boundary. Read-only tools (search, fetch, list events) run freely. Any tool that creates, modifies, or deletes something external triggers a LangGraph `interrupt()` before it runs.

```
Search MCP           → allowed, no interruption
Read Calendar         → allowed, no interruption
Create Calendar Event → 🚨 interrupt before this
                          ↓
                     Human approval
                          ↓
                     create_event()
```

## Shared State (`AgentState`)

- `user_request`
- `task_type`
- `research_results`
- `proposed_action`
- `approval_status`
- `execution_result`
- `final_summary`
- `error`

## Graph Flow

```
user_request
     ↓
  Supervisor
     ↓
[Research Agent if needed] → research_results
     ↓
Planning Agent → proposed_action
     ↓
interrupt() → approval_status
     ├── reject → back to Planning Agent
     └── approve
             ↓
        Action Agent → execution_result (or error → retry/ask)
             ↓
        Final Summary
```

## Folder Structure

```
main.py                 # Interactive CLI runner
src/
├── agents/
│   ├── supervisor.py
│   ├── research_agent.py
│   ├── planning_agent.py
│   └── action_agent.py
├── mcp/
│   ├── search_mcp.py
│   ├── calendar_mcp.py
│   └── notes_mcp.py
├── graph/
│   ├── state.py
│   ├── graph.py
│   ├── approval.py
│   └── summary.py
├── services/
└── utils/
```

## Architectural Rules
- Agents should not call MCP tools directly outside their defined responsibility (e.g. the Planning Agent never calls an execution tool).
- All side-effecting tool calls go through the Action Agent, and only after approval.
- Business/agent logic stays out of the MCP tool wrappers; wrappers only handle the external call.
- Graph state is the single source of truth passed between agents — agents don't hold their own hidden state.
