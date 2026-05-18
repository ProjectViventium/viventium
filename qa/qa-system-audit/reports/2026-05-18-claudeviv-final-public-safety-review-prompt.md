<!-- qa-evidence-exempt: ClaudeViv review prompt artifact; companion run report holds the standard evidence template. -->
# ClaudeViv Final Public-Safety And QA-Gate Review Prompt - 2026-05-18

You are a review-only second-opinion reviewer. Do not make changes.

Review the current local Viventium checkout and return JSON using the ClaudeViv review schema.
Use max effort. Be skeptical. Validate or reject the claims below using repository evidence.

## Objective

Confirm whether the QA/docs repair now addresses the user's complaint:

- QA must start from a complete feature inventory.
- QA must enumerate natural and obvious user use cases.
- QA must treat those use cases as a checklist.
- QA must run applicable cases like a user via browser/computer/voice/Telegram/CLI/etc.
- QA must compare visible UI/UX with code, docs, nested docs/repos, logs, DB/state, scripts,
  generated config, and shipped artifacts.
- QA must not claim completion when real user-path evidence is blocked or missing.

## Primary Files To Inspect

- `qa/README.md`
- `qa/feature-user-use-case-checklist.md`
- `qa/_templates/cases.md`
- `qa/_templates/feature-readme.md`
- `qa/_templates/run-report.md`
- `docs/requirements_and_learnings/01_Key_Principles.md`
- `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`
- `AGENTS.md`
- `CLAUDE.md`
- `viventium_v0_4/LibreChat/AGENTS.md`
- `tests/release/test_qa_operating_contract.py`
- `qa/qa-system-audit/cases.md`
- `qa/qa-system-audit/reports/2026-05-18-feature-use-case-checklist-repair.md`
- `qa/qa-system-audit/reports/2026-05-18-claudeviv-feature-use-case-review-summary.md`
- Affected escaped-case owners:
  - `qa/web-search/cases.md`
  - `qa/modern-playground-voice/cases.md`
  - `qa/web-search-telegram/cases.md`
  - `qa/agent-config-continuity/cases.md`
  - `qa/config-alignment/cases.md`
  - `qa/citation-rendering/cases.md`

## Evidence Codex Collected

- `tests/release/test_qa_operating_contract.py -q`: 21 passed.
- `tests/release/ -q`: 607 passed, 4 skipped.
- `git diff --cached --check`: clean.
- Parent staged diff scan for local home paths, personal identifiers, common token shapes, and
  email addresses: no hits.
- Nested LibreChat staged final-content scan for local home paths, personal identifiers, common
  token shapes, and email addresses: no hits.
- Nested LibreChat full staged patch scan has a caveat: the patch removes a pre-existing local
  absolute path from `viventium_v0_4/LibreChat/AGENTS.md`. The staged final content is sanitized,
  but a normal public PR diff can display removed lines from the old base. Treat this as a
  public-review risk if true.
- Live product search/voice behavior is not claimed fixed. It remains recorded as `FAIL` or
  `PARTIAL` until a product fix and full signed-in browser/voice rerun pass with search providers
  healthy and degraded.

## Claims To Validate

1. The QA contract now makes feature inventory plus natural user use-case checklists mandatory.
2. The release test enforces the product-wide checklist, owner coverage, per-feature checklist
   sections, rejection of generic placeholder rows, stale backlog pressure, and escaped-case
   promotion across affected owners.
3. The 2026-05-18 voice + web-search miss is represented in all affected owners, not only the
   playground/search folders.
4. The reports do not hand-wave the product bug as fixed.
5. Public-safety posture is acceptable for the parent staged diff, but the nested LibreChat PR diff
   caveat is real if the removed old line would appear in a public review.
6. There is no unnecessary overcomplication that should be simplified before review without
   weakening the user's required QA bar.

## Required Output Focus

- Findings first, ordered by severity.
- Separate confirmed issues from risks.
- Identify exact files/sections for any gap.
- Recommend the least complicated fix path for each issue.
- Explicitly say whether the nested-diff caveat blocks public PR readiness.
