# Live WHOOP Agent QA Run - 2026-07-27

## Summary

- Result: `PASS` for protected activation, installed config parity, real-browser inventory use, and
  cognitive-value A/B; `PARTIAL` for `VHP-007` persistence/degraded behavior.
- Build/source under test: public Viventium-Health component commit
  `a8c14028069e91405c570545866ebfa206b4ee7d`, merged LibreChat commit
  `6ba9ee1cf92cce7946e4204d499629dc78fc4fe7`, and the parent Health integration PR branch.
- Runtime/artifact under test: installed owner-local Health executable, compiled Viventium config,
  restarted local-prod Viventium runtime, and main-agent tool bindings.
- Environment: local macOS Viventium runtime, real owner-authorized WHOOP API evidence, and real
  logged-in Chrome UI.
- Tester: Codex with a separated five-axis review; Claude review-only was unavailable because the
  provider usage limit blocked both Desktop and CLI attempts.
- Related change: WHOOP-first raw-file evidence component and bounded read-only parent MCP wiring.

No health value or body, account or device identity, OAuth value, archive or conversation
identifier, hash, private screenshot, or owner-specific filesystem path appears in this report.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `VHP-001` | PASS | 158-case focused compiler/Health/manifest suite | Direct and generated MCP definitions matched. |
| `VHP-002` | PASS | Source contract and live tool calls | Main agent had server discovery and exactly three bounded read tools; no auth, pull, write, delete, path, memory, network, or command tool. |
| `VHP-003` | PASS | All 12 lock refs matched public main; release suite 41/41 | Reviewed component identities and shipped manifest policy aligned. |
| `VHP-004` | PASS | Live A/B/C compare, tools-only dry run/apply, post-compare | Four bindings added to the main agent, zero removed; unrelated agent/user fields preserved. |
| `VHP-005` | PASS | Real Chrome inventory conversation | Visible tool states and privacy-bounded final inventory matched the request. |
| `VHP-006` | PASS | Separate evidence-enabled and no-evidence Chrome conversations | Evidence path added useful sourced planning; control invoked no tools and made no current-health claim. |
| `VHP-007` | PARTIAL | Supported compile/restart, Chrome navigation/refresh, read-only persistence inspection | Visible persistence passed; missing-executable path was not run and one visibly completed message retained an unfinished persistence flag. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `VHP-UC-001` | Check current capture status/resources without asking for measurements | Real Chrome chat plus list-runs/list-records | PASS | Complete status, six resource names, capture time, and integrity presence only | Live tool states, generated config, component run contract | None |
| `VHP-UC-002` | Request a concise plan from only relevant current evidence | Real Chrome chat plus two bounded read-record calls | PASS | Actionable, source/capture-time-cited, uncertainty-aware, non-diagnostic answer | Expanded tool states, private archive integrity already proven by component QA | None |
| `VHP-UC-003` | Ask what can be known while forbidding tools, memory, and assumptions | Fresh real Chrome chat | PASS | One concise refusal to infer current recovery | Zero tool calls; persisted control message finished | None |
| `VHP-UC-004` | Use Health before executable/auth is available and recover | Component CLI test; parent browser path not run | PARTIAL | Component missing-auth wording was explicit | Synthetic missing-auth test passed | Parent missing-executable visible wording remains unproven |
| `VHP-UC-005` | Refresh/revisit after runtime restart | Restarted runtime and real Chrome refresh | PARTIAL | Tool states and final text remained visible | Runtime healthy; generated config present; one evidence message retained `unfinished: true` | Align stored completion flag with visibly complete response |
| `VHP-UC-006` | Install/upgrade from reviewed component identities | Compiler/manifests/public refs | PASS | Not a separate UI action in this run | Source, lock, native manifest, and 12 public main tips matched | Fresh clean-machine install remains a release-wide gate, not a Health-only claim |
| `VHP-UC-007` | Prepare public review evidence | Public diff and QA suites | PASS | Public report contains sanitized results only | Public-safety tests and identifier scan | None |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Viventium-Health parent evidence integration.
- Requirement: `docs/requirements_and_learnings/07_MCPs.md`, read-only bounded evidence with truthful
  provenance and no new health database or saved-memory write.
- Use case: inspect capture availability and use a relevant record for planning from the main agent.
- QA case: `VHP-004` through `VHP-007` and `VHP-UC-001` through `VHP-UC-007`.
- Expected result: protected tools-only activation, current evidence retrieval, useful
  uncertainty-aware non-diagnostic wording, restart persistence, and honest failure boundaries.
- Actual evidence: real Chrome tool use/A-B, healthy runtime restart, generated-config inspection,
  private persistence status inspection, 158 focused tests, 41 release tests, 37 productivity tests,
  and 12 exact public main refs.
- Remaining gap or fix: run the missing-executable browser case and investigate why one visibly
  complete evidence-rich assistant message retained an unfinished persistence flag.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Parent MCP source of truth; `VHP-001`–`VHP-007`; `VHP-UC-001`–`VHP-UC-007`. |
| Code owning path | Which code path owns the behavior? | Parent config compiler, merged LibreChat source-of-truth agent/tools policy, and component stdio MCP. |
| Docs and nested docs/repos | Which docs define expected behavior? | Parent MCP requirements plus component vision, spec, ADR, privacy policy, cases, and owner acceptance reports. |
| Scripts or harnesses | Which suites exercised it? | Health component unittest/live-contract suites, parent pytest suites, agent sync compare/dry-run/apply, and supported config compile/restart. |
| Local/external prerequisite state | Which dependency was proven? | Active owner WHOOP grant, installed Health executable, loaded daily schedule, and healthy Viventium web/API/playground services. |
| Logs | Which sanitized logs confirm or contradict the result? | Runtime health checks passed; no log output was used as a substitute for the browser result. |
| DB/state/persistence | Which stored state confirms it? | Control/inventory finished state and evidence tool-call names matched the UI; evidence answer retained the documented unfinished-flag anomaly. |
| Generated/shipped artifact | Which artifact was inspected? | Nested source YAML, compiled runtime YAML, private generated runtime YAML, parent lock, and native LibreChat pin. |
| Real user path | Which surface was used like a user? | Logged-in Chrome main-agent conversations after a real Viventium runtime restart. |
| Visual/UX comparison | Did UI match evidence? | Tool buttons, expanded tool states, final inventory/planning/control wording, and refreshed conversation state agreed with actual calls. |
| Not run / blocked | What remains unrun? | Missing-executable browser behavior, natural late WHOOP correction, and deliberate revoke/reconnect. |

## User-Grade Evidence

- Surface exercised: logged-in Chrome Viventium web chat using the real main agent and installed
  Viventium-Health stdio MCP.
- Real user path: after a supported runtime compile/restart, open a fresh chat, request a bounded
  capture inventory, run a separate relevant evidence-planning request, run a fresh no-tool control,
  navigate away, return, and refresh.
- Visible outcome: inventory and evidence-enabled answers were complete and appropriately scoped;
  the control made no unsupported recovery claim.
- Expanded/detail state: visible tool details showed list-runs/list-records and exactly two bounded
  read-record operations on the evidence path; private IDs, hashes, and content were inspected only
  on the private surface and are not reproduced here.
- Persistence/reload result: tool states and final text persisted after navigation/refresh; one
  visibly completed evidence response retained an unfinished backend flag.
- Local/external prerequisite state: WHOOP authorization, Health executable, generated config, and
  Viventium web/API/playground health were all active.
- Evidence retrieval classification, if applicable: successful non-empty provider retrieval; no
  provider-unavailable, timeout, rate-limit, auth/config, request-rejected, unsupported, or local
  prerequisite failure occurred in the browser run.
- Fallback path, if applicable: not applicable because the configured official provider and local
  connector were healthy; the explicit no-tool control was a comparison, not a fallback.
- Backend/log/DB confirmation: read-only persistence inspection confirmed tool names and the control's
  zero-tool state, and exposed the unfinished-flag anomaly; service health checks confirmed restart.
- Final model/runtime wording check: the evidence answer cited WHOOP and capture time, labeled the
  vendor value as an estimate rather than medical truth, stated uncertainty, and made no diagnosis.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests were supporting evidence, not substitutes for the required visible UI, detail state,
  persistence, and wording checks.

## Automated Evidence

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
VIVENTIUM_HEALTH_LIVE_CONTRACT=1 PYTHONPATH=src \
  python3 -m unittest tests.test_whoop_live_contract -v
uvx ruff check src tests
python3 -m compileall -q src tests
uv build --out-dir /tmp/viventium-health-dist-final

uv run --isolated --with pytest --with pyyaml python -m pytest \
  tests/release/test_config_compiler.py \
  tests/release/test_viventium_health_integration.py \
  tests/release/test_native_component_manifest.py -q
uv run --isolated --with pytest --with pyyaml python -m pytest \
  tests/release/test_public_bootstrap_manifests.py \
  tests/release/test_private_repo_resolution_contract.py \
  tests/release/test_qa_operating_contract.py::test_release_tests_have_central_qa_ownership \
  tests/release/test_qa_storage_guard.py -q
uv run --isolated --with pytest --with pyyaml python -m pytest \
  tests/release/test_ci_release_workflows.py tests/release/test_no_runtime_nlu.py -q
```

## Findings

- Defects: no connector or parent integration defect remained after review. The review removed a
  secret-bearing configure argument, corrected ordinary chat-retention wording, and tightened the
  exact Health-binding assertion before final reruns.
- Regressions: none in the affected suites or real browser paths.
- Flakes: none observed.
- Environment issues: the broader native-payload suite was also attempted; 185 cases passed and 24
  stopped at its intended 10-GiB free-space reserve gate on this host. The affected native component
  manifest checks passed inside the focused 158-case suite. Claude Desktop and CLI review-only paths
  were blocked by the provider usage limit; no Claude verdict is claimed.
- Residual risks: missing-executable browser wording and the stored unfinished flag remain open;
  naturally late provider correction and destructive revoke/reconnect remain component-level open
  gates so the active daily pool is not interrupted solely for QA.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, timestamps, statuses, and conclusions only.
