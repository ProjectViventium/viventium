# GlassHive Production Hardening Local QA - 2026-06-22

## Summary

- Result: PASS for local approval readiness; cloud deploy, GitHub push, and parent pinning were not
  performed and are out of scope for this report.
- Build/source under test: local GlassHive runtime source checkout and public-safe QA harnesses.
- Runtime/artifact under test: evidence gating, constraint-ledger availability, file
  materialization, artifact discovery, effort telemetry, transcript metadata, browser-visible
  workspace/artifact controls, structured provider-failure evidence, provider-backed wait/continue
  browser flow, and public-safe benchmark fixtures.
- Environment: local development checkout only.
- Tester: Codex.
- Acceptance status: the implemented runtime slice, deterministic browser fixture with input
  materialization and terminate controls, expanded
  public-safe benchmark corpus, host Codex xhigh smoke, host Claude Opus max smoke, Docker Codex smoke,
  provider-backed Codex plus Claude host browser wait/continue full-matrix bridges, and private long-form host
  Codex/Claude reruns passed locally after same-workspace repair where required. Docker Claude live
  completion still requires an approved headless credential, and private source-quality adjudication
  stays in private QA evidence.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `GHDR-001` | PASS/PARTIAL | `tests/test_run_evidence.py`, public-safe benchmark corpus, sanitized private existing-workspace replay | Generic source/date ledger checks pass, including strict planning omission failure, final-output drift detection, workbook-hidden drift detection, access-timestamp/source-date separation, explicitly excluded out-of-window note handling, and negative drift controls. Private long-form rerun/adjudication remains private and outside this public report. |
| `GHDR-002` | PASS | `tests/test_profile_runtime.py`, `tests/test_api.py`, `tests/test_run_evidence.py` | Successful worker runs now fail truthfully when required run evidence or constraint ledgers are absent or failing; service-level recovery no longer upgrades an evidence-check failure into a completed run; valid final-answer-only chat results with internal notes are not falsely failed as missing file deliverables; fresh `reports/` and `output/` deliverables are eligible for provider-failure recovery. |
| `GHDR-004` | PASS | `tests/test_run_evidence.py`, `tests/test_profile_runtime.py`, `live_provider_wait_continue_smoke.py`, `live_provider_browser_wait_continue_qa.py`, browser fixture harnesses | Host provider wait/continue smokes passed for Codex and Claude. Deterministic browser wait/status/controls passed. Provider-backed Codex and Claude host browser wait/continue, artifact preview, short-ref, continuation, evidence, transcript-metadata, and redaction checks passed locally. Structured provider rate-limit, overload/response-failure, content-filter, auth-missing, request-rejected, missing Python module/runtime dependency, zero-exit structured provider error, and unsupported-runtime-configuration events are preserved in evidence or runtime classification instead of being reduced to a generic missing-final-output result. Benign provider/error terms and false structured error fields such as `is_error: false` in successful assistant output are not misclassified, and decorated Markdown `FINAL REPORT:` markers are accepted. |
| `GHDR-005` | PASS/PARTIAL | host Codex xhigh, host Claude max, Codex and Claude host provider-browser bridges, Docker Codex, Docker Claude credential-blocker probe, Docker safe-env regression | Codex xhigh and Claude max effort/profile projection are coherent for covered host runs. Docker Claude failed closed as `provider_auth_missing` because no headless token was present; token pass-through is implemented and tested without persisting a secret. |
| `GHDR-006` | PASS | Playwright browser fixture, direct artifact byte/signature checks, provider-backed Codex/Claude host full-matrix runs | Markdown, CSV, HTML, PDF, XLSX, DOCX, and PPTX preview/download/open checks passed for the local fixture and real host provider runs. The fixture also proved inline/source-path input materialization plus pause/resume/interrupt/terminate user controls. |
| `GHDR-007` | PASS/PARTIAL | public-safe benchmark suite, private benchmark lane | Fourteen public-safe benchmark fixtures passed, including the final rerun after raw support-capture hygiene filtering. Private long-form Codex and Claude host reruns completed locally; raw evidence and human/source-quality adjudication remain private QA. |
| `GHDR-009` | PASS/PARTIAL | runtime preflight/projection tests and live smokes | Capability projection is truthful for covered profiles; Docker Claude live completion depends on a credential prerequisite. |

## Traceability

- Feature: GlassHive universal deep research, document generation, and worker runtime reliability.
- Requirement: `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`.
- Use case: constrained worker run, user-visible workspace monitoring, continuation, generated
  artifact preview/download, provider effort projection, and degraded provider/auth handling.
- QA case: `GHDR-001`, `GHDR-002`, `GHDR-004`, `GHDR-005`, `GHDR-006`, `GHDR-007`, and `GHDR-009`.
- Expected result: GlassHive preserves constraints, records truthful run evidence, opens real
  artifacts, keeps signed-link material off public surfaces, and reports profile/effort truth for
  Codex and Claude paths. Provider failures are classified from structured CLI evidence with
  retryability and recovery guidance.
- Actual evidence: automated runtime tests passed; deterministic browser QA passed; public-safe
  benchmark corpus passed fourteen of fourteen cases; sanitized private long-form host reruns
  confirmed the new generic verifier catches source-window and dependency failure classes and can
  support same-workspace repair; host Codex xhigh and host Claude max wait/continue
  smokes passed; provider-backed Codex and Claude host browser wait/continue passed; Docker Codex
  live run/resume passed; Docker Claude failed closed with the expected provider-auth prerequisite.
- Remaining gap or fix: Docker Claude live completion with an approved headless credential and
  private human/source-quality adjudication remain separate from this local approval slice.
  Cloud deployment, GitHub push, and parent pin verification were intentionally not performed.

## Full-View Evidence Checklist

This report links the GlassHive feature, owning requirement, user use cases, QA cases, expected
behavior, observed evidence, and remaining out-of-scope gates. It names the real user path used, records docs and nested docs touched,
checks logs, DB/state/persistence through the harness outputs, and marks Docker Claude live
completion as BLOCKED on credentials rather than substituting another path. Automated tests and
model/provider smokes support the finding; the local provider-backed browser user path was run for
both Codex and Claude host profiles.

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Real user path | Was a browser or visible workspace path exercised? | PASS through Playwright/browser fixture with project, worker, artifact preview, `/w/{ref}`, refresh, pause/resume/interrupt/terminate, input materialization, and download checks; PASS through provider-backed Codex and Claude host browser full-matrix bridges for running state, reload, artifact preview, short-ref, continuation, final state, and document downloads. |
| Docs and nested docs | Did QA docs reflect product truth? | PASS for this local approval slice; cloud deploy, GitHub push, and parent pin reconciliation are explicitly out of scope. |
| Logs, DB/state/persistence | Did state agree with visible UX? | PASS for fixture DB counts, event/state checks, run status, and artifact inventory; live provider smokes and both provider-browser bridges recorded run states, evidence JSON, and transcript metadata. |
| Generated artifacts | Did files open/render? | PASS for Markdown, CSV, HTML, PDF, XLSX, DOCX, and PPTX local fixture artifacts plus provider-backed Codex/Claude host full-matrix artifacts. |
| Degraded path | Did failures fail closed? | PASS for Docker Claude credential blocker, timeout/transcript tests, structured provider-failure evidence across rate-limit, overload/response-failure, content-filter, auth-missing, request-rejected, zero-exit structured provider errors, benign provider/error prose false-positive controls, and unsupported-runtime-configuration classes, empty-file guards, and zero-byte artifact regression tests. |
| Remaining release gate | Is any required user path still not run? | PASS for local user paths in this scope. Docker Claude with a real headless token and private long-form adjudication remain separate credential/private-evidence gates. |

## User-Grade Evidence

- Surface exercised: Playwright/browser against the local GlassHive project page, worker page,
  artifact preview/download pages, and signed `/w/{ref}` workspace route; provider-backed Codex
  and Claude host browser wait/continue bridges; CLI/API live-provider smokes for host Codex and
  host Claude; Docker CLI live smoke for Codex.
- Real user path: opened the project UI, opened artifact preview, followed tokenless workspace and
  download links, refreshed `/w/{ref}`, exercised pause/resume/interrupt/terminate, queued continuation, and
  verified the continued worker output was visible.
- Visible outcome: project/worker pages rendered; provider-backed worker page showed running then
  completed state; artifact preview showed the public marker; fixture and provider-backed runs opened
  or downloaded the requested artifact formats; input materialization appeared in user-visible output;
  workspace controls stayed visible after reload; continuation output appeared on the worker detail
  surface; terminate transitioned an active synthetic run truthfully.
- Expanded/detail state: artifact inventory, API `/live`, run state, DB counts, evidence JSON,
  document signatures, and browser console/request failures were inspected by the harnesses.
- Persistence/reload result: `/w/{ref}` refresh persisted controls and workspace view; downloaded
  files remained available through short-link indirection; continuation reused the same workspace.
- Backend/log/DB confirmation: host Codex and host Claude smokes observed `running -> completed`
  for initial and continuation runs; the provider-backed Codex and Claude browser bridges observed
  the same first/continuation state transition with `evidence_result=pass` and transcript metadata;
  fixture SQLite contained project, worker, runs, and events; Docker Claude probe recorded coherent
  `profile=claude-code`, `execution_mode=docker`, and `provider_auth_missing`.
- Final model/runtime wording check: completed live smokes required `FINAL REPORT:` and matching
  artifact markers; Docker Claude returned an honest credential failure instead of success-shaped
  wording.
- Substitution check: provider-free browser evidence proves the full local visible UI contract,
  provider-backed CLI smokes prove live Codex/Claude execution, and provider-backed Codex/Claude
  browser bridges prove the combined host paths. This report does not claim cloud deployment,
  GitHub push, or parent pin release.

## Automated Evidence

Passed:

```bash
node --check qa/glasshive_deep_research/scripts/local_browser_user_grade_qa.cjs
node qa/glasshive_deep_research/scripts/local_browser_user_grade_qa.cjs --state-root "$TMPDIR/glasshive-local-browser-user-grade-20260622-input-terminate-rerun3" --timeout-ms 70000
viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python qa/glasshive_deep_research/scripts/local_user_grade_browser_qa.py
WPR_CODEX_CLI_XHIGH_ROUTE_PROVEN=1 GLASSHIVE_HOST_RUN_TIMEOUT_SEC=480 viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python qa/glasshive_deep_research/scripts/live_provider_browser_wait_continue_qa.py --profile codex-cli --execution-mode host --effort xhigh --artifact-mode full-matrix --delay-seconds 5 --running-timeout-sec 90 --first-timeout-sec 900 --continue-timeout-sec 900 --poll-sec 5
GLASSHIVE_HOST_RUN_TIMEOUT_SEC=480 viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python qa/glasshive_deep_research/scripts/live_provider_browser_wait_continue_qa.py --profile claude-code --execution-mode host --effort max --artifact-mode full-matrix --delay-seconds 5 --running-timeout-sec 90 --first-timeout-sec 900 --continue-timeout-sec 900 --poll-sec 5
viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python qa/glasshive_deep_research/scripts/run_public_safe_benchmarks.py --state-root "$TMPDIR/glasshive-public-safe-benchmarks"
cd viventium_v0_4/GlassHive/runtime_phase1 && ./.venv/bin/python -m pytest tests/test_bootstrap.py tests/test_run_evidence.py tests/test_profile_runtime.py -q
cd viventium_v0_4/GlassHive/runtime_phase1 && ./.venv/bin/python -m pytest tests/test_api.py tests/test_mcp_server.py tests/test_models.py tests/test_bootstrap.py tests/test_run_evidence.py tests/test_profile_runtime.py -q
cd viventium_v0_4/GlassHive/runtime_phase1 && ./.venv/bin/python -m pytest tests/test_api.py::test_evidence_failure_is_not_recovered_as_completed tests/test_profile_runtime.py::test_collect_completed_run_recovers_from_latest_run_artifacts tests/test_profile_runtime.py::test_collect_completed_run_with_explicit_run_id_ignores_previous_finished_run tests/test_profile_runtime.py::test_openclaw_collect_completed_run_recovers_final_json_without_exit_file -q
WPR_RUN_CLI_LIVE_TESTS=1 WPR_CODEX_CLI_XHIGH_ROUTE_PROVEN=1 ./.venv/bin/python -m pytest tests/test_cli_live.py::test_live_codex_worker_can_run_and_resume -q
cd viventium_v0_4/GlassHive/runtime_phase1 && ./.venv/bin/python -m pytest tests/test_run_evidence.py::test_run_evidence_classifies_structured_provider_rate_limit tests/test_run_evidence.py::test_run_evidence_classifies_structured_provider_overload tests/test_run_evidence.py::test_run_evidence_classifies_structured_provider_content_filter tests/test_run_evidence.py::test_run_evidence_classifies_structured_provider_auth_missing tests/test_run_evidence.py::test_run_evidence_classifies_structured_provider_request_rejected tests/test_profile_runtime.py::test_runtime_error_classifies_unsupported_runtime_configuration -q
cd viventium_v0_4/GlassHive/runtime_phase1 && ./.venv/bin/python -m pytest tests/test_run_evidence.py::test_run_evidence_allows_internal_notes_when_final_answer_requested_in_chat tests/test_run_evidence.py::test_coverage_compliance_counts_structured_final_answer_items tests/test_run_evidence.py::test_run_evidence_classifies_zero_exit_structured_provider_error tests/test_api.py::test_fresh_user_artifact_deliverable_accepts_standard_deliverable_roots tests/test_api.py::test_worker_ui_redacts_nested_runtime_paths_unless_diagnostics_enabled -q
cd viventium_v0_4/GlassHive/runtime_phase1 && ./.venv/bin/python -m pytest tests/test_run_evidence.py::test_run_evidence_does_not_classify_benign_provider_terms_in_success_output tests/test_run_evidence.py::test_run_evidence_accepts_markdown_decorated_final_report_marker tests/test_run_evidence.py::test_coverage_compliance_warns_when_count_unverifiable_in_professional_artifact tests/test_run_evidence.py::test_coverage_compliance_fails_when_table_rows_below_requested_range tests/test_api.py::test_fresh_user_artifact_deliverable_accepts_standard_deliverable_roots -q
cd viventium_v0_4/GlassHive/runtime_phase1 && ./.venv/bin/python -m pytest tests/test_docker_sandbox.py::test_safe_docker_exec_env_preserves_claude_headless_oauth_only tests/test_profile_runtime.py::test_claude_code_runtime_passes_headless_oauth_without_api_key_mode tests/test_profile_runtime.py::test_claude_code_runtime_passes_gateway_headers -q
```

Additional broad suites passed during this pass:

```bash
cd viventium_v0_4/GlassHive/runtime_phase1 && ./.venv/bin/python -m pytest tests -q
cd viventium_v0_4/GlassHive/frontends/glass-drive-ui && uv run pytest -q
viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python -m pytest tests/release/test_qa_operating_contract.py tests/release/test_qa_results_public_safety.py -q
git -C viventium_v0_4/GlassHive diff --check
viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python -m py_compile qa/glasshive_deep_research/scripts/live_provider_browser_wait_continue_qa.py qa/glasshive_deep_research/scripts/local_user_grade_browser_qa.py qa/glasshive_deep_research/scripts/run_public_safe_benchmarks.py
node --check qa/glasshive_deep_research/scripts/local_browser_user_grade_qa.cjs
```

Focused regressions added or covered:

- Docker/workstation success fails when evidence contract fails.
- Docker/workstation success fails when evidence cannot be written.
- Docker/workstation success fails when the constraint ledger cannot be written.
- Empty bootstrap upload rejection with explicit `allow_empty` escape hatch.
- Host projected empty source-file rejection.
- Zero-byte required CSV does not satisfy completion compliance.
- Planning/spec source-window omission fails when the ledger is strict; `constraint-ledger` reference passes.
- Final-output and extracted generated-artifact text are scanned for source-window drift; current
  regressions cover direct final text and generated XLSX workbook text.
- Structured progress text that merely mentions `FINAL REPORT:` no longer counts as a final report;
  the marker must be line-anchored in a real final response field.
- Coverage-range expectations such as requested row/entity counts are extracted generically and
  checked against deliverable CSV/TSV/JSON/XLSX/Markdown/HTML tables.
- Codex xhigh route fallback persists effort projection telemetry.
- Timeout/interruption evidence records transcript metadata and recovered timeout policy.
- Structured provider rate-limit and overload/response-failure evidence is recorded as a retryable
  failure classification with diagnostic summary and recovery guidance. Content-filter,
  auth-missing, request-rejected, zero-exit structured provider errors, and
  unsupported-runtime-configuration classes are also preserved without claiming success. Benign
  provider/error terms and false structured error fields such as `is_error: false`, `error: "none"`,
  or `failure: "false"` in successful assistant output are not treated as provider failures.
- Markdown-decorated `FINAL REPORT:` markers such as heading/bold forms are accepted while mid-line
  progress chatter remains rejected.
- Explicit coverage counts fail when extractable table/list evidence is below the requested minimum,
  but warn instead of hard-failing when a valid professional artifact/prose answer does not expose
  an extractable count.
- Final-answer-only chat tasks can satisfy explicit count coverage through structured final-output
  lists/tables and are not falsely failed because internal notes exist.
- Provider/runtime recovery can promote a fresh completed user deliverable from standard
  `artifacts/`, `reports/`, or `output/` roots after a retryable provider/runtime capture failure.
  Support-only folders such as `research/`, `planning/`, `specs/`, and `notes/` cannot trigger that
  recovery path by themselves.
- Nested runtime path maps are redacted from normal worker UI/live payloads and remain visible only
  through explicit diagnostics mode.
- Active-run heartbeat JSON records heartbeat sequence, transcript file byte/mtime metadata, tail
  hashes, last-output timestamp, and quiet duration so long or stuck runs are diagnosable without
  exposing raw transcript text.
- Codex and Claude Code worker launch now sends the contracted instruction through stdin instead of
  argv, and OpenClaw launch uses a generic private instruction-file pointer instead of raw prompt
  argv, preventing private prompts from appearing in local process listings while preserving redacted
  command/evidence telemetry.

## Findings

- Successful Docker/workstation CLI runs now use the same blocking `evidence_result` gate as
  host-native runs.
- Successful runs now fail truthfully when the constraint ledger or run evidence cannot be written
  or read. Timeout/provider/runtime failure paths preserve their original failure class.
- Bootstrap/user-file materialization rejects empty inline, base64, or source-projected files unless
  the file entry explicitly sets `allow_empty: true`.
- Zero-byte user deliverables are excluded from artifact discovery.
- Strict source/date constraints now fail when a planning/spec/delegation file omits both a
  `constraint-ledger` reference and a restatement of the strict constraint. This is generic and
  prevents constraint loss before final artifacts exist.
- Constraint compliance now scans the final captured output plus extracted generated XLSX/DOCX/PPTX/PDF
  text where local tooling is available, in addition to workspace Markdown/CSV/JSON/HTML text.
  Missing or failed binary-text extraction is reported as a `WARN` instead of a silent pass.
- Completion detection now requires a line-anchored `FINAL REPORT:` marker in final output or
  structured final response fields, avoiding false success from progress/instruction chatter.
- Public-safe benchmark coverage expanded from seven to fourteen provider-free cases, adding
  notes-only deliverable intent, strict planning window widening, structured final-marker
  false-positive, workbook-hidden source-window drift, binary extraction warning, and coverage range
  pass/fail controls.
- Content hygiene now skips raw support web-capture snapshots while still scanning real deliverables
  and worker-authored structured research data, so preserved crawl caches do not drown out final
  artifact quality signals.
- Raw support web-capture snapshots are also skipped by the shared workspace text scanner used for
  source-window and seed checks, while normal `research/` notes remain scanned.
- Codex effort projection is recorded in evidence JSON and host `run.started` audit payloads.
- Stopped-run evidence preserves recovered timeout policy and transcript metadata.
- Active-run status now includes bounded transcript progress metadata, including byte counts,
  modification time, tail hash, last-output timestamp, and quiet duration. Focused regressions cover
  timeout and foreground preview-server/port-failure transcript preservation.
- Host and Docker Codex/Claude launch paths now avoid prompt-in-argv leakage, and OpenClaw paths use
  only a private instruction-file pointer in argv. Focused regressions verify host stdin delivery,
  Docker per-run `instruction.stdin` redirection with `0600` permissions, OpenClaw file-pointer
  command construction, active-session instruction redaction, local-path log scrubbing, and absence
  of private prompt text or local paths from argv/evidence command display and transcript tails.
- Service-level queue recovery no longer masks an evidence-check failure: a runtime success that
  fails the evidence gate remains failed, even when a zero-exit recovery probe could otherwise find
  fresh artifacts.
- Recovered zero-exit completions now require readable per-run evidence and a constraint ledger
  before they can be reported as completed.
- Workspace-relative transcript metadata now resolves against the run workspace, so relative
  constraint-ledger paths are not falsely marked missing in evidence JSON.
- The provider-backed Codex and Claude host browser bridges passed running-state visibility, reload
  while running, artifact preview, tokenless short-ref workspace navigation, continuation, evidence
  status, transcript metadata, and public-visible redaction checks.
- Missing Python module failures such as optional import mistakes are classified as runtime
  dependency blockers instead of generic unknown failures.
- Docker Python tooling now includes `requests` alongside document/artifact tooling, and worker
  guidance still requires providers to verify optional non-stdlib imports before depending on them.
- Private long-form host reruns are kept out of the public repo. Sanitized outcome: Codex xhigh
  completed with valid deliverables and advisory support-data hygiene warnings; Claude Opus max
  initially failed strict source-window compliance, then a same-workspace continuation repaired the
  deliverables and produced passing evidence with no warnings.
- ClaudeViv review-only pass first hit the helper's structured-output retry limit; a compact Opus
  max retry completed with no blockers. Its two non-blocking follow-ups, raw support captures in
  gating scans and string-valued false error fields, were fixed with regressions before signoff.
- Docker Claude Opus max failed closed with `provider_auth_missing` because this shell did not have
  a headless credential for containerized Claude CLI auth.

## Official Reference Check

- OpenAI Codex config reference still treats reasoning effort as structured config, including
  `model_reasoning_effort="xhigh"` when supported by the active route:
  [OpenAI Codex configuration reference](https://developers.openai.com/codex/config-reference).
- Claude Code Skills remain capability folders with instructions/scripts/resources, so GlassHive
  should discover and present available skills without hardcoding stale branded guarantees:
  [Claude Code Skills documentation](https://docs.anthropic.com/en/docs/claude-code/skills).
- MCP authorization guidance reinforces auth/origin/local-server safety for exposed tools:
  [MCP authorization documentation](https://modelcontextprotocol.io/docs/tutorials/security/authorization).
- Playwright best practices still emphasize resilient user-visible testing:
  [Playwright best practices](https://playwright.dev/docs/best-practices).
- OpenAI and Anthropic eval guidance reinforces success criteria, datasets/cases, traces, graders,
  and repeated eval runs rather than overfitting a single benchmark:
  [OpenAI evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)
  and [Anthropic agent evals guidance](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents).

## Public-Safety Review

- [x] No LibreChat code or image was modified in this hardening pass.
- [x] This report uses synthetic public-safe QA descriptions and avoids private prompts, customer
  data, cloud evidence, and unrelated environments.
- [x] Artifact/browser evidence is summarized without raw signed-link query strings, runtime tokens,
  local home paths, or raw private benchmark content.
- [x] Private long-form benchmark evidence is kept out of this public report and recorded only as a
  private QA gate.
- [x] Remaining credential/private-evidence gaps are stated separately from this local approval
  result; no cloud deploy, GitHub push, or LibreChat image/code change is claimed.
