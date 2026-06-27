# 2026-06-25 Phase 0 Periphery Metadata QA

## Summary

Phase 0 implemented a private periphery artifact metadata path for Prompt Workbench scheduled
prompts. It created an authenticated API surface for listing sanitized sidecar metadata and
classifying invalid sidecars. It did not activate risk-radar generation, add a saved-memory key,
inject periphery into the main prompt, or add a browser UI.

Result: `PERI-002` passed. `PERI-001` is `PASS/PARTIAL` because recent nightly failures are now
classified and bounded, but stale queued-row cleanup and a private snapshot harness remain before
any new nightly insight routine should run.

## Scope Run

- Requirement: `docs/requirements_and_learnings/53_Viventium_Periphery_Nightly_Insights.md`
- QA cases: `PERI-001`, `PERI-002`, `PERI-003`
- User use cases: `PERI-UC-001`, `PERI-UC-003`
- Code owning path: Prompt Workbench scheduled-prompt backend.
- Docs and nested docs/repos: requirement doc, periphery QA cases, runtime QA map.
- Scripts or harnesses: release pytest checks for Prompt Workbench and scheduled GlassHive prompts.
- Logs: not copied into this report; only public-safe classes and counts are recorded.
- DB/state/persistence: local scheduler ledger status counts and terminal callback classes.
- Generated/shipped artifact: no compiled or shipped artifact changed.
- Real user path: Prompt Workbench API plus scheduler and GlassHive callback ledger inspection.
- Visual/UX comparison: browser UI not changed in Phase 0.
- Not run / blocked: browser Playwright QA, private snapshot harness, risk-radar pilot,
  health-pressure persistence, and old queued-row cleanup.

## Traceability

feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap

- Feature: periphery artifact metadata review.
- Requirement: private typed sidecar artifacts are inspectable without leaking raw insight content.
- Use case: a user or admin checks whether private nightly insight artifacts exist.
- QA case: `PERI-002`.
- Expected result: valid sidecars become sanitized metadata; invalid sidecars are classified.
- Actual evidence: focused happy/unhappy tests passed and the full Prompt Workbench test file passed.
- Remaining gap: no browser-facing artifact panel exists in Phase 0.

## Full-View Evidence Checklist

- Code owning path: inspected and changed Prompt Workbench scheduled-prompt backend and app route.
- Docs and nested docs/repos: updated requirement doc and periphery QA cases.
- Scripts or harnesses: release pytest checks run through `uv`.
- Logs: no raw logs copied; only public-safe local ledger classes recorded.
- DB/state/persistence: scheduler DB inspected for run totals, active nightly schedule, terminal
  callback state, stale queued rows, and parent task outcome.
- Generated/shipped artifact: not applicable; no packaged artifact changed.
- Real user path: API-level Workbench read path and scheduler/GlassHive ledger path exercised.
- Visual/UX comparison: BLOCKED by scope because no browser UI was added.
- Not run / blocked: snapshot harness and risk-radar pilot remain future work; supporting evidence
  cannot replace required user-path evidence for those future surfaces.

## User-Grade Evidence

- Surface exercised: Prompt Workbench API, scheduler DB/state, and GlassHive callback ledger.
- Real user path: an admin-owned scheduled prompt can be queried through the Workbench periphery
  metadata API after private sidecar files exist in that prompt's private folder.
- Visible outcome: the API response shows one valid artifact with module, timestamps, content
  counts, source-reference count, scheduled-run-reference hash, and markdown existence.
- Expanded/detail state: invalid JSON and module/path mismatch sidecars are returned as invalid
  metadata with explicit reasons.
- Persistence/reload result: sidecar files persisted on disk are rediscovered by a fresh API call;
  no new saved-memory key or main prompt state is persisted.
- Backend/log/DB confirmation: scheduler ledger inspection showed current built-in nightly state,
  terminal callback chains, and bounded stale queued rows.
- Final model/runtime wording check: no user-facing model prompt or runtime wording was changed.
- Substitution check: automated tests, source inspection, API responses, DB rows, and callback
  metadata support this Phase 0 API path; they do not substitute for future browser UI, snapshot
  harness, risk-radar generation, or health-pressure user-path QA.

## Automated Evidence

Ran:

- `uv run --with pytest --with pyyaml --with fastapi --with httpx --with croniter --with pydantic python -m pytest tests/release/test_prompt_workbench.py -q`
  - Result: `82 passed`
- `uv run --with pytest --with pyyaml --with fastapi --with httpx --with croniter --with pydantic python -m pytest tests/release/test_scheduled_glasshive_prompts.py -q`
  - Result: `13 passed, 5 skipped`
- `uv run --with pytest --with pyyaml python -m pytest tests/release/test_no_runtime_nlu.py -q`
  - Result: `4 passed`
- `uv run --with pytest --with pyyaml python -m pytest tests/release/test_project_boundary_contamination.py -q`
  - Result: `1 passed`
- `uv run --with pytest --with pyyaml python -m pytest tests/release/test_qa_results_public_safety.py -q`
  - Result: `1 passed`
- `uv run --with pytest --with pyyaml python -m pytest tests/release/test_qa_operating_contract.py -q`
  - Result: `4 failed, 19 passed`; failures were not in the periphery report after template repair.
    Remaining failures are pre-existing or unrelated local artifacts in emotional-cortex,
    GlassHive host-worker, and older memory-hardening QA reports.

ClaudeViv review:

- Auth check returned `CLAUDE_OK`.
- First structured Opus review ran but failed after structured-output schema retries.
- Shorter review-only Sonnet pass completed successfully.
- ClaudeViv verdict: Phase 0 can land as-is; Workbench private metadata is the right insertion
  point; implementation respects less-is-more; activation gates must stay closed for risk-radar
  generation.
- ClaudeViv recommended three cheap branch tests before final: user-level schedule rejection,
  missing required sidecar fields, and missing markdown companion. Those tests were added and passed
  in the `82 passed` Workbench run above.

Focused happy/unhappy coverage added:

- Valid sidecar plus matching markdown returns sanitized metadata.
- Invalid JSON and module/path mismatch return explicit invalid reasons.
- Missing required sidecar fields return `missing_required_fields` with the missing field list.
- Valid sidecar without a matching markdown file returns `markdownExists: false`.
- User-level schedules reject periphery artifact inspection with a 400 response.
- Another user's scheduled prompt returns forbidden.
- Responses omit private body text, source ids, and absolute local paths.

## Findings

- PASS: private sidecar metadata is inspectable without raw markdown or raw insight text.
- PASS: malformed sidecars are classified rather than ignored or treated as insight.
- PASS: no new main-prompt injection, saved-memory key, or active risk-radar routine was added.
- PARTIAL: current scheduler/GlassHive substrate is classified enough for Phase 0 metadata work, but
  stale queued-row cleanup and the private snapshot harness are still needed before activation.
- BLOCKED: browser Playwright QA is not applicable until a browser-facing periphery panel exists.
- RESIDUAL: the broader QA operating-contract suite still fails on unrelated local QA artifacts
  outside this periphery metadata slice.
- REVIEWED: ClaudeViv agreed there is no Phase 0 blocker and called out the same remaining Phase 1
  gates: stale queued-row cleanup, snapshot harness, and no active risk-radar generator until the
  canonical nightly path is freshly proven.

## Public-Safety Review

- [x] Raw private prompts are not copied into this report.
- [x] Raw scratchpad or artifact bodies are not copied into this report.
- [x] Raw conversation ids, message ids, account identifiers, and local absolute paths are omitted.
- [x] Secrets, credentials, callback payloads, and private screenshots are omitted.
- [x] Evidence is reported as counts, statuses, public-safe failure classes, and test results.
