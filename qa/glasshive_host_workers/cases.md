# GlassHive Host Workers QA Cases

Automated Codex app-server probe owner: `tests/release/test_glasshive_codex_app_server_probe.py`.

## Case ID Convention

Use stable `GHHOST-NNN` IDs for glasshive host workers cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `GHHOST-001` | Host-native workers act on the intended local/browser/file surface and report completion without exposing plumbing. | User-visible behavior matches source, docs, persisted state, and logs | GlassHive MCP/API, host worker, browser/desktop/file surfaces | `tests/release/test_stable_dev_runtime_workflows.py` plus user-grade QA when visible | PASS 2026-06-22 for local approval scope: host Codex xhigh and host Claude max wait/continue smokes passed with run/evidence markers; provider-backed Codex and Claude host browser wait/continue passed. |
| `GHHOST-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | PASS 2026-06-22 for `qa/glasshive_deep_research/reports/2026-06-22-production-hardening-local-qa.md` plus public QA contract/public-safety scan. |
| `GHHOST-003` | One-shot delegation preserves instruction precision without forced canned status | Assistant can self-check the delegated instruction and acknowledges in its own voice | MCP tool result, web chat, callback result | GlassHive `test_mcp_server.py` plus browser callback QA | PASS/PARTIAL 2026-06-25: live MCP one-shot delegation created a project/worker/run, preserved diagnostics, completed, and returned artifacts; browser chat callback run remains a separate gate. |
| `GHHOST-004` | Artifact discovery excludes runtime/browser scratch state and only promotes user-facing deliverables. | Users receive the actual worker output, not Chrome extension capture pages, browser profile data, uploaded-source metadata, or temporary scratch files. | GlassHive API/MCP artifacts, live payload, artifact open/download links, browser preview | GlassHive `test_api.py`, `test_mcp_server.py`, and real-browser artifact-open QA | PASS/PARTIAL 2026-06-25: provider-backed live worker produced, served, downloaded, and browser-previewed the expected Markdown artifact; callback artifact parity remains a separate gate. |
| `GHHOST-005` | Host and workstation workers preserve native CLI/browser/computer capability while adding broker MCP grants. | A user can ask unknown future work and the selected worker can decide using its full native capability surface plus brokered tools. | Host Codex/Claude launch, worker-local config, workspace Codex path, runtime preflight, logs | `test_profile_runtime.py`, real `codex mcp list` capability probe, Claude help/launch probe, worker config inspection | PASS/PARTIAL (2026-06-14 source/runtime probes and targeted tests; live post-change worker launch still required after runtime rebuild/restart) |
| `GHHOST-006` | Bootstrapped workspace images include AI-worker browser extensions, native messaging hosts, native skill awareness, and truthful workstation capability context without forcing workflows. | A new user's workspace worker starts with truthful browser/computer/document substrate awareness and diagnostic evidence without warning clutter. | Docker/workstation image, Chromium/Chrome profile, Codex/Claude worker prompts, worker logs | `test_docker_sandbox.py`, `test_profile_runtime.py`, `test_run_evidence.py`, `glasshive-browser-extension-check`, real local Docker smoke, real browser/Computer Use bridge QA | PASS/PARTIAL 2026-06-27: docs7 source/tests and local Docker smoke proved current image contract, worker capability guidance, active-run heartbeat, desktop-prime marker, and artifact/evidence pass; provider-backed browser bridge connectivity remains separate acceptance when configured. |
| `GHHOST-007` | Callback copy distinguishes a failed evidence gate with available artifacts from a total worker failure. | The user can tell whether a usable partial/delivered file exists and what still failed, without misleading success wording. | Telegram/web callbacks, callback outbox, artifact open/download links, run evidence | LibreChat `glasshive.spec.js`, GlassHive `test_api.py`, and real callback QA | PASS/PARTIAL 2026-06-25: automated coverage, live web callback/browser QA, and live Telegram/voice delivery-ledger claim/mark parity pass; real external Telegram send/audible voice delivery for this exact failed-evidence artifact case remains a side-effectful gate. |
| `GHHOST-008` | Codex effort values are clamped before launch when a host model supplies an unsupported per-run effort. | A bad `effort=minimal` from voice/chat cannot make the worker fail before it starts acting. | Voice/chat MCP launch, host Codex command, config compiler, run evidence | `tests/test_profile_runtime.py::test_codex_cli_provider_config_clamps_minimal_without_route_allowlist`; `tests/test_mcp_server.py::test_worker_tool_schemas_advertise_host_native_execution`; `tests/release/test_config_compiler.py::test_render_runtime_env_emits_glasshive_launch_env_only_when_enabled`; real local GlassHive launch QA | PASS 2026-06-25: automated tests, live marker smoke, live Yahoo Finance browser smoke, DB/log/evidence checks, and Playwright UI checks passed; see `reports/2026-06-25-codex-minimal-effort-clamp-qa.md`. Full doctor validation remains blocked by local disk-space prerequisite. |
| `GHHOST-009` | Browser/computer evidence, worker steering, and chat callbacks stay truthful after host-worker completion. | A successful browser task is not mislabeled as provider failure, blank steering fails before HTTP, own finished callbacks replace pending chat placeholders, and unrelated in-progress replies are not clobbered. | GlassHive run evidence, MCP `worker_message`, LibreChat callback receiver, real Chrome/LibreChat UI | `test_run_evidence.py`, `test_mcp_server.py`, LibreChat `glasshive.spec.js`, live MCP/callback/Chrome QA | PASS 2026-06-25: targeted and broader affected tests passed, live runtime rejected blank `worker_message`, synthetic signed callback updated its own unfinished placeholder, unrelated active placeholder returned retryable `425`, and real Chrome showed the completed callback without the placeholder. |
| `GHHOST-010` | Host workers can suppress selected plugins by canonical plugin ID without stripping unrelated capabilities, retaining a contaminated native session, or adding prompt policy. | Viventium workers do not load the conflicting Feelings plugin, while other plugins and global user plugin settings remain available; a policy change replaces the old native session only after terminating it and carries visible history forward. | Config compiler, worker-local Codex config, Claude launch settings, provider session binding, worker instruction | Compiler/wizard tests; `test_profile_runtime.py` denylist/fail-closed cases; `test_conversation_provider.py::test_native_policy_change_supersedes_contaminated_session_and_seeds_visible_history`; installed config/DB/browser QA | PASS 2026-08-02: compiled and installed runtime denies only `viventium-feelings@project-viventium`; live worker config proved that plugin disabled and unrelated plugins retained; provider, DB, log, and browser QA passed. See `reports/2026-08-02-codex-worker-native-policy-qa.md`. |
| `GHHOST-011` | Codex personality and mutable developer state preserve native roles without stale authority or needless native-session churn. | Viventium defaults to `none`; current authority is worker-local developer instruction; changed state serially replaces; unchanged or absent Phase-B state reuses; production stays on `codex exec`; App Server stays disabled because settings were stale and injection was append-only. | Config compiler, worker-local Codex config, provider session lifecycle, isolated App Server probe, installed UI/API/DB/log path | Compiler/runtime/provider tests, three-state App Server probe, four-turn installed API probe, real-browser Viventium prompt | PASS 2026-08-02: installed config/runtime, serial replacement, continuity, exact browser output, and latency evidence passed; App Server was explicitly rejected and remains off. |
| `GHHOST-012` | Dynamic application authority is pinned at the actual provider/native boundary and separately graded for causal effect. | Structural broker text precedes one exact declared tail; off has none; changed authority replaces safely; behavior is not accepted from markers or config alone. | LibreChat provider headers, GlassHive request hydration/session bundle, worker-local Codex config, exact-model contrast | LibreChat/GlassHive provider tests, release contract, installed DB/config correlation, four-way semantic contrast | PARTIAL 2026-08-02: transport/order passed; behavioral potency failed `1/4` and remains open. See `../emotional-cortex/reports/2026-08-02-glasshive-feeling-authority-and-contrast.md`. |
| `GHHOST-013` | Automatic conversation fallback preserves the logical agent's complete endpoint-owned capability bundle and safe diagnostics. | A real fallback keeps broker/tool capability, project instructions, visible history, and one current Feeling tail instead of becoming a stripped worker. | LibreChat primary/fallback materialization, signed capability headers, GlassHive request/run/worker state, safe logs | forced lazy and initialization fallback tests plus request/run/worker audit | PASS 2026-08-04: forced fallback tests passed in canonical and active components; request/run/worker evidence linked the historical failure to a missing fallback bundle, not provider misrouting or Feeling delivery. |
| `GHHOST-015` | Future capacity retries use one persisted, due-aware scheduler path with bounded threads and exact recovery. | Temporary host contention waits safely and resumes once without destabilizing the computer, duplicating work, or starving eligible workers. | GlassHive service scheduler, SQLite run queue, bounded executor, process/thread lifecycle | 12 focused `test_api.py` capacity/scheduler cases plus isolated 200-retry thread-count stress and post-fix full runtime QA | PARTIAL 2026-08-10: 12 focused tests, the 175-case API file, a 200-retry constant-thread stress, and the 791-case full runtime suite passed; installed/running capacity recovery remains pending. See `reports/2026-08-10-capacity-retry-scheduler-thread-safety.md`. |

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
- Last run: PASS/PARTIAL 2026-06-25. A live MCP one-shot delegation with synthetic public-safe
  content created a fresh project/worker/run, exposed diagnostics only when requested, completed
  successfully, and returned a user-facing artifact. Browser chat callback acceptance for this exact
  one-shot path remains open.

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
- Last run: PASS/PARTIAL 2026-06-25. Local deterministic browser QA and artifact regressions
  covered scratch exclusion, preview/download, and generated Markdown/CSV/HTML/PDF/XLSX/DOCX/PPTX
  files; a provider-backed live worker also produced and served the expected Markdown artifact via
  GlassHive artifact APIs, and real Playwright browser preview showed the expected file page and
  content. Callback artifact delivery remains a separate release gate.

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
     `workers-projects-runtime-workstation:phase1-node22-docs8-openclaw2026.7.1-5`, its base image
     matches the reviewed digest, and its provenance attests Ubuntu snapshot `20260801T000000Z`.
  2. Verify Codex and Claude Code package specs are pinned to dated, QA-checked stable versions, or
     that any override has matching version and capability evidence.
  3. Verify managed policy exists for both Chromium and Google Chrome locations. By default it must
     use an empty `ExtensionInstallForcelist`; when `GLASSHIVE_AI_WORKER_BROWSER_EXTENSIONS` or
     `WPR_AI_WORKER_BROWSER_EXTENSIONS` opts in to `claude`, `codex`, or `all`, verify the exact
     configured extension IDs and Chrome Web Store update URL are present.
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
- Last run: PASS/PARTIAL 2026-06-27. The docs7 source/tests and local Docker smoke proved the
  current image contract, worker capability guidance, active-run heartbeat, desktop-prime marker,
  artifact/evidence pass, and compute cleanup. The 2026-06-23 managed-worker QA remains the browser
  extension bridge reference: Claude native-host installation was proven, while Codex remains
  partial in Linux workstation mode until a real first-party Codex Chrome native-host bundle and
  reachable node-repl executable are provisioned through the documented worker-local config. See
  `reports/2026-06-23-workspace-native-browser-connectors.md` and
  `../glasshive_watch_desktop/reports/2026-06-27-docker-heartbeat-prime-local-qa.md`.

## `GHHOST-007` - Failed Evidence Gate With Deliverable Copy

- Requirement: `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`.
- Risk covered: a worker writes a useful artifact/report, the final evidence gate fails for a real
  constraint/completion reason, and the user sees only generic "I got stuck" wording that implies
  nothing was delivered.
- Preconditions: local GlassHive and LibreChat callback paths available; use synthetic public-safe
  artifacts and callback metadata.
- Steps:
  1. Force a run to fail with `glasshive_evidence_check_failed` while retaining a user-facing
     deliverable in the callback payload.
  2. Verify GlassHive keeps the run failed and includes `failure_code`, `failure_class`, retryability,
     and deliverable metadata in the signed callback payload.
  3. Verify LibreChat renders the callback as "worker output exists, final verification failed" rather
     than generic total failure or misleading success.
  4. Repeat a total/provider failure with a stray deliverable-shaped object and verify the copy remains
     generic failure wording.
  5. For release acceptance, rerun through web plus Telegram/voice callback parity with a provider-backed
     worker result and artifact links.
- Expected result: failed evidence-gate callbacks with deliverables stay failed but tell the user a
  usable output exists and what verification failed; total failures are not softened by incidental
  deliverable fields.
- Forbidden result: "I got stuck" for a real evidence-gate failure with available output; "completed"
  wording for a failed run; or total/provider failures presented as partial-delivery successes.
- Evidence to capture: targeted tests, signed callback payload summary, visible web/Telegram/voice
  wording, artifact-link presence, run evidence status, and public-safety review.
- Automation: `viventium_v0_4/GlassHive/runtime_phase1/tests/test_api.py` and
  `viventium_v0_4/LibreChat/api/server/routes/viventium/__tests__/glasshive.spec.js`.
- Last run: PASS/PARTIAL 2026-06-25. Deterministic GlassHive and LibreChat callback regressions
  passed, a live signed callback updated a synthetic web conversation placeholder with the
  partial-delivery wording visible in Chrome, and live Telegram/voice delivery-ledger claim/mark
  parity passed with the same wording. Real external Telegram send/audible voice delivery for this
  exact failed-evidence artifact case remains a side-effectful release gate. See
  `reports/2026-06-25-first-principles-path-coverage-audit.md`.

## `GHHOST-008` - Codex Effort Clamp And Provider Rejection Prevention

- Requirement: `docs/requirements_and_learnings/01_Key_Principles.md` and
  `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`.
- Risk covered: a host LLM sends `effort=minimal` for an ordinary GlassHive task, the active Codex
  provider route rejects that unsupported `reasoning.effort`, and the user sees a failed worker
  before the requested browser/computer/file action starts.
- Preconditions: local GlassHive runtime available; use a synthetic public-safe task. If the active
  route explicitly supports `minimal`, configure `WPR_CODEX_CLI_ALLOWED_REASONING_EFFORTS` to include
  it and record that proof; otherwise leave the default safe allowlist.
- Steps:
  1. Verify the MCP schema tells host models to omit ordinary per-run effort and says `minimal` is
     explicitly allowlisted only.
  2. Build a Codex launch command from a worker bootstrap containing
     `WPR_CODEX_CLI_REASONING_EFFORT=minimal` with no explicit route allowlist.
  3. Verify the command uses `model_reasoning_effort="medium"` and does not disable web search or
     image generation through the old `minimal` branch.
  4. Verify config compiler fields can render an explicit active-route allowlist and fallback into
     runtime env.
  5. Exercise the real local GlassHive surface after restart with a synthetic browser/computer task
     and verify the run no longer fails with unsupported `reasoning.effort`.
- Expected result: bad or stale host-model effort input is clamped to the configured fallback before
  launch; operator allowlists remain available for proven routes; callbacks are truthful and no raw
  provider JSON is needed for the ordinary user path.
- Forbidden result: `model_reasoning_effort="minimal"` reaches the active provider without an
  explicit allowlist, or the callback reports a provider-rejected worker for this preventable config
  mismatch.
- Evidence to capture: targeted pytest output, MCP schema assertion, compiled env snippet without
  secrets, GlassHive run state/evidence summary, browser-visible result or exact blocker, and public
  safety review.
- Automation: `viventium_v0_4/GlassHive/runtime_phase1/tests/test_profile_runtime.py`,
  `viventium_v0_4/GlassHive/runtime_phase1/tests/test_mcp_server.py`, and
  `tests/release/test_config_compiler.py`.
- Last run: PASS 2026-06-25. Automated regressions passed, two live workers with requested
  `minimal` clamped to `medium`, the Yahoo Finance browser smoke completed, Chrome state confirmed
  the active Yahoo Finance tab, DB/log/evidence checks agreed, and Playwright UI checks showed the
  completed result. See `reports/2026-06-25-codex-minimal-effort-clamp-qa.md`. Full doctor
  validation remains blocked by local disk-space prerequisite.

## `GHHOST-009` - Evidence Status Codes, Steering Validation, And Callback Placeholder Resolution

- Requirement: `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`.
- Risk covered: browser accessibility node ids are mistaken for provider status codes, host models send
  steering without a worker id and create a downstream 404, terminal callbacks save under their own
  unfinished chat placeholder and leave the user seeing a spinner, or terminal callbacks overwrite an
  unrelated in-progress assistant reply.
- Preconditions: local GlassHive and LibreChat runtime available; use only synthetic public-safe callback
  data for live persistence/visual checks.
- Steps:
  1. Build run evidence from a successful browser/computer transcript containing accessibility labels such
     as `401 menu item` or `403 close button`.
  2. Call `worker_message` with a blank worker id through MCP.
  3. Post a signed terminal callback for a synthetic conversation whose active leaf is an unfinished
     `Generation in progress.` assistant placeholder.
  4. Post a signed terminal callback while an unrelated `Generation in progress.` assistant placeholder is
     active and verify the receiver returns retryable `425` without overwriting it.
  5. Open the synthetic conversation in the real browser and verify the final callback text replaced the
     intended placeholder, then remove the synthetic rows.
- Expected result: evidence status is pass/unknown rather than provider auth failure; MCP rejects the
  blank worker id before HTTP; callback persistence updates its own placeholder with `unfinished=false`,
  unrelated active placeholders are left intact and retried with `425`, and the visible UI shows the
  completed message without a spinner.
- Forbidden result: `provider_auth_missing` from browser node numbers; `/workers//message` in runtime logs;
  completed callback saved as a child under its own unfinished placeholder; unrelated in-progress response
  overwritten by a background callback.
- Evidence to capture: targeted tests, live MCP validation result, live callback DB fields, visible browser
  result, cleanup confirmation, and sanitized log/DB summary.
- Automation: `viventium_v0_4/GlassHive/runtime_phase1/tests/test_run_evidence.py`,
  `viventium_v0_4/GlassHive/runtime_phase1/tests/test_mcp_server.py`, and
  `viventium_v0_4/LibreChat/api/server/routes/viventium/__tests__/glasshive.spec.js`.
- Last run: PASS 2026-06-25. Targeted tests include own-placeholder update, unrelated-placeholder
  no-clobber, and placeholder-text coupling guard; restarted live runtime returned retryable `425` for a
  synthetic unrelated active placeholder without updating or saving callback rows. See
  `reports/2026-06-25-callback-placeholder-and-evidence-status-qa.md` and
  `reports/2026-06-25-first-principles-path-coverage-audit.md`.

## `GHHOST-010` - Worker Plugin Denylist

- Requirement: `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`.
- Risk covered: a Viventium worker loads a plugin that conflicts with Viventium-owned behavior, or
  suppression accidentally disables every plugin, mutates global user config, or crowds the prompt.
- Preconditions: a config containing canonical plugin IDs and synthetic source Codex config with one
  denied and one allowed plugin.
- Steps:
  1. Compile the host-worker config and inspect the generated denylist environment value.
  2. Materialize both Codex and Claude host workers.
  3. Inspect worker-local Codex TOML and Claude `--settings` JSON.
  4. Inspect the worker instruction and the original source plugin config.
  5. Start a session with the plugin available, disable it in worker-local native config, and prove
     that the contaminated session still retains stale capability context.
  6. Change the generic native-policy fingerprint and verify the old worker terminates before one
     replacement session starts with complete visible history.
- Expected result: only configured exact IDs are disabled in the selected worker; unlisted plugins and
  source/global config remain unchanged; no plugin-policy text appears in the instruction; and a
  previously contaminated native session cannot survive the policy boundary.
- Forbidden result: runtime branches on a specific plugin name, all plugins disabled, source/global
  config edited, denylist text added to the model prompt, two concurrent authoring sessions, or a
  resumed session that still exposes the denied plugin.
- Evidence to capture: compiler output, worker-local native config, command settings, instruction text,
  focused tests, and public-safety scan.
- Automation: `tests/release/test_config_compiler.py`, `tests/release/test_wizard.py`, and
  `viventium_v0_4/GlassHive/runtime_phase1/tests/test_profile_runtime.py`.
- Last run: PASS 2026-08-02. The escaped contaminated-session case reproduced in an isolated native
  thread; automated policy-fingerprint supersession and fail-closed worker config passed. The
  surgical change was compiled into the active installed runtime, restarted, and verified through
  generated config, worker-local config, DB/session lifecycle, runtime logs, API turns, and a real
  Viventium browser turn. See
  `reports/2026-08-02-codex-worker-native-policy-qa.md`.

## `GHHOST-011` - Codex Personality And App Server QA Gate

- Requirement: `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`.
- Risk covered: a worker-specific personality silently replaces Viventium Feelings, `none` is used
  without support evidence, or App Server metadata changes while the model still receives stale
  developer instructions.
- Steps:
  1. Compile `codex_personality` for every supported value and reject all others.
  2. Prove Viventium defaults to worker-local `none`, while standalone GlassHive still inherits when
     Viventium does not compile the setting.
  3. Keep the App Server probe disabled by default.
  4. Run changing synthetic developer settings on one App Server thread using the documented
     per-turn collaboration-mode developer field; separately cover process restart/resume; reject
     the transport if the first state remains model-visible or the second state is ignored.
  5. Confirm developer-role `thread/inject_items` is append-only diagnostic evidence, not a
     current-only replacement mechanism.
  6. On production `codex exec`, prove present changed authority serially replaces the worker;
     present unchanged and absent Phase-B authority reuse it; higher-authority content is absent from
     the user instruction.
  7. Verify the installed runtime through generated config, worker config, API/UI output, DB/log
     lifecycle, and native/provider latency.
- Expected result: Viventium removes Codex's competing personality instructions by default without
  removing capabilities; current state uses native developer authority; changed state replaces one
  session serially; unchanged and Phase-B state reuse it; production uses `codex exec`; App Server
  remains off until a bounded replacement mechanism and full lifecycle both pass.
- Forbidden result: forcing the Viventium default on standalone GlassHive, adding personality/Feeling
  policy to user text, switching production transport, or accepting settings metadata without
  model-visible proof, or treating a two-turn append-only injection probe as long-session approval.
- Automation: `tests/release/test_config_compiler.py`,
  `tests/release/test_glasshive_codex_app_server_probe.py`, and GlassHive
  `runtime_phase1/tests/test_profile_runtime.py`.
- Last run: PASS 2026-08-02. Canonical config compiled to `none`; standalone inheritance and explicit
  alternatives passed. App Server settings failed a three-state same-thread/reconnect probe and
  append-only injection was rejected. Installed production `codex exec` passed changed/unchanged/
  Phase-B lifecycle checks plus the real browser path.

## `GHHOST-013` - Complete Capability Bundle On Fallback

- Requirement: `docs/requirements_and_learnings/51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md`.
- Risk covered: the primary worker fails before visible text, the configured fallback really runs,
  but its lazily materialized config omits the signed broker and project capability bundle.
- Steps:
  1. Force both initialization-time and lazy fallback from a declared primary to a declared fallback.
  2. Resolve capability ownership from the fallback endpoint and use the shared signed attachment path.
  3. Verify `agents_md`, `claude_md`, `codex_md`, broker capabilities, visible history, and one exact
     current Feeling tail reach the fallback worker.
  4. Join request to run to worker; do not infer historical routing from the mutable current-session row.
  5. Verify the primary throw logs exactly one sanitized class/status/code/chain-depth/message-hash
     record and never raw messages, stacks, tokens, or secrets.
- Expected result: fallback is the same complete logical agent on its declared endpoint; the next
  eligible turn can return to primary without duplicated authority or lost history.
- Forbidden result: copying arbitrary primary headers, a stripped fallback bundle, duplicate Feeling,
  provider-route claims based only on mutable session state, or secret-bearing error logs.
- Last run: PASS 2026-08-04. Forced provider and fallback tests passed in both checkouts; historical
  request/run/worker joins proved the fallback actually used its declared route; one Feeling tail was
  already correct; the missing capability bundle and missing safe primary diagnostic were fixed.

## `GHHOST-014` - Compact Signed Host-Tool Grant

- Requirement: `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`.
- Risk covered: the broker serializes full conversation resources into an authorization header,
  causing HTTP 431 before a worker can discover host tools; removing native worker tools to force an
  eval pass would then regress legitimate workstation tasks.
- Steps:
  1. Initialize a provider request with a large synthetic resource bundle.
  2. Sign only a bounded digest reference and retain the exact validated resource scope server-side.
  3. Rehydrate and revalidate the scope at broker initialization, failing closed on mismatch or
     expiry.
  4. Run a real provider-backed recall turn and audit broker plus native-tool provenance.
- Expected result: the signed grant remains below the conservative 4 KiB header budget, the worker
  discovers `file_search`, and declared native capabilities remain available for tasks that need
  them.
- Forbidden result: transcript content in the bearer token, unbounded cache growth, unverified
  rehydration, universal native-tool stripping, or a tool catalog without a completed call.
- Last run: PASS-AUTOMATED/LIVE 2026-08-08. A representative grant fell from 20,411 to 942
  characters; 46 broker/provider/route tests passed and a live worker completed brokered
  `file_search` with zero native command executions.

## `GHHOST-015` - Bounded Capacity-Retry Scheduler

- Requirement: `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`.
- Risk covered: a future capacity retry is correctly left unclaimed, but a due-unaware processor
  finalizer immediately resubmits it and allocates another process-local timer. A few queued runs can
  then create thousands of threads and destabilize the host before their deadlines arrive.
- Preconditions: use an isolated GlassHive service and synthetic workers/runs. Configure the runtime
  to report retryable capacity contention, persist future `retry_after` values, record baseline and
  peak service thread counts, and keep private machine diagnostics outside the public report.
- Steps:
  1. Queue future capacity retries and verify a worker processor returns without immediate
     resubmission, native execution, or any per-run timer/thread creation.
  2. Persist at least several hundred future retries across multiple workers, run repeated scheduler
     cycles before their deadlines, and verify there is one scheduler thread and a bounded service
     thread footprint independent of queued-run count.
  3. Release capacity or advance the deadlines. Verify each eligible worker is submitted at most
     once per scheduler cycle and each run is claimed/executed exactly once, with one terminal result
     and no duplicate `run.started`/terminal event pair.
  4. Persist a future retry, stop the service, reopen the same SQLite state, and verify it remains
     dormant before its deadline and recovers exactly once afterward.
  5. Put due runs on paused, terminated, and ready workers with a tight discovery limit. Verify the
     ineligible rows are excluded before the limit and cannot starve ready work.
  6. Begin shutdown during scheduler work and while it is waiting. Verify no new retry dispatch
     begins, the wake exits promptly, and the scheduler thread terminates.
  7. Independently inject a scheduled-run phase error, retry-discovery error, and next-deadline lookup
     error. Verify sanitized errors are observable, unaffected phases still run, and the scheduler
     falls back to its normal interval instead of dying or spinning.
- Expected result: SQLite `retry_after` is the sole retry clock; one shared due-aware scheduler wakes
  the bounded executor; immediate continuation occurs only for due work; every eligible run recovers
  once across normal operation and restart; service thread count stays bounded under hundreds of
  future retries.
- Forbidden result: `threading.Timer` or any per-run retry thread; immediate self-resubmission for a
  future row; thousands of threads from a small queue; duplicate native execution; paused/terminated
  starvation; dispatch after shutdown; or one scheduler phase failure silently disabling another.
- Evidence to capture: sanitized focused/full-suite results, source assertion that no per-retry timer
  path exists, SQLite run/event counts before and after due time and restart, scheduler error logs,
  baseline/peak thread counts, and confirmation that the tested runtime artifact contains the fix.
- Automation: `runtime_phase1/tests/test_api.py` cases
  `test_retryable_host_busy_waits_and_retries_without_terminal_failure`,
  `test_future_capacity_retry_does_not_resubmit_processor_or_create_timer`,
  `test_single_scheduler_wakes_each_due_retry_worker_once`,
  `test_persisted_future_retry_wakes_after_service_restart`,
  `test_hundreds_of_future_capacity_retries_do_not_create_retry_threads`,
  `test_retry_scheduler_boundary_rechecks_immediately_when_deadline_just_crossed`,
  `test_retry_scheduler_excludes_paused_and_terminated_workers_before_limit`,
  `test_retry_scheduler_does_not_dispatch_after_shutdown_begins`,
  `test_scheduler_cycle_contains_one_phase_failure_and_runs_the_other`,
  `test_scheduler_wait_lookup_failure_uses_interval_and_stays_observable`,
  `test_shutdown_during_scheduler_cycle_terminates_scheduler_thread`, and
  `test_retryable_capacity_wait_has_max_attempts`.
- Last run: PARTIAL 2026-08-10. All 12 focused automated cases passed. The complete 175-case
  `test_api.py` file passed; a synthetic 200-retry backlog kept thread count constant; and the
  post-fix 791-case runtime suite passed with five expected skips. Installed/running artifact
  identity plus a controlled real capacity-wait/recovery remain pending; automated success is not
  yet a runtime-completion claim. See
  `reports/2026-08-10-capacity-retry-scheduler-thread-safety.md`.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Glasshive Host Workers. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `GHHOST-UC-001` | On GlassHive MCP/API, host worker, browser/desktop/file surfaces, verify that host-native workers act on the intended local/browser/file surface and report completion without exposing plumbing. | owning requirement for `GHHOST-001` / `GHHOST-001` | GlassHive MCP/API, host worker, browser/desktop/file surfaces | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to GHHOST-001. | User-visible behavior matches source, docs, persisted state, and logs | PASS 2026-06-22 for local approval scope: host Codex/Claude wait/continue and provider-backed Codex/Claude browser wait/continue passed. |
| `GHHOST-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `GHHOST-002` / `GHHOST-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to GHHOST-002. | The user sees an honest setup, retry, or degraded-state result for GHHOST-002; no fake success is accepted. | PASS 2026-06-22: hardening report and public-safety scan passed. |
| `GHHOST-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `GHHOST-002` / `GHHOST-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to GHHOST-002. | GHHOST-002 remains correct after the persistence or parity step and final wording matches evidence. | PASS 2026-06-22: rerun after report/template update passed. |
| `GHHOST-UC-004` | Delegate a precise one-shot lookup/action and inspect the returned audit before the callback arrives. | `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md` / `GHHOST-003` | Web chat or MCP harness with `worker_delegate_once` | Tool result `acknowledgement_guidance`, sanitized `delegation_audit`, diagnostics-only `submitted_instruction`, callback final result, logs/state | Assistant writes its own short acknowledgement, does not quote a canned template, and the audit preserves the specific target/success condition enough to catch wrong-worker/wrong-scope dispatch. | PASS/PARTIAL 2026-06-25: live MCP one-shot delegation and artifact result passed; browser chat callback run pending. |
| `GHHOST-UC-005` | Open a generated artifact after browser automation created local Chrome profile/capture files. | `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md` / `GHHOST-004` | GlassHive artifact API/MCP plus browser artifact preview | Live payload, artifact list, open/download status, MCP signed-link payload, browser preview, logs/events | The preview opens the legitimate worker deliverable; runtime/browser scratch paths are rejected and never surfaced as artifact links. | PASS/PARTIAL 2026-06-25: local browser fixture/artifact regressions plus provider-backed live Markdown artifact download and Playwright browser preview passed; callback artifact path pending. |
| `GHHOST-UC-006` | Ask a host/workstation worker to perform an open-ended task that may need browser/computer/file capabilities. | `docs/requirements_and_learnings/01_Key_Principles.md` / `GHHOST-005` | LibreChat/GlassHive MCP, host Codex/Claude or workstation Codex, logs, worker-local config | CLI capability probes, worker config, launch argv summary, run DB status, visible final result, public-safety scan. | The worker decides the path using native capability plus broker access; no launch-time stripping or raw plumbing appears as the user result. | PASS/PARTIAL (2026-06-14 source/runtime probes and targeted tests; live post-change worker launch pending) |
| `GHHOST-UC-007` | Start a fresh workstation worker image and verify Claude/Codex browser extensions plus skill awareness before a browser-capable task. | `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md` / `GHHOST-006` | Docker/workstation image, noVNC browser, worker prompt files, CLI capability probes | Dockerfile policy, extension-check output, browser profile install, bridge connection, AGENTS/CLAUDE/CODEX prompt files, targeted tests | New workspace workers have the expected native extension substrate and know their skill families, while choosing tools themselves based on the user request. | PASS/PARTIAL 2026-06-23: `docs6` image/worker/browser QA passed for profile install and Claude bridge; Codex bridge awaits first-party Linux native-host bundle plus node-repl provisioning. |
| `GHHOST-UC-007B` | Receive a callback where the worker produced an artifact/report but final evidence verification failed. | `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md` / `GHHOST-007` | LibreChat web callback route, Telegram/voice callback parity path, GlassHive run evidence/outbox | Callback payload failure metadata, visible callback text, artifact refs, run status, targeted tests, public-safety scan | The user sees that output exists and final verification failed, while the run remains failed and total failures still use clear failure wording. | PASS/PARTIAL 2026-06-25: deterministic tests, live Chrome web callback, and Telegram/voice delivery-ledger parity passed; real external Telegram send/audible voice delivery for the exact case remains a side-effectful gate. |
| `GHHOST-UC-008` | From chat or voice, ask GlassHive to open a public website through a host Codex worker after a host model supplies or could supply a low-effort override. | `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md` / `GHHOST-008` | LibreChat/voice MCP launch, host Codex command/evidence, GlassHive API, browser/computer surface | MCP schema, generated runtime env, command evidence, run DB/state, callback text, visible browser result or exact blocker | The worker starts with a supported effort value, uses the configured fallback when needed, and does not fail before action due to unsupported `reasoning.effort`. | PASS 2026-06-25: live host Codex worker opened Yahoo Finance in Chrome while requested `minimal` clamped to `medium`; Playwright UI and Chrome state verified completion. |
| `GHHOST-UC-009` | Let a host-worker callback arrive after the chat has an unfinished assistant placeholder, and try steering without a known worker id. | `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md` / `GHHOST-009` | LibreChat web callback route, real Chrome conversation view, GlassHive MCP, run evidence | Targeted tests, live callback DB fields, live MCP validation result, visible browser state, cleanup result, sanitized logs | The final callback replaces its own pending placeholder with `unfinished=false`, unrelated active placeholders are retried instead of overwritten, blank steering is rejected before HTTP, and browser node ids do not become provider failures. | PASS 2026-06-25: synthetic live callback and real Chrome QA passed; blank worker id rejected by live MCP; unrelated active placeholder returned live `425`; affected automated suites passed. |
| `GHHOST-UC-010` | Start or resume a Viventium host worker while one installed plugin is denied by exact ID. | `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md` / `GHHOST-010` | Generated runtime env, host Codex/Claude launch config, provider session binding, worker instruction | Compiler output, worker-local TOML, Claude settings JSON, session/worker state, source config, targeted tests, real browser path | The denied plugin is unavailable only inside that worker; contaminated sessions are superseded serially with visible history preserved; other plugins stay available and no suppression policy consumes prompt context. | PASS 2026-08-02: source, installed config/runtime, API, DB/log, and browser QA passed. |
| `GHHOST-UC-011` | Use Viventium's Feeling-owned Codex default across changed, unchanged, and Phase-B state; compare App Server without switching production. | `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md` / `GHHOST-011` | Generated env, worker-local TOML, provider lifecycle, App Server QA, Viventium UI | Compiler/runtime/provider tests, state hashes, worker IDs, outputs, terminal events, latency | Viventium defaults to `none`; current state remains native developer authority; only changed authority pays serial replacement; App Server fails closed while stale/append-only. | PASS 2026-08-02: installed production path passed and App Server was rejected/off. |
| `GHHOST-UC-012` | Send the same ordinary prompt with Feelings off and three contrasting enabled states through the real GlassHive-backed Main. | `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md` / `GHHOST-012` | Authenticated local chat API, GlassHive provider, Codex worker config, semantic judge | Exact restored fixtures, native suffix/count/order, outputs, semantic scores, request latency, cleanup | Correct native authority and materially different state-shaped choices both pass; no base replacement or prompt-specific branch | PARTIAL 2026-08-02: placement passed; semantic potency failed `1/4`. |
| `GHHOST-UC-013` | Let a primary model fail before visible text and inspect the configured fallback result. | `docs/requirements_and_learnings/51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md` / `GHHOST-013` | authenticated chat, LibreChat fallback, GlassHive request/run/worker audit | forced tests, signed bundle keys, history, Feeling count, sanitized primary diagnostic | The fallback remains a complete Viventium agent and its real declared route is auditable without exposing the error. | PASS 2026-08-04: forced tests and request/run/worker forensic audit passed. |
| `GHHOST-UC-015` | Let many host-capacity waits remain queued, restart the service, then release capacity. | `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md` / `GHHOST-015` | isolated GlassHive API/service, SQLite state, worker callbacks/status, OS thread monitor | due/future run counts, run/event uniqueness, scheduler logs, service thread baseline/peak, source and active artifact identity | The service stays responsive with one shared scheduler; future work sleeps, persists, and each eligible run resumes once when due. | PARTIAL 2026-08-10: 12 focused cases, 200-retry bounded-thread stress, the 175-case API file, and the 791-case runtime suite passed; installed real capacity recovery remains. |
