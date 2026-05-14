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
