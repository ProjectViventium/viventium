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

## FR-004: Degraded Mode Is Explicit Before Implementation

- Requirement: `51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md`
- Surfaces: CLI, GlassHive boundary
- Preconditions: GlassHive host workers are unavailable and operator passes `--allow-degraded`
- Steps: start feature-request intake, then approve the spec with `--allow-degraded`
- Expected Result: intake is created, approval creates an isolated feature worktree, and implementation remains blocked/degraded without silent direct CLI execution
- Forbidden Result: coding starts from a raw request or hidden non-GlassHive runtime
- Evidence: dated report under `reports/`
- Last Run: 2026-05-14 local implementation QA - passed

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Feature Request. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `FEATREQ-UC-001` | Start a feature request from the helper or CLI with synthetic user value, scope, non-goals, and acceptance criteria, then review the generated spec before implementation approval. | `51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md` / `FR-001` | macOS helper dialog or `bin/viventium feature-request start` | Generated feature spec, helper/CLI output, workflow state, and dated QA report | Implementation is blocked until the spec names success criteria, missing cases, non-goals, impacted surfaces, and QA acceptance. | 2026-05-14 local implementation QA - passed |
| `FEATREQ-UC-002` | Approve a synthetic feature request with normal and degraded GlassHive availability. | `51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md` / `FR-002`, `FR-004` | CLI workflow boundary, git worktree list, helper status | Isolated worktree summary, degraded-state status, logs/state, and QA report | Feature implementation uses an isolated worktree and degraded mode is explicit; no raw request becomes immediate code. | 2026-05-14 local implementation QA - passed |
| `FEATREQ-UC-003` | Run the PR-preparation path with PR creation enabled and disabled using synthetic local evidence. | `51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md` / `FR-003` | CLI PR preparation path and public-safe git diff review | QA status, privacy scan summary, approval gate output, and dated QA report | PR creation is gated by approval, passing QA, and public-safe artifacts; disabled mode prompts rather than creating a cloud PR. | 2026-05-14 policy covered; cloud PR creation intentionally not run |
