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