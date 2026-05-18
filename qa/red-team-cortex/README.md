# Red Team Cortex QA

## Scope

- Owning requirements: see `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md` for the current requirement mapping.
- Primary outcome: Red Team activates for explicit pressure tests and integrates evidence-backed corrections without duplicate or unsupported claims.
- User-visible surfaces: web background cards, final answer, activation logs.

## Quality Bar

- Exercise the real user surface when the behavior is visible.
- Compare the visible result with source code, generated/runtime config, logs, persisted state, and docs.
- Keep public evidence sanitized: no secrets, account identifiers, raw private logs, local absolute paths, or private screenshots.

## Required Suites

| Suite | Command or Manual Path | Required When |
| --- | --- | --- |
| Feature contract | `tests/release/test_background_agent_governance_contract.py` | Relevant code/docs/config changes |
| Full-view QA | Real surface -> visible result -> supporting logs/state/docs -> sanitized report | User-visible behavior changes |
| Public-safety scan | Pattern scan over report/diff | Before PR/public push |

## Current Status

- Case catalog: `cases.md`.
- Reports: `reports/` for new dated public-safe runs.
- Last catalog update: 2026-05-17.
