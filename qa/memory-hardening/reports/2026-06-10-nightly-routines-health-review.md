# 2026-06-10 Nightly Routines Health Review

<!-- qa-evidence-exempt: Historical operational health snapshot retained verbatim; current acceptance uses the full evidence template. -->

## Summary

- Result: PARTIAL / DEGRADED.
- Build/source under test: local Viventium checkout and active installed local-prod runtime.
- Runtime/artifact under test: generated runtime config, memory hardener LaunchAgent and trigger
  receipts, Scheduler, Prompt Workbench, GlassHive, callback outbox, transcript index state,
  RAG sidecar health, status output, and QA/eval artifacts.
- Environment: local macOS runtime, system timezone `<observed-system-timezone>`, audit started at
  `2026-06-10T11:16:05Z`.
- Tester: Codex automation `viventium-nightly-routines-qa`.
- Related change: daily read-only overnight-routine QA audit after the memory-maintenance and
  Workbench nightly windows.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `MEMHARD-001` | SKIPPED / PASS-SAFETY | Jun 10 launchd trigger receipt finalized with `status=skipped`, `reason=on_battery_power`, `exit_code=0` | No model-backed apply or transcript vector work should be forced on battery |
| `MEMHARD-002` | PASS | This public-safe report plus public-safety regression test | Private prompt, transcript, memory, token, account, path, callback payload, and screenshot evidence omitted |
| `MEMHARD-003` | PASS / SKIPPED | Power receipt recorded on-battery skip; current audit power later showed AC charging and no thermal/performance warning | Power gate behaved correctly at fire time |
| `MEMHARD-005` | PASS-SAFETY | Loaded LaunchAgent uses direct wrapper with explicit scheduled trigger marker and `StartCalendarInterval` hour 3 minute 0 | Generated timezone context still needs careful interpretation during timezone-shift |
| `MEMHARD-010` | PASS | Jun 9 and Jun 10 schedule trigger receipts exist and are public-safe | Both recent receipts finalized as power skips with no run id, as expected |
| `MTM-006` | PARTIAL / DEGRADED | Transcript indexes total 50 processed and 0 pending/deferred/skipped, but RAG health failed | Browser recall/source-card proof blocked by RAG/Docker unavailable |
| `RAG-001` | FAIL / DEGRADED | Generated config expects local RAG API, but health/metrics connection failed and Docker socket was unavailable | This is a live prerequisite failure, not just an unrun proof gap |
| `PW-033` | PASS | Workbench API, Scheduler DB, GlassHive DB, callbacks, and Playwright all showed Jun 10 completed run | Jun 9 failure remains historical evidence and recovered today |
| `SCHED-002` | PASS | Built-in task due at `2026-06-10T10:00:00Z`, completed at `10:34:18Z` | Started inside the due/grace window and next run is Jun 11 |
| `SCHED-006` | PASS | Child run, parent task ledger, GlassHive run, and terminal callback agreed | Parent ledger status `success`, delivery `sent` |
| `SCHED-009` | PASS | Callback outbox had 0 pending/delivering rows; latest run callbacks delivered once | 2 historical dead-letter rows remain watch-only |
| `MEMCONT-001` | PASS / PARTIAL | Existing Jun 8 continuity capture was `ok`; current dedupe dry-run passed | Fresh continuity capture was not run because it writes App Support state |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Viventium overnight routines.
- Requirement: Memory hardening, transcript maintenance, Workbench scheduled reflection, Scheduler,
  GlassHive callbacks, RAG health, and continuity checks must be judged after their real due windows
  without hiding skipped, stale, failed, degraded, or not-due routines.
- Use case: Daily read-only health review after the expected overnight maintenance windows.
- QA cases: `MEMHARD-001`, `MEMHARD-003`, `MEMHARD-005`, `MEMHARD-010`, `MTM-006`,
  `RAG-001`, `PW-033`, `SCHED-002`, `SCHED-006`, `SCHED-009`, and `MEMCONT-001`.
- Expected result: Due routines either run, skip for a documented policy reason, or are marked
  not due; visible Workbench state agrees with Scheduler/GlassHive ledgers; degraded RAG/power
  prerequisites are not converted into fake passes.
- Actual evidence: Memory hardening produced a valid scheduled trigger receipt and skipped on
  battery; Workbench completed the Jun 10 chain through Scheduler, GlassHive, callback, and visible
  UI; RAG/Docker health failed; focused tests and transcript evals passed.
- Remaining gap: Repair local RAG/Docker sidecars, rerun browser recall/source-card proof, monitor
  the next Workbench run after the Jun 9 provider-connectivity failure, and rerun Claude review when
  available.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Nightly routines against memory, transcript/RAG, Workbench, Scheduler, GlassHive, and continuity cases listed above |
| Code owning path | Which code path owns the behavior? | Memory hardener wrapper, config compiler outputs, Scheduler DB/task engine, Prompt Workbench, GlassHive runtime, and RAG sidecar |
| Docs and nested docs/repos | Which docs define expected behavior? | `01_Key_Principles.md`, `20_Memory_System.md`, `39_Installer_and_Config_Compiler.md`, `45_Runtime_Feature_QA_Map.md`, and feature QA cases |
| Scripts or harnesses | Which checks exercised the behavior? | Focused release pytest slice, transcript eval runner, memory-dedupe dry-run, Workbench API/DB checks, and Playwright CLI |
| Local/external prerequisite state | Which prerequisites were healthy or degraded? | Core web, Scheduler, Workbench, and GlassHive healthy; memory skipped by power policy; RAG/Docker degraded |
| Logs | Which sanitized logs confirm or contradict the result? | Memory-hardening receipt/log, Scheduler health logs, Workbench health logs, and GlassHive runtime/callback evidence |
| DB/state/persistence | Which sanitized state confirms it? | Scheduler task/run rows, GlassHive run/callback rows, trigger receipts, transcript index counts, latest continuity capture, and dedupe counts |
| Generated/shipped artifact | Which generated artifact was inspected? | Generated runtime key summary and loaded LaunchAgent schedule/command shape |
| Real user path | Which surface was exercised like a user? | Playwright opened Prompt Workbench, selected the built-in schedule, inspected recent run state, and reloaded the page |
| Visual/UX comparison | Does visible UI match backend evidence? | Yes for Workbench: visible Jun 10 completed row matched Scheduler/GlassHive/callback rows |
| Not run / blocked | Which required surface was not run? | Browser recall/source-card proof blocked by RAG/Docker unavailability; fresh continuity capture not run because it writes App Support state; Claude review unavailable |

## User-Grade Evidence

- Surface exercised: Prompt Workbench in a real browser through Playwright CLI, plus local CLI/status
  surfaces for memory, RAG, scheduler, and dedupe.
- Real user path: Opened local Workbench, selected `Subconscious Deep Thought`, inspected recent run
  history and proposal presence, reloaded the page, and closed the browser.
- Visible outcome: Workbench showed the built-in schedule enabled, next Jun 11 local run, Jun 10
  completed run, Jun 9 failed run, and Jun 8 completed run.
- Expanded/detail state: Schedules detail showed the GlassHive host execution route, recent run list,
  and a fresh Jun 10 memory-proposal entry.
- Persistence/reload result: Workbench rendered again after reload; API/DB evidence confirmed the
  same next-run and latest-run state.
- Local/external prerequisite state: Scheduler, Workbench, and GlassHive health responded; memory
  receipt recorded scheduled power skip; RAG and Docker-backed sidecars were unavailable.
- Evidence retrieval classification, if applicable: RAG connection failed, so recall proof was
  blocked by local prerequisite unavailability rather than treated as successful-empty.
- Fallback path, if applicable: No browser/computer/local-delegation fallback was used because the
  audit was read-only and the relevant blocker was local sidecar availability.
- Backend/log/DB confirmation: Scheduler child/parent rows, GlassHive run/callback rows, trigger
  receipts, transcript indexes, and status output matched the visible/CLI findings.
- Final model/runtime wording check: The report labels memory hardening as SKIPPED, Workbench as
  PASS, and RAG as DEGRADED; no visible state is contradicted.
- Substitution check: Logs, DB rows, API responses, source inspection, and tests are supporting
  evidence; Playwright supplied the required browser-visible Workbench proof, while browser recall
  remains blocked rather than substituted with backend state.

## Timing Anchor

| Field | Evidence |
| --- | --- |
| Audit start | `2026-06-10 13:16:05 <observed-local-tz-abbrev>` / `2026-06-10T11:16:05Z` |
| System timezone | `<observed-system-timezone>` from `/etc/localtime`; `date` reported `<observed-local-tz-abbrev> +0200` |
| `systemsetup` timezone | Not available without administrator access |
| Automation fire time | Intended `2026-06-10T11:15Z` / `13:15 <observed-local-tz-abbrev>`; audit started about one minute later |
| Previous automation run from prompt | `2026-06-09T11:31:54.144Z` |
| Automation cadence note | Codex Desktop RRULE is UTC in this local Desktop environment |

## Due Windows Used

| Routine | Source schedule | Due window local | Due window UTC | Grace used | Actual evidence | Judgment |
| --- | --- | --- | --- | --- | --- | --- |
| Memory hardening, generated context | `0 3 * * *`, timezone context `<configured-local-timezone>` | Jun 10 `09:00-09:45 <observed-local-tz-abbrev>` | Jun 10 `07:00-07:45Z` | 45 minutes | Receipt fired `09:13 <observed-local-tz-abbrev>` / `07:13Z`, skipped on battery, exit 0 | SKIPPED / PASS-SAFETY |
| Memory hardening, LaunchAgent nominal local clock | `StartCalendarInterval` hour 3 minute 0 on current system timezone | Jun 10 `03:00-03:45 <observed-local-tz-abbrev>` | Jun 10 `01:00-01:45Z` | 45 minutes | LaunchAgent receipt arrived later after timezone-shift/wake context | Timing note only; not a failure by itself |
| Workbench nightly reflection | Workbench daily `03:00`, `<workbench-schedule-timezone>` | Jun 10 `12:00-12:45 <observed-local-tz-abbrev>` | Jun 10 `10:00-10:45Z` | 45 minutes | Started `10:19:51Z`, completed `10:34:18Z` | PASS |
| Transcript ingest/vector maintenance | Memory-hardening scheduled run | Same as memory hardening | Same as memory hardening | 45 minutes | No model/vector run because power gate skipped before work | SKIPPED today; latest successful artifacts Jun 8 |
| User-level morning schedules | User-level daily `08:00`, `<workbench-schedule-timezone>` | Jun 10 `17:00 <observed-local-tz-abbrev>` | Jun 10 `15:00Z` | Not applied | Audit ran before due time | NOT DUE |
| Prompt benchmark/eval routines | No separate due scheduled routine found | Not due | Not due | Not applied | Supporting evals were run manually | NOT DUE |

Timezone-shift/timezone note: the generated memory-hardening timezone context remained `<configured-local-timezone>`,
while the current system timezone was `<observed-system-timezone>`. Per the June 8 contract, QA used the
public-safe trigger receipt as the authoritative scheduled-delivery evidence and did not treat
timezone-shift, DST, or launchd wake coalescing as degradation when the receipt finalized cleanly.

## Routine Results

### Memory Hardening

Status: SKIPPED / PASS-SAFETY.

Evidence:

- Loaded `ai.viventium.memory-harden` LaunchAgent was not running at audit time, had `runs=2`,
  `last exit code=0`, used the direct wrapper path with `--scheduled --trigger launchd`, and had
  `StartCalendarInterval` hour 3 minute 0.
- Jun 10 schedule receipt: `trigger_source=launchd`, fired `2026-06-10T07:13:18Z`, timezone at
  fire `<observed-system-timezone>`, schedule payload `0 3 * * *` with timezone context `<configured-local-timezone>`,
  `status=skipped`, `reason=on_battery_power`, `exit_code=0`, no run id.
- Jun 9 schedule receipt also finalized as `skipped` / `on_battery_power` / exit 0.
- Current audit power later showed AC charging, battery present, and no thermal/performance
  warning; the receipt proves the scheduled fire itself was on battery.
- Latest model-backed hardener remains `20260608T100005Z`: `success`, OpenAI/GPT-5.5/xhigh,
  one hardener attempt, zero failures, no fallback, complete 135/135-message lookback, no input-cap
  omission, zero changed memory keys, transcript vector upload count 4 plus 1 inventory, zero
  deletes, zero vector-presence errors, and no failure file.

Not run:

- No `apply`, transcript ingest/catch-up, rebuild, repair, or model-backed work was started by this
  audit.

### Meeting Transcript Maintenance

Status: SKIPPED today due memory-hardening power gate; latest artifact state healthy, recall proof
blocked by RAG.

Evidence:

- The latest successful hardener run saw 30 transcript files, ignored 4 by config, had 3 pending
  before processing, 23 unchanged, 0 summary failures, 0 cap skips, 0 partial/truncated/too-large
  files, and 0 vector-presence errors.
- Persisted transcript indexes currently total 50 processed entries and 0 pending, deferred, or
  skipped entries across three private indexes.
- Because Jun 10 skipped before model/vector work, there is no new Jun 10 run directory and that is
  expected.

Blocked:

- Browser transcript recall/source-card proof and direct vector-document proof were not run because
  the local RAG service was unavailable.

### Conversation Recall / RAG

Status: FAIL / DEGRADED prerequisite.

Evidence:

- Generated runtime config expects local RAG on port `8110`.
- `GET /health` and unauthenticated `/metrics` checks against the local RAG API failed to connect.
- Docker CLI could not connect to the user Docker socket, so Docker-backed RAG/search sidecars were
  not inspectable/running through the expected local path.
- `bin/viventium status` reported the product needs attention: core web surfaces, Scheduler,
  GlassHive, and Prompt Workbench were running, while Conversation Recall/RAG, local Web Search
  sidecars, and Microsoft 365 MCP were starting/unhealthy.

Classification:

- This is not merely an unrun browser proof gap. It is a degraded local prerequisite that blocks
  recall proof and should be repaired outside the read-only audit.

### Workbench Nightly Reflection

Status: PASS for Jun 10, with a recovered Jun 9 failure noted.

Evidence:

- Built-in `Subconscious Deep Thought` definition was active, daily `03:00`
  `<workbench-schedule-timezone>`, executor `glasshive_host`, memory mode `propose`, next run
  `2026-06-11T10:00:00Z`.
- Scheduler child run was due `2026-06-10T10:00:00Z`, started `10:19:51Z`, completed
  `10:34:18Z`, status `completed`, and included rendered/variable hashes plus private detail
  pointer.
- Parent task ledger reported `last_status=success`, delivery outcome `sent`, and
  `last_delivery_at=2026-06-10T10:34:18Z`; catch-up policy remained `catch_up` with
  `max_late_s=43200`.
- GlassHive run completed from `10:19:51Z` to `10:34:18Z`, output present, no error text, no retry.
- Callback outbox delivered worker resume, run queued, run started, and run completed events in one
  attempt each.
- Playwright opened the local Workbench, saw `Subconscious Deep Thought` enabled with next Jun 11
  at 12:00 PM local, opened detail, saw recent runs `completed` for Jun 10, `failed` for Jun 9,
  and `completed` for Jun 8, plus a fresh Jun 10 memory proposal. The browser was closed and
  private snapshots from this run were deleted.

Recent failure:

- The Jun 9 Workbench due run failed after starting inside its due window. GlassHive delivered a
  terminal failed callback in one attempt; sanitized diagnostics point to Codex websocket/DNS
  connectivity failures. Jun 10 recovered successfully, so this is historical failure evidence, not
  a current broken chain.

### Scheduler, GlassHive, And Callback Health

Status: PASS for built-in nightly substrate.

Evidence:

- Scheduler health endpoint returned ok and recent logs showed health checks plus bootstrap-schedule
  requests succeeding.
- Workbench health endpoint returned ok.
- GlassHive health endpoint returned ok.
- Callback aggregate: `delivered=307`, `dead_lettered=2`, `pending=0`, `delivering=0`; newest Jun
  10 callbacks delivered once.
- The two dead-letter rows are historical May rows and did not block the Jun 10 run.

### User-Level Schedules

Status: NOT DUE at audit time for the active morning rows.

Evidence:

- Several active user-level morning schedules had next due `2026-06-10T15:00:00Z`, which was after
  the `11:16Z` audit start.
- These rows are separate account/action evidence and did not block the built-in Workbench nightly
  or memory-hardening contract.

### Continuity And Dedupe

Status: PASS / PARTIAL.

Evidence:

- Existing latest continuity capture from Jun 8 was `ok` with no warnings or errors.
- Fresh continuity capture was not run because the command writes a new App Support state file.
- Current memory-dedupe dry-run reported zero duplicate groups, zero duplicate docs, zero deletes,
  and did not create indexes.
- Focused continuity release tests passed as part of the regression slice.

## Automated Evidence

```bash
node qa/meeting-transcript-memory/evals/run-evals.cjs
# 12 passed, 0 failed

uv run --with pytest --with pyyaml --with requests --with packaging --with pydantic --with croniter \
  python -m pytest tests/release/test_scheduled_glasshive_prompts.py \
  tests/release/test_memory_hardening_contract.py tests/release/test_default_nightly_routines.py \
  tests/release/test_rag_api_override_contract.py tests/release/test_continuity_audit.py \
  tests/release/test_qa_results_public_safety.py -q
# 82 passed, 5 skipped

bin/viventium memory-dedupe --dry-run --json
# duplicateGroups=0, duplicateDocs=0, deletedCount=0, indexesCreated=false

bin/viventium status
# needs attention: core web/Scheduler/GlassHive/Workbench running; RAG/search/MS365 sidecars degraded
```

Additional read-only checks:

- `date`, `date -u`, `/etc/localtime`, and LaunchAgent inspection.
- Generated runtime env key summary with secrets, user/account values, URLs, and local paths
  redacted.
- Memory-hardening trigger receipts and summary JSON.
- Transcript index counts.
- Scheduler, scheduled prompt, GlassHive run, and callback outbox SQLite summaries.
- Workbench and GlassHive health endpoints.
- Playwright CLI browser QA against Prompt Workbench; private snapshots deleted.

## Claude Review

- `ClaudeViv` was unavailable on this machine.
- Local Claude CLI was attempted in review-only mode with tools disabled and a sanitized evidence
  prompt, but the CLI refused the run because the account was at its session limit until later in
  the local day.
- No Claude second-opinion output was obtained or incorporated. This is a QA-process gap, not
  product evidence.

## Findings

1. Memory hardening did not run model work on Jun 10 because the scheduled receipt recorded
   `on_battery_power`. Severity: none for product behavior; classify as expected SKIPPED /
   PASS-SAFETY. Next action: keep the machine on AC for the next due window if model-backed
   maintenance is desired.
2. Conversation Recall/RAG is degraded today. Severity: P2 for recall/RAG user paths because local
   RAG health and Docker-backed prerequisites are unavailable. Next action: repair/restart Docker
   and the RAG/search sidecars outside this read-only audit, then rerun RAG health plus browser
   recall/source-card proof.
3. Jun 9 Workbench nightly failed due Codex websocket/DNS connectivity, then Jun 10 recovered.
   Severity: P2 if repeated; one overnight reflection was missed, but the built-in chain is healthy
   today. Next action: monitor Jun 11 and consider classifying this provider/network failure more
   specifically than `unknown` if it recurs.
4. Fresh continuity capture was not run because it writes App Support state. Severity: low QA proof
   gap; existing Jun 8 capture and current dedupe/test evidence are healthy.
5. Claude second-opinion review could not be completed because ClaudeViv was unavailable and local
   Claude was rate/session-limited. Severity: QA-process gap; rerun after the limit resets when
   release signoff needs the independent review.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No raw private prompts, memories, chats, transcripts, screenshots, account identifiers, or
  customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or
  raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports,
  App Support state dumps, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized statuses, counts, timestamps, and conclusions.

## Verdict

Overall status: PARTIAL / DEGRADED.

The built-in Workbench nightly reflection completed successfully today through the documented
Scheduler -> GlassHive -> callback -> Workbench chain, and memory hardening produced authoritative
launchd trigger receipts. The Jun 10 memory maintenance lane intentionally skipped on battery, so
there is no stale-run failure to fix there. The live degraded item is Conversation Recall/RAG:
local RAG and Docker-backed sidecars were unavailable, blocking browser recall/vector proof and
keeping the broader overnight-routine health review from a clean PASS.
