# Project Documentation

This directory contains the reference specifications, architecture definitions, and design decisions for the **AI Personal Task Executor**.

## Contents

- [**PRD.md**](PRD.md) — Problem statement, target user, core MVP scope, out-of-scope boundaries, and success criteria.
- [**ARCHITECTURE.md**](ARCHITECTURE.md) — Technical stack (LangGraph, Python), multi-agent roles (Supervisor, Research, Planning, Action), MCP server integration, shared state schema (`AgentState`), and folder layout.
- [**DESIGN.md**](DESIGN.md) — Output conventions, approval prompt format, state transitions, and user interaction design.
- [**DECISIONS.md**](DECISIONS.md) — Architectural Decision Records (ADRs) explaining technical tradeoffs and rationales.
- [**TEST_PLAN.md**](TEST_PLAN.md) — Test criteria for routing, ReAct research loop, approval gates, action execution, and error recovery.
- [**SECURITY.md**](SECURITY.md) — Human approval safety boundary, credentials handling, secret storage, and input validation requirements.

---

## Active Workflow & Tracking (Root Directory)

For active project progress, implementation tasks, and coding guidelines, refer to the files in the repository root:

- [**main.py**](../main.py) — Interactive CLI runner with demo and custom task execution.
- [**README.md**](../README.md) — Project overview and setup instructions.
- [**MEMORY.md**](../MEMORY.md) — Current implementation status, completed tasks, and next steps.
- [**TASKS.md**](../TASKS.md) — Phased task breakdown and completion tracking.
- [**RULES.md**](../RULES.md) — Architectural and development rules for coding and agent boundaries.
