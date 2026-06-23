<!-- qa-evidence-exempt: legacy sanitized RCA/QA note retained for historical context; current acceptance must use cases plus a fresh v2 report. -->

# 2026-06-11 Nightly Routines Health Review

## Summary

- Result: PASS with watch items.
- Watch items: Workbench nightly completed correctly but took much longer than the recent healthy
  baseline; user-level schedules failed later in the day because a connected model account needs
  reconnect; browser recall/source-card proof was not run.
- Build/source under test: local Viventium checkout and active installed local-prod runtime.
- Runtime/artifact under test: generated runtime config, memory-hardening LaunchAgent and trigger
  receipt, Scheduler, Prompt Workbench, GlassHive, callback outbox, transcript indexes, RAG sidecar,
  power state, status output, and QA/eval artifacts.
- Environment: local macOS runtime, current system timezone `<observed-system-timezone>`, audit first
  timestamp `2026-06-11T12:45:21Z`, final evidence timestamp `2026-06-11T15:21:30Z`.
- Tester: Codex automation `viventium-nightly-routines-qa`.
- Related change: daily read-only overnight-routine QA audit after the memory-maintenance and
  Workbench nightly windows.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `MEMHARD-001` | SKIPPED / PASS-SAFETY | Jun 11 launchd trigger receipt finalized with `status=skipped`, `reason=on_battery_power`, `exit_code=0` | No model-backed apply or transcript vector work should be forced on battery |
| `MEMHARD-002` | PASS | This public-safe report plus focused public-safety regression coverage | Private prompt, transcript, memory, token, account, path, callback payload, and screenshot evidence omitted |
| `MEMHARD-003` | PASS / SKIPPED | Receipt recorded on-battery skip; later audit power showed AC and no thermal/performance warning | Power gate behaved correctly at scheduled fire |
| `MEMHARD-005` | PASS-SAFETY | Loaded LaunchAgent uses the direct wrapper with explicit scheduled trigger marker and `StartCalendarInterval` hour 3 minute 0 | Timezone-shift/wake timing was recorded but not treated as failure when the receipt finalized cleanly |
| `MEMHARD-010` | PASS | Jun 9, Jun 10, and Jun 11 public-safe launchd receipts exist and finalized cleanly | All three recent receipts were policy skips on battery with exit 0 |
| `MTM-006` | PARTIAL / PROOF GAP | Transcript indexes total 50 processed entries and evals passed 12/0; RAG service is healthy | Browser transcript recall/source-card proof was not run during this read-only audit |
| `RAG-001` | PASS-SERVICE / PROOF GAP | Generated RAG port returned `/health` `UP`; container had the expected host binding | Browser recall/source-card proof remains unrun |
| `RAG-002` | PASS | Report summarizes RAG health without raw private runtime data | `/metrics` returned expected unauthenticated 401 |
| `PW-029` | PASS-CORRECTNESS / LONG-DURATION | Workbench UI, Scheduler DB, GlassHive DB, and callbacks showed Jun 11 completed run | Duration was 9,833s vs recent healthy runs around 190-867s, with Jun 5 and Jun 1 historical long outliers |
| `SCHED-002` | PASS | Built-in task due at `2026-06-11T10:00:00Z`, started at `10:05:17Z`, completed at `12:49:09Z` | Started inside the due/grace window; completed after the audit first timestamp |
| `SCHED-006` | PASS | Child run, parent task ledger, GlassHive run, and terminal callback agreed | Parent ledger status `success`, delivery `sent` |
| `SCHED-009` | PASS | Callback outbox had 0 pending/delivering rows after completion; latest callbacks delivered once | 2 historical dead-letter rows from May remain visible but did not change today |
| `SCHED-010` | PASS | Built-in schedule is active, `glasshive_host` / `workbench`, next run `2026-06-12T10:00:00Z` | No hardcoded user identity recorded in public evidence |
| `MEMCONT-001` | PASS / PARTIAL | Dedupe dry-run found zero duplicate groups/docs/deletes; focused continuity tests passed | Fresh continuity capture was not run because it writes App Support state |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Viventium overnight routines.
- Requirement: Memory hardening, transcript maintenance, Workbench scheduled reflection, Scheduler,
  GlassHive callbacks, RAG health, and continuity checks must be judged after their real due windows
  without hiding skipped, stale, failed, degraded, or not-due routines.
- Use case: Daily read-only health review after the expected overnight maintenance windows.
- QA cases: `MEMHARD-001`, `MEMHARD-003`, `MEMHARD-005`, `MEMHARD-010`, `MTM-006`,
  `RAG-001`, `PW-029`, `SCHED-002`, `SCHED-006`, `SCHED-009`, `SCHED-010`, and
  `MEMCONT-001`.
- Expected result: Due routines either run, skip for a documented policy reason, or are marked
  not due; visible Workbench state agrees with Scheduler/GlassHive ledgers; degraded prerequisites
  and proof gaps are not converted into fake passes.
- Actual evidence: Memory hardening produced a valid scheduled trigger receipt and skipped on
  battery; Workbench completed the Jun 11 chain through Scheduler, GlassHive, callback, and visible
  UI; RAG service health recovered; transcript indexes remained fully processed; focused tests and
  transcript evals passed.
- Remaining gap: Investigate the long Workbench runtime if it repeats, reconnect the affected
  user-level Anthropic account for later schedules, and run browser recall/source-card proof when
  model-backed user-path QA is explicitly in scope.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Nightly routines against memory, transcript/RAG, Workbench, Scheduler, GlassHive, and continuity cases listed above |
| Code owning path | Which code path owns the behavior? | Memory hardener wrapper, config compiler outputs, Scheduler DB/task engine, Prompt Workbench, GlassHive runtime, and RAG sidecar |
| Docs and nested docs/repos | Which docs define expected behavior? | `01_Key_Principles.md`, `20_Memory_System.md`, `39_Installer_and_Config_Compiler.md`, `45_Runtime_Feature_QA_Map.md`, and feature QA cases |
| Scripts or harnesses | Which checks exercised the behavior? | Focused release pytest slice, transcript eval runner, memory-dedupe dry-run, Workbench DB/API checks, RAG health checks, and Playwright CLI |
| Local/external prerequisite state | Which prerequisites were healthy or degraded? | Core web, Scheduler, Workbench, GlassHive, RAG, search sidecars, and MCP sidecars were reachable; memory skipped by power policy |
| Logs | Which sanitized logs confirm or contradict the result? | Memory-hardening trigger receipt/log, Scheduler health, Workbench health, GlassHive runtime/callback evidence |
| DB/state/persistence | Which sanitized state confirms it? | Scheduler task/run rows, GlassHive run/callback rows, trigger receipts, transcript index counts, dedupe counts |
| Generated/shipped artifact | Which generated artifact was inspected? | Generated runtime key summary and loaded LaunchAgent schedule/command shape |
| Real user path | Which surface was exercised like a user? | Playwright opened Prompt Workbench, selected the built-in schedule, inspected recent run state, and confirmed visible persistence |
| Visual/UX comparison | Does visible UI match backend evidence? | Yes for Workbench: visible Jun 11 completed row matched Scheduler/GlassHive/callback rows |
| Not run / blocked | Which required surface was not run? | Browser recall/source-card proof was not run; fresh continuity capture was not run because it writes App Support state |

## User-Grade Evidence

- Surface exercised: Prompt Workbench in a real browser through Playwright CLI, plus local
  CLI/status surfaces for memory, RAG, scheduler, and dedupe.
- Real user path: Opened local Workbench, selected the built-in `Subconscious Deep Thought`
  scheduled prompt, inspected recent run history, and compared the visible row to Scheduler and
  GlassHive state.
- Visible outcome: Workbench showed the built-in schedule enabled, next Jun 12 local run, and a
  Jun 11 `completed` run with the standard GlassHive completion summary.
- Expanded/detail state: Schedules detail showed the GlassHive host execution route and recent run
  list.
- Persistence/reload result: Workbench rendered again after navigation; API/DB evidence confirmed
  the same next-run and latest-run state.
- Local/external prerequisite state: Scheduler, Workbench, GlassHive, RAG, SearXNG, Firecrawl,
  Google Workspace MCP, Microsoft 365 MCP, and status-bar helper were reachable/running. The broader
  Scheduler status still needs attention because later user-level rows require account reconnect.
- Evidence retrieval classification, if applicable: RAG service health was successful; browser
  recall/source-card proof was not run, so recall remains a user-path proof gap rather than a
  service failure today.
- Backend/log/DB confirmation: Scheduler child/parent rows, GlassHive run/callback rows, trigger
  receipts, transcript indexes, and status output matched the visible/CLI findings.
- Final model/runtime wording check: The report labels memory hardening as skipped by policy,
  Workbench as correctness-pass with long duration, RAG as service-pass with proof gap, and
  user-level account failures as separate from the built-in overnight contract.
- Substitution check: Logs, DB rows, API responses, source inspection, and tests are supporting
  evidence. Playwright supplied the required browser-visible Workbench proof; browser recall remains
  a named unrun case, not substituted with backend state.

## Timing Anchor

| Field | Evidence |
| --- | --- |
| Intended automation fire | `2026-06-11T11:15:00Z` / `2026-06-11 13:15 <observed-local-tz-abbrev>` |
| Audit first timestamp | `2026-06-11T12:45:21Z` / `2026-06-11 14:45 <observed-local-tz-abbrev>` |
| Final evidence timestamp | `2026-06-11T15:21:30Z` / `2026-06-11 17:21 <observed-local-tz-abbrev>` |
| Current system timezone | `<observed-system-timezone>` from `/etc/localtime`; `date` reported `<observed-local-tz-abbrev> +0200` |
| `systemsetup` timezone | Not available without administrator access |
| Generated memory schedule context | Schedule `0 3 * * *`, exported timezone context `<configured-local-timezone>` |
| Loaded LaunchAgent schedule | `StartCalendarInterval` hour `3`, minute `0`; direct wrapper with `--scheduled --trigger launchd` |
| Workbench scheduled-prompt timezone | `<workbench-schedule-timezone>`, daily `03:00`, next run `2026-06-12T10:00:00Z` |
| Automation cadence note | Codex Desktop RRULE is UTC in this local Desktop environment; this checker is only a read-only observer |

## Due Windows Used

| Routine | Source schedule | Due window local | Due window UTC | Grace used | Actual evidence | Judgment |
| --- | --- | --- | --- | --- | --- | --- |
| Memory hardening, current local LaunchAgent clock | `StartCalendarInterval` hour 3 minute 0 | Jun 11 `03:00-03:45 <observed-local-tz-abbrev>` | Jun 11 `01:00-01:45Z` | 45 minutes | No model run; later launchd receipt finalized cleanly after wake/timezone-shift context | Timing note only; not failure by itself |
| Memory hardening, generated schedule context | `0 3 * * *`, exported timezone context `<configured-local-timezone>` | Jun 11 `09:00-09:45 <observed-local-tz-abbrev>` | Jun 11 `07:00-07:45Z` | 45 minutes | Receipt fired `09:02 <observed-local-tz-abbrev>` / `07:02Z`, skipped on battery, exit 0 | SKIPPED / PASS-SAFETY |
| Workbench nightly reflection | Workbench daily `03:00`, `<workbench-schedule-timezone>` | Jun 11 `12:00-12:45 <observed-local-tz-abbrev>` | Jun 11 `10:00-10:45Z` | 45 minutes for start/normal completion | Started `10:05:17Z`, completed `12:49:09Z` | PASS-CORRECTNESS / LONG-DURATION |
| Transcript ingest/vector maintenance | Memory-hardening scheduled run | Same as memory hardening | Same as memory hardening | 45 minutes | No model/vector run because power gate skipped before work | SKIPPED today; latest successful artifacts Jun 8 |
| User-level later schedules | User-level due rows | Jun 11 `17:00 <observed-local-tz-abbrev>` | Jun 11 `15:00Z` | Not applied to overnight audit | Not due at intended automation fire or audit first timestamp; later failed from connected-account reconnect | NOT DUE for overnight audit; separate account action |
| Prompt benchmark/eval routines | No separate due scheduled routine found | Not due | Not due | Not applied | Supporting evals were run manually | NOT DUE |

Timing note: per the June 8 memory-hardening contract, QA used the public-safe trigger receipt as
authoritative scheduled-delivery evidence and did not treat timezone-shift, DST, wake coalescing, or
audit-time timezone differences as degradation when the receipt finalized cleanly. The dual timing
anchors above remain recorded so future audits can detect a true missing receipt or conflicting
trigger if one appears.

## Routine Results

### Memory Hardening

Status: SKIPPED / PASS-SAFETY.

Evidence:

- Loaded LaunchAgent was not running at audit time, had last exit code 0, used the direct wrapper
  path with `--scheduled --trigger launchd`, and had `StartCalendarInterval` hour 3 minute 0.
- Jun 11 schedule receipt: `trigger_source=launchd`, fired `2026-06-11T07:02:00Z`, timezone at fire
  `<observed-system-timezone>`, schedule payload `0 3 * * *` with exported timezone context
  `<configured-local-timezone>`, `status=skipped`, `reason=on_battery_power`, `exit_code=0`, no run id.
- The wrapper writes the schedule receipt before the power gate and finalizes it after the skip.
- Recent schedule receipts from Jun 9, Jun 10, and Jun 11 all finalized as `skipped` /
  `on_battery_power` / exit 0.
- Current audit power later showed AC power, battery charged, and no thermal/performance warning;
  the receipt proves the scheduled fire itself was on battery.
- Latest model-backed hardener remains `20260608T100005Z`: `success`, OpenAI/GPT-5.5/xhigh,
  one hardener attempt, zero failures, no fallback, complete 135/135-message lookback, no input-cap
  omission, zero changed memory keys, transcript vector upload count 4 plus 1 inventory, zero
  deletes, zero vector-presence errors, and no failure file.

Not run:

- No `apply`, transcript ingest/catch-up, rebuild, repair, or model-backed work was started by this
  audit. Today's nominal cycle therefore produced no fresh model-backed memory evidence.

### Meeting Transcript Maintenance

Status: SKIPPED today due memory-hardening power gate; persisted artifact state healthy; browser
proof gap remains.

Evidence:

- Persisted transcript indexes currently total 50 processed entries and 0 pending, deferred, or
  skipped entries across three private indexes.
- The latest successful hardener run uploaded 4 transcript summary vectors plus 1 inventory and
  recorded zero vector-presence errors.
- Transcript eval runner passed 12/0, including summary-only, source-backed inventory, broad
  chronological inventory, prompt-injection, and configured-sidecar-ignore cases.
- Because Jun 11 skipped before model/vector work, there is no Jun 11 model-backed run directory;
  that is expected under the power gate.

Not run:

- Browser transcript recall/source-card proof for `MTM-006` and `MTM-007` was not run.

### Conversation Recall / RAG

Status: PASS-SERVICE / PROOF GAP.

Evidence:

- Generated runtime config expects local RAG on port `8110`.
- `GET /health` on the local RAG API returned `UP`.
- Unauthenticated `/metrics` returned 401, which proves the endpoint is reachable and auth-gated.
- Docker Desktop was reachable; the RAG API container had a live `127.0.0.1:8110` host binding and
  had been up for about 20 hours.

Not run:

- Browser recall answer/source-card proof for `RAG-001` was not run during this read-only audit, so
  full recall acceptance remains a proof gap.

### Workbench Nightly Reflection

Status: PASS-CORRECTNESS / LONG-DURATION.

Evidence:

- Built-in `Subconscious Deep Thought` definition was active, daily `03:00`
  `<workbench-schedule-timezone>`, executor `glasshive_host`, memory mode `propose`, next run
  `2026-06-12T10:00:00Z`.
- Scheduler child run was due `2026-06-11T10:00:00Z`, started `10:05:17Z`, completed
  `12:49:09Z`, status `completed`, and included rendered/variable hashes plus private detail
  pointer.
- Parent task ledger reported `last_status=success`, delivery outcome `sent`, and
  `last_delivery_at=2026-06-11T12:49:09Z`; catch-up policy remained `catch_up` with
  `max_late_s=43200`.
- GlassHive run completed from `10:05:17Z` to `12:49:09Z`, output present, no error text, no retry.
- Callback outbox delivered worker resume, run queued, run started, and run completed events in one
  attempt each.
- Playwright opened the local Workbench, selected the built-in schedule, and saw the Jun 11 run as
  `completed` plus the next Jun 12 local run.

Duration context:

| Due date | Status | Duration seconds | Completion lag seconds |
| --- | --- | ---: | ---: |
| 2026-06-11 | completed | 9,833 | 10,150 |
| 2026-06-10 | completed | 868 | 2,059 |
| 2026-06-09 | failed | 5,631 | 6,594 |
| 2026-06-08 | completed | 190 | 204 |
| 2026-06-07 | completed | 241 | 272 |
| 2026-06-05 | completed | 11,221 | 11,230 |
| 2026-06-04 | completed | 203 | 230 |
| 2026-06-03 | completed | 237 | 248 |

The run was correct and complete, but its duration is a watch item because it is far above the
recent healthy 190-868 second completions and resembles the Jun 5 long-run outlier.

### Scheduler, GlassHive, And Callback Health

Status: PASS for built-in nightly substrate; separate user-level account action needed.

Evidence:

- Scheduler health endpoint returned ok with runtime identity fields.
- Workbench health endpoint returned ok.
- GlassHive metrics after completion: `queued_runs=0`, `active_runs=0`, `callback_pending=0`,
  `callback_delivering=0`, `callback_oldest_pending_age_seconds=0`.
- Latest Jun 11 callbacks delivered in one attempt each.
- Two dead-letter callbacks remain from May. They are historical rows; newest update was May 30 and
  no fresh dead-letter delta occurred today.

Separate account-action evidence:

- After the overnight audit start, four active user-level schedules due at `2026-06-11T15:00:00Z`
  failed because an Anthropic connected account needs reconnect. These rows were not due at the
  intended automation fire or at the audit first timestamp, and they do not block the built-in
  Workbench nightly or memory-hardening contract.

### Continuity And Dedupe

Status: PASS / PARTIAL.

Evidence:

- Current memory-dedupe dry-run reported zero duplicate groups, zero duplicate docs, zero deletes,
  and did not create indexes.
- Focused continuity release tests passed as part of the regression slice.
- Fresh continuity capture was not run because the command writes a new App Support state file.

## Automated Evidence

```bash
node qa/meeting-transcript-memory/evals/run-evals.cjs
# 12 passed, 0 failed
```

```bash
python3 -m pytest tests/release/test_memory_hardening_contract.py \
  tests/release/test_scheduled_glasshive_prompts.py \
  tests/release/test_rag_api_override_contract.py \
  tests/release/test_continuity_audit.py \
  tests/release/test_project_boundary_contamination.py -q
# Initial default interpreter check failed because that Python lacked pytest.
```

```bash
<temp-venv>/bin/python -m pytest tests/release/test_memory_hardening_contract.py \
  tests/release/test_scheduled_glasshive_prompts.py \
  tests/release/test_rag_api_override_contract.py \
  tests/release/test_continuity_audit.py \
  tests/release/test_project_boundary_contamination.py -q
# 77 passed, 5 skipped
```

The temporary venv lived outside the repository and was deleted after the run.

```bash
bin/viventium memory-dedupe --dry-run --json
# duplicateGroups=0, duplicateDocs=0, deletedCount=0
```

Other read-only checks:

- `bin/viventium memory-harden status --json`
- `bin/viventium dev-runtime status`
- `bin/viventium status`
- `curl /health` for Scheduling Cortex, Prompt Workbench, GlassHive metrics, and RAG
- read-only SQLite queries for Scheduler and GlassHive ledgers
- LaunchAgent plist and `launchctl print`
- Docker status and container listing
- Playwright CLI Workbench open/snapshot/select flow

Private Playwright snapshot files created by the browser check were deleted after inspection and
are not public evidence.

## Claude Review

ClaudeViv was not available as a separate command, so local Claude CLI was used in review-only mode
with tools disabled.

Claude agreed with the callback, power, test posture, git-hygiene, and user-level schedule
separation classifications. It challenged three points:

- Memory hardening: Claude recommended downgrading to partial because the receipt aligned with the
  exported timezone context rather than the current local LaunchAgent clock. Final classification
  keeps SKIPPED / PASS-SAFETY because the June 8 product contract says timezone-shift, DST, audit-time
  timezone differences, and launchd wake coalescing are not degradation when the public-safe receipt
  finalizes cleanly. The report now records both timing anchors explicitly.
- RAG: Claude recommended a symmetric `PASS-SERVICE / browser-proof-gap` instead of plain PASS.
  Incorporated.
- Workbench: Claude recommended grounding the long-duration label with baseline evidence. The report
  now includes recent duration rows and uses `PASS-CORRECTNESS / LONG-DURATION`.

Unresolved risks after review:

- If the memory schedule ever has no finalized receipt after the due window plus grace, it should be
  marked PARTIAL/FAIL rather than inferred from stale run directories.
- If Workbench long-duration runs repeat, investigate GlassHive worker runtime, provider latency, and
  memory proposal generation timing.
- Browser recall/source-card acceptance remains unrun today.
- User-level Anthropic reconnect failures require account action if those later schedules matter.

## Public-Safety Review

- This report uses sanitized counts, statuses, timestamps, and feature identifiers only.
- It does not include raw private prompts, raw transcripts, memory values, account identifiers,
  callback payloads, browser screenshots, local home-directory paths, tokens, cookies, Mongo IDs, or
  provider request IDs.
- The repository worktree was already dirty before this audit. This report and linked case updates
  should be reviewed separately from unrelated pending work.

## Verdict

The built-in overnight contract is healthy today: memory hardening was safely skipped by power
policy, Workbench completed through the full Scheduler -> GlassHive -> callback -> visible UI chain,
RAG service health recovered, and focused tests/evals passed. Remaining work is not a forced
nightly repair: monitor the long Workbench duration, reconnect the affected user-level Anthropic
account, and run browser recall/source-card proof when user-path recall acceptance is in scope.
