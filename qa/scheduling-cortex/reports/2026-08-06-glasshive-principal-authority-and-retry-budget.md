# GlassHive Principal Authority And Retry Budget QA - 2026-08-06

## Summary

- Result: **PASS automated / PARTIAL user surface**.
- Build/source under test: uncommitted public-safe GlassHive, Scheduling Cortex, Glass Drive, and
  LibreChat scheduler-bridge candidate.
- Runtime/artifact under test: local GlassHive runtime, Glass Drive UI, Scheduling Cortex source
  suites, and synthetic recurrence ledgers.
- Environment: isolated local development services with neutral tenant, principal, workspace, and
  instruction fixtures.
- Tester: delegated scheduling-hardening pass followed by primary-agent browser acceptance.
- Related change: `SCHED-020` and GlassHive `GHUCP-021`–`023`.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `SCHED-020` | PASS automated / PARTIAL hosted | GlassHive recurrence/runtime, Glass Drive, and Scheduling Cortex suites | Disablement races and bounded terminal/retry states pass; hosted admin path remains blocked. |
| `GHUCP-021` | PASS locally | Real browser create, Run now, history, pause, resume, and refresh | One recurring definition remained active after cleanup. |
| `GHUCP-022` | PASS automated | Timezone, recurrence, stale-rule, overlap, retry, and idempotency cases | Dense/sparse/month-end recurrence is bounded. |
| `GHUCP-023` | PARTIAL | Browser disconnected-account recovery plus authority/revalidation suites | Installed automatic fire with a real provider remains blocked. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `SCHED-UC-020` | Disable a principal who owns recurring work, then observe terminal and transient failures | Runtime/API suites plus Glass Drive browser recovery path | PARTIAL | A disconnected selected account showed explicit reconnect instructions and a safe-retry guarantee | Authority epoch/state, deterministic occurrence identity, terminal action-required count, and bounded retry tests passed | Hosted tenant-admin disable and installed clock fire |
| `GHUCP-UC-007` | Create recurring work, run it, inspect history, pause, resume, refresh, and restart | Glass Drive browser and local runtime | PARTIAL | One completed occurrence remained visible after restart; pause/resume and next-run copy stayed correct | One definition and one immutable completed occurrence matched DB/API/MCP state | Automatic wall-clock fire with real credentials |
| `GHUCP-UC-009` | Encounter revoked/missing account state and retry safely | Glass Drive browser | PASS locally | Recovery copy named Connections, reconnection, and Run now; it explicitly stated that no duplicate was created | Expected structured conflict; occurrence history remained one completed row | Hosted provider revocation |
| `GHUCP-UC-011` | Stage and cut over all scheduling owners without split authority | Local source/rollout harness | BLOCKED | No hosted service was changed | Single-owner metadata, definition authority, and rollout readiness contracts passed | Explicit cloud mutation approval and hosted cutover |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: GlassHive-owned recurring workspace work bridged through Scheduling Cortex.
- Requirement: principal authority, one schedule owner, fire-time revalidation, bounded retry, and
  exactly-once occurrence identity in Requirement 55 and the scheduling requirements.
- Use case: a user schedules a saved workspace; disablement blocks future work; reconnectable
  account failure is actionable and safe to retry.
- QA case: `SCHED-020`, `GHUCP-021`, `GHUCP-022`, and `GHUCP-023`.
- Expected result: no disabled-user fire, no ordinary-task collateral disablement, one deterministic
  occurrence, immediate terminal action-required state, and bounded transient retry.
- Actual evidence: concurrent authority tests, recurrence/ledger suites, real browser schedule
  create/run/history/pause/resume/recovery, restart persistence, and DB/API/MCP agreement.
- Remaining gap or fix: hosted tenant-admin browser path, installed wall-clock execution with an
  actual worker account, and hosted rollout/rollback continuity.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is proven? | Requirement 55, `SCHED-020`, `GHUCP-021`–`023`, and the use cases above. |
| Code owning path | Which code path owns behavior? | GlassHive principal authority/recurrent definition transaction, Scheduling Cortex workspace schedule bridge/ledger, BFF schedule route, and browser schedule UI. |
| Docs and nested docs/repos | Which docs define expected behavior? | Requirement 55, scheduling QA catalog, GlassHive runtime README, and Scheduling Cortex README. |
| Scripts or harnesses | Which suites exercised it? | GlassHive recurring/API/schema/catalog tests, Glass Drive server tests, Scheduling Cortex schedule/storage/dispatch tests, and Playwright CLI. |
| Local/external prerequisite state | Which prerequisite was proven healthy or degraded? | Local services and synthetic worker execution were healthy; the negative account path intentionally used a disconnected synthetic provider. |
| Logs | Which logs confirm or contradict the result? | The manual happy path completed; the negative path returned its expected structured conflict without an uncaught UI exception. |
| DB/state/persistence | Which state confirms it? | One active definition, one completed occurrence after a failed retry, retained workspace identity, and preserved state after runtime restart. |
| Generated/shipped artifact | Which artifact was inspected? | Source API/MCP/browser contracts and local rollout harness; installed/hosted artifact remains blocked. |
| Real user path | Which product path was used? | Real Glass Drive browser scheduling with create, Run now, history, pause, resume, refresh, restart, and reconnect-required recovery. |
| Visual/UX comparison | Did visible UI match expected evidence? | Yes locally; status, workspace name, next run, history count, and recovery copy matched ledger/API evidence. |
| Not run / blocked | Which required surface was not run? | Hosted tenant-admin disable, real-provider automatic fire, and hosted cutover/rollback. |

## User-Grade Evidence

- Surface exercised: Glass Drive Schedules, Workspaces, and Connections in a real browser against the
  local source runtime.
- Real user path: created hourly recurring work, manually ran it, inspected history, paused with
  confirmation, resumed, restarted the runtime, disconnected the selected account, retried, and
  restored deployment-managed state.
- Visible outcome: exactly one completed occurrence remained; the negative run gave explicit
  reconnect and safe-retry instructions rather than an internal error.
- Expanded/detail state: history showed the occurrence timestamp/status; workspace card showed the
  human workspace name, account state, next run, and tags.
- Persistence/reload result: definition, occurrence, workspace name, and next-run metadata survived
  runtime restart and browser refresh.
- Local/external prerequisite state: local runtime/UI were healthy; real hosted tenant administration
  and provider credentials were not authorized.
- Evidence retrieval classification, if applicable: disconnected credentials were classified as
  auth/config repair required, not provider-empty or success.
- Fallback path, if applicable: user could return to Connections, reconnect, and safely retry; no
  deployment fallback was silently used while account-only policy was active.
- Backend/log/DB confirmation: the failed manual attempt did not add an occurrence; authority and
  retry tests confirmed atomic disable/revalidation and bounded attempts.
- Final model/runtime wording check: the browser stated the reason, exact recovery action, and that
  no duplicate occurrence was created.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for required visible-UI, detail-state,
  persistence, or wording steps. The local browser path was run; hosted paths remain partial.

## Automated Evidence

```bash
cd viventium_v0_4/GlassHive
runtime_phase1/.venv/bin/python -m pytest -q \
  runtime_phase1/tests/test_recurring_schedules.py \
  runtime_phase1/tests/test_recurring_schedule_api.py \
  runtime_phase1/tests/test_schema_version.py \
  runtime_phase1/tests/test_workspace_lifecycle_catalog.py

cd frontends/glass-drive-ui && .venv/bin/python -m pytest -q tests/test_server.py

cd viventium_v0_4/LibreChat/viventium/MCPs/scheduling-cortex
uv run --group test pytest -q \
  tests/test_glasshive_workspace_schedules.py tests/test_storage.py tests/test_dispatch.py
```

The final locked-environment Scheduling Cortex suite recorded 143 tests plus 16 subtests. The final
GlassHive runtime collection recorded 1,063 tests (1,060 passed and 3 skipped), the Glass Drive
suite recorded 193 passed, and the parent release suite recorded 2,308 passed and 9 skipped.

## Findings

- Defects: post-disable native create/enable/manual-run/run-link races, unbounded action-required
  churn, and linear stale recurrence were closed before acceptance.
- Regressions: authority mutation, terminal action-required, bounded transient retry, restart lost
  response, and dense/sparse/month-end recurrence cases now protect these behaviors.
- Flakes: none observed in focused reruns.
- Environment issues: hosted tenant administration, real provider credentials, and cloud cutover
  were intentionally not mutated.
- Residual risks: installed wall-clock timing, real-provider lease/grant renewal, and hosted upgrade/
  rollback continuity.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
