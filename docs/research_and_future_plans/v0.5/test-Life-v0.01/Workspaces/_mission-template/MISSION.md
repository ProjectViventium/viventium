# Mission

## Identity

- **Mission ID:** `mission-example`
- **Created:** `YYYY-MM-DDTHH:MM:SSZ`
- **Parent host:** `example`
- **Parent task reference:** `source://task/example`
- **Worker host/profile:** `not_selected`

## User goal

State the user's ask faithfully, without inventing a workflow.

## Explicit constraints

- No synthetic constraint is active.

## Success condition

Define the concrete result the user must be able to inspect or use.

## Permission scope

### Allowed reads

- `life://CURRENT.md`

### Allowed writes

- This mission workspace only.

### External actions

- None without explicit user authorization and the active host's confirmation policy.

## Completion gate

- Inspect every deliverable.
- Trace material claims to evidence.
- Complete `receipts/MISSION_RECEIPT.json`.
- Include the independent GlassHive evidence-harness result when GlassHive executes the mission.
- Finish with the line-anchored `FINAL REPORT:` marker required by the GlassHive worker contract.
- State remaining blockers honestly.

The terminal response begins its final section exactly as:

```text
FINAL REPORT:
```
