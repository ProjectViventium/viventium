# Self-Healing QA

## Scope

Owns QA for Viventium self-healing workflow dispatch, private artifacts, helper Heal UX, and
GlassHive host-worker integration.

## Owning Docs

- `docs/requirements_and_learnings/51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md`
- `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`
- `docs/requirements_and_learnings/01_Key_Principles.md`

## Quality Bar

Heal must be explicit, private by default, GlassHive-backed when available, diagnose-only by default,
and unable to mutate the active checkout without an explicit apply/worktree gate.
