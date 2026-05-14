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
