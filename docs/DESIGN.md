# Design System

This project is primarily a backend/agent system with a text-based (CLI/chat) interface for the MVP, so "design" here covers output conventions rather than visual UI.

## Tone
Clear, direct, minimal — no filler text between steps.

## Output Conventions

**Research output**
- Short list of findings, each with the source
- No raw dumps of search results

**Proposed action (shown before approval)**
- Plain-language summary of what will happen
- The exact action payload (e.g. event title, date, time, attendees) shown explicitly, not implied

**Approval prompt**
- Always phrased as a clear yes/no decision: Approve / Reject
- Never bundled with unrelated information

**Execution result**
- Success: confirm what was done and any relevant reference (e.g. event link)
- Failure: state what failed, what was tried, and what happens next (retry / ask user)

**Final summary**
- Three parts: what was researched, what was planned, what was done
- Kept to a few lines — not a full transcript replay

## States to Handle
- Empty research results (no findings found)
- Pending approval (waiting on user)
- Rejected (returning to planning)
- Execution failure (retry / ask)
- Successful completion

## Future UI (out of scope for MVP)
If a graphical interface is added later, it should surface the same four states above (research → proposal → approval → result) rather than introducing new interaction patterns.
