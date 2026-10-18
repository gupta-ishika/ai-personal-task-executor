# AI Personal Task Executor

A multi-agent AI system that researches, plans, and executes small personal productivity tasks — but always pauses for human approval before taking any external action.

## What it does
Given a request like "Find a cafe for 4 people this Saturday evening, under ₹3000, and schedule it on my calendar," the system:

1. Researches the request (Research Agent + Search MCP)
2. Proposes a concrete action (Planning Agent)
3. Pauses and asks for human approval before doing anything external
4. Executes the approved action (Action Agent + Calendar/Notes MCP)
5. Returns a short summary of what was researched, planned, and done

## Tech
- LangGraph for orchestration, shared state, and checkpoint/resume
- A multi-agent architecture (Supervisor, Research, Planning, Action)
- MCP for external tool access (Search, Calendar, Notes)
- A ReAct-style tool-selection loop within agents
- Human-in-the-loop approval (`interrupt()`) before any side-effecting action

## Project Docs

### Reference Documentation (`docs/`)
See the [docs/](docs/README.md) directory for full project specifications and architectural details:
- [`docs/PRD.md`](docs/PRD.md) — what and why
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — how it's built
- [`docs/DESIGN.md`](docs/DESIGN.md) — output/interaction conventions
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — key architectural decisions and reasons
- [`docs/TEST_PLAN.md`](docs/TEST_PLAN.md) — what "working" means
- [`docs/SECURITY.md`](docs/SECURITY.md) — security requirements

### Active Workflow & Tracking (Root)
- [`main.py`](main.py) — interactive CLI runner and demo execution entrypoint
- [`RULES.md`](RULES.md) — development rules & boundaries
- [`TASKS.md`](TASKS.md) — implementation task breakdown & phases (Phases 1-15)
- [`MEMORY.md`](MEMORY.md) — current project state, component audit & next steps

## Status & Capabilities

- **Phases 1–10 Complete:** Fully implemented, live DuckDuckGo search & web scraping, human-in-the-loop verified, powered by local Ollama (`llama3.2:3b`), and passing 86 automated tests.
- **Real vs Simulated Boundaries:**
  - 🟢 **Local LLM Inference:** **100% Real** (Runs locally via Ollama `llama3.2:3b` for dynamic reasoning and synthesis).
  - 🟢 **Live Web Search & Scraping:** **100% Real** (Real DuckDuckGo web search via `ddgs`, live HTTP scraping with `requests` + `BeautifulSoup`, keyword relevance scoring, and prompt injection defense).
  - 🟢 **Notes Persistence:** **100% Real** (Saves formatted `.md` Markdown files to `./notes/`).
  - 🟢 **LangGraph Pipeline:** **100% Real** (State routing, ReAct loop, interrupt pause, human approval/rejection).
  - 🟡 **Calendar MCP:** **In-Memory Simulation** (Stores events in Python RAM during process execution; disk persistence and `.ics` export scheduled for Phase 12).
  - 🟡 **Session Memory:** **In-Memory** (`MemorySaver()`; persistent SQLite checkpointer scheduled for Phase 14).


## Setup & Usage

### 1. Environment Setup
```bash
# Copy placeholder env variables
copy env.example .env.local

# Activate virtual environment
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Running the Project
```bash
# Interactive CLI menu
python main.py

# Run Primary Demo (Research + Plan + Approve + Schedule)
python main.py --demo

# Run Re-planning Demo (Reject first proposal -> Re-plan alternative -> Approve)
python main.py --demo-replan

# Run custom task with auto-approval
python main.py --request "Schedule a meeting with Rahul tomorrow at 5 PM" --auto-approve
```

### 3. Running Tests
```bash
pytest
```
