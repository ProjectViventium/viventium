<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# 2026-06-02 Nightly Routines Health Review

Overall status: **PARTIAL / degraded-provider and schedule-timing follow-up required**.

This was a read-only audit after the expected overnight window. The audit did not start
model-backed apply, transcript ingest/catch-up, vector rebuild, repair, background-agent work,
runtime stops, Docker stops, or owner-memory/conversation mutations. Raw prompts, transcript text,
account identifiers, private paths, tokens, callback payloads, browser snapshots, and proposal
contents stayed outside the public repo.

## Scope

Docs and QA sources reviewed:

- `AGENTS.md`
- `docs/requirements_and_learnings/01_Key_Principles.md`
- `docs/requirements_and_learnings/20_Memory_System.md`
- `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`
- `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`
- `docs/02_ARCHITECTURE_OVERVIEW.md`
- `docs/03_SYSTEMS_MAP.md`
- `qa/README.md`
- `qa/memory-hardening/cases.md`
- `qa/meeting-transcript-memory/cases.md`
- `qa/memory-continuity/cases.md`
- `qa/prompt-workbench/cases.md`
- `qa/conversation-recall-rag/cases.md`
- `qa/scheduling-cortex/cases.md`

## Power And Safety Gate

| Check | Evidence | Status |
| --- | --- | --- |
| Current power source | AC power, battery charged | `PASS` |
| Thermal state | No thermal/performance warning in current sample | `PASS` |
| Forced overrides | No `--ignore-power-gate`, `--ignore-idle-gate`, model apply, transcript catch-up, repair, or rebuild was run | `PASS` |
| Overnight sleep explanation | Power log around the documented 03:00 hardener window showed the machine awake with sleep prevented | `PARTIAL` for timing root cause |

No power-budget skip was recorded for today.

## Expected Vs Actual

| Routine | Expected overnight behavior | Actual evidence | Status |
| --- | --- | --- | --- |
| Memory hardening | Launch at configured `0 3 * * *` local schedule, then apply bounded memory hardening when power/idle gates allow it. | Latest run `20260602T100006Z` completed successfully, applied one user, and changed two memory keys. However it started at `2026-06-02T10:00:06Z` (06:00 local), while generated config and the loaded LaunchAgent both say 03:00 America/Toronto. No crontab or alternate LaunchAgent was found, and launchd logs did not identify the 10:00Z trigger. | `PARTIAL/DEGRADED` |
| Provider/model telemetry | Fresh run proves the configured OpenAI/GPT-5.5 path or reports fallback clearly. | Top-level status reports configured OpenAI/GPT-5.5, but per-user telemetry shows 2 model attempts, 1 `model_schema_error`, and final selection of Anthropic Claude Opus 4.7 `xhigh`. OpenAI probe passed, then the real proposal attempt fell back. | `PARTIAL/DEGRADED` |
| Transcript ingest/catch-up | Scan configured transcript source, process pending summaries, and keep vector lifecycle current. | Hardener saw 26 source entries, ignored 3, reused 23 unchanged processed files, had 0 pending, 0 skipped by cap, 0 vector-presence errors, and 0 requeued missing vectors. Aggregate index status is 47/47 processed across 3 indexes. | `PASS` for scan state, `PARTIAL` for browser recall signoff |
| Transcript summary/RAG artifacts | RAG service is reachable and transcript vector state is trustworthy before browser recall signoff. | RAG health returned `UP`; transcript indexes are current and hardener vector telemetry reported no missing-vector requeue. Direct JWT-backed vector-document proof and browser chat recall were not rerun. | `PARTIAL` |
| Scheduled Workbench deep-think routine | Built-in Workbench schedule dispatches through Scheduling Cortex -> GlassHive -> callback -> Workbench history. | Due `2026-06-02T10:00:00Z`, started `10:00:04Z`, completed `10:03:15Z`; Scheduler DB, GlassHive DB, callback outbox, metrics, and Playwright Workbench UI agreed. This 10:00Z time is expected for the Workbench schedule's America/Los_Angeles 03:00 setting. | `PASS` |
| Prompt benchmark / Workbench evals | Run if a scheduled nightly eval lane is documented. | No separate scheduled exact-model eval lane was found. The transcript eval bank was run manually and passed. | `PASS/N/A` |
| Scheduler state | Scheduler health, due-run state, and delivery ledger agree; stale/missed rows remain visible. | Latest built-in Workbench run completed and parent delivery ledger is `success` / `sent`. Active ledger still has 9 user-level rows marked `missed/missed`, 1 `fallback_delivered`, and 3 active rows with no status/outcome. | `PASS` for built-in, `PARTIAL` for active user-level rows |
| GlassHive callback outbox | Latest delivery has no active retry backlog or fresh dead-letter. | Latest callback events delivered in one attempt; metrics show 0 pending, 0 delivering, oldest pending age 0, and 2 historical dead-letter rows. | `PASS` |
| Continuity state | Restore/continuity metadata is current and does not require recall rebuild. | Continuity audit artifact status `ok`; messages surface available, schedules active count 14, recall rebuild not required, warnings/errors empty. Saved-memory count is 24 with latest timestamp still 2026-05-22 despite today's hardener apply summary, so the saved-memory timestamp/index path needs targeted follow-up. | `PASS/PARTIAL` |
| Status bar/manual ingest | Manual-ingest state is unchanged unless the user invoked it. | No changed manual-ingest state was found. | `PASS/UNCHANGED` |
| Brain readiness/status copy | User-visible status should agree with configured routes and runtime health. | Runtime status shows Primary AI configured in live services, but Brain Setup still says Primary AI needs connected-account setup. | `PARTIAL` |

## Evidence Checked

- Memory-hardening status, latest summary, redacted run log, transcript indexes, latest public
  efficiency marker, LaunchAgent state, crontab absence, and sanitized power-log window.
- Generated runtime config key presence for GlassHive, Workbench, memory hardening schedule/timezone,
  provider/model/fallbacks, transcript source, RAG URL, embeddings provider/model/profile, and
  scheduler port.
- Viventium status, dev-runtime alignment, Docker-backed helper service presence, and status rows.
- Scheduler `/health`, sanitized SQLite scheduled prompt run/task aggregates, and active ledger
  status buckets.
- GlassHive metrics, sanitized run aggregate, callback status counts, and callback event counts.
- Prompt Workbench real-browser UI through Playwright, including visible enabled built-in schedule,
  latest completed run, and private proposal summary count.
- RAG health, transcript index counts/statuses, continuity audit artifact, and memory-dedupe
  dry-run.
- Git drift was inspected; existing dirty/untracked files were present before this report and were
  not reverted.

## Read-Only Commands Run

| Command / check | Result |
| --- | --- |
| `pmset -g batt`, `pmset -g therm`, filtered `pmset -g log` | AC power, no current thermal/performance warning; machine awake around 03:00 local. |
| `bin/viventium memory-harden status --json` | Latest run success; transcript index 47/47 processed; no lock held. |
| Latest hardener `summary.json` / `run-log.redacted.jsonl` | Apply succeeded but OpenAI proposal attempt failed with `model_schema_error` and fell back to Anthropic. |
| `launchctl print` for memory hardener | Loaded LaunchAgent, not running, last exit 0, event trigger Hour 3 Minute 0. |
| `crontab -l`, LaunchAgents search, active scheduler metadata query | No alternate hardener trigger found; Workbench schedule is the only active memory-related scheduler row. |
| `bin/viventium status --json` | CLI printed rich status; core services reachable, but Brain Setup Primary AI copy remains `Needs setup`. |
| Scheduler SQLite queries | One completed scheduled prompt since prior cutoff; active task ledger still has 9 missed user-level rows and 1 fallback-delivered row. |
| GlassHive SQLite and metrics queries | Latest run completed in about 3 minutes; latest callbacks delivered; no active callback backlog. |
| Playwright Workbench inspection | Workbench loaded with 0 console errors/warnings; built-in schedule detail and latest completed run visible; browser session closed cleanly. |
| `curl` RAG `/health` | `UP`. |
| `bin/viventium continuity-audit` | Wrote local App Support artifact; sanitized status `ok`, no warnings/errors, recall rebuild not required. |
| `bin/viventium memory-dedupe --dry-run --json` | 0 duplicate groups/docs, 0 deletes, no index creation. |
| `node qa/meeting-transcript-memory/evals/run-evals.cjs` | 12 passed, 0 failed. |
| Focused release pytest suite | 130 passed, 22 skipped. |

## Stale, Skipped, Failed, Partial, Or Degraded Items

1. **High: memory-hardening trigger timing is unresolved.** The loaded LaunchAgent is configured for
   03:00 local, but recent automatic hardener runs landed around 10:00Z. Today's Workbench
   schedule is expected at 10:00Z; the hardener's matching timestamp may indicate an undocumented
   trigger path or a LaunchAgent scheduling drift. No root cause was proven in this read-only audit.
2. **High: configured primary hardener provider failed under real load.** OpenAI/GPT-5.5 probe
   passed, but the proposal attempt recorded `model_schema_error`; Anthropic fallback completed the
   run. Top-level status does not expose this clearly enough.
3. **Medium: 9 active user-level schedules remain missed/missed.** These need owner/context
   classification as stale rows, expected missed windows, or genuine scheduler defects. One active
   row also reports `fallback_delivered`, which means the primary delivery path did not carry it.
4. **Medium: recall/browser signoff remains unrun.** RAG health and hardener vector telemetry are
   supporting evidence only; browser chat recall and direct vector-document proof were not rerun.
5. **Medium: Primary AI status copy is inconsistent.** Live services show a configured route, while
   Brain Setup tells the user to connect Primary AI.
6. **Low: Workbench duration variance remains unexplained.** Today's run completed in about 3
   minutes; yesterday's took about 8h33m. Today's pass lowers urgency but does not explain the
   prior outlier.
7. **Low: saved-memory continuity timestamp did not move.** Continuity still reports latest saved
   memory update on 2026-05-22, while today's hardener summary says two memory keys changed.

## ClaudeViv Review

No separate `ClaudeViv` binary was available, so the local Claude Code CLI was used as the
review-only second-opinion path with read-only repo tools. It returned JSON and made no changes.

Confirmed by review:

- Overall `PARTIAL` is the defensible result.
- Provider fallback and the misleading top-level provider/model status are real degraded findings.
- The hardener trigger source is the highest-priority unresolved reliability gap.
- The 9 missed user-level schedules and 1 fallback-delivered row should not be dismissed as
  background noise.
- Browser recall and direct vector proof remain `PARTIAL` under the QA contract.
- Current power/thermal evidence supports `PASS`.

Corrections incorporated:

- `chars_fed_to_model=0` for transcripts is not suspicious because 3 ignored plus 23 unchanged
  accounts for all 26 scanned entries.
- Historical dead-letter callback rows are kept as a note, not elevated to a current failure.
- Automated tests/evals are listed as supporting evidence, not substitutes for missing user-path
  recall proof.
- The Workbench run itself is a pass today; only the prior duration variance remains unexplained.

Unresolved risks from review:

- The hardener's actual trigger path needs to be identified before the schedule can be called
  reliable.
- The OpenAI `model_schema_error` payload and call shape need diagnosis.
- Primary AI status-copy mismatch needs tracing to connected-account state, config state, or UI
  cache.
- Saved-memory timestamp continuity should be cross-checked against the hardener apply/write path.

## Case Status Updates

| Case | Status |
| --- | --- |
| `MEMHARD-001` | `PARTIAL/DEGRADED` |
| `MEMHARD-002` | `PASS` |
| `MEMHARD-003` | `PASS` |
| `MTM-006` | `PASS/PARTIAL` |
| `MEMCONT-001` | `PASS/PARTIAL` |
| `RAG-001` | `PARTIAL` |
| `PW-029` | `PASS/PARTIAL` |
| `SCHED-002` | `PASS/PARTIAL` |
| `SCHED-006` | `PASS` |
| `SCHED-009` | `PASS` |

## Next Actions

1. Identify the actual 10:00Z memory-hardener trigger source and either align it with the documented
   03:00 local schedule or update the product truth if 10:00Z is intentional.
2. Diagnose OpenAI/GPT-5.5 `model_schema_error` from the hardener's model-call path; fix the call
   shape or make the active primary provider explicit in generated config/status.
3. Classify the 9 missed and 1 fallback-delivered active user-level schedule rows with owner/context
   evidence.
4. Trace the Primary AI Brain Setup mismatch and make the user-visible status agree with real route
   readiness.
5. Run a sanitized browser recall/RAG user-path check and direct vector-document proof in a future
   safe QA window before upgrading recall status beyond `PARTIAL`.
6. Compare continuity saved-memory timestamps with the hardener apply/write path so the audit does
   not report stale memory state after a real apply.
