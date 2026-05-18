# Self-Healing Cases

## SH-001: Heal Fails Loud When GlassHive Host Workers Are Disabled

- Requirement: `51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md`
- Surfaces: CLI, helper
- Preconditions: compiled runtime has GlassHive host workers disabled
- Steps: run `bin/viventium heal start`
- Expected Result: command exits non-zero with clear GlassHive unavailable class
- Forbidden Result: silent direct CLI fallback or hidden worker runtime
- Evidence: dated report under `reports/`
- Last Run: 2026-05-14 local implementation QA - passed

## SH-002: Heal Creates Private RCA/Review Prompt Artifacts

- Requirement: `51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md`
- Surfaces: CLI, App Support state
- Preconditions: GlassHive host workers enabled or explicit degraded mode
- Steps: start heal workflow and inspect run artifact names
- Expected Result: RCA, orchestrator review, proposed-fix, and implementation prompt files exist under App Support
- Forbidden Result: raw artifacts written under repo docs, qa, commits, or public reports
- Evidence: dated report under `reports/`
- Last Run: 2026-05-14 local implementation QA - passed

## SH-003: Helper Shows Healing Status

- Requirement: `51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md`
- Surfaces: macOS helper
- Preconditions: active heal workflow state exists
- Steps: open helper menu
- Expected Result: status row shows `Healing (N mins passed)` and menu label indicates active work
- Forbidden Result: helper reports Stopped while a workflow is active without any work indication
- Evidence: dated report under `reports/`
- Last Run: 2026-05-14 local implementation QA - passed by native helper visual/status QA

## SH-004: Apply Mode Uses Isolated Worktree

- Requirement: `51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md`
- Surfaces: CLI, git
- Preconditions: operator explicitly starts heal with `--mode apply`
- Steps: start heal apply workflow
- Expected Result: workflow creates a fresh `heal/<slug>-<run-id>` worktree and implementation prompts point at that worktree
- Forbidden Result: code edits in the active user checkout
- Evidence: dated report under `reports/`
- Last Run: 2026-05-14 local implementation QA - passed

## SH-005: Degraded Mode Is Explicit And Private

- Requirement: `51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md`
- Surfaces: CLI, App Support workflow state
- Preconditions: GlassHive host workers are unavailable and operator passes `--allow-degraded`
- Steps: start heal workflow with `--allow-degraded`
- Expected Result: workflow reports `degraded_ready`, marks `failure_class=glasshive_degraded_mode`, avoids GlassHive IDs, and writes private artifacts with restrictive permissions
- Forbidden Result: silent direct CLI fallback, public QA artifacts with raw prompts/logs, or hidden worker execution
- Evidence: dated report under `reports/`
- Last Run: 2026-05-14 local implementation QA - passed

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Self Healing. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `SELFHEAL-UC-001` | Start a synthetic heal workflow from CLI/helper with GlassHive host workers disabled. | `51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md` / `SH-001`, `SH-003` | CLI and macOS helper status | Command exit/status, helper menu state, sanitized logs, workflow state, and dated QA report | Heal fails loudly or shows active healing truthfully; it never pretends hidden work is running. | 2026-05-14 local implementation QA - passed |
| `SELFHEAL-UC-002` | Start heal in degraded mode and inspect the private RCA/review/proposed-fix artifacts. | `51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md` / `SH-002`, `SH-005` | CLI workflow state and private App Support artifact summary | Sanitized artifact names/counts, permissions summary, logs/state, and public QA report | Private RCA artifacts are created outside the repo, degraded mode is explicit, and no raw prompts/logs enter public artifacts. | 2026-05-14 local implementation QA - passed |
| `SELFHEAL-UC-003` | Start apply mode with synthetic input and verify the implementation path uses an isolated worktree. | `51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md` / `SH-004` | CLI, git worktree list, workflow state | Worktree summary, active checkout git status, implementation prompt target, and dated QA report | Apply mode uses a fresh heal worktree and leaves the active user checkout untouched. | 2026-05-14 local implementation QA - passed |
