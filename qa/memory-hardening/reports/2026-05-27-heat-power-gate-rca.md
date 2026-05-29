# 2026-05-27 Heat RCA: Memory Hardening Power Budget

## Scope

This report covers the follow-up heat investigation after the local-prod helper polling fix. It
records public-safe evidence only: no raw transcripts, account identifiers, local absolute paths,
private browser URLs, command lines containing private values, or screenshots.

## Root Cause Summary

- The earlier helper issue was real and fixed: helper steady-state health checks now use the modern
  playground health endpoint instead of repeatedly rendering the playground root.
- The laptop was still hot because the helper bug was not the only contributor. The remaining
  contributors were:
  - active browser/desktop rendering and meeting/media tabs;
  - Codex desktop plus long-lived computer-use helper clients;
  - Docker VM baseline and occasional container bursts;
  - Viventium transcript/memory hardening model work launched under Codex.
- The Viventium-owned heat root after the helper fix was optional transcript-summary maintenance
  running model-backed memory hardening while the machine was on battery.
- A second maintenance run was later observed with an explicit power-gate override flag. That run was
  not local prod and not Docker; it was an audit/maintenance process launched under Codex. It was
  terminated to stop the bypassing maintenance work without stopping Viventium local prod.

## Fix Implemented

- Added a reusable local power-budget helper at `scripts/viventium/power_budget.py`.
- Updated `scripts/viventium/memory_harden.py` so model-backed `dry-run`, `apply`, and
  `ingest-transcripts` skip on macOS battery power or recorded thermal/performance warning unless
  the operator explicitly passes `--ignore-power-gate` with
  `VIVENTIUM_MEMORY_HARDENING_ALLOW_POWER_OVERRIDE=1`.
- Kept `--ignore-idle-gate` separate: it does not bypass the power/thermal gate.
- Prevented non-interactive audit loops from bypassing the gate with only `--ignore-power-gate`.
- Lowered OS priority for spawned Node/model hardening children when work is allowed to run.
- Updated the live nightly QA automation policy so it reports power-budget skips instead of forcing
  model-backed work with `--ignore-power-gate`.
- Documented the contract in the memory-system and installer/config-compiler requirements docs.
- Added `MEMHARD-003` as the reusable QA case for local power-budget behavior.

## Evidence

- Power source during the follow-up: battery power.
- Thermal state: no recorded macOS thermal/performance warning at the time of inspection.
- Active runtime status after stopping the pre-change maintenance run: local prod still pointed at
  the active checkout and status returned normally.
- Live battery-gate check: `ingest-transcripts --apply --ignore-idle-gate --json` returned
  `status: skipped` with `reason: on_battery_power`.
- Process check after terminating the bypassing maintenance run: no remaining
  `memory_harden.py`, `viventium-memory-hardening.js`, or spawned Opus hardening process was found.
- A 12-second recheck after hardening the override contract found no respawned memory-hardening
  process and `bin/viventium dev-runtime status` returned normally.
- The remaining top process sample was no longer Viventium memory work; it was dominated by macOS
  Spotlight indexing, Docker VM aggregate load, audio, browsers, and Codex.
- Docker container stats after the memory-hardening loop was stopped showed low per-container CPU
  usage; the VM wrapper remained a measurable aggregate contributor, while Firecrawl Postgres had
  high historical block I/O and should be reviewed separately if heat persists with foreground apps
  idle.
- Claude review-only second pass agreed the memory-hardening gate is the correct immediate
  Viventium-owned fix, and flagged follow-ups: shared power-budget helper, full `MEMHARD-003` case,
  read-only CLI lock decoupling, helper run-anyway UX, last-skip visibility, lower child priority,
  and audit automation backoff. This report incorporates the shared helper, case detail, lower
  priority, and automation-policy update.

## Test Results

- `python3 -m py_compile scripts/viventium/memory_harden.py scripts/viventium/power_budget.py`
- `uv run --with pytest --with pyyaml python -m pytest tests/release/test_memory_hardening_contract.py -q`
- Live battery skip probe through the wrapper returned the expected structured skip.
- `bin/viventium dev-runtime status` returned normally after the maintenance process was stopped.

## Remaining Gaps

- Heat RCA is still `PARTIAL`, not closed, because non-Viventium foreground load can still keep the
  machine warm.
- Other model-backed Viventium maintenance entrypoints still need explicit adoption of the shared
  `power_budget.py` helper or a documented exemption.
- Read-only status commands should be decoupled from the mutating CLI lock so status inspection is
  never blocked by long-running maintenance.
- The helper should expose an explicit "run anyway" UX for operator-triggered transcript ingest when
  on battery, and status surfaces should show the last skipped reason plus how long maintenance has
  been behind.
- Docker was not the primary root cause in the captured samples, but Docker VM baseline and RAG or
  database bursts remain measurable contributors and should be reviewed separately if heat persists
  while browsers/Codex are idle and maintenance is not running.

## Public-Safety Review

This report uses sanitized process categories, statuses, and outcomes only. It intentionally omits
private paths, account names, raw transcript text, private URLs, raw DB rows, secrets, and screenshots.
