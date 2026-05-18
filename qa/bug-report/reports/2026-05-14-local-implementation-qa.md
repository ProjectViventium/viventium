<!-- qa-evidence-exempt: legacy or audit-style report; supersede with the standard run-report template on next rerun. -->
# Bug Report Workflow Local QA - 2026-05-14

## Scope

Local implementation QA for the Viventium bug-report workflow extension.

## Evidence

- `python3 -m py_compile` passed for workflow and compiler scripts.
- `uv run --with pytest --with pyyaml pytest tests/release/test_stable_dev_runtime_workflows.py -q`
  passed: 19 tests.
- `PYTHONPATH=. uv run --with pytest --with pyyaml pytest tests/release/ -q` passed: 537 tests,
  1 skipped.
- `swift build` passed for the helper package before native QA.
- Native helper menu QA showed top-level actions limited to Open, Start/Stop, status, Advanced, and
  Quit.
- Native Advanced menu QA showed Check for Updates, Create Backup Snapshot, Heal Viventium, Report a
  Bug, Request a Feature, Approve Build or Fix, Cancel Active Workflow, Open Work Artifacts,
  transcript ingest, Start Viventium at Login, and Show Status Bar Icon.
- Native Report a Bug dialog QA verified fields for what happened, steps to reproduce, expected
  behavior, actual behavior, and other useful details, with guided placeholders.
- Current installed-helper QA reopened **Advanced > Report a Bug...** and verified the five guided
  input fields plus **Continue**/**Cancel** controls without creating a workflow.
- CLI QA started and cancelled a synthetic bug-report intake in isolated temp App Support state,
  verifying degraded mode is explicit and user data stays out of the repo.
- Playwright local smoke signed into the local UI with a synthetic local QA account and captured the
  authenticated Viventium chat surface.

## Results

- BR-001: Passed. CLI tests verified `bug-report.md` captures supplied reproduction input plus
  missing reproduction, impacted surface, evidence, and QA acceptance sections before implementation.
- BR-002: Passed. Approval creates an isolated `bugfix/<slug>` worktree; cancel removes the clean
  worktree and throwaway branch.
- BR-003: Passed. Native helper QA verified the Advanced menu entry and guided bug-report dialog.
- BR-004: Passed. The degraded path remains explicit and does not start hidden direct CLI bug-fix
  work.

## Residual Risk

Starting a full real bug-fix implementation through GlassHive was not run because it would launch a
long-running worker that may inspect private local logs. The intake, approval, isolated worktree, and
shared GlassHive dispatch/cancel paths are covered by local tests and live synthetic dispatch.
