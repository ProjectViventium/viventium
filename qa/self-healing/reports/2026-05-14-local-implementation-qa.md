# Self-Healing Local QA - 2026-05-14

## Scope

Local implementation QA for the Viventium self-healing workflow adapter, GlassHive boundary, helper
controls, private artifacts, cancel behavior, and isolated apply worktree behavior.

## Evidence

- `python3 -m py_compile` passed for `scripts/viventium/workflows.py` and
  `scripts/viventium/workflows/cli.py`.
- `tests/release/test_stable_dev_runtime_workflows.py` passed and covers:
  - loud failure when GlassHive host workers are disabled
  - private RCA/review/proposed-fix prompt artifact creation
  - GlassHive host-worker dispatch with `execution_mode=host`, `profile=codex-cli`, and
    `bootstrap_bundle.files[].content`
  - workflow cancel interrupting the GlassHive worker instead of silently clearing only local state
  - explicit heal apply mode creating an isolated `heal/<slug>-<run-id>` git worktree
  - helper menu entries for Heal Viventium, Cancel Active Workflow, and Open Work Artifacts
  - helper status strings for `Healing (N mins passed)`
- The broader parent release suite passed: 532 tests, 1 skipped.
- Local GlassHive health was verified against `/health` and `/v1/metrics/summary`; `/v1/metrics`
  currently returns 404, and the workflow adapter now accepts the healthy endpoints.
- A live local GlassHive-backed feature-request dispatch was started with synthetic input and then
  cancelled. The GlassHive run state became `interrupted` with operator interruption text.
- `swift build` passed for the helper.
- Native helper menu QA showed **Advanced > Heal Viventium...**, **Cancel Active Workflow**, and
  **Open Work Artifacts**.
- Native Heal settings QA opened the modal, verified provider default **Auto (Codex preferred)**,
  thinking default **xHigh**, and dismissed with **Cancel**.
- A reversible local workflow-status fixture showed the status-bar glyph as `V*` and the disabled
  status row as `Healing (0 mins passed)`, then restored the previous active workflow state.

## Results

- SH-001: Passed. Disabled GlassHive host workers produce a blocked workflow with
  `failure_class=glasshive_unavailable`; no hidden direct CLI runtime is used.
- SH-002: Passed. RCA, orchestrator review, proposed-fix, and implementation prompts are created
  under private App Support workflow state, with restrictive file permissions.
- SH-003: Passed by native helper QA. The helper status path rendered `Healing (N mins passed)`,
  showed the `V*` active-work glyph, and exposed Heal Viventium, Cancel Active Workflow, and Open
  Work Artifacts.
- SH-004: Passed. `--mode apply` creates an isolated heal worktree and points implementation prompts
  at that worktree instead of the active checkout.

## Remaining Manual QA

Starting a full real heal implementation was intentionally not run because it would inspect private
local logs and may create code changes. The diagnose/apply prompt gates, private artifacts, isolated
worktree behavior, live GlassHive dispatch, and cancel/interruption path were tested locally.
