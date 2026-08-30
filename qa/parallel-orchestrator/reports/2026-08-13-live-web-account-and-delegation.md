# Parallel Work Live Web Account, Delegation, and Capacity QA Run - 2026-08-13

## Summary

- Result: PARTIAL overall. The specific live restart-recovery/exact-artifact branch in `PWK-024`
  passed on the then-running source, but later Store, Service, MCP, and Web changes make it historical
  supporting evidence rather than a current-candidate PASS. Broader capacity/concurrency acceptance
  remains partial.
- Build/source under the live run: the then-active Parallel Work source, including the Core
  delegation facade and raw MCP response repair, compiled MCP endpoint propagation, local
  idle-reaper policy, and the GlassHive passive-reconciliation repair. Later owning-source changes
  are covered only by automation until the post-fix live rerun.
- Runtime/artifact under test: isolated local QA Core, GlassHive runtime, and Docker mission image.
- Environment: synthetic non-admin account in an isolated local QA stack; headed Playwright Web.
- Tester: Codex implementation run with independent lifecycle and release-review passes.
- Related change: the dark Parallel Work implementation defined by
  [`55_Parallel_Work_Orchestration.md`](../../../docs/requirements_and_learnings/55_Parallel_Work_Orchestration.md).

The post-fix exact-artifact mission recovered automatically, auto-admitted at 13:33:30, completed at
13:34:15, and released its lease as `runtime_returned`. `acceptance.txt` was exactly 30 bytes, with
no trailing newline or period, and SHA-256
`fe61354cb902c3e3b35afd12b5cd8c7d2a9bec321ee6aa323231ff55837c64ed`. Headed Web showed one
authoritative receipt, one Completed card, and a fresh read-only View reporting
`workstation-desktop · ready`; receipt, card, and View truth persisted after reload. No active leases
remained.

The rapid-input probe issued only objective A because the route remounted before B or C could be
sent. A produced exactly one user message, one authoritative receipt, one origin/external binding,
and one GlassHive delegation. It completed at 13:41:09 and wrote `alpha.txt` as exactly 22 bytes
containing `alpha mission complete`, with no trailing newline and SHA-256 prefix `e00f3340`. B, C,
and the quick-C response path were never issued. This is narrow exactly-once evidence for A, not a
pass for rapid A/B/C or multi-mission concurrency. Voice and every user-level work control were
untouched.

Post-probe source work repaired each observed authority/lifecycle branch with a dedicated
regression: canonical route plus message-cache rollover, delayed-receipt disposal, original-job
identity on lost-response retry, exact superseded-provider cancellation, presentation-only Phase B
with case-insensitive bootstrap-header removal, and bounded delegation metadata. The final focused
client/controller/provider/Phase-B audit passed 150/150 and the full client passed 1,447/1,447.
Telegram's route suite passed 46/46 after its stale action-service test double was corrected. The
real post-fix A/B/C browser sequence has not run because the isolated account login still requires
manual credential entry; these automated passes do not change the PARTIAL user-path verdict.

Phase 1–4 lifecycle repairs now automate durable claim, startup handshake, exact control, lifecycle
effect, callback, and revocation replay ownership. Current supporting automation includes the Phase 4
startup file at 25/25, an independent two-store startup/replay audit, and green API 240, MCP 148,
UI 107, plus affected lifecycle/account/delegation suites. These automated results do not replace
the remaining real-surface gates.

The final source-only security/admission pass added evidence that did not exist during the headed
run: a disposable real-Redis matrix passed 110 tests with one intentional skip, the in-memory
logical-turn matrix passed 30/30, and the request controller passed 23/23; the automated local
HTTP/WebSocket/MCP owner matrix passed 390/390; the combined clean-room bootstrap/profile/Docker
matrix passed 390/390; and Anthropic structural debug logging passed 95/95 without prompt, tool,
model, provider, header, or credential values. These results move the corresponding cases only to
PARTIAL. No current Telegram retry, real two-account surface, enterprise-owner, hostile container,
or provisioned proxy-network acceptance was run.

After those source edits froze, the complete current-tree GlassHive gate passed 1,328 tests with
five intentional skips (1,333 collected).

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `PWK-001` | PARTIAL | Headed Web toggle, successful preference writes, reload, restart, and canonical account state | Web passed in both directions; Telegram remains blocked. |
| `PWK-002` | PARTIAL | A produced one user message, one receipt, one binding, one GlassHive delegation, and one exact completed artifact | Route remount prevented B and C from being issued; quick-C and multi-mission behavior remain unrun. |
| `PWK-003` | PARTIAL | In-memory and real-Redis first-owner/create-once, stale-receipt, active-capacity, and controller lost-response automation | Real Telegram/media duplicate delivery and current-candidate post-commit retry remain unrun. |
| `PWK-004` | PARTIAL | One authoritative receipt, Completed card, fresh read-only View showing `workstation-desktop · ready`, and reload persistence | Stale, unavailable, overflow, Telegram, and Voice branches remain. |
| `PWK-006` | PARTIAL | Structured capacity wait, restart, automatic admission, terminal artifact, `runtime_returned` lease release, and zero active leases | The recovery branch passed; three-way same-provider concurrency, overflow order, and maximum-load behavior were not run. |
| `PWK-008` | PARTIAL | Automated local two-owner HTTP, terminal WebSocket, and MCP courier fail-close matrix | Real two-account Web/Telegram, enterprise parity, and callback/delivery isolation remain unrun. |
| `PWK-016` | BLOCKED | No release-grade percentile or focused-mode network trace was captured | The browser remained usable, but that observation cannot prove the exact latency budgets. |
| `PWK-018` | FAIL | Source/runtime inspection plus the separate installed Telegram report | Installed-artifact parity, parent pins, and clean install remain unproven. |
| `PWK-019` | PARTIAL | Authoritative receipts correlated one-to-one with their origin/external binding and GlassHive delegation; Completed/View truth persisted | Durable-receipt truth passed; the adversarial mission-root peer-spawn probe remains unrun. |
| `PWK-022` | PARTIAL | Trusted local account identity is enforced across HTTP, terminal WebSocket, and MCP courier compatibility paths | Enterprise deployment and exhaustive live legacy-route evidence remain unrun. |
| `PWK-024` | PARTIAL | Historical automatic restart recovery, 13:33:30 admission, 13:34:15 completion, exact 30-byte artifact/hash, and `runtime_returned` release | The run predates later owning-source edits. Repeat it on the current candidate before restoring PASS; `PWK-006` also retains broader capacity/concurrency gaps. |
| `PWK-025` | PARTIAL | Earlier automatically delegated Docker missions completed and released all leases. Current source additionally has 390/390 bootstrap/profile/Docker automation for immutable admission, no-follow purge, inert generation reservation, exact tmpfs options, exact-ID startup, and fresh policy reattestation. | The required full-profile provider/broker proxies, per-mission peer isolation, and generation-bound grant substrate are not provisioned; hostile real-container, raw-egress, peer-inspection, owner, and concurrent-cap probes remain. |
| `PWK-035` | PARTIAL | Canonical route/cache and duplicate-retry regressions; full client 1,447/1,447 | Automated behavior is green; post-fix headed A/B/C plus reload is waiting on manual login. |
| `PWK-036` | PARTIAL | Exact supersession, mixed-case Phase-B bearer stripping, no-tools request, and bounded metadata validation | Source/automation is green; real mission/card/callback correlation remains to be rerun. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `PWK-UC-001` | Enable Parallel Work and rapidly issue A, B, and quick C while continuing to use Main. | Headed Playwright Web | PARTIAL | A appeared once and completed with one receipt. | Exactly one user message, one binding, one GlassHive delegation, and one 22-byte `alpha.txt` correlated. | Route remount meant B, C, and quick-C were never issued; Telegram remains blocked. |
| `PWK-UC-002` | Open Active Work empty, after terminal work, after refresh/restart, and in degraded or rollback states. | Headed Playwright Web | PARTIAL | The authoritative receipt, Completed card, and fresh read-only View persisted after reload. | Core and owner-scoped GlassHive state agreed; View reported `workstation-desktop · ready`. | Stale/unavailable, rollback, Telegram, and Voice remain. |
| `PWK-UC-004` | Launch work, encounter capacity, and recover without bypassing the guard. | Headed Playwright Web plus GlassHive runtime | PARTIAL | The mission recovered, completed, and exposed its terminal card/View. | It auto-admitted at 13:33:30, completed at 13:34:15, released as `runtime_returned`, and produced the exact 30-byte artifact/hash. | Upload/media, connected-account, auth, approval, expiry, and provider-quota branches remain. |
| `PWK-UC-007` | Launch automatic isolated work without granting a mission root peer authority. | Headed Playwright Web plus Docker mission | PARTIAL | Completed mission state appeared once in Active Work and opened a fresh read-only View. | Receipt, origin binding, Docker delegation/work/lease, completion, release, and zero active leases correlated. | Adversarial root spawn, hostile environment, forged mode, unsafe host, concurrent caps, and two-owner probes remain. |
| `PWK-UC-008` | Install, enable, inspect shipped layers, and roll back. | Isolated runtime inspection; no clean installer run | BLOCKED | The isolated Web runtime was usable; no clean-install or rollback UX was exercised. | Generated runtime endpoint/reaper settings were inspected, but source, pins, built, installed, and clean-install identities are not aligned. | Run supported clean install and rollback after all artifacts are pinned. |
| `PWK-UC-009` | Keep Main/controls available while work waits at capacity. | Headed Playwright Web plus scheduler state | PARTIAL | The accepted mission retained structured capacity truth and later completed automatically. | Restart recovery, exact artifact, terminal release, and zero active leases passed. | Maximum-load responsiveness, exact user controls, fairness, rapid multi-mission load, and provider `429` remain. |
| `PWK-UC-012` | Disable automatic admission while existing work remains visible and controllable across restart. | No rollback user path | BLOCKED | Existing cards survived ordinary restart, but rollback was not exercised. | Retained work state supports only ordinary restart continuity, not rollback acceptance. | Run the installed rollback drill with live work and callback/control verification. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: account-wide Parallel Work with authoritative Active Work and isolated durable missions.
- Requirement: Main may acknowledge delegation only after a durable receipt, and resource-constrained
  work must remain structured, retryable, and recoverable across restart.
- Use case: enable Parallel Work in Web, launch synthetic work, inspect its board/detail state, launch
  one exact-artifact mission through constrained capacity and restart, then attempt rapid A/B/C.
- QA case: `PWK-001`, `PWK-002`, `PWK-004`, `PWK-006`, `PWK-019`, `PWK-024`, `PWK-025`,
  `PWK-035`, and `PWK-036`.
- Expected result: one provider call creates one durable mission and receipt; constrained work waits
  without false terminality and resumes automatically after capacity and restart.
- Actual evidence: the exact-artifact mission waited truthfully, recovered across restart,
  auto-admitted at 13:33:30, completed at 13:34:15, produced the expected 30-byte artifact/hash, and
  released as `runtime_returned`. The A-only probe also completed exactly once, but route remount
  prevented B and C from being issued.
- Remaining gap or fix: retain the exact restart/artifact run as historical regression evidence, then
  repeat it on the current candidate before restoring `PWK-024` to PASS. Separately run B/C/quick-C
  and the full capacity/concurrency, control, surface, isolation, and release matrices. A-only
  evidence must never be promoted into a three-input concurrency pass.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | The durable receipt, roster, capacity wait, and restart contracts in requirement 55 and `PWK-001/004/006/019/024/025`. |
| Code owning path | Which code path owns the behavior? | Core's provider tool projection, raw MCP decoder, account binding, and GlassHive proxy; compiler/launcher endpoint propagation; GlassHive delegation, lease, scheduler, reconciliation, and idle reaper. |
| Docs and nested docs/repos | Which docs or nested repo docs define the expected behavior? | Requirement 55, the workstation sandbox runtime requirement, Agent Streaming continuity, and this living case catalog. |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | Headed Playwright browser flow, supported isolated-stack lifecycle, release-contract checks, the Phase 4 startup file, independent two-store audit, and API/MCP/UI suites. |
| Local/external prerequisite state | Which required dependency was healthy or degraded? | Docker and the QA services were healthy; measured host memory headroom was below the configured admission floor while one retained Docker worker still consumed real resources. |
| Logs | Which sanitized logs confirm or contradict the result? | The artifact mission auto-admitted at 13:33:30, completed at 13:34:15, and released as `runtime_returned`; the A-only mission completed at 13:41:09. |
| DB/state/persistence | Which sanitized state confirms it? | Each issued objective had one authoritative receipt and one matching origin/external binding and GlassHive delegation. Terminal board/View state persisted after reload, and active leases were zero. |
| Generated/shipped artifact | Which generated or installed artifact was inspected? | The isolated runtime received its configured GlassHive endpoint and local idle-reaper settings. The workspace API package build predates the final stream source, the active installed checkout is older and lacks sampled Parallel Work files, and the parent still pins older LibreChat and GlassHive commits. Clean install and rollback remain unrun. |
| Real user path | Which surface was used like a user? | A synthetic non-admin account used Settings, chat, Active Work, refresh/restart, and View in a real headed Playwright browser. |
| Visual/UX comparison | Did visible behavior match supporting evidence? | Yes: one authoritative receipt, a Completed card, and a fresh read-only View reporting `workstation-desktop · ready` agreed with durable state and persisted after reload. |
| Not run / blocked | Which required surface was not run? | B, C, quick-C, every user-level work control, Telegram, audible Voice, scheduler delivery, rollback, owner isolation, hostile sandbox, concurrent-capacity load, pins/shipped artifacts, and clean install remain blocked or partial. |

Supporting logs, DB/state/persistence, API responses, source inspection, and automated tests cannot
replace required user-path evidence; that is why the unrun branches remain `BLOCKED`, `PARTIAL`, or
`FAIL`.

## User-Grade Evidence

- Surface exercised: headed Playwright Web against the isolated local QA runtime.
- Real user path: opened Settings > Account, toggled Parallel Work both ways, reloaded and restarted,
  submitted synthetic delegation prompts, read the authoritative receipt, opened Active Work, and
  followed the read-only View.
- Visible outcome: the exact-artifact mission showed one authoritative receipt, one Completed card,
  and a fresh View reporting `workstation-desktop · ready`. The later rapid probe issued A once and
  showed one receipt; B and C were never issued because the route remounted.
- Expanded/detail state: the completed work's View loaded through the supported proxy and matched its
  board state without exposing raw internal IDs, paths, prompts, or provider diagnostics.
- Persistence/reload result: preference, receipt, Completed card, and fresh View truth persisted
  after reload. The capacity-waiting artifact mission recovered automatically across restart.
- Local/external prerequisite state: Docker and required local services were available; the resource
  guard truthfully denied admission because available memory could not satisfy the configured floor.
- Evidence retrieval classification, if applicable: local prerequisite degraded by real resource
  pressure; this was not a successful-empty result, provider outage, or fabricated headroom.
- Fallback path, if applicable: no fallback or host-mode bypass was allowed; the mission remained
  durably queued.
- Backend/log/DB confirmation: sanitized counts correlated each issued objective to one receipt,
  origin/external binding, GlassHive delegation, terminal state, lease release, and visible state.
  Active leases were zero after completion.
- Final model/runtime wording check: Main used accepted/dispatched wording only after the durable
  receipt. The UI used neutral lifecycle wording, then showed Completed only after terminal truth.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for any required visible-UI, detail-state,
  persistence, or wording step.

## Automated Evidence

Public-safe command shapes used during this implementation and QA pass:

```bash
python3 -m pytest tests/release/test_config_compiler.py -q
python3 -m pytest tests/release/test_stable_dev_runtime_workflows.py -q
python3 -m pytest tests/release/test_parallel_work_contract.py -q
python3 -m pytest tests/release/test_qa_operating_contract.py -q

cd viventium_v0_4/GlassHive
python3 -m pytest runtime_phase1/tests/test_phase4_lifecycle_effects.py -q
python3 -m pytest runtime_phase1/tests/test_api.py -q
python3 -m pytest runtime_phase1/tests/test_mcp_server.py -q
```

- Phase 4 startup lifecycle-effect file: 25 tests passed.
- Independent two-store startup/replay audit: PASS.
- In-memory logical-turn lifecycle: 30/30; disposable real-Redis stream suites: 110 passed with one
  intentional skip; request controller: 23/23. The Redis Jest runner reported its existing
  post-success open-handle warning after all assertions passed.
- GlassHive API suite: 240 tests passed.
- GlassHive MCP suite: 148 tests passed.
- UI suite: 107 tests passed.
- Complete GlassHive runtime tree: 1,328 passed with five intentional skips (1,333 collected).
- Clean-room bootstrap/profile/Docker: 390/390.
- Affected account, delegation, lifecycle, callback/effect, and runtime suites: green.
- Canonical route/cache plus original-job duplicate retry: focused client/controller tests green;
  adjacent client SSE/route tests 62/62 and full client 1,447/1,447.
- Exact supersession and presentation-only Phase B, including mixed-case bearer headers: final
  independent focused audit 150/150.
- Telegram canonical action route: 46/46; shared work-action service: 14/14. The prior two 502s were
  a stale test double missing the action executor's snapshot-invalidation seam, not product errors.
- A monolithic full-backend Jest rerun exhausted its Node heap after a long all-green prefix. The
  deterministic two-shard rerun then completed: shard 1 passed 2,073 tests with 1 skipped; shard 2
  passed 2,025 tests with 18 skipped. Shard 2 reported lingering Jest open handles after completing
  all tests, but exited successfully when the idle runner was interrupted; that runner-lifecycle
  warning remains separate from the passing assertions.
- Parallel Work release contract and public-safety checks: 5/5 passed. Repository QA operating
  contract: 20/23 passed and 3 failed. The three failures are real release-governance blockers:
  this feature's QA folder is still untracked,
  central QA ownership/tracking is incomplete, and legacy dated reports still violate the current
  v2 template gate. This task does not stage or commit, so none is waived. The target report's own
  v2 evidence-template validator passed.
- Frozen delivery-layer audit: the workspace `packages/api/dist` predates the final stream-lifecycle
  source. The active installed runtime uses the older pinned checkout, lacks sampled Parallel Work
  service/test/doc files, and its immutable GlassHive database quick-check reports corruption. The
  candidate was therefore not substituted into that running artifact for user-path QA.
- Direct public-safety and relative-link scans over the four changed documents passed. No code, live
  runtime, component pin, or commit was changed by this documentation update.

## Findings

- Defects: earlier live QA found three distinct owning-path defects rather than accepting prose as
  success: the Main facade was filtered from the direct provider, raw MCP results were decoded in the
  wrong shape/against the wrong local endpoint, and restart reconciliation stranded a structured
  capacity retry while refreshing the idle-reap clock. All three owning branches now have real
  browser evidence; the repaired restart branch also produced the exact artifact and released its
  lease.
- Regressions: an earlier capacity run incorrectly coupled feature availability to a consumed slot;
  the post-repair browser rerun kept availability true. Restart-stranding remains the reusable
  `PWK-024` regression, now historical PARTIAL evidence pending the post-change live rerun.
- Harness limitation: the rapid probe's route remounted after A. B and C were never issued, so the
  A-only exactly-once result cannot be interpreted as evidence about three-input ordering or mission
  concurrency.
- Environment issues: the retained completed Docker worker consumed enough real memory to block the
  later mission. This correctly triggered structured capacity wait and exposed the missing local
  idle-reaper/restart lifecycle; the post-fix run recovered and left zero active leases. Telegram
  still lacks a safe independent QA poller.
- Residual risks: B/C/quick-C, every user-level work control, audible Voice, Telegram, scheduler
  delivery, hostile isolation, concurrent caps, two-owner security, rollback, pin/build/installed
  artifact parity, database repair, and clean install remain unaccepted. The deployment flag stays
  false.

An earlier exact-file QA instruction included punctuation inside its own authoritative payload, so
the resulting 31-byte file matched that ambiguous instruction. It was not counted as a product
failure. The corrected unambiguous acceptance case passed with exactly 30 bytes, no trailing newline
or period, and SHA-256
`fe61354cb902c3e3b35afd12b5cd8c7d2a9bec321ee6aa323231ff55837c64ed`.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
