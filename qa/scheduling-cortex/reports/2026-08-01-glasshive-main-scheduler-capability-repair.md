# GlassHive Main Scheduler Capability Repair — 2026-08-01

## Summary

`SCHED-019`: **PASS** on the active local production runtime.

Scheduling Cortex was healthy, but GlassHive's broker route forwarded an already-aborted HTTP
lifecycle signal into the real MCP call. Catalog discovery therefore worked while `tools/call`
failed locally before Scheduling Cortex received it. The repair separates cancellation ownership:
GlassHive owns intentional run cancellation, the broker owns its provider timeout, and a completed
web/relay request no longer cancels the MCP operation.

- Result: PASS
- Build/source under test: final reviewed parent candidate with merged LibreChat and GlassHive trees
- Runtime/artifact under test: active installed local production runtime
- Environment: local macOS browser and Telegram Desktop
- Tester: Codex with Computer Use and supporting runtime inspection
- Related change: compiler-owned Scheduler capability projection and durable broker execution

## Scope Run

| Check | Result | Public-safe evidence |
| --- | --- | --- |
| Scheduler health and direct MCP | PASS | Health was `ok`; initialize, tool listing, and count-only `schedule_list` completed in milliseconds. |
| GlassHive broker direct call | PASS | Two concurrent authenticated calls completed successfully; Scheduler recorded two real `CallToolRequest`s. |
| LibreChat user path | PASS | A synthetic count-only prompt returned the verified active/total summary. Harness activity showed a connected-tool step and the result survived refresh. |
| Telegram user path | PASS | The same prompt returned the same summary once; configured voice rendering was delivered and no late text duplicate appeared after the observation window. |
| Persistence and run uniqueness | PASS | Each surface stored one user and one assistant message. GlassHive stored two completed, error-free requests/runs total for the two surface checks. |
| Capability isolation | PASS | Both worker bundles allowed only `scheduling-cortex`; dynamic policy expansion was disabled. |
| Invalid grant | PASS | A synthetic invalid grant returned HTTP 401 with structured RPC authentication failure. |
| Aborted route signal regression | PASS | Route tests inject an already-aborted request signal and prove it is not forwarded to catalog/tool execution. |
| Requested Claude second opinion | BLOCKED | The signed-in review surface reported exhausted plan usage. No substitute model was presented as the requested review. The repository's five-axis and security checklists were completed locally. |

No schedule titles, prompts, identifiers, user identifiers, tokens, local absolute paths, screenshots,
or database exports are included in this public report.

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: interactive Scheduling Cortex access from a GlassHive-backed Main Agent.
- Requirement: `docs/requirements_and_learnings/11_Scheduling_Cortex.md` interactive access contract.
- Use case: inspect current schedules from web or Telegram through the agent's selected MCP tool.
- QA case: `SCHED-019` and `SCHED-UC-019`.
- Expected result: both surfaces return the same verified result, preserve it across refresh/relay,
  grant no unrelated MCP server, and never present provider failure as a successful empty list.
- Actual evidence: visible web and Telegram outcomes, expanded harness activity, persistence counts,
  GlassHive terminal aggregates, broker/Scheduler logs, health, and invalid-grant behavior.
- Remaining gap or fix: destructive live Scheduler stop was intentionally not performed against the
  active schedule ledger; the automated degraded-provider contract covers that unhappy path.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which contract is proven? | Scheduler interactive access contract, `SCHED-019`, and `SCHED-UC-019` |
| Code owning path | Which path owns it? | Compiler policy -> LibreChat grant/route/broker -> GlassHive worker -> Scheduler MCP |
| Docs and nested docs/repos | Where is behavior defined? | Scheduler requirement, living cases, merged LibreChat and GlassHive source |
| Scripts or harnesses | What exercised it? | Computer Use, direct authenticated broker probe, compiler/Jest/pytest suites |
| Local/external prerequisite state | Were dependencies healthy? | Scheduler and broker health were `ok`; native harness auth was ready |
| Logs | What corroborated tool use? | Sanitized broker success and real Scheduler `CallToolRequest` entries |
| DB/state/persistence | What persisted? | One user/assistant pair per surface and two terminal error-free provider runs |
| Generated/shipped artifact | What artifact was checked? | Generated runtime config, source config, component pins, and active installed checkout |
| Real user path | Which surfaces ran? | Logged-in Viventium browser via Computer Use and Telegram Desktop |
| Visual/UX comparison | Did UI/delivery match? | Same verified count-only result, connected-tool activity, refresh persistence, no duplicate |
| Not run / blocked | What remained unavailable? | Live destructive service stop and requested Claude review; neither substituted for run evidence |

## User-Grade Evidence

- Surface exercised: logged-in Viventium browser with expanded harness activity and Telegram Desktop.
- Real user path: asked the Main Agent to inspect schedules on each surface, refreshed the browser,
  and observed Telegram through the late-duplicate window.
- Visible outcome: both surfaces returned the same verified count-only result; Telegram delivered one
  authored text response plus its configured voice rendering.
- Expanded/detail state: the browser showed harness-started and connected-tool activity steps.
- Persistence/reload result: the web result/activity survived refresh; each surface retained one
  user/assistant pair and no late duplicate appeared.
- Local/external prerequisite state: Scheduling Cortex, the broker, GlassHive, LibreChat, Telegram,
  and native harness authentication were healthy.
- Evidence retrieval classification, if applicable: successful non-empty MCP result; invalid auth was
  separately rejected, and provider-degraded/timeout classes remained explicit in automation.
- Fallback path, if applicable: no fallback was used; the selected Scheduling Cortex MCP authored the
  evidence and no direct wrapper LLM substituted for it.
- Backend/log/DB confirmation: sanitized Scheduler calls, broker invocations, Mongo pair counts,
  GlassHive terminal state, exact capability bundles, and generated config matched the visible turns.
- Final model/runtime wording check: the Main reported verified scheduler data and did not claim the
  scheduling connection was unavailable.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for any required visible-UI, detail-state,
  persistence, or wording step.

## Automated Evidence

- LibreChat broker route/service/conversation-provider: **40 passed**.
- LibreChat broker/Phase B/managed-upgrade focused gate: **213 passed**; the exact Node 24 route
  regression also passed **7/7**.
- GlassHive full runtime suite: **772 passed, 3 skipped**.
- Runtime config compiler: **173 passed**.
- Scheduling Cortex: **114 passed, 8 subtests passed**.
- Parent component/public-safety release slice: **48 passed**.
- Changed JavaScript formatting and both repository diff checks: **PASS**.

## Delivery Trace

`agent tool selection -> compiler GlassHive policy -> exact conversation grant -> GlassHive native
capability broker -> user-scoped MCP connection -> Scheduling Cortex -> authored web/Telegram answer`

The live generated config, source config, and installed config had matching hashes during the user
turn. Broker logs recorded successful invocations at the same timestamps as Scheduler
`CallToolRequest`s. Mongo and GlassHive terminal state agreed with the visible results.

LibreChat PR 87 merged as `5f9c44ef47ff83a4889313fda74dfe1f5e817ad3` after every hosted
check passed, including the full API suite on Node 24. GlassHive PR 47 merged as
`5c2117ab7ebfa94a6556aba8822b34fcab44c54d` after the full local runtime suite passed. In both
repositories, the merge tree exactly matched the audited head tree; the parent lock pins those
merged commits.

## Findings

- Defects: missing Scheduler projection and request-signal cancellation were repaired.
- Regressions: none observed in web, Telegram, persistence, broker isolation, or hosted tests.
- Flakes: a GlassHive callback-budget test race was isolated and made deterministic; final suites passed.
- Environment issues: the requested Claude review-only pass was blocked by external plan quota.
- Residual risks:
- Invalid authorization and stale-aborted request lifecycle: **PASS**.
- Provider timeout/degraded mapping, rate limiting, unavailable user, write-grant enforcement, and
  catalog retry behavior: **PASS-AUTOMATED**.
- A destructive live Scheduler-stop test was not run against the owner's active runtime. The
  automated degraded-provider contract covers it without interrupting live schedules.
- The requested Claude review-only pass was blocked by external plan quota. Claude is supporting
  evidence rather than a replacement for user-surface, persistence, runtime, and test evidence.
- No schedule create/update/delete operation was needed for this escaped read/list failure; existing
  CRUD coverage remains owned by `SCHED-001`.

There is no remaining blocker for interactive Scheduler access from the GlassHive-backed Main Agent.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
