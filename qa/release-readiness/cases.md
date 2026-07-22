# Release Readiness QA Cases

## Case ID Convention

Use `REL-NNN` for release-readiness and public-push packaging checks.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `REL-001` | Public/private boundary | No private identifiers, secrets, raw logs, or local paths enter public history | Parent repo | `git diff --check` and public/private pattern scans | PARTIAL 2026-07-22; complete local parent-candidate inventory and public-safety review passed, while staged diff and remote parent-PR exactness remain under `REL-008` |
| `REL-002` | Nested repo boundary | Nested component diffs are reviewed independently before parent pin update | LibreChat and changed nested repos | `git diff --check`, targeted tests, line-by-line review | PARTIAL 2026-07-22; all 11 reviewed heads are clean, pushed, and hosted in open PRs with exact head parity. Corrected LibreChat `44ac1f7a...` passes 59 stream and 216 Viventium route tests locally plus all 15 hosted checks; independent approvals and merges remain open. |
| `REL-003` | Reproducible component pin | Parent manifest points to the pushed nested commit | Parent `components.lock.json` | Git status/commit SHA inspection | PARTIAL 2026-07-22; both parent manifests point to pushed LibreChat review head `44ac1f7a149e5a915e52f2f9f54fce5d38bab710`, and the other refs match their hosted review heads. Source/pin identity aligns for review; merged, built, shipped, and installed identity is unproved. |
| `REL-004` | User-grade QA evidence | Browser-visible background-agent behavior works without contradictory main errors | Web UI | `node qa/background_agents/evals/run-visible-cards-browser-qa.cjs --headless` | PASS 2026-05-11 local / 2026-05-12 UTC |
| `REL-005` | Project boundary contamination | Viventium public tree contains no cross-project brand/account markers | Parent repo plus nested source tree | `python3 -m pytest tests/release/test_project_boundary_contamination.py -q` | PASS 2026-07-21 in the focused frozen-candidate run |
| `REL-006` | Immutable payload privacy | The exact assembled installer payload contains no producer-machine paths, runtime logs/audits, bytecode caches, secrets, or personal state | Native payload tree and archive | payload assembler exclusions plus `verify_native_public_safety.py` byte/path scans | PARTIAL 2026-07-20; pre-fix payload fails the new gate and 77 focused producer/gate tests pass; rebuilt payload scan pending |
| `REL-007` | Dependency security and compatibility | A clean lockfile install has no moderate-or-higher production advisory and still passes affected runtime/tests/builds on supported Node | LibreChat manifests, lockfile, upload/provider paths, CI | `npm ci`, production `npm audit`, malformed-file regression, provider/package/API/client suites and builds | PARTIAL 2026-07-22; corrected exact LibreChat head `44ac1f7a...` passes 59 stream and 216 Viventium route tests locally and all 15 hosted checks, including actual Redis. Exact native payload install/artifact proof remains open. |
| `REL-008` | Candidate/PR exactness | Every public PR contains exactly the audited final-state diff; nested merge SHAs, parent pins, built payload, and installed evidence agree | All nested repos, parent manifest, workflows, payload | local/remote SHA and compare checks, PR-file review, CI, fresh-clone install/upgrade | PARTIAL 2026-07-22; 11 clean nested heads are hosted in open PRs with local/remote SHA parity and available CI evidence. Corrected LibreChat local and all 15 hosted checks passed; independent approvals, merges, post-merge pins, parent PR exactness, payload, and fresh install/upgrade remain open. |
| `REL-009` | CI provider-secret isolation | Proposed PR code and dependency lifecycle scripts cannot read live-eval provider credentials | GitHub Actions workflows | `test_ci_release_workflows.py` plus hosted environment/ruleset inspection | PARTIAL 2026-07-22; source/static contracts and exact hosted nested-head reachability pass. Protected-environment reviewers, secret scope, and live-eval execution remain unverified administrative/external gates. |

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
- Last run: PARTIAL 2026-07-22. Complete local parent-candidate inventory, diff hygiene, special-file
  and binary classification, and public-safety review found no real secret, private state, personal
  path, or unintended payload. Staged-diff inspection and remote parent-PR parity still belong to
  `REL-008` and have not run.

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
- Last run: PASS 2026-07-21 in the focused frozen-candidate run. The project-boundary test passed
  as part of 33 focused QA-contract, public-safety, install-label, and boundary tests.

## `REL-006` - Immutable Payload Public Safety

- Requirement: public/private boundary and immutable Easy Install payload contract
- Risk covered: a clean source tree produces an archive that leaks the build user's path or carries
  runtime audit/log/cache bytes that were never visible in the source diff.
- Preconditions: assemble the exact candidate through the owning production assembler in a
  detached/private build root.
- Steps:
  1. Assert prompt-bundle identifiers are stable and relative to the prompt root.
  2. Reject forbidden payload paths including runtime logs, `*-audit.json`, `__pycache__`, `.pyc`,
     and `.pyo` without excluding legitimate source packages merely named `logs`.
  3. Scan every payload byte for the exact producer workspace and temporary prefixes.
  4. Scan Viventium-owned/generated text for home/temp/private paths and high-confidence secrets.
  5. Repeat against the final archive and published workflow artifact.
- Expected result: zero finding, stable digest/file/byte ledger, and the same verifier runs in both
  candidate and release workflows.
- Forbidden result: source scans pass while the archive contains a machine path, audit record,
  runtime log, bytecode cache, or credential.
- Evidence to capture: pre-fix rejection, focused tests, final verifier output, tree/archive digests,
  file/byte counts, and workflow check.
- Last run: PARTIAL 2026-07-20. The new verifier rejects the exact pre-fix payload and 77 focused
  tests pass; the rebuilt exact candidate scan and clean-machine run remain in progress.

## `REL-007` - Dependency Advisory And Compatibility Gate

- Requirement: lockfile reproducibility and no known moderate-or-higher production dependency
  vulnerability in the shipped LibreChat runtime.
- Risk covered: clearing an audit by a blind override introduces a peer-major mismatch, Node engine
  incompatibility, upload denial of service, provider failure, or test-only ESM break.
- Preconditions: final LibreChat manifests and lockfile are aligned; CI and runtime Node versions
  are explicit.
- Steps:
  1. Install with `npm ci` and inspect the resolved `file-type`, Anthropic Vertex SDK, Google Auth,
     gaxios, and uuid graph.
  2. Run `npm audit --omit=dev --audit-level=moderate` and separately record dev-only residuals.
  3. Run the malformed ASF regression with a strict timeout and the affected upload/provider tests.
  4. Run complete API, package, schema/provider, client, and production build checks.
  5. Verify the native-candidate workflow runs the production audit.
- Expected result: production audit is clean, supported Node engines align, tests/builds pass, and
  no blanket transitive-major override is used.
- Forbidden result: vulnerable upload parsing remains reachable, gaxios/uuid is falsely declared
  fixed while an old Vertex peer remains, or the audit fix breaks clean install/test/build.
- Evidence to capture: resolved dependency graph, audit output, exact regression/broad-suite totals,
  build result, and workflow diff.
- Last run: PARTIAL 2026-07-22. Corrected exact LibreChat head `44ac1f7a...` passes 59 stream and
  216 Viventium route tests locally. Independent code review and Claude Desktop Fable 5 Extra found
  no remaining P0-P3 issue. All 15 hosted checks pass, including actual Redis; exact native
  payload/install identity remains open.

## `REL-008` - Final Candidate And PR Exactness

- Requirement: nested-repository, parent-pin, shipped-artifact, and installed-artifact alignment
- Risk covered: the reviewed tree differs from the pushed branch, a dirty historical commit leaks
  a scratch file, a squash/merge changes the component SHA, or fresh install still fetches old code.
- Preconditions: all implementation and QA edits have stopped; final candidates start from fetched
  public `main` and contain no unrelated history.
- Steps:
  1. Construct clean final-state branches from fetched `origin/main`; never publish a branch whose
     intermediate history contained quarantined material.
  2. Re-run per-file/line, secret/path, dependency, tests, builds, and artifact scans on those exact
     trees.
  3. Obtain the review-only Claude pass, commit with public-safe identity, push only to `origin`, and
     open PRs.
  4. Compare every remote PR head/diff with the audited local commit; wait for required checks.
  5. Merge nested PRs first, update parent refs/artifacts to merged SHAs, rerun fresh install/upgrade,
     then review and merge the parent PR.
- Expected result: exact local/remote SHA parity, clean PR files, green CI, merged nested refs in the
  parent, and clean fresh-clone install/upgrade evidence.
- Forbidden result: force-push/reset, direct-main bypass, stale pin, unreviewed cloud commit, or a
  dirty intermediate commit visible in remote history.
- Evidence to capture: branch bases/heads, per-PR compare/file/check results, merged SHAs, parent
  manifest, payload digest, and fresh-clone ledger.
- Last run: PARTIAL 2026-07-22. All 11 clean nested branches are hosted in open PRs and their remote
  head hashes matched the reviewed local commits. Available hosted checks were inspected. The
  independent approvals, merges, post-merge identities, parent PR,
  rebuilt payload, and fresh-clone install/upgrade proof remain open.

## `REL-009` - CI Provider-Secret Isolation

- Requirement: `40_Public_Private_Boundaries_and_License_Matrix.md` CI provider-secret boundary.
- Risk covered: a same-repository pull request changes npm lifecycle or eval code and exfiltrates
  `GROQ_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY` from a secret-bearing workflow.
- Preconditions: workflow source is present; hosted protections are reviewed separately by a release
  owner with repository-administration visibility.
- Steps:
  1. Confirm every `pull_request`/`pull_request_target` workflow contains no `secrets.*` reference.
  2. Confirm the secretless PR contract runs without provider credentials or npm lifecycle.
  3. Confirm the live workflow accepts only protected-default-branch push/manual events and targets
     the named protected environment; confirm it fetches and validates the exact parent-pinned
     LibreChat commit rather than skipping an absent nested checkout.
  4. Confirm dependency installation completes before provider secrets are injected into the one
     live-eval step, and confirm the live workflow disables npm lifecycle scripts and does not
     install Python packages.
  5. In GitHub settings, verify required environment reviewers, default-branch-only deployment,
     dedicated synthetic spend-limited environment secrets, and protected-branch review rules.
- Expected result: proposed PR code never receives provider secrets; trusted live eval remains
  available after protected review, with credentials scoped to the exact eval step.
- Forbidden result: any PR-reachable workflow references repository/environment secrets, any
  dependency installation step receives provider credentials, or the hosted environment permits an
  unprotected ref/direct write to reach the live job.
- Evidence to capture: RED/GREEN static test output, workflow diff, and sanitized hosted policy
  inspection without secret values.
- Last run: PARTIAL 2026-07-22. The split workflow, disabled npm lifecycle hooks, step-scoped secret
  boundary, and pass/failure/outage shell semantics pass 19/19 workflow tests. The current
  LibreChat pin is reachable at corrected hosted PR head `44ac1f7a...`.
  Hosted environment reviewers, protected-ref deployment policy, secret scope, and a trusted live
  eval were not changed or verified in this local source audit.

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
- Last run: PARTIAL 2026-07-22. All 11 reviewed nested worktrees were clean, their heads were pushed
  to open hosted PRs, and local/remote head parity was verified. Component-focused checks passed at
  those heads. Corrected LibreChat `44ac1f7a...` passes 59 stream and 216 Viventium route tests
  locally plus all 15 hosted checks; independent approvals and merges remain open.

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
- Last run: PARTIAL 2026-07-22. Both parent manifests point to corrected, pushed LibreChat review
  head `44ac1f7a149e5a915e52f2f9f54fce5d38bab710`, and all other managed refs match their clean hosted
  review heads. Source/pin and hosted-check identity align for review; prove merged, built,
  shipped, and installed identities before promoting this case to `PASS`.

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

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Release Readiness. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `REL-UC-001` | Review the intended public diff before staging or publication. | public/private boundary / `REL-001` | Parent repo | Diff hygiene, added-line sensitive-pattern scan, QA public-safety contracts | No private identifiers, secrets, raw logs, or local paths enter public history. | PARTIAL 2026-07-22; complete local parent-candidate review passed, while staged and remote parent-PR inspection remains under `REL-008`. |
| `REL-UC-002` | Scan the Viventium parent and nested source tree for another project's brand, account, or operating context. | project boundary / `REL-005` | Parent repo plus nested source tree | Boundary test, source/report review, public-safety scan | Only Viventium-scoped synthetic fixtures and public-safe examples remain. | PARTIAL 2026-07-22; local candidate and nested-delta reviews passed, including corrected LibreChat local and hosted checks, while post-merge pin and parent remote-PR exactness remain under `REL-008`. |
| `REL-UC-003` | Reconcile each nested candidate head with the parent pin, then compare the built, shipped, and installed identities. | nested boundary and reproducible pin / `REL-002`, `REL-003`, `REL-008` | All managed component repos, parent lock, payload, installed runtime | Source status/SHAs, parent refs, remote reachability, artifact digests, installed provenance | Every delivery surface carries the exact reviewed component identities without uncommitted or unpublished drift. | PARTIAL 2026-07-22; 11 clean hosted PR heads and current parent refs align, including corrected LibreChat `44ac1f7a...`, whose 15 hosted checks pass. Approvals, merges, post-merge pins, and built/shipped/installed parity remain open. |
| `REL-UC-004` | Open a pull request that changes activation/eval code, then run the live eval manually from the protected default branch. | `40_Public_Private_Boundaries_and_License_Matrix.md` / `REL-009` | GitHub Actions PR check and protected environment | Workflow source, check logs, environment deployment history, branch/ruleset settings, static regression | PR validation receives no provider credentials; only the reviewed protected-branch live step can access dedicated synthetic secrets. | PARTIAL 2026-07-22; source/static isolation passes, while protected-environment administration and a trusted live run remain unverified. |

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
- `tests/release/test_openclaw_bridge_release_truth.py`
- `tests/release/test_private_repo_resolution_contract.py`
- `tests/release/test_productivity_activation_live_eval.py`
- `tests/release/test_productivity_activation_source_of_truth.py`
- `tests/release/test_project_boundary_contamination.py`
- `tests/release/test_public_bootstrap_manifests.py`
