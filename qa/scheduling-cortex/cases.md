# Scheduling Cortex QA Cases

## Case ID Convention

Use stable `SCHED-NNN` IDs for scheduling cortex cases.

## Case Catalog

| Case ID | Requirement | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- |
| `SCHED-001` | Create/update existing schedule | Browser/Telegram scheduling, Scheduling Cortex MCP | test_scheduling_mcp_supervision.py plus user-surface QA | NOT YET RUN (cataloged 2026-05-17; run when feature changes) |
| `SCHED-002` | Trigger and delivery ledger | Scheduler trigger, delivery ledger, visible notification/chat | test_scheduling_mcp_supervision.py | FAIL 2026-05-24 ([report](../memory-hardening/reports/2026-05-24-nightly-routines-health-review.md)); local-prod due rows were stale while a dev-env scheduler answered the shared health port |
| `SCHED-003` | Auth/runtime failure copy | CLI/status, chat/tool failure copy | test_preflight.py or focused scheduler check | NOT YET RUN (cataloged 2026-05-17; run when feature changes) |

## `SCHED-001` - Create/update existing schedule

- Requirement: Create/update existing schedule.
- Risk covered: Viventium claims the behavior works without proving the real user-visible surface and supporting state.
- Preconditions: local runtime or focused harness is available with synthetic public-safe data.
- Steps:
  1. Through the scheduling surface, create or update a synthetic reminder; verify visible confirmation, persisted schedule state, and no duplicate when updating existing briefing-style schedules.
  2. Compare visible result with source/config, logs or persisted state summary, and the owning requirement doc.
  3. Save a public-safe dated report under `reports/` using the standard run-report template.
- Expected result: visible behavior, supporting evidence, and documentation agree.
- Forbidden result: mocks, backend logs, source inspection, or model output are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, state/log summary, and public-safety review.
- Automation: test_scheduling_mcp_supervision.py plus user-surface QA.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## `SCHED-002` - Trigger and delivery ledger

- Requirement: Trigger and delivery ledger.
- Risk covered: Viventium claims the behavior works without proving the real user-visible surface and supporting state.
- Preconditions: local runtime or focused harness is available with synthetic public-safe data.
- Steps:
  1. Run or simulate a due schedule; verify visible delivery or `{NTA}` suppression, ledger state, and final wording does not contradict tool state.
  2. Compare visible result with source/config, logs or persisted state summary, and the owning requirement doc.
  3. Save a public-safe dated report under `reports/` using the standard run-report template.
- Expected result: visible behavior, supporting evidence, and documentation agree.
- Forbidden result: mocks, backend logs, source inspection, or model output are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, state/log summary, and public-safety review.
- Automation: test_scheduling_mcp_supervision.py.
- Last run: FAIL 2026-05-24
  ([report](../memory-hardening/reports/2026-05-24-nightly-routines-health-review.md)); local-prod
  scheduled rows were overdue/stale and the live scheduler health endpoint was served by a dev-env
  scheduler attached to a different DB.

## `SCHED-003` - Auth/runtime failure copy

- Requirement: Auth/runtime failure copy.
- Risk covered: Viventium claims the behavior works without proving the real user-visible surface and supporting state.
- Preconditions: local runtime or focused harness is available with synthetic public-safe data.
- Steps:
  1. Disable or block the scheduler endpoint in a local-safe way; verify status/error copy identifies scheduler unavailability rather than claiming completion.
  2. Compare visible result with source/config, logs or persisted state summary, and the owning requirement doc.
  3. Save a public-safe dated report under `reports/` using the standard run-report template.
- Expected result: visible behavior, supporting evidence, and documentation agree.
- Forbidden result: mocks, backend logs, source inspection, or model output are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, state/log summary, and public-safety review.
- Automation: test_preflight.py or focused scheduler check.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Scheduling Cortex. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `SCHED-UC-001` | On Browser/Telegram scheduling, Scheduling Cortex MCP, verify that create/update existing schedule. | owning requirement for `SCHED-001` / `SCHED-001` | Browser/Telegram scheduling, Scheduling Cortex MCP | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to SCHED-001. | The visible result for SCHED-001 matches the documented requirement. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `SCHED-UC-002` | On Scheduler trigger, delivery ledger, visible notification/chat, try trigger and delivery ledger with missing setup, missing auth/config, empty state, or a degraded dependency. | owning requirement for `SCHED-002` / `SCHED-002` | Scheduler trigger, delivery ledger, visible notification/chat | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to SCHED-002. | The user sees an honest setup, retry, or degraded-state result for SCHED-002; no fake success is accepted. | FAIL 2026-05-24 ([report](../memory-hardening/reports/2026-05-24-nightly-routines-health-review.md)); due rows did not advance in local-prod scheduler DB |
| `SCHED-UC-003` | After auth/runtime failure copy, refresh, restart, retry, or switch linked surfaces and verify persistence/parity. | owning requirement for `SCHED-003` / `SCHED-003` | CLI/status, chat/tool failure copy | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to SCHED-003. | SCHED-003 remains correct after the persistence or parity step and final wording matches evidence. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
