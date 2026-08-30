# Parallel Work Installed Telegram Provider-Backed Mission QA Run - 2026-08-17

## Summary

- Result: **PASS** for the exact single-mission installed-runtime journey; **PARTIAL** for the
  complete Parallel Work release matrix.
- Build/source under test: current checkout activated through the supported local-runtime path.
- Runtime/artifact under test: installed local production, including Telegram ingress, Core,
  GlassHive, callback delivery, Web Control Panel, and a generated PDF opened in Preview.
- Environment: local production with public-safe synthetic mission content.
- Tester: Codex through Telegram Desktop, a real headed Web browser, and Preview.
- Related change: exact readiness gating, durable mission/message/retry continuity, truthful
  provider/capacity recovery, server-owned Main callback identity, and stage-specific adjudication.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `PWK-013` | PARTIAL | One useful Main-authored completion delivered once to Telegram and persisted in Web | Multi-destination, zero-target, Voice, and external-boundary replay remain |
| `PWK-015` | PARTIAL | Provider attention and explicit user retry recovered the same workspace without duplicate work | Exhaustion and all bridge-recovery variants remain |
| `PWK-037` | PASS | Installed launcher reached exact account-aware readiness before Telegram admission | Generic API reachability was not accepted as readiness |
| `PWK-039` | PASS for single-mission continuation | One follow-up became a noninterrupting durable Message on the same work | Broader simultaneous-work coverage is owned elsewhere |
| `PWK-UC-005` | PARTIAL | Completion survived user move-on and runtime recovery and returned once with artifact links | Archive/delete, Scheduler/Voice, and fanout remain |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `PWK-UC-001-A` | Send a substantial Telegram request, then ask Main an unrelated quick question | Telegram Desktop | PASS | One durable acknowledgement appeared and Main answered the quick question without waiting | One server-owned Main binding and one work record were correlated | Rapid multi-mission load remains separate |
| `PWK-UC-003-A` | Add guidance, encounter provider attention, reauthorize, and retry | Telegram Desktop and durable work actions | PASS for Message/Retry branch | Guidance receipt and truthful attention/recovery states were visible | Same workspace resumed; no duplicate mission and no stale automatic authority reuse | Remaining exact controls remain elsewhere |
| `PWK-UC-004-A` | Wait through capacity pressure | Telegram and GlassHive runtime | PASS for this episode | Work stayed queued instead of failing and later ran | Same run/work rows progressed to completion without weakening the guard | Forced maximum-load/fairness remains |
| `PWK-UC-005-A` | Move on, let the mission complete across runtime recovery, and open the artifact | Telegram Desktop, headed Web, and Preview | PASS for this branch | One completion with links and PDF attachment arrived; 11 rendered pages were visually inspected | One sent delivery, completed adjudication, and completed/delivered card survived reload | Archive/delete, Voice, Scheduler, and multiple destinations remain |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Parallel Work provider-backed mission continuity and callback delivery.
- Requirement: a substantial Telegram request becomes durable work while Main stays responsive;
  guidance/retry keep exact-work identity; terminal truth returns once with usable artifacts.
- Use case: launch, continue talking, guide, recover from provider/capacity attention, move on, then
  receive and inspect the finished result.
- QA case: `PWK-013`, `PWK-015`, `PWK-037`, `PWK-039`, and `PWK-UC-005`.
- Expected result: account-aware readiness gates ingress; one mission/workspace survives guidance,
  recovery, and restart; Main authors one useful completion and the artifact opens.
- Actual evidence: Telegram, Preview, Web reload, Core delivery state, and GlassHive work state all
  agreed for one installed mission and an 11-page PDF.
- Remaining gap or fix: finish rapid concurrency, multi/zero-destination fanout, archived/deleted
  origins, Voice/Scheduler/owner isolation, load/fairness, clean install, rollback, and artifact pins.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Single provider-backed Telegram mission and cases listed above |
| Code owning path | Which code path owns the behavior? | Launcher readiness, Telegram ingress, durable work actions, provider classification, callback adjudication, delivery, and Control Panel roster |
| Docs and nested docs/repos | Which docs define expected behavior? | Parallel Work requirement, Telegram bridge requirement, and `qa/parallel-orchestrator/cases.md` |
| Scripts or harnesses | Which suites exercised it? | Mission adjudication, orchestration readiness, provider classification, Telegram ingress/bridge, capability broker, profile runtime, and launcher ordering suites |
| Local/external prerequisite state | Which dependency was healthy or degraded? | Installed local stack reached exact readiness; provider auth/quota and capacity attention were exercised and recovered explicitly |
| Logs | Which sanitized logs confirm or contradict the result? | Launcher readiness, provider recovery, stale callback reclaim, and sent delivery were correlated by stage and status |
| DB/state/persistence | Which persisted state confirms it? | One Main binding, one durable work/workspace, one follow-up Message, one completed adjudication, and one sent delivery |
| Generated/shipped artifact | Which generated or shipped artifact was inspected? | Generated 11-page PDF opened in Preview; installed runtime was active current checkout, not clean-install/pin proof |
| Real user path | Which real surface was used? | Telegram send/receive, unrelated Main follow-up, guidance, explicit Retry, Preview artifact inspection, Web card inspection, and reload |
| Visual/UX comparison | Did visible state match supporting evidence? | Yes: attention, queue, completion, delivered card, links, attachment, and rendered PDF matched durable state |
| Not run / blocked | Which required surface was not run? | Full concurrency/fairness, multi/zero-target fanout, archive/delete, Voice/Scheduler, clean install, rollback, and pins |

Supporting evidence cannot replace required user-path evidence. Those unrun branches keep the full
feature `PARTIAL` even though the exact installed journey passed.

## User-Grade Evidence

- Surface exercised: installed Telegram Desktop, headed Web Control Panel, and Preview.
- Real user path: sent a public-safe research/PDF request, asked Main an unrelated quick question,
  added guidance, recovered the exact work through explicit Retry after provider reauthorization,
  waited through capacity queueing and runtime recovery, received completion, opened the PDF, and
  reloaded the Active Work card.
- Visible outcome: Telegram showed durable acknowledgement, responsive Main, guidance/provider/
  capacity truth, then one useful terminal completion with download, preview, workspace links, and
  the PDF attachment.
- Expanded/detail state: Preview displayed page 1 of 11 with a complete thumbnail rail; Web showed
  the top Active Work card as completed, delivered, and read-only with View.
- Persistence/reload result: runtime recovery reclaimed the stale callback; after browser reload the
  same card remained completed/delivered and the browser console had zero errors.
- Local/external prerequisite state: exact orchestration readiness was healthy before ingress;
  provider authorization and capacity degraded during the mission and recovered without bypass.
- Evidence retrieval classification, if applicable: provider authorization/quota attention and
  capacity unavailable were distinct recoverable states, not successful-empty results.
- Fallback path, if applicable: explicit user Retry after reauthorization resumed the same workspace;
  no ambiguous automatic retry or silent provider remap occurred.
- Backend/log/DB confirmation: Core and GlassHive evidence agreed on one binding, one work/workspace,
  one follow-up, completed adjudication, and one sent delivery.
- Final model/runtime wording check: user-visible text accurately described readiness, attention,
  queueing, and terminal delivery; status text did not substitute for Main's useful completion.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for any required visible-UI, detail-state,
  persistence, or wording step.

## Automated Evidence

- Mission adjudication, orchestration readiness, provider classification, Telegram ingress,
  capability broker, profile runtime, launcher ordering, and Telegram bridge regression suites
  passed after the fixes.
- Telegram Python suite: **439 tests passed**.

## Findings

- Defects: four escaped structural defects were promoted to regressions: generic reachability used
  as readiness; successful structured fallback overridden by earlier primary prose; callback loss
  of authoritative Main identity/request shape; and generic adjudication exceptions collapsing to
  misleading failure.
- Regressions: no affected regression remained in the final exact journey.
- Flakes: none observed in the final run.
- Environment issues: provider authorization/quota and capacity attention occurred and recovered
  truthfully during the run.
- Residual risks: the broader release gates named above remain unrun and the feature remains dark.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, timestamps, and conclusions only.
