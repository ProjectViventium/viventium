# QA System Audit

## Scope

- Owning requirements docs: `docs/requirements_and_learnings/01_Key_Principles.md`,
  `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`, and `qa/README.md`.
- Runtime/code owners: `qa/`, `tests/release/`, feature requirement docs, agent instruction files,
  and scripts or harnesses that create QA evidence.
- User-visible surfaces: all feature QA areas, with emphasis on browser, Telegram, voice, installer,
  CLI/helper, MCP/tool, scheduler, GlassHive, and prompt/workbench flows.
- Out of scope: repairing every feature-specific QA gap in this audit pass.

## Quality Bar

- Primary user outcome: any developer or AI agent can trace a feature from requirement to QA owner,
  cases, automated tests, user-grade evidence, latest result, known gaps, and fix path.
- Speed/latency expectation: the QA system should be simple to use during ordinary development; it
  must not require a heavyweight process or duplicate docs.
- Persistence/reload expectation: living cases and dated reports stay updated when behavior changes.
- Failure behavior: stale, missing, ignored, or non-user-grade evidence is marked as blocked/partial,
  not passed.
- Public/private boundary: QA records summarize logs, DBs, local runtime state, and browser/computer
  evidence without exposing private data.

## Required Suites

| Suite | Command or Manual Path | Required When | Last Run |
| --- | --- | --- | --- |
| QA operating contract | `uv run --with pytest --with pyyaml python -m pytest tests/release/test_qa_operating_contract.py -q` | Every QA-system change | 2026-05-17 pass |
| QA folder shape inventory | `find qa -mindepth 1 -maxdepth 1 -type d ...` | Every QA-system audit | 2026-05-17 pass |
| Requirements-to-QA map review | Manual compare of `docs/requirements_and_learnings/*.md`, `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`, and `qa/` | Every release-readiness audit | 2026-05-17 pass |
| Release-test traceability review | Manual/source grep for QA case IDs and QA docs in `tests/release/` | Every release-readiness audit | 2026-05-17 pass |
| Public-safety scan | Pattern scan over public QA docs and tracked status review | Before public push/PR | 2026-05-17 pass |

## Coverage Matrix

| Requirement / Surface | Cases | Last Full Run |
| --- | --- | --- |
| QA spine exists and is easy to follow | `QASYS-001` | 2026-05-17 pass |
| Every feature has requirement-to-QA traceability | `QASYS-002` | 2026-05-17 pass |
| QA folders follow the living README/cases/reports shape | `QASYS-003` | 2026-05-17 pass |
| User-grade full-view evidence is required and recorded | `QASYS-004` | 2026-05-17 contract pass; feature runs required |
| Release tests and scripts are tied to cases/results | `QASYS-005` | 2026-05-17 pass |
| Agent instructions consistently point to real QA docs | `QASYS-006` | 2026-05-17 pass |
| Public-safe records are tracked and reproducible | `QASYS-007` | 2026-05-17 pass |
| Full-view evidence gate blocks hand-waved completion | `QASYS-008` | 2026-05-18 pass |

## Current Status

- Last full QA-system audit: 2026-05-17.
- Current result: the QA operating system now has standard feature folders, cases-based release-test
  ownership, enforced full-view evidence rules, a report-template gate against hand-waved completion,
  and public-safe result boundaries.
- Known residual work: older flat reports should be superseded under each feature `reports/` folder as those features are rerun; feature-specific QA still needs real user-grade runs when behavior changes.
- Next required hardening: keep adding narrower case IDs to dated feature reports and do not accept feature changes without a real user-grade evidence loop.
