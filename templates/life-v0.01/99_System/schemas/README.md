# Schemas

Versioned portable contracts for Life artifacts. Prefer stable logical IDs and explicit migrations.

- `source-manifest.schema.json`: the thin Sources ownership boundary
- `mission-context-delta.schema.json`: append-only parent/user context updates
- `mission-question.schema.json`: worker question and callback/checkpoint state
- `mission-receipt.schema.json`: deliverables, promotions, self-check, and independent evidence result
- `insight-sidecar.schema.json`: provenance, confidence, falsifiers, and surfacing rules

These schemas are design contracts, not proof that a V0.5 runtime validates them yet.
