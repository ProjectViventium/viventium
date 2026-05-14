# Feature Request Workflow Local QA - 2026-05-14

## Scope

Local implementation QA for feature-request intake, approval gating, isolated feature worktrees, PR
policy propagation, GlassHive dispatch/cancel, and helper controls.

## Evidence

- `tests/release/test_stable_dev_runtime_workflows.py` passed and covers:
  - feature-request intake artifact creation
  - required intake sections for success criteria, non-obvious cases, missing requirements, non-goals,
    impacted surfaces, and QA acceptance
  - PR setting propagation through compiled runtime env and workflow artifacts
  - prompt text for the disabled auto-PR setting
  - approved feature implementation creating an isolated `feature/<slug>-<run-id>` git worktree
  - implementation prompt explicitly forbidding remote PR/push unless a later explicit action asks
    for it
  - helper menu entries for Request a Feature and Approve Build or Fix
- The broader parent release suite passed: 532 tests, 1 skipped.
- A live local GlassHive-backed feature-request run was dispatched with synthetic intake text and
  then cancelled. Viventium returned to idle and the GlassHive run state became `interrupted`.
- `swift build` passed for the helper.
- Native helper menu QA showed **Advanced > Request a Feature...** and
  **Advanced > Approve Build or Fix...**.
- Native Feature Request modal QA opened the intake dialog, verified the feature-request prompt and
  **Continue**/**Cancel** actions, and dismissed with **Cancel** without creating a workflow.

## Results

- FR-001: Passed. Intake is materialized before implementation and includes the required planning
  sections.
- FR-002: Passed. Approval creates an isolated feature worktree and does not switch or edit the active
  checkout.
- FR-003: Partially covered. Runtime config exports the PR policy and artifacts include the required
  user prompt when automatic PR creation is disabled. Actual cloud PR creation was intentionally not
  exercised.

## Remaining Manual QA

Remote PR creation remains gated by public-safety checks. The implementation prompt and workflow
policy forbid push/remote PR creation unless a later explicit action asks for it and QA passes.
