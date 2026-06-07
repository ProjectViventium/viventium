<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# 2026-05-30 Nightly Gaps Repair Follow-up

## Scope

Public-safe follow-up for the remaining nightly automation gaps around Scheduling Cortex,
Prompt Workbench scheduled GlassHive delivery, and enabled runtime sidecar convergence.

## Requirements

- `docs/requirements_and_learnings/01_Key_Principles.md`: full-view evidence, no generated-file
  patching as product fix, and user-visible proof for browser/scheduler/GlassHive flows.
- `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`: generated runtime env is
  an output; runtime availability must come from compiler/launcher contracts.
- `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`: host-worker
  dependency failures must be structured and surfaced.
- `docs/requirements_and_learnings/49_Prompt_Architecture_and_Token_Efficiency.md`: Workbench
  scheduled prompts execute through Scheduling Cortex and GlassHive host workers, with raw details
  private.

## RCA

The previous 03:00 Workbench run failed before assignment because GlassHive returned a structured
host runtime dependency conflict for `codex-cli`. The scheduler preserved only a generic HTTP 409,
and the generated service environment did not pass the Codex app-bundle binary path to GlassHive.

A second launcher gap kept enabled sidecars degraded after manual/partial starts: `bin/viventium
launch` treated the runtime as already running when only the core web surfaces were healthy. That
allowed Conversation Recall, SearXNG, Firecrawl, and MCP sidecars to remain down while the CLI
looked satisfied.

Claude's review also caught two edge cases in the same RCA chain: Codex.app discovery needed to
cover the normal per-user macOS app root, and Scheduler-owned REST dispatch needed the same safe
host-substrate recovery rule documented for GlassHive MCP dispatch.

A later post-restart QA run exposed a second root cause in the terminal-delivery chain: GlassHive
could reconcile a host worker as gone before the wrapper had written its exit marker, even though a
valid final report was already present in the worker output. That made the child run terminal in
GlassHive while the Workbench/Scheduler parent could remain stale until another callback arrived.

## Fixes

- Generated runtime env now emits GlassHive host CLI binary paths and the active GlassHive DB path.
- GlassHive host runtime env consumes those binary-path overrides.
- Scheduling Cortex preserves structured GlassHive HTTP failure payloads and stores the real
  failure class.
- Workbench scheduled dispatch now uses configured profile/mode metadata and, when host
  `runtime_dependency_missing` occurs before assignment without a host workspace-root constraint,
  retries the same task through docker/sandbox execution before terminal failure.
- `bin/viventium launch` now checks enabled runtime sidecars before declaring the stack already
  running, including RAG, local web-search sidecars, local workspace MCP sidecars, and Telegram
  polling sidecars; if core web surfaces are up but enabled sidecars are unhealthy, it starts the
  supported launcher repair path instead of silently exiting.
- Codex.app discovery now checks `/Applications`, `~/Applications`, and the
  `VIVENTIUM_CODEX_APP_DIRS` override, matching the service environment rather than relying on the
  interactive shell.
- Background-agent compiler tests/docs were aligned to the current 2026-05-30 voice async/690 ms
  contract.
- GlassHive reconcile now checks for completed run artifacts before marking a missing-process or
  paused-worker active run as orphaned. If no completed output exists, it finalizes the run as
  interrupted and emits a terminal parent callback instead of leaving Workbench/Scheduler stale.
- The reconcile loop now isolates per-worker recovery errors so one bad worker cannot prevent later
  workers from reconciling, and recovered terminal runs now use state-checked finalization before
  emitting terminal callbacks.
- A pre-existing local QA-results artifact leak flagged during final review was sanitized across
  `qa/results`, and a regression now blocks local home paths, provider request ids, bearer tokens,
  and API-key-shaped values from QA result files that may be exported.

## Evidence

- Generated runtime env includes GlassHive host-worker availability, a Codex app-bundle binary path,
  and the active App Support GlassHive DB path.
- Full supported restart brought the live runtime to `Viventium is ready`.
- Live status after restart showed LibreChat frontend/API, Modern Playground, Telegram Bridge,
  Telegram Codex, Conversation Recall, SearXNG, Firecrawl, Google Workspace MCP, Microsoft 365 MCP,
  and the macOS helper all running.
- Direct probes returned healthy responses for LibreChat API, frontend, playground, Conversation
  Recall, SearXNG, Firecrawl root, GlassHive API, and authenticated MCP endpoints.
- Docker showed local RAG/vector DB, SearXNG, Firecrawl, and MS365 sidecars running.
- Workbench loopback auth resolved the single local admin without putting the account identifier in
  this report.
- A real `Subconscious Deep Thought` manual run on the local admin account queued through GlassHive,
  received a GlassHive run id, completed, and updated the parent scheduler task to `success` /
  `sent`.
- The final post-reconcile-fix/restart proof showed the latest Scheduler run row `completed`, the parent
  task ledger `success` / `sent`, the GlassHive run row `completed` with output present, and
  delivered `run.queued`, `run.started`, and `run.completed` callbacks.
- Browser QA with Playwright opened Prompt Workbench and confirmed the Workbench/schedule surface
  was visible after the final repair. Screenshots/snapshots were not published because they can
  contain private prompt and memory text.
- After the follow-up launcher health gate change, `bin/viventium launch` returned
  `Viventium is already running` only while enabled sidecars were also healthy.

## Commands

- `uv run --with pytest --with pyyaml --with pydantic python -m pytest ...` targeted launcher,
  continuity, compiler, preflight, and Scheduler/GlassHive regressions: **18 passed**.
- `uv run --with pytest --with pyyaml python -m pytest tests/release/test_config_compiler.py -q`:
  **108 passed**.
- `uv run --with pytest --with pyyaml python -m pytest tests/release/test_preflight.py -q`: **63
  passed**.
- `uv run --with pytest --with pyyaml --with pydantic python -m pytest
  tests/release/test_scheduled_glasshive_prompts.py -q`: **12 passed, 5 skipped**.
- GlassHive runtime/profile/reconcile regressions under
  `viventium_v0_4/GlassHive/runtime_phase1`: **8 passed**.
- `uv run --with pytest python -m pytest tests/release/test_qa_results_public_safety.py -q`:
  **1 passed**.
- Focused launcher sidecar regressions in `tests/release/test_cli_upgrade.py`: **5 passed**.
- Full `test_cli_upgrade.py` produced **30 passed** but the `uv` wrapper was interrupted after the
  pytest summary because a subprocess cleanup wait did not return; this was not counted as a clean
  completion gate.
- Focused compiler drift fix tests: **2 passed**.
- `bin/viventium continuity-audit`: **ok**, no Mongo introspection warning after the continuity
  resolver repair.
- `bash -n bin/viventium`, `git diff --check`, Prompt Workbench Playwright CLI smoke, final
  `bin/viventium status`, final `bin/viventium launch`, and public-safety scan: **PASS**.

## Status

PASS for SCHED-002, SCHED-006, SCHED-008, and PW-029 on this real local runtime.

SCHED-005 remains PARTIAL only for the live host-worker overlap stress case; this run proved normal
delivery after the dependency repair, not simultaneous host contention.

## Claude Review

Claude returned `accept_with_risks` on the final review. Actionable findings addressed here:
Codex.app discovery covers the per-user app root/override, launcher idempotence checks enabled
MCP/Telegram sidecars in addition to RAG/search sidecars, Scheduler REST dispatch has a safe docker
recovery branch for host runtime dependency blockers, GlassHive reconcile is per-worker isolated and
state-checked, and the local QA-results leak was sanitized with a regression gate.

Remaining non-blocking risks: the exact missing-process-with-completed-output race is regression
covered but not intentionally reproduced on the live runtime after the fix; the full
`test_cli_upgrade.py` cleanup hang needs separate RCA; `SCHED-005` live host-worker overlap stress
remains separate.

## Public Safety

Raw prompt bodies, user email, local absolute paths, private DB rows, private logs, browser
snapshots, memory proposal contents, and launch tokens were excluded from this public report.
