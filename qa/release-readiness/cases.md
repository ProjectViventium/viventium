# Release Readiness QA Cases

## Case ID Convention

Use `REL-NNN` for release-readiness and public-push packaging checks.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `REL-001` | Public/private boundary | No private identifiers, secrets, raw logs, or local paths enter public history | Parent repo | `git diff --check` and public/private pattern scans | PASS 2026-05-12 |
| `REL-002` | Nested repo boundary | Nested component diffs are reviewed independently before parent pin update | LibreChat nested repo | `git diff --check`, targeted tests, line-by-line review | PASS 2026-05-12 |
| `REL-003` | Reproducible component pin | Parent manifest points to the pushed nested commit | Parent `components.lock.json` | Git status/commit SHA inspection | PASS 2026-05-12 |
| `REL-004` | User-grade QA evidence | Browser-visible background-agent behavior works without contradictory main errors | Web UI | `node qa/background_agents/evals/run-visible-cards-browser-qa.cjs --headless` | PASS 2026-05-11 local / 2026-05-12 UTC |
| `REL-005` | Project boundary contamination | Viventium public tree contains no cross-project brand/account markers | Parent repo plus nested source tree | `python3 -m pytest tests/release/test_project_boundary_contamination.py -q` | PASS 2026-05-12 |
| `REL-006` | Zero open required gates | Release/default Parallel Work remains dark and focused while any required case is open; explicit local QA stays marked pre-gate | Release CLI, config schema, QA catalogs | `python3 scripts/viventium/parallel_work_release_gate.py --mode release` | PARTIAL 2026-08-22 — RED-first evaluator automation is implemented; installed claim-gate case `REL-UC-004` is not run. |

## `REL-001` - Public Diff Hygiene

- Requirement: `AGENTS.md` public/private boundary
- Risk covered: public branch leaks private account data, paths, secrets, raw logs, screenshots, or local runtime output
- Preconditions: parent working tree has intended changes only
- Steps:
  1. Run `git diff --check`.
  2. Scan tracked diffs and intended untracked artifacts for private markers.
  3. Review any broad-scan hits and classify placeholders separately from private values.
- Expected result: only synthetic values, hashes, and documented placeholders remain.
- Forbidden result: real account identifiers, credentials, owner paths, raw logs, screenshots, private URLs, or generated runtime files are staged.
- Evidence to capture: sanitized scan summary and reviewer findings.
- Automation: shell scans plus independent review.
- Last run: PASS 2026-05-12. Parent, LibreChat, and GlassHive diff checks passed; added-line and
  PR-base scans found no real private values.

## `REL-005` - Project Boundary Contamination

- Requirement: Viventium work must stay Viventium-scoped across repo code, docs, tests, and QA
  evidence.
- Risk covered: QA accounts, brand names, domains, or private context from another project enter
  Viventium source or public artifacts.
- Preconditions: intended source and QA artifact changes are present.
- Steps:
  1. Run `python3 -m pytest tests/release/test_project_boundary_contamination.py -q`.
  2. Review any hits and remove or replace them with Viventium-scoped synthetic placeholders.
- Expected result: zero cross-project marker hits in the public tree.
- Forbidden result: another project's QA account, brand, domain, customer context, or private
  operating state appears in Viventium code, docs, tests, or QA artifacts.
- Evidence to capture: pass/fail line from the release test.
- Last run: PASS 2026-05-12.

## `REL-002` - Nested Component Boundary

- Requirement: nested repos have separate histories and must be reviewed/committed independently
- Risk covered: parent PR claims a fix while nested source remains dirty or unpushed
- Preconditions: nested repo has current implementation diff
- Steps:
  1. Inspect nested `git status --short --branch`.
  2. Review nested diff line by line.
  3. Run the targeted nested test suites for changed surfaces.
  4. Commit and push nested branch before parent pin update.
- Expected result: nested origin branch contains the reviewed implementation commit.
- Forbidden result: parent commit without matching nested pushed commit and pin.
- Evidence to capture: nested commit SHA and PR link.
- Automation: git inspection plus targeted Jest/Pytest suites.
- Last run: PASS 2026-05-12. Independent subagent and ClaudeViv reviews found blockers; those were
  fixed or converted into explicit release gates before nested commits.

## `REL-003` - Parent Pin Matches Nested Commit

- Requirement: `components.lock.json` reflects shipped nested component commits
- Risk covered: fresh clone installs old nested code while parent docs/tests claim the new behavior
- Preconditions: nested component commit has been pushed to `origin`
- Steps:
  1. Update the `LibreChat` `ref` in `components.lock.json` to the pushed nested commit.
  2. Inspect the parent diff.
  3. Commit parent after the nested repo is committed.
- Expected result: parent manifest references the exact nested commit intended for review.
- Forbidden result: stale ref or unreviewed local nested changes.
- Evidence to capture: parent diff and nested SHA.
- Automation: git inspection.
- Last run: PASS 2026-08-30. Parent and Native payload manifests point at merged LibreChat commit
  `8c0b30234f5e99a56a1a0bac1f791575e60eea35`; the lifecycle inventory records the same ref.

## `REL-004` - Browser-Visible Background Cards

- Requirement: QA evidence must prove the user-visible browser path, not only backend state
- Risk covered: background cards or results exist in logs/DB but the user sees missing cards, contradictory copy, or a main error banner
- Preconditions: local app running; synthetic/local QA account available through private env; no private prompt text in public report
- Steps:
  1. Open the app with the Playwright harness.
  2. Send a synthetic prompt that should visibly activate Red Team and Confirmation Bias.
  3. Verify both named cards, why/result/status details, no forbidden main wording, no main error banner, and reload persistence.
- Expected result: both cards are visible by name before and after reload; stored `messages.content`
  contains matching terminal cortex parts with successful insights; no main-answer error banner or
  critical HTTP error appears.
- Forbidden result: missing cards, terminal error cards in place of successful insights,
  contradictory "I cannot run/show background agents" copy, visible request error, or persistence
  loss.
- Evidence to capture: dated public-safe hash-only report.
- Automation: `node qa/background_agents/evals/run-visible-cards-browser-qa.cjs --headless`.
- Last run: PASS 2026-05-11 local / 2026-05-12 UTC. The browser showed both required named cards,
  expanded detail sections, terminal status text, parent answer visibility before and after reload,
  stored successful terminal cortex insights, Groq-first activation config with no drift, and no
  critical HTTP errors. ACT-21 latest-user browser QA also passed: setup cards appeared, the simple
  `TEST_OK` turn answered before and after reload, and no stale-history cortex cards attached to
  that latest turn. This is local synthetic evidence; final public release remains gated on
  committed diffs, nested pin agreement, public/private scans, and review-only checks.

## `REL-006` - Zero Open Required Parallel Work Gates

- Requirement: [Parallel Work rollout and completion gates](../../docs/requirements_and_learnings/55_Parallel_Work_Orchestration.md#rollout-and-completion-gates).
- Risk covered: a release or default exposure says Ready, enables Parallel Work, or defaults an
  account to parallel while required user-grade evidence is still `NOT RUN`, `FAIL`, `PARTIAL`,
  `BLOCKED`, missing, or unknown.
- Preconditions: current QA catalogs and `config.schema.yaml` are present.
- Steps:
  1. Run `python3 scripts/viventium/parallel_work_release_gate.py --mode release`.
  2. Confirm every `PWK-*`, every `REL-*`, `TR-014`, `EMO-UC-047`, and `EMO-UC-048` appears in the result.
  3. Confirm any open gate exits nonzero and names its owner case.
  4. Confirm schema defaults remain availability `false` and mode `focused`.
  5. For local testing only, run with `--mode local-qa --allow-local-qa-override` and confirm the
     result says **PRE-GATE / NOT READY**.
  6. Put each case result manifest and referenced proof files under the private App Support
     `qa/evidence/` directory, then record it with
     `bin/viventium qa-evidence record --manifest <private-result.json>`. The command verifies the
     files, requires explicit local-QA mode, and binds the receipt to the active installed candidate.
  7. For `REL-UC-004`, activate its exact expiring session with
     `bin/viventium qa-control activate --case-id REL-UC-004`, restart the installed runtime, and run
     `bin/viventium qa-control inject-release-claim`. Verify the prompt mismatch and synthetic disk
     pressure both fail every claim path, then run `restore-release-claim`, clear the exact session,
     and restart. Never fill the real disk.
- Expected result: release/default fails closed until zero required gates are open. Explicit local QA
  can exercise the feature without changing or weakening shipped defaults. Release receipts require
  a publisher-pinned asymmetric signature, independently signed producer/service evidence, and an
  external monotonic witness; a same-user-readable local HMAC never authorizes release.
- Forbidden result: implicit override, missing-case pass, unknown status treated as pass, local QA
  called Ready, self-signed or replayed release evidence, private paths in JSON, or source defaults
  changed to available/parallel.
- Evidence to capture: public-safe JSON result, focused test output, config defaults, source/nested
  pin/build/installed identities, and the visible claim wording under `REL-UC-004`.
- Last run: `PARTIAL` 2026-08-22. The evaluator and focused automation were run; the installed
  release-claim failure matrix remains `NOT RUN`.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Release Readiness. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `REL-UC-001` | On Parent repo, verify that public/private boundary. | owning requirement for `REL-001` / `REL-001` | Parent repo | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to REL-001. | No private identifiers, secrets, raw logs, or local paths enter public history | NOT RUN (cataloged 2026-05-18; next feature run required) |
| `REL-UC-002` | On Parent repo plus nested source tree, try project boundary contamination with missing setup, missing auth/config, empty state, or a degraded dependency. | owning requirement for `REL-005` / `REL-005` | Parent repo plus nested source tree | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to REL-005. | The user sees an honest setup, retry, or degraded-state result for REL-005; no fake success is accepted. | NOT RUN (cataloged 2026-05-18; next feature run required) |
| `REL-UC-003` | After nested repo boundary, refresh, restart, retry, or switch linked surfaces and verify persistence/parity. | owning requirement for `REL-002` / `REL-002` | LibreChat nested repo | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to REL-002. | REL-002 remains correct after the persistence or parity step and final wording matches evidence. | NOT RUN (cataloged 2026-05-18; next feature run required) |
| `REL-UC-004` | Leave one PARTIAL Parallel Work case, one prompt-layer mismatch, and injected disk pressure, then request release, completion, and readiness through every supported claim path. | Zero-open gate / `REL-006`, `PWK-018` | Public CLI, install summary, release check, installed Web/Telegram status wording | Evaluator JSON, prompt registry result, typed disk probe, config defaults, visible wording, source/nested pin/build/installed identities | Every claim fails closed, names all three blockers, keeps Parallel Work dark and default focused, and never says Ready or Complete. Recovery closes only the blockers that have current evidence. | NOT RUN (cataloged 2026-08-22; required before release). |

## Release Test Traceability

- `tests/release/test_agent_sync_review_contract.py`
- `tests/release/test_bootstrap_components.py`
- `tests/release/test_common_sh.py`
- `tests/release/test_cursor_claude_bridge.py`
- `tests/release/test_git_helper.py`
- `tests/release/test_librechat_package_rebuild_contract.py`
- `tests/release/test_local_web_search_compose.py`
- `tests/release/test_ms365_launcher_contract.py`
- `tests/release/test_no_runtime_nlu.py`
- `tests/release/test_parallel_work_release_gate.py`
- `tests/release/test_personal_account_qa_cleanup_plan.py`
- `tests/release/test_personal_account_qa_recovery.py`
- `tests/release/test_private_repo_resolution_contract.py`
- `tests/release/test_productivity_activation_live_eval.py`
- `tests/release/test_productivity_activation_source_of_truth.py`
- `tests/release/test_project_boundary_contamination.py`
- `tests/release/test_public_bootstrap_manifests.py`
- `tests/release/test_qa_release_attestation.py`
- `tests/release/test_rel_uc_004_semantic_verifier.py`
- `tests/release/test_release_catalog_semantic_verifier.py`
- `tests/release/test_startup_secret_redaction.py`
