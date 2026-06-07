<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# Stable Dev Runtime QA: Helper Steady-State Health

Date: 2026-05-27

## Scope

This report covers `SDR-008` and `STABLEDEV-UC-004`: keep local prod running while ensuring the macOS helper does not continuously render the modern playground root page just to decide health.

## Result

PASS.

The source, shipped helper artifact, automated regression tests, browser-facing modern playground route, and live refreshed helper are verified. The approved live refresh restarted only the macOS status-bar helper. Local prod and Docker services were not stopped.

## Root Cause Evidence

- Docker was running but was not the primary CPU source in the sampled state. Container CPU was low: Firecrawl API about 0.3%, Firecrawl Postgres about 1.0%, SearXNG 0%, and Microsoft 365 MCP 0%.
- The sampled high product-specific CPU was the modern playground Next server, with the status-bar helper also active.
- Local prod was attached to the documented ports `3180`, `3190`, and `3300`. The sampled dev offset ports `4180`, `4190`, and `4300` were not occupied.
- The live helper log still reflected the old behavior: in a 5000-line tail sample, root-page health probes dominated (`root_get=4990`, `health_get=3`).
- The existing local-prod/dev-env boundary was respected: no duplicate singleton services were started and no recommendation was made to stop Docker or shut down Viventium as the durable fix.

## Fix Under Test

- The helper now computes one `StackHealthSnapshot` per refresh path and caches healthy steady-state snapshots for 30 seconds.
- The modern playground readiness probe uses `/api/health` instead of `/`.
- The modern playground exposes a lightweight `GET /api/health` route with `Cache-Control: no-store`.
- Helper-launched start/stop logs rotate when oversized before new detached helper commands write to them.
- QA lifecycle probes now use the same lightweight playground health route.
- Runtime summary probes also use the lightweight playground health route.
- Split-workspace helper checks reuse the already-computed helper health snapshot where available.

## User-Level QA

- `http://localhost:3300/api/health` returned HTTP 200 with `{ "status": "ok", "surface": "modern-playground" }` and `Cache-Control: no-store`.
- Playwright opened `http://localhost:3300`; the visible page title was `Viventium Voice Assistant`, and the voice UI rendered with listening/speaking controls.
- A separate curl probe to `/api/health` returned HTTP 200 in about 0.006 seconds after the route was compiled.
- After approval, `bin/viventium runtime-checkout use --this --allow-protected-folder` refreshed and relaunched only the helper.
- The helper PID changed after refresh, while local prod stayed attached to the same checkout and continued listening on `3180`, `3190`, and `3300`.
- First post-refresh log window: `root_get=0`, `health_get=4`, `pretransform=0`, `failed_load=0`.
- Second steady-state log window over 75 seconds: `steady_root_get=0`, `steady_health_get=2`, `steady_pretransform=0`, `steady_failed_load=0`.
- After the helper refresh, the modern playground `next-server` was no longer in the sampled top CPU list. The remaining top CPU sample was dominated by WindowServer/Codex activity, with Docker VM modestly active.

## Automated Checks

- `swiftc -parse-as-library -typecheck apps/macos/ViventiumHelper/Sources/ViventiumHelper/ViventiumHelperApp.swift` passed.
- `cd viventium_v0_4/agent-starter-react && pnpm exec tsc --noEmit` passed.
- `uv run --with pytest --with pyyaml python -m pytest tests/release/test_voice_playground_dispatch_contract.py tests/release/test_native_stack_helpers.py tests/release/test_stack_port_probe_timeouts.py -q` passed: 39 tests.
- `uv run --with pytest --with pyyaml python -m pytest tests/release/test_macos_helper_install.py -q` passed: 11 tests after the split-workspace snapshot adjustment.
- `uv run --with pytest --with pyyaml python -m pytest tests/release/test_stable_dev_runtime_workflows.py -q` passed: 23 tests after the runtime-summary health probe adjustment.
- `uv run --with pytest --with pyyaml python -m pytest tests/release/test_cli_upgrade.py -q -x -k 'not upgrade_restart_stops_running_stack and not upgrade_restart_stops_scoped_dependency_jobs_before_bootstrap'` passed: 35 tests, 2 deselected. The two deselected upgrade-restart fixture tests hung in their temporary stop-wait harness during this local run and were stopped.
- `python3 -m py_compile scripts/viventium/qa_helper_lifecycle.py` passed.
- `python3 -m py_compile scripts/viventium/install_summary.py scripts/viventium/qa_helper_lifecycle.py` passed.
- `git diff --check` on touched files passed.

## Second Opinion

A review-only Claude pass agreed that the helper root-page polling was the correct product root cause and that the `/api/health` plus snapshot-cache approach respects the local-prod/dev-env boundary. Claude flagged two consistency gaps that were fixed in this pass: runtime summary playground probing and the split-workspace helper cache bypass.

## Remaining Notes

The installed helper executable is locally code-signed during installation, so its final checksum differs from the unsigned shipped prebuilt. The live installed helper contains the new `/api/health` probe string and the post-refresh runtime evidence proves the intended behavior.
