<!-- qa-evidence-exempt: legacy or audit-style report; supersede with the standard run-report template on next rerun. -->
# Claude Second-Opinion Summary - 2026-05-17

## Scope

Claude was run in structured review-only mode against the local Viventium checkout, with the QA-system
audit, prior documentation/implementation audit, QA docs, requirement docs, release tests, and agent
instructions supplied as context. Claude was instructed not to edit files.

The raw Claude JSON output was not committed because it includes local execution metadata. This summary
captures the public-safe conclusions Codex accepted after review.

## Accepted Corrections

- `QASYS-007` should be treated as the immediate clean-clone blocker. `qa/results/README.md` was
  required by a release test while ignored by git.
- The full-view evidence checklist already exists in `qa/_templates/run-report.md`; the gap is that
  feature reports do not consistently use those headings.
- The migration backlog needs burn-down enforcement. It is not enough to list legacy folders forever.
- The traceability finding and `45_Runtime_Feature_QA_Map.md` finding are one underlying issue:
  the central feature-to-QA map is incomplete.
- Release-test traceability is thinner than the first audit wording implied: only a tiny subset of
  release tests name QA case IDs or owning QA paths.
- `CLAUDE.md` path checks should be part of the QA operating-contract test because it is agent-facing
  context and currently references missing QA/docs paths.

## Accepted Additions

- Add a path-existence scan for backticked `qa/...` and `docs/requirements_and_learnings/...`
  references in agent instructions.
- Add a required-public-QA-file tracked/ignored check.
- Add a `QA_OWNER` convention for release tests with a small allowlist for low-level helper tests.
- Add a test that hard-coded `qa/...` paths in release tests exist.
- Add a report-shape check for user-grade-evidence headings, with explicit exemptions for non-runtime
  audit reports.
- Add migration backlog burn-down logic so completed folders are removed from `_migration.md`.
- Add stale `Last Run` warnings for active case catalogs.
- Account for flat top-level QA artifacts such as `qa/privacy_publish_audit.md`.

## Fix Started

Codex updated `.gitignore` so `qa/results/README.md` can be tracked while timestamped generated result
subfolders remain ignored:

- keep ignored: `qa/results/*`
- allow: `qa/results/`
- allow: `qa/results/README.md`

The README still needs to be tracked in the eventual commit for the clean-clone fix to be complete.

## Public-Safety Review

- [x] No secrets, token values, passwords, cookies, private prompts, raw logs, DB rows, screenshots,
  local absolute paths, or private account identifiers included.
- [x] Ignored/local QA result concerns are summarized without copying raw result content.
