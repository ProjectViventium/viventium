# Bug Report Workflow QA

Owns QA for Viventium local bug-report intake, approval gates, isolated bugfix worktrees, and helper
UX.

## Owning Docs

- `docs/requirements_and_learnings/51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md`

## Surfaces

- `bin/viventium report-bug`
- `bin/viventium workflows start bug-report`
- macOS helper Advanced > Report a Bug
- GlassHive host-worker dispatch
- private local workflow artifacts under App Support

## Quality Bar

Bug-report workflows must collect user-provided reproduction details before fix work, avoid the
user's active checkout, avoid public/private leakage, and only move into implementation after the
report is approved.
