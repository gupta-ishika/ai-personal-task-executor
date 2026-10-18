# Tasks

## Phase 1: Setup
- [x] Initialize project
- [x] Configure Python environment and dependencies (LangGraph, MCP client libs)
- [x] Configure Git
- [x] Set up `.env.example` and local `.env`

## Phase 2: Shared State & Graph Skeleton
- [x] Define `AgentState`
- [x] Build the base LangGraph graph with placeholder nodes
- [x] Wire up checkpointing so the graph can pause and resume

## Phase 3: Supervisor Agent
- [x] Implement request parsing and task-type classification
- [x] Route to Research → Planning → Action in sequence
- [x] Test routing for all three task-type variants

## Phase 4: Research Agent + Search MCP
- [x] Implement Search MCP (`search()`, `fetch_page()`)
- [x] Implement Research Agent's ReAct-style tool loop
- [x] Return structured findings into state
- [x] Add tests

## Phase 5: Planning Agent
- [x] Convert research findings into a concrete proposed action payload
- [x] Handle all three task-type variants (schedule, save note, research→action)
- [x] Add tests

## Phase 6: Human-in-the-Loop Approval
- [x] Implement `interrupt()` before any side-effecting tool call
- [x] Implement Approve/Reject handling
- [x] On reject, route back to Planning Agent
- [x] Add tests for approve and reject paths

## Phase 7: Action Agent + Calendar/Notes MCP
- [x] Implement Calendar MCP (`list_events()`, `create_event()`)
- [x] Implement Notes MCP (`save_note()`) if in scope
- [x] Implement Action Agent execution logic
- [x] Add failure handling (retry, then ask user)
- [x] Add tests, including simulated tool failure

## Phase 8: Final Summary & Polish
- [x] Implement end-of-run summary (researched / planned / done)
- [x] Handle empty-research and other edge-case states from docs/DESIGN.md
- [x] Implement interactive CLI runner (`main.py`) with demo and re-planning modes
- [x] Run full test suite across all three task-type variants
- [x] Update MEMORY.md with final project state

## Phase 9: Local LLM Integration (Ollama llama3.2:3b)
- [x] Detect downloaded Ollama models (`llama3.2:3b`)
- [x] Build `src/utils/llm.py` integration client with automatic offline fallback
- [x] Wire `llama3.2:3b` into Supervisor classification for complex requests
- [x] Wire `llama3.2:3b` into Research Agent for dynamic search synthesis on unindexed topics
- [x] Wire `llama3.2:3b` into Planning Agent for AI Executive Analysis note generation
- [x] Wire `llama3.2:3b` into Final Summary for conversational executive summaries
- [x] Verify complete test suite (76/76 passing in ~4s) and live CLI run

## Phase 10: Live Web Search & Scraping (Highest Priority)
- [x] Replace mock index with real live web search (DuckDuckGo Search via `duckduckgo-search` / `ddgs` or Tavily API)
- [x] Replace hardcoded `fetch_page()` with live HTTP fetching and clean HTML extraction (`requests` + `beautifulsoup4`)
- [x] Implement relevance scoring: filter candidate results by keyword/token overlap against user criteria before selection
- [x] Handle invalid URLs, HTTP errors, network timeouts, and unsupported MIME types gracefully without crashing
- [x] Implement honest failure handling: Never fabricate results; return an explicit "Search yielded no results" if queries fail
- [x] Treat scraped web text as untrusted (prompt injection defense before feeding to agent planning)
- [x] Keep source URLs in state for full citation traceability
- [x] Add unit test suite with mocks covering: provider errors/timeouts, rate limits, and adversarial prompt injection ("ignore instructions and do X")

## Phase 11: Interactive Continuous Chat Mode (REPL) & Routing Evals
- [x] Add interactive conversation loop in `main.py` with a stable session thread ID
- [x] Support back-and-forth task clarification, multi-turn plan revisions, and sequential task requests
- [x] Add test for multi-turn conversational follow-ups referencing earlier research results
- [x] Add Supervisor evaluation test suite with tricky user requests to catch classification drift in `llama3.2:3b`
- [x] Add CLI commands: `/help`, `/exit`, `/history`, and `/status`

## Phase 12: Persistent Calendar Storage & iCal (.ics) Export (Quick Win)
- [ ] Persist scheduled events to a local `calendar.json` file so events survive process restarts
- [ ] Generate downloadable `.ics` (iCalendar) files for immediate import into Google, Apple, or Outlook Calendar without OAuth friction
- [ ] Track clear action lifecycle states in `AgentState` (`proposed`, `approved`, `rejected`, `executing`, `completed`, `failed`)
- [ ] Verify approved-payload match: ensure Action Agent only executes the exact approved payload
- [ ] Verify the file write succeeded on disk before reporting execution success
- [ ] Add tests for calendar persistence, `.ics` generation, payload integrity, and disk write validation

## Phase 13: Real Google Calendar API Integration (OAuth 2.0)
- [ ] Implement Google Calendar v3 API client with `google-auth-oauthlib` (`credentials.json` / `token.json`)
- [ ] Handle OAuth token expiration, permission errors, API timeouts, and failed event creation
- [ ] Verify Google Calendar API response status before reporting execution success
- [ ] Add approved-payload test for real Google Calendar API requests
- [ ] Add idempotency check: prevent duplicate event creation when resuming or retrying an action
- [ ] Fall back gracefully to local `.ics` export if Google credentials are not configured

## Phase 14: Persistent SQLite LangGraph Checkpointer
- [ ] Replace in-memory `MemorySaver` with `SqliteSaver` in `main.py`
- [ ] Persist session threads and interrupt states into a local SQLite DB (`task_state.db`)
- [ ] Add recovery test verifying that an action that succeeded externally before a crash/interrupt is not re-executed upon restart

## Phase 15: True External MCP Server Subprocess Architecture (Optional)
- [ ] Refactor Python tool wrappers into true external MCP servers running over `stdio` / `Streamable HTTP`
- [ ] Connect using official `@modelcontextprotocol/sdk` client if full MCP specification compliance is needed