<!-- qa-evidence-exempt: legacy sanitized RCA/QA note retained for historical context; current acceptance must use cases plus a fresh v2 report. -->

# 2026-06-07 Nightly Routines Health Review

Public-safe overnight health review for memory hardening, transcript ingest/RAG, Prompt Workbench
nightly reflection, Scheduler/GlassHive callback health, and continuity checks.

Raw prompt text, saved-memory values, transcript text, account identifiers, callback payloads,
tokens, screenshots, and local absolute paths were not copied into this report. A Playwright
snapshot was used for local visual inspection and then deleted because it contained private
Workbench detail text.

## Timing Anchor

- Audit anchor: 2026-06-07 03:16 EDT / 2026-06-07T07:16:16Z.
- Later sanity clock during evidence capture: 2026-06-07 03:31 EDT / 2026-06-07T07:31:49Z.
- System timezone: America/Toronto (`/etc/localtime` -> `America/Toronto`).
- Automation previous fire time from prompt: 2026-06-06T13:48:17.766Z.
- Generated memory-hardening timezone/config: enabled, `0 3 * * *`, America/Toronto,
  OpenAI `gpt-5.5` `xhigh`, dry-run-first on, transcript source configured,
  transcript RAG mode `detailed_summary_only`.
- LaunchAgent: loaded label `ai.viventium.memory-harden`, `StartCalendarInterval` hour 3 minute 0,
  state not running, launchctl reported runs `0`. The loaded command and stdout/stderr paths point
  at a temporary install/App Support tree rather than the current stable App Support runtime; the
  temporary stdout/stderr files were absent. This is schedule-install drift evidence. The initial
  audit anchor was still inside the configured 03:00 + 30 minute grace window; the later sanity
  clock was one minute after that configured grace window, while the observed 10:00Z cadence was
  still not due.
- Prompt Workbench schedule: built-in `Subconscious Deep Thought` active, daily 03:00
  America/Los_Angeles, next run `2026-06-07T10:00:00Z`.

## Due-Window Table

| Routine | Configured / observed due | Due local | Due UTC | Grace used | Audit classification at 03:16 EDT |
| --- | --- | --- | --- | --- | --- |
| Memory hardening, configured LaunchAgent | `0 3 * * *` America/Toronto | 2026-06-07 03:00 EDT | 2026-06-07T07:00Z | 30 min, to 03:30 EDT / 07:30Z | WAITING / IN GRACE |
| Memory hardening, observed recent cadence | recent successful runs at about 10:00Z | 2026-06-07 06:00 EDT | 2026-06-07T10:00Z | 30 min, to 06:30 EDT / 10:30Z | NOT DUE |
| Prompt Workbench nightly reflection | 03:00 America/Los_Angeles | 2026-06-07 06:00 EDT | 2026-06-07T10:00Z | 30 min, to 06:30 EDT / 10:30Z | NOT DUE |
| User-level provider reconnect schedules | 08:00 America/Los_Angeles | 2026-06-07 11:00 EDT | 2026-06-07T15:00Z | 15 min, to 11:15 EDT / 15:15Z | NOT DUE |

Timing verdict: the June 7 audit fired too early for the observed 10:00Z nightly cadence. The
configured 03:00 memory-hardening window was still in grace at the initial anchor and barely past
grace at the later sanity clock; because the loaded LaunchAgent itself is drifted, this is a
schedule-delivery risk rather than proof of a completed June 7 product failure. Today should not be
marked failed merely because no June 7 hardener or Workbench run had completed by 03:16 EDT.

## Findings

| Surface | Expected | Evidence | Status |
| --- | --- | --- | --- |
| Memory hardener scheduled run | June 7 run should be judged only after due plus grace. | No `20260607*` current-runtime run directory by 03:27 EDT. Audit was still in configured grace and before observed 10:00Z cadence. | NOT DUE / WAITING |
| Memory hardener latest actual run | Recent runs should use configured OpenAI path without fallback or provider/schema failure. | Latest current-runtime run `20260606T135011Z` succeeded 2026-06-06T13:50:11Z to 13:53:59Z via OpenAI `gpt-5.5` `xhigh`; model probe ok; one hardener attempt, zero hardener failures/fallback; transcript summarizer attempts clean. | PASS for model/provider path |
| Transcript ingest | Configured transcript lane should catch up bounded files and keep vector lifecycle honest. | Latest run saw 30 files, ignored 4 by config, 23 unchanged, 3 pending, zero vector-presence errors, zero requeued missing vectors, and no summary failures. Current indexes show 47 processed entries across three private indexes. | PARTIAL |
| Transcript vector/RAG | RAG sidecar should be reachable when transcript summary artifacts need vector-backed recall. | Generated runtime has `START_RAG_API=true`, `RAG_API_URL=http://localhost:8110`, Ollama embeddings configured. Health probes to `8110` failed and no listener was present. Latest hardener deferred transcript vectors once with `vector_runtime_unavailable`. | FAIL |
| Prompt Workbench Jun 7 run | Jun 7 Workbench chain should not be judged before 10:00Z plus grace. | Active built-in schedule next run is `2026-06-07T10:00:00Z`; Playwright showed enabled row, next Jun 7 6:00 AM local. | NOT DUE |
| Prompt Workbench Jun 6 run | Prior due run should have created Scheduler child run -> GlassHive run -> callback -> Workbench completed row. | Active task last delivery shows Jun 6 due `2026-06-06T10:00:00Z` marked missed at `2026-06-06T13:48:17Z`, reason `misfire_grace_exceeded`; there is no Jun 6 `scheduled_prompt_runs` row. Workbench visible recent runs/proposals stop at Jun 5. | FAIL |
| Scheduler state | Scheduler DB and health should be owned by local prod runtime. | `/health` returned public-safe runtime identity with isolated local-prod profile; 20 total / 8 active tasks. Four active user-level provider-reconnect rows are next due at `2026-06-07T15:00:00Z`, not due during this audit. | PASS/PARTIAL |
| GlassHive callback health | No active backlog; latest callbacks bounded and observable. | GlassHive health/metrics ok, 0 queued runs, 0 active runs, 0 callback pending/delivering, 2 historical dead-lettered callbacks, oldest pending age 0. Recent non-nightly GlassHive callbacks delivered. | PASS with follow-up |
| Power/thermal gate | Audit must not force expensive work on battery/thermal constraint. | Machine on AC power, battery present at 80%, no recorded thermal/performance warning, no power or idle override used. | PASS |
| CLI QA commands | Read-only CLI checks should be runnable without stale lock obstruction. | `bin/viventium memory-dedupe --dry-run --json` and `bin/viventium continuity-audit` were blocked by a live CLI lock claiming `install`; the lock PID belonged to a macOS Folder Actions process. Direct read-only checks were run instead. | PARTIAL |
| Continuity / dedupe | Continuity audit and dedupe should be clean. | Direct continuity capture status `ok`, warnings/errors empty, messages available, saved-memory count 24, schedules active count 8, recall rebuild false. Direct Node memory-dedupe dry-run: 0 duplicate groups/docs/deletes for memory entries and keys, no indexes created. | PASS/PARTIAL due CLI lock |
| Status-bar/manual ingest | Manual ingest state should not mutate during read-only audit. | Helper was running. Manual transcript ingest log latest entry remained 2026-05-15; no manual ingest was started. | PASS |
| Public/private boundary | Report and case updates must stay sanitized. | This report uses counts, timestamps, statuses, and hashes only. Playwright local snapshots were deleted. `git diff --check` passed for current working tree state. | PASS |

## Commands And Results

| Command / probe | Result |
| --- | --- |
| `date`, `date -u`, `/etc/localtime`, `pmset -g batt`, `pmset -g therm` | Timing anchored; AC power; no thermal/performance warning. |
| Generated runtime env key extraction | Memory hardening, Workbench, Scheduler, GlassHive, RAG keys inspected with secrets/paths redacted. |
| `launchctl print gui/<uid>/ai.viventium.memory-harden` and LaunchAgent plist inspection | Label loaded; 03:00 schedule; state not running; runs 0; command/log paths point at temporary install/App Support tree. |
| `bin/viventium memory-harden status --json` | Latest run success `20260606T135011Z`; transcript indexes 47 processed; efficiency gate finished. |
| RAG health probes to generated `RAG_API_URL` | Failed to connect to port 8110; no listener present. |
| Scheduler `/health` and SQLite read-only queries | Health ok; active built-in Workbench task next due Jun 7 10:00Z; Jun 6 due marked missed; no Jun 6 child run row. |
| GlassHive `/health`, `/v1/metrics/summary`, SQLite aggregates | Runtime ok; 0 queued/active; 0 pending/delivering callbacks; 2 historical dead-letter rows. |
| Playwright CLI Workbench inspection | Opened local Workbench, verified built-in schedule enabled/next Jun 7 6:00 AM local, detail visible with latest completed Jun 5 run/proposal; browser closed and snapshots deleted. |
| `node qa/meeting-transcript-memory/evals/run-evals.cjs` | 12 passed, 0 failed. |
| Direct Node memory-dedupe dry-run | 0 duplicate memory groups/docs/deletes; 0 duplicate key groups/docs/deletes; indexes not created. |
| Direct `continuity_audit.py capture` | Status ok, warnings/errors empty, recall rebuild false. |
| Focused release pytest set | `152 passed, 2 warnings` for continuity audit, memory hardening, RAG API contract, scheduled GlassHive prompts, and Prompt Workbench. |
| Nested scheduler pytest via `uv` | 18 passed. |
| `git diff --check` | Clean. |

## Classification

- Overall: PARTIAL.
- PASS: hardener latest model/provider path, power gate, transcript deterministic evals, continuity
  metadata, memory dedupe direct dry-run, Scheduler identity, GlassHive callback backlog, public
  safety.
- FAIL: Jun 6 built-in Workbench nightly reflection missed the full
  `scheduled prompt -> filled placeholders -> GlassHive run -> callback -> scheduler ledger ->
  Workbench completed` chain.
- FAIL: generated RAG/recall sidecar is currently unreachable, and latest hardener deferred
  transcript vector work because the vector runtime was unavailable.
- PARTIAL: memory hardening schedule delivery surface has drift because the loaded LaunchAgent
  points at a temporary install/App Support tree; at audit time the June 7 run was still waiting/not
  due, so this is schedule-install drift evidence rather than a June 7 hardener failure. The actual
  trigger path for the successful Jun 6 hardener run is unresolved.
- PARTIAL: normal `bin/viventium` read-only QA commands are blocked by a stale-looking `install`
  lock whose PID is an unrelated macOS process.
- NOT DUE: Jun 7 Workbench nightly reflection, observed 10:00Z memory cadence, and 15:00Z
  user-level provider-reconnect rows.

## Claude Review

ClaudeViv was not available on the local PATH, so a local Claude CLI review-only pass was run with
tools disabled and a sanitized evidence packet. The reviewer agreed that Jun 7 Workbench and the
observed 10:00Z memory cadence were not due, and agreed that LaunchAgent drift is a delivery risk.
It sharpened the classifications: Jun 6 Workbench should be plain FAIL because no delivery began,
and the unreachable RAG sidecar/vector deferral is product failure evidence for recall rather than
only a QA proof gap. The main unresolved risk it added is that the successful Jun 6 hardener run
occurred despite the loaded LaunchAgent reporting no runs and stale paths, so the real trigger path
must be identified before calling schedule delivery reliable.

## Next Actions

1. Clear or repair the stale CLI-operation lock through an operator-safe path, then rerun
   `bin/viventium continuity-audit` and `bin/viventium memory-dedupe --dry-run --json` through the
   public CLI wrapper.
2. Identify what actually triggered the successful Jun 6 memory-hardening run, then reconcile the
   memory-hardening LaunchAgent from the current active runtime and verify the loaded command/log
   paths point at the stable App Support runtime.
3. Bring the configured RAG sidecar on port 8110 healthy, then rerun transcript vector proof and
   browser recall/source-card QA before claiming transcript recall is fully healthy.
4. Investigate why the Jun 6 Workbench nightly row was first processed 228 minutes late and marked
   missed. If this is expected strict-misfire behavior after the host is asleep/offline, add a
   product decision for whether the built-in nightly reflection should use explicit catch-up
   metadata; if not expected, fix the launcher/scheduler availability gap.
5. Inspect the two historical GlassHive dead-lettered callbacks enough to confirm age/cause without
   exposing payloads, then decide whether they need cleanup or a regression case.
6. Run a follow-up after 2026-06-07T10:30Z to classify the actual Jun 7 Workbench and observed
   memory-hardener cadence instead of relying on pre-due evidence.
