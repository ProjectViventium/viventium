# Prompt Architecture QA Cases

## Case ID Convention

Use stable `PROMPT-NNN` IDs for prompt architecture cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `PROMPT-001` | Prompt source, registry, compiled bundle, and runtime prompt use stay aligned without prompt/private-data drift. | User-visible behavior matches source, docs, persisted state, and logs | prompt registry, eval harness, prompt workbench, runtime prompts | `tests/release/test_prompt_registry.py` plus user-grade QA when visible | PARTIAL/PASS-SAFETY 2026-06-25 ([heart prompt live sync](reports/2026-06-25-heart-prompt-live-sync.md)); source/live sync verified, exact-model/user-path eval still pending |
| `PROMPT-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | PARTIAL/PASS-SAFETY 2026-06-25 ([heart prompt live sync](reports/2026-06-25-heart-prompt-live-sync.md)); public report uses counts/statuses only, no raw private text |

## `PROMPT-001` - Core User Flow

- Requirement: Prompt source, registry, compiled bundle, and runtime prompt use stay aligned without prompt/private-data drift.
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
- Last run: PARTIAL/PASS-SAFETY 2026-06-25
  ([heart prompt live sync](reports/2026-06-25-heart-prompt-live-sync.md)); source/live sync and
  string guards passed, but exact-model/user-path eval remains pending.

## `PROMPT-002` - Public-Safe Evidence Record

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
- Last run: PARTIAL/PASS-SAFETY 2026-06-25
  ([heart prompt live sync](reports/2026-06-25-heart-prompt-live-sync.md)); the report keeps private
  identifiers, raw chats, and raw memory values out of public evidence.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Prompt Architecture. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `PROMPT-UC-001` | On prompt registry, eval harness, prompt workbench, runtime prompts, verify that prompt source, registry, compiled bundle, and runtime prompt use stay aligned without prompt/private-data drift. | owning requirement for `PROMPT-001` / `PROMPT-001` | prompt registry, eval harness, prompt workbench, runtime prompts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to PROMPT-001. | User-visible behavior matches source, docs, persisted state, and logs | PARTIAL/PASS-SAFETY 2026-06-25 ([report](reports/2026-06-25-heart-prompt-live-sync.md)); exact-model/user-path eval pending |
| `PROMPT-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `PROMPT-002` / `PROMPT-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to PROMPT-002. | The user sees an honest setup, retry, or degraded-state result for PROMPT-002; no fake success is accepted. | PARTIAL/PASS-SAFETY 2026-06-25 ([report](reports/2026-06-25-heart-prompt-live-sync.md)); public-safe evidence created |
| `PROMPT-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `PROMPT-002` / `PROMPT-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to PROMPT-002. | PROMPT-002 remains correct after the persistence or parity step and final wording matches evidence. | PARTIAL/PASS-SAFETY 2026-06-25 ([report](reports/2026-06-25-heart-prompt-live-sync.md)); linked report reviewed after creation |

## Release Test Traceability

- `tests/release/test_prompt_architecture_eval_harness.py`
- `tests/release/test_prompt_registry.py`
