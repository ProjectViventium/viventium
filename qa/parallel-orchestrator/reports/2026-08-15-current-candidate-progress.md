# Parallel Work Current-Candidate Progress QA Run - 2026-08-15

## Summary

- Result: PARTIAL. Current source, isolated-runtime, Telegram Desktop, headed Web A/B/C, performance,
  and hostile clean-room slices passed. Required authenticated provider work, all
  running-work controls, remaining audible Steer/Pause/Retry/Dismiss paths, maximum-load fairness,
  scheduler fanout, installed artifacts, clean install, and rollback remain open. The quality-parity
  bank now passes independently on Direct Main, Codex-root, and Claude-root paths.
- Build/source under test: the current dirty workspace candidate. No nested component commit or
  parent pin is claimed by this report.
- Runtime/artifact under test: the isolated local QA runtime restarted from the current checkout;
  this is not the installed production artifact.
- Environment: synthetic non-admin local QA account, headed Playwright, Telegram Desktop, Docker
  clean-room workers, and owner-scoped GlassHive account API.
- Tester: Codex implementation and QA run.
- Related change: the dark Parallel Work implementation defined by
  [`55_Parallel_Work_Orchestration.md`](../../../docs/requirements_and_learnings/55_Parallel_Work_Orchestration.md).

The live GlassHive runtime had one escaped scheduler defect: a `needs_input` worker with queued
follow-ups could repeatedly resubmit a processor and saturate the worker pool. The fix excludes
paused, needs-input, stopping, and terminated workers from retry selection, next-deadline selection,
processor-final resubmission, survivor-monitor resubmission, and direct processor admission.
Focused RED-to-GREEN coverage passed, the complete API module passed, and the restarted runtime
remained between 0 and 2.5 percent CPU across repeated scheduler cycles instead of the prior
sustained multi-core saturation.

The final-source restart also exposed six durable compute-release claims left behind by already
exited exact Docker generations. Recovery kept trying an in-container stop command even though a
fresh inspect proved that each captured generation was already terminal. The runtime now clears
only a matching `dead` or `exited` exact-generation session marker without issuing Docker exec;
missing, mismatched, or live generations remain fenced. The new regression failed before the fix,
then passed with the adjacent exact-generation matrix. The complete 1,437-test GlassHive suite
passed, and the isolated restart reaper reduced the durable pending-claim count from six to zero
with zero active host leases and an `ok` SQLite quick check.

Startup recall verification had a separate false failure: the wrapper counted 16 synthetic QA-only
messages as search-eligible even though the owning Meilisearch plugin deliberately excludes them.
The wrapper now consumes the plugin's `getSyncProgress()` eligibility contract rather than carrying
a stale duplicate filter. The regression and full release suite passed; the same live environment
then reported 301/301 eligible messages and 58/58 conversations indexed, with no backfill required.

Real Telegram Desktop exercised the account-wide toggle, roster, Message, Queue, Resume, Pause
unavailability, Stop confirmation, and Dismiss. Toggle state persisted after runtime restart.
Message, Queue, Resume, Stop, and Dismiss produced the expected visible outcomes. Pause truthfully
reported unavailable because the selected item had already returned to `needs_input`; it was not
recorded as a successful pause. A provider-authenticated running worker is still required for
successful Pause and Steer evidence.

The current headed Web candidate also completed the post-route-fix rapid-input path. It retained one
Alpha ask, one Beta ask, and the later quick-C ask in one canonical conversation; Main produced one
durable background receipt and one Active Work card for each substantial ask, then answered quick C
with the required word `BLUE`. Both mission cards truthfully settled at `needs_input` because the
synthetic QA account had no connected OpenAI or Anthropic account. Reopening the canonical URL kept
both asks, both receipts, and `BLUE` visible, proving route/cache/reload continuity without claiming
provider execution.

A current headed browser call then exercised the real audible Voice path with synthetic microphone
input and an independent local recording. The generic round trip visibly transcribed the request
and audibly returned the requested short phrase. The same call read the account-wide Parallel Work
setting, listed the current roster and available actions, and exercised Queue, Message, Resume, and
Stop. The first Queue attempt exposed a release blocker: Voice said “Queued” while the durable action
receipt recorded Message. The shared provider-facing action contract omitted Queue semantics. A
RED-to-GREEN regression now makes every tool/schema and compact Voice context distinguish all eight
actions and requires an explicitly named action to be reported from durable truth. After a fresh
call, Queue and Message produced their exact completed receipts, Resume audibly reported the real
authorization attention while its receipt recorded re-admission, and Stop settled the selected
synthetic run cancelled with no nonterminal sibling. Ending the browser call visibly reached Ended;
the gateway observed the client disconnect and exited its call process. Running Pause/Steer and
Voice Retry/Dismiss still require suitable provider-backed or terminal fixtures.

After the current-source restart, a second real Telegram Desktop prompt at 16:23 asked only for the
current Active Work state and explicitly prohibited starting or changing work. The visible response
reported Parallel Work on, distinguished two needs-input items from cancelled and failed terminal
items, reported four additional failed launch attempts, and truthfully said that nothing was
running. Mongo contained the one user turn and one assistant response with the same on/no-mutation
wording. GlassHive contained zero new delegations and zero active host leases for this request. The
two contemporaneous GlassHive runs were the expected provider-owned Main/deep-memory conversation
lane, not durable Parallel missions; no Active Work action or delegation was created.

The real clean-room probe used an idle synthetic worker with no active run. It found no ambient
provider/cloud authority, Docker socket, host home mount, protected application state, direct
default route, metadata access, arbitrary external egress, or sibling-worker reachability. The
provider and broker proxy health routes were reachable only through their reviewed mission-network
aliases, and an unauthorised broker call returned 401. Source inspection and the full Docker suite
also prove per-mission internal networks, exact proxy profiles, exact worker generation and image,
private namespaces, exact mounts, read-only root, reviewed tmpfs options, loopback-only published
ports, no ambient secrets, and invocation-local tmpfs grant projection. Host Docker-admin authority
remains outside the worker threat boundary and is not claimed as sandbox-contained.

The live performance slice measured 2,000 focused/known-empty turn preparations at 0.001 ms p95
and 0.223 ms maximum with zero user, known-work, roster, network, or model calls. Fifty authenticated
active-work reads measured 5.832 ms p50, 9.130 ms p95, and 39.457 ms maximum. One durable synthetic
delegation committed in 40.926 ms, and 20 lost-response replays measured 5.666 ms p95 and 7.507 ms
maximum. Durable state contained exactly one delegation, one worker, and one run; missing capability
authorization became nonretryable `needs_input` before any `run.started` event and with zero active
lease. This is supporting performance and idempotency evidence, not a substitute for the post-fix
headed A/B/C user path or a multi-sample unique-delegation p95.

A real explicit host-Codex mission initially exposed a separate local authorization projection bug:
the isolated worker home received the owner-local CLI authorization baseline only when an optional
bootstrap bundle was present. The runtime now copies that baseline for explicit local host-Codex
workers while keeping automatic Parallel clean-room and enterprise workers fail-closed. Focused
tests cover both the positive local path and the enterprise no-copy boundary. The installed CLI then
authenticated, completed a synthetic root mission, and persisted its native root session. Multiple
synthetic child-directed missions still produced no actual child lifecycle, however, so native-child
capability remains false and no child/settling/recursive-Stop pass is claimed.

The same real-provider pass found that explicit local host-Claude mission roots were also isolated
from the owner-local login but, unlike the conversation lane, did not receive the existing
access-only authorization projection. Mission and conversation roots now share that projection;
refresh authority is never forwarded, and enterprise mode rejects missing server-owned
authorization without consulting local owner state. Deterministic boundary tests passed, followed
by current installed-CLI root, resume, and plugin-isolation smokes. This proves the current root and
resume path, not the still-open background-session roster, restart, targeted native controls, or
recursive Stop gates.

The versioned quality bank now passes across all three supported paths. Four exact synthetic prompts
ran through real Telegram Main and fresh installed Codex and Claude CLI roots. A randomized blind
review scored all 12 answers at least 4/5 on Intelligence, Relevance, Usefulness, and Alignment, with
no format or safety violation. The first review caught an internal Markdown `FINAL REPORT` delimiter
in one Claude payload; shared parser/callback handling was fixed with RED-to-GREEN regressions, and a
fresh real Claude root reran clean. Per-path scores, latencies, sanitized findings, and the
substitution check are recorded in the dedicated
[`quality-parity` report](2026-08-15-quality-parity.md).

Real running-root interrupt/restart probes now pass for both installed providers. Each host root
entered `running`, exact interrupt settled the run as `interrupted`, and a fresh service instance
preserved that terminal state without a live PID or process resurrection. Startup may normalize the
idle stopped harness to `paused`; it did not revive the run. This advances root control and restart,
with the separate live-child recursive Stop result recorded below.

The current installed Claude CLI then emitted one real native child start/completion lifecycle
through GlassHive. A second run stopped the root while its child was still active: the exact run
settled `interrupted`, active child count reached zero, and restart preserved both terminal truth and
zero active children with no PID resurrection. This closes current-provider child projection and
recursive root Stop/restart; visible Web/Telegram topology, unrelated-session isolation, and targeted
native Message remain.

A fresh sanitized agent A/B/C comparison was also completed before any possible sync. The isolated
QA environment has no dedicated tracked agent or adjacent LibreChat source bundle, so its live state
was compared with the canonical tracked local bundle. Four live agent records differ from that
source: protected fields include Main instructions/tool options, handoff tools and voice parameters,
and model parameters. All 15 compared source records also differ from the current working-tree
version across instructions, tools, provider/model/fallback settings, edges, recursion/background
settings, and related fields. No push was attempted; this breadth requires intentional reconciliation
and a reviewed, environment-specific source before any live sync.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `PWK-001` | PARTIAL | Real Telegram toggle off/on, roster refresh, and restart persistence | Post-fix Web account login and cross-surface reload remain. |
| `PWK-004` | PARTIAL | Current restarted Telegram roster distinguished needs-input, terminal, overflow, and no-running truth | Stale/unavailable Telegram state plus post-login Web/Voice parity remain. |
| `PWK-002` | PARTIAL | Current headed A/B/quick-C retained one ask and one durable card per substantial objective, answered `BLUE`, and persisted after canonical-URL reload | Provider execution and running-work correlation remain blocked on provider reconnect. |
| `PWK-003` | PARTIAL | One live commit plus 20 stable replays produced exactly one delegation/worker/run | Real Telegram/media lost-response delivery remains. |
| `PWK-005` | PARTIAL | Real Telegram controls plus audible Voice Queue, Message, Resume-to-needs-authorization, and Stop; every accepted action matched its durable receipt | Successful running Pause/Steer, Web parity, Voice Retry/Dismiss, and injected user-path races remain. |
| `PWK-006` | PARTIAL | Scheduler spin fixed; zero active lease for needs-input work; broad capacity automation | Three same-provider missions plus visible overflow remain. |
| `PWK-009` | PARTIAL | Real installed host-Codex root+resume pass; running-root Stop persisted `interrupted` across service restart with no process resurrection | The installed model did not create a real child in repeated synthetic child-directed missions; child projection, settling, and recursive child Stop remain. |
| `PWK-010` | PARTIAL | Real installed host-Claude root+resume+plugin isolation and child lifecycle pass; live-child Stop reached zero active children and persisted across restart | Visible Web/Telegram topology, unrelated-session isolation, and targeted native Message remain. |
| `PWK-016` | PARTIAL | Focused 0.001 ms p95 with zero calls; active-work 9.130 ms p95; one durable acceptance 40.926 ms | Toggle timing and unique-delegation p95 still require headed/current-candidate evidence. |
| `PWK-017` | PARTIAL | Current audible call: setting, roster/actions, Queue, Message, truthful Resume attention, Stop, and call end; no unsolicited call | Running Steer/Pause plus Retry/Dismiss voice paths remain. |
| `PWK-018` | FAIL | Current source is not committed/pinned/built into the installed artifact | Clean install and rollback remain unrun. |
| `PWK-020` | PARTIAL | Live account API replay was stable and insert-once; crash/restart automation is green | Lost-response UI retry through Web/Telegram remains. |
| `PWK-024` | PARTIAL | Missing authorization entered durable needs-input with no provider start or active lease; scheduler remained idle | Repeat the historical resource-recovery artifact branch on the final candidate. |
| `PWK-025` | PARTIAL | Real hostile worker probe passed environment, mount, socket, egress, metadata, peer, broker-auth, and proxy-health checks | Run concurrent cap and user-owned mission/tool success after provider reconnect. |
| `PWK-026` | PASS | Clean-seed/reseed automation plus live current-source restart; exactly one agent retained the server-owned orchestration declaration | No duplicate, stripped, or false declaration was present. |
| `PWK-029` | PARTIAL | Real Telegram action buttons and confirmation path worked without duplicate effects | Tampered, expired, cross-user, second-tap, media, and uncertain-response user paths remain. |
| `PWK-031` | PASS | Real Telegram Main plus fresh installed Codex/Claude roots; randomized blind 12-answer I/R/U/A review | Every answer independently scored at least 4/5 in each dimension with no format or safety violation. |
| `PWK-035` | PASS | Route/cache/duplicate automation plus headed canonical A/B/C navigation, visible content, and reload persistence | The route stayed canonical and did not lose either durable receipt or quick-C output. |
| `PWK-036` | PARTIAL | Validation and Phase-B automation remain green; live durable acceptance avoided 422 | Real rapid-Web/card/callback correlation remains. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `PWK-UC-001` | Toggle Parallel Work and rapidly send A, B, and quick C. | Telegram Desktop and headed Web | PARTIAL | Telegram toggle persisted after restart. Web retained one Alpha ask, one Beta ask, one durable card for each, and the exact quick answer `BLUE` after canonical-URL reload. | Account state, canonical conversation state, two distinct needs-input work cards, and restart/reload truth agreed. | Provider-authenticated execution, running controls, and concurrency remain. |
| `PWK-UC-003` | Control exact work. | Telegram Desktop and audible headed Voice | PARTIAL | Telegram passed Message, Queue, Resume, Stop, Dismiss, and truthful unavailable Pause. Voice passed Queue, Message, Resume-to-needs-authorization, Stop, and call end. | Action receipts and final work state agreed with every accepted visible or spoken result. | Successful running Pause/Steer plus Web, Voice Retry/Dismiss, and lost-response parity remain. |
| `PWK-UC-004` | Encounter missing authorization and recover. | GlassHive account API and runtime | PARTIAL | One accepted item became explicit needs-input rather than claiming execution. | Exactly one durable work record, zero start event, and zero active lease. | Reconnect and Resume through the user surface remain. |
| `PWK-UC-006` | Run and inspect native Codex and Claude child work. | Real installed Codex and Claude CLIs through GlassHive | PARTIAL | Both roots authenticated, completed, resumed, and stopped while running. Claude projected one real child, and recursive Stop reached zero active children across restart. Codex still emitted no real child. | Native root sessions persisted; Claude plugin isolation and child lifecycle passed; restart showed no process resurrection; repeated Codex child-directed attempts contained no child projection. | Visible topology, unrelated-session isolation, targeted native Message, and a future Codex child-capable build remain. |
| `PWK-UC-007` | Probe automatic mission isolation and peer-spawn safety. | Real Docker mission boundary | PARTIAL | Reviewed proxies worked; host, peer, metadata, arbitrary egress, and unauthorised broker access did not. | Fresh inspect, network membership, mount, namespace, env, and grant evidence agreed. | Provider-backed tool success and concurrent lease cap remain. |
| `PWK-UC-008` | Install, enable, inspect, and roll back. | No installed acceptance run | BLOCKED | None. | Current nested commits, pins, built bundle, and installed runtime are not aligned. | Commit, pin, build, clean install, upgrade, and rollback. |
| `PWK-UC-009` | Keep Main and controls responsive under load. | Live isolated runtime plus Telegram | PARTIAL | Telegram controls remained responsive and the scheduler no longer saturated CPU. | Full API automation passed; repeated live CPU samples stayed near idle. | Maximum admitted provider load, fairness, 429, and Main latency remain. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: account-wide Parallel Work with durable isolated missions and exact controls.
- Requirement: focused turns add no network/model latency; accepted work is insert-once; blocked work
  does not consume execution capacity; automatic missions cannot inspect host or peer authority.
- Use case: toggle and control work in Telegram, submit/replay one synthetic delegation, inspect
  blocked runtime truth, and probe the real clean-room boundary.
- QA case: `PWK-001`, `PWK-003`, `PWK-005`, `PWK-016`, `PWK-020`, `PWK-024`, `PWK-025`, and
  `PWK-029`.
- Expected result: fast focused/Main paths, one durable receipt per source event, truthful needs-input,
  no processor spin, exact controls, and no host/peer authority exposure.
- Actual evidence: the measured performance and replay limits passed; one durable needs-input record
  had no start event or active lease; Telegram and exercised audible Voice actions matched durable
  receipts; the clean-room hostile probe failed closed; the repaired live scheduler stayed near idle.
- Remaining gap or fix: reconnect the test provider, run live provider missions, finish
  controls/Voice/scheduler/load/native gates,
  then align commits, pins, artifacts, install, and rollback.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement and QA cases are being proven? | Requirement 55 and the case rows above. |
| Code owning path | Which code owns the behavior? | Core turn context/account/action services; GlassHive account API, store, processor scheduler, profile runtime, bootstrap, and Docker sandbox. |
| Docs and nested docs/repos | Which sources define expected behavior? | Requirement 55, workstation sandbox requirement 48, the Parallel Work case catalog, and nested Core/GlassHive tests. |
| Scripts or harnesses | What exercised it? | Headed Playwright, Telegram Desktop, a headed Voice call with temporary synthetic microphone audio, authenticated account-API timing probe, read-only DB correlation, real Docker hostile probe, and automated suites. |
| Local/external prerequisite state | Which dependency was healthy or degraded? | Core, GlassHive, proxies, Docker, Telegram, and Voice were live. The restarted service-authenticated readiness probe reported policy version 1, isolated ready, host missions disallowed, and zero active host missions. The synthetic QA provider connection still needs human reconnect. |
| Logs | What confirms or contradicts the result? | Sanitized runtime sampling showed no renewed processor saturation; no provider-start event existed for missing authorization; Voice tool, TTS, disconnect, and process-exit events agreed with the spoken result and clean call shutdown. |
| DB/state/persistence | What confirms it? | One delegation/worker/run after 20 replays, needs-input state, zero active lease, exact action receipts, persisted Telegram preference, and exactly one retained agent orchestration declaration after restart. |
| Agent source/live drift | Was A/B/C reviewed before any sync? | Four protected live-vs-canonical agent records and 15 canonical-vs-working-tree records differ; QA-specific source files are absent, so no push occurred. |
| Generated/shipped artifact | What was inspected? | Current isolated generated runtime only; installed production artifacts and parent pins remain stale. |
| Real user path | What was used like a user? | Telegram Desktop, headed Web, and a headed audible Voice call; provider reconnect remains manual. |
| Visual/UX comparison | Did visible truth match state? | Yes after the Voice Queue/Message contract fix: Telegram and Voice results matched exact durable receipts; unavailable/needs-authorization states were not reported as running. |
| Not run / blocked | What remains? | Web A/B/C, running Pause/Steer, remaining Voice controls, scheduler fanout, max load, clean install, and rollback. |

## User-Grade Evidence

- Surface exercised: Telegram Desktop, headed Playwright Web, and a current headed audible Voice
  call with temporary synthetic microphone audio.
- Real user path: toggled Parallel Work, refreshed the Telegram roster, sent Message and Queue
  actions, resumed needs-input work, attempted Pause, confirmed Stop, dismissed terminal work, and
  restarted the isolated stack. In the headed Voice call, the user listed work/actions, queued a
  follow-up, sent guidance, resumed a named item, stopped another named item, and ended the call.
- Visible outcome: accepted Telegram actions changed the selected card; the raced Pause
  reported unavailable; Stop required confirmation and settled cancelled; Dismiss removed only the
  terminal item. Voice spoke the roster/action choices and each result; after the contract fix,
  Queue and Message produced distinct durable action receipts, Resume truthfully requested
  authorization, Stop cancelled the selected work, and the call ended without a lingering process.
- Expanded/detail state: roster and action affordances refreshed after each action.
- Persistence/reload result: toggle state survived restart.
- Local/external prerequisite state: Telegram and Docker were healthy; the synthetic QA provider
  connection is missing or expired.
- Evidence retrieval classification: capability authorization missing, distinct from provider
  execution failure or successful-empty work.
- Fallback path: no unsafe host or ambient-credential fallback was used.
- Backend/log/DB confirmation: action receipts, one insert-once delegation, no run-start event, no
  active lease, Voice tool/latency events, gateway process exit, and stable CPU matched the visible,
  spoken, and API truth.
- Final model/runtime wording check: no exercised path claimed running/completed when durable state
  was needs-input or unavailable.
- Substitution check: automation, API responses, logs, DB rows, and source support the result but do
  not replace the required post-login Web, remaining Voice controls, scheduler, install, or rollback
  paths.

## Automated Evidence

```bash
cd viventium_v0_4/GlassHive
runtime_phase1/.venv/bin/python -m pytest runtime_phase1/tests/test_api.py -q
runtime_phase1/.venv/bin/python -m pytest runtime_phase1/tests -q

cd viventium_v0_4/LibreChat
CI=true npm test -- packages/api
```

- Complete GlassHive runtime: 1,437 collected, exit 0, intentional opt-in live-environment
  skips; the native Codex/Claude lifecycle and restart cases also passed separately against the
  installed CLIs.
- Glass Drive UI: 113/113 passed in its package-aware import environment.
- Current GlassHive API module after the processor-admission fix: PASS.
- Current LibreChat API package: 118 suites, 2,988 passed, one intentional skip.
- Current LibreChat data-provider package: 817 passed, one intentional skip.
- Current LibreChat data-schemas package: 416 passed, three intentional skips.
- Focused current stream gates passed 142/143 across in-memory logical-turn and real-Redis manager,
  transport, and store suites; the one skipped case is intentional.
- Telegram runtime: 438 passed.
- Voice gateway and voice tools: 500 plus 84 passed.
- Full LibreChat API shards: 4,149 passed with 19 intentional skips.
- Current provider-facing Parallel Work action/context matrix after the Voice Queue-versus-Message
  correction: 18 suites and 302 tests passed.
- Full LibreChat client: 1,452 passed.
- Current production build: all four shared packages rebuilt successfully; the production client
  rebuilt successfully with post-build verification, and its generated bundles contain the
  Parallel Work projection.
- Parent config-compiler suite: 190/190 passed with the current candidate.
- Parent release suite: 1,343 passed with 30 intentional environment/platform skips on the final
  current-tree pass.

## Findings

- Defects: fixed the live needs-input queued-follow-up processor spin, direct executor-slot waste,
  exact exited-generation recovery loop, and false local-search parity failure.
- Regressions: none in the affected API and complete GlassHive suites.
- Flakes: none in the final focused scheduler runs.
- Environment issues: human sign-in and connected-provider reconnect are still required for the
  post-fix Web and provider-backed mission paths.
- Residual risks: every case still marked PARTIAL, FAIL, BLOCKED, or NOT RUN in the living catalog;
  current source builds pass, but it is not yet committed, pinned, installed, or rollback-proven.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
