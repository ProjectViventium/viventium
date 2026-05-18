# Scheduling Cortex QA

## Scope

- Owning requirements: see `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md` for the current requirement mapping.
- Primary outcome: Schedule create/update/list/trigger flows produce correct visible reminders and persisted schedule state.
- User-visible surfaces: browser/Telegram/scheduler MCP, delivery ledger.

## Quality Bar

- Exercise the real user surface when the behavior is visible.
- Compare the visible result with source code, generated/runtime config, logs, persisted state, and docs.
- Keep public evidence sanitized: no secrets, account identifiers, raw private logs, local absolute paths, or private screenshots.

## Required Suites

| Suite | Command or Manual Path | Required When |
| --- | --- | --- |
| Feature contract | `tests/release/test_scheduling_mcp_supervision.py` | Relevant code/docs/config changes |
| Full-view QA | Real surface -> visible result -> supporting logs/state/docs -> sanitized report | User-visible behavior changes |
| Public-safety scan | Pattern scan over report/diff | Before PR/public push |

## Current Status

- Case catalog: `cases.md`.
- Reports: `reports/` for new dated public-safe runs.
- Last catalog update: 2026-05-17.
