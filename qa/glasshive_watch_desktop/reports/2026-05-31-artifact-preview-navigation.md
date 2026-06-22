<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# GlassHive Watch Artifact Preview Navigation - 2026-05-31

## Scope

This report covers the escaped Watch / Steer artifact-delivery bug where clicking `View workspace`
from inside a completed file preview could recursively load another Watch / Steer page inside the
preview frame.

Public-safety note: live deployment names, raw worker IDs, signed links, tokens, account identifiers,
and secret-bearing command lines are intentionally omitted. Raw browser and VM evidence stayed in the
private user-data area or transient tool output.

## Requirements

- `docs/requirements_and_learnings/01_Key_Principles.md`: GlassHive data in/out must be exact;
  workers stay general; user-visible browser behavior requires user-grade QA.
- `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`: artifact links
  open a GlassHive preview first, raw downloads are explicit, signed actions remain self-authorizing,
  preview workspace navigation must not recurse inside the frame, and multiple generated files must
  stay discoverable from Watch / Steer.
- `qa/glasshive_watch_desktop/cases.md`: `GHWATCH-003`, `GHWATCH-004`, and `GHWATCH-005`.

## Fix Verified

- Artifact preview `View workspace` now includes `target="_top"` and `rel="noopener noreferrer"`.
- The artifact preview page is intentionally same-origin embeddable by Watch / Steer:
  `frame-ancestors 'self'` and `X-Frame-Options: SAMEORIGIN` allow the signed preview to appear in
  the GlassHive frame while still blocking cross-origin framing.
- Existing signed download/open semantics were preserved.
- The completed file preview remains stable while signed action URLs rotate.
- Watch / Steer now renders a general workspace-file inventory from the runtime artifact list. This
  is not a worker prompt rule and does not force a file output; it only surfaces real files that
  already exist.
- The live payload reuses one bounded breadth-first workspace inventory for the workspace summary
  and signed artifact list, and the inventory walk prunes scaffold/heavy directories before descent.
- The UI asset revision is `20260531b`, so browsers do not keep stale Watch / Steer JavaScript or
  CSS after this fix.

## Automated Checks

- `node --check viventium_v0_4/GlassHive/frontends/glass-drive-ui/src/glass_drive_ui/static/watch.js`:
  PASS.
- `cd viventium_v0_4/GlassHive && runtime_phase1/.venv/bin/python -m pytest runtime_phase1/tests/test_api.py::test_live_payload_file_deliverable_includes_signed_open_and_download_links runtime_phase1/tests/test_api.py::test_live_payload_artifact_inventory_includes_multiple_signed_files runtime_phase1/tests/test_api.py::test_artifact_open_page_previews_text_without_forcing_download runtime_phase1/tests/test_api.py::test_enterprise_signed_artifact_open_page_actions_remain_signed runtime_phase1/tests/test_mcp_server.py::test_workspace_artifacts_returns_signed_download_links -q`:
  PASS, 5 tests.
- `cd viventium_v0_4/GlassHive/frontends/glass-drive-ui && .venv/bin/python -m pytest tests/test_server.py::test_launcher_workspace_hive_static_controls -q`:
  PASS. This static frontend regression check now asserts the Watch / Steer file-preview embedding
  contract: file deliverable promotion, stable preview keys, no reconnect loop for file previews,
  result actions, workspace-file inventory rendering, and the `Open delivered file in new tab` menu
  label.
- `cd viventium_v0_4/GlassHive && runtime_phase1/.venv/bin/python -m pytest runtime_phase1/tests -q`:
  PASS for the full GlassHive runtime test suite after tightening one asynchronous callback test to
  wait for the existing capacity-wait callback instead of reading the callback capture immediately.
- `cd viventium_v0_4/GlassHive/frontends/glass-drive-ui && .venv/bin/python -m pytest tests -q`:
  PASS for the full GlassHive UI test suite.
- After the Claude follow-up fixes, reran:
  - `node --check viventium_v0_4/GlassHive/frontends/glass-drive-ui/src/glass_drive_ui/static/watch.js`: PASS.
  - `cd viventium_v0_4/GlassHive/frontends/glass-drive-ui && .venv/bin/python -m pytest tests/test_server.py::test_launcher_workspace_hive_static_controls -q`: PASS.
  - the focused five runtime artifact tests listed above: PASS.
  - the full GlassHive runtime test suite: PASS.
  - the full GlassHive UI test suite: PASS.
- After the final breadth-first inventory refinement, reran:
  - the focused five runtime artifact tests listed above: PASS.
  - the full GlassHive runtime test suite: PASS.

## Live Browser QA

Surface: approved enterprise GlassHive Watch / Steer deployment, using a synthetic completed text
artifact with marker content.

Steps run:

1. Opened a fresh signed Watch / Steer URL in the in-app browser.
2. Verified the top-level page showed `Completed`, one preview iframe, and a delivered-file summary.
3. Inspected the embedded artifact preview.
4. Verified the embedded preview had exactly one `Download file` link and exactly one
   `View workspace` link.
5. Verified the `View workspace` link target was `_top` and rel contained `noopener noreferrer`.
6. Verified the embedded preview had zero nested iframes before clicking.
7. Clicked `View workspace` from inside the embedded preview.
8. Verified the top-level page remained a single Watch / Steer surface with one preview iframe.
9. Verified the embedded preview still had zero nested iframes and did not contain recursive steer
   controls.
10. Fetched the live `Download file` action and verified status `200`, `Content-Disposition:
    attachment`, no-store cache policy, `nosniff`, exact byte count, and the synthetic marker.

Observed result:

- PASS. The recursive workspace-in-preview failure did not reproduce after the runtime patch.
- PASS. File preview and explicit download still worked.
- PASS. Signed action URL rotation did not destabilize the displayed preview.

## Multi-File QA

Prompt shape:

`Create exactly two user-facing text files in the workspace root: first.txt containing exactly FIRST_OK and second.txt containing exactly SECOND_OK.`

Runtime evidence:

- Worker completed.
- Live payload promoted the latest file deliverable.
- Runtime artifact inventory contained `first.txt` and `second.txt`.
- Direct artifact downloads returned exact marker content for both files.

Browser evidence:

- Watch / Steer showed the latest file preview for the promoted artifact.
- The result panel displayed `Workspace files (2)`.
- Both `first.txt` and `second.txt` were visible with explicit `Open` and `Download` actions.
- Downloading from the visible workspace-file rows returned `FIRST_OK` and `SECOND_OK`, with
  attachment and `nosniff` headers.
- The loaded UI assets used `watch.js?v=20260531b` and `styles.css?v=20260531b`.
- Browser DOM/text QA captured the expanded panel with both files and their actions.
- Final smoke after the breadth-first runtime deploy repeated the visible multi-file check and exact
  marker downloads.

Observed result:

- PASS after fix. The first multi-file browser check exposed that extra files were not discoverable
  in the Watch / Steer UI. The deployed fix surfaces the runtime artifact inventory generally, without
  asking the worker to change its behavior or forcing every task into file output.

## No-File QA

Prompt shape:

`Do not create, modify, or save any user-facing files. Return only this final report: FINAL REPORT: NO_FILE_DELIVERY_OK`

Runtime evidence:

- Worker completed.
- Final output contained the synthetic marker.
- Live payload had no deliverable.
- Runtime artifact inventory was empty.

Browser evidence:

- Watch / Steer showed `NO_FILE_DELIVERY_OK`.
- Result actions were hidden.
- Artifact list was hidden.
- Visible text did not include `Open file`, `Download file`, or `Workspace files`.
- The loaded UI asset used `watch.js?v=20260531b`.
- Browser DOM/text QA captured the text-only result with no file actions.
- Final smoke after the breadth-first runtime deploy repeated the no-file check.

Observed result:

- PASS. Text-only/no-file work did not invent downloadable artifacts.

## Runtime Evidence

- Runtime health endpoint returned `ok` after deployment.
- Runtime and UI services were active after restart.
- Sanitized runtime journal showed expected service restart/startup lines and no new stack traces.
- Temporary deployment SSH keys matching this QA run were removed; VM authorized-key scan returned
  zero matching entries.
- Final post-deploy check after the breadth-first runtime update again showed runtime active, UI
  active, health `ok`, no recent `Traceback`/`ERROR`/`Exception` lines, and no temporary key entry.

## Second-Opinion Review

Review-only Claude pass confirmed the `target="_top"` fix addresses the iframe-recursion failure and
is consistent with the existing GlassHive navigation pattern. It found no blocking issues. It also
flagged follow-up risks, handled as follows:

- The CSP/X-Frame-Options change is part of the artifact preview embed contract and is now documented
  above instead of being treated as an invisible implementation detail.
- The frontend embed path needed a regression guard beyond `node --check`; the static Watch / Steer
  controls test now asserts the file-preview embedding contract.
- The new artifact inventory added hot-path filesystem work; the runtime now reuses the workspace
  inventory between the workspace summary and artifact list, and the traversal prunes ignored
  directories before descent.
- The UI silently capped the displayed inventory at 20 files; it now renders an explicit
  `N more files` overflow row when the runtime returns more than the visible slice.
- Claude follow-up review found no blocker/regression in those changes. It accepted the performance
  mitigation for this closure, accepted the explicit 20-row overflow behavior, and flagged a low
  edge case where depth-first traversal could starve shallow later siblings. The inventory traversal
  was then changed to breadth-first and retested.
- Final Claude review of the breadth-first refinement found no blocker/regression and accepted the
  final state for closure. It noted only non-blocking polish: explicit `scandir` handle closing and
  same-level budget fairness for very wide workspaces.

Claude also noted that the broader local GlassHive working tree contains unrelated uncommitted work.
That is a repo-state/release hygiene concern, not a reason to revert this hotfix; any commit or
release should isolate the artifact-preview changes from unrelated local edits.

## Remaining Risk

- A deeper browser/DOM automation test for the frontend embedding lifecycle would be stronger than
  the current static frontend contract test. The live browser QA covered the real escaped behavior;
  the static test prevents the current embedding and artifact-list contracts from disappearing
  silently.
- A future broader performance cleanup can collapse other legacy deliverable/image discovery walks
  into the same inventory source. This fix removed the extra artifact-list walk introduced by this
  change, pruned excluded directories before descent, and changed the shared inventory traversal to
  breadth-first; it did not refactor every older discovery path.
- The bounded breadth-first inventory still has ordinary bounded-listing limits: extremely wide
  same-level output sets can consume the cap before later same-level siblings, and the current
  implementation relies on Python's iterator cleanup for `os.scandir`. Claude classified both as
  non-blocking polish, not closure blockers.
