# Parallel Work QA Run - 2026-08-18

## Summary

- Result: PASS for rapid A/B/C accounting, Main availability, durable launch presentation, the
  natural existing-mission-versus-new-mission decision, additive same-work guidance, and terminal
  completion delivery after provider recovery.
- Build/source under test: current public source checkout with the rebuilt LibreChat API package.
- Runtime/artifact under test: installed local production activated from that checkout.
- Environment: local macOS runtime, installed Telegram Desktop, headed Chrome, and real Redis for
  stream-manager integration.
- Tester: Codex with an independent review-only Claude pass.
- Related change: bind Main's launch presentation and delivery acknowledgement to the exact durable
  GlassHive receipt instead of provider prose or stream timing; preserve the original mission when
  Message adds guidance; treat the current lifecycle callback as terminal authority during follow-up
  adjudication; retain durable receipt proof across every surface without forcing Web or Scheduler
  into an external-adapter presentation contract; separate current-task constraints from stale
  assistant context; coalesce queued Retry-plus-Message into one continuation; and recover safe idle
  Docker compute only under freshly measured pressure; retain continuation guidance in the trusted
  constraint ledger while stripping the reserved source from public ingress; preserve final-attempt
  stderr classification; reset wait coalescing after real execution; and keep provider fallback from
  replaying recovered authorship or masking the primary failure when fallback preflight is unavailable.
  A final independent adversarial pass also caught and closed queued Message-to-Message guidance loss
  and post-lease capacity callback flooding before acceptance.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `PWK-002` | PASS | Two durable Telegram mission acknowledgements, direct `169`, two mission rows, reloaded Active Work | Three-way execution and maximum load remain separate cases. |
| `PWK-038` | PASS | 39 lifecycle tests, 260 GlassHive API tests, 429 combined LibreChat orchestration tests, and independent focused review | Covers terminal, multi-launch, mixed-answer, exact receipt/ack, cross-surface presentation authority, persistence races, and the legacy Message route. |
| `PWK-039` | PASS | Natural Telegram request/continuation/recovery, exact action ledger, delegation count, headed Chrome reload, completed PDF | Main reused one exact mission, preserved its research/PDF contract while adding the 30-day request, recovered the preserved workspace, and did not substitute inline research or create a duplicate. |
| `PWK-041` | PASS | Current-task envelope, public-ingress, and continuation regressions plus real Markdown artifact | Earlier assistant-only PDF wording did not become a current requirement; current Message/Retry guidance remains authoritative while the worker can still use full conversational context for judgment. |
| `PWK-042` | PASS | Store/service transaction regression, repeated queued Message chain, one current work, one final artifact | Message atomically replaces a still-queued Retry or Message source, retains every never-started user instruction, and produces no hidden runnable sibling. |
| `PWK-043` | PASS | Cached-versus-fresh pressure regressions, installed restart, two final runs and artifacts | Fresh recovery blocks any stale-cache release; true pressure releases safe idle compute oldest-first without mutating completed work or workspace truth. |
| `PWK-044` | PARTIAL | Live escaped outbox cardinality plus pre-claim, post-lease, and execution-boundary regressions | Multiple probes on either capacity path now create one wait transition/callback; only actual runtime invocation resets the episode. A forced post-fix installed capacity-wait episode remains to be captured. |
| `PWK-UC-001` | PASS | Installed Telegram plus headed Web reload | Main stayed usable and both independent objectives remained visible and controllable. |

## Final Installed Acceptance Rerun

The final synthetic, public-safe Telegram sequence used two substantial objectives and one quick
question. Main returned quick C as the exact number `56`, acknowledged one continued A and one new B,
and created exactly two current durable missions. Adding guidance to A did not create a third work
item. Headed Chrome showed both cards once in the Control Panel, retained them after reload, and then
showed both as running after a supported full-stack restart.

Real Docker memory pressure initially kept both missions queued. The installed runtime released only
safe idle workstation compute, freshly remeasured capacity, and admitted both current runs. B first
recorded structured provider quota exhaustion and recovered through the configured trusted fallback;
both final workers ran on the fallback without a model downgrade chosen by the scheduler. A and B
completed once and each produced one accepted terminal callback plus one sent Telegram continuation.

- A artifact: public-safe Markdown comparison, 11,446 bytes, 127 lines, SHA-256
  `f0ec8588b3ae3f2262f61f20c7ba0f44936a9a50b2ba13e370d79b57ff6ccecc`; three strategies,
  tradeoffs, failure recovery, acceptance matrix, and the requested single-worker recommendation;
  no PDF requirement or PDF artifact.
- B artifact: public-safe Markdown checklist, 3,551 bytes, 55 lines, SHA-256
  `6197c3193cd275b8ecddd75ebd98b459eca20424d11873a8599782a7cb0fe3b2`; 34 checks covering
  restart recovery, exactly-one durable completion, callback delivery, and cross-cutting safety.
- Callback/delivery truth: one `run.completed` callback row per current run, each accepted on its
  first HTTP attempt; two Main-authored continuations persisted and two Telegram delivery rows settled
  `sent`. No external email, draft, or account mutation was requested or performed.
- Runtime truth: API, Web, playground, GlassHive runtime, and Glass Drive ports were listening; API
  and Web health checks passed after the final activation.

After the final queued-guidance and wait-episode fixes, the supported current-checkout activation was
run again. A fresh headed-Chrome reload retained Control Panel -> Active Work, completed/delivered
cards, and an active Main composer. API, Web, and playground returned HTTP 200; the two authenticated
GlassHive surfaces returned the expected HTTP 401 to unauthenticated health probes. The active
GlassHive database returned `ok` from its quick check, no foreign-key violations, and contained the
new additive `runtime_invoked_at` column. Recent active GlassHive, LibreChat, and Telegram log tails
contained zero traceback, unhandled/uncaught, bind-conflict, or malformed-database signatures. The
only browser network errors were timestamped during the deliberate restart; the post-reload page had
no product error, only the existing React Router future-version warning.

The same trace exposed 202 and 195 duplicate wait callback intents for A and B before admission. That
was a real defect, not accepted noise. The scheduler still needs to update retry timing indefinitely,
but user transition and callback cardinality are now one per contiguous structured failure class. The
exact regression was RED with two events, then GREEN with two-plus probes, one event, one callback,
zero retry-budget consumption, and no terminal failure. Because the live defect preceded this final
fix, `PWK-044` remains honestly PARTIAL until a post-fix installed forced-wait run is captured.

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `PWK-UC-001` | Send substantial A, substantial B, then quick C without waiting. | Telegram Desktop and headed Chrome | PASS | Two neutral background receipts; quick C returned `169` before the A/B receipts; reloaded Control Panel retained both independent missions and controls. | Exactly two new missions; exact durable-effect acknowledgements; both missions remained truthfully queued for host capacity. | None for this accounting/availability use case. |
| `PWK-UC-001-capacity` | Keep using Main while admitted work waits for capacity. | Telegram Desktop and headed Chrome | PASS | Main answered C; queued cards stayed visible with an explicit host-capacity reason. | Queue state persisted across the Web reload; no background objective became inline prose. | Three simultaneous executions and maximum-load fairness remain `PWK-006`/`PWK-028`. |
| `PWK-UC-001-reload` | Reload Web and reopen Active Work after Telegram admission. | Headed Chrome | PASS | Both current queued/pending cards reappeared at the top with View links and Pause/Stop controls; Main's composer remained usable. | Visible state matched the two durable mission rows and pending delivery state. | Voice and Scheduler parity were not part of this narrow run. |
| `PWK-UC-001-reuse` | Naturally request substantial research/PDF work, ask a quick unrelated question, add a 30-day launch-sequence requirement, then recover from a provider failure without creating a new mission. | Telegram Desktop, headed Chrome, and macOS Preview | PASS | Main acknowledged one background mission, returned the exact quick answer while it ran, accepted additive guidance, truthfully surfaced the provider failure, retried the preserved workspace, and finally returned the completed PDF link. | One exact work record and worker were reused; Message and Retry/Message action receipts settled on that work; the original deep-research, citation, PDF, verification, and review contract remained in the final instruction; the final run completed with a 10-page Letter PDF, 28 tiered sources, and the requested 30-day sequence. Active Work showed `Completed` and `Delivery: delivered` after reload. | The hosted public-link hostname was unavailable in this local-only runtime, so the exact verified local artifact was opened in Preview for the on-screen review step. Remote tunnel reachability remains a separate remote-access gate. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Parallel Work — one always-available Main with durable GlassHive missions.
- Requirement: `docs/requirements_and_learnings/55_Parallel_Work_Orchestration.md`, Product outcome
  and Always-ready Main sections.
- Use case: rapidly submit two independently completable objectives and one quick direct question.
- QA case: `PWK-002`, `PWK-038`, `PWK-039`, `PWK-041` through `PWK-044`, and
  `PWK-UC-001`.
- Expected result: A/B appear exactly once as distinct durable work; Main promptly answers C; a
  superseded response cannot hang or replace the exact receipt with stale inline prose.
- Actual evidence: two Telegram launch receipts in each rapid run; direct quick answers; exact Message
  and Retry receipts on one existing work record in the natural run; zero duplicate delegations during
  reuse/continuation/recovery; a verified 10-page, 28-source PDF in the earlier research run; two
  verified Markdown artifacts in the final restart/pressure run; authoritative completed deliveries;
  and matching reloaded Web state.
- Remaining gap or fix: none for the narrow use case; broader release gates remain open below.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Requirement 55; `PWK-002`, `PWK-038`, `PWK-UC-001`. |
| Code owning path | Which code path owns the behavior? | LibreChat stream manager/store, request controller, capability broker, and delivery interaction path. |
| Docs and nested docs/repos | Which docs or nested repo docs define the expected behavior? | Requirement 55 and the Parallel Work README/case catalog. |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | Jest lifecycle/controller/Telegram/broker/interactions suites, real-Redis manager integration, release-contract pytest, and API build. |
| Local/external prerequisite state | Which required local service, provider, Docker-backed sidecar, OAuth grant, API key, model, or hosted dependency was proven healthy or degraded? | Installed API/Web/playground returned HTTP 200 after supported current-checkout activation; GlassHive remained authenticated; the first provider run degraded truthfully and the preserved-workspace retry completed. |
| Logs | Which sanitized logs confirm or contradict the result? | Test output confirmed exact receipt binding and no-terminal/multi-launch regressions; final active-service tails had zero fatal signatures; post-restart headed Chrome had no product console errors. |
| DB/state/persistence | Which sanitized state, DB count/hash, persisted message, config, or artifact confirms it? | Two new independent missions in the A/B run; one exact work record in the natural run; Message and Retry/Message receipts on that work with zero duplicate delegations; current terminal adjudication marked completed and delivered; final PDF was 10 Letter pages with 28 tiered sources and the requested 30-day sequence; active DB quick/FK checks passed and the additive invocation marker was present. |
| Generated/shipped artifact | Which generated config, compiled bundle, prebuilt helper, or installed artifact was inspected when applicable? | API package rebuilt; supported current-checkout activation selected the same checkout as live stack owner. |
| Real user path | Which browser/computer, Telegram, voice, installer, CLI, MCP/tool, scheduler, or GlassHive path was used like a user? | Installed Telegram Desktop and headed Chrome Control Panel/Active Work. |
| Visual/UX comparison | Does the visible UI/UX or delivered result match the expected behavior and supporting evidence? | Yes: Telegram showed admission, additive update, quick direct reply, truthful failure, same-work retry, and final completed link; reloaded Active Work showed `Completed` and `Delivery: delivered`; the exact PDF opened and rendered cleanly in Preview. |
| Not run / blocked | Which required surface was not run, and why is the result partial or blocked? | Voice, Scheduler, maximum load, clean install, and rollback were not run; they are separate release cases and do not reduce this narrow PASS. |

Supporting evidence cannot replace required user-path evidence. The real Telegram and headed-browser
paths above were run; docs and nested docs, logs, DB/state/persistence, tests, and builds corroborate
those visible results.

## User-Grade Evidence

- Surface exercised: installed Telegram Desktop and headed Chrome Web UI.
- Real user path: submitted A, B, and quick C in Telegram; opened Control Panel and Active Work in
  Web; inspected cards and controls; reloaded the page; reopened Active Work.
- Visible outcome: direct `169` arrived before two neutral background-work acknowledgements; both
  independent mission cards were Queued with an explicit host-capacity reason.
- Expanded/detail state: cards exposed View links, instructions, delivery state, and applicable
  Pause/Stop or Dismiss controls without hiding queued or terminal work.
- Persistence/reload result: after a full reload, both current queued/pending cards reappeared at the
  top with their controls and Main's composer remained available.
- Local/external prerequisite state: API, Web, and playground were healthy; the authenticated
  GlassHive boundary correctly rejected an unauthenticated root request; limited host capacity was
  represented as queueing rather than failure.
- Evidence retrieval classification, if applicable: successful non-empty retrieval; degraded host
  capacity was explicitly classified in the UI.
- Fallback path, if applicable: no substitute user path was needed.
- Backend/log/DB confirmation: exactly two new missions backed the two acknowledgements; persisted
  messages recorded exact durable-effect delivery; the direct answer used ordinary committed truth.
- Existing-work confirmation: the later natural request settled Retry and Message on one existing
  work reference; the natural continuation and recovery stayed on that same reference; none created a
  duplicate delegation, and the same card survived browser reload from running through completed.
- Artifact confirmation: the final PDF rendered as 10 unclipped Letter pages, contained 28 tiered
  sources and the requested 30-day developer-community launch sequence, and was opened on screen in
  Preview. Telegram returned the user-facing review link; its hosted hostname was not reachable from
  the local-only runtime, which is recorded as a separate remote-access limitation rather than hidden.
- Final model/runtime wording check: Main used the same surface-neutral receipt wording for both
  newly admitted missions; on the later reuse path it acknowledged only after exact action receipts
  and did not perform the delegated research inline through a foreground consultant.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for any required visible-UI, detail-state,
  persistence, or wording step.

## Automated Evidence

Final affected-tree results after the surgical fixes and independent-review corrections:

- GlassHive evidence/MCP/account/API/leases/Phase 3/Phase 4/parallel-safety/actions/profile/provider
  plus Store-integrity matrix: 1,265/1,265 passed, including the final repeated-Message,
  capacity-bounce, post-lease wait, and explicit legacy-to-additive-schema regression.
- LibreChat current focused callback/request/Telegram/interactions/broker/orchestration matrix:
  7/7 suites and 209/209 tests passed. The current real-Redis logical-turn, job-store,
  event-transport, manager, and reconnect matrix passed 5/5 suites and 159/159 tests with one
  intentional skip; the known Jest open-handle warning appeared only after the complete passing
  result and the process was then stopped.
- Public Parallel Work contract, QA public-safety, and no-runtime-NLU gates: 10/10 passed.
- Python compilation and scoped repository diff checks: passed.
- Independent Claude review: PASS after executing the capacity-bounce Message chain, a 12-message
  queued chain, 36 pre-claim and 37 post-lease probes, additive legacy migration/idempotence, and the
  invocation-marker CAS boundary. Its three findings were converted to RED regressions before the
  final fixes; no remaining blocker was found in the reviewed lifecycle.

```bash
CI=true npx jest --ci --runInBand --coverage=false src/stream/__tests__/logicalTurn.spec.ts
CI=true npx jest --ci --runInBand --coverage=false controllers/agents/request.test.js server/routes/viventium/__tests__/interactions.spec.js server/routes/viventium/__tests__/telegram.spec.js server/services/viventium/__tests__/GlassHiveCapabilityBroker.spec.js test/app/clients/tools/util/glassHiveOrchestrationTools.test.js
REDIS_URI=redis://127.0.0.1:46379 CI=true npx jest --ci --runInBand --coverage=false src/stream/__tests__/GenerationJobManager.stream_integration.spec.ts src/stream/__tests__/RedisJobStore.stream_integration.spec.ts
npm run build:api
uv run --with pytest --with pyyaml python -m pytest tests/release/test_parallel_work_contract.py tests/release/test_qa_results_public_safety.py -q
```

## Findings

- Defects: mission admission and Main presentation previously had separate commit boundaries, so a
  committed launch could lose its acknowledgement or become stale inline prose. Provider fallback
  could also miss a committed receipt created in a different host request; Message could replace the
  original mission contract or fail on the legacy route; and terminal follow-up could synthesize from
  stale failed conversation state after a newer completed callback. The final acceptance pass also
  found stale assistant context being treated as current artifact requirements, queued Retry followed
  by Message creating a sibling continuation, safe idle Docker workstations retaining scarce compute
  while new work waited, and one callback/outbox row being created on every same-class capacity probe.
- Regressions: receipt presentation now waits for exact durable proof or a true terminal;
  non-superseded turns support several launches plus a direct answer; delivery acknowledgement
  requires the exact receipt and persists across acknowledgement-before-insert ordering. Receipt lists
  now fence provider replay on every surface while singular terminal presentation remains limited to
  response-only external adapters. Same-work Message is additive and current lifecycle terminal truth
  wins during adjudication. Current-task evidence is now host-derived; queued Retry-plus-Message is one
  atomic replacement; pressure relief is limited to freshly verified safe idle compute; and repeated
  same-class scheduler probes update timing without republishing the user transition; real execution
  resets that suppression boundary. Repeated never-started Messages retain every earlier user
  instruction in the single queued replacement, and host-lease/capacity rejection no longer resets
  the wait episode merely because the database row was claimed. Public MCP input cannot forge the reserved constraint source;
  continuation guidance remains authoritative; final-attempt stderr remains classifiable; cached
  resource pressure is freshly disproved before any release; and provider fallback neither replays
  recovered authorship nor masks the primary error when its own preflight is unavailable.
- Flakes: the affected API Jest group passed all 182 tests but retained its known open-handle
  warning; it was stopped only after Jest printed the complete passing result. The real-Redis run
  likewise printed its complete 86-pass, one-intentional-skip result before the lingering Jest
  process was stopped.
- Environment issues: the first Redis command omitted the temporary test port and was stopped before
  rerunning against the intended isolated Redis instance; no result from that misconfigured run is
  counted.
- Residual risks: Parallel Work remains dark. Three-way same-provider execution, maximum-load
  fairness, remaining Voice/Scheduler paths, real two-owner UI isolation, clean install, rollback,
  pins, and shipped-artifact alignment remain separate release gates.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
