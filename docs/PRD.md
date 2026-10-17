# Product Requirements Document

## Product
AI Personal Task Executor (MVP)

## Problem
Handling small personal productivity tasks — finding information, making a plan, and taking an action based on it — usually means switching between search, notes, and an app (calendar, email) yourself. There's no single assistant that can research, plan, and act on your behalf while still keeping you in control of anything consequential.

## Target Users
Individuals (initially just me) who want a chat-based agent to handle personal productivity tasks that combine research with a real action, without giving up approval over that action.

## Goal
Build an AI agent that can research something, form a plan, and perform an external action (e.g. scheduling an event) — but always asks for human approval before the action is executed.

## Core Features

1. Supervisor agent that receives a task and routes it to the right sub-agents
2. Research agent (uses MCP search tools to gather information)
3. Planning agent (turns research into a concrete proposed action)
4. Action agent (executes the approved action via MCP tools)
5. Human-in-the-loop approval gate before any external action is executed
6. ReAct-style tool-selection loop within agents (reason → choose tool → execute → observe → repeat if needed)
7. LangGraph orchestration with state and checkpoint/resume support

## MVP

- Accept one productivity request at a time (text input)
- All task types use the same underlying graph structure — Research → Plan → Human Approval → Action — with task-specific stages skipped when not needed. The variants:
  - Schedule something (e.g. "Schedule a meeting with Rahul tomorrow at 5 PM") → Plan → Approval → Calendar action
  - Research & save (e.g. "Find 3 good cafes and save the options") → Research → Plan → Approval → save results as a local Markdown/JSON note
  - Research → Action (e.g. "Find a cafe for 4 people and create a calendar event after I approve") — runs the full Research → Plan → Approval → Action sequence; the primary demo flow
- Run research and planning steps without interruption
- Pause and request human approval (Approve/Reject) immediately before any external action is performed
- On approval, execute the action via MCP tools
- On rejection, re-plan instead of executing
- On tool failure during execution, the agent retries, and if it still fails, asks the user for guidance — rather than crashing
- Provide an end-of-run summary of what was done

## Out of Scope

- General-purpose assistant covering unrelated domains (email + WhatsApp + Instagram + shopping + calendar all at once)
- Full autonomous browser agent
- Full travel planner
- Voice interface
- Mobile or remote access
- More than 4 agents (Supervisor, Research, Planning, Action), or MCP integrations beyond Search, Calendar, and (optionally) Notes
- Persistent long-term memory beyond LangGraph's checkpointer
- Fully autonomous execution without approval gates

## Success Criteria

A user should be able to:

1. Give the agent a productivity request (e.g. "Find a cafe for 4 people this Saturday evening, under ₹3000, and schedule it on my calendar")
2. See the agent research and propose a plan without any interruption
3. Be shown a clear approval prompt before the calendar event (or other action) is actually created
4. Approve the action and have it executed correctly
5. Reject the action and have the agent re-plan instead of executing
6. See the agent handle a failed action attempt (retry, then ask for guidance) instead of the run crashing
7. Receive a short summary of what was researched, planned, and done at the end of the run
