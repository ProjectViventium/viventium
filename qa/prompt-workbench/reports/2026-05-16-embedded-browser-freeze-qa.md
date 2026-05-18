<!-- qa-evidence-exempt: legacy or audit-style report; supersede with the standard run-report template on next rerun. -->
# Prompt Workbench Embedded Browser Freeze QA - 2026-05-16

## Scope

Validated the Prompt Workbench after a user-reported freeze in the embedded browser. This pass was
local-only and did not run reviewed live sync, cloud push, or live model evals.

## Findings

- The backend and CLI lifecycle were healthy: `/api/health` returned `ok`, and the workbench was
  running on the loopback URL.
- The embedded browser control path could list the existing workbench tab, but reload/attach timed
  out after the earlier freeze. This means the existing embedded tab was wedged and could not be
  used as the only proof surface.
- Headed Chrome reproduced the relevant app width and showed the earlier layout problem: the old
  breakpoint stacked the atlas above the workbench too early and made collapse feel ineffective.
- A review-only Claude pass agreed with that diagnosis and identified another issue: action
  messages could add a second topbar row while the app shell pinned the header to a fixed height.
- The original built bundle eagerly included Monaco editor code before the Prompt tab was opened,
  creating unnecessary startup work for embedded browsers.
- A second review-only Claude pass challenged the remaining Drafts-tab freeze path and identified
  a stronger likely failure mode: stale app HTML can point at missing lazy chunks, and Suspense
  alone does not recover from dynamic import failures.
- The workbench had allowed cached `304 Not Modified` responses for the app shell after rebuilds.
  That could keep a bad or stale local bundle alive in an embedded tab.

## Fixes Verified

- Reduced side panel widths and kept embedded-width browser layouts in the desktop sidebar model
  until a smaller breakpoint.
- Changed the app shell header row to `minmax(64px, auto)` so action messages grow the header
  without overlapping the work area.
- Debounced React Flow resize refitting and removed resize animation from automatic refits.
- Constrained the Settings popover and close button so it does not block unrelated header controls
  after close.
- Code-split the heavy dock panels. The initial app chunk is now about 518 KB, while the Prompt
  editor/Monaco chunk loads only when the Prompt tab is opened.
- Scoped static cache policy: `/` and `/index.html` are now always served fresh with `no-store`,
  while hashed `/assets/...` files remain immutable.
- Added `/api/build-version` with a public-safe index hash and entry asset names for local
  diagnostics.
- Added a panel-level error boundary around every lazy dock view. If a stale or missing Drafts
  chunk fails to load, the UI shows a "Drafts could not load" recovery panel with a reload action
  instead of silently freezing.
- Hardened dock layout localStorage handling so stale old keys are cleared and storage failures
  fall back to the default layout.

## Browser QA

Tooling:

- Headed Google Chrome through Playwright against the production bundle at `http://127.0.0.1:8781/`.

Scenarios:

1. Loaded an embedded-width desktop viewport.
2. Confirmed no horizontal overflow and a 64px header before actions.
3. Collapsed and expanded Prompt Flow from the header icon.
4. Confirmed `Cmd/Ctrl+B` does not steal focus from the search input, then collapses and expands
   Prompt Flow when focus is outside editable controls.
5. Collapsed and expanded the Sync sidebar.
6. Opened Settings from the logo, toggled Dark/System, closed Settings, and confirmed Sync collapse
   still works.
7. Opened Prompt, waited for the Prompt editor assets, collapsed and expanded the metadata sidebar.
8. Ran a no-live eval preview and confirmed the action message fits inside the expanded header.
9. Loaded a mobile dark viewport and confirmed no horizontal overflow and working sidebar collapse.
10. Reloaded the rebuilt production bundle and confirmed the app shell returned `200 OK` with
    `Cache-Control: no-store`.
11. Confirmed built assets returned `Cache-Control: public, max-age=31536000, immutable`.
12. Seeded stale old dock layout state, reloaded, clicked Drafts, and confirmed Draft Review opened
    in about 314 ms with no console errors and low event-loop lag.
13. Simulated a missing `DraftPanel-*.js` chunk, clicked Drafts, and confirmed the recovery panel
    appeared while the rest of the workbench remained responsive.

## Automated Checks

- `npm run build` in the Prompt Workbench app: passed.
- `uv run --with pytest --with PyYAML --with pydantic --with fastapi --with uvicorn --with httpx python -m pytest tests/release/test_prompt_workbench.py -q`: passed, 41 tests.

## Residual Risk

The already-open embedded browser tab from the failed state remained wedged from the tool side even
after the product bundle was fixed. A hard reload or new embedded tab is required to pick up the
new split bundle. The running local workbench server is healthy and serving the rebuilt assets. New
tabs and refreshed sessions receive the fresh app shell, and stale lazy-chunk failures now show a
recoverable in-app message instead of a dead panel.
