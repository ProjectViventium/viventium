# GlassHive Host Workers QA Cases

## Case ID Convention

Use stable `GHHOST-NNN` IDs for glasshive host workers cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `GHHOST-001` | Host-native workers act on the intended local/browser/file surface and report completion without exposing plumbing. | User-visible behavior matches source, docs, persisted state, and logs | GlassHive MCP/API, host worker, browser/desktop/file surfaces | `tests/release/test_stable_dev_runtime_workflows.py` plus user-grade QA when visible | PASS 2026-06-22 for local approval scope: host Codex xhigh and host Claude max wait/continue smokes passed with run/evidence markers; provider-backed Codex and Claude host browser wait/continue passed. |
| `GHHOST-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | PASS 2026-06-22 for `qa/glasshive_deep_research/reports/2026-06-22-production-hardening-local-qa.md` plus public QA contract/public-safety scan. |
| `GHHOST-003` | One-shot delegation preserves instruction precision without forced canned status | Assistant can self-check the delegated instruction and acknowledges in its own voice | MCP tool result, web chat, callback result | GlassHive `test_mcp_server.py` plus browser callback QA | PARTIAL (2026-05-18 MCP/runtime QA; browser callback run pending) |
| `GHHOST-004` | Artifact discovery excludes runtime/browser scratch state and only promotes user-facing deliverables. | Users receive the actual worker output, not Chrome extension capture pages, browser profile data, uploaded-source metadata, or temporary scratch files. | GlassHive API/MCP artifacts, live payload, artifact open/download links, browser preview | GlassHive `test_api.py`, `test_mcp_server.py`, and real-browser artifact-open QA | PASS/PARTIAL 2026-06-22: local artifact-scope/browser preview coverage passed for synthetic scratch exclusions and seven deliverable types; provider-backed live callback path remains. |
| `GHHOST-005` | Host and workstation workers preserve native CLI/browser/computer capability while adding broker MCP grants. | A user can ask unknown future work and the selected worker can decide using its full native capability surface plus brokered tools. | Host Codex/Claude launch, worker-local config, workspace Codex path, runtime preflight, logs | `test_profile_runtime.py`, real `codex mcp list` capability probe, Claude help/launch probe, worker config inspection | PASS/PARTIAL (2026-06-14 source/runtime probes and targeted tests; live post-change worker launch still required after runtime rebuild/restart) |
| `GHHOST-006` | Bootstrapped workspace images include AI-worker browser extensions, native messaging hosts, and native skill awareness without forcing workflows. | A new user's workspace worker starts with truthful Claude/Codex browser-extension substrate and worker-visible skill inventory. | Docker/workstation image, Chromium/Chrome profile, Codex/Claude worker prompts, worker logs | `test_docker_sandbox.py`, `test_bootstrap.py`, `test_profile_runtime.py`, `glasshive-browser-extension-check`, real browser/Computer Use bridge QA | PASS/PARTIAL 2026-06-23: `docs6` build and managed-worker QA proved both CRXs installed, Claude native host installed and invoked, and Codex visibly reproduced disconnected when the first-party Linux native-host bundle plus node-repl provisioning were absent. |

## `GHHOST-001` - Core User Flow

- Requirement: Host-native workers act on the intended local/browser/file surface and report completion without exposing plumbing.
- Risk covered: implementation, docs, and user-visible behavior drift apart.
- Preconditions: local Viventium runtime or the specific feature harness is available with synthetic, public-safe data.
- Steps:
  1. Exercise the feature through the real user surface, not only a unit test.
  2. Compare the visible result with source code, generated/runtime config, logs, persisted state, and the owning requirement doc.
  3. Capture a public-safe report with expected result, forbidden result, evidence, residual risk, and follow-up.
- Expected result: the feature behaves as documented and every supporting layer agrees.
- Forbidden result: backend logs, mocks, source inspection, or model completions are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, generated/runtime state summary, and docs/case links.
- Automation: `tests/release/test_stable_dev_runtime_workflows.py` plus any narrower feature tests discovered during implementation.
- Last run: PASS 2026-06-22 for local approval scope. Host Codex xhigh and host Claude max
  wait/continue smokes passed through the local runtime with run/evidence markers, and the
  provider-backed Codex plus Claude host browser wait/continue bridges passed running-state,
  reload, artifact preview, short-ref, continuation, evidence, transcript-metadata, and redaction
  checks. Cloud/deployment browser reruns are separate deployment gates, not part of this local
  pass.

## `GHHOST-002` - Public-Safe Evidence Record

- Requirement: public QA artifacts must be reproducible and free of secrets, personal data, local paths, raw IDs, and private screenshots.
- Risk covered: a useful local QA run cannot be safely reviewed or published.
- Preconditions: a dated QA report is created for this feature.
- Steps:
  1. Review the report and related diffs for local absolute paths, account identifiers, tokens, raw logs, raw DB rows, private chats, and screenshots with private content.
  2. Keep raw/private evidence outside the public repo and summarize only public-safe counts, statuses, hashes, and conclusions.
  3. Link the report back to this case and the owning requirement doc.
- Expected result: the public report proves the behavior without leaking private/local data.
- Forbidden result: a report includes private transcripts, account identifiers, raw runtime dumps, local home paths, tokens, or secret-bearing command lines.
- Evidence to capture: public-safety scan result and link to the sanitized report.
- Automation: public-safety pattern scan plus relevant release tests.
- Last run: PASS 2026-06-22 for the local GlassHive hardening report and public QA
  contract/public-safety scan.

## `GHHOST-003` - Delegation Acknowledgement And Instruction Audit

- Requirement: `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`.
- Risk covered: the tool forces a prefabricated user-facing status line, or the assistant cannot
  inspect what it actually delegated and misses a wrong target/scope.
- Preconditions: callback context is available; synthetic public-safe task with a specific target,
  success condition, and short final-answer constraint.
- Steps:
  1. Call `worker_delegate_once` through the real chat/MCP path with a precise synthetic task.
  2. Verify the tool result contains `acknowledgement_guidance` rather than a literal `user_status`
     for dispatched work.
  3. Verify `delegation_audit.instruction_preview` preserves the target and success condition after
     redaction.
  4. When `expose_diagnostics=true`, verify `submitted_instruction` is present for explicit
     diagnostics; otherwise worker/run/project ids and full instruction remain hidden from routine
     user-facing output.
  5. Let the callback deliver the final result and verify it is self-contained enough to be useful
     without dumping raw worker logs.
- Expected result: the assistant writes its own acknowledgement, can self-check the delegated
  instruction, and receives a concise final callback.
- Forbidden result: the user sees a forced canned phrase; routine output exposes worker/run/project
  ids or raw instruction text; the final callback is only a naked list with no user-useful result or
  blocker.
- Evidence to capture: sanitized tool result keys, visible acknowledgement, callback text, log/state
  summary, and public-safety review.
- Automation: `viventium_v0_4/GlassHive/runtime_phase1/tests/test_mcp_server.py` plus browser
  callback QA when visible.
- Last run: PARTIAL (2026-05-18 MCP/runtime QA in
  `reports/2026-05-18-delegation-contract-runtime-qa.md`; browser callback run pending).

## `GHHOST-004` - Artifact Deliverable Scope

- Requirement: `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`.
- Risk covered: browser automation state or runtime scratch files are mistaken for worker output,
  causing empty/wrong `index.html` previews or exposing profile/cookie/upload metadata as artifacts.
- Preconditions: a synthetic worker workspace contains one legitimate user-facing artifact plus
  browser-profile scratch files, an extension `capture/index.html`, and projected upload metadata.
- Steps:
  1. Query the live payload and artifact list through the GlassHive API.
  2. Request open/download links for the legitimate artifact.
  3. Attempt to open/download the scratch/browser/upload paths directly.
  4. Repeat the artifact listing/signing path through the MCP artifact tools.
  5. Open the artifact preview in a real browser and confirm the visible page is the legitimate
     result rather than the extension capture shell.
- Expected result: legitimate `artifacts/`, `reports/`, `output/`, root, or generated app files can
  be delivered; top-level `tmp/`, `uploads/`, browser profile directories, extension internals, and
  cookie/login stores are not listed, promoted, signed, opened, or downloaded.
- Forbidden result: a URL like `tmp/chrome-user-data/.../Extensions/.../capture/index.html` appears
  as `deliverable.workspace_path`, in `workspace_artifacts`, or as an open/downloadable artifact.
- Evidence to capture: sanitized API/MCP results, real-browser preview result, targeted test output,
  and confirmation that no private paths or raw browser state were copied into public QA.
- Automation: `viventium_v0_4/GlassHive/runtime_phase1/tests/test_api.py` and
  `viventium_v0_4/GlassHive/runtime_phase1/tests/test_mcp_server.py`.
- Last run: PASS/PARTIAL 2026-06-22. Local deterministic browser QA and artifact regressions
  covered scratch exclusion, preview/download, and generated Markdown/CSV/HTML/PDF/XLSX/DOCX/PPTX
  files. Provider-backed live callback artifact flow remains a separate release gate.

## `GHHOST-005` - Native Worker Capability Preservation

- Requirement: `docs/requirements_and_learnings/01_Key_Principles.md`,
  `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`, and
  `docs/requirements_and_learnings/07_MCPs.md`.
- Risk covered: GlassHive projects a broker MCP by replacing the worker CLI's native config, launches
  Codex/Claude in a stripped mode, or disables browser/computer features in workstation mode.
- Preconditions: local Codex and/or Claude host CLIs are installed; use synthetic public-safe tasks
  and do not expose private account content in public evidence.
- Steps:
  1. Inspect the selected host CLI versions and capability surfaces (`codex mcp list`, Claude help /
     Chrome flag availability) using sanitized output.
  2. Launch or materialize a brokered host Codex worker and verify worker-local
     `$CODEX_HOME/config.toml` contains the scoped `glasshive-user-capabilities` broker plus
     allowlisted native MCP definitions, and excludes unrelated private MCPs/secrets.
  3. Verify workstation Codex launches do not pass blanket `--disable browser_use` or
     `--disable computer_use`, and do not ignore the worker-local Codex config unless explicitly
     configured.
  4. Verify Claude Code launch includes `--chrome` when supported in host and workstation modes,
     with an explicit opt-out only.
  5. Exercise a real user-level host/workstation prompt that could require browser/computer/file
     capabilities and verify the worker, logs, and visible result align.
- Expected result: broker projection is additive; selected workers retain native browser/computer,
  shell, file, MCP, and local app capabilities based on worker type while receiving scoped broker
  access.
- Forbidden result: worker-local Codex config contains only the broker block; workstation Codex
  disables native browser/computer by default; host Claude launches with Chrome integration off by
  default; tests accept a stripped worker as healthy.
- Evidence to capture: sanitized CLI capability probes, worker-local config summary, command argv
  summary without secrets, logs/DB run status, and visible user result or explicit blocker.
- Automation: `viventium_v0_4/GlassHive/runtime_phase1/tests/test_profile_runtime.py` plus a
  real user-path GlassHive host/workstation run when the active runtime has the change loaded.
- Last run: PASS/PARTIAL (2026-06-14 targeted source/runtime probes and unit tests; live
  post-change worker launch remains required after local runtime rebuild/restart).

## `GHHOST-006` - Workspace Image Extension And Skill Readiness

- Requirement: `docs/requirements_and_learnings/01_Key_Principles.md` and
  `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`.
- Risk covered: a fresh workspace image gives workers document tooling but omits the native
  browser-use extensions or hides skill/plugin capability awareness, leading to stripped workers for
  new users.
- Preconditions: Docker is available; the workstation image can be rebuilt or an already rebuilt
  image is present; use only synthetic public-safe browser/computer tasks.
- Steps:
  1. Inspect/generated-build the workstation Dockerfile and verify the default image tag is
     `workers-projects-runtime-workstation:phase1-node22-docs6`.
  2. Verify Codex and Claude Code package specs are pinned to dated, QA-checked stable versions, or
     that any override has matching version and capability evidence.
  3. Verify managed policy exists for both Chromium and Google Chrome locations and includes
     `fcoeoabgfenejglbffodgkkbkcdhcgfn;https://clients2.google.com/service/update2/crx` and
     `hehggadaopoacecdllhhajmbjkdcmajg;https://clients2.google.com/service/update2/crx`.
  4. Run `glasshive-browser-extension-check` inside the image/container. For full acceptance after
     launching the browser, rerun profile and native-host validation and record whether profile
     install is complete, native messaging is installed, or a vendor bundle is still pending.
  5. Open the workspace browser/desktop like a user and verify the browser-use extension bridge is
     connected or truthfully record the exact auth/bridge/provisioning blocker. Do not add user-facing
     warning UX to compensate for a substrate provisioning issue.
  6. Inspect generated worker `AGENTS.md`, host harness prompts, and Codex/Claude compatibility files
     to verify the native skill inventory is present and framed as optional capability selection.
  7. Verify workstation Codex compatible-provider launch does not disable `plugins`,
     `browser_use`, or `computer_use` by default; explicit lockdown through
     `WPR_CODEX_CLI_DISABLE_FEATURES` remains allowed and tested.
- Expected result: policy, profile, and bridge evidence agree that browser/computer capability is
  available when configured; worker prompt files include native skill awareness; no prompt-specific
  routing or forced skill usage is added.
- Forbidden result: extension IDs absent from the image, policy-only evidence claimed as full
  connected bridge proof, Codex plugin/native surfaces disabled by default, or a hardcoded prompt
  rule that forces a listed skill regardless of the user's request.
- Evidence to capture: generated Dockerfile summary, `glasshive-browser-extension-check` result,
  browser profile/bridge status, sanitized CLI version/capability probes, worker prompt snippets,
  targeted test output, and public-safety scan.
- Automation: `viventium_v0_4/GlassHive/runtime_phase1/tests/test_docker_sandbox.py`,
  `viventium_v0_4/GlassHive/runtime_phase1/tests/test_bootstrap.py`, and
  `viventium_v0_4/GlassHive/runtime_phase1/tests/test_profile_runtime.py`.
- Last run: PASS/PARTIAL 2026-06-23. `docs6` source, image, and managed-worker QA proved Codex
  CLI `0.142.0`, Claude Code `2.1.186`, both Chrome Web Store extension IDs `profile-installed`,
  Claude native-host manifest/wrapper installation, and an active `claude --chrome-native-host`
  process spawned by Chromium. Codex remains partial in Linux workstation mode until a real
  first-party Codex Chrome native-host bundle and reachable node-repl executable are provisioned
  through the documented worker-local config; the Codex popup visibly reproduced `Disconnected`
  without those prerequisites. See `reports/2026-06-23-workspace-native-browser-connectors.md`.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Glasshive Host Workers. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `GHHOST-UC-001` | On GlassHive MCP/API, host worker, browser/desktop/file surfaces, verify that host-native workers act on the intended local/browser/file surface and report completion without exposing plumbing. | owning requirement for `GHHOST-001` / `GHHOST-001` | GlassHive MCP/API, host worker, browser/desktop/file surfaces | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to GHHOST-001. | User-visible behavior matches source, docs, persisted state, and logs | PASS 2026-06-22 for local approval scope: host Codex/Claude wait/continue and provider-backed Codex/Claude browser wait/continue passed. |
| `GHHOST-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `GHHOST-002` / `GHHOST-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to GHHOST-002. | The user sees an honest setup, retry, or degraded-state result for GHHOST-002; no fake success is accepted. | PASS 2026-06-22: hardening report and public-safety scan passed. |
| `GHHOST-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `GHHOST-002` / `GHHOST-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to GHHOST-002. | GHHOST-002 remains correct after the persistence or parity step and final wording matches evidence. | PASS 2026-06-22: rerun after report/template update passed. |
| `GHHOST-UC-004` | Delegate a precise one-shot lookup/action and inspect the returned audit before the callback arrives. | `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md` / `GHHOST-003` | Web chat or MCP harness with `worker_delegate_once` | Tool result `acknowledgement_guidance`, sanitized `delegation_audit`, diagnostics-only `submitted_instruction`, callback final result, logs/state | Assistant writes its own short acknowledgement, does not quote a canned template, and the audit preserves the specific target/success condition enough to catch wrong-worker/wrong-scope dispatch. | PARTIAL (2026-05-18 MCP/runtime QA; browser callback run pending) |
| `GHHOST-UC-005` | Open a generated artifact after browser automation created local Chrome profile/capture files. | `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md` / `GHHOST-004` | GlassHive artifact API/MCP plus browser artifact preview | Live payload, artifact list, open/download status, MCP signed-link payload, browser preview, logs/events | The preview opens the legitimate worker deliverable; runtime/browser scratch paths are rejected and never surfaced as artifact links. | PASS/PARTIAL 2026-06-22: local browser fixture and artifact regressions passed; provider-backed callback artifact path pending. |
| `GHHOST-UC-006` | Ask a host/workstation worker to perform an open-ended task that may need browser/computer/file capabilities. | `docs/requirements_and_learnings/01_Key_Principles.md` / `GHHOST-005` | LibreChat/GlassHive MCP, host Codex/Claude or workstation Codex, logs, worker-local config | CLI capability probes, worker config, launch argv summary, run DB status, visible final result, public-safety scan. | The worker decides the path using native capability plus broker access; no launch-time stripping or raw plumbing appears as the user result. | PASS/PARTIAL (2026-06-14 source/runtime probes and targeted tests; live post-change worker launch pending) |
| `GHHOST-UC-007` | Start a fresh workstation worker image and verify Claude/Codex browser extensions plus skill awareness before a browser-capable task. | `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md` / `GHHOST-006` | Docker/workstation image, noVNC browser, worker prompt files, CLI capability probes | Dockerfile policy, extension-check output, browser profile install, bridge connection, AGENTS/CLAUDE/CODEX prompt files, targeted tests | New workspace workers have the expected native extension substrate and know their skill families, while choosing tools themselves based on the user request. | PASS/PARTIAL 2026-06-23: `docs6` image/worker/browser QA passed for profile install and Claude bridge; Codex bridge awaits first-party Linux native-host bundle plus node-repl provisioning. |
