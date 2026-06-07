# Stable Dev Runtime Cases

## SDR-001: Dev Env Uses Separate App-Facing Ports

- Requirement: `50_Stable_Dev_Runtime.md`
- Surfaces: CLI, generated config
- Preconditions: canonical config exists
- Steps: run `bin/viventium dev-env create dev --port-offset 1000`, then inspect the dev config
- Expected Result: LibreChat API, frontend, playground, and voice health ports are offset
- Forbidden Result: heavy singleton service ports are unnecessarily offset or duplicated
- Evidence: dated report under `reports/`
- Last Run: 2026-05-14 local implementation QA - passed

## SDR-002: Singleton Services Are Not Duplicated By Default

- Requirement: `50_Stable_Dev_Runtime.md`
- Surfaces: CLI, compiler, launcher
- Preconditions: dev env exists with default shared singleton policy
- Steps: compile the dev env and inspect generated runtime env
- Expected Result: shared singleton markers are present and start flags for shared services are false
- Forbidden Result: dev start launches duplicate recall/RAG, SearXNG, Firecrawl, Google MCP, or MS365 MCP by default
- Evidence: dated report under `reports/`
- Last Run: 2026-05-14 local implementation QA - passed

## SDR-003: Activate Current Uses Runtime Checkout

- Requirement: `50_Stable_Dev_Runtime.md`
- Surfaces: CLI, helper config
- Preconditions: developer checkout is valid
- Steps: run `bin/viventium dev-runtime activate-current --validate --allow-protected-folder`
- Expected Result: existing runtime-checkout state is updated; no code is copied into an install path
- Forbidden Result: parallel active checkout state, physical source copy, or unreviewed nested repo pin change
- Evidence: dated report under `reports/`
- Last Run: 2026-05-14 local implementation QA - passed by live activation, validation, and restart

## SDR-004: Upgrade Check Is Side-Effect-Free

- Requirement: `50_Stable_Dev_Runtime.md`
- Surfaces: CLI, helper
- Preconditions: git checkout with upstream
- Steps: run `bin/viventium upgrade --check --json`
- Expected Result: JSON reports update status and blockers without pull, compile, helper install, or restart
- Forbidden Result: working tree, generated runtime files, helper bundle, or running stack changes
- Evidence: dated report under `reports/`
- Last Run: 2026-05-14 local implementation QA - passed by CLI smoke and native helper modal QA

## SDR-005: Helper Update Modal Shows Blocked State Clearly

- Requirement: `50_Stable_Dev_Runtime.md`
- Surfaces: macOS helper, CLI
- Preconditions: helper is installed from the current checkout
- Steps: open Advanced > Check for Updates while the checkout has local QA edits
- Expected Result: modal reports update is blocked with a clear dirty-checkout reason and does not install or restart
- Forbidden Result: silent pull/install, ambiguous error, or helper quits while checking
- Evidence: dated report under `reports/`
- Last Run: 2026-05-14 local implementation QA - passed by native helper modal QA

## SDR-006: Helper Prompt Workbench Stop Is Runtime-Safe

- Requirement: `50_Stable_Dev_Runtime.md`
- Surfaces: macOS helper, CLI, local process state
- Preconditions: helper is installed from the current checkout
- Steps: start Prompt Workbench through `bin/viventium prompt-workbench start`, then use or inspect
  `Advanced > Prompt Workbench > Stop`
- Expected Result: only the managed Prompt Workbench web process stops; the main Viventium runtime
  keeps its current running/stopped state
- Forbidden Result: `bin/viventium stop`, native stack stop, LibreChat stop, or arbitrary port-kill
  behavior from the Prompt Workbench submenu
- Evidence: dated report under `reports/`
- Last Run: 2026-05-15 local CLI/helper integration QA - passed

## SDR-007: Status Summary Is Truthful When Optional Runtime Surfaces Are Down

- Requirement: `50_Stable_Dev_Runtime.md`, `45_Runtime_Feature_QA_Map.md`
- Surfaces: CLI status, generated runtime config, macOS helper state
- Preconditions: core web surfaces are running; one or more enabled optional surfaces are unreachable
- Steps: run `bin/viventium status`, inspect generated runtime env/config, and verify the helper process when `showInStatusBar` is enabled
- Expected Result: status headline is "needs attention"; core surfaces are Running; each enabled but unreachable optional service is Action Required; helper status is shown separately and truthfully
- Forbidden Result: status says "ready" while enabled recall/search/MCP/helper surfaces are broken, or shows "still starting" because of a stale start lock
- Evidence: dated report under `reports/`
- Last Run: 2026-05-17 live runtime sanity - passed

## SDR-008: Helper Steady-State Health Checks Stay Lightweight

- Requirement: `50_Stable_Dev_Runtime.md`, `viventium_v0_4/docs/VOICE_CALLS.md`
- Surfaces: macOS helper, modern playground, helper-launched logs
- Preconditions: installed local-prod runtime is running with the modern playground enabled
- Steps: inspect the helper source/test contract, load the modern playground health route, and compare
  helper/start logs before and after a steady-state observation window
- Expected Result: helper status refreshes share one health snapshot per tick, the playground probe
  uses `/api/health` instead of `/`, steady-running checks back off, and helper-launched stack logs are
  rotated on new starts when oversized
- Forbidden Result: recurring helper `GET / 200` root-page probes, duplicated health probes per refresh
  cycle, unbounded helper-start log growth, or any recommendation to stop local prod/Docker as the
  durable product fix
- Evidence: dated report under `reports/`
- Last Run: 2026-05-27 implementation QA - passed with live helper refresh

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Stable Dev Runtime. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `STABLEDEV-UC-001` | Run the stable dev runtime status/start path and inspect generated runtime config, helper state, and web surface reachability. | `50_Stable_Dev_Runtime.md` / `SDR-001`-`SDR-007` | `bin/viventium status`, dev-runtime/dev-env CLI, helper status, and browser/health endpoints | Generated config summary, status output, helper state, logs, release tests, and dated QA report | Core services and optional services are classified truthfully, with helper status separate from runtime readiness. | 2026-05-17 live runtime sanity - passed for status classification |
| `STABLEDEV-UC-002` | Run the same status path when optional services or helper surfaces are disabled/unreachable. | `50_Stable_Dev_Runtime.md` / `SDR-007` | CLI status, generated runtime config, helper state, and logs | Optional service health, stale lock checks, generated env/config, logs, and QA report | Status says needs attention/action required for unreachable enabled optional surfaces and never masks broken dependencies as ready. | 2026-05-17 live runtime sanity - passed |
| `STABLEDEV-UC-003` | Start and stop Prompt Workbench from the CLI/helper path and verify it does not start or stop the main Viventium runtime. | `50_Stable_Dev_Runtime.md` / `SDR-006` | CLI prompt-workbench lifecycle, helper submenu, health endpoint, process state | PID/port metadata summary, `/api/health`, process state, helper install inspection, and QA report | Only the managed workbench process is affected; LibreChat/main Viventium stack state is preserved. | 2026-05-15 local CLI/helper integration QA - passed |
| `STABLEDEV-UC-004` | Leave local prod running while developing and verify the helper does not continuously render user-facing root pages to decide health. | `50_Stable_Dev_Runtime.md` / `SDR-008` | macOS helper, modern playground `/api/health`, helper-launched logs, real browser route check | Helper source/test contract, Playwright health/root checks, sanitized log counts, live port/process snapshot | Local prod stays up, dev/server logs stop accumulating helper root-page probes, and no singleton service is stopped or duplicated. | 2026-05-27 implementation QA - passed with live helper refresh |

## Release Test Traceability

- `tests/release/test_cli_upgrade.py`
- `tests/release/test_detached_librechat_api_watchdog.py`
- `tests/release/test_detached_librechat_supervision.py`
- `tests/release/test_librechat_client_defaults.py`
- `tests/release/test_librechat_dev_start_config_sync.py`
- `tests/release/test_macos_helper_install.py`
- `tests/release/test_native_stack_helpers.py`
- `tests/release/test_stable_dev_runtime_workflows.py`
- `tests/release/test_stack_port_probe_timeouts.py`
