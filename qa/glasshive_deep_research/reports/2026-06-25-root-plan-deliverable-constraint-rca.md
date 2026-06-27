# GlassHive Root Plan Deliverable Constraint RCA - 2026-06-25

## Summary

- Result: PASS for local fix readiness.
- Scope: local GlassHive/Viventium App Support runtime, existing host-worker incident workspaces,
  run-evidence verifier, callback payload records, artifact preview UI, and regression tests.
- Privacy boundary: this report intentionally omits the private user prompt, raw worker/run/project
  ids, local absolute paths, private screenshots, and raw artifact text. Raw evidence was inspected
  locally only.

## Incident Shape

A user asked Viventium to launch two host-native GlassHive workers for a plan-only research spike.
Both workers created substantial Markdown deliverables and the artifact links opened correctly, but
Telegram reported both workers as stuck/failed with:

```text
GlassHive evidence check failed: constraint compliance failed:
strict source/date constraints not referenced in planning file
```

The DB/callback payloads showed the apparent contradiction was real: the run state was failed due to
the evidence gate, while the callback payload still contained a ready file deliverable. Telegram
faithfully rendered the failed run status and linked the available artifact.

## Root Cause

The failure was in GlassHive run-evidence classification, not in Telegram and not in the workers'
ability to write files.

The verifier classified any Markdown filename whose stem contained words such as `plan` or `spec` as
a constraint-propagation file. That rule was correct for internal paths such as planning notes,
specs, prompts, subagent instructions, delegation notes, and ledger files, because those files must
carry strict source/date/auth/scope constraints forward. It was too broad for final user-facing
deliverables in the workspace root or output/artifact/report roots.

Because both delivered Markdown files were root user deliverables with `plan` in the filename, the
evidence gate required them to reference `glasshive-run/constraint-ledger.json` or restate the
ledger constraints exactly. They were final plans, not internal propagation files, so this became a
false hard failure.

## What Went Right

- Both host workers produced real deliverables.
- The artifact preview/open endpoint returned the generated Markdown through GlassHive.
- Callback payloads preserved the ready deliverable instead of losing the files.
- The evidence gate failed closed rather than silently calling an uncertain run completed.
- Telegram did not invent a result; it reported the failed evidence status it received.

## What Went Wrong

- Run-evidence filename classification overreached from internal planning files into user-facing
  deliverables.
- The callback wording foregrounded the hard evidence failure, which made the user-facing Telegram
  message sound like nothing useful had been delivered even though the artifact link was valid.
- The live App Support runtime had to be restarted after the source fix; source correctness alone
  was not enough for the Telegram/GlassHive path.

## Fix

- Narrowed constraint propagation classification so root/output/artifacts/reports deliverables named
  `plan` or `spec` are not treated as internal propagation files solely by filename.
- Kept the strict rule for internal support paths and filenames: `planning/`, `specs/`, `research/`,
  `notes/`, prompts, subagent instructions, delegation notes, constraints, and ledgers.
- Kept source/date drift scanning over user-facing deliverables, so a final plan that uses
  out-of-window cited evidence still fails.
- Kept strict-constraint softening checks on root plan/spec deliverables, so final text that weakens
  a hard source/date constraint still fails.
- Reused the canonical support-artifact directory set for the support-path boundary so verifier and
  artifact-support concepts do not drift.
- Added regression tests proving both sides of the boundary.
- Updated the GlassHive requirement doc and QA case matrix.
- Restarted the App Support runtime from the patched checkout through the supported dev-runtime
  activation path after clearing safe tool cache space for the doctor preflight.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `GHDR-001A` | PASS | Rebuilding evidence for both existing host-worker workspaces changed constraint compliance from `fail` to `pass`; advisory completion/content warnings stayed non-blocking warnings. | Real incident replay stayed private; public evidence uses sanitized status and no raw IDs. |
| `GHDR-001A` | PASS | A root user-facing plan with a cited source published after the user-limited source window still fails source/date compliance. | Negative control keeps the real guard. |
| `GHDR-001A` | PASS | An internal planning file that omits the strict source/date constraint still fails with the original propagation error. | Internal propagation remains strict. |
| `GHDR-001A` | PASS | Root, `output/`, `artifacts/`, and `reports/` Markdown deliverables named with `plan` or `spec` avoid the ledger-reference propagation failure; internal-named root files still fail when they drop strict constraints. | Pins the documented deliverable-root boundary. |
| `GHDR-001A` | PASS | A root user-facing plan that softens a hard source/date window with "wherever possible" still fails. | Softening detection remains intentional. |
| `GHDR-001A`, `GHHOST-001` | PASS | GlassHive runtime, MCP, UI, LibreChat API, LibreChat frontend, and modern playground health/listeners were verified after restart; GlassHive uses the App Support DB/log paths and the patched checkout. | Confirms live runtime, not only source. |
| `GHDR-001A`, `GHHOST-004` | PASS | Playwright opened both existing delivered Markdown artifact previews through GlassHive, confirmed title/heading/metadata, download and workspace actions, populated preview length, and reload persistence. | Auto-created Playwright snapshots were deleted because they contained private artifact text. |
| `GHDR-001A` | PASS | Targeted root-plan/deliverable-root/internal-name/softening regressions, run-evidence/profile tests, API evidence/deliverable tests, and the full GlassHive runtime pytest suite passed locally. | Automated checks support the user path. |
| `GHDR-001A` | PASS | Review-only ClaudeViv second opinion confirmed the RCA and surgical owner, recommended reusing the canonical support-dir set, preserving/clarifying softening behavior, adding deliverable-root/internal-name tests, and tracking callback wording separately. | Verifier/test/docs actions were applied; callback wording is filed as `GHHOST-007`. |

## Traceability

- Feature: GlassHive host-worker run evidence and callback artifact truth.
- Requirement: `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`.
- Use case: constrained host-worker run produces a root Markdown plan deliverable and sends a
  Telegram/web callback with artifact links.
- QA case: `GHDR-001A`, with callback wording follow-up tracked as `GHHOST-007`.
- Expected result: user-facing root/output/artifact/report deliverables named with `plan` or `spec`
  do not fail the ledger-reference propagation rule solely by filename, while source/date drift and
  softened strict constraints still fail.
- Actual evidence: code-level replay, targeted regressions, full runtime tests, live App Support
  restart/health, DB/log inspection, Playwright browser artifact preview, and ClaudeViv review all
  support the boundary.
- Remaining gap: callback wording for genuine evidence-failed runs with available artifacts is not
  fixed in this patch and is tracked separately.

## Full-View Evidence Checklist

This report connects feature -> requirement -> use case -> QA case -> expected result -> actual
evidence -> remaining gap for the local verifier fix. It includes the real user path, docs and
nested docs, logs, DB/state/persistence, generated/shipped artifact verification, and public/private
safety. The fixed runtime was restarted and checked through the App Support runtime, not only source
inspection.

| Evidence surface | Result | Sanitized pointer |
| --- | --- | --- |
| Real user path | PASS | Playwright opened GlassHive artifact preview pages for both existing delivered Markdown files, checked actions and reload persistence, then removed private snapshots. |
| Docs and nested docs | PASS | Requirement doc, deep-research QA case, host-worker callback follow-up case, and this report were updated. |
| Logs, DB/state/persistence | PASS | Runtime health/listeners and process cwd/open DB/log state were inspected; historical failed rows were left intact as truthful history. |
| Generated/shipped artifact verification | PASS | The live App Support process was restarted from the patched checkout, and artifact preview/open surfaces still served the delivered Markdown files. |
| Cross-surface parity | PASS/PARTIAL | Source replay, automated tests, live runtime health, browser preview, and DB/log inspection agree for the verifier boundary. Already-sent Telegram callbacks remain historical and cannot be changed. |
| Public/private safety | PASS | Private prompt text, raw worker/run/project ids, local absolute paths, screenshots, and raw artifact text are excluded from this report. |

## User-Grade Evidence

- Surface exercised: Playwright browser against local GlassHive artifact preview/open pages, plus
  local App Support GlassHive runtime/API health and DB/log state.
- Real user path: opened both existing artifact preview links a Telegram user would click, verified
  the visible page metadata/actions, and reloaded the preview.
- Visible outcome: GlassHive preview pages rendered the delivered Markdown artifact names, file
  metadata, `Download file` actions, `View workspace` actions, and populated preview bodies.
- Expanded/detail state: runtime health, process cwd, open App Support DB/log files, callback DB
  counts, and regenerated evidence status were inspected.
- Persistence/reload result: browser reload kept the preview page and actions available; live
  GlassHive restart preserved the existing DB history and artifact availability.
- Backend/log/DB confirmation: GlassHive runtime, MCP, UI, LibreChat API, LibreChat frontend, and
  modern playground listeners were healthy after restart; DB history still records the old failed
  runs and delivered callbacks as history.
- Final model/runtime wording check: rebuilt evidence for the old workspaces reports
  `constraint_compliance=pass` with only advisory warnings; historical Telegram wording remains
  unchanged and callback copy follow-up is filed separately.
- Substitution check: source inspection, DB rows, logs, tests, and ClaudeViv review supported the
  browser/user path; they did not replace the Playwright artifact-preview check or live runtime
  restart verification.

## Automated Evidence

Commands are shown from the repository root with public-safe relative paths:

```bash
cd viventium_v0_4/GlassHive/runtime_phase1
.venv/bin/python -m pytest tests/test_run_evidence.py::test_constraint_compliance_allows_user_facing_root_plan_deliverable_without_ledger_link \
  tests/test_run_evidence.py::test_constraint_compliance_allows_user_facing_deliverable_roots_named_plan_or_spec \
  tests/test_run_evidence.py::test_constraint_compliance_still_requires_internal_named_root_files_to_preserve_constraints \
  tests/test_run_evidence.py::test_constraint_compliance_still_flags_softened_constraints_in_root_plan_deliverable \
  tests/test_run_evidence.py::test_constraint_compliance_still_scans_root_plan_deliverable_for_source_date_drift \
  tests/test_run_evidence.py::test_constraint_compliance_fails_when_planning_file_omits_strict_source_window -q
.venv/bin/python -m pytest tests/test_run_evidence.py tests/test_profile_runtime.py -q
.venv/bin/python -m pytest -q

cd ../../..
bin/viventium dev-runtime activate-current --validate --restart --allow-protected-folder --allow-dirty-local-testing
```

The parent QA operating-contract check was also run with the available GlassHive venv. It initially
failed because this new report did not use the required V2 evidence-template headings; this report
was then updated to the standard structure. The same run also reported unrelated pre-existing older
report violations outside this task's files.

## Findings

- Existing historical run rows still say failed; that is truthful history and should not be mutated.
- Old callbacks already sent to Telegram cannot be unsent. The fixed runtime prevents the same false
  blocking failure on future equivalent root deliverables.
- Callback wording still needs a separate UX/product-truth pass so genuine evidence failures with
  available artifacts explain both facts clearly. That follow-up is tracked in `GHHOST-007`; it was
  intentionally not bundled into this verifier-boundary fix.

## Public-Safety Review

- [x] No private prompt text, raw artifact body, screenshots, personal emails, hostnames, or raw
  worker/run/project ids are included.
- [x] Commands use repository-relative paths and public-safe placeholders rather than local absolute
  paths.
- [x] Playwright auto-snapshots containing private preview text were deleted and not committed.
- [x] Public report text was scanned for the incident-specific private terms and raw runtime IDs
  relevant to this RCA.
