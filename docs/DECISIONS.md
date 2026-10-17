# Architecture Decisions

## ADR-001

Decision:
Use LangGraph for orchestration.

Reason:
Gives the project real state management, conditional routing, and checkpoint/resume — needed to pause the graph at the approval gate and resume after the user responds.

## ADR-002

Decision:
Use a multi-agent architecture (Supervisor, Research, Planning, Action) instead of one monolithic agent.

Reason:
Keeps each agent's responsibility narrow and easy to reason about, and demonstrates a real multi-agent design rather than a single prompt doing everything.

## ADR-003

Decision:
Use MCP for all external tool access (search, calendar, notes) instead of calling APIs directly from agent code.

Reason:
Keeps tool access consistent and swappable, and is the integration pattern the project is meant to demonstrate.

## ADR-004

Decision:
Limit MCP servers to Search, Calendar, and optionally Notes.

Reason:
Enough to demonstrate the full research → plan → approve → act pipeline without the integration surface sprawling (no Gmail, Slack, WhatsApp, booking APIs, etc.).

## ADR-005

Decision:
Treat all three task types (schedule, research & save, research→action) as variants of one pipeline rather than separate workflows. "Create something" was dropped from scope since it had no matching MCP integration (it implied email, which isn't in scope).

Reason:
Keeps the implementation to a single, well-tested graph shape instead of several different architectures, and keeps every task type backed by a real MCP tool.

## ADR-006

Decision:
Require human approval only immediately before a side-effecting tool call, not before every step.

Reason:
Research and planning are reversible and low-risk; interrupting there would add friction without reducing risk. This keeps `interrupt()` meaningful rather than a formality.

## ADR-007

Decision:
Add explicit failure handling (retry once, then ask the user) to the MVP scope. "Alternative tool" was dropped since the current MCP set has no real alternative for a given action (e.g. there's only one way to create a calendar event).

Reason:
Without it, any tool failure would crash the graph, which undermines the point of demonstrating a robust agent pipeline. Keeping it to retry/ask keeps the implementation honest to what actually exists.

## ADR-008

Decision:
Use a keyword-scoped ReAct loop (reason → tool call → observe → repeat until sufficient) rather than a general autonomous reasoning framework.

Reason:
Demonstrates the ReAct pattern without building unnecessary complexity into an MVP.

## ADR-009

Decision:
Integrate local Ollama (`llama3.2:3b`) for dynamic agent reasoning while preserving fast, deterministic rule-based fallbacks for unit test runs.

Reason:
Paid cloud API keys (OpenAI/Anthropic) introduce friction, costs, and external network dependencies. Leveraging local Ollama gives genuine generative reasoning (natural task classification, research synthesis, rich Markdown reports, and conversational summaries) completely free and private, while automatic detection of `PYTEST_CURRENT_TEST` ensures all automated tests run in seconds without flake or external requirements.

## ADR-010

Decision:
Implement MCP clients as in-process Python wrappers initially rather than external daemon processes running over stdio / Streamable HTTP.

Reason:
Permits testing the core LangGraph multi-agent coordination, human approval gate, and side-effecting tool boundaries without the operational overhead of running multi-process IPC daemons during early development. External stdio / Streamable HTTP MCP server processes are staged for Phase 15.

## ADR-011

Decision:
Persist notes to real disk storage immediately (`./notes/*.md`), while keeping calendar operations in-memory for the MVP baseline before adding file-based `.ics`/`calendar.json` persistence.

Reason:
Notes persist structured research output directly into the workspace where users can inspect markdown files immediately. Calendar event disk persistence and iCalendar `.ics` export are scheduled as a dedicated step (Phase 12) prior to full Google OAuth integration (Phase 13).
