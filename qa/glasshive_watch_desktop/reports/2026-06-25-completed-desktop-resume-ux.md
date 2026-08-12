# Completed Desktop Resume UX QA - 2026-06-25

<!-- qa-evidence-exempt: Historical focused UX evidence retained for lineage; current full-view acceptance is recorded in later feature reports. -->

## Scope

This report covers the reusable public-safe repro for a completed GlassHive worker whose live desktop
compute is no longer attached. The expected product behavior is:

- Completed or parked workers do not waste compute just because a user opens a link.
- Existing results and generated files remain visible from Watch / Steer.
- The desktop frame must not look broken with an endless `Desktop reconnecting` loop when the run is
  already complete.

Private enterprise links, account identifiers, screenshots, and logs are intentionally excluded.

## Repro Harness

- Fixture: `qa/glasshive_watch_desktop/scripts/completed_desktop_fixture.py`
- UI assets served: real `frontends/glass-drive-ui/src/glass_drive_ui/static/watch.html`,
  `desktop.html`, `watch.js`, and `desktop.js`
- Worker payload: synthetic completed worker, `codex-cli` profile, two public-safe deliverables
- noVNC behavior:
  - `worker-completed-no-view`: no desktop advertised.
  - `worker-completed-import-502`: `rfb.js` import deliberately returns HTTP 502.
  - `worker-completed-disconnect`: `rfb.js` imports a tiny synthetic RFB class that emits a disconnect.
  - `worker-active-disconnect`: active run imports a tiny synthetic RFB class, drops once, then
    reconnects on the next refresh.

The fixture reproduces the important bug class without customer data: the live payload advertises a
desktop-ish runtime, but the desktop asset path is unavailable while the worker is already completed.

## Fix Under Test

`desktop.js` now keeps the last live payload, uses canonical active/settled state constants, and
consults the runtime view-health signal before showing a reconnect loop. When a workspace is completed,
parked, paused, or failed, the desktop frame shows an honest settled-state message and points the user
to the status panel or resume path.

`watch.js` also carries the same UI revision and no longer overlays a completed desktop iframe with
`Preparing live workspace`. This matters when an older browser tab refreshes after the worker is
complete: the parent Watch page and the nested desktop frame now agree that the workspace is parked,
not actively reconnecting.

Expected completed copy:

- `Workspace complete`
- `The latest output and workspace files are available from the status panel. Continue this workspace when you want fresh compute.`
- `Clipboard sync: inactive until workspace resumes`

## Evidence

Automated tests:

```text
frontends/glass-drive-ui: uv run --group dev python -m pytest tests/test_server.py -q
Result: 91 passed
```

```text
runtime_phase1: uv run --group dev python -m pytest \
  tests/test_api.py::test_live_payload_survives_unavailable_idle_compute \
  tests/test_api.py::test_live_payload_promotes_workspace_html_as_deliverable \
  tests/test_api.py::test_completed_file_callback_adds_signed_open_download_and_watch_links \
  tests/test_api.py::test_live_payload_file_deliverable_includes_signed_open_and_download_links -q
Result: 4 passed
```

Browser QA:

- Opened the no-view Watch URL in a real Playwright browser. It showed completed state with zero console
  errors. Opening `/desktop/worker-completed-no-view` directly showed `Workspace complete`.
- Opened the import-502 Watch URL and waited past the next desktop refresh interval. The console still
  contained only one deliberate noVNC 502, and the iframe stayed on `Workspace complete`.
- Opened the disconnect Watch URL. The synthetic RFB import succeeded, then emitted a disconnect; the
  iframe showed `Workspace complete` with zero console errors.
- Opening latest output on the disconnect case showed `Open file`, `Download file`, and
  `Workspace files (2)`. Both synthetic files remained listed with open/download actions.
- Opened the active-disconnect Watch URL and waited through the synthetic non-clean disconnect plus
  refresh. The iframe returned to `Sandbox connected`, the overlay was hidden, the URL carried
  `gh_ui_rev=20260625a`, there were zero console errors, and the active worker did not show
  `Workspace complete`.

Expected browser console noise:

- HTTP 502 for the synthetic `/novnc/.../core/rfb.js` path.

The no-view direct `/desktop` case emitted only a fixture `favicon.ico` 404, not a GlassHive noVNC
error.

## ClaudeViv Review Follow-Up

ClaudeViv reviewed the first local fix and correctly flagged that `ready` was too broad as a settled
worker state, and that the browser fixture should cover the realistic no-view and disconnect paths.
The final fix addressed both points before deployment:

- `ready` is no longer treated as settled by itself.
- active and settled states are centralized in named constants aligned to the backend state model.
- runtime `view_health.healthy === false` can suppress probing for terminal/parked workspaces.
- browser QA now covers no-view, import failure, and disconnect cases.

## Result

`GHWATCH-008` is `PASS` for the completed/parked workspace scope and for the local browser
active-disconnect client reconnect slice. Broader live Docker noVNC self-heal coverage stays owned by
the existing runtime regression case and future full live-worker QA runs.
