# 2026-07-18 Nightly Routines Health Review

Read-only audit for the Viventium overnight-routine automation.

## Verdict

Overall status: **PARTIAL**.

- **PASS**: audit timing, power/thermal gate, macOS LaunchAgent trigger receipt, saved-memory hardening, transcript scan, Prompt Workbench nightly reflection, Scheduler/GlassHive built-in chain, and latest periphery risk-radar artifact.
- **FAIL**: transcript vector/RAG maintenance. The scheduled hardener deferred vector lifecycle work because the local RAG runtime was unreachable.
- **WATCH**: unrelated user-level scheduled prompts had Telegram mapping/delivery partials; historical callback debt and one older host-busy queued GlassHive row remain outside today's built-in nightly run.

## Summary

The built-in overnight chain was partial: scheduling, power gating, memory hardening, transcript
scanning, Workbench, Scheduler/GlassHive, and the latest periphery artifact passed, while vector/RAG
maintenance failed closed because its local runtime was unavailable.

## Scope Run

The audit covered the generated schedule and runtime configuration, macOS LaunchAgent receipt,
hardener and transcript telemetry, RAG prerequisites, Scheduler/GlassHive and Workbench ledgers,
the real Workbench browser surface, the latest periphery metadata, and public-safe cleanup.

## Traceability

The evidence maps the memory-hardening, transcript, RAG, Prompt Workbench, Scheduler, and periphery
cases to their active configuration, trigger, runtime, browser state, persistence ledgers, and
remaining remediation.

## Full-View Evidence Checklist

- Code owning path: hardener, scheduled wrapper, Workbench, Scheduler, and RAG health paths reviewed.
- Docs and nested docs/repos: owning feature cases and runtime requirements checked.
- Scripts or harnesses: status commands and focused release tests executed.
- Logs: trigger and lifecycle receipts plus bounded service telemetry inspected.
- DB/state/persistence: Scheduler, GlassHive, Workbench, and hardener state compared.
- Generated/shipped artifact: active generated config and loaded LaunchAgent verified.
- Real user path: Workbench was opened and inspected through Playwright.
- Visual/UX comparison: visible schedule, latest run, route, model, effort, and artifact state reviewed.
- Not run / blocked: vector lifecycle completion was blocked by the unavailable local RAG runtime.

## User-Grade Evidence

- Surface exercised: Prompt Workbench in a real Playwright browser plus Viventium CLI health surfaces.
- Real user path: The built-in nightly routine was opened and its latest run, next run, route, model, effort, memory mode, and artifact state were inspected.
- Visible outcome: Workbench showed the run completed and the latest risk-radar artifact passed.
- Expanded/detail state: Schedule timing, GlassHive route, evidence snapshot, and periphery counts were expanded.
- Persistence/reload result: Browser, API, Scheduler, and GlassHive state agreed after completion.
- Backend/log/DB confirmation: LaunchAgent receipts, hardener telemetry, scheduler ledgers, and RAG health supported the visible outcome.
- Final model/runtime wording check: The browser displayed the configured Sol/xhigh execution provenance without contradicting runtime records.
- Substitution check: Playwright supplied the visible user path; logs, APIs, and DB rows supported it and did not replace it.

## Automated Evidence

Focused default-nightly, memory-hardening, compiler, Workbench, scheduled-GlassHive, and periphery
release tests passed. The vector/RAG health probe correctly exposed the unavailable dependency.

## Findings

The main escaped operational gap is unavailable RAG/PGVector service coverage during the scheduled
hardener. The system failed closed, but that is still a failed maintenance outcome rather than a
pass.

## Public-Safety Review

- [x] Runtime and database identifiers are redacted or summarized.
- [x] Private prompt, transcript, message, and artifact bodies are excluded.
- [x] No personal account identity, secret, or local absolute path is included.

## Timing Truth

Audit anchor:

- Local time: 2026-07-18 11:17:04 EDT
- UTC time: 2026-07-18 15:17:04Z
- System/generated runtime timezone: America/Toronto
- Automation fire time: the prompt labels the observer target as 11:15Z, but the local Desktop observer actually fired around 11:17 EDT / 15:17Z. The product schedules were judged from their own runtime schedule/receipt evidence, not from the Codex observer label.

Due windows used for judgment:

| Routine | Due local | Due UTC | Grace | Audit classification |
| --- | --- | --- | --- | --- |
| Memory hardening and transcript maintenance | 2026-07-18 03:00 EDT | 2026-07-18 07:00Z | 30m | Due; evidence expected |
| Prompt Workbench nightly reflection | 2026-07-18 03:00 EDT | 2026-07-18 07:00Z | 45m | Due; evidence expected |
| Periphery risk-radar artifact from Workbench nightly | 2026-07-18 03:00 EDT | 2026-07-18 07:00Z | 45m | Due; evidence expected |
| User-level 08:00 America/Toronto schedules | 2026-07-18 08:00 EDT | 2026-07-18 12:00Z | 30m | Due, but separate from built-in nightly |
| User-level 08:00 America/Los_Angeles schedules | 2026-07-18 11:00 EDT | 2026-07-18 15:00Z | 30m | Within/just past grace depending exact anchor; observed rows had run |
| User-level 13:00 America/Toronto schedule | 2026-07-18 13:00 EDT | 2026-07-18 17:00Z | 30m | NOT DUE at audit anchor |
| Future one-time schedules | 2026-07-21/22 | 2026-07-21/22 | n/a | NOT DUE |

## Evidence Checked

Memory hardening:

- `bin/viventium memory-harden status --json` reported `schedule_health.state=healthy`, no missed expected window, generated schedule `0 3 * * *`, and timezone America/Toronto.
- LaunchAgent plist and `launchctl` agreed on label `ai.viventium.memory-harden`, a direct wrapper command, `StartCalendarInterval` Hour 3 Minute 0, no `StartInterval`, loaded state, and last exit 0.
- Latest scheduled trigger receipt fired at 2026-07-18 03:00:04 EDT / 07:00:04Z, finished at 07:02:40Z, exited 0, and referenced run id `20260718T070007Z`.
- Hardener summary for `20260718T070007Z`: status success, mode apply, one eligible redacted user selected/applied, provider OpenAI, model `gpt-5.6-sol`, effort `xhigh`, one successful model attempt, no fallback, changed keys `moments` and `drafts`, no conflicts.

Transcript and RAG:

- Transcript scan telemetry: 39 files seen, 6 ignored by config, 33 unchanged, 0 pending, 0 skipped by cap, 0 summary failures.
- Vector telemetry: 66 vector-presence errors, 0 uploaded, 0 deleted, 1 deferred, reason `vector_runtime_unreachable`.
- Live RAG health check: `http://localhost:8110/health` connection refused; no listener was present on 8110 and no matching RAG container was running.
- Ollama was running and had the configured embedding model `qwen3-embedding:0.6b`, so the immediate missing component was the RAG API/PGVector sidecar path, not the local embedding model.
- The docs require vector recall to fail closed when the runtime is unhealthy; the hardener did that, but the vector maintenance outcome itself failed for this run.

Workbench, Scheduler, GlassHive:

- Scheduler health endpoint returned healthy scheduling-cortex service state.
- Workbench health endpoint returned ok.
- Workbench API showed `Subconscious Deep Thought` active, daily 03:00 America/Toronto, executor `glasshive_host`, channel `workbench`, profile `codex-cli`, model `gpt-5.6-sol`, requested effort `xhigh`, next run 2026-07-19 07:00Z, last status success.
- Scheduler DB row for today's built-in run: due 2026-07-18 07:00:00Z, started 07:00:02Z, completed 07:08:20Z, status completed, a redacted GlassHive run reference, callback event `run.completed`, and callback status completed.
- GlassHive DB showed the corresponding redacted run completed and queued/started/completed callbacks delivered on attempt 1.
- No fresh callback backlog or dead-letter was observed for today's built-in run. Historical callback debt and one older host-busy queued run remain watch items.

Workbench browser QA:

- Playwright opened the local Workbench and selected `Subconscious Deep Thought`.
- Visible state showed enabled daily 03:00 America/Toronto schedule, next Jul 19 3:00 AM, GlassHive host execution, `gpt-5.6-sol`, requested effort `xhigh`, memory off, evidence snapshot complete, and the Jul 18 3:00 AM run completed.
- Periphery panel showed 7 artifacts indexed, 3 passed and 4 warning; the latest `risk_radar` artifact passed and was generated Jul 18 3:03 AM.

Periphery:

- Latest risk-radar sidecar was schema v2, generated 2026-07-18 07:03:21Z, quality status passed, markdown present, 10/10 source refs resolved, 0 ungrounded claims, stale after 2026-07-22 07:03:21Z, and 0 memory proposal refs.
- Older warning/stale artifacts remain historical context, not today's run failure.

Other current-state dependencies:

- SearXNG and Firecrawl health checks were connection-refused at audit time. This is current action-required evidence only; today's risk-radar artifact passed from the scheduled run evidence.
- `bin/viventium status` reported Conversation Recall action required, SearXNG/Firecrawl action required, Microsoft 365 MCP action required, status-bar helper running, and transcript ingest configured.
- The public and nested git worktrees were already dirty; no code/config changes were made to repair product behavior in this audit.

Power and thermal:

- Machine was on AC power with battery charged.
- `pmset -g therm` showed no thermal or performance warning.
- No power-budget skip receipt was present for today's hardener run.

## Checks Run

- Focused release suite:
  `uv run --with pytest --with pyyaml --with pydantic --with fastapi --with requests --with croniter python -m pytest tests/release/test_default_nightly_routines.py tests/release/test_memory_hardening_contract.py tests/release/test_config_compiler.py tests/release/test_prompt_workbench.py tests/release/test_scheduled_glasshive_prompts.py tests/release/test_periphery_eval_harness.py -q`
  Result: **320 passed, 27 skipped**.
- Transcript eval bank:
  `node qa/meeting-transcript-memory/evals/run-evals.cjs`
  Result: **12 passed, 0 failed**.
- RAG contract guardrails:
  `uv run --with pytest --with pyyaml python -m pytest tests/release/test_rag_api_override_contract.py tests/release/test_rag_compose_resource_guardrails.py -q`
  Result: **12 passed**.
- Read-only runtime probes: memory hardener status, LaunchAgent/launchctl state, trigger/lifecycle receipts, hardener summary/log telemetry, scheduler DB, GlassHive DB, Workbench API/UI, periphery metadata, RAG/search health endpoints, Docker/Ollama readiness, power/thermal status.

## Second Opinion

ClaudeViv was not available, so the local Claude CLI was used review-only with a sanitized evidence packet and no requested tool use.

Claude agreed that the timing, memory LaunchAgent, Workbench, periphery, scheduler, and power/thermal classifications were defensible. It recommended stronger wording for the vector lane: saved-memory hardening should remain PASS, but the vector/RAG sub-lane should be **FAIL** rather than PARTIAL because no vector lifecycle work completed. It also called out that SearXNG/Firecrawl checks are current-state observations, not proven fire-time failures, and that the prompt's `11:15Z` observer label should be treated as a label/cadence mismatch rather than a product schedule miss.

## Open Risks And Next Actions

1. Restore the local Conversation Recall/RAG sidecar path and rerun a read-only health check first; do not rebuild or ingest from the observer.
2. After RAG is healthy, run the supported bounded transcript backfill/repair path from an operator-controlled flow and verify vector uploads/presence checks.
3. Re-run browser transcript recall/source-card QA only after RAG health and vector presence are proven.
4. Investigate current user-level schedule delivery partials separately: Telegram mapping lookup returned 404 on some rows while LibreChat delivery was empty/NTA.
5. Keep historical GlassHive callback debt and the older host-busy queued run on the scheduler watch list, but do not classify them as today's built-in nightly failure.

## Public-Safety Notes

This report intentionally omits raw transcript text, memory values, account identifiers, private prompt bodies, screenshots, private file names, private artifact paths, and local absolute paths.
