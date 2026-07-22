# 2026-06-27 Docker Active-Run Heartbeat And Desktop Prime Local QA

<!-- qa-evidence-exempt: Historical environment-specific regression record retained as supporting evidence; it is not a release-wide user-path report. -->

## Scope

- Local-only GlassHive QA for `GHWATCH-011` and the workstation slice of `GHHOST-006`.
- No cloud deploy, no LibreChat image/code change, no provider-backed model call.
- Synthetic public-safe smoke run used a deterministic local shell command inside the real Docker
  workstation container.

## Requirements Checked

- Docker/workstation runs write truthful `active-run.json` status like host-native runs.
- Active status includes transcript existence, byte counts, mtimes, tail hashes, quiet duration,
  timeout policy, stop reason, exit code, and evidence path.
- Fresh desktop priming writes private diagnostic state and is exposed through runtime description.
- Worker prompts provide factual workstation capability context without forcing a workflow.
- Missing HTML visual smoke prerequisites are explicit and actionable.
- No residual warning UX was added.

## Automated Evidence

- `uv run pytest tests/test_profile_runtime.py tests/test_docker_sandbox.py tests/test_run_evidence.py -q`
  - Result: PASS.
  - Covered Docker active-run completion/timeout states, active-session instruction redaction,
    desktop-prime marker success/failure, runtime description pass-through, worker capability
    guidance, image/tooling contract, and evidence prerequisite messaging.
- Focused API/watch-status regression:
  - `tests/test_api.py::test_live_payload_survives_unavailable_idle_compute`
  - `tests/test_api.py::test_live_logs_follow_profile_when_legacy_runtime_metadata_is_stale`
  - `tests/test_api.py::test_running_worker_exposes_runtime_paths_before_task_finishes`
  - `tests/test_api.py::test_completed_docker_run_opens_workspace_html_in_sandbox_browser_once`
  - `tests/test_api.py::test_desktop_action_refreshes_activity_before_idle_reaper`
  - `tests/test_api.py::test_desktop_action_and_artifact_preview_surface_in_project_ui`
  - Result: PASS.

## Local Docker Smoke

- Workstation image present: `workers-projects-runtime-workstation:phase1-node22-docs7`.
- Smoke worker ran inside a real local Docker workstation container and created
  `output/heartbeat-smoke.txt`.
- Artifact verification: `heartbeat-smoke.txt` existed and contained `smoke ok`.
- Final output: `FINAL REPORT: Smoke artifact created.`
- Evidence summary: `evidence_result.status=pass`, with no failure or warning reasons.
- Active-run summary:
  - `state=completed`
  - `heartbeat_sequence=2`
  - `timeout_seconds=30`
  - `exit_code=0`
  - `stop_reason=process_exit`
  - `evidence_path=glasshive-run/evidence.json`
  - stdout/stderr/exit/ledger transcript entries existed with byte counts and tail hashes.
- Desktop-prime summary:
  - `schema=glasshive.desktop_prime.v1`
  - `status=launched`
  - image recorded as `workers-projects-runtime-workstation:phase1-node22-docs7`
  - runtime description exposed the marker.
- Cleanup: the smoke container was terminated after inspection; files/evidence remained in the
  local temp workspace for debugging.

## Local Watch UI Browser QA

- A synthetic local runtime API and Glass Drive UI were started against the same Docker workstation
  runtime slice.
- Playwright opened the real Watch page for a synthetic `codex-cli` Docker worker.
- Running-state evidence:
  - The header showed `codex-cli workspace · running`.
  - The state pill showed `running`.
  - The latest-output ribbon showed `Live status` and `Workspace is actively executing. You are
    watching the live desktop for this run.`
  - The primary frame stayed on the live noVNC desktop surface.
- Completion-state evidence:
  - The header changed to `codex-cli workspace · Completed`.
  - The latest-output ribbon changed to `Latest result`.
  - The detail panel opened with `Delivered result`, `Open file`, `Download file`, workspace-file
    metadata, and final output text.
  - The primary frame still showed the live desktop/noVNC surface instead of replacing the desktop
    with the artifact preview.
- Artifact route evidence:
  - The visible links used relative authenticated app routes without signed query strings.
  - `Open file` returned an HTML preview page with `watch artifact ok`.
  - `Download file` returned `text/plain`, `Content-Disposition: attachment`, and exact bytes
    `watch artifact ok`.
- Runtime/API evidence:
  - Frontend polling requests for worker/workspace live payloads returned `200 OK`.
  - Browser console warnings/errors: `0`.
  - Live payload reported `profile=codex-cli`, `backend=codex-cli`, `execution_mode=docker`,
    `state=ready`, `view_health.reason=ok`, and `desktop_prime.status=launched`.
  - Active-run evidence for the second run reported `state=completed`, `runtime=codex-cli`,
    `worker.profile=codex-cli`, `worker.execution_mode=docker`, `heartbeat_sequence=4`,
    `exit_code=0`, `stop_reason=process_exit`, stdout byte count, and stdout tail hash.
  - `evidence.json` reported `schema=glasshive.run.evidence.v1`,
    `worker.backend=codex-cli`, `model=local/watch-smoke`, `evidence_result.status=pass`,
    one artifact, and `final_output.status=ok`.
- Cleanup evidence:
  - The synthetic worker was terminated through the runtime API.
  - Docker showed no remaining synthetic workstation container after termination.
  - Local browser and harness servers were stopped.

## Unhappy Paths Covered

- Docker timeout path writes `active-run.json` with `state=timeout` and `stop_reason=timeout`.
- Idle desktop prime failure writes `desktop-prime.json` with `status=failed` before bubbling the
  underlying exception.
- HTML browser smoke evidence reports explicit missing Node/Playwright prerequisites instead of a
  vague unavailable result.

## Remaining Gates

- Provider-backed Codex/Claude browser/computer bridge connectivity is not claimed by this report.
  That remains part of configured browser extension/native-host acceptance.
- Cloud/live enterprise QA is out of scope for this local pass and requires a separate approved deploy.
