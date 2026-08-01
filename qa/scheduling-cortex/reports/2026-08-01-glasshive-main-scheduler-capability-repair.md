# GlassHive Main Scheduler Capability Repair — 2026-08-01

## Result

`SCHED-019`: **PASS** on the active local production runtime.

Scheduling Cortex was healthy, but GlassHive's broker route forwarded an already-aborted HTTP
lifecycle signal into the real MCP call. Catalog discovery therefore worked while `tools/call`
failed locally before Scheduling Cortex received it. The repair separates cancellation ownership:
GlassHive owns intentional run cancellation, the broker owns its provider timeout, and a completed
web/relay request no longer cancels the MCP operation.

## What Was Run

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

## Unhappy Paths And Residual Risk

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
