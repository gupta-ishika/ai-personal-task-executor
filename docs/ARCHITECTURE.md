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
- `user_feedback`
- `conversation_history`
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
    └── llm.py          # Local Ollama (llama3.2:3b) integration client
```

## Architectural Rules
- Agents should not call MCP tools directly outside their defined responsibility (e.g. the Planning Agent never calls an execution tool).
- All side-effecting tool calls go through the Action Agent, and only after approval.
- Business/agent logic stays out of the MCP tool wrappers; wrappers only handle the external call.
- Graph state is the single source of truth passed between agents — agents don't hold their own hidden state.

## Implementation Reality & Production Roadmap

### Current Implementation State
- **LLM Engine:** Local Ollama running `llama3.2:3b` via HTTP REST (`http://localhost:11434`), with automatic offline/sub-second fallback for deterministic `pytest` runs.
- **Notes Storage:** 100% real local filesystem persistence (`./notes/*.md`).
- **Calendar MCP:** Currently an in-memory client (`self._events`) with mock event IDs and URLs. Events do not persist after the CLI process terminates.
- **Search MCP:** Uses a curated local index supplemented by dynamic Ollama research synthesis. Does not make live outbound web requests or parse live HTML.
- **Session Memory:** Uses in-memory `MemorySaver()`. Conversations reset across process restarts.
- **Tool Protocol:** Implemented as in-process Python wrapper classes adhering to the MCP interface convention, rather than separate stdio / Streamable HTTP subprocess servers.

### Evolution Path to Full Production
1. **Live Web Search & Scraping:** Integrate DuckDuckGo Search / Tavily API and live HTTP scraping with prompt injection guardrails (Phase 10).
2. **Interactive REPL:** Support multi-turn conversational chat sessions in `main.py` with stable thread ID (Phase 11).
3. **Calendar Persistence & iCal (.ics) Export:** Add `calendar.json` disk storage and `.ics` export for zero-friction calendar import (Phase 12).
4. **Google Calendar API:** Implement OAuth 2.0 and Google Calendar v3 API client with approved-payload verification and idempotency (Phase 13).
5. **Persistent Checkpointer:** Migrate from `MemorySaver` to `SqliteSaver` with no-duplicate-execution tests (Phase 14).
6. **External MCP Servers:** Spawn true MCP server processes via `@modelcontextprotocol/sdk` over `stdio` / `Streamable HTTP` if full protocol compliance is desired (Phase 15 - Optional).
