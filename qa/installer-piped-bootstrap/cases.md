# Installer Piped Bootstrap QA Cases

## Case ID Convention

Use stable `PIPE-NNN` IDs for installer piped bootstrap cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `PIPE-001` | One-line/piped install bootstrap is safe, clear, and recoverable on a fresh public checkout. | User-visible behavior matches source, docs, persisted state, and logs | installer shell, bootstrap logs, generated files | `tests/release/test_public_bootstrap_manifests.py` plus user-grade QA when visible | PARTIAL 2026-07-19; 10 isolated shell tests plus local assembler/bootstrap contracts pass for destination safety and fail-closed Native trust; approved redistribution/trust, signed bootstrap, hostile-repository safety, live public URL, and immutable release proof not run |
| `PIPE-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | PASS 2026-07-19; Native payload report passes its template validator and targeted identity/path/credential pattern scan |

## `PIPE-001` - Core User Flow

- Requirement: One-line/piped install bootstrap is safe, clear, and recoverable on a fresh public checkout.
- Risk covered: implementation, docs, and user-visible behavior drift apart.
- Preconditions: local Viventium runtime or the specific feature harness is available with synthetic, public-safe data.
- Steps:
  1. Exercise the feature through the real user surface, not only a unit test.
  2. Compare the visible result with source code, generated/runtime config, logs, persisted state, and the owning requirement doc.
  3. Capture a public-safe report with expected result, forbidden result, evidence, residual risk, and follow-up.
- Expected result: the feature behaves as documented and every supporting layer agrees.
- Forbidden result: backend logs, mocks, source inspection, or model completions are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, generated/runtime state summary, and docs/case links.
- Automation: `tests/release/test_public_bootstrap_manifests.py` plus any narrower feature tests discovered during implementation.
- Last run: PARTIAL 2026-07-19. Isolated fake- and real-Git harnesses proved an unrelated origin,
  tracked-dirty tree, and clean local-ahead revision are refused before CLI execution, while the
  equivalent supported SSH origin reaches the installed CLI after the expected update and exact
  remote-revision checks. The opt-in Native branch embeds release/digest/Developer ID trust rather
  than accepting environment overrides, and empty production trust refuses before download, Git, or
  source fallback. Ten focused shell tests and the bundled-Python bootstrap/producer source contracts
  passed. The approved redistribution/trust values, signed bootstrap archive, live public URL, fresh
  clone, hostile-repository defense, hook-safe staging,
  interruption recovery, signed/notarized artifact, and immutable provenance were not run; the
  current validation is not production acceptance.

## `PIPE-002` - Public-Safe Evidence Record

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
- Last run: PASS 2026-07-19. The Native payload production-integration report passes the QA report
  template validator in isolation, and a targeted scan of its code, tests, docs, workflow, and report
  found no local absolute path, personal email, private-key marker, or common token pattern. The
  report uses synthetic values and explicitly marks the production user path blocked.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Installer Piped Bootstrap. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `PIPE-UC-001` | On installer shell, bootstrap logs, generated files, verify that one-line/piped install bootstrap is safe, clear, and recoverable on a fresh public checkout. | owning requirement for `PIPE-001` / `PIPE-001` | installer shell, bootstrap logs, generated files | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to PIPE-001. | User-visible behavior matches source, docs, persisted state, and logs | PARTIAL 2026-07-19; isolated destination safety, bundled bootstrap source, and unprovisioned Native fail-closed behavior pass; fresh public URL, approved redistribution/trust, signed Native hand-off, and recovery remain open |
| `PIPE-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `PIPE-002` / `PIPE-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to PIPE-002. | The user sees an honest setup, retry, or degraded-state result for PIPE-002; no fake success is accepted. | PASS 2026-07-19; Native report template and public-safety scan pass, with production gaps marked blocked |
| `PIPE-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `PIPE-002` / `PIPE-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to PIPE-002. | PIPE-002 remains correct after the persistence or parity step and final wording matches evidence. | PASS 2026-07-19; scan rerun after final report/template corrections |
