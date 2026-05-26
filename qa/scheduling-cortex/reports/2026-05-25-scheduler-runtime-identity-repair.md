# Scheduling Cortex Runtime Identity Repair - 2026-05-25

## Status

- `SCHED-004` runtime identity and port ownership: `PASS`
- `SCHED-002` trigger and delivery ledger: `PARTIAL`
- `PW-029` scheduled GlassHive prompts: `PARTIAL`

The repair proves local-prod scheduler ownership and dev-env scheduler port isolation. It does not
claim that the next due scheduled prompt has delivered, because repair QA intentionally did not
trigger a real private scheduled prompt or mutate owner memory/conversation state.

## Requirements Reviewed

- `AGENTS.md`
- `docs/requirements_and_learnings/01_Key_Principles.md`
- `docs/requirements_and_learnings/11_Scheduling_Cortex.md`
- `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`
- `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`
- `docs/requirements_and_learnings/49_Prompt_Architecture_and_Token_Efficiency.md`
- `docs/requirements_and_learnings/50_Stable_Dev_Runtime.md`
- `docs/02_ARCHITECTURE_OVERVIEW.md`
- `docs/03_SYSTEMS_MAP.md`
- `viventium_v0_4/docs/DEVELOPMENT_GUIDE.md`
- `qa/README.md`
- `qa/feature-user-use-case-checklist.md`
- `qa/scheduling-cortex/cases.md`
- `qa/prompt-workbench/cases.md`

Relevant rules applied:

- Scheduling Cortex is a per-runtime durable sidecar, not a shared singleton.
- Local prod and dev envs must have distinct app-facing/runtime-local sidecar state.
- Shared singleton defaults are recall/RAG, SearXNG, Firecrawl, Google Workspace MCP, and
  Microsoft 365 MCP.
- Product fixes must be source/config/runtime fixes, not App Support generated-state edits.
- Health/status endpoints and public QA must not expose raw local paths, secrets, private prompts,
  schedule bodies, user ids, private schedule titles, or raw conversation content.
- User-visible QA and supporting state/log/DB evidence must be kept distinct; supporting evidence
  cannot substitute for a required due/delivery run.

## RCA

The local-prod nightly scheduler appeared healthy because `localhost:7110/health` returned
`{"status":"ok"}`, but that port was owned by a dev-env Scheduling Cortex process attached to a
different scheduler DB. The local-prod launcher accepted any healthy response on the configured
port, the scheduler health payload had no runtime identity, and dev-env config generation did not
offset `scheduling_mcp_port` even though the scheduler owns per-runtime mutable state.

Existing tests passed because they checked launcher scaffolding and compiler behavior around broad
runtime setup, but did not assert scheduler DB identity in `/health`, launcher rejection of foreign
or legacy health payloads, or dev-env scheduler port isolation.

## Fix

- Added a public-safe Scheduling Cortex `/health` identity payload with `db_path_sha256`,
  `state_root_sha256`, runtime profile, dev-env flag, hashed dev-env name, service, status, and pid.
- Updated the launcher/watchdog to accept an existing scheduler only when the health DB hash matches
  the launcher runtime's expected scheduler DB.
- Changed mismatched or legacy scheduler health from "healthy enough" to a fail-loud port ownership
  conflict.
- Removed broad same-source scheduler process cleanup for the stop/restart path so a healthy
  foreign runtime is not killed by command pattern.
- Updated dev-env creation and config compilation so the scheduler gets an offset runtime-local
  sidecar port. The default offset is biased away from shared singleton ports such as RAG.
- Documented the runtime identity contract in Scheduling Cortex, installer/config compiler, stable
  dev-runtime, and Scheduling Cortex MCP docs.
- Added reusable QA case `SCHED-004`.

## Claude Review

A review-only Claude pass on `opus` confirmed the RCA and challenged the initial scoped-kill
proposal. The key accepted correction was that source-directory-scoped cleanup could still kill an
active dev-env scheduler when local prod and dev env run from the same checkout. The implemented fix
therefore treats mismatched or missing health identity as a conflict and leaves foreign healthy
runtime processes alone.

## Verification

Commands run:

- `bash -n viventium_v0_4/viventium-librechat-start.sh`
  - Result: pass.
- `python3 -m py_compile scripts/viventium/dev_runtime.py scripts/viventium/config_compiler.py viventium_v0_4/LibreChat/viventium/MCPs/scheduling-cortex/scheduling_cortex/server.py`
  - Result: pass.
- `uv run --with pytest --with pyyaml --with pydantic --with croniter --with fastapi --with fastmcp python -m pytest tests/release/test_scheduling_mcp_supervision.py tests/release/test_stable_dev_runtime_workflows.py -q`
  - Result: `23 passed`, one upstream FastMCP warning.
- `uv run --with pytest --with pyyaml --with pydantic --with croniter --with fastapi --with fastmcp python -m pytest tests/release/test_config_compiler.py tests/release/test_scheduling_mcp_supervision.py tests/release/test_stable_dev_runtime_workflows.py tests/release/test_prompt_workbench.py tests/release/test_scheduled_glasshive_prompts.py -q`
  - Result: `213 passed`, one upstream FastMCP warning.
- Temporary config compile proof:
  - Local-prod generated scheduler URL stayed on the canonical scheduler port and RAG stayed on the
    shared singleton port.
  - Existing dev-env generated scheduler URL moved to an offset scheduler port distinct from both
    local-prod scheduler and shared RAG.
- Temporary scheduler probe:
  - `/health` returned the expected identity fields and did not expose raw local paths or dev-env
    names.
- Supported background launch:
  - `bin/viventium launch` restored local prod.
  - `curl http://localhost:7110/health` returned an identity-bearing Scheduling Cortex response for
    local prod.
  - `bin/viventium status` reported Viventium ready.
- Playwright CLI:
  - Prompt Workbench opened successfully in a real browser.
  - The Prompt Flow tree showed the scheduled-prompt group and enabled schedules. The snapshot was
    not copied into this report because it can contain private user-level schedule labels.

## Not Run

- The next natural nightly due time was not waited for during this repair.
- A real private scheduled GlassHive run was not manually triggered, because that could mutate owner
  memories or conversations.
- A clean-machine install was not run; this was a local runtime/source repair.

## Public-Safety Review

This report intentionally omits raw App Support paths, raw DB paths, health hash values, private
schedule titles, private prompts, user identifiers, tokens, screenshots, and raw Playwright
snapshots.

## Remaining Risk

`SCHED-002` and `PW-029` remain `PARTIAL` until the next safe due/manual scheduled run proves the
delivery ledger and visible result on the real runtime. The scheduler ownership bug that blocked
that proof is repaired and covered by `SCHED-004`.
