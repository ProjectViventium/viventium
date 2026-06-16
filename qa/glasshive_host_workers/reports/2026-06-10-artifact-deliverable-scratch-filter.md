# GlassHive Artifact Deliverable Scratch Filter QA - 2026-06-10

## Summary

- Result: PASS for the code under review in an isolated local GlassHive runtime; the already-running
  local production GlassHive service was inspected pre-fix but was not restarted during this QA run.
- Build/source under test: current local checkout plus nested GlassHive runtime source.
- Runtime/artifact under test: artifact discovery, live deliverable payload, artifact open/download
  rejection, MCP artifact signing filter, and browser artifact preview.
- Environment: isolated local GlassHive API on a throwaway database with synthetic public-safe files.
- Tester: Codex.
- Related change: reject runtime/browser scratch paths from user-facing artifact delivery.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `GHHOST-004` | PASS | Targeted API/MCP tests, full nested API/MCP suites, isolated API checks, Playwright preview/rejection checks | Existing live runtime still needs restart/deploy to pick up the source fix. |
| `GHHOST-UC-005` | PASS | Real browser opened the legitimate CSV preview and the rejected extension capture path | Browser evidence used synthetic paths only. |
| `GHHOST-002` | PARTIAL | This report uses the evidence template and was reviewed for public-safety constraints | Parent QA contract test still fails on unrelated pre-existing reports outside this change. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `GHHOST-UC-005` | Open a generated artifact after browser automation created local Chrome profile/capture files. | Isolated GlassHive API and Playwright browser preview. | PASS | Browser page title was `GlassHive file - result.csv`; visible preview body showed `name,status synthetic,ok`. The bad extension capture path showed `{"detail":"Artifact path is not downloadable"}`. | Live payload selected `artifacts/result.csv`; artifact list contained only the legitimate CSV; direct open/download rejected scratch paths; MCP artifact tools filtered scratch/upload paths. | Restart/deploy the live GlassHive service before expecting existing local production URLs to reflect this fix. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: GlassHive host-worker artifact delivery.
- Requirement: `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`.
- Use case: `GHHOST-UC-005`.
- QA case: `GHHOST-004`.
- Expected result: user-facing artifact delivery promotes legitimate worker outputs and rejects
  runtime/browser scratch state such as `tmp/chrome-user-data`, extension capture pages, upload
  metadata, and cookie/login stores.
- Actual evidence: synthetic API/MCP/browser QA showed the legitimate CSV was listed, promoted, and
  previewed, while the extension capture path and scratch paths were rejected or omitted.
- Remaining gap or fix: live local production GlassHive must be restarted or redeployed to apply the
  source change to existing running URLs.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | GlassHive workstation runtime, `GHHOST-UC-005`, `GHHOST-004`. |
| Code owning path | Which code path owns the behavior? | Nested GlassHive deliverable predicate and API/MCP artifact routes. |
| Docs and nested docs/repos | Which docs or nested repo docs define the expected behavior? | GlassHive requirement doc now states scratch/browser state is never a user-facing deliverable. |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | GlassHive pytest API/MCP suites and Playwright CLI browser QA. |
| Local/external prerequisite state | Which required local service, provider, Docker-backed sidecar, OAuth grant, API key, model, or hosted dependency was proven healthy or degraded? | No external provider auth required; isolated local API was healthy. |
| Logs | Which sanitized logs confirm or contradict the result? | Test runner output showed targeted and full nested GlassHive API/MCP suites passed. |
| DB/state/persistence | Which sanitized state, DB count/hash, persisted message, config, or artifact confirms it? | Throwaway runtime state showed one synthetic worker with one legitimate listed artifact. |
| Generated/shipped artifact | Which generated config, compiled bundle, prebuilt helper, or installed artifact was inspected when applicable? | Source/runtime code under nested GlassHive checkout; no shipped binary or installed service was restarted. |
| Real user path | Which browser/computer, Telegram, voice, installer, CLI, MCP/tool, scheduler, or GlassHive path was used like a user? | Playwright opened the artifact preview and the forbidden extension capture path through the GlassHive HTTP surface. |
| Visual/UX comparison | Does the visible UI/UX or delivered result match the expected behavior and supporting evidence? | Yes: legitimate CSV preview rendered; scratch path rendered an error response. |
| Not run / blocked | Which required surface was not run, and why is the result partial or blocked? | Live local production restart was intentionally not performed to avoid disturbing an active worker. |

## User-Grade Evidence

- Surface exercised: GlassHive artifact API and browser artifact preview.
- Real user path: create synthetic worker workspace, request live payload and artifacts, open the
  legitimate artifact preview in a browser, then open the forbidden extension capture path in a
  browser.
- Visible outcome: legitimate preview showed the CSV file name and content; forbidden path showed
  `Artifact path is not downloadable`.
- Expanded/detail state: API live payload pointed at `artifacts/result.csv`; artifact list omitted
  top-level `tmp/`, `uploads/`, and browser-profile files.
- Persistence/reload result: not applicable for this isolated artifact-open check; no persistent
  production state was mutated.
- Local/external prerequisite state: isolated GlassHive API responded on a local test port; Playwright
  CLI prerequisite `npx` was present.
- Evidence retrieval classification, if applicable: not applicable; this was artifact delivery, not
  external evidence retrieval.
- Fallback path, if applicable: not applicable.
- Backend/log/DB confirmation: automated API/MCP tests passed; isolated API returned HTTP 400 for the
  bad path and listed only the legitimate CSV.
- Final model/runtime wording check: not applicable to final assistant wording; runtime-visible error
  class was specific and did not claim the scratch file was a deliverable.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for any required visible-UI, detail-state,
  persistence, or wording step. A Playwright browser path was run for the visible artifact preview.

## Automated Evidence

```bash
runtime_phase1/.venv/bin/python -m pytest runtime_phase1/tests/test_api.py::test_artifact_surfaces_reject_browser_runtime_scratch_paths runtime_phase1/tests/test_api.py::test_live_payload_artifact_inventory_includes_multiple_signed_files runtime_phase1/tests/test_api.py::test_deliverable_detection_ignores_glasshive_scaffold_files -q
runtime_phase1/.venv/bin/python -m pytest runtime_phase1/tests/test_mcp_server.py::test_workspace_artifacts_returns_signed_download_links runtime_phase1/tests/test_mcp_server.py::test_workspace_artifact_download_rejects_traversal_before_signing -q
runtime_phase1/.venv/bin/python -m pytest runtime_phase1/tests/test_api.py -q
runtime_phase1/.venv/bin/python -m pytest runtime_phase1/tests/test_mcp_server.py -q
runtime_phase1/.venv/bin/python -m py_compile runtime_phase1/src/workers_projects_runtime/deliverables.py runtime_phase1/src/workers_projects_runtime/api.py runtime_phase1/src/workers_projects_runtime/mcp_server.py
uv run --with pytest --with pyyaml python -m pytest tests/release/test_qa_operating_contract.py -q
```

- Targeted API tests: PASS.
- Targeted MCP tests: PASS.
- Full nested GlassHive `test_api.py`: PASS.
- Full nested GlassHive `test_mcp_server.py`: PASS.
- Py compile check: PASS.
- Parent QA operating-contract test: 22 PASS, 1 FAIL due to unrelated pre-existing dated reports
  outside this change that lack the required evidence template or explicit exemption.
- Review-only second opinion: BLOCKED because local Claude CLI reported its session limit was reached.

## Findings

- Defects fixed: Chrome extension capture pages and browser/runtime scratch state can no longer be
  listed, signed, opened, downloaded, or promoted as user-facing artifacts.
- Regressions found: none in nested GlassHive API/MCP suites.
- Flakes observed: none.
- Environment issues: parent repo has no local pytest environment; ephemeral `uv` test environment
  was used for the QA operating-contract check. Local Claude CLI was unavailable due to a session
  limit, so the required review-only second opinion remains unrun.
- Residual risks: existing live local production GlassHive process will continue old behavior until
  it is restarted or updated to the patched source; second-opinion review should be rerun when Claude
  is available.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
