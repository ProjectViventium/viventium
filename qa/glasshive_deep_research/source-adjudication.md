# Source Adjudication Template

Use this template when a GlassHive deep-research result contains a material source dispute,
classification dispute, date-window dispute, or seed-entity coverage dispute. This is QA evidence,
not runtime logic. Do not copy private prompts, client names, screenshots, raw logs, or confidential
benchmark artifacts into this public repo.

## Dispute

- Date:
- Run/profile:
- Question or claim being adjudicated:
- User-stated constraint from `glasshive-run/constraint-ledger.json`:
- Artifact or field under review:

## Primary/Public Sources Checked

| Source | Type | Date Checked | Relevant Evidence | Link Or Public Citation |
| --- | --- | --- | --- | --- |
|  | Company/official filing/primary publication/public database |  |  |  |

## Decision

Mark one:

- `EXCLUDED`: the item violates the user-stated scope and should not be counted.
- `FLAGGED`: the item may remain, but the final report must call out the caveat or uncertainty.
- `KEPT`: the item fits the stated scope and evidence supports keeping it.
- `UNRESOLVED`: evidence is insufficient; the result needs human review or another research pass.

Decision:

Rationale:

## Follow-Up

- Runtime change needed: yes/no
- Prompt/harness change needed: yes/no
- QA case to update:
- Private evidence location, if any:
