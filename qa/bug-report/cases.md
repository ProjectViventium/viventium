# Bug Report Workflow Cases

## BR-001: Bug Intake Captures Reproduction Details

- Requirement: `51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md`
- Surfaces: helper, CLI, GlassHive workflow
- Preconditions: user reports a local Viventium bug
- Steps: start bug-report workflow with what happened, steps, expected behavior, actual behavior, and details
- Expected Result: workflow creates `bug-report.md` with the supplied report details plus missing reproduction, evidence, impacted surface, and QA acceptance sections before implementation
- Forbidden Result: worker starts coding from a vague bug report without intake
- Evidence: dated report under `reports/`
- Last Run: 2026-05-14 local implementation QA - passed by CLI tests and native helper dialog QA

## BR-002: Bug Fix Uses Isolated Worktree

- Requirement: `51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md`
- Surfaces: CLI, git
- Preconditions: approved bug report
- Steps: approve implementation phase
- Expected Result: worker uses a fresh `bugfix/<slug>` worktree and leaves the user's primary checkout untouched
- Forbidden Result: branch switch, stash, or edits in the user's active checkout
- Evidence: dated report under `reports/`
- Last Run: 2026-05-14 local implementation QA - passed by CLI/git tests, including cancel cleanup

## BR-003: Helper Bug Report UX Is Understandable

- Requirement: `51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md`
- Surfaces: macOS helper
- Preconditions: helper is installed from the current checkout
- Steps: open Advanced > Report a Bug
- Expected Result: dialog asks for what happened, steps to reproduce, expected behavior, actual behavior, and other details with understandable placeholders/tooltips
- Forbidden Result: generic blank prompt that does not guide a non-technical user
- Evidence: dated report under `reports/`
- Last Run: 2026-05-14 local implementation QA - passed by native helper menu/dialog QA

## BR-004: Degraded Mode Is Explicit Before Bug Fix Work

- Requirement: `51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md`
- Surfaces: CLI, GlassHive boundary
- Preconditions: GlassHive host workers are unavailable and operator passes `--allow-degraded`
- Steps: start bug-report intake, then approve the report with `--allow-degraded`
- Expected Result: intake is created, approval creates an isolated bugfix worktree, and implementation remains blocked/degraded without silent direct CLI execution
- Forbidden Result: hidden non-GlassHive bug fixer or coding from vague report details
- Evidence: dated report under `reports/`
- Last Run: 2026-05-14 local implementation QA - passed

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Bug Report. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `BUGREPORT-UC-001` | Start a bug report from the helper or CLI with synthetic reproduction details and review the generated intake before implementation approval. | `51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md` / `BR-001`, `BR-003` | macOS helper dialog or `bin/viventium bug-report start` | Intake markdown summary, helper/CLI output, workflow state, and dated QA report | The user sees guided fields for what happened, reproduction steps, expected/actual behavior, impacted surface, evidence, and QA acceptance before any coding starts. | 2026-05-14 local implementation QA - passed |
| `BUGREPORT-UC-002` | Approve a synthetic bug report when GlassHive workers are unavailable or degraded. | `51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md` / `BR-002`, `BR-004` | CLI workflow boundary, git worktree list, helper status | Isolated worktree path summary, sanitized workflow status, logs/state, and QA report | The bugfix worktree is isolated and degraded mode is explicit; no hidden direct fixer or active-checkout edit occurs. | 2026-05-14 local implementation QA - passed |
| `BUGREPORT-UC-003` | After intake/approval, inspect the report, workflow state, and git status to verify the user checkout and public QA artifacts remain clean. | `51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md` / `BR-001`-`BR-004` | CLI status, git status, helper status where available | Sanitized report, workflow state, git status, and dated QA evidence | The saved report matches the user request, private workflow artifacts stay outside the repo, and the active checkout is not drifted by worker setup. | 2026-05-14 local implementation QA - passed |
