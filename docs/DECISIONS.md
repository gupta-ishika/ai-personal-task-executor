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
