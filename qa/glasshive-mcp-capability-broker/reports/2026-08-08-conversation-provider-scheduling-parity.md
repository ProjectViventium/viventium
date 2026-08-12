# Conversation-Provider Scheduling Parity RCA And QA

Date: 2026-08-08
Status: **PASS — repaired and proven on Telegram and authenticated browser**

## Outcome

The main Viventium Agent can now use its structurally declared Scheduling Cortex capability when
GlassHive is the conversation provider. Telegram and the configured non-admin Test Account browser
each created one synthetic one-time reminder, showed a success reply, persisted the requested local
time/timezone/payload, deleted the exact reminder through chat, and left zero schedule residue. The
browser result also survived a page reload. Synthetic conversations and local JWT sessions were
removed.

This is a universal capability-boundary fix. Runtime behavior does not match reminder wording,
agent/display names, provider labels, user identity, or the synthetic QA markers.

## Root cause

The escaped failure had three contributing layers:

1. **Declared capability was not projected.** The main Agent carried Scheduling Cortex, but the
   conversation-provider broker only projected MCP servers with an explicit reviewed policy.
   Scheduling Cortex and the read-only Viventium Health server lacked that policy. Native worker
   tools could still exist, making the overall worker look capable while the declared MCP was absent.
2. **Live calls inherited a dead cancellation signal.** After policy/projection was repaired, real
   scheduling calls still ended before reaching the MCP. Broker diagnostics showed the provider call
   starting with both parent and broker signals already aborted. The route forwarded an outer
   request signal whose lifecycle had completed before the worker's broker request began.
3. **Redundant discovery consumed the request budget.** The MCP client had already completed
   `tools/list`, but each tool call rediscovered the same schemas. This was not the final failure, but
   it amplified delay and retry pressure and made the stale-signal symptom harder to isolate.

The original assistant response was therefore truthful about its observed tool failure but wrong as
product behavior: the scheduler was installed, healthy, and declared; the cognitive/provider bridge
failed to deliver it.

## Surgical repair

- Added reviewed source-of-truth broker policies for every non-excluded MCP structurally attached to
  the main Agent. Scheduling permits bounded reads plus user-owned schedule CRUD; Viventium Health is
  read-only.
- Added a compiler parity guard so a future main-Agent MCP cannot silently ship without a reviewed
  conversation-provider projection policy.
- Made provider projection explicit and observable as `complete`, `partial`, or `empty`, with stable
  structured omission reasons. Partial/empty boundaries reach the actual worker instruction channel,
  so another native tool cannot mask an omitted server.
- Bound broker cancellation to the real broker HTTP request/response lifecycle. Normal response
  completion removes listeners; a genuine client disconnect still aborts work. Completed outer
  chat/provider signals are not reused.
- Reused only successful, non-empty schema discovery for the same short-lived signed grant. User
  existence and current policy are revalidated on every request. Failures, empty results,
  credentials, and tool results are not cached.
- Required `invocation_id` in every brokered write schema and forwarded it through the generic invoke
  escape hatch. Shared replay protection rejects duplicate logical mutations.
- Added a reusable Test Account browser harness with exact schedule and conversation cleanup plus a
  cleanup-only recovery mode for interrupted QA.

## Alignment and rejected alternatives

The model still interprets the request and chooses its tools. Policy answers only whether a declared
capability is authorized. No router asks whether text “looks like scheduling,” and the main prompt was
not taught one complaint-specific response.

Rejected approaches:

- hardcoding reminder/scheduler phrases, surface names, or provider names;
- bypassing GlassHive with a special Telegram scheduler branch;
- making the main Agent claim tools that were not materially projected;
- disabling cancellation entirely instead of binding it to the correct request;
- weakening email, calendar, file, permission, or other connected-account mutation confirmation.

`writePolicy: allow` is limited to the reviewed low-impact Scheduling Cortex policy. It still requires
an invocation ID and replay guard. Connected-account writes remain confirmation-gated by their own
policies.

## Evidence

| Gate | Result | Evidence |
| --- | --- | --- |
| Policy/projection/compiler | PASS | Dynamic compiler guard covers all main-Agent MCPs except declared exclusions; Scheduling and Health source/generated policies match. Final focused compiler/health run: 4/4. Earlier full affected compiler/health run: 158/158. |
| Broker/provider/route regressions | PASS | 63/63 across provider bootstrap, projection, broker discovery/invocation/replay, and the HTTP route's live request-scoped `AbortSignal`, including normal finish, request abort, premature response close, and a real socket disconnect. |
| Scheduling Cortex regressions | PASS | 114 tests plus 6 subtests. |
| Telegram create | PASS | Native Telegram visibly confirmed one synthetic reminder only after tool success. Scheduler persistence contained exactly one active one-time row with the requested Toronto time, timezone, and payload. |
| Telegram delete | PASS | Native Telegram visibly confirmed deletion; Scheduling Cortex received delete calls; the exact row count returned to zero before its due time. |
| Test Account browser create | PASS | Authenticated non-admin browser visibly showed the scheduled reminder; persistence contained exactly one correct row. |
| Browser persistence | PASS | The same completed assistant message container remained visible after a real page reload. |
| Test Account browser delete | PASS | Browser visibly showed successful deletion; the exact schedule count returned to zero. |
| Cleanup | PASS | Zero matching Telegram/browser schedules, zero synthetic browser messages/conversations, and the temporary local JWT session was removed. |
| Cancellation RCA | PASS | Pre-fix live log: provider call started with parent/broker signals aborted. Post-fix Telegram and browser logs repeatedly showed `parent_signal_aborted=false`, `broker_signal_aborted=false`, followed by MCP invocation. |
| Runtime | PASS | Supported local runtime was reactivated from the current checkout; API, web, Scheduling Cortex, GlassHive provider, and Telegram surfaces were exercised after activation. |

Private raw screenshots, account identifiers, message IDs, schedule IDs, and full logs remain under the
local private QA evidence root and are not published. This report uses only synthetic content and
aggregate/hash-safe results.

## Iteration record

The failed steps are retained as evidence:

- initial live Telegram attempts proved complete projection but timed out before Scheduling Cortex;
- signal instrumentation exposed an already-aborted inherited signal;
- the post-route-fix Telegram run passed create/delete;
- the first authenticated browser launch failed closed because the local web runtime had stopped and
  created no schedule;
- two later browser attempts proved product create/delete but exposed an overly literal QA assertion
  that demanded hidden structured message content; the harness recovered each exact reminder through
  the visible scheduling path and left zero residue;
- the final harness uses the stable rendered message boundary and passed all create/reload/delete and
  cleanup gates;
- after extracting the lifecycle helper for direct regression coverage, the supported runtime was
  reactivated again and the authenticated browser repeated create/reload/delete against the final
  source with correct persistence and zero schedule/conversation residue.

## Independent review

A read-only Claude Opus adversarial pass approved the architecture and security boundaries but first
blocked acceptance because cancellation's disconnect and normal-finish guarantees were asserted more
broadly than the route tests proved. The lifecycle helper was then exercised independently for request
abort, premature response close, normal finish and listener cleanup, plus a real socket disconnect.
The three affected suites passed 63/63. A narrow re-review returned **APPROVE**, independently
reconciled the count, and found no mounting, require, race, listener-leak, or write-after-disconnect
defect in the final extraction.

## Delivery boundary

The fix is active in the local installed runtime for QA. No public commit, push, pull request, cloud
deployment, or live Agent sync was performed. Nested LibreChat changes still require their own review,
commit, component pin/update, and shipped-artifact verification before any release claim.
<!-- qa-evidence-exempt: Historical or specialized supporting artifact retained without retroactively inventing missing evidence; current release acceptance requires a fresh full-view report. -->
