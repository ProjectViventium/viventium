# 2026-07-30 Nightly Routines Health Review

Read-only audit for the Viventium nightly routines. This report is public-safe: it records sanitized
statuses, counts, hashes, and timestamps only. Raw prompts, private run bodies, callback payloads,
local absolute paths, account identifiers, transcripts, memories, tokens, and screenshots are not
included.

## Timing Anchor

- Audit start observed: 2026-07-30 11:16:21 EDT / 2026-07-30T15:16:21Z.
- Report finalized: 2026-07-30 11:32:14 EDT / 2026-07-30T15:32:14Z.
- System timezone: America/Toronto, confirmed from the non-privileged local timezone link and
  `date`.
- Desktop automation cadence: the prompt says the observer RRULE is 11:15Z; this local Desktop run
  was observed around 15:15Z / 11:15 EDT. The observer is not the product scheduler.
- Generated runtime timezone/config: `VIVENTIUM_MEMORY_HARDENING_TIMEZONE=America/Toronto`,
  `VIVENTIUM_MEMORY_HARDENING_SCHEDULE='0 3 * * *'`, OpenAI `gpt-5.6-sol` / `xhigh`,
  Workbench enabled on port 8781, and local RAG URL `http://localhost:8110`.
- LaunchAgent schedule: direct memory wrapper with `StartCalendarInterval` hour 3, minute 0, no
  competing interval trigger.
- Workbench scheduled prompt: built-in nightly definition active at 03:00 America/Toronto; next run
  recorded as 2026-07-31T07:00:00Z.

| Routine | Due Local | Due UTC | Grace Used | Observed Evidence | Status |
| --- | --- | --- | --- | --- | --- |
| Memory hardening LaunchAgent/apply | 2026-07-30 03:00 EDT | 2026-07-30T07:00:00Z | 60 minutes | Trigger receipt fired at 2026-07-30T07:00:02.536Z; apply run finished success at 2026-07-30T07:02:23.457Z | PASS-APPLY / PARTIAL-VECTOR |
| Transcript ingest/catch-up inside hardener | 2026-07-30 03:00 EDT | 2026-07-30T07:00:00Z | 60 minutes | Latest hardener scan saw 39 eligible files, 0 pending, 66 vector-presence errors, and vector writes deferred because vector runtime was unreachable | PASS scan / FAIL-SERVICE vector |
| Workbench nightly reflection | 2026-07-30 03:00 EDT | 2026-07-30T07:00:00Z | 60 minutes | Scheduler run started at 2026-07-30T07:00:18.573965Z and completed at 2026-07-30T07:06:11.834268Z through GlassHive callbacks | PASS-CHAIN / DETAIL-UI NOT EXERCISED |
| Periphery risk-radar artifact | 2026-07-30 03:00 EDT | 2026-07-30T07:00:00Z | 60 minutes | Fresh schema-v2 sidecar generated at 2026-07-30T07:02:57Z; quality passed, markdown paired, snapshot complete, 11 grounded claims, 0 ungrounded claims | PASS |
| User-level scheduled prompts | Per user schedule | Per user schedule | 15 minutes when due | Several user schedules ran after audit timing with suppressed, reconnect, Telegram mapping, or misfire rows | OUT OF SCOPE / WATCH |
| Current browser recall/RAG service proof | Audit-time health check | Audit-time health check | none | RAG API unreachable; API container exited code 1 with database-auth startup failure while PGVector remained healthy | FAIL-SERVICE / P1 PERSISTENT |

No built-in routine was before its due time plus grace at audit time. No product failure was inferred
from timezone travel, DST, launchd wake coalescing, or the observer automation cadence.

## Evidence Checked

- Memory hardener status JSON: latest scheduled trigger receipt complete, exit 0, launchd source,
  no schedule mismatch, no missed expected window, no provider/model/effort mismatch, lock not held,
  one eligible user, one successful OpenAI `gpt-5.6-sol` / `xhigh` model attempt, and no fallback.
- Memory hardener latest summary: status success; changed stable memory buckets were recorded only
  as key names/counts; transcript maintenance had 39 files seen, 0 pending, 0 skipped by cap, 66
  vector-presence errors, and vector writes deferred with `vector_runtime_unreachable`.
- Transcript private indexes: 56 cumulative processed transcript records across local user hashes,
  with no pending index status. This proves the scheduled scan state, not current RAG retrieval.
- Power state: AC power, battery charging, no observed power-budget skip, and no power/idle override
  flags used. No separate thermal warning was observed in the checked hardener evidence.
- Runtime surfaces: LibreChat frontend/API, Scheduling Cortex, GlassHive, Workbench, SearXNG, and
  Firecrawl root were reachable. Firecrawl `/health` still returns 404 and remains a watch item.
- Workbench scheduler DB: built-in schedule active, executor `glasshive_host`, channel `workbench`,
  daily 03:00 America/Toronto, rendered and variable snapshot hashes present, parent ledger success,
  delivery sent, no last error.
- GlassHive DB: the matching run completed with no failure class or error text. The run's callbacks
  were delivered in one attempt; historical dead-letter callbacks remain watch-only.
- Workbench browser/API proof: real Chromium loaded Workbench, found the built-in nightly schedule
  visible as enabled with next 2026-07-31 03:00 local. Detailed run body UI was intentionally not
  opened or retained because it can expose private reflection content; the completion chain is
  proven by API, Scheduler, and GlassHive ledgers.
- Periphery metadata API: latest `risk_radar` artifact is schema v2, fresh/non-stale, quality
  passed, markdown exists, source refs resolved 8/8, grounded claims 11, ungrounded claims 0, memory
  proposals 0, snapshot complete, and missing prerequisites empty.
- Current RAG evidence: `http://localhost:8110` was unreachable; the RAG API container was exited
  with code 1; recent logs reported database password-authentication failure while creating vector
  extension. PGVector was healthy and accepted a read-only TCP `select 1` using its generated env.
  RAG API and PGVector container env hashes matched, so the root cause is not proven by top-level
  env drift alone.
- Git/code drift: the parent worktree was already dirty across many unrelated files before this
  audit report update. No runtime repair or product source fix was applied by this audit.

## QA Commands

- `bin/viventium memory-dedupe --dry-run --json`: PASS, zero duplicate groups/docs and zero deletes.
- Focused release contracts: PASS, 344 passed and 23 skipped.
- `node qa/meeting-transcript-memory/evals/run-evals.cjs`: PASS, 12/12.
- `python3 qa/periphery-nightly-insights/scripts/run-periphery-evals.py`: PASS, 6/6 static cases,
  including degraded-Mongo handling.
- Playwright real-browser Workbench probe: PASS for loading Workbench and visible built-in schedule
  presence. The generated snapshot was deleted because it can include private schedule text and an
  auth token.

## Verdict

- Memory hardening scheduled apply: PASS.
- Memory hardening vector/recall lane: PARTIAL/FAIL-SERVICE because vector presence checks failed
  and vector writes were deferred due the current RAG outage.
- Transcript ingest/catch-up as scheduled scan: PASS for no-pending scan state, with browser
  transcript recall/source-card proof blocked by RAG service failure.
- Workbench nightly reflection chain: PASS for scheduled prompt -> filled placeholders/hashes ->
  GlassHive run -> callbacks -> scheduler ledger -> Workbench schedule visibility. Detailed private
  run content UI was not exercised in this read-only public-safe audit.
- Periphery nightly insight artifact: PASS.
- Scheduler state: PASS for the built-in nightly task; WATCH for user-level schedules with account,
  mapping, delivery, or misfire rows that are outside the built-in nightly contract.
- Conversation Recall/RAG service: FAIL-SERVICE / P1 persistent recall outage, continuing from the
  2026-07-29 audit and now also degrading the memory-hardener vector lane.
- Power budget: PASS, no skip observed.

## Fix Plan

1. P1: repair current RAG API startup without deleting vector data. Inspect the actual RAG API DSN
   construction, any `DATABASE_URL` or secret-file override, URL-encoding behavior, and PG auth
   settings before restarting. Matching container env hashes alone are not enough because persisted
   Postgres role state may differ from generated env after prior initialization or rotation.
2. After RAG starts, run `/health`, a scoped vector query, and a browser recall/source-card proof
   against synthetic or sanitized transcript evidence before changing MTM/RAG cases back to pass.
3. Treat the broad `bin/viventium status` memory-hardening `execution_unverified` row as a separate
   monitoring-surface defect or watch item: the dedicated schedule receipt proves the scheduled
   apply lane, but the aggregator wording can still mislead operators.
4. Keep user-level provider reconnect, Telegram mapping, and misfire rows as account/user-schedule
   action items unless proven to block the built-in nightly contract.

## Claude Review

ClaudeViv was not available as a local command, so local Claude CLI was used in review-only mode
with sanitized evidence and edit/tool use disallowed. It agreed with the timing, scheduler,
periphery, and power classifications, and recommended splitting memory hardening into apply PASS
versus vector/recall degradation, avoiding a plain Workbench PASS without a private detail-view UI
check, strengthening the RAG root-cause plan, and treating the broad status aggregation mismatch as
a real monitoring watch item. Those corrections are incorporated above.
<!-- qa-evidence-exempt: Historical or specialized supporting artifact retained without retroactively inventing missing evidence; current release acceptance requires a fresh full-view report. -->
