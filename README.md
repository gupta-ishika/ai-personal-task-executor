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
- [`RULES.md`](RULES.md) — development rules & boundaries
- [`TASKS.md`](TASKS.md) — implementation task breakdown & phases
- [`MEMORY.md`](MEMORY.md) — current project state & next steps

## Status
All phases (1 through 8) completed. Fully implemented, human-in-the-loop verified, and passing 76 automated tests. See [`MEMORY.md`](MEMORY.md) for project status.

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
