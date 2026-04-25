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
- Reliable scheduling with explicit misfire handling.
- Easy deployment.
- Truthful live-data handling: scheduled prompts must not guess fresh external facts such as
  weather, news, markets, or web facts. If no verified tool/cortex result is available for a
  requested live section, the generated user-visible answer should omit that section instead of
  inventing a degraded placeholder or advice.

## Public-Safe Policy Notes

- The main agent parses natural language into structured schedule objects.
- The MCP server validates and stores schedules.
- Keep schedule naming, reminders, and delivery content generic and user-safe.
- Avoid private-contact examples in the public contract.
- List/search browsing must be summary-safe. Ordinary schedule browsing is not a license to expose
  full internal prompts, generated delivery prose, or raw delivery payloads to other answer
  surfaces.

## Misfire And Catch-Up Contract

The scheduler is a local runtime loop, so it must handle host sleep, restart, and long pauses
without silently dropping user-facing reminders.

- A task is a misfire when it is due but first processed after `SCHEDULER_MISFIRE_GRACE_S`
  seconds. The default grace is 900 seconds.
- User-created one-time reminders default to catch-up delivery when they are late but still inside
  the catch-up window. The default catch-up window is 12 hours, controlled by
  `SCHEDULER_CATCH_UP_MAX_LATE_S`, with a hard cap of 24 hours.
- Catch-up eligibility is based only on structured task fields: `created_source == "user"` and
  `schedule.type == "once"`, unless explicit `metadata.misfire_policy` overrides it. Runtime code
  must not inspect prompt text, reminder wording, agent names, or other human-facing labels.
- `metadata.misfire_policy.mode` may be `catch_up` or `strict`. `skip`, `miss`, and `missed` are
  treated as `strict`. `metadata.misfire_policy.max_late_s` may narrow or extend the per-task
  window up to the hard cap.
- Recurring tasks, heartbeat tasks, and system/agent-created tasks default to strict misfire
  handling so a sleeping host does not spam stale runs when it wakes.
- A catch-up delivery must be visibly honest. The dispatch layer prepends a deterministic notice to
  delivered text, for example: `Late reminder: originally scheduled for 2026-02-13 19:00 UTC;
  delivered 85 minutes late.`
- If a task is missed instead of caught up, the delivery ledger must still be populated. Missed
  rows record `last_delivery_outcome=missed`, a structured reason such as
  `misfire_grace_exceeded` or `catch_up_window_exceeded`, `last_delivery_at`, and a
  `last_delivery` payload with due time, local due label, late seconds, and policy details.
- Exact wall-clock delivery while the Mac is asleep is not guaranteed by this MCP alone. That would
  require a separate wake-scheduling or cloud-dispatch design.

## Dispatch Behavior

### LibreChat Channel
- Scheduler generation is canonical.
- Runs should flow through the existing scheduler-authenticated internal routes.
- Conversation policy can be `new` or `same`.

### Telegram Channel
- Scheduled Telegram delivery should reuse the canonical scheduler-generated final/follow-up text.
- Do not start a second agent run through the Telegram chat route just for scheduled tasks.
- Scheduled Telegram delivery must classify transport/runtime fallback separately from
  model-generated content. If a model or background cortex guesses at a live fact, the correct fix is
  the scheduled prompt/source-of-truth truthfulness contract, not a Telegram text filter.
- Scheduler follow-up polling must pass the originating `scheduleId` into the LibreChat cortex-state
  endpoint. The cortex fallback helper uses that structured schedule context to suppress the generic
  "couldn't finish" text for scheduled runs instead of sending it to Telegram.
- When a scheduled run can only surface deferred fallback text, the cortex-state endpoint must expose
  structured provenance (`canonicalTextSource`, `canonicalTextFallbackReason`). Delivery ledgers must
  record this as `fallback_delivered` or `suppressed` with the fallback reason, not as ordinary
  `sent/delivered`.

Current owning implementation points:

- `viventium/MCPs/scheduling-cortex/scheduling_cortex/dispatch.py:30` injects the default scheduled
  self-prompt contract, including the rule that live external facts require verified tool/cortex
  evidence and should otherwise be omitted.
- `api/server/services/viventium/cortexFallbackText.js:74` suppresses the generic deferred fallback
  sentence when a structured `scheduleId` is present.
- `api/server/services/viventium/cortexMessageState.js:214` returns empty scheduled fallback text with
  `deferred_fallback` / `empty_deferred_response` provenance when no usable insight exists.
- `api/server/routes/viventium/scheduler.js:563` and
  `api/server/routes/viventium/telegram.js:1259` thread the query `scheduleId` into cortex-state
  recovery.
- `viventium/MCPs/scheduling-cortex/scheduling_cortex/dispatch.py:1213` sends `scheduleId` during
  scheduler polling, and `dispatch.py:1298` converts deferred fallback provenance into either
  canonical fallback text or a suppressed fallback reason.
- `viventium/MCPs/scheduling-cortex/scheduling_cortex/dispatch.py:1901` and `dispatch.py:2235`
  classify suppressed/degraded fallback visibility separately from ordinary delivery.
- `viventium/MCPs/scheduling-cortex/scheduling_cortex/scheduler.py:29` and `scheduler.py:231` persist
  deferred fallback degradation metadata while preserving compatible scheduler success semantics.
- `viventium/MCPs/scheduling-cortex/scheduling_cortex/scheduler.py` resolves structured misfire
  policy, catches up eligible user-created one-time reminders, and writes delivery ledgers for
  missed tasks.
- `viventium/MCPs/scheduling-cortex/scheduling_cortex/dispatch.py` prepends the deterministic late
  reminder notice on visible catch-up deliveries and carries `late_delivery` metadata into channel
  delivery details.

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
