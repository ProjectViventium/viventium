# GlassHive Watch Desktop QA Cases

## Case ID Convention

Use stable `GHWATCH-NNN` IDs for glasshive watch desktop cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `GHWATCH-001` | Live desktop/watch flows expose enough state for takeover without leaking private screen data into public artifacts. | User-visible behavior matches source, docs, persisted state, and logs | GlassHive desktop/watch surface, worker status, callback evidence | `tests/release/test_prompt_registry.py` plus user-grade QA when visible | PASS 2026-05-23 local enterprise watch UI; see `qa/glasshive_azure_enterprise/reports/2026-05-23-launcher-watch-enterprise-qa.md`. |
| `GHWATCH-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | PASS 2026-05-23 for sanitized report; see `qa/glasshive_azure_enterprise/reports/2026-05-23-launcher-watch-enterprise-qa.md`. |

## `GHWATCH-001` - Core User Flow

- Requirement: Live desktop/watch flows expose enough state for takeover without leaking private screen data into public artifacts.
- Risk covered: implementation, docs, and user-visible behavior drift apart.
- Preconditions: local Viventium runtime or the specific feature harness is available with synthetic, public-safe data.
- Steps:
  1. Exercise the feature through the real user surface, not only a unit test.
  2. Compare the visible result with source code, generated/runtime config, logs, persisted state, and the owning requirement doc.
  3. Capture a public-safe report with expected result, forbidden result, evidence, residual risk, and follow-up.
- Expected result: the feature behaves as documented and every supporting layer agrees.
- Forbidden result: backend logs, mocks, source inspection, or model completions are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, generated/runtime state summary, and docs/case links.
- Automation: `tests/release/test_prompt_registry.py` plus any narrower feature tests discovered during implementation.
- Last run: PASS 2026-05-23 local enterprise watch UI. Playwright verified the watch surface,
  latest result detail, managed project workspace link, pause/resume state, no overlapping overlay
  text, and zero page console errors after reload.

## `GHWATCH-002` - Public-Safe Evidence Record

- Requirement: public QA artifacts must be reproducible and free of secrets, personal data, local paths, raw IDs, and private screenshots.
- Risk covered: a useful local QA run cannot be safely reviewed or published.
- Preconditions: a dated QA report is created for this feature.
- Steps:
  1. Review the report and related diffs for local absolute paths, account identifiers, tokens, raw logs, raw DB rows, private chats, and screenshots with private content.
  2. Keep raw/private evidence outside the public repo and summarize only public-safe counts, statuses, hashes, and conclusions.
  3. Link the report back to this case and the owning requirement doc.
- Expected result: the public report proves the behavior without leaking private/local data.
- Forbidden result: a report includes private transcripts, account identifiers, raw runtime dumps, local home paths, tokens, or secret-bearing command lines.
- Evidence to capture: public-safety scan result and link to the sanitized report.
- Automation: public-safety pattern scan plus relevant release tests.
- Last run: PASS 2026-05-23. Public report uses synthetic content and omits tokens, real account
  identifiers, raw DB rows, and private logs.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Glasshive Watch Desktop. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `GHWATCH-UC-001` | On GlassHive desktop/watch surface, worker status, callback evidence, verify that live desktop/watch flows expose enough state for takeover without leaking private screen data into public artifacts. | owning requirement for `GHWATCH-001` / `GHWATCH-001` | GlassHive desktop/watch surface, worker status, callback evidence | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to GHWATCH-001. | User-visible behavior matches source, docs, persisted state, and logs | PASS 2026-05-23 local enterprise watch UI. |
| `GHWATCH-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `GHWATCH-002` / `GHWATCH-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to GHWATCH-002. | The user sees an honest setup, retry, or degraded-state result for GHWATCH-002; no fake success is accepted. | PASS 2026-05-23 sanitized report. |
| `GHWATCH-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `GHWATCH-002` / `GHWATCH-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to GHWATCH-002. | GHWATCH-002 remains correct after the persistence or parity step and final wording matches evidence. | PASS 2026-05-23 after runtime reload and report update. |
