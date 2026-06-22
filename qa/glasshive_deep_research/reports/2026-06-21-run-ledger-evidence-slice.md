# GlassHive Deep Research QA Run Ledger - 2026-06-21 to 2026-06-22

## Summary

- Result: PARTIAL.
- Build/source under test: local GlassHive runtime source checkout.
- Runtime/artifact under test: constraint ledger, evidence JSON and `evidence_result` gating, completion compliance, host dependency projection, route-proven effort handling, document validation, advisory content hygiene, backend/profile truth, long-run heartbeat, browser-visible artifact preview, short-ref workspace navigation, and private long-form benchmark reruns.
- Environment: local development checkout.
- Tester: Codex.
- Acceptance status: local automated, fixture-browser, host Codex wait/continue, and host Claude wait/continue evidence passed for the covered scope; release-complete signoff still has Docker Claude, private rerun, and browser-UI long-run gates. Host/local automated and browser evidence passed, both host Codex and host Claude completed earlier private long-form benchmark reruns, the current default Docker workstation image passed a smoke after pruning unused Docker build cache, and prior ClaudeViv review-only passes completed. Post-continuation work added blocking `evidence_result` surfacing, xhigh route-proof/clamp telemetry, Docker Claude max preflight, bootstrap empty-file rejection, and a public-safe local browser fixture that caught and fixed a stale `/watch` workspace-link route. The second ClaudeViv pass validated the main direction and identified a medium false-positive risk in host evidence gating; post-review fixes now prevent attached/input formats and explicitly forbidden formats from becoming required outputs, and prevent ordinary future-date prose from being treated as source-window drift. A follow-up privacy pass moved artifact-returned View workspace links to clean `/w/{ref}` workspace pages and hashed runtime worker-view cookie names. A later Docker model probe found and fixed a Docker Codex effort projection bug; Docker Codex xhigh now completes with command/evidence proof, while Docker Claude Opus 4.8 max honestly reports `provider_auth_missing` because the containerized Claude CLI is not logged in. A later ClaudeViv review found additional hardening gaps; post-review fixes now redact sensitive query fields even when they appear at the start of a log value, stop legacy worker console/view/terminal HTML from reflecting signed query strings into links or JavaScript, hash Glass Drive UI worker-view cookie names, avoid `VaR estimate = ...` JavaScript false positives, and preserve required formats after parenthetical forbidden formats such as `no PDF`. Follow-up Claude auth work added the documented `CLAUDE_CODE_OAUTH_TOKEN` headless-token path to bootstrap/env/runtime projection while keeping it secret/run-only in enterprise. A redirect-safety pass now rejects unconfigured absolute `/r/{ref}` targets while allowing configured operator/runtime/artifact origins, rejects browser-normalized relative bypasses such as leading `//` and backslash paths, and a fresh Playwright fixture proved tokenless artifact preview -> `/w/{ref}` workspace navigation after that change. Corrected real host-Codex and host-Claude API wait/continue smokes passed with `running -> completed` state evidence for both initial runs and continuations. The earlier host-Claude max provider overload is now both classified as retryable `provider_response_failed` and followed by a successful retry. Public-safe generic fixture benchmarks pass, named degraded-path slices pass, and clean parent/nested branches are committed and pushed. Provider-backed browser wait/continue in the visible UI path, live Docker Claude completion with a real headless token, and post-contract rerun of the private source-window failure remain before release-complete signoff.

## Scope Run

## 2026-06-22 Continuation Evidence

- Nested component boundary: GlassHive was committed at
  `bf3af68c661ea755973d502c90b6f3f602563a2d`; the clean parent branch pins that exact ref, and
  both nested and parent branches were pushed to review branches. The original working tree still
  contains unrelated non-GlassHive component pin changes, so the releaseable parent commit was made
  from a clean worktree.
- Harness repair: the live wait/continue smoke now uses a unique public-safe worker/workspace suffix
  and requires the first-run artifact marker, preventing stale workspace artifacts from faking a
  pass.
- Codex host xhigh: corrected public-safe wait/continue smoke passed. The initial run and
  continuation both observed `running -> completed`; the first artifact marker and continuation
  marker were present in the same artifact; evidence status was `pass`. The route did not silently
  claim unsupported xhigh: it emitted visible fallback telemetry when the provider route lacked
  xhigh proof.
- Claude host max: the first public-safe wait/continue smoke exposed a provider overload path:
  structured `api_error_status=529` was previously classified as `unknown`. The classifier now maps
  structured overload/service-unavailable evidence to retryable `provider_response_failed`, and a
  negative regression prevents ordinary unstructured prose containing `overloaded` from being
  misclassified. A subsequent host Claude max retry passed: initial run and continuation both
  observed `running -> completed`, both artifact markers were present, and evidence status was
  `pass`.
- Degraded-path slice: named tests passed for timeout evidence, interrupt/cancel/steer, max-run
  cancellation, quota/concurrency, enterprise auth gates, `X-GlassHive-*` identity headers,
  wait/status timeout, workspace continuation, stale profile/runtime refresh, scratch artifact
  rejection, short-ref auth/cookie behavior, and signed-query log redaction.
- Browser user path: Playwright opened the local project, opened the text artifact preview, clicked
  `View workspace`, landed on `/w/{ref}`, refreshed the page, verified the iframe still rendered the
  public marker, and confirmed the top-level visible text and links had no signed-query fields or
  raw worker ids. Console warnings/errors were zero.
- Suites rerun after the continuation fixes: full runtime tests passed, full Glass Drive UI tests
  passed, public-safe benchmark suite passed seven of seven cases, component pin/bootstrap tests
  passed, parent QA operating-contract/public-safety tests passed, and the targeted classifier
  regression passed.

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `GHDR-001` | PARTIAL | `tests/test_run_evidence.py`, private host Codex and host Claude benchmark evidence, ClaudeViv review-only passes | Ledger extraction/compliance is covered by automated tests. The Codex rerun preserved constraints. The Claude rerun produced valid deliverables but used out-of-window supporting evidence in notes/structured fields; this was detected by the verifier, and the worker contract was tightened generically to treat excluded sources as rejected evidence only. ClaudeViv caught the verifier/prompt seam; rejected/out-of-scope evidence is now allowed while merely flagged out-of-window evidence still fails. A later ClaudeViv pass also caught a date-window false-positive class; tests now prove future subject dates are allowed when sources remain in-window. A post-contract rerun is pending. |
| `GHDR-002` | PASS | `tests/test_run_evidence.py`, `tests/test_profile_runtime.py`, full runtime suite, local browser fixture, real Codex xhigh capability probe, private benchmark evidence JSON, ClaudeViv review | Evidence inventories recursive deliverables, validates professional artifacts where libraries are present, flags notes-only missing deliverables, detects `FINAL REPORT:` for Codex and Claude result JSON, records completion compliance, and now produces a blocking `evidence_result` for missing final reports, constraint failures, completion failures, and invalid professional artifacts. Post-review regressions prove attached/input formats are not treated as required outputs, explicitly forbidden formats are subtracted, and parenthetical `no PDF` does not hide a later required CSV. Artifact-returned workspace controls now use clean `/w/{ref}` links instead of raw worker/project route ids. |
| `GHDR-003` | PASS | `tests/test_run_evidence.py`, public-safe fixture benchmarks, compact real host Codex/Claude evidence, private benchmark evidence | Hygiene fixtures cover crawl/nav/script/paywall contamination, lowercase JavaScript `var`, `VAR`/`VaR` false-positive protection including `VaR estimate = ...`, JSON leaves, CSV cells, negative self-check wording, and long prose false-positive protection. Hygiene remains advisory; real compact host runs exposed and fixed false positives for negative “exclude/no cookie/script/navigation” wording and large clean CSV files. |
| `GHDR-004` | PARTIAL | `tests/test_profile_runtime.py`, MCP wait/status tests, active-run heartbeat from real long Codex/Claude benchmark runs, `live_provider_wait_continue_smoke.py`, local `/w/{ref}` browser action QA | Host timeout/interrupt regressions pass; both private long runs recorded active `running` heartbeats with timeout policy and transcript paths. API/MCP wait/status/continue degraded regressions pass, and a real host-Codex API wait/continue smoke observed `running -> completed` for the first run and continuation, with the continuation marker added to the same artifact. Fresh Playwright local `/w/{ref}` browser controls proved pause, resume, interrupt, terminate, refresh persistence, invalid-ref rejection, and matching events/state with no positive-path console/request failures. Full long-running browser wait/continue on a real provider-backed run remains pending. |
| `GHDR-005` | PARTIAL | `tests/test_profile_runtime.py`, `tests/test_bootstrap.py`, real Codex xhigh probe, compact real host Codex/Claude benchmarks, host Codex/Claude wait/continue smokes, private host Codex xhigh and Claude Opus 4.8 max benchmark evidence, Docker workstation smoke, live Docker model probes | Host Codex projected xhigh into the actual command when route proof was present. Without route proof or explicit allowlist, requested xhigh now clamps to fallback with visible telemetry. Compact public-safe real host Codex xhigh passed with `effort=xhigh`; compact public-safe real host Claude Opus 4.8 max passed with `model=claude-opus-4-8` and `effort=max`. Corrected host Codex xhigh and host Claude max wait/continue smokes both passed with `running -> completed` first/continuation states and marker checks. Docker/workspace Claude max now preflights `--effort` support before launch. A real Docker Codex xhigh probe completed a public-safe artifact task with evidence `pass`; an initial run exposed that Docker Codex dropped effort outside the custom-provider path, and the fix now proves `model_reasoning_effort="xhigh"` in command/evidence. Docker Claude Opus 4.8 max proves `--effort max` projection but is blocked by absent containerized Claude credentials and now classifies the run as `provider_auth_missing`. The runtime now supports `CLAUDE_CODE_OAUTH_TOKEN` projection for the documented headless-token path; this shell did not have that token, so live Docker Claude completion remains blocked on an external credential prerequisite. |
| `GHDR-005A` | PASS | `tests/test_run_evidence.py`, API/MCP tests, Playwright UI smoke, private benchmark evidence | Evidence and UI derive backend truth from `profile + execution_mode`; Codex/Claude workers no longer present legacy OpenClaw as the meaningful backend truth. |
| `GHDR-006` | PASS for local fixture scope | Real Playwright artifact-preview smoke; public-safe local browser fixture; evidence library validation tests; private benchmark artifact inspection; Docker workstation smoke | The fixture produced Markdown, CSV, HTML, PDF, XLSX, DOCX, and PPTX artifacts plus deliberate scratch files. Fresh Playwright proved project/worker pages, text artifact preview, short-ref download, clean `/w/{ref}` View workspace navigation, iframe render, refresh persistence, pause/resume/interrupt/terminate actions, invalid-ref rejection, and no raw token leakage or positive-path console/request failures for the fixture. Follow-up tests prove signed query fields are redacted at string start, legacy worker console/view/terminal pages no longer reflect signed query strings into rendered links or JavaScript, runtime plus Glass Drive UI worker-view cookie names are hash-derived rather than raw worker-id-derived, and unconfigured absolute `/r/{ref}` redirect targets are rejected. Direct downloads structurally validated all seven file types with PDF header/EOF, CSV rows, HTML marker, `openpyxl`, `python-docx`, and `python-pptx`. Codex private benchmark produced valid PDF/XLSX/HTML/screenshot artifacts. Claude private benchmark produced valid PDF/DOCX/XLSX artifacts. The current default Docker image smoke proved LibreOffice, Pandoc, Poppler, Python document libraries, and browser-extension profile install. Real provider-backed release matrix should still rerun. |
| `GHDR-007` | PARTIAL | Public-safe fixture benchmark suite; compact real host Codex xhigh and Claude Opus 4.8 max runs; private long-form Codex xhigh and Claude Opus 4.8 max benchmark runs; ClaudeViv review-only pass | Public-safe fixture suite passed seven cases: generic market research, technical literature, file transformation, text-only/no-file, contamination warning, source-window negative control, and missing-artifact negative control. Compact real host Codex xhigh and Claude Opus 4.8 max runs both produced Markdown+CSV artifacts with completion/constraint/hygiene `pass`. Raw private evidence remains outside this repo. Sanitized private outcome: Codex delivered a larger workbook/report set with passing evidence and a few coverage/adjudication gaps; Claude delivered valid artifacts and broad coverage but failed source-window compliance. ClaudeViv agreed production-grade must remain partial. |
| `GHDR-008` | PARTIAL | Private benchmark comparison plus `source-adjudication.md` and `source-adjudication-corpus.md` | One source-exclusion dispute was correctly handled in the private benchmark path. A public-safe corpus now covers stale status, source/date blending, and version-boundary disputes. A separate private benchmark source-risk item remains for human/source adjudication. This is QA evidence, not runtime hardcoding. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `GHDR-UC-001` | Launch a constrained long-running worker and inspect run state. | Host Codex/Claude private benchmark runs | PARTIAL | Private final artifacts rendered/opened locally. | Heartbeats include runtime, model where applicable, timeout policy, process pid, transcript paths, final evidence JSON, and artifact inventory. | Claude source-window drift needs post-contract rerun. |
| `GHDR-UC-002` | Open/download a generated artifact. | Isolated local API plus Playwright browser; local artifact render/open checks; Docker workstation smoke | PASS for local fixture scope | Project, worker console, artifact preview, short-ref download, and View workspace pages rendered; artifact preview showed report content plus Download file and View workspace controls; `/w/{ref}` reload persisted the synthetic desktop marker; DOCX wrapper rendered in browser. | Synthetic project/worker/artifact state, API logs, browser assertions, short-ref redirect assertion, scratch-exclusion check, direct download validation for Markdown/CSV/HTML/PDF/XLSX/DOCX/PPTX, private PDF page render samples, `openpyxl`, `python-docx`, `python-pptx`, and Docker default-image tool/version smoke. | Real provider-backed release matrix still required; local product path passed. |
| `GHDR-UC-003` | Compare Codex xhigh and Claude max benchmark outputs. | Public-safe fixture suite, compact real host Codex/Claude runs, host Codex/Claude wait/continue smokes, private local benchmark runs, and public-safe Docker model probes | PARTIAL | Compact real host Codex and Claude artifact sets were created and inspected through evidence; both private final artifact sets opened/inspected locally; Docker Codex public-safe Markdown artifact was created; host Codex and Claude wait/continue smokes completed. | Public-safe fixture suite passed seven cases. Compact real host Codex xhigh and Claude Opus 4.8 max both passed completion, constraint, hygiene, final-output, profile, effort, and artifact checks. Corrected host Codex xhigh and host Claude max wait/continue smokes both passed with marker checks. Private Codex evidence passed constraint, hygiene, completion, final-output, profile, effort, and artifact checks. Private Claude evidence passed artifact/final-output checks but failed source-window compliance and warned on two auth-wall caveats. Docker Codex xhigh evidence passed after effort projection fix; Docker Claude Opus max evidence proved `--effort max` and failed as `provider_auth_missing`. `CLAUDE_CODE_OAUTH_TOKEN` projection is now tested, but no headless token is present in this shell for a live Docker Claude completion rerun. | Post-contract private long-form rerun and live Docker Claude completion with a real headless token pending. |
| `GHDR-UC-004` | Trigger timeout/interruption and recover. | Automated host timeout/interrupt tests plus real host-Codex API wait/continue smoke | PARTIAL | Not exercised through browser wait/status UI in this slice. | Timeout/interrupt evidence JSON regressions passed. Live host-Codex API smoke observed `running -> completed` for initial and continuation runs and updated the same artifact. | Live wait/status/continue/cancel/degraded browser QA pending. |
| `GHDR-UC-005` | Adjudicate a source dispute. | Private benchmark artifact review, public-safe template, and public-safe corpus | PARTIAL | Sanitized outcome recorded without raw private evidence. | Template exists; one private exclusion dispute was handled; the public-safe corpus covers three generic dispute classes; one private ranking/source-risk item remains open. | Private benchmark-specific adjudication remains outside the public repo. |

## Traceability

- Feature: GlassHive universal deep research and document generation.
- Requirement: `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`.
- Use case: `GHDR-UC-001` through `GHDR-UC-005`.
- QA case: `GHDR-001` through `GHDR-008`.
- Expected result: local workers preserve constraints, project real capabilities, create inspectable artifacts, record truthful evidence, and expose user-visible preview/download paths.
- Actual evidence: automated suites passed; real compact Codex and Claude host probes produced inspected artifacts; Playwright opened local project/worker/artifact preview pages; public-safe fixture benchmark suite passed; private host Codex/Claude long-form benchmark runs completed and produced evidence JSON plus inspected deliverables.
- Remaining gap or fix: post-contract rerun for source-window compliance, live Docker Claude completion with a real headless token, degraded live browser matrix, private benchmark-specific adjudication, and release/commit hygiene for the nested GlassHive repo.

## Key Findings

- Fixed: host worker environments now project verified bundled workspace dependency paths when available. A real Codex xhigh probe resolved the bundled artifact module and recorded workspace dependency env keys in evidence.
- Fixed: evidence parser now detects Claude Code JSON `type=result` final messages containing `FINAL REPORT:`.
- Fixed: completion compliance now catches requested artifact types and support-notes-only outputs without turning generic "must include columns" prose into seed entities.
- Fixed: document validation dependencies are present in the runtime venv, so XLSX/DOCX/PPTX checks use real libraries rather than reporting unavailable.
- Fixed: advisory content hygiene no longer flags normal long Markdown/text reports as overlong structured fields; structured CSV/JSON-style overlong fields can still warn.
- Fixed: source-window drift from the Claude benchmark produced a generic worker-contract tightening: excluded source/date/auth/scope items must not support facts, scoring, or deliverables and may only be recorded as rejected/out-of-scope evidence.
- Fixed after ClaudeViv review: constraint compliance no longer fails lines explicitly labeled rejected/out-of-scope/not-used, while lines merely marked flagged still fail when they widen the source/date window.
- Fixed after local browser QA: artifact-preview `View workspace` short refs in the standalone API app no longer redirect to an unmounted `/watch/...` route; they now open a clean `/w/{ref}` workspace control page, keep user-visible links tokenless, and use hashed worker-view cookie names instead of raw worker-id cookie names.
- Fixed after subagent runtime audit: unproven Codex xhigh clamps with visible telemetry, Docker/workspace Claude max fails closed when `--effort` support is absent, host bootstrap rejects file entries without content/source, and blocking evidence failures are user-visible instead of silently accepted.
- Fixed after ClaudeViv review: evidence-result gating no longer treats attached/uploaded/input formats as missing output artifacts, explicitly forbidden output formats are subtracted from required formats, and future subject dates are allowed when the cited/source evidence remains inside the ledger window.
- Fixed after Docker model probe: Docker Codex per-run `effort=xhigh` no longer depends on the custom OpenAI-compatible provider branch; copied-auth Docker Codex now records `model_reasoning_effort="xhigh"` and evidence `effort=xhigh`.
- Fixed after Docker degraded probe: Claude/Codex-style “not logged in / please run login” failures classify as `provider_auth_missing` instead of `unknown`, including runtime-error paths raised after CLI exit.
- Fixed after local browser action QA: the `/w/{ref}` workspace view no longer shows the old instructional takeover block; Playwright verified the clean view plus pause/resume/interrupt/terminate controls with matching API state/events.
- Added live wait/continue harness evidence: `live_provider_wait_continue_smoke.py` ran a real host-Codex public-safe task with an intentional delay, observed `running -> completed`, then continued in the same workspace and verified the continuation marker in the same artifact.
- Fixed after public-safe generic benchmarks and compact real host runs: seed `topic/topics` and colon-form `Seed entities:` descriptors no longer create false missing-seed warnings; mixed “deliver X/Y, do not create Z” lines keep required formats separate from forbidden formats; negative self-check prose about excluding cookie/navigation/script text no longer warns; and CSV hygiene scans cells instead of treating a large clean CSV as one overlong structured field.
- Fixed after the later ClaudeViv review: signed-link log redaction now covers sensitive query fields at the start of a log value; old worker console/view/terminal HTML strips signed query strings before rendering links or JavaScript helpers; Glass Drive UI worker-view cookie names are hash-derived like the runtime API; content hygiene treats `VaR estimate = ...` as finance prose rather than JavaScript; parenthetical forbidden formats such as `(no PDF)` no longer erase later required formats; and future subject dates remain allowed when source evidence is dated inside the ledger window.
- Fixed after short-ref redirect review: `/r/{ref}` now accepts relative, same-origin, and configured GlassHive operator/runtime/artifact origins, strips signed query parameters before redirect, and rejects unconfigured absolute redirect targets in both runtime API and Glass Drive UI.
- Fixed after compact ClaudeViv review: the redirect validator now rejects browser-normalized relative bypass targets such as leading `//`, multi-slash, and backslash-containing paths; runtime and UI tests cover those cases plus the explicit comma-list redirect allowlist. The QA public-safety gate now scans feature QA scripts and public GlassHive research docs, flags raw `gh_token`, `gh_sig`, `gh_exp`, or `gh_kind` assignments, and flags raw GlassHive runtime ids in public evidence.
- Fixed after ClaudeViv follow-up review: provider service-failure classification now requires structured failure evidence or a numeric 529/503-style provider marker before treating overload/service-unavailable text as retryable `provider_response_failed`; ordinary unstructured prose containing `overloaded` remains `unknown`.
- Fixed after public-safe source review: `source-adjudication-corpus.md` now provides reusable public fixtures for stale status, source/date blending, and version-boundary disputes without adding runtime-specific rules.
- Residual: live Docker Claude completion with a real headless token, provider-backed long-running browser wait/continue, live cancellation/quota/profile fallback, private long-form source-window rerun, private benchmark-specific source adjudication, and nested-repo release/commit/pin hygiene remain before production-grade signoff. The artifact/tool short-ref path no longer exposes raw signed-link tokens and now opens `/w/{ref}` for member-facing workspace controls, but diagnostic/internal built-in project/view routes still use `wrk_` and `prj_` ids where directly visited.

## Official Reference Checks

- OpenAI Codex config reference: `model_reasoning_effort` supports values including `xhigh` when the active route supports it.
- Anthropic model docs identify `claude-opus-4-8` as the Claude Opus 4.8 API/model ID.
- Claude Code docs confirm model selection and effort support are CLI-level configuration surfaces; GlassHive must record command/env evidence rather than assuming defaults.

## Automated Evidence

```bash
./.venv/bin/python -m pytest tests/test_bootstrap.py tests/test_run_evidence.py tests/test_profile_runtime.py -q
./.venv/bin/python -m pytest tests/test_run_evidence.py tests/test_profile_runtime.py tests/test_api.py tests/test_mcp_server.py tests/test_models.py -q
./.venv/bin/python -m pytest -q
./.venv/bin/python -m pytest tests/test_docker_sandbox.py -q
uv run pytest -q
viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python -m pytest tests/release/test_qa_operating_contract.py tests/release/test_qa_results_public_safety.py -q
viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python -m pytest tests/release/test_config_compiler.py tests/release/test_prompt_registry.py tests/release/test_stable_dev_runtime_workflows.py -q
```

All commands above exited successfully after the latest worker-contract patch.

Post-continuation focused rerun:

```bash
./.venv/bin/python -m pytest tests/test_run_evidence.py tests/test_bootstrap.py tests/test_profile_runtime.py -q
./.venv/bin/python -m pytest tests/test_api.py::test_artifact_open_page_previews_text_without_forcing_download tests/test_api.py::test_enterprise_signed_artifact_open_page_actions_remain_signed -q
```

Post-ClaudeViv hardening rerun:

```bash
./.venv/bin/python -m pytest tests/test_run_evidence.py -q
./.venv/bin/python -m pytest tests/test_bootstrap.py tests/test_profile_runtime.py tests/test_api.py::test_artifact_open_page_previews_text_without_forcing_download tests/test_api.py::test_enterprise_signed_artifact_open_page_actions_remain_signed -q
./.venv/bin/python -m pytest -q
uv run pytest -q
viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python -m pytest tests/release/test_qa_operating_contract.py tests/release/test_qa_results_public_safety.py -q
viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python -m pytest tests/release/test_config_compiler.py tests/release/test_prompt_registry.py tests/release/test_stable_dev_runtime_workflows.py -q
```

All commands above exited successfully after the route/evidence/effort updates and post-ClaudeViv false-positive hardening.

Post-privacy-route focused rerun:

```bash
./.venv/bin/python -m pytest tests/test_api.py tests/test_run_evidence.py -q
```

The command above exited successfully after the `/w/{ref}` workspace route, worker-view cookie-name hashing, and signed-link redaction updates.

Post-Docker-effort/classification focused rerun:

```bash
./.venv/bin/python -m pytest tests/test_profile_runtime.py::test_workspace_codex_command_honors_per_run_effort_without_custom_provider tests/test_profile_runtime.py::test_cli_failure_classifies_not_logged_in_provider_session tests/test_profile_runtime.py::test_runtime_error_classifies_not_logged_in_provider_session tests/test_run_evidence.py::test_run_evidence_records_effective_effort_from_command_and_env -q
```

The command above exited successfully after the Docker Codex effort projection and provider-auth classification fixes.

Post-degraded-flow focused rerun:

```bash
./.venv/bin/python -m pytest tests/test_profile_runtime.py::test_host_cli_timeout_writes_truthful_evidence tests/test_profile_runtime.py::test_host_cli_interrupt_writes_run_evidence tests/test_profile_runtime.py::test_cli_failure_classifies_not_logged_in_provider_session tests/test_profile_runtime.py::test_runtime_error_classifies_not_logged_in_provider_session tests/test_api.py::test_pause_resume_freezes_active_run_without_losing_it tests/test_api.py::test_interrupt_stops_active_run_and_keeps_worker_ready tests/test_api.py::test_steer_interrupts_active_run_and_redirects_to_new_instruction tests/test_api.py::test_worker_quota_enforced_per_user tests/test_api.py::test_active_worker_quota_retry_after_uses_idle_release tests/test_api.py::test_assign_run_refreshes_stale_worker_model_before_queue tests/test_api.py::test_worker_find_or_resume_refreshes_runtime_when_alias_reprofiles tests/test_api.py::test_enterprise_short_artifact_ref_is_auth_gated_and_durable_by_default tests/test_api.py::test_artifact_open_page_previews_text_without_forcing_download tests/test_api.py::test_enterprise_signed_artifact_open_page_actions_remain_signed -q
./.venv/bin/python -m pytest tests/test_mcp_server.py::test_enterprise_mcp_http_auth_middleware_gates_transport_requests tests/test_mcp_server.py::test_enterprise_mcp_requires_service_authentication tests/test_mcp_server.py::test_enterprise_owner_and_alias_accept_generic_glasshive_identity_headers tests/test_mcp_server.py::test_workspace_status_returns_view_steer_link_for_web_mcp_surfaces tests/test_mcp_server.py::test_workspace_wait_prefers_newer_worker_run_over_stale_failed_run tests/test_mcp_server.py::test_workspace_wait_returns_timeout_without_callback tests/test_mcp_server.py::test_workspace_wait_uses_configured_default_timeout_when_omitted tests/test_mcp_server.py::test_workspace_continue_rechecks_stale_connected_account_guard_with_fresh_broker -q
```

Both commands above exited successfully after the `/w/{ref}` action, degraded wait/status, auth, quota, stale metadata, and provider-auth classification updates.

Post-public-safe-benchmark focused rerun:

```bash
./.venv/bin/python -m pytest tests/test_run_evidence.py -q
viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python qa/glasshive_deep_research/scripts/run_public_safe_benchmarks.py
```

Both commands above exited successfully after the seed descriptor, mixed required/forbidden output,
negative hygiene context, and CSV cell-scanning fixes.

Post-ClaudeViv privacy/parser focused rerun:

```bash
./.venv/bin/python -m pytest tests/test_api.py::test_runtime_sensitive_url_log_filter_redacts_signed_tokens tests/test_api.py::test_enterprise_member_ui_redacts_runtime_internals tests/test_run_evidence.py::test_content_hygiene_is_generic_and_advisory tests/test_run_evidence.py::test_constraint_compliance_allows_official_future_subject_when_sources_remain_in_window tests/test_run_evidence.py::test_completion_compliance_keeps_required_formats_when_line_also_forbids_pdf tests/test_run_evidence.py::test_completion_compliance_keeps_required_format_after_parenthetical_no_pdf -q
uv run pytest tests/test_server.py::test_signed_watch_sets_worker_scoped_cookie tests/test_server.py::test_short_worker_view_ref_redirects_and_sets_worker_cookie tests/test_server.py::test_enterprise_short_worker_view_ref_bootstraps_direct_link_and_rechecks_asserted_owner tests/test_server.py::test_ui_sensitive_url_log_filter_redacts_signed_tokens tests/test_server.py::test_novnc_submodule_imports_can_inherit_signed_token_from_cookie tests/test_server.py::test_enterprise_artifact_link_ref_uses_worker_cookie_identity tests/test_server.py::test_signed_runtime_proxy_sets_worker_scoped_cookie tests/test_server.py::test_signed_runtime_proxy_refreshes_worker_cookie_expiry tests/test_server.py::test_worker_live_poll_refreshes_worker_cookie_expiry -q
```

Both commands above exited successfully after the leading-query redaction, legacy signed-query
reflection, Glass Drive UI cookie hashing, `VaR estimate`, source-date, and parenthetical format
fixes.

Post-Claude-headless-token focused rerun:

```bash
./.venv/bin/python -m pytest tests/test_bootstrap.py::test_enterprise_bootstrap_keeps_provider_secrets_out_of_interactive_runtime_env tests/test_profile_runtime.py::test_claude_code_runtime_passes_gateway_headers tests/test_profile_runtime.py::test_claude_code_runtime_passes_headless_oauth_without_api_key_mode -q
```

The command above exited successfully after adding `CLAUDE_CODE_OAUTH_TOKEN` to the allowed
bootstrap/runtime projection path while preserving enterprise secret/run-only handling. The current
shell does not have a real `CLAUDE_CODE_OAUTH_TOKEN`, so live Docker Claude completion remains a
credential-prerequisite blocker rather than a runtime projection blocker.

Post-token-setup live Docker Claude attempt:

```bash
claude setup-token
```

Claude CLI auth was valid and `claude --version` reported `2.1.178`, but `claude setup-token` did
not complete within a bounded 120 second non-interactive run. No `CLAUDE_CODE_OAUTH_TOKEN`,
`ANTHROPIC_API_KEY`, or `ANTHROPIC_AUTH_TOKEN` was present in the shell. Live Docker Claude
completion therefore remains blocked on a credential prerequisite; the runtime projection path is
covered by tests.

Post-short-ref-redirect focused rerun:

```bash
./.venv/bin/python -m pytest tests/test_api.py::test_enterprise_short_workspace_ref_mints_fresh_session_cookie_after_original_token_expiry tests/test_api.py::test_short_workspace_ref_rejects_unconfigured_absolute_redirect_target -q
uv run pytest tests/test_server.py::test_short_worker_view_ref_redirects_and_sets_worker_cookie tests/test_server.py::test_short_worker_view_ref_rejects_unconfigured_absolute_redirect_target tests/test_server.py::test_enterprise_short_worker_view_ref_bootstraps_direct_link_and_rechecks_asserted_owner -q
```

Both commands exited successfully after adding configured-origin enforcement for short workspace
redirects in the runtime API and Glass Drive UI.

Post-ClaudeViv redirect hardening focused rerun:

```bash
./.venv/bin/python -m pytest tests/test_api.py::test_enterprise_short_workspace_ref_mints_fresh_session_cookie_after_original_token_expiry tests/test_api.py::test_short_workspace_ref_rejects_unconfigured_absolute_redirect_target tests/test_api.py::test_short_workspace_ref_rejects_relative_redirect_bypass_targets tests/test_api.py::test_short_workspace_ref_allows_explicit_redirect_host_allowlist -q
uv run pytest tests/test_server.py::test_short_worker_view_ref_redirects_and_sets_worker_cookie tests/test_server.py::test_short_worker_view_ref_rejects_unconfigured_absolute_redirect_target tests/test_server.py::test_short_worker_view_ref_rejects_relative_redirect_bypass_targets tests/test_server.py::test_short_worker_view_ref_allows_explicit_redirect_host_allowlist tests/test_server.py::test_enterprise_short_worker_view_ref_bootstraps_direct_link_and_rechecks_asserted_owner -q
viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python -m pytest tests/release/test_qa_results_public_safety.py -q
```

The runtime redirect hardening tests, Glass Drive UI redirect hardening tests, and strengthened QA
public-safety gate all passed after the compact ClaudeViv review.

Post-short-ref-redirect browser smoke:

```bash
python qa/glasshive_deep_research/scripts/local_user_grade_fixture.py --fresh
playwright_cli open "the fixture project URL emitted by the script"
playwright_cli open "the fixture artifact preview URL emitted by the script"
playwright_cli click "View workspace"
playwright_cli snapshot
playwright_cli eval "check visible text and links for signed-query fields"
playwright_cli console warning
playwright_cli requests
```

The browser opened the project page, artifact preview, and `/w/{ref}` workspace wrapper. The artifact
preview showed only `/v1/link-refs/{ref}` and `/w/{ref}` links, the workspace wrapper kept the
address bar and visible controls on `/w/{ref}` routes, the iframe rendered the public marker after
refresh, the visible/link token-leak check returned no signed query fields, and console warnings and
errors were zero. The fixture server and Playwright browser were stopped after the smoke.

Post-live-provider wait/continue smoke:

```bash
viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python qa/glasshive_deep_research/scripts/live_provider_wait_continue_smoke.py --profile codex-cli --execution-mode host --effort high --delay-seconds 35 --first-timeout-sec 240 --continue-timeout-sec 240
```

The command exited successfully. The first run and continuation both observed `running` then
`completed`; the first run created `artifacts/live-wait.md`, and the continuation added
`GLASSHIVE_LIVE_CONTINUE_SMOKE` to the same artifact. A follow-up syntax check for the harness also
passed with `python -m py_compile`.

Post-2026-06-22 corrected live-provider and degraded slice:

```bash
viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python -m py_compile qa/glasshive_deep_research/scripts/live_provider_wait_continue_smoke.py
viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python qa/glasshive_deep_research/scripts/live_provider_wait_continue_smoke.py --profile codex-cli --execution-mode host --effort xhigh --delay-seconds 40 --first-timeout-sec 420 --continue-timeout-sec 420 --poll-sec 5
viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python qa/glasshive_deep_research/scripts/live_provider_wait_continue_smoke.py --profile claude-code --execution-mode host --effort max --delay-seconds 40 --first-timeout-sec 600 --continue-timeout-sec 600 --poll-sec 5
./.venv/bin/python -m pytest tests/test_profile_runtime.py::test_classify_cli_failure_maps_structured_provider_overload tests/test_profile_runtime.py::test_host_cli_timeout_writes_truthful_evidence tests/test_profile_runtime.py::test_host_cli_interrupt_writes_run_evidence tests/test_profile_runtime.py::test_claude_code_runtime_passes_headless_oauth_without_api_key_mode tests/test_api.py::test_max_run_duration_cancels_expired_run_and_releases_compute tests/test_api.py::test_interrupt_stops_active_run_and_keeps_worker_ready tests/test_api.py::test_steer_interrupts_active_run_and_redirects_to_new_instruction tests/test_api.py::test_worker_quota_enforced_per_user tests/test_api.py::test_active_worker_quota_counts_resuming_workers tests/test_api.py::test_worker_find_or_resume_refreshes_runtime_when_alias_reprofiles tests/test_api.py::test_live_logs_follow_profile_when_legacy_runtime_metadata_is_stale tests/test_api.py::test_artifact_surfaces_reject_browser_runtime_scratch_paths -q
./.venv/bin/python -m pytest tests/test_mcp_server.py::test_enterprise_mcp_http_auth_middleware_gates_transport_requests tests/test_mcp_server.py::test_enterprise_mcp_requires_service_authentication tests/test_mcp_server.py::test_workspace_wait_returns_timeout_without_callback tests/test_mcp_server.py::test_workspace_continue_queues_same_workspace_recovery tests/test_mcp_server.py::test_workspace_continue_rejects_active_previous_run tests/test_mcp_server.py::test_workspace_launch_returns_structured_quota_block_with_reuse_options tests/test_mcp_server.py::test_enterprise_owner_and_alias_accept_generic_glasshive_identity_headers -q
uv run pytest tests/test_server.py::test_enterprise_bootstrap_requires_authenticated_user_assertion tests/test_server.py::test_short_worker_view_ref_redirects_and_sets_worker_cookie tests/test_server.py::test_short_worker_view_ref_rejects_unconfigured_absolute_redirect_target tests/test_server.py::test_short_worker_view_ref_rejects_relative_redirect_bypass_targets tests/test_server.py::test_ui_sensitive_url_log_filter_redacts_signed_tokens tests/test_server.py::test_enterprise_artifact_link_ref_uses_worker_cookie_identity -q
```

The corrected Codex host smoke passed with unique workspace/artifact marker evidence and
route-fallback telemetry for unproven xhigh. The first Claude host max smoke returned structured
overload evidence and proved retryable `provider_response_failed`; a later host Claude max retry
completed both the initial run and continuation with marker and evidence checks. The named degraded
slices all passed.

Post-2026-06-22 local browser smoke:

```bash
viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python qa/glasshive_deep_research/scripts/local_user_grade_fixture.py --fresh
playwright_cli open "the fixture project URL emitted by the script"
playwright_cli goto "the fixture artifact preview URL emitted by the script"
playwright_cli click "View workspace"
playwright_cli reload
playwright_cli snapshot
playwright_cli eval "check top-level visible text and links for signed-query fields and raw worker ids"
playwright_cli console warning
```

The project page, artifact preview, `/w/{ref}` workspace view, and refreshed iframe rendered
successfully. The artifact preview exposed only managed short refs. The `/w/{ref}` top-level page had
no signed-query fields or raw worker ids in visible text or links, and console warnings/errors were
zero.

Final affected-suite rerun:

```bash
./.venv/bin/python -m pytest tests -q
uv run pytest -q
viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python -m pytest tests/release/test_qa_operating_contract.py tests/release/test_qa_results_public_safety.py -q
viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python -m pytest tests/release/test_config_compiler.py tests/release/test_prompt_registry.py tests/release/test_stable_dev_runtime_workflows.py -q
```

All four commands exited successfully after the public-safe benchmark and compact real host-worker fixes.
The runtime suite, public-safe benchmark, QA/public-safety release slice, and release workflow slice
were rerun successfully again after the Claude headless-token projection patch; Glass Drive UI was
unchanged by that patch and its full suite had already passed after the signed-link/cookie changes.

Post-ClaudeViv final affected-suite rerun:

```bash
./.venv/bin/python -m pytest tests -q
uv run pytest -q
viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python qa/glasshive_deep_research/scripts/run_public_safe_benchmarks.py
viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python -m pytest tests/release/test_qa_operating_contract.py tests/release/test_qa_results_public_safety.py -q
viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python -m pytest tests/release/test_config_compiler.py tests/release/test_prompt_registry.py tests/release/test_stable_dev_runtime_workflows.py -q
```

All commands exited successfully after the compact ClaudeViv redirect-hardening and public-safety
gate fixes.

Additional local probes:

- Direct host-env probe: `NODE_PATH` projection let Node resolve the bundled artifact module.
- Real Codex xhigh capability probe: produced inspected text/CSV/Markdown artifacts; evidence reported completion-compliance `pass`, final-output `ok`, profile truth `codex-cli`, xhigh effort, and no blockers for the requested artifacts.
- Public-safe generic fixture benchmark suite: seven deterministic cases passed, covering generic market research, technical literature, file transformation, text-only/no-file, content-contamination warning, source-window negative control, and missing-artifact negative control.
- Compact real host Codex xhigh benchmark: created Markdown and CSV artifacts, inspected both with shell commands, and produced evidence `pass` with completion, constraint, hygiene, final-output, profile, backend, and `effort=xhigh` all coherent.
- Compact real host Claude Opus 4.8 max benchmark: created Markdown and CSV artifacts, inspected both with shell commands, and produced evidence `pass` with completion, constraint, hygiene, final-output, `model=claude-opus-4-8`, backend, and `effort=max` all coherent.
- Private host Codex xhigh benchmark: produced valid PDF/XLSX/HTML/screenshot artifacts; evidence reported constraint `pass`, hygiene `pass`, completion `pass`, and final-output `ok`.
- Private host Claude Opus 4.8 max benchmark: produced valid PDF/DOCX/XLSX artifacts; evidence reported completion `pass` and final-output `ok`, but constraint `fail` from source-window drift and hygiene `warn` from auth-wall caveats.
- Docker workstation compatibility smoke: the installed prior workstation image started a disposable sandbox, proved Codex/Claude CLI versions, Node, Python document libraries, LibreOffice, Pandoc, Poppler, browser-extension policy, noVNC health, and the worker bootstrap contract; the disposable container was removed.
- Docker default-image smoke: after pruning unused Docker build cache, the current default workstation image built and started a disposable sandbox; it proved Codex CLI `0.140.0`, Claude Code `2.1.178`, Node, Python document libraries, LibreOffice, Pandoc, Poppler, browser-extension profile install, noVNC health, and the worker bootstrap contract; the disposable container was removed.
- Docker Codex xhigh model probe: a real disposable Docker `codex-cli` worker using local developer copied auth created a public-safe Markdown artifact, produced `evidence_result.status=pass`, and recorded `model_reasoning_effort="xhigh"` plus `effort=xhigh`.
- Docker Claude Opus 4.8 max model probe: a real disposable Docker `claude-code` worker recorded `claude-opus-4-8` and `--effort max`, then failed before artifact creation because the containerized Claude CLI reported “Not logged in”; the run now reports `provider_auth_missing` instead of `unknown`. Follow-up code supports the documented `CLAUDE_CODE_OAUTH_TOKEN` headless-token path, but this shell currently reports that token absent.
- Host Claude max wait/continue retry: the public-safe live-provider smoke observed `running -> completed` for the initial run and continuation, verified first/continuation artifact markers, recorded `profile=claude-code`, `execution_mode=host`, `effort=max`, and evidence `pass`.
- Playwright UI smoke: opened local project, worker console, artifact preview, short-ref download, and View workspace pages; artifact preview showed synthetic report content, Download file, and View workspace controls with no console or request failures. The first fixture run exposed a stale `/watch/...` redirect that produced a 404; the route was fixed and later privacy QA proved the artifact page links to `/w/{ref}`, the workspace wrapper and desktop wrapper keep the browser address bar and DOM controls on `/w/{ref}` routes, and the visible text does not contain raw project or worker ids. Direct internal diagnostic routes may still expose raw ids when visited intentionally.
- Playwright action smoke: on the refreshed `/w/{ref}` page, Pause changed API state to `paused`, Resume returned state to `ready`, Interrupt kept the worker `ready`, and Terminate changed state to `terminated`; events recorded `worker.paused`, `worker.resumed`, `worker.interrupted`, and `worker.terminated`.
- Fresh Playwright degraded/action smoke: public-safe fixture opened project/worker pages, artifact preview, tokenless download, clean `/w/{ref}` workspace wrapper and iframe, refreshed the workspace view, clicked Pause/Resume/Interrupt/Terminate, verified matching API state/events, and checked an invalid `/w/{ref}` returns an auth/not-found rejection. Positive-path browser console warnings/errors and request failures were empty.
- Artifact file matrix: direct open/download checks covered `answer.md`, `output/data.csv`, `reports/report.html`, `artifacts/report.pdf`, `artifacts/book.xlsx`, `artifacts/brief.docx`, and `artifacts/deck.pptx`; every open URL returned an HTML wrapper without attachment, every download returned an attachment with the expected MIME class, and downloaded content structurally validated with public-safe markers. Playwright also opened the DOCX wrapper page.
- ClaudeViv review-only pass: the first structured attempt ran to the helper's structured-output retry limit without usable findings; a concise Opus 4.8 retry completed. Claude validated the main direction as aligned partial progress, identified the host evidence-gating false-positive risk that is now partly fixed with generic regressions, and reinforced that broader Docker task QA, degraded UI paths, old built-in UI route-ID hardening, and release/commit hygiene remain blockers.
- Compact ClaudeViv review-only pass: the first max-effort retry hit provider overload after a long run; a compact review completed. Claude confirmed the slice is safe to present as honest partial/local evidence, called out the redirect relative-path hardening gap and missing comma-list tests now fixed, recommended extending the public-safety gate for signed-query strings and QA Python files now fixed, and reaffirmed nested-repo commit/pin hygiene as the highest blocker before any shipped claim.

## Private Benchmark Status

- Private long-form Codex xhigh run: completed locally outside this public repo. Sanitized result: artifact delivery passed, evidence passed, and quality review found coverage/adjudication follow-up items rather than runtime delivery failure.
- Private long-form Claude Opus 4.8 max run: completed locally outside this public repo. Sanitized result: artifact delivery passed, source-window compliance failed, and a generic contract fix was added.
- Raw prompts, artifacts, logs, screenshots, company names, and comparison notes remain private. Public reporting uses sanitized counts, pass/partial/fail findings, and generic issue categories only.

## Full-View Evidence Checklist

| Evidence surface | Result / sanitized pointer |
| --- | --- |
| Requirement and use case | `48_GlassHive_Workstation_Sandbox_Runtime.md`; `GHDR-UC-001` to `GHDR-UC-005`; `GHDR-001` to `GHDR-008`. |
| Code owning path | `bootstrap.py`, `run_evidence.py`, `profile_runtime.py`, `runtime_env.py`, API/MCP/UI regression tests. |
| Docs and nested docs/repos | Runtime requirement doc and this QA report updated; private benchmark evidence remains outside the public repo. |
| Scripts or harnesses | Runtime pytest suites, Glass Drive UI tests, parent QA safety tests, public-safe fixture benchmark harness, live provider wait/continue smoke, direct host-worker probes, private benchmark runs, Playwright browser smoke, Docker workstation smoke, Docker Codex/Claude model probes. |
| Logs/state | Temporary SQLite/API state, active-run heartbeats, run evidence JSON, transcript tails, API server logs, and private benchmark artifact evidence. |
| Generated/shipped artifact | Synthetic report/CSV/text/PDF/XLSX/DOCX/PPTX/HTML artifacts inspected; compact real host Codex/Claude Markdown+CSV artifacts passed evidence; private PDF/XLSX/DOCX/HTML/screenshot artifacts structurally and visually inspected; installed and current default Docker workstation image smokes passed; Docker Codex created a public-safe Markdown artifact. |
| Real user path | Playwright opened real local UI and artifact preview pages; compact real host Codex/Claude workers completed and artifacts were inspected through evidence; private long-running workers completed and artifacts were inspected locally. |
| Not run / blocked | Docker Claude model task completion until a real `CLAUDE_CODE_OAUTH_TOKEN` or equivalent approved credential is present, provider-backed long-running browser wait/continue, live quota/profile-fallback matrix, private long-form post-contract source-window rerun, private benchmark-specific source adjudication, and nested-repo release/commit hygiene. |

## User-Grade Evidence

- Surface exercised: local GlassHive API/UI in a real Playwright browser, host Codex and Claude worker processes, generated artifact preview, temporary SQLite state, run evidence JSON, and worker workspace files.
- Real user path: browser opened the local project workspace, worker console, and artifact preview URL; the preview displayed synthetic report content plus Download file and View workspace controls.
- Visible outcome: artifact preview rendered the expected Markdown content, project/worker pages showed profile truth, compact real Codex/Claude host runs completed with Markdown+CSV artifacts, and no browser console or request failures were captured in the browser fixture.
- Expanded/detail state: worker console showed artifact links and workspace controls; artifact detail page showed filename, MIME/size metadata, download control, and workspace navigation.
- Persistence/reload result: local live-view reload persisted the synthetic desktop marker after the artifact short-ref opened the workspace; full type-by-type artifact preview/download/reload remains pending.
- Local/external prerequisite state: Codex CLI and Claude Code CLI versions were present; bundled workspace dependency paths were discoverable; Docker daemon was available after starting Docker Desktop; installed and current default Docker workstation image smokes passed after unused build-cache cleanup; Docker Codex could use local developer copied auth; Docker Claude could not use the containerized CLI login in this environment and failed as `provider_auth_missing`; `claude setup-token` did not complete within the bounded non-interactive attempt and `CLAUDE_CODE_OAUTH_TOKEN` is absent in the current shell, so the live headless-token path could not be completed.
- Evidence retrieval classification, if applicable: local API/browser paths passed; compact real host Codex/Claude artifacts were retrieved through local evidence/API state; private benchmark final artifacts were retrieved locally; degraded/error retrieval paths remain pending.
- Fallback path, if applicable: real Codex xhigh capability probe used local shell/Node fallback when appropriate and recorded the resolved bundled artifact module.
- Backend/log/DB confirmation: API server logs, temporary SQLite-backed state, active-run heartbeat JSON, and evidence JSON matched the visible project/worker/artifact path.
- Final model/runtime wording check: evidence reported Codex profile truth as `codex-cli`; compact Claude benchmark evidence reported `claude-code` with `claude-opus-4-8`; neither compact run surfaced legacy OpenClaw as backend truth.
- Substitution check: automated tests, logs, DB/state, evidence JSON, live host-Codex API wait/continue, and fresh Playwright support the local browser/user path; they do not substitute for live browser wait/continue on a provider-backed run, live Docker Claude headless-token completion, and broader generic benchmark reviews.

## Findings

- Defects fixed: verifier false positives for seed section headings, final-deliverable softening checks, JSON file hygiene scanning, stdout-only final report detection, and source-window prompt enforcement weakness.
- Regressions: none observed after the last full affected-suite run; post-contract rerun still required.
- Flakes: none observed in this slice.
- Environment issues: default Docker image initially failed on local Docker storage, but succeeded after unused build-cache cleanup.
- Residual risks: source-window compliance post-fix rerun, provider-backed browser wait/continue, live cancellation/quota/profile fallback, live Docker Claude headless-token completion, private benchmark-specific adjudication, and nested-repo release/commit hygiene remain open before production-grade signoff.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private prompts, raw benchmark content, private artifacts, screenshots, or customer data.
- [x] No local absolute paths, hostnames, personal emails, or raw runtime dumps.
- [x] Private evidence is summarized only as sanitized status and generic findings.
