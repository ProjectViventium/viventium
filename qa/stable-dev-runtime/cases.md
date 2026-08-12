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
- Last Run: 2026-08-05 current-checkout activation QA - passed by validated live activation,
  installed-helper rebinding, restart, browser refresh, and process/ownership checks
  ([report](reports/2026-08-05-latest-checkout-activation-and-supervision.md))

## SDR-004: Upgrade Check Is Side-Effect-Free

- Requirement: `50_Stable_Dev_Runtime.md`
- Surfaces: CLI, helper
- Preconditions: git checkout with upstream
- Steps: run `bin/viventium upgrade --check --json`
- Expected Result: JSON reports update status and blockers without fetch/pull, Git metadata writes,
  App Support creation, compile, helper install, or restart; exit `0`, `2`, or `3` matches the
  structured result
- Forbidden Result: `FETCH_HEAD`, working tree, App Support, generated runtime files, helper bundle,
  or running stack changes
- Evidence: dated report under `reports/`
- Last Run: 2026-07-19 automated local-remote and no-App-Support regressions - passed; post-change
  headed helper modal rerun remains open

## SDR-005: Helper Update Modal Shows Blocked State Clearly

- Requirement: `50_Stable_Dev_Runtime.md`
- Surfaces: macOS helper, CLI
- Preconditions: helper is installed from the current checkout
- Steps: open Advanced > Check for Updates while the checkout has local QA edits
- Expected Result: modal reports update is blocked with a clear dirty-checkout reason and does not install or restart
- Forbidden Result: silent pull/install, ambiguous error, or helper quits while checking
- Evidence: dated report under `reports/`
- Last Run: 2026-07-19 source/prebuilt and parser regressions - passed; the last headed native modal
  evidence is 2026-05-14 and must be rerun for release acceptance

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
- Last Run: 2026-08-05 current-checkout activation QA - passed; status kept optional-service
  degradation visible while core surfaces remained running
  ([report](reports/2026-08-05-latest-checkout-activation-and-supervision.md))

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

## SDR-009: Failed Activation Validation Does Not Restart The Stack

- Requirement: `50_Stable_Dev_Runtime.md`
- Surfaces: `bin/viventium dev-runtime`, config compiler, doctor, running local services
- Preconditions: local prod is healthy and an intentionally invalid synthetic config is available
- Steps: record API and Workbench PIDs, run `dev-runtime activate-current --validate --restart`
  against the invalid config, then compare PIDs and health
- Expected Result: command exits nonzero at compilation or doctor, explains that the running stack
  was not restarted, and leaves both PIDs/health unchanged
- Forbidden Result: failed validation continues into a delayed stop/restart or masks compiler failure
- Evidence: release regression plus dated feature QA report
- Last Run: 2026-07-11 local unhappy-path QA - passed; compiler failure returned 1 and both PIDs stayed unchanged

## SDR-010: Upgrade Safety Is Structured And Honest

- Requirement: `50_Stable_Dev_Runtime.md`, `39_Installer_and_Config_Compiler.md`
- Surfaces: public CLI, managed component checkouts, continuity audit, macOS helper
- Preconditions: synthetic clean, refresh-required, dirty, malformed, running, and stop-failure
  states are available
- Steps: run `upgrade --check --json`, then exercise the mutating upgrade guard in isolated fixtures
- Expected Result: clean pin differences are refreshable; dirty selected work returns `3`; unselected
  dirty work does not block; running/no-restart, bad baseline, and stop failure abort before unsafe
  mutation; helper preserves valid blocker detail
- Forbidden Result: exit `0` with blockers, fetch during check, dirty component mutation, swallowed stop
  failure, auto-restart after continuity error, or wording that claims partial state was rolled back
- Evidence: `test_stable_dev_runtime_workflows.py`, `test_cli_upgrade.py`, rebuilt universal helper
- Last Run: 2026-07-19 - passed 84/84 across the two complete affected modules; live no-share guest
  running/no-restart and dirty-selected-component refusal also passed without stopping core services;
  successful/late-failure and headed helper-dialog lanes remain open

## SDR-011: Helper Recovery Is Compatible With Legacy Logs And Single-Flight

- Requirement: `50_Stable_Dev_Runtime.md`, `03_Telegram_Bridge.md`
- Surfaces: installed macOS helper, detached launcher, LibreChat web/API, Telegram Desktop
- Preconditions: local prod is stopped; `helper-start.log` is an owner-owned single-link regular file
  created by an older launcher at mode `0644`; runtime supervision still desires `running`
- Steps: launch the installed helper, observe the full search-index/client warm-up, repeat with a
  manual `start --restart` while helper supervision remains enabled, then send a synthetic
  exact-response Telegram turn after every required surface is healthy
- Expected Result: the helper tightens the compatible legacy log to `0600`, submits one detached
  recovery, waits through warm-up without another restart, and Telegram works after recovery
- Forbidden Result: secure log migration disables recovery, helper/manual `start --restart`
  submissions overlap during the receipt replacement window, the API remains down, or Telegram
  exposes a generic connection bubble after the helper reports healthy
- Evidence: helper/source regressions, installed helper artifact hashes/signature, timestamped helper
  logs, port/health checks, Telegram Desktop bubble/audio, Mongo message, GlassHive run audit
- Last Run: PASS 2026-08-04; one supervisor launch at `14:25:46Z` reached healthy at `14:28:41Z`.
  A later manual restart published and cleared its startup claim, produced zero competing helper
  launches and one runtime process group, restored every core port, and the clean Telegram marker
  persisted without error.

## SDR-012: Installed Helper Maintains Durable Runtime Intent

- Requirement: `50_Stable_Dev_Runtime.md`
- Surfaces: installed macOS helper, helper config, local-prod API/web/playground/Recall surfaces
- Preconditions: installed helper is bound to the active checkout; runtime supervision desires
  `running`; protected-folder access is approved when the active checkout requires it
- Steps: verify the installed binary matches the current shipped helper artifact, stop local prod
  outside the helper's intentional **Stop** action, wait for bounded helper recovery, then refresh the
  browser surface; separately exercise the supervisor state model for **Stop**, **Quit**, and **Start**
- Expected Result: the helper relaunches the stopped stack without a login/reboot or manual CLI
  start, all required surfaces recover, refresh succeeds, intentional stopped state remains stopped,
  and later Start resumes supervision
- Forbidden Result: one-shot login-only startup, unbounded rapid launch loops, duplicate concurrent
  launches, helper reinstall erasing desired state or unknown config, or a green status row backed by
  another checkout's Prompt Workbench
- Evidence: installed binary/source hashes, helper state and sanitized logs, process ownership, health
  probes, browser refresh, and release regressions
- Last Run: in progress 2026-08-05; installed artifact and automated state/backoff/config-preservation
  lanes passed, while the real protected-folder recovery lane awaits the macOS approval prompt

## SDR-013: Dev Stop Preserves Local Prod Ownership

- Requirement: `50_Stable_Dev_Runtime.md`
- Surfaces: config compiler, `dev-env` wrapper, stack/native stop, Prompt Workbench, local RAG,
  browser, processes, ports, Docker
- Preconditions: local prod and a named QA dev environment are running together; Workbench is enabled
  for both; the QA lane owns local RAG rather than sharing prod RAG
- Steps: inspect compiled ports and wrapper identity; open both Workbench pages; record sanitized
  state/PID/port and prod-container baselines; run the supported QA dev stop; compare every dev and
  prod surface afterward
- Expected Result: Workbench has an offset compiler-owned port and runtime-owned state/PID; both
  visible pages are distinct and watchdog-stable before stop; QA stop closes all QA listeners and
  QA Compose containers while every prod API/web/playground/GlassHive/Workbench PID and prod RAG
  container identity remains unchanged; stale native PIDs cannot authorize a kill; a restart-facing
  start adopts exactly one identity-matched selected-runtime native listener and atomically restores
  its PID receipt so the next supported stop owns it; the stop child inherits the selected
  `runtime.env` plus `runtime.local.env` and selected App Support/profile/port/data ownership rather
  than ambient canonical values, including when a selected local path references its selected state
  root; ambient native credential inputs cannot outrank the selected local layer
- Forbidden Result: shared-checkout process sweep, canonical-state fallback, prod port/container
  removal, QA Workbench left running, local RAG using the prod Compose project or vector host port,
  a stale PID killing an unrelated native process, or truncated process output skipping an exact
  selected-runtime MongoDB or Meilisearch PID because its data path occurs late in argv; lookalike
  service executables, prefixed data/config paths, and similarly named LiveKit options must not pass
  ownership checks; zero, multiple, or foreign listener PIDs must not be adopted, and an existing
  Meilisearch port must not be trusted without process and data-path validation; a shell-local
  selected port or data path must not disappear at the native child boundary and fall back to prod
- Evidence: [2026-08-10 prod/dev isolation report](reports/2026-08-10-prod-dev-runtime-isolation.md)
- Last Run: PARTIAL 2026-08-10. The supported isolated-runtime stop/start restored the selected
  API/Web/Playground/GlassHive/Workbench/native services while measured local prod remained healthy,
  and the complete-argv, exact-`ucomm`, canonical `lsof`, foreign-runtime, unique-listener, stale-PID,
  and selected-environment regressions pass. The retained runtime logs do not preserve the earlier
  exact-listener adoption event, so a fresh supported start -> adopt -> stop -> start run with a
  sanitized durable ledger is still required before this case can be called PASS.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Stable Dev Runtime. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID        | Natural user action                                                                                                                                                                          | Requirement / case link                                      | Real surface to use                                                                           | Supporting evidence to compare                                                                                                                                                        | Expected visible result                                                                                                                                               | Last run                                                                                                                                                                                                                             |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `STABLEDEV-UC-001` | Run the stable dev runtime status/start path and inspect generated runtime config, helper state, and web surface reachability.                                                               | `50_Stable_Dev_Runtime.md` / `SDR-001`-`SDR-007`             | `bin/viventium status`, dev-runtime/dev-env CLI, helper status, and browser/health endpoints  | Generated config summary, status output, helper state, logs, release tests, and dated QA report                                                                                       | Core services and optional services are classified truthfully, with helper status separate from runtime readiness.                                                    | PASS 2026-08-05; current checkout, helper, stack owner, processes, browser refresh, and health converged ([report](reports/2026-08-05-latest-checkout-activation-and-supervision.md))                                                |
| `STABLEDEV-UC-002` | Run the same status path when optional services or helper surfaces are disabled/unreachable.                                                                                                 | `50_Stable_Dev_Runtime.md` / `SDR-007`                       | CLI status, generated runtime config, helper state, and logs                                  | Optional service health, stale lock checks, generated env/config, logs, and QA report                                                                                                 | Status says needs attention/action required for unreachable enabled optional surfaces and never masks broken dependencies as ready.                                   | PASS 2026-08-05; Recall degradation was visible until semantic recovery and the unrelated maintenance failure remained `Action Required` ([report](reports/2026-08-05-latest-checkout-activation-and-supervision.md))                |
| `STABLEDEV-UC-003` | Start and stop Prompt Workbench from the CLI/helper path and verify it does not start or stop the main Viventium runtime.                                                                    | `50_Stable_Dev_Runtime.md` / `SDR-006`                       | CLI prompt-workbench lifecycle, helper submenu, health endpoint, process state                | PID/port metadata summary, `/api/health`, process state, helper install inspection, and QA report                                                                                     | Only the managed workbench process is affected; LibreChat/main Viventium stack state is preserved.                                                                    | 2026-05-15 local CLI/helper integration QA - passed                                                                                                                                                                                  |
| `STABLEDEV-UC-004` | Leave local prod running while developing and verify the helper does not continuously render user-facing root pages to decide health.                                                        | `50_Stable_Dev_Runtime.md` / `SDR-008`                       | macOS helper, modern playground `/api/health`, helper-launched logs, real browser route check | Helper source/test contract, Playwright health/root checks, sanitized log counts, live port/process snapshot                                                                          | Local prod stays up, dev/server logs stop accumulating helper root-page probes, and no singleton service is stopped or duplicated.                                    | 2026-05-27 implementation QA - passed with live helper refresh                                                                                                                                                                       |
| `STABLEDEV-UC-005` | Promote a checkout with validation enabled while the candidate config or prerequisites are invalid.                                                                                          | `50_Stable_Dev_Runtime.md` / `SDR-009`                       | `dev-runtime activate-current --validate --restart`, API/Workbench health and PIDs            | Compiler/doctor exit, CLI wording, pre/post process identity                                                                                                                          | Validation fails loudly before stop/restart and the current healthy stack remains untouched.                                                                          | PASS 2026-07-11; synthetic invalid config returned 1 and pre/post API and Workbench PIDs matched.                                                                                                                                    |
| `STABLEDEV-UC-006` | Check for and attempt an upgrade from clean, refreshable, dirty, running, and continuity-error states.                                                                                       | `50_Stable_Dev_Runtime.md` / `SDR-004`, `SDR-005`, `SDR-010` | CLI JSON/text, helper modal, disposable running runtime                                       | Exit/status JSON, Git metadata, component state, audit status, process health, helper dialog                                                                                          | Inspection is side-effect-free; safe refresh remains available; blockers stop before mutation with specific guidance; no partial state is called rolled back.         | PARTIAL 2026-07-19; 84 affected-module regressions, universal helper rebuild/install, and live no-share running/dirty refusal pass; successful/late-failure update and headed helper dialog remain open.                             |
| `STABLEDEV-UC-007` | Let the installed helper recover a stopped local-prod stack created by an older helper, repeat with a manual restart under helper supervision, then use Telegram immediately after recovery. | `50_Stable_Dev_Runtime.md` / `SDR-011`                       | macOS helper, runtime ports, Telegram Desktop                                                 | legacy log mode migration, startup claim, helper launch count, process-group count, health endpoints, visible bubble/audio, Mongo and GlassHive state                                 | Each recovery survives the complete warm-up with one owner, all user surfaces become healthy, and the next Telegram turn succeeds without a generic connection error. | PASS 2026-08-04; installed helper migrated the log and recovered once; the manual restart then used a live startup claim, zero competing helper launches, and one runtime process group before delivering the exact Telegram marker. |
| `STABLEDEV-UC-008` | Leave the installed local-prod stack in desired `running` state, stop it outside the helper menu, and wait without logging in or manually starting it.                                       | `50_Stable_Dev_Runtime.md` / `SDR-012`                       | installed macOS helper, runtime ports, browser refresh                                        | installed binary hashes, helper state/backoff log, process roots, semantic health, visible UI and refresh                                                                             | The helper detects the stopped stack, submits one bounded recovery launch from the active checkout, restores every required surface, and continues supervising it.    | IN PROGRESS 2026-08-05; shipped/installed artifact and automated lanes pass; protected-folder approval is pending for the live recovery launch.                                                                                      |
| `STABLEDEV-UC-009` | Keep local prod and a named dev env running, open both Workbench pages, then stop only the dev env through the supported wrapper.                                                            | `50_Stable_Dev_Runtime.md` / `SDR-013`                       | browser, `dev-env run <name> stop`, process/port state, Docker                                | Compiled port/state identity, exported native-child ownership, visible page distinction, watchdog stability, complete native argv, pre/post prod PIDs, dev/prod Compose container IDs | The dev Workbench and every dev-owned listener/container stop; local prod and its shared/owned services keep the same identities.                                     | PARTIAL 2026-08-10; supported stop/start isolation and current selected-runtime health are proven, but the earlier exact-listener adoption event was not preserved in a durable sanitized ledger. Repeat the complete supported lifecycle before PASS. |

## Release Test Traceability

- `tests/release/test_cli_upgrade.py`
- `tests/release/test_config_compiler.py`
- `tests/release/test_detached_librechat_api_watchdog.py`
- `tests/release/test_detached_librechat_supervision.py`
- `tests/release/test_librechat_client_defaults.py`
- `tests/release/test_librechat_dev_start_config_sync.py`
- `tests/release/test_macos_helper_install.py`
- `tests/release/test_macos_helper_supervision.py`
- `tests/release/test_native_stack_helpers.py`
- `tests/release/test_stable_dev_runtime_workflows.py`
- `tests/release/test_stack_port_probe_timeouts.py`
