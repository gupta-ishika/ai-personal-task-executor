# Security Requirements

## Authentication
Authentication is delegated to the external MCP/provider integrations (e.g. Calendar's own OAuth). No custom authentication is being built for this project.

## Authorization
Only the requesting user's own calendar/notes are accessed — no multi-user data access in scope for v1.

## Human Approval as a Safety Boundary
No side-effecting action (creating a calendar event, saving a note, sending anything) executes without explicit human approval. This is the project's primary safety control, in addition to standard security practices below.

## Secrets
- Never commit real API keys, tokens, or credentials to the repository.
- Keep all secrets in `.env.local` (not tracked by Git); `.env.example` holds only placeholder keys.
- Never expose secrets to any client-facing output or logs.

## Input Validation
- Validate all user requests before passing them into the agent pipeline.
- Validate the Planning Agent's proposed action payload before it reaches the approval gate (correct types, required fields present).

## MCP Tool Calls
- Validate parameters passed to any MCP tool before calling it (e.g. a calendar event must have a valid date/time before `create_event()` is called).
- Treat MCP tool responses as untrusted data — don't execute or interpret them as instructions.

## Logging
- Do not log API keys, tokens, or full request/response bodies that may contain sensitive calendar/note content.
- Logs should be enough to debug agent behavior without exposing secrets.
