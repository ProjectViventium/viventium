# Scheduling Cortex (Selective Consciousness Continuity)

**Purpose**: Single source of truth for the Scheduling Cortex. This path adds lightweight,
scalable scheduling with no UI changes, built as an MCP server with a persistent scheduler loop.

## Executive Summary

We will implement a dedicated Scheduling MCP server that:
- stores per-user scheduled tasks in SQLite
- exposes CRUD + search tools to the main agent only
- runs a background scheduler loop that triggers prompts on time
- dispatches through existing LibreChat and Telegram routes

## Requirements

### Functional
1. No UI changes.
2. Main agent only creates schedules.
3. Per-user isolation.
4. CRUD + search for scheduled tasks.
5. Support LibreChat, Telegram, or both.
6. Task payload includes prompt, agent id, time, pattern, created source, and channels.
7. Default to a new conversation per run unless explicitly configured otherwise.
8. Non-blocking scheduler.
9. No external API additions.
10. Auto-injected context should provide user identity and the main agent id.

### Non-Functional
- Lightweight and scalable.
- Reliable scheduling with misfire handling.
- Easy deployment.

## Public-Safe Policy Notes

- The main agent parses natural language into structured schedule objects.
- The MCP server validates and stores schedules.
- Keep schedule naming, reminders, and delivery content generic and user-safe.
- Avoid private-contact examples in the public contract.
- List/search browsing must be summary-safe. Ordinary schedule browsing is not a license to expose
  full internal prompts, generated delivery prose, or raw delivery payloads to other answer
  surfaces.

## Dispatch Behavior

### LibreChat Channel
- Scheduler generation is canonical.
- Runs should flow through the existing scheduler-authenticated internal routes.
- Conversation policy can be `new` or `same`.

### Telegram Channel
- Scheduled Telegram delivery should reuse the canonical scheduler-generated final/follow-up text.
- Do not start a second agent run through the Telegram chat route just for scheduled tasks.

## Summary-Safe Browsing Contract

Default schedule browsing tools such as `schedule_list` and `schedule_search` should return summary
fields only:

- identifiers
- schedule metadata
- status timestamps
- delivery outcome metadata
- a short human-readable summary

The following must stay out of default list/search payloads:

- full schedule prompt text
- `last_generated_text`
- raw `last_delivery` payloads

Detailed inspection belongs to explicit detail tools such as `schedule_get` or
`schedule_last_delivery`, not routine browsing surfaces that may be pulled into ordinary answering
context.
