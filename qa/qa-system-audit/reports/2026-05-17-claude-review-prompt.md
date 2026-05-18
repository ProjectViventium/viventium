<!-- qa-evidence-exempt: legacy or audit-style report; supersede with the standard run-report template on next rerun. -->
You are a second-opinion reviewer on a local engineering QA-system audit task.

Workspace:
- Repo root: the directory passed as the first argument to the Claude review helper.
- The repo has nested components under `viventium_v0_4/`.

Objective:
- Do a max-effort review-only pass over Codex's QA-system audit.
- Verify whether the audit accurately evaluates Viventium's QA side: docs, records, cases,
  procedures, scripts, feature requirements, release tests, user-grade evidence, and public-safety
  practice.
- Identify missed gaps, overstated claims, sharper fixes, and the simplest path to world-class but
  not overcomplicated QA.
- Do not make changes.

Primary audit artifact:
- `qa/qa-system-audit/reports/2026-05-17-qa-system-audit.md`
- `qa/qa-system-audit/README.md`
- `qa/qa-system-audit/cases.md`

Related prior audit:
- `qa/documentation-implementation-audit/reports/2026-05-17-full-codebase-doc-implementation-audit.md`
- `qa/documentation-implementation-audit/reports/2026-05-17-claude-review-summary.md`

Core files to inspect:
- `AGENTS.md`
- `CLAUDE.md`
- `qa/README.md`
- `qa/_migration.md`
- `qa/_templates/README.md`
- `qa/_templates/feature-readme.md`
- `qa/_templates/cases.md`
- `qa/_templates/run-report.md`
- `tests/release/test_qa_operating_contract.py`
- `docs/requirements_and_learnings/01_Key_Principles.md`
- `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`
- all requirement docs under `docs/requirements_and_learnings/`
- top-level folders under `qa/`
- tests under `tests/release/`

User's desired QA rule to evaluate:
- Gather full-view evidence: look at logs, DB, code, nested repos, nested docs/markdown files, and use
  the computer or browser to use the feature like a user. Evaluate interactions, results, visible UI/UX,
  and compare resultant UI/UX against supporting evidence. Identify all gaps, issues, and
  misalignments before fixing them.

Claims to validate or challenge:
- Viventium has a strong central QA philosophy, but the traceability system is incomplete.
- `qa/README.md`, `01_Key_Principles.md`, and `AGENTS.md` include the user-grade evidence rule, but
  feature folders and reports do not consistently enforce or record it.
- `CLAUDE.md` has stale QA paths and is not fully aligned with current QA folders.
- Many `qa/<feature>/` folders remain legacy and are tracked in `_migration.md`, but migration is
  not complete or strongly enforced.
- `45_Runtime_Feature_QA_Map.md` is useful but not a complete feature-to-QA traceability matrix.
- Release tests rarely reference QA case IDs or owning QA folders.
- `qa/results/README.md` is required by `test_qa_operating_contract.py`, but `qa/results/` is ignored
  by `.gitignore`, creating clean-clone fragility.
- The right fix is a small traceability spine and checker, not a heavy test-management system.

Constraints:
- Review only. Do not edit files, run destructive commands, stage, commit, push, or modify runtime state.
- Keep all output public-safe.
- Tie claims to concrete evidence: file paths, line references if possible, tests, docs, or folder state.
- Separate strong evidence from speculation.
- If inspecting ignored local result folders, summarize only counts and path-shape findings; do not
  quote private content, raw logs, DB rows, secrets, account identifiers, message IDs, chat IDs,
  session IDs, local absolute paths, private prompts, or screenshots.
- Treat existing uncommitted changes as user-owned.

Non-goals:
- Do not implement fixes.
- Do not recommend a heavyweight external test-management platform.
- Do not duplicate detailed feature requirements into the QA map; prefer pointers and small metadata.

What I want back:
- Findings Codex missed, ordered by severity.
- Findings Codex overstated or should weaken.
- Specific changes to the QA audit report.
- Specific docs/scripts/tests/procedures that would fix the gaps with minimum complexity.
- Public/private-safety risks in the audit itself.
- A recommended repair order.

Return JSON that matches the structured review helper schema:
- `summary`
- `findings`
- `risks`
- `tests_to_add`
- `alternatives`
- `evidence`
