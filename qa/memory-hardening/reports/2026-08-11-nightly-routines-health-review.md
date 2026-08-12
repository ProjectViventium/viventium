<!-- qa-evidence-exempt: Public-safe nightly summary. Raw prompts, health records, transcript text, identities, tokens, local paths, browser snapshots, and private run identifiers remain outside the repository. -->

# Nightly routines health review — 2026-08-11

## Outcome

**Overall: BLOCKED / PARTIAL.** The observer ran after every reviewed product lane was due. Memory
hardening, bounded transcript maintenance, RAG liveness, the natural Nightly Reflection worker, and
the natural Health Context worker all ran. The result cannot be PASS because:

1. the canonical cognitive-integrity gate is `blocked` on the configured QA account's stale
   immediate-memory-writer receipt;
2. both templated Workbench schedules left a second occurrence row visibly stuck `queued/running`
   beside their completed row;
3. the 06:00 WHOOP acquisition ran but failed all six resources during OAuth refresh, so Health
   Context correctly consumed a degraded snapshot;
4. protected live Agent configuration differs from the dirty source bundle for all 15 reviewed
   Agents and was not reconciled.

No schedule, prompt, memory, transcript, vector, account, provider, or runtime state was repaired or
forced during this audit. No power/idle bypass or model-backed QA run was started.

## Timing truth

- System and generated product timezone: `America/Toronto` (`EDT`, UTC-04:00).
- Codex observer recurrence: host-local `11:15`, with no explicit timezone field.
- Effective observer fire: scheduled `2026-08-11 11:15 EDT` / `15:15Z`.
- First observable audit anchor: `2026-08-11 11:18:17 EDT` / `15:18:17Z`.
- Closeout clock: `2026-08-11 11:51:26 EDT` / `15:51:26Z`.
- Prior observer fire supplied by the automation: `2026-08-10 11:16:28 EDT` / `15:16:28Z`.

The desktop recurrence is an observer cadence, not a product scheduler. Its `automation.toml` does
not expose a more precise current start receipt, so the scheduled fire and first observable process
anchor are recorded separately.

| Lane | Product due, local | Product due, UTC | Completion grace | Observed | Judgment |
| --- | --- | --- | --- | --- | --- |
| Memory hardening + transcript maintenance | Aug 11 03:00 EDT | Aug 11 07:00Z | Product missed-window tolerance 60 minutes, through 04:00 EDT / 08:00Z | Trigger 03:00:01; run 03:00:04–03:00:53 EDT | DUE; ran inside window |
| Prompt Workbench Nightly Reflection | Aug 11 03:00 EDT | Aug 11 07:00Z | 60 minutes for completion; separate 12-hour catch-up policy | 03:00:15–03:06:22 EDT | DUE; worker completed |
| WHOOP acquisition | Aug 11 06:00 EDT | Aug 11 10:00Z | 30 minutes | 06:00:02–06:00:45 EDT | DUE; ran and failed |
| Prompt Workbench Health Context | Aug 11 06:15 EDT | Aug 11 10:15Z | 60 minutes | 06:15:15–06:17:45 EDT | DUE; worker completed with degraded evidence |
| Codex observer | Aug 11 11:15 EDT | Aug 11 15:15Z | Not a product completion window | First evidence 11:18:17 EDT | Observer only |

No reviewed routine was `NOT DUE`. Travel, DST, wake coalescing, and audit-time timezone differences
did not affect today's classifications.

## Cognitive-integrity gate

The final read-only `bin/viventium cognitive-integrity --json` capture returned schema version `3`,
top-level status `blocked`, and exactly one `blockingChecks` entry:
`qaAccountImmediateMemoryWriterRuntime`.

Every reported check field is preserved below. The configured account hash was present in the raw
private report but is intentionally withheld here.

| Check | Fields |
| --- | --- |
| `conversationRecallRuntime` | `declaredStatus=UP`; `httpStatus=200`; `reason=healthy`; `status=ok` |
| `glasshiveHostWorkerRuntime` | `binaryInvocation=canonical_or_wrapper`; `codeModeHostEnabled=true`; `companionReady=true`; `reasons=[]`; `status=ok` |
| `liveMemoryExposure` | `readTokenLimit=8000`; `storageTokenLimit=8000`; `reasons=[]`; `status=ok` |
| `liveProviderCapabilityTransport` | `hostTools=[file_search, web_search]`; `transport=broker_mcp`; `reasons=[]`; `status=ok` |
| `memoryHardening` | `executionMismatch=false`; `latestRunStatus=success`; `missedExpectedWindow=false`; `scheduleState=healthy`; `status=ok` |
| `promptBundleDrift` | `driftCount=0`; `livePromptCount=82`; `sourcePromptCount=82`; `reason=none`; `status=ok` |
| `qaAccountImmediateMemoryWriterRuntime` | `ageSeconds=175474`; `effort=medium`; `model=gpt-5.6-luna`; `provider=openai`; `reason=runtime_receipt_stale`; `scope=configured_qa_test_account`; `status=blocked`; `updatedAt=2026-08-09T15:03:50.320Z` |
| `qaAccountSavedMemoryReadRuntime` | `ageSeconds=2824`; `effort=null`; `model=null`; `provider=null`; `reason=context_loaded`; `scope=configured_qa_test_account`; `status=ok`; `updatedAt=2026-08-11T15:01:19.696Z` |
| `qaTestAccount` | `accountCount=1`; account hash present/withheld; `reasons=[]`; `role=USER`; `selectorConfigured=true`; `status=ok` |
| `runtimeConfigDrift` | `addedSections=[]`; `changedSections=[]`; `removedSections=[]`; `driftCount=0`; `reason=none`; `status=ok` |
| `sourceMemoryExposure` | `readTokenLimit=8000`; `storageTokenLimit=8000`; `reasons=[]`; `status=ok` |
| `sourceProviderCapabilityTransport` | `hostTools=[file_search, web_search]`; `transport=broker_mcp`; `reasons=[]`; `status=ok` |
| `workbenchNightly` | `activeCount=1`; `definitionCount=1`; `executionProfile=codex-cli`; `executor=glasshive_host`; `lastErrorClass=null`; `lastStatus=completed`; `latestAnyStatus=completed`; `latestManualAt=null`; `latestManualStatus=null`; `latestRunFailure=false`; `latestScheduledAt=2026-08-11T07:00:15.584342Z`; `latestScheduledStatus=completed`; `manualRecoveryAfterScheduledFailure=false`; `reasons=[]`; `scheduledAgeSeconds=31688`; `status=ok` |

The report's complete control-plane map was:

| Key | Owner | Trigger | Evidence |
| --- | --- | --- | --- |
| `provider_capability_transport` | compiled LibreChat provider capability registry + signed GlassHive broker | each initialized Agent turn | resolved host tools in signed grant and MCP tools/list |
| `saved_memory_exposure` | memory storage policy + `memory.readProfile` | each Agent initialization | governed keys delivered whole or with a model-visible omission boundary |
| `saved_memory_runtime_health` | LibreChat per-user read and immediate-writer health receipts | each attempted saved-memory read/write path | privacy-safe read/writer receipt joined to the configured QA identity |
| `conversation_recall` | LibreChat `file_search` + recall runtime health/freshness gate | opted-in Agent initialization and model-controlled tool call | source/vector provenance and explicit inconclusive degraded result |
| `workbench_nightly` | Prompt Workbench definition + Scheduler + GlassHive callback ledger | managed local nightly schedule | one active definition and latest scheduled delivery state, distinct from manual recovery |
| `qa_test_account` | canonical `runtime.extra_env` selector + local non-admin LibreChat account | Prompt Workbench live eval or local native-surface QA | explicit selector resolves to exactly one non-admin account before model work |
| `glasshive_host_worker_runtime` | compiled `runtime.env` + GlassHive host-worker prerequisite discovery | compile/restart and every host-worker preflight | enabled Codex runtime features have executable sibling companions at the invocation path |
| `memory_hardening` | local LaunchAgent and memory-hardening run ledger | 03:00 local direct wrapper | schedule receipt, execution tuple, and latest run state |
| `codex_observer` | optional Codex automation | independent scheduled observation | reads this report; never owns or mutates product schedules |

The observer entry was `key=codexObserver`,
`reason=optional_external_observer_not_a_product_control_plane`, `status=observer_only`.

The gate is correctly blocking on its current 36-hour saved-memory receipt contract. An observer-only
audit cannot refresh the writer receipt without initiating an actual user/model write path, so this
classification is a current user-path proof gap rather than evidence that the writer is failing.
The receipt lacks source-surface provenance, so the separate current read receipt proves freshness
for the configured identity but not which user surface minted it.

## Lane results

| Lane | Status | Evidence and remaining gap |
| --- | --- | --- |
| Cognitive integrity | **BLOCKED** | One stale configured-QA writer receipt. All other reported checks were `ok`, but the gate missed the live duplicate occurrence rows and does not expose protected Agent A/B/C coverage. |
| Memory hardening | **PASS** | One 03:00 direct-wrapper LaunchAgent, schema-v3 job-PID-attested trigger receipt, exit `0`, healthy schedule, OpenAI Luna/medium requested and effective, no fallback/runtime/vector/provider error. The apply selected one eligible user and changed the allowed `context`/`signals` keys. |
| Transcript ingest/catch-up | **PASS / HEALTHY NO-CHANGE** | 40 files seen, 34 unchanged, 6 ignored by declared config, 0 pending/capped/truncated/failed/vector-error; persisted index has 57/57 processed files. No transcript/vector mutation was required. |
| Recall/RAG runtime | **PASS-LIVENESS / RETRIEVAL PROOF GAP** | HTTP 200 and declared `UP`; hardener saw no vector errors. No browser recall query or source/vector provenance result was run, so retrieval quality remains unproven rather than failed. |
| Nightly Reflection worker | **PASS-DELIVERY / FAIL-LEDGER** | Natural Sol/xHigh host run completed through GlassHive and three callbacks, and Workbench showed `completed`, scheduled, delivered after refresh/reopen. A second same-due keyed row remains visibly `queued/running`. |
| WHOOP acquisition | **FAIL** | The loaded 06:00 LaunchAgent ran, last exit `1`, and all six resources returned `authorization_failed` with zero items. |
| Health Context worker | **DEGRADED / PARTIAL** | Natural Sol/xHigh host run completed with three callbacks. The bounded snapshot truthfully reported `degraded` and `whoop_pull_incomplete`, included 18 historical records with zero read failures, and exposed the prerequisite in Workbench. It also has the duplicate queued occurrence row. |
| GlassHive callback substrate | **PASS-CURRENT / WATCH-HISTORY** | Six current callbacks delivered, active backlog zero, no dead letters since the prior observer. Nine historical dead letters remain unchanged. |
| Saved-memory dedupe | **PASS-DRY-RUN** | Zero duplicate groups/docs for entries and keys; no indexes or data changed. |
| Provider/model/fallback | **PASS for hardener and Workbench model routes** | Luna/medium hardener and both Sol/xHigh Workbench runs used intended tuples without fallback. WHOOP OAuth remains independently failed. |
| Power/thermal | **PASS-NO-SKIP** | AC power, charged battery, no thermal/performance warning, and no power-budget skip. No override used. |
| Agent/config drift | **REVIEW REQUIRED** | Compiled runtime/prompt bundle is aligned at 82/82. Protected Agent compare differs live-vs-source on 15/15 and dirty source-vs-HEAD on 15/15; adjacent live LibreChat equals source, while two adjacent source fields differ from HEAD. No sync was applied. |
| Status bar/transcript source | **PASS-CURRENT STATE** | Status-bar helper is on; transcript source is configured and unchanged. Manual ingest was not invoked. |

## Escaped scheduler defect

**Severity: High (`P1`) — user-visible audit integrity and replay-protection coverage defect.** The
worker outcome was delivered, so this is not classified as data loss or a critical outage, but a
terminal run and a permanently queued sibling for the same occurrence contradict the single-ledger
contract and make the Workbench history untrustworthy.

### Actual evidence

- Nightly Reflection due `07:00Z` has one unkeyed terminal delivered row and one keyed
  `queued/running` row.
- Health Context due `10:15Z` has the same pair.
- Both keyed rows have expired 15-minute leases; no current lease remains held.
- Both parent tasks advanced to the next day's correct local occurrence, so the evidence does not
  support an imminent same-day catch-up replay.
- The browser shows both the completed and queued rows after refresh/reopen.
- `workbenchNightly.status=ok` selected the completed row and did not report the contradictory
  same-due sibling.

### Root cause

Scheduling Cortex claims the occurrence and adds ephemeral `_scheduled_prompt_run_id` and
`_scheduled_prompt_occurrence_key` fields. For a templated Workbench prompt,
`_refresh_workbench_rendered_prompt()` persists refreshed render metadata and then replaces the
runtime task with the stored task. It restores `next_run_at`, rendered prompt, and metadata but drops
the ephemeral preclaim fields. `_dispatch_glasshive_task()` therefore sees no preclaimed run ID and
creates a second unkeyed row. The callbacks terminalize that child while the original keyed claim is
left queued.

The current green test covers a preclaimed GlassHive row only when dispatch is mocked or variable
rendering does not replace the task. It does not combine a templated prompt, real render refresh,
preclaim, GlassHive assignment, callback, and visible refresh.

### Repair plan — not applied

1. Merge refreshed persisted fields into the existing runtime task so scheduler-private occurrence
   context survives rendering; do not blindly replace the runtime task.
2. Fail closed if a scheduled dispatch that was preclaimed is about to create an unkeyed row.
3. Add a blocking templated-prompt regression proving exactly one keyed row receives GlassHive and
   terminal callback fields, plus a non-templated negative control and restart/persistence check.
4. Extend cognitive integrity to detect multiple rows for one task/definition/due time, a terminal
   row beside a nonterminal sibling, and expired keyed occurrence rows. Its output should also
   declare that the current `workbenchNightly` check is scoped to Nightly Reflection rather than all
   Workbench routines.
5. Preserve the two historical orphan rows as evidence until an explicit reconciliation design is
   reviewed; do not delete or rewrite them to make the gate green.
6. Do not restart from the current heavily dirty tree. Reconcile the owning source changes and
   protected Agent A/B/C drift first, then use the supported restart path and prove a fresh natural
   or synthetic occurrence through UI, DB, callbacks, and logs.

## WHOOP failure analysis

The 06:00 acquisition is a separate product scheduler and failed independently of Workbench.

- The LaunchAgent uses the installed Viventium-Health runtime and the same owner-only credential
  root used by manual commands; it has no divergent environment-variable credential source.
- A manual full-history run at `2026-08-10 19:03Z` completed all six resources with 51 items.
- Its one-hour access token expired at `20:03Z`; a refresh token and all requested scopes remain
  present in the protected token record.
- At `10:00Z` today the scheduled correction tried the expired-token refresh path. The runtime
  flattens any `CredentialError` during resource acquisition to `authorization_failed`, so the
  exact sanitized provider response class is not retained. All six resources consequently show the
  same result.

This rejects an interactive-shell-versus-LaunchAgent credential-path explanation. The remaining
leading issue is failed refresh-token exchange, but provider rejection versus client/rotation defect
cannot be distinguished from current receipts.

Required next action: reconnect WHOOP through the supported owner UI, then verify a read-only status
and the next supported acquisition. Separately, add privacy-safe refresh failure classes (for
example token endpoint HTTP class versus missing rotated token) so a future audit can distinguish
account action from product refresh logic without logging secrets.

## Logs, DB, state, and artifacts inspected

- generated runtime timezone, hardener model/schedule settings, Workbench enablement, scheduler DB,
  RAG URL, and health-context enablement;
- memory LaunchAgent plist, launchctl state, schedule trigger/lifecycle receipt, hardener summary,
  lock state, transcript index, model/fallback telemetry, and power/thermal state;
- WHOOP LaunchAgent plist/state, public-safe status/runs, protected token metadata without token
  values, and stdout/stderr result classes;
- canonical scheduler definitions, tasks, same-due run rows, execution snapshots, leases, next-run
  timestamps, callback payload presence, and parent delivery fields;
- GlassHive runs and callback outbox aggregates, including current backlog and dead-letter delta;
- private Workbench render/snapshot manifests only through sanitized counts/status/prerequisites;
- compiled prompt/runtime drift and fresh protected Agent A/B/C comparison;
- headed Workbench UI history, detail, next local schedule, health prerequisite, refresh/reopen,
  browser console, and request-error check;
- RAG health, memory dedupe dry-run, transcript and periphery eval artifacts.

Raw transcript/health/conversation content, prompts, email addresses, account identifiers, tokens,
local absolute paths, browser snapshot text, and private run IDs were not copied into this report.

## Commands and QA results

- `bin/viventium cognitive-integrity --json`: exit `2`, correctly `blocked` on one writer receipt.
- `bin/viventium memory-harden status --json`: healthy schema-v3 scheduled receipt and successful
  natural run.
- `bin/viventium health whoop status`, `health schedule status`, and `health runs`: schedule loaded;
  current acquisition failed six-for-six authorization.
- focused release matrix: `281 passed, 24 skipped`; skipped Workbench/Scheduler dependency paths were
  immediately rerun with their optional dependencies.
- dependency-complete Workbench/Scheduler release rerun: `181 passed, 0 skipped`.
- Scheduling Cortex storage/scheduler/dispatch suite: `134 passed` plus `8` subtests.
- transcript eval bank: `12/12 passed`.
- periphery deterministic eval bank: `6/6 passed`.
- memory dedupe dry-run: zero duplicate groups/documents; no mutation.
- headed Playwright: PASS for schedule visibility, terminal details, degraded prerequisite visibility,
  refresh/reopen, and zero console errors/warnings; FAIL for truthful single-occurrence history because
  both schedules visibly retain queued siblings.

The release runs emitted 91 repeated pytest temporary-directory cleanup warnings around copied
component virtual environments. Assertions passed; the warnings remain test-harness cleanup debt.

## Independent review

ClaudeViv was unavailable. Local Claude CLI ran review-only with Opus/xHigh and no tools.

Claude agreed with the overall block, worker/ledger split, exact templated-render field-loss RCA, the
need for a real combined regression, gate detection, preserving historical evidence, and avoiding a
restart from the dirty tree. It challenged the gate's coverage, duplicate-row blast radius, health
RCA, writer-gate satisfiability, ignored transcript files, recall wording, and dependency skips.

Follow-up evidence confirmed these useful adjustments:

- the cognitive gate has a real detection gap for contradictory same-due rows and does not declare
  its Health Context/protected-Agent coverage boundary;
- the health symptom was traced to the expired-token refresh path, not merely named;
- recall is labeled liveness-only, with retrieval proof left open;
- the dependency skips were rerun to zero;
- the writer gate cannot be refreshed by this observer without violating its no-model-work boundary.

Follow-up evidence rejected or narrowed other review hypotheses:

- the two orphan leases are expired and next-run times advanced, so no active lease or same-day
  catch-up replay is currently indicated;
- the six transcript files were ignored by declared config, not unexplained;
- the hardener was not an overall no-op: it applied allowed saved-memory changes while transcript
  vectors required no change;
- the WHOOP schedule and manual path share the same credential store, so execution-context credential
  divergence is not supported.

Unresolved risks are the exact WHOOP refresh rejection class, fresh configured-account writer proof,
retrieval-level recall proof, protected Agent reconciliation, the two historical occurrence orphans,
and the next post-fix natural occurrence.

## Next actions

1. Reconnect WHOOP through the supported owner UI; do not force a provider pull from this observer.
2. Reconcile the dirty scheduler/Workbench source and protected Agent A/B/C state before any compile,
   activation, or restart.
3. Implement and test the templated preclaim preservation plus fail-closed unkeyed-dispatch guard.
4. Extend cognitive-integrity scope/detection for occurrence contradictions, Health Context coverage,
   and protected Agent drift disclosure.
5. Run a separate authorized user-grade saved-memory writer/read proof for the configured QA account;
   do not have the nightly observer create one.
6. After an approved patch and supported restart, verify the next occurrence through Workbench UI,
   scheduler DB, GlassHive callback outbox, and logs. Keep the current audit BLOCKED until then.

