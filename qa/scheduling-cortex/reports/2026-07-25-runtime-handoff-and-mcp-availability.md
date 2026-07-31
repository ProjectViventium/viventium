# Scheduling Cortex Runtime Handoff And MCP Availability - 2026-07-25

## Summary

- Result: `PASS-AUTOMATED/PARTIAL-LIVE`
- Scope: existing-user upgrade handoff, scheduler process ownership, durable schedules DB, and
  live MCP availability
- Source under test: local universal-upgrade candidate
- Public/private boundary: this report contains only synthetic inputs, counts, hashes-as-equality
  conclusions, and sanitized runtime observations

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `SCHED-017` | `PASS-AUTOMATED/PARTIAL-LIVE` | Real renamed-component listener, foreign listener, SQLite preservation, live health, and MCP protocol | Signed-in browser refresh and new delivery remain unrun. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `SCHED-UC-004` | Start local prod while a prior same-database scheduler owns the port. | Local scheduler process, CLI status, and MCP client | `PASS/PARTIAL` | CLI displayed the scheduler and its 12 active / 27 total ledger summary. | Matching health identity, real MCP initialize/10-tool list, process scope, SQLite bytes, and `quick_check`. | Signed-in MCP card refresh was not run. |
| `SCHED-UC-007` | Promote a checkout while an installed or source scheduler is running or starting. | Synthetic real process/port plus supported activation stop contract | `PASS-AUTOMATED` | Stop closes the exact matching port and fails loud after complete cleanup when it cannot. | Renamed-root, helper-selected source, pre-bind, surviving-listener, foreign-identity, and DB-preservation regressions. | None for the automated ownership contract. |
| `SCHED-UC-008` | Create a schedule and observe its next delivery after promotion. | Not run | `PARTIAL` | No new delivery is claimed. | Existing DB is healthy and preserved. | Create, trigger, observe delivery, and inspect ledger. |

## Root Cause

An installed scheduler could still be listening after activation renamed its component into a
rollback slot. The stop routine returned early when the original component paths and PID file were
absent, then required the stable installed directory to exist before trying that lexical process
scope. A same-database process could therefore escape stop, later lose dependable imports, and
conflict with the promoted runtime.

The red `scheduling-cortex - Unavailable` component is a related visible symptom but a distinct
state: LibreChat renders it when the active MCP configuration map omits a server persisted on the
agent. The current generated and backend configuration include `scheduling-cortex`; a post-promotion
browser refresh remains the visible acceptance gate.

## Fix

- Probe the scheduler port even when both component directories and the PID file are absent.
- Preserve a mismatched healthy listener untouched; an identity-empty listener never triggers
  cross-scope broadening.
- After canonical schedules-DB identity matches, try the selected, declared source, and stable
  installed lexical scopes without requiring those directories to exist.
- Wait for bounded socket release, then flag any survivor without returning nonzero inside a
  `set -e` cleanup path. Complete managed cleanup and fail the outer stop before activation can
  publish.
- Do not write or replace the schedules DB during ownership transfer.

## Evidence

| Surface | Result | Evidence |
| --- | --- | --- |
| Escaped upgrade shape | `PASS` | A real synthetic scheduler started from an installed component, then that root was renamed and its PID file omitted. |
| Matching identity | `PASS` | The identity-bound stop closed the real listener after the original installed path disappeared and when helper mode selected installed while the process belonged to source. |
| Foreign identity | `PASS` | A real listener with a different DB hash remained alive and untouched. |
| Schedule durability | `PASS` | Exact SQLite bytes remained unchanged and `PRAGMA quick_check` returned `ok`. |
| Surviving listener | `PASS` | A deterministic no-op stop records failure, reaches a trailing teardown marker under `set -e`, and leaves the outer stop able to fail publication. |
| Live service identity | `PASS` | Current `/health` reports `status=ok`, `service=scheduling-cortex`, and the canonical schedules-DB hash. |
| Live MCP protocol | `PASS` | A real client initialized protocol `2025-11-25` and listed 10 scheduling tools. |
| Existing ledger | `PASS/PARTIAL` | SQLite is healthy with 12 active / 27 total tasks; the latest stored delivery failure remains truthful historical ledger state. |
| Visible LibreChat MCP state | `PARTIAL` | Generated/backend config contains the server; post-fix signed-in browser expansion and refresh have not yet run. |
| New schedule delivery | `PARTIAL` | No new user-visible schedule was created or delivered during this repair. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> gap`

- Feature: Scheduling Cortex across existing-user upgrades.
- Requirement: runtime health identity and rename-safe upgrade stop in
  `docs/requirements_and_learnings/11_Scheduling_Cortex.md`.
- Use case: promote a source checkout while an installed same-database scheduler owns the port.
- QA case: `SCHED-017`.
- Expected: drain the matching process, preserve foreign runtimes, preserve schedule data, and make
  MCP tools available from the promoted runtime.
- Actual: real renamed-component and foreign-process tests pass; live health and MCP protocol pass.
- Gap: signed-in browser expansion/refresh and a new visible schedule delivery are still required.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Scheduling Cortex runtime identity; `SCHED-UC-004`, `SCHED-UC-007`, `SCHED-UC-008`; `SCHED-017`. |
| Code owning path | Which code path owns the behavior? | Launcher scheduler stop, runtime activation stop-before-publish, and scheduler health identity. |
| Docs and nested docs/repos | Which docs define the expected behavior? | Scheduling Cortex, installer/config compiler, stable runtime, runtime QA map, and this case catalog. |
| Scripts or harnesses | Which harnesses exercised it? | Release test harness, real synthetic HTTP listener, SQLite fixture, real MCP client, and CLI status. |
| Local/external prerequisite state | Which prerequisites were proven healthy or degraded? | Local scheduler and Mongo-backed core were reachable; Prompt Workbench was currently reachable, while the latest historical schedule row still records its prior outage. |
| Logs | Which sanitized logs confirm or contradict the result? | Historical renamed-component import failure and identity conflict were inspected; current watchdog added no new conflict after restart. |
| DB/state/persistence | Which state proves it? | 12 active / 27 total tasks, exact synthetic SQLite bytes, and `PRAGMA quick_check=ok`. |
| Generated/shipped artifact | Which generated or installed artifact was inspected? | Current generated MCP config contains `scheduling-cortex`; the helper-installed component and source scopes are both covered. |
| Real user path | Which real surface was used? | Local CLI status and a real MCP initialize/`list_tools` exchange against the running scheduler. |
| Visual/UX comparison | Does visible UX match supporting evidence? | CLI status matches ledger truth; signed-in LibreChat MCP-card refresh remains unrun. |
| Not run / blocked | Which required surface was not run? | Signed-in MCP detail/refresh and a newly created schedule delivery; result remains `PARTIAL-LIVE`. |

## User-Grade Evidence

- Surface exercised: local Scheduler MCP/tool endpoint and Viventium CLI status.
- Real user path: inspected the running scheduler through status, then initialized its real MCP
  transport and listed its tools.
- Visible outcome: CLI showed Scheduler with 12 active / 27 total tasks and the stored last-delivery
  issue; no false service-down result was inferred from that historical ledger state.
- Expanded/detail state: MCP initialization returned the scheduler server identity and 10 tools;
  health carried the canonical DB identity.
- Persistence/reload result: the current scheduler restarted with the same canonical schedules DB;
  synthetic rename and foreign-identity processes preserved exact DB bytes.
- Local/external prerequisite state: scheduler, core API, and Prompt Workbench endpoints were
  reachable during the live probe.
- Evidence retrieval classification, if applicable: not applicable; this is local scheduler
  ownership and MCP availability, not external evidence retrieval.
- Fallback path, if applicable: no browser/computer/local-delegation fallback replaces the unrun
  signed-in MCP-card check.
- Backend/log/DB confirmation: current health identity, MCP result, 12/27 ledger counts, historical
  ownership logs, and SQLite `quick_check` agree.
- Final model/runtime wording check: the report distinguishes a healthy MCP from a stored delivery
  failure and does not call the visible/browser path complete.
- Substitution check: logs, DB rows, API responses, source inspection, model review, and unit tests
  support the finding but are not substitutes for the remaining signed-in UI and delivered-schedule
  user paths.

## Automated Evidence

```text
Scheduler-focused: 16 passed, 1 skipped
Full Telegram suite: 346 passed
Full release suite: 1,993 passed, 11 skipped
Shell syntax and diff checks: pass
```

## Findings

- Defects: renamed-component listener escape, helper-selected source ownership, `set -e` cleanup
  truncation, socket-release race, and pre-bind PID gaps were fixed.
- Regressions: no focused scheduler, stable-runtime, helper, CLI-upgrade, or Telegram regression.
- Flakes: none observed in repeated focused runs.
- Environment issues: signed-in browser state was unavailable.
- Residual risks: visible MCP-card refresh and a new schedule delivery remain required.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
