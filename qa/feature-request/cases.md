# Feature Request Workflow Cases

## FR-001: Intake Blocks Implementation

- Requirement: `51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md`
- Surfaces: helper, CLI, GlassHive workflow
- Preconditions: user submits a local feature request
- Steps: start feature-request workflow
- Expected Result: workflow creates `feature-request.md` with success criteria, missing cases, non-goals, impacted surfaces, and QA acceptance before implementation
- Forbidden Result: worker starts coding from the raw request without intake
- Evidence: dated report under `reports/`
- Last Run: 2026-05-14 local implementation QA - passed by CLI and native helper modal QA

## FR-002: Feature Work Uses Isolated Worktree

- Requirement: `51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md`
- Surfaces: CLI, git
- Preconditions: approved feature spec
- Steps: approve implementation phase
- Expected Result: worker uses a fresh `feature/<slug>` worktree and leaves the user's primary checkout untouched
- Forbidden Result: branch switch, stash, or edits in the user's active checkout
- Evidence: dated report under `reports/`
- Last Run: 2026-05-14 local implementation QA - passed

## FR-003: PR Creation Honors Policy

- Requirement: `51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md`
- Surfaces: CLI, GitHub/PR adapter
- Preconditions: feature implementation passes QA
- Steps: run PR preparation with setting enabled and disabled
- Expected Result: enabled path creates PR only after approval gates; disabled path prompts before creating PR
- Forbidden Result: PR from private artifacts, unrelated dirty work, or failed QA
- Evidence: dated report under `reports/`
- Last Run: 2026-05-14 local implementation QA - policy covered; cloud PR creation intentionally not run
