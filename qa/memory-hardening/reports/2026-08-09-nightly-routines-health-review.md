# 2026-08-09 Nightly Routines Health Review

Public-safe, observer-only review of Viventium after the built-in 03:00 local routines. Private
account ids, hashes, prompts, conversations, transcript contents, callback payloads, artifact
bodies, secrets, and local absolute paths are omitted.

## Result

**Built-in nightly routines: PASS. Overall cognitive/control-plane readiness: PARTIAL-SAFE.**

The natural memory-hardening and Workbench lanes both ran inside their due windows and completed
successfully. Transcript maintenance was a healthy scheduled no-op, the current periphery artifact
passed, RAG/vector support was healthy, and no power-budget skip occurred. Overall readiness remains
partial because a separate read-only A/B/C review found 13 protected live managed-agent differences
that require an owner field-level decision. No sync or repair was attempted.

## Timing Anchor

| Item | Evidence |
| --- | --- |
| Audit anchor | 2026-08-09 11:17:12 EDT (`America/Toronto`) / 2026-08-09T15:17:12Z |
| Closeout check | 2026-08-09 11:39:36 EDT / 2026-08-09T15:39:36Z |
| System timezone | `America/Toronto`; `/etc/localtime`, local `date`, and generated runtime agree |
| Prior automation fire | 2026-08-08T15:15:51.382Z, supplied by the automation |
| Current observer fire | approximately 2026-08-09 11:17 EDT / 15:17Z |
| Observer recurrence | daily 11:15, no explicit timezone field; interpreted in host local time |
| Generated product schedule | memory hardening `0 3 * * *`; built-in Workbench daily `03:00`; both currently resolve to `America/Toronto` |
| LaunchAgent schedule | one `StartCalendarInterval`, Hour 3 / Minute 0; no competing interval trigger |
| Workbench next occurrence | 2026-08-10 03:00 EDT / 2026-08-10T07:00:00Z |

The observer cadence is intentionally independent of the product schedulers. It ran after both
product due times plus grace. Travel, host sleep, or a future timezone change must be recomputed
from the current system/schedule timezone rather than treating the observer recurrence as UTC.

## Due-Window Judgment

| Routine | Due local | Due UTC | Grace used | Actual observed | Status |
| --- | --- | --- | --- | --- | --- |
| Memory hardening LaunchAgent | Aug 9 03:00 EDT | Aug 9 07:00Z | completion by 03:30 / 07:30Z | fired 03:00:04.884; finished 03:00:49.721 | PASS-CADENCE-TRANSITION |
| Transcript maintenance inside hardener | Aug 9 03:00 EDT | Aug 9 07:00Z | same scheduled run | scan ran; zero pending model-summary work | PASS-SCHEDULED-NOOP |
| Workbench nightly reflection | Aug 9 03:00 EDT | Aug 9 07:00Z | completion by 03:30 / 07:30Z; scheduler misfire grace is 15m | started 03:00:27.617; completed 03:05:23.359 | PASS |
| Periphery risk-radar output | produced by Workbench run | after Aug 9 07:00Z | same terminal chain | paired artifact generated 03:03:23 local | PASS |
| RAG/vector support | no separate nightly due time | N/A | service/telemetry check | health `UP`; vector containers healthy | PASS-SERVICE |

All built-in lanes were due and actually ran. None was `NOT DUE`, power-skipped, or waiting at the
audit anchor. The 4.884-second and 27.617-second start jitter were well inside grace.

The expected UTC fires are timezone-derived, not hardcoded. Read-only projections for the
2026-11-01 Toronto fall-back resolved both the hardener and Scheduler 03:00 occurrence to 08:00Z,
so the independent-review DST concern was not reproduced.

## Cognitive Integrity Gate

`bin/viventium cognitive-integrity --json` returned `schemaVersion=3`, top-level `status=ok`, and
`blockingChecks=[]`. A later read-only rerun preserved the same statuses; the report has no explicit
measurement timestamp, so the audit records the command time separately.

| Check | Every reported field |
| --- | --- |
| `conversationRecallRuntime` | `declaredStatus=UP`, `httpStatus=200`, `reason=healthy`, `status=ok` |
| `glasshiveHostWorkerRuntime` | `binaryInvocation=canonical_or_wrapper`, `codeModeHostEnabled=true`, `companionReady=true`, `reasons=[]`, `status=ok` |
| `liveMemoryExposure` | `readTokenLimit=8000`, `storageTokenLimit=8000`, `reasons=[]`, `status=ok` |
| `liveProviderCapabilityTransport` | `hostTools=[file_search]`, `transport=broker_mcp`, `reasons=[]`, `status=ok` |
| `memoryHardening` | `executionMismatch=false`, `latestRunStatus=success`, `missedExpectedWindow=false`, `scheduleState=healthy`, `status=ok` |
| `promptBundleDrift` | `driftCount=0`, `livePromptCount=76`, `sourcePromptCount=76`, `reason=none`, `status=ok` |
| `qaAccountImmediateMemoryWriterRuntime` | `ageSeconds=831` at the anchor, `effort=medium`, `model=gpt-5.6-luna`, `provider=openai`, `reason=writer_completed`, `scope=configured_qa_test_account`, `status=ok`, `updatedAt=2026-08-09T15:03:50.320Z` |
| `qaAccountSavedMemoryReadRuntime` | `ageSeconds=863` at the anchor, `effort=null`, `model=null`, `provider=null`, `reason=context_loaded`, `scope=configured_qa_test_account`, `status=ok`, `updatedAt=2026-08-09T15:03:17.769Z` |
| `qaTestAccount` | `accountCount=1`, `role=USER`, `selectorConfigured=true`, `reasons=[]`, `status=ok`; private account hash present but withheld |
| `runtimeConfigDrift` | `addedSections=[]`, `changedSections=[]`, `removedSections=[]`, `driftCount=0`, `reason=none`, `status=ok` |
| `sourceMemoryExposure` | `readTokenLimit=8000`, `storageTokenLimit=8000`, `reasons=[]`, `status=ok` |
| `sourceProviderCapabilityTransport` | `hostTools=[file_search]`, `transport=broker_mcp`, `reasons=[]`, `status=ok` |
| `workbenchNightly` | `activeCount=1`, `definitionCount=1`, `executionProfile=codex-cli`, `executor=glasshive_host`, `lastErrorClass=null`, `lastStatus=completed`, `latestAnyStatus=completed`, `latestManualAt=null`, `latestManualStatus=null`, `latestRunFailure=false`, `latestScheduledAt=2026-08-09T07:00:27.617236Z`, `latestScheduledStatus=completed`, `manualRecoveryAfterScheduledFailure=false`, `reasons=[]`, `scheduledAgeSeconds=29833`, `status=ok` |

The QA-account read/writer receipts predated the observer fire by about 14 minutes; this audit did
not start those model-backed actions. Their ordering is not treated as a new write-then-read test.

The nine control planes were preserved and cross-checked:

| Key | Owner | Trigger | Evidence contract |
| --- | --- | --- | --- |
| `provider_capability_transport` | compiled LibreChat registry + signed GlassHive broker | every initialized Agent turn | resolved host tools in signed grant and MCP tools/list |
| `saved_memory_exposure` | memory storage policy + `memory.readProfile` | Agent initialization | governed keys whole or with a model-visible omission boundary |
| `saved_memory_runtime_health` | per-user read/writer receipts | attempted saved-memory paths | privacy-safe receipt joined to configured QA identity |
| `conversation_recall` | `file_search` + recall health/freshness gate | opted-in initialization/tool call | source/vector provenance and explicit inconclusive degradation |
| `workbench_nightly` | Workbench + Scheduler + GlassHive callback ledger | managed nightly schedule | one active definition and latest scheduled state, distinct from manual recovery |
| `qa_test_account` | runtime selector + non-admin account | Workbench eval/native QA | exactly one non-admin selector before model work |
| `glasshive_host_worker_runtime` | compiled env + prerequisite discovery | compile/restart/preflight | enabled companion exists at invocation path |
| `memory_hardening` | LaunchAgent + hardener ledger | 03:00 direct wrapper | receipt, execution tuple, and latest run state |
| `codex_observer` | optional Codex automation | independent observation | reads the report and never owns product schedules |

Observer metadata remained `key=codexObserver`,
`reason=optional_external_observer_not_a_product_control_plane`, `status=observer_only`.

## Lane Evidence

| Lane | Status | Evidence |
| --- | --- | --- |
| Memory schedule/receipt | PASS-CADENCE-TRANSITION | Latest receipt is dated 2026-08-09, schema v2, `launchd_parent_legacy`, attested, schedule-aligned, exit 0, and joined to the successful run. Exactly one legacy-v2 receipt exists and the single-use transition is open. A second v2 receipt would be rejected; the next natural run must produce valid v3 proof. |
| Memory execution | PASS | One eligible hashed user was selected/applied on OpenAI Luna/medium; requested/effective tuple matched; one model attempt, no fallback or provider/runtime/vector error; complete 158/158-message and 36/36-conversation lookback; 9 valid/current keys. |
| Transcript maintenance | PASS-SCHEDULED-NOOP | Scanner saw 40 files: 34 processed/unchanged, 6 ignored, 0 pending/requeued/removed/failed/truncated/partial, 0 summary failures, and 0 model characters. This is a scanner-proven empty run, not a zero-input blind no-op. |
| Vector/RAG | PASS-SERVICE / RECALL-PROOF-GAP | One current meeting-inventory artifact uploaded; 0 deletes/deferred/presence errors; RAG API and vector service healthy. Browser recall/source-card correctness was not rerun. |
| Power/thermal | PASS / NO-SKIP | AC power, fully charged, no thermal/performance warning, no skip, no override. This is audit-time evidence, not a synthetic battery-gate exercise. |
| Workbench definition | PASS | One active built-in definition, fixed Toronto 03:00 schedule, memory off, GlassHive host, `codex-cli`, Sol/xhigh; next occurrence advanced to Aug 10. |
| Scheduler/GlassHive/callbacks | PASS / WATCH-HISTORY | Natural row has `trigger_kind=scheduled`, `trigger_source=scheduler_loop`, rendered/snapshot hashes, completed GlassHive run, and queued/started/completed callbacks delivered on attempt 1. Active callback backlog and new dead letters are zero. Nine old dead letters and three stale queued rows remain cleanup debt. |
| Periphery snapshot/artifact | PASS | Snapshot complete with no missing prerequisites; latest paired risk-radar artifact passed, 8/8 sources resolved, high confidence, current through Aug 12, memory proposals 0. |
| Workbench visible UI | PASS | Headed Playwright showed the completed natural run, current evidence/artifact details, prior failures as history, and the Aug 10 next occurrence. Reload preserved the selected schedule and detail state. |

## Drift And Provenance Boundaries

- The gate's `promptBundleDrift=0` covers the 76-entry source-to-compiled prompt registry, and
  `runtimeConfigDrift=0` covers compiled-to-live runtime config.
- The separate required A/B/C managed-agent comparison found 13 protected live-vs-source
  differences across instructions, tools, provider/model, fallbacks, and workspace options. The
  live adjacent scaffold matched its tracked source, while proposed source-vs-HEAD edits exist.
  Existing same-day review classifies these differences as `REVIEW REQUIRED`; no sync was run.
- Workbench's prompt sync sidebar separately showed 11 synced prompt objects and 1 needs-merge
  object. This is a different comparison surface from the 13 managed-agent A/B/C differences.
- Because the canonical JSON does not declare managed-agent drift as an exclusion, top-level `ok`
  can be misread as all Agent Builder state synchronized. This is a **P1 integrity-observability
  contract gap**, but it does not invalidate the independently proven built-in nightly runs.
- One same-definition Workbench row was due at 2026-08-09T03:17:00Z, completed, carried
  `trigger_kind=scheduled`, but had no `trigger_source`; the UI calls it an unknown run. It occurred
  about twelve hours before this audit's pytest matrix, so test contamination was ruled out by
  timestamp. It cannot certify or contradict the unique natural 07:00Z `scheduler_loop` row, but
  its legacy/migration provenance remains an active read-only query.
- A disconnected Anthropic Test Account path is separate owner account-action evidence. Today's
  built-in lanes used healthy OpenAI paths; no claim is made about every drifted managed agent.

## Evidence Checked

- Automation memory/config, local/UTC clocks, system timezone, generated runtime timezone/config.
- LaunchAgent plist and live `launchctl` state; hardener trigger receipt, lifecycle receipt, latest
  summary, provider/model/fallback telemetry, eligibility, transcript index, vector telemetry, and
  redacted logs.
- Scheduler and GlassHive health, read-only SQLite run/task/callback rows, Workbench API/browser
  state, periphery snapshot/artifact metadata, and RAG/Docker health.
- Power/battery/thermal status and git/source/config drift. The worktree was already broadly dirty;
  this observer did not repair, sync, start, stop, or apply product state.

## QA And Eval Results

| Command / check | Result |
| --- | --- |
| `bin/viventium cognitive-integrity --json` | PASS: `status=ok`, `blockingChecks=[]`; every check above `ok` |
| `bin/viventium memory-harden status --json` | PASS-CADENCE-TRANSITION: current dated receipt/run healthy, no mismatch or missed window |
| Required managed-agent A/B/C compare, JSON mode | PARTIAL-SAFE: 13 protected differences; diagnostic only, no sync |
| Focused nightly/compiler/Workbench/periphery/scheduling/RAG/continuity/agent-sync pytest matrix | 415 passed, 23 skipped, 0 failed; 455 temp-directory cleanup warnings |
| Transcript eval harness | 12 passed, 0 failed |
| Periphery offline eval harness | 6 passed, 0 failed |
| `bin/viventium memory-dedupe --dry-run --json` | 0 duplicate groups, documents, or deletions; no index creation |
| Public QA safety test | 1 passed |
| Headed Playwright Workbench action/detail/reload | PASS; current schedule and results persisted; temporary private snapshots removed |
| 2026-11-01 hardener and Scheduler timezone projections | PASS; both derive Toronto 03:00 as 08:00Z |

The 455 pytest warnings concern temporary copied-environment cleanup (`Directory not empty`). They
did not fail the suite or write the unexplained Workbench row, which predates the tests, but remain
harness cleanup debt.

## Claude Review

ClaudeViv was not available, so local Claude CLI used Claude Opus 5 at xhigh in review-only mode
with tools disabled. Claude made no changes. It agreed with `BUILT-IN NIGHTLY PASS` and overall
`PARTIAL-SAFE`, confirmed the narrow RAG and transcript-no-op classifications, and challenged:

- protected managed-agent drift should be an explicit high-priority exclusion/check in the
  canonical integrity map;
- the unknown Workbench row should be actively attributed rather than passively ignored;
- the remaining v2 receipt budget and next v3 predicate should be explicit;
- receipt freshness, timezone projections, QA-probe attribution, and warning isolation should be
  checked rather than inferred.

Follow-up inspection resolved the proposed DST failure: both owning timezone functions project
08:00Z on Nov 1. It also ruled out today's tests as the source of the 03:17Z row. The current hardener
receipt is dated Aug 9 and exactly one legacy-v2 receipt has consumed the entire single-use budget;
the next natural receipt must be valid v3. The unexplained row's originating legacy path remains
unconfirmed.

## Stale, Skipped, Partial, And Silently Degraded Items

- **Partial-safe:** 13 protected managed-agent A/B/C differences remain intentionally unsynced.
- **Integrity-map gap, P1:** top-level `ok` does not declare the managed-agent comparison exclusion.
- **Cadence transition:** current hardener v2 receipt is accepted; any next v2 receipt fails closed.
- **Provenance gap:** one off-window completed Workbench row lacks `trigger_source`.
- **Historical only:** Aug 8 evidence-check and Aug 7 quota failures remain visible; today's natural
  run recovered. Nine old callback dead letters and three old queued GlassHive runs had no new delta.
- **QA proof gap:** browser recall/source-card correctness and the battery/thermal skip branch were
  not exercised today.
- **Harness watch:** pytest temporary-directory cleanup emitted warnings.
- **No current skip/failure:** no due built-in lane was stale, power-skipped, missed, or silently
  downgraded in its current receipt/ledger/UI evidence.

## Next Actions

1. Add a distinct protected-managed-agent drift check or explicit exclusion to cognitive-integrity
   JSON so top-level `ok` cannot be mistaken for full Agent Builder synchronization.
2. Review the 13 protected A/B/C differences field by field. Preserve live tools/workspaces/provider
   state; do not broad-sync. This is an owner decision, not an observer repair.
3. Observe the next natural hardener receipt. It must be schema v3 with canonical launchd job-PID
   proof; a second schema-v2 receipt should fail closed.
4. Attribute the 03:17Z Workbench row from read-only run/callback/runtime deployment evidence and
   keep it excluded from cadence certification until its trigger source is known.
5. Reconnect or explicitly waive the separate Anthropic Test Account path, and terminalize the old
   callback/queued rows, only through an authorized product-maintenance workflow.
6. Fix the pytest temporary-directory cleanup warnings and rerun browser recall/source-card proof
   before recall release signoff.

No product runtime, schedule, prompt, memory, conversation, transcript, vector, account, or
background-agent state was changed by this audit.
