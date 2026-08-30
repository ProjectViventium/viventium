# Scheduled Main Agent Builder Inheritance QA Run - 2026-08-18

## Summary

- Result: **PASS** for `SCHED-016` across real Prompt Workbench presentation, Main-Agent execution,
  LibreChat and Telegram delivery, compiled runtime routing, persistence, cleanup, and simulated
  configured fallback.
- Build/source under test: current checkout with scheduler-owned Main provider/model/effort overrides
  removed from supported compiler, MCP, authenticated route, and Workbench presentation paths.
- Runtime/artifact under test: installed local production using freshly compiled runtime output.
- Environment: local production with public-safe synthetic schedule controls.
- Tester: Codex through a real headed browser and Telegram Desktop with supporting suites and ledger
  inspection.
- Related change: `executor="viventium_agent"` now resolves the persisted Main Agent as configured in
  Agent Builder at execution time; `executor="glasshive_host"` remains a distinct Workbench route.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `SCHED-016` | PASS | Real Workbench Main control completed and delivered through LibreChat; a second delivered to Telegram | Fallback activation was safely simulated rather than forcing a live provider failure |
| Compiler/runtime inheritance | PASS | Supported schema/examples and compiled output carried no schedule-owned Main tuple | Fresh runtime output was inspected |
| Workbench presentation | PASS | UI showed `Viventium Main (Agent Builder)` and no current schedule-owned model/effort after refresh | Historical run provenance remained labeled historical |
| Cleanup | PASS | Synthetic schedule/task/run/conversation/message/transaction residue count returned to zero | Private raw identifiers were not retained in this report |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `SCHED-UC-016-A` | Inspect a scheduled Main row in Prompt Workbench | Headed browser | PASS | UI identified Main Agent Builder inheritance and omitted current schedule-owned model/effort | API metadata and compiled environment agreed | None for presentation branch |
| `SCHED-UC-016-B` | Trigger one Main schedule from Workbench | Supported Workbench and LibreChat | PASS | Exact synthetic control result appeared in LibreChat | Runtime loaded persisted Main, used compiled origin, and completed the run | None for this branch |
| `SCHED-UC-016-C` | Trigger a second Main schedule to Telegram | Workbench and Telegram Desktop | PASS | A new exact synthetic bot bubble appeared | Run ledger recorded completed/delivered and Telegram sent/delivered without schedule-owned model/effort | None for this branch |
| `SCHED-UC-016-D` | Encounter a recoverable Main primary failure | Automated exact-path simulation | PARTIAL user-grade | No live provider fault was introduced | Regression initialized the configured Agent Builder fallback | A natural live failure can be monitored without mutating provider config |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Scheduling Cortex Main-Agent dispatch inheritance.
- Requirement: [Scheduling Cortex - Dispatch Behavior](../../../docs/requirements_and_learnings/11_Scheduling_Cortex.md#dispatch-behavior).
- Use case: future scheduled Viventium work follows whatever provider, model, parameters, GlassHive
  options, and fallback are currently saved on Main in Agent Builder.
- QA case: `SCHED-016`.
- Expected result: compiler, environment, MCP payload, route metadata, and UI never silently replace
  Main or delete its fallback; real scheduled work uses current Agent Builder state.
- Actual evidence: Web inspection/refresh, one real LibreChat delivery, one real Telegram delivery,
  runtime logs, run ledger, compiled output, cleanup, and configured-fallback simulation agreed.
- Remaining gap or fix: the next natural private schedule occurrence was not accelerated; a live
  fallback failure was not forced because that would mutate provider/runtime conditions.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Scheduling dispatch inheritance and `SCHED-016` |
| Code owning path | Which code path owns the behavior? | Config compiler, scheduler MCP payload, authenticated route, Agent initialization, Workbench API/UI, and compiled LibreChat origin |
| Docs and nested docs/repos | Which docs define expected behavior? | Scheduling Cortex requirement, Scheduling QA cases, compiler/runtime docs, and nested LibreChat scheduler behavior |
| Scripts or harnesses | Which suites exercised it? | Config compiler, Scheduling Cortex, affected LibreChat, Prompt Workbench, and production build suites |
| Local/external prerequisite state | Which dependency was healthy or degraded? | Installed Web/API/GlassHive/Telegram and persisted Main were healthy; independent Claude review auth was degraded |
| Logs | Which sanitized logs confirm or contradict the result? | Logs showed scheduler loading Main from Agent Builder, projecting GlassHive capability, and preparing configured fallback |
| DB/state/persistence | Which persisted state confirms it? | Completed/delivered run rows had no schedule-owned model/effort; cleanup left zero synthetic residue |
| Generated/shipped artifact | Which generated or shipped artifact was inspected? | Fresh compiled runtime output and active installed checkout; no clean-install/pin claim |
| Real user path | Which real surface was used? | Browser Workbench selection/refresh, supported manual schedule trigger, LibreChat result, and Telegram delivery |
| Visual/UX comparison | Did visible state match supporting evidence? | Yes: UI inheritance copy, delivered outputs, logs, compiled config, and run ledger agreed |
| Not run / blocked | Which required surface was not run? | Natural cadence was not accelerated; live configured fallback activation and independent Claude verdict were not obtained |

Supporting evidence cannot replace required user-path evidence. The real Workbench, LibreChat, and
Telegram branches passed; the simulated fallback and blocked independent review do not become live
user-path acceptance.

## User-Grade Evidence

- Surface exercised: headed Prompt Workbench browser, LibreChat, and Telegram Desktop.
- Real user path: selected scheduled rows, confirmed Main-Agent inheritance copy, refreshed the page,
  manually triggered a public-safe synthetic Main control through the supported Workbench, observed
  LibreChat delivery, then triggered and observed a second exact Telegram delivery.
- Visible outcome: Workbench showed `Viventium Main (Agent Builder)` without a schedule-owned current
  model/effort; the exact synthetic result appeared once in LibreChat and once in Telegram.
- Expanded/detail state: selected scheduled-row detail explained that route and fallback are
  inherited at run time while old model/effort values appeared only as historical provenance.
- Persistence/reload result: Workbench wording survived refresh; run ledger settled completed and
  delivered; synthetic definitions and evidence rows were then removed with zero residue.
- Local/external prerequisite state: current checkout, compiled runtime, GlassHive Main, LibreChat,
  Workbench, and Telegram were healthy; external Claude review OAuth was unavailable.
- Evidence retrieval classification, if applicable: independent review was provider retry exhausted,
  then auth/config missing; product execution itself was healthy.
- Fallback path, if applicable: configured Agent Builder fallback initialization passed an exact
  recoverable-failure simulation; no live provider configuration was mutated to force it.
- Backend/log/DB confirmation: logs loaded Main from Agent Builder and prepared its fallback; the run
  ledger recorded completed/delivered and Telegram sent/delivered with no schedule-owned tuple.
- Final model/runtime wording check: Workbench did not present a fixed current schedule model/effort,
  and both delivered controls matched their exact synthetic outcomes.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for any required visible-UI, detail-state,
  persistence, or wording step.

## Automated Evidence

- Config compiler: **190 tests passed**; supported examples/schema omit `runtime.scheduled_agent`
  and compiled output carries no legacy scheduled-agent variables.
- Scheduling Cortex: **173 tests plus 10 subtests passed**.
- Affected LibreChat: **3 suites / 66 tests passed**.
- Prompt Workbench: **179 tests passed**, and the production build passed.
- Exact regressions lock compiler/schema, MCP payload, authenticated-route stripping, persisted Main
  initialization, configured fallback, Workbench presentation, and compiled-origin selection.

## Findings

- Defects: Scheduler had supplied its own fixed tuple, bypassed persisted Main, removed Main fallback,
  and the standalone Workbench initially targeted an obsolete development origin. The structural
  inheritance and compiled-origin paths were repaired.
- Regressions: drift locks now fail on reintroduced overrides, dropped fallback, misleading current
  model/effort presentation, or ignored compiled origin.
- Flakes: none observed in the final product runs.
- Environment issues: visible Claude Opus review exhausted retries; the same-model headless attempt
  then encountered expired local OAuth. No independent verdict was inferred.
- Residual risks: ordinary next-cadence monitoring and a naturally occurring live primary failure
  remain observational follow-ups, not blockers to the exact passed branches.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, timestamps, and conclusions only.
