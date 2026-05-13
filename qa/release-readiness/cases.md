# Release Readiness QA Cases

## Case ID Convention

Use `REL-NNN` for release-readiness and public-push packaging checks.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `REL-001` | Public/private boundary | No private identifiers, secrets, raw logs, or local paths enter public history | Parent repo | `git diff --check` and public/private pattern scans | 2026-05-12 PASS |
| `REL-002` | Nested repo boundary | Nested component diffs are reviewed independently before parent pin update | LibreChat nested repo | `git diff --check`, targeted tests, line-by-line review | 2026-05-12 PASS |
| `REL-003` | Reproducible component pin | Parent manifest points to the pushed nested commit | Parent `components.lock.json` | Git status/commit SHA inspection | 2026-05-12 PASS |
| `REL-004` | User-grade QA evidence | Browser-visible background-agent behavior works without contradictory main errors | Web UI | `node qa/background_agents/evals/run-visible-cards-browser-qa.cjs --headless` | 2026-05-11 local / 2026-05-12 UTC PASS |
| `REL-005` | Project boundary contamination | Viventium public tree contains no cross-project brand/account markers | Parent repo plus nested source tree | `python3 -m pytest tests/release/test_project_boundary_contamination.py -q` | 2026-05-12 PASS |

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
- Last run: 2026-05-12 PASS. Parent, LibreChat, and GlassHive diff checks passed; added-line and
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
- Last run: 2026-05-12 PASS.

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
- Last run: 2026-05-12 PASS. Independent subagent and ClaudeViv reviews found blockers; those were
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
- Last run: 2026-05-12 PASS. Parent manifest now points at the pushed LibreChat and GlassHive
  feature-branch commits.

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
- Last run: 2026-05-11 local / 2026-05-12 UTC PASS. The browser showed both required named cards,
  expanded detail sections, terminal status text, parent answer visibility before and after reload,
  stored successful terminal cortex insights, Groq-first activation config with no drift, and no
  critical HTTP errors. ACT-21 latest-user browser QA also passed: setup cards appeared, the simple
  `TEST_OK` turn answered before and after reload, and no stale-history cortex cards attached to
  that latest turn. This is local synthetic evidence; final public release remains gated on
  committed diffs, nested pin agreement, public/private scans, and review-only checks.
