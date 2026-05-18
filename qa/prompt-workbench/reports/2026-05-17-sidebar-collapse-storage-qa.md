<!-- qa-evidence-exempt: legacy or audit-style report; supersede with the standard run-report template on next rerun. -->
# Prompt Workbench Sidebar Collapse Storage QA - 2026-05-17

## Scope

Investigated a user-reported freeze/crash when using the Prompt Workbench top navigation sidebar
collapse controls. This pass was local-only and did not run reviewed live sync, cloud push, Mongo
mutation, or live model evals.

## Root Cause

The sidebar collapse controls changed React state correctly, but workbench preference persistence
used raw browser `localStorage` in app-level effects. In embedded or restricted browser modes,
preference storage can throw. A thrown storage write after clicking collapse caused an uncaught
React error, unmounted the app shell, and left the page blank.

## Fixes Verified

- Added a small safe storage boundary for local workbench preferences.
- Replaced raw preference storage access in the app shell, Prompt editor metadata toggle, and dock
  layout persistence.
- Added a root-level recovery boundary around the full workbench app, not only lazy dock panels.
- Debounced dock layout persistence so collapse/resize activity does not write layout state on
  every FlexLayout model event.
- Added an accessible label to the Prompt metadata collapse button.
- Added a release regression that blocks any raw `localStorage` use outside the safe storage
  wrapper.

## Browser QA

Tooling:

- Headed Chromium through Playwright against the production bundle at `http://127.0.0.1:8781/`.
- Browser-plugin attempt against the already-open embedded tab could list the tab, but DOM
  inspection timed out because the tab was already wedged from the failing state.

Scenarios:

1. Normal collapse loop: clicked Hide Prompt Flow, Hide Sync, Show Prompt Flow, and Show Sync.
2. Storage failure after load: patched Viventium preference storage writes/removes to throw, then
   repeated both top nav sidebar collapse controls.
3. Storage failure before load: patched Viventium preference reads/writes/removes to throw before
   the app initialized, then loaded and repeated collapse controls.
4. Prompt metadata collapse: opened Prompt, clicked Hide prompt metadata and Show prompt metadata
   while storage persistence was throwing.
5. Drafts navigation: clicked the Drafts tab and returned to Prompt in both normal and storage
   failure runs.
6. Keyboard collapse: pressed Cmd+B twice to collapse and restore the Prompt Flow sidebar in both
   normal and storage failure runs.

## Results

- Normal collapse loop passed with no console/page errors.
- Storage failure after load passed with no console/page errors.
- Storage failure before load passed with no console/page errors.
- Prompt metadata collapse passed with no console/page errors.
- Drafts navigation passed with no console/page errors.
- Cmd+B sidebar collapse passed with no console/page errors.
- The workbench stayed mounted in all scenarios.

## Automated Checks

- `npm run build` in the Prompt Workbench app: passed.
- `uv run --with pytest --with PyYAML --with pydantic --with fastapi --with uvicorn --with httpx python -m pytest tests/release/test_prompt_workbench.py -q`: passed, 42 tests.

## Second Opinion

A review-only Claude pass agreed that the storage exception path is a plausible crash root cause
and recommended two follow-ups before final acceptance: add a root-level app error boundary and
reduce dock layout persistence churn. Both follow-ups were implemented. A final review-only Claude
pass recommended tightening the raw-storage regression and moving a dock focus persistence write out
of a React state updater; both follow-ups were implemented and retested.

## Residual Risk

The original embedded tab may remain a stale wedged browser instance from the failed state. A hard
refresh or a new in-app browser tab is required to pick up the rebuilt bundle. The fixed bundle
serves a fresh app shell and survives storage-unavailable collapse flows in real browser QA. The
reported macOS helper embedded browser should still get one final smoke pass after reopening the
wedged tab, because this report's completed interaction QA used headed Chromium against the same
local production bundle.
