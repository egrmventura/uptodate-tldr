# Claude Code — Project Rules

## Token Conservation

- Do not spawn subagents unless the user explicitly asks for them or names an agent type.
- Maximum 2 parallel agents at any time.
- Prefer inline work (grep, Read, Edit) over spawning Explore agents for simple lookups.
- Do not use MCP tools (Gmail, Google Drive, Google Calendar) unless the user specifically requests them.
- Do not load deferred tool schemas unless needed for the current task.
- Keep effort level consistent with the global setting — do not escalate on your own.

## Project Context

- Python 3.12, flat layout at repo root.
- All secrets live in .env (symlinked outside repo). Never read .env contents into conversation.
- Source contract: Source.fetch(topic, config) -> list[Item], must never raise.
- LinkedIn source is disabled by default and documented as fragile.
