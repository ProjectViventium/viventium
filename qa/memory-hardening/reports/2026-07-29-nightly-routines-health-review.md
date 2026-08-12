# 2026-07-29 Nightly Routines Health Review

Read-only audit for the Viventium nightly routines. This report is public-safe: it records sanitized
statuses, counts, hashes, and timestamps only. Raw prompts, private run bodies, callback payloads,
local absolute paths, account identifiers, transcripts, memories, tokens, and screenshots are not
included.

## Timing Anchor

- Audit start observed: 2026-07-29 11:18:16 EDT / 2026-07-29T15:18:16Z.
- System timezone: America/Toronto, confirmed from the non-privileged local timezone link and `date`.
- Desktop automation cadence: the prompt says the observer RRULE is 11:15Z; this local Desktop run
  was observed around 15:15Z / 11:15 EDT. The observer is not the product scheduler.
- Generated runtime timezone/config: `VIVENTIUM_MEMORY_HARDENING_TIMEZONE=America/Toronto`,
  `VIVENTIUM_MEMORY_HARDENING_SCHEDULE='0 3 * * *'`, Workbench seed nightly enabled,
  Scheduler URL on localhost, Workbench port 8781, and unattended Sol/xHigh route configured.
- LaunchAgent schedule: direct memory wrapper with `StartCalendarInterval` hour 3, minute 0, no
  competing interval trigger.
- Workbench scheduled prompt: built-in nightly definition active at 03:00 America/Toronto; next run
  recorded as 2026-07-30T07:00:00Z.

| Routine | Due Local | Due UTC | Grace Used | Observed Evidence | Status |
| --- | --- | --- | --- | --- | --- |
| Memory hardening LaunchAgent | 2026-07-29 03:00 EDT | 2026-07-29T07:00:00Z | 60 minutes | Trigger receipt fired at 2026-07-29T07:00:05.858Z; run finished success at 2026-07-29T07:02:27.370Z | PASS |
| Transcript ingest/catch-up inside hardener | 2026-07-29 03:00 EDT | 2026-07-29T07:00:00Z | 60 minutes | Latest hardener scan saw 39 eligible files, 33 unchanged, 0 pending, 0 vector errors; cumulative transcript state had 56 processed records | PASS scan / RECALL PROOF BLOCKED |
| Workbench nightly reflection | 2026-07-29 03:00 EDT | 2026-07-29T07:00:00Z | 60 minutes | Scheduler run started at 2026-07-29T07:00:05.812672Z and completed at 2026-07-29T07:02:14.295967Z | PASS |
| Periphery risk-radar artifact | 2026-07-29 03:00 EDT | 2026-07-29T07:00:00Z | 60 minutes | Fresh schema-v2 sidecar generated at 2026-07-29T07:01:27Z; quality passed structurally, markdown paired, memory proposals 0, but source snapshot lacked Mongo-backed conversation/memory sources | PASS structure / PARTIAL content-source coverage |
| User-level scheduled prompts | Per user schedule | Per user schedule | 15 minutes when due | Several active user schedules ran after or near audit time; provider reconnect errors are account-action evidence, not built-in nightly failure | OUT OF SCOPE / WATCH |
| Current browser recall/RAG service proof | Audit-time health check | Audit-time health check | none | RAG API unreachable; API container exited code 1 with database-auth startup failures while PGVector container was healthy | FAIL-SERVICE |

No routine was before its due time plus grace at audit time. No product failure was inferred from
timezone travel, DST, launchd wake coalescing, or the observer automation cadence.

## Evidence Checked

- Memory hardener status JSON: latest scheduled trigger receipt complete, exit 0, launchd source,
  no schedule mismatch, no provider/model/effort mismatch, lock not held, one eligible user, one
  successful model attempt, no fallback, OpenAI `gpt-5.6-sol` with `xhigh`.
- Memory hardener latest summary: status success; changed stable memory buckets were recorded only
  as key names/counts; 53 conversations and 271 messages selected under the configured input cap;
  transcript maintenance had 0 pending files and 0 vector presence errors. The processed transcript
  count is cumulative state, not proof that current RAG retrieval is working.
- Power state: AC power, battery charging, no observed power-budget skip, no override flags used.
- Runtime surfaces: LibreChat frontend/API, Scheduling Cortex, GlassHive, Workbench, SearXNG, and
  Firecrawl root were reachable. Firecrawl `/health` still returns 404 and remains a watch item.
- Workbench scheduler DB: built-in schedule active, executor `glasshive_host`, channel `workbench`,
  daily 03:00 America/Toronto, parent ledger success, delivery sent, no last error.
- Workbench run DB: the due run had rendered and variable snapshot hashes, GlassHive project/worker/run
  references, private detail pointer present, callback payload present, and no error class.
- GlassHive DB: the run completed with no failure class and no error text. Today's three callbacks
  were delivered; historical dead-letter callbacks exist but are not tied to today's run.
- Workbench browser/API proof: real Chromium loaded the Workbench, found the built-in nightly row,
  confirmed it is active with next 2026-07-30T07:00:00Z and executor `glasshive_host`.
- Periphery metadata API: latest `risk_radar` artifact is schema v2, fresh/non-stale, quality passed,
  markdown exists, snapshot and scheduled-run refs are hashed, one grounded no-result observation,
  zero ungrounded claims, zero memory proposals.
- Periphery snapshot metadata: snapshot generated at 2026-07-29T07:00:05.458779Z, status degraded,
  27 source refs from schedules/reasoning/recent runs, and missing prerequisite `mongo`; conversation
  and memory source counts were 0. This missing-Mongo state is infrastructure/source coverage
  evidence and is separate from user-level provider reconnect rows.
- Current RAG evidence: `http://localhost:8110` was unreachable; the RAG API container was exited
  with code 1; recent logs repeatedly reported database password-authentication startup failures.
  The PGVector container was healthy and current container env hashes matched, suggesting persisted
  database credential state may be out of sync with the generated runtime env.
- Git/code drift: parent and nested component worktrees were already dirty across many files before
  this report update; no runtime repair or source fix was applied by this audit.

## QA Commands

- `bin/viventium memory-dedupe --dry-run --json`: PASS, zero duplicate groups/docs and zero deletes.
- Focused release contracts: PASS, 343 passed and 23 skipped.
- `node qa/meeting-transcript-memory/evals/run-evals.cjs`: PASS, 12/12.
- `python3 qa/periphery-nightly-insights/scripts/run-periphery-evals.py`: PASS, 6/6 static cases,
  including degraded-Mongo handling.
- Playwright real-browser Workbench probe: PASS for loading Workbench, visible built-in schedule
  presence, active next-run state, and same-page API `success` state. Full snapshot output was not
  retained because it can expose private schedules.

## Verdict

- Memory hardening: PASS.
- Transcript ingest/catch-up as scheduled hardener work: PASS for the scheduled scan and no-pending
  state, with end-to-end recall proof blocked because current RAG API is down.
- Transcript browser recall/vector proof: FAIL-SERVICE / PROOF BLOCKED because current RAG API is
  down. This is separate from the successful scheduled hardener, but it is still a live recall
  outage.
- Workbench nightly reflection chain: PASS.
- Periphery nightly insight artifact: PASS-STRUCTURE / PARTIAL-CONTENT because the artifact is
  valid and honest but the source snapshot is degraded by missing Mongo-backed evidence.
- Scheduler state: PASS for the built-in nightly task; WATCH for user-level schedules with account
  reconnect failures.
- Power budget: PASS, no skip observed.

## Fix Plan

1. P2: repair current RAG/PGVector startup without deleting data: inspect generated RAG env, Docker
   compose env injection, and persisted PGVector volume initialization; reconcile the database
   credential state or migrate the volume under backup.
2. After RAG starts, run `/health`, a scoped vector query, and a browser recall/source-card proof
   against synthetic or sanitized transcript evidence before changing MTM-006 back to pass.
3. Restore Mongo availability for the Workbench periphery snapshot path or explicitly classify the
   source as unavailable in the Workbench status surface; rerun the next nightly or safe manual
   preview and verify conversations/memories are included when available.
4. Keep user-level provider reconnect errors as account-action items unless they are proven to block
   the built-in nightly contract.

## Claude Review

ClaudeViv was not available as a local command, so local Claude CLI was used in review-only mode
with sanitized evidence. It agreed the memory hardener and Workbench chain PASS classifications are
defensible, and it specifically recommended tightening transcript and periphery wording so the RAG
outage does not get hidden by a successful scheduled scan and a structurally valid no-result artifact.
Those corrections are incorporated above. Remaining unresolved risk: current recall retrievability
is unproven until RAG is repaired and browser/source-card proof is rerun.
<!-- qa-evidence-exempt: Historical or specialized supporting artifact retained without retroactively inventing missing evidence; current release acceptance requires a fresh full-view report. -->
