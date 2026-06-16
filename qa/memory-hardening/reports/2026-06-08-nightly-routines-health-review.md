# 2026-06-08 Nightly Routines Health Review

## Summary

- Result: PARTIAL.
- Build/source under test: local Viventium checkout and active installed local-prod runtime.
- Runtime/artifact under test: generated App Support runtime config, memory hardener LaunchAgent,
  Scheduler, Prompt Workbench, GlassHive, RAG sidecar, transcript index state, and QA reports.
- Environment: local macOS runtime, system timezone `America/Toronto`, audit at
  `2026-06-08T11:16:21Z`.
- Tester: Codex automation `viventium-nightly-routines-qa`.
- Related change: daily read-only overnight-routine QA audit after the observed `10:00Z` cadence.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `MEMHARD-001` | PARTIAL | Latest hardener run succeeded; trigger authority unresolved | Generated/LaunchAgent `03:00 America/Toronto` schedule was not proven as the source of the observed `10:00Z` run |
| `MEMHARD-002` | PASS | This public-safe report plus public-safety test | Private prompt, transcript, memory, token, account, and path evidence omitted |
| `MEMHARD-003` | PASS | AC power, no thermal/performance warning | No power or idle override used |
| `MEMHARD-005` | PARTIAL | LaunchAgent loaded and successful, but schedule truth unresolved | Needs trigger-source proof before release signoff |
| `MTM-006` | PASS/PARTIAL | RAG health `UP`, transcript indexes 50 processed, browser recall not rerun | Nightly artifact contract passed; recall answer proof remains separate |
| `RAG-001` | PASS/PARTIAL | RAG sidecar `UP`, vectors uploaded, browser recall not rerun | Service health is not a substitute for recall answer QA |
| `PW-029` | PASS | Playwright Workbench detail showed Jun 8 completed run | Snapshot files deleted after sanitized observation |
| `SCHED-002` | PASS | Scheduler parent ledger and child run completed | Built-in task next due Jun 9 `10:00Z` |
| `SCHED-006` | PASS | Terminal callback and parent ledger matched | Latest callback delivered in one attempt |
| `SCHED-009` | PASS | Callback backlog counts clean | Two historical dead-letter rows remain watch-only |
| `MEMCONT-001` | PASS | Continuity capture `ok`, recall rebuild not required | Dedupe dry-run found zero duplicates |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `MEMHARD-UC-001` | Inspect scheduled memory-hardening result after overnight due window | CLI/status, LaunchAgent state, logs/state | PARTIAL | CLI status showed latest run success | Run summary, redacted log, LaunchAgent plist, generated runtime env | Trigger authority between configured `03:00` and observed `10:00Z` remains unresolved |
| `MEMHARD-UC-006` | Inspect install/upgrade memory-hardening readiness after scheduled run | CLI/status and LaunchAgent state | PARTIAL | Latest hardener completed | Generated config and LaunchAgent stable, but no launchd last-run timestamp found | Prove which trigger fired today's hardener |
| `PW-029` | Inspect built-in Workbench scheduled prompt run | Playwright CLI browser | PASS | Workbench showed `Subconscious Deep Thought` enabled, Jun 8 completed, next Jun 9 | Scheduler DB, GlassHive DB, callback outbox | None for normal in-grace run |
| `SCHED-UC-002` | Verify trigger and delivery ledger | Scheduler DB, GlassHive DB, Workbench browser | PASS | Workbench detail showed Jun 8 completed | Parent task success/sent, child completed, callback delivered | Live delayed catch-up remains separate case |
| `SCHED-UC-009` | Inspect callback outbox after scheduled delivery | GlassHive health and DB | PASS | No user-visible backlog | 0 queued/active, 0 pending/delivering, latest callbacks delivered once | Historical dead-letter rows need eventual archive/explanation |
| `MEETING-UC-002` | Verify transcript maintenance with RAG prerequisite | Hardener status, RAG health | PASS | Not browser-visible for this nightly artifact check | 50 processed indexes, 4 vectors uploaded, RAG `UP` | None for artifact maintenance |
| `MEETING-UC-003` | Verify browser transcript recall answer after maintenance | Not run | PARTIAL | Not run in this read-only overnight audit | RAG health and index state only | Browser recall/source-card proof remains separate |
| `MEMCONT-UC-001` | Capture continuity state and dedupe dry-run | CLI/status | PASS | CLI commands completed | Continuity `ok`, recall rebuild false, dedupe counts zero | None |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Viventium nightly routines.
- Requirement: Memory hardening, transcript maintenance, Workbench scheduled prompts, Scheduler,
  GlassHive callbacks, RAG health, and continuity must complete after the real due window without
  hiding skipped, stale, failed, or not-due routines.
- Use case: Daily read-only overnight health review after the observed `10:00Z` routine cadence.
- QA case: `MEMHARD-001`, `MEMHARD-005`, `MTM-006`, `RAG-001`, `PW-029`, `SCHED-002`,
  `SCHED-006`, `SCHED-009`, and `MEMCONT-001`.
- Expected result: Due built-in routines run or are honestly marked skipped/not due; visible
  Workbench state matches Scheduler/GlassHive ledgers; no power/thermal skip is hidden; public QA
  evidence stays sanitized.
- Actual evidence: Workbench and memory hardening both completed around `10:00Z`, transcript/RAG
  artifact maintenance succeeded, Scheduler/GlassHive/callback state matched, automated checks
  passed, and continuity/dedupe were clean.
- Remaining gap or fix: Memory hardening trigger authority is unresolved because generated config
  and the LaunchAgent declare `03:00 America/Toronto`, while the observed successful run occurred at
  `10:00Z`.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Nightly routines against memory, transcript/RAG, Workbench, Scheduler, GlassHive, and continuity cases listed above |
| Code owning path | Which code path owns the behavior? | Memory hardener wrapper, generated runtime compiler, Scheduler DB/task engine, Prompt Workbench, GlassHive runtime, and RAG sidecar |
| Docs and nested docs/repos | Which docs or nested repo docs define the expected behavior? | `01_Key_Principles.md`, `20_Memory_System.md`, `39_Installer_and_Config_Compiler.md`, `45_Runtime_Feature_QA_Map.md`, feature QA cases, and v0.4 runtime docs |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | Playwright CLI, transcript eval runner, focused release pytest slice, memory-dedupe dry-run, continuity-audit |
| Local/external prerequisite state | Which required local service, provider, Docker-backed sidecar, OAuth grant, API key, model, or hosted dependency was proven healthy or degraded? | AC power, no thermal warning, RAG `UP`, Scheduler `ok`, Workbench `ok`, GlassHive `ok`, OpenAI/GPT-5.5 hardener telemetry clean |
| Logs | Which sanitized logs confirm or contradict the result? | Redacted memory hardener run log; launchd log proof did not expose trigger timestamp |
| DB/state/persistence | Which sanitized state, DB count/hash, persisted message, config, or artifact confirms it? | Scheduler task/run rows, GlassHive run/callback rows, transcript index counts, memory hardener summary, continuity manifest |
| Generated/shipped artifact | Which generated config, compiled bundle, prebuilt helper, or installed artifact was inspected when applicable? | Generated runtime env and loaded LaunchAgent |
| Real user path | Which browser/computer, Telegram, voice, installer, CLI, MCP/tool, scheduler, or GlassHive path was used like a user? | Playwright CLI browser opened Prompt Workbench schedule/detail; CLI/status commands inspected local runtime |
| Visual/UX comparison | Does the visible UI/UX or delivered result match the expected behavior and supporting evidence? | Yes for Workbench: visible Jun 8 completed run matched Scheduler/GlassHive/callback rows |
| Not run / blocked | Which required surface was not run, and why is the result partial or blocked? | Browser recall/source-card proof was not rerun; memory trigger-source proof could not be recovered from launchd logs |

## User-Grade Evidence

- Surface exercised: Prompt Workbench in a real browser through Playwright CLI; local CLI/status
  surfaces for memory, continuity, and dedupe.
- Real user path: browser opened Prompt Workbench, selected the built-in scheduled prompt, inspected
  recent run detail, then reloaded to confirm persistence.
- Visible outcome: Workbench showed `Subconscious Deep Thought` enabled, next Jun 9 6:00 AM, and
  recent run `completed` for Jun 8 6:00 AM.
- Expanded/detail state: Schedules detail panel showed recent completed runs and memory proposal
  entry for Jun 8.
- Persistence/reload result: after reload, the schedule/detail state was still visible.
- Local/external prerequisite state: AC power, no thermal/performance warning, RAG `UP`, Scheduler
  `ok`, Workbench `ok`, GlassHive `ok`, Docker-backed RAG containers running.
- Evidence retrieval classification, if applicable: RAG service health was available; browser recall
  answer proof was not run, so no successful-empty/provider unavailable/timeout/rate limit/auth
  classification was needed for a user answer.
- Fallback path, if applicable: no browser/computer/local-delegation fallback was needed; primary
  local surfaces responded.
- Backend/log/DB confirmation: scheduler child/parent rows, GlassHive run/callback rows, memory
  hardener summary/log, transcript indexes, and continuity manifest matched the visible result.
- Final model/runtime wording check: Workbench visible wording did not contradict backend state;
  the memory-hardening trigger-source gap is documented as PARTIAL instead of overclaiming PASS.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for any required visible-UI, detail-state,
  persistence, or wording step.

## Automated Evidence

```bash
node qa/meeting-transcript-memory/evals/run-evals.cjs
uv run --with pytest --with pyyaml --with requests --with packaging --with pydantic --with croniter \
  python -m pytest tests/release/test_scheduled_glasshive_prompts.py \
  tests/release/test_memory_hardening_contract.py tests/release/test_default_nightly_routines.py \
  tests/release/test_rag_api_override_contract.py tests/release/test_continuity_audit.py \
  tests/release/test_qa_results_public_safety.py -q
bin/viventium memory-dedupe --dry-run --json
bin/viventium continuity-audit
uv run --with pytest --with pyyaml --with requests --with packaging \
  python -m pytest tests/release/test_qa_results_public_safety.py -q
```

## Findings

- Defects: unresolved memory hardening trigger authority between generated/LaunchAgent local
  `03:00` schedule and observed `10:00Z` successful run.
- Regressions: none proven in the built-in Workbench/Scheduler/GlassHive chain.
- Flakes: first focused pytest attempt failed setup due missing ephemeral `pydantic`/`croniter`;
  rerun with dependencies passed.
- Environment issues: local Claude `--bare` review mode was not logged in, so normal local Claude
  CLI was used with tools disabled.
- Residual risks: two historical GlassHive dead-letter callback rows remain; browser recall/source
  grounding was not rerun; live delayed-tick catch-up remains a separate future proof.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails,
  account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or
  raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB
  exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions
  only.

## Verdict

Overall status: **PARTIAL**.

The built-in overnight work completed successfully at the observed `10:00Z` cadence, but memory
hardening still has an unresolved trigger-authority gap: generated config and the loaded LaunchAgent
declare a local `03:00 America/Toronto` schedule, while the only observed June 8 hardener run started
at `10:00Z` (`06:00 America/Toronto`). This did not cause a user-visible miss today, so it is not a
nightly execution failure. It is a schedule-truth gap that needs follow-up before release signoff.

## Timing Anchor

| Field | Evidence |
| --- | --- |
| Audit start | `2026-06-08 07:16:21 EDT` / `2026-06-08T11:16:21Z` |
| Later anchor | `2026-06-08 07:17:40 EDT` / `2026-06-08T11:17:40Z` |
| System timezone | `America/Toronto` from `/etc/localtime`; `date` reported `EDT` |
| Automation fire time | Intended `2026-06-08 07:15 EDT` / `2026-06-08T11:15Z` |
| Automation cadence note | Codex Desktop RRULE is UTC in this local Desktop environment |

## Due Windows Used

| Routine | Source schedule | Due window local | Due window UTC | Grace used | Judgment |
| --- | --- | --- | --- | --- | --- |
| Memory hardening, configured | `0 3 * * *`, `America/Toronto`; LaunchAgent Hour `3`, Minute `0` | Jun 8 `03:00-03:45 EDT` | Jun 8 `07:00-07:45Z` | 45 minutes | **PARTIAL evidence**: no distinct `07:00Z` run was proven |
| Memory hardening, observed cadence | Recent successful run cadence and automation memory | Jun 8 `06:00-06:45 EDT` | Jun 8 `10:00-10:45Z` | 45 minutes | **PASS execution**: run `20260608T100005Z` finished at `10:03:37Z` |
| Workbench nightly reflection | Workbench definition daily `03:00`, `America/Los_Angeles` | Jun 8 `06:00-06:45 EDT` | Jun 8 `10:00-10:45Z` | 45 minutes | **PASS** |
| Transcript ingest/vector maintenance | Memory-hardening run | Jun 8 `06:00-06:45 EDT` | Jun 8 `10:00-10:45Z` | 45 minutes | **PASS for nightly artifact maintenance** |
| User-level provider reconnect rows | Scheduler DB rows | Jun 8 `11:00 EDT` | Jun 8 `15:00Z` | Not applicable | **NOT DUE** at audit time |
| Prompt benchmark/eval routines | No separate due scheduled routine found | Not due | Not due | Not applicable | **NOT DUE**; supporting evals were run manually |

## Runtime And Schedule Evidence

- Generated runtime still had memory hardening enabled with provider `openai`, model `gpt-5.5`,
  effort `xhigh`, schedule `0 3 * * *`, and timezone `America/Toronto`.
- The loaded `ai.viventium.memory-harden` LaunchAgent existed, was not running at audit time,
  reported `runs=1`, `last exit code=0`, and invoked the supported memory hardening wrapper with
  generated runtime state. Its `StartCalendarInterval` was Hour `3`, Minute `0`.
- The only June 8 memory hardening run directory was `20260608T100005Z`.
- Recent hardener run directories showed the observed successful `10:00Z` cadence on Jun 2, Jun 3,
  Jun 4, and Jun 8. No useful launchd timestamp was available from the read-only log pass.
- Workbench scheduled prompt definition was active, titled `Subconscious Deep Thought`, timezone
  `America/Los_Angeles`, daily `03:00`, memory write mode `propose`, template
  `workbench_nightly_subconscious_thought_formation_v1`.

## Routine Results

### Memory Hardening

Status: **PARTIAL** because execution succeeded, but trigger authority is unresolved.

Evidence:

- Latest run: `20260608T100005Z`, mode `apply`, status `success`, started
  `2026-06-08T10:00:05Z`, finished `2026-06-08T10:03:37Z`.
- Provider/model telemetry: `openai` / `gpt-5.5` / `xhigh`; advisory probe succeeded; hardener
  model attempts `1`, failures `0`, no fallback evidence.
- One selected user hash; lookback complete with `135/135` messages fed and no input-cap omission.
- Saved-memory changes: no accepted changed keys, one rejected operation, no hardener failure file.
- Read-only trigger follow-up: `launchctl blame` did not expose a last-run timestamp, unified log
  query did not prove whether the `03:00` LaunchAgent path fired or skipped, and no LaunchAgent
  timezone override was set.

Required follow-up:

- Identify the authoritative memory-hardening trigger for installed local prod: LaunchAgent-only,
  Scheduler/Workbench-mediated, or intentionally shared.
- Reconcile generated schedule, LaunchAgent, and observed run cadence so the next audit does not
  need to infer from historical `10:00Z` behavior.
- Prove there is no double-fire risk and no gap if Workbench fails but memory hardening is expected
  independently.

### Meeting Transcript Maintenance

Status: **PASS** for the overnight artifact contract, with browser recall proof still separate.

Evidence:

- Latest hardener transcript telemetry: `30` files seen, `4` ignored by config, `23` unchanged,
  `3` pending before processing, `0` summary failures, `0` skipped by cap, `0` partial/truncated/
  too-large files, `0` vector-presence errors.
- Apply results uploaded `4` transcript vectors, deleted `0`, and uploaded `1` inventory vector in
  `detailed_summary_only` mode.
- Persisted transcript indexes after the run showed `50` processed files, `0` pending, `0`
  deferred, and `0` skipped.
- RAG health on the generated port returned `UP`.

Not run:

- Browser recall/source-card grounding and direct vector-document proof were not rerun in this
  overnight audit. That remains a QA proof gap for recall behavior, not evidence that the nightly
  artifact routine failed.

### Workbench Nightly Reflection

Status: **PASS**.

Evidence:

- Scheduler task was active with executor `glasshive_host`, channel `workbench`, catch-up policy
  mode `catch_up`, max late seconds `43200`.
- Latest scheduled prompt run was due `2026-06-08T10:00:00Z`, started `10:00:13Z`, completed
  `10:03:23Z`, status `completed`, error class `null`, and had rendered/variable hashes plus a
  private detail pointer.
- GlassHive run started and ended in the same window, state `completed`, output present, error text
  length `0`, retry attempts `0`.
- Callback outbox delivered `worker.resumed_by_alias`, `run.queued`, `run.started`, and
  `run.completed` for the Jun 8 run in one attempt each.
- Parent scheduler ledger reported `last_status=success`, delivery outcome `sent`, and
  `next_run_at=2026-06-09T10:00:00Z`.
- Playwright CLI real-browser QA opened Prompt Workbench, selected `Subconscious Deep Thought`,
  saw it enabled with next run Jun 9 6:00 AM, and saw recent run `completed` for Jun 8 6:00 AM.
  After reload, the schedule/detail state remained visible. Temporary Playwright snapshots were
  deleted because they contained private prompt context.

### Scheduler, GlassHive, And Callback Health

Status: **PASS**, with bounded historical callback debt noted.

Evidence:

- Scheduler `/health` returned `ok` with runtime identity hashes and local prod isolated profile.
- Prompt Workbench `/api/health` returned `ok`.
- GlassHive `/health` returned `ok`; queued runs `0`, active runs `0`, callback pending `0`,
  callback delivering `0`, callback max attempts `0`, oldest pending age `0`.
- Callback outbox aggregate showed no active backlog. There were `2` historical dead-letter rows
  from earlier work; no fresh dead-letter row appeared in the Jun 8 chain.

### Power And Thermal

Status: **PASS**.

Evidence:

- Machine was on AC power, internal battery was charged, and no thermal or performance warning was
  recorded.
- The audit did not pass `--ignore-power-gate`, `--ignore-idle-gate`, or start model-backed
  hardening/ingest/catch-up work.

### User-Level Provider Reconnect Rows

Status: **NOT DUE / separate account action**.

Evidence:

- Active user-level reconnect rows had next due time `2026-06-08T15:00:00Z`
  (`11:00 America/Toronto`), after this audit window.
- These rows did not block the built-in Workbench or memory-hardening evidence inspected here.

## Commands And Checks

| Command or check | Result |
| --- | --- |
| Playwright CLI Workbench browser run | PASS: visible enabled schedule, Jun 8 completed run, persistence after reload |
| `node qa/meeting-transcript-memory/evals/run-evals.cjs` | PASS: `12` passed, `0` failed |
| Focused release slice with `uv run` | PASS: `78` passed, `5` skipped |
| First pytest attempt | Setup-only failure: missing ephemeral `pydantic`/`croniter`; rerun with deps passed |
| `bin/viventium memory-dedupe --dry-run --json` | PASS: `0` duplicate groups/docs/deletes for memory entries and keys |
| `bin/viventium continuity-audit` | PASS: metadata-only capture `ok`, warnings `[]`, recall rebuild not required |
| RAG/Scheduler/Workbench/GlassHive health endpoints | PASS |
| LaunchAgent/log trigger timestamp proof | PARTIAL: no reliable last-run timestamp found |

Focused release slice:

```text
78 passed, 5 skipped
```

Transcript evals:

```text
12 passed, 0 failed
```

Continuity capture:

```text
status: ok
warnings: []
schedules latest: 2026-06-08T10:03:23.629178Z
recall rebuild required: false
```

## Second Opinion

ClaudeViv was not installed. The local Claude CLI was available; `--bare` mode was not logged in, so
the review was rerun through the normal local Claude CLI with tools disabled and a sanitized,
review-only prompt.

Claude agreed that Workbench, transcript/RAG artifact maintenance, provider reconnect due timing,
power/thermal, evals, dedupe, and service health were classified correctly. Claude disagreed with
the initial "PASS with watch item" framing for memory hardening and recommended **PARTIAL** because
the LaunchAgent/config schedule and observed run cadence remain two active schedule truths. This
report adopts that recommendation.

## Public-Safety Notes

- No raw transcript text, saved-memory values, private prompt text, account identifiers, tokens,
  raw callback payloads, screenshots, or local absolute paths were written to this report.
- Playwright snapshot files created during browser QA were deleted after extracting sanitized
  visible-state evidence.
- Raw App Support logs, DB rows, and private detail files remain outside the public repo.

## Next Actions

1. Resolve memory-hardening trigger authority across generated config, LaunchAgent, and observed
   `10:00Z` execution.
2. Add or run a read-only launchd timestamp proof for the next audit, or adjust the product status
   command to expose the trigger source and fired-at timestamp.
3. Keep historical GlassHive dead-letter rows visible in callback-health audits until they are
   intentionally archived or explained.
4. Rerun browser recall/source-card grounding separately if release signoff needs full RAG user-path
   proof, rather than treating service health as recall-answer acceptance.
