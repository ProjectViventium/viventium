# Scheduled Turn Context Budget And Title QA Run - 2026-08-18

## Summary

- Result: **PASS-LIVE** for `SCHED-026` on installed local production.
- Escaped failure: a small one-time reminder repeatedly ended as `completion_error` while a large
  Active Work roster was present. The created assistant-only conversation also exposed an internal
  scheduler marker as its sidebar title.
- Root cause: time, Active Work, and source-selection capsules had independent limits but were
  concatenated into one 16 KiB GlassHive `turn_context` field. Title generation received the
  private execution envelope instead of a separate task source.
- Repair: one caller-owned context budget now reserves fixed capsules first and truncates only whole
  Active Work roster items. Scheduler dispatch now carries a separate bounded title source.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `SCHED-026` durable retry | PASS | The same previously failed one-time occurrence retried after activation, received provider HTTP 200, delivered once, and became inactive | No replacement task was created for this proof |
| `SCHED-026` public title | PASS | A fresh one-time reminder delivered in Chrome and its task-derived title persisted after refresh | Internal scheduler execution text remained absent from the new title |
| Structural diagnostics | PASS | GlassHive recorded only validation field/type for the pre-fix rejection | Rejected context content was not logged |
| Automated regression | PASS | 298 provider/context tests, 25 scheduler/time-context tests, 25 full scheduler-route tests, 90 Scheduling Cortex dispatch tests, and 2 focused GlassHive tests passed | Three unrelated existing surface-prompt assertions were excluded and not represented as passing |
| Cleanup | PASS | Both synthetic task rows were deleted through the scoped storage owner and four QA-only conversations were archived through the product UI | Archive is recoverable; run-ledger evidence remains internal |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `SCHED-026-A` | Create a one-time reminder while many work items exist | Logged-in Chrome | PASS | Main confirmed the exact scheduled time and cancellation wording | One durable task row was created | None for one-time creation |
| `SCHED-026-B` | Let a failed reminder recover after the product fix | Installed Scheduler, LibreChat, and GlassHive | PASS | Reminder appeared once in its own conversation | Same occurrence changed from structured failure to success/sent; task became inactive | None for durable retry branch |
| `SCHED-026-C` | Reload the delivered reminder | Chrome refresh | PASS | Reminder remained visible | Conversation and delivery ledger agreed | None |
| `SCHED-026-D` | Inspect the new scheduled conversation title | Chrome sidebar and refresh | PASS | Exact task-derived title appeared; no internal marker | Trusted title-source courier and route regression passed | Historical pre-fix titles are cleanup/migration debt, not evidence for the new path |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Scheduling Cortex through Main and the GlassHive conversation provider.
- Requirement: [Scheduling Cortex dispatch behavior](../../../docs/requirements_and_learnings/11_Scheduling_Cortex.md#dispatch-behavior).
- Use case: create a small reminder while Main has a large Active Work roster; rely on durable retry;
  read the result in a human-titled conversation after refresh.
- QA case: `SCHED-026`.
- Expected result: valid context stays within the provider contract; retry is not duplicated; visible
  result, task state, provider admission, and title all agree.
- Actual evidence: two real Chrome-created one-time reminders, installed-runtime restart, provider
  HTTP status, scheduler task/run ledgers, visible delivery, sidebar title, and refresh agreed.
- Remaining gap: recurring change-only checks and multi-mission `waiting_external` remain owned by
  `SCHED-023` and `SCHED-024`; this run does not convert those cases to PASS.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which contract is proven? | Scheduling dispatch behavior and `SCHED-026` |
| Code owning path | Which layers own it? | Scheduling dispatch, authenticated scheduler route, Agent request context assembly, Active Work capsule builder, GlassHive metadata validation |
| Docs and nested docs/repos | Which truth changed? | Scheduling requirement and Scheduling QA catalog |
| Scripts or harnesses | Which checks ran? | Affected Jest, Scheduling Cortex unittest, and GlassHive pytest selections |
| Local/external prerequisite state | Was the stack healthy? | Installed local API, Web, modern playground, Scheduler, and GlassHive were responding |
| Logs | What proves the failure and recovery? | Pre-fix structural `turn_context:string_too_long`; post-fix completion request HTTP 200 |
| DB/state/persistence | What proves durable truth? | Same failed occurrence later succeeded/sent; fresh one-time task delivered and became inactive |
| Generated/shipped artifact | What ran? | Current dirty checkout activated as installed local production; no clean-install or release-pin claim |
| Real user path | What did the user do? | Chrome message -> Main tool use -> due scheduler run -> visible reminder -> refresh |
| Visual/UX comparison | Did UI match state? | Yes; output and task-derived title matched ledger state after refresh |
| Not run / blocked | What is outside this case? | Telegram parity, recurring change-only cadence, clean install, and public release pins |

## User-Grade Evidence

- Surface exercised: logged-in Chrome against installed local production.
- Real user path: asked Main to create a public-safe one-time reminder, waited for its natural due
  run, opened the generated conversation, and refreshed it.
- Visible outcome: the reminder delivered once; the fresh conversation used the task source as its
  title instead of exposing the private scheduler envelope.
- Expanded/detail state: create reply included scheduled time and cancellation instruction.
- Persistence/reload result: reminder body and human title remained after refresh.
- Backend/log/DB confirmation: provider accepted the fixed request; task/run ledgers recorded
  success/sent and inactive one-time state.
- Final model/runtime wording check: visible success did not contradict ledger state.
- Substitution check: automated tests and logs support, but do not replace, the real Chrome run.

## Automated Evidence

- LibreChat provider/context matrix: **4 suites / 298 tests passed**.
- Scheduler/time-context selection: **2 suites / 25 tests passed**.
- Full authenticated scheduler route: **25/25 passed**.
- Scheduling Cortex dispatch: **90/90 passed**.
- GlassHive structural validation and turn-context refresh: **2/2 passed**.
- Formatting, Python compilation, and diff checks are part of the final acceptance pass.

## Findings

- Defects: independent context ceilings overflowed one provider field; internal scheduler text was
  reused for public metadata.
- Regressions added: shared byte budget, whole-item truncation with high-priority retention,
  deterministic scheduled message identity, public title-source courier, and structural-only
  validation diagnostics.
- Environment issues: none blocked the final installed Chrome journey.
- Residual risks: historical pre-fix internal-marker titles outside this run remain local migration
  debt; recurring and mission-gated schedules retain their existing PARTIAL/NOT RUN status.

## Public-Safety Review

- [x] No secrets, tokens, cookies, credentials, private prompts, or private account content.
- [x] No personal email, local absolute path, hostname, conversation/task/message ID, or DB export.
- [x] Synthetic reminder wording is public-safe.
- [x] Runtime evidence is summarized by status/class/count only.
