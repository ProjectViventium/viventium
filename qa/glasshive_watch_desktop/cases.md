# GlassHive Watch Desktop QA Cases

## Case ID Convention

Use stable `GHWATCH-NNN` IDs for glasshive watch desktop cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `GHWATCH-001` | Live desktop/watch flows expose enough state for takeover without leaking private screen data into public artifacts. | User-visible behavior matches source, docs, persisted state, and logs | GlassHive desktop/watch surface, worker status, callback evidence | `tests/release/test_prompt_registry.py` plus user-grade QA when visible | PASS 2026-05-23 local enterprise watch UI; see `qa/glasshive_azure_enterprise/reports/2026-05-23-launcher-watch-enterprise-qa.md`. |
| `GHWATCH-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | PASS 2026-05-23 for sanitized report; see `qa/glasshive_azure_enterprise/reports/2026-05-23-launcher-watch-enterprise-qa.md`. |
| `GHWATCH-003` | Completed file deliverables are usable from Watch / Steer without surprising downloads or recursive workspace embeds. | User sees the delivered file preview, can explicitly download it, and can return to the workspace without nested watch pages. | Watch / Steer file preview iframe, artifact open route, download route, project workspace link | `runtime_phase1/tests/test_api.py::test_artifact_open_page_previews_text_without_forcing_download`, `runtime_phase1/tests/test_api.py::test_enterprise_signed_artifact_open_page_actions_remain_signed`, and browser QA | PASS 2026-05-31; see `qa/glasshive_watch_desktop/reports/2026-05-31-artifact-preview-navigation.md`. |
| `GHWATCH-004` | Multiple file deliveries remain discoverable without forcing one hardcoded output format. | User can verify the latest delivered file and inspect/download each workspace artifact when more than one file exists. | Watch / Steer latest result, workspace artifact list, artifact open/download route | Browser QA plus artifact API/log evidence | PASS 2026-05-31; see `qa/glasshive_watch_desktop/reports/2026-05-31-artifact-preview-navigation.md`. |
| `GHWATCH-005` | Non-file or no-file tasks do not invent downloadable artifacts. | User sees the final result/status without bogus `Open file`, `Download file`, or workspace-file actions. | Watch / Steer latest result panel, callback/status output | Browser QA plus live payload inspection | PASS 2026-05-31; see `qa/glasshive_watch_desktop/reports/2026-05-31-artifact-preview-navigation.md`. |
| `GHWATCH-006` | Latest workspace output is visibly actionable from the watch ribbon and workspace overview. | User can immediately tell where to click to inspect the latest output/status, then close it without leaving the live surface. | Watch / Steer ribbon, result panel, workspace overview tile | `frontends/glass-drive-ui/tests/test_server.py::test_launcher_workspace_hive_static_controls` plus Playwright browser QA | PASS 2026-06-16; see `qa/glasshive_watch_desktop/reports/2026-06-16-latest-output-affordance.md`. |
| `GHWATCH-007` | A Watch URL with `surface=desktop` keeps the live workstation desktop primary after file delivery. | User can still inspect/control the live worker while file actions remain explicit. | Watch / Steer, embedded desktop, latest-output file actions | Static UI tests plus Playwright/Chrome browser QA | PASS 2026-06-16; see `qa/glasshive_watch_desktop/reports/2026-06-16-worker-capability-and-delivery-story.md`. |
| `GHWATCH-008` | `view_available` means the noVNC desktop asset path is reachable. | User is not sent to a broken or endlessly reconnecting desktop view. | Runtime describe API, noVNC proxy/assets, Watch / Steer desktop iframe | `runtime_phase1/tests/test_docker_sandbox.py::test_describe_self_heals_novnc_when_service_port_resets` plus browser QA | PASS 2026-06-16; see `qa/glasshive_watch_desktop/reports/2026-06-16-worker-capability-and-delivery-story.md`. |
| `GHWATCH-009` | LibreChat callback result persists into visible conversation state without raw tool plumbing. | User sees the final worker result after refresh/reopen. | LibreChat web conversation, callback outbox, message store | `LibreChat/api/server/routes/viventium/__tests__/glasshive.spec.js` plus authenticated browser QA | PASS 2026-06-16; see `qa/glasshive_watch_desktop/reports/2026-06-16-worker-capability-and-delivery-story.md`. |
| `GHWATCH-010` | Worker desktop browser starts with clean browser chrome by default. | User sees the worker browser without a bookmark bar or unsupported `--no-sandbox` warning. | Docker workstation container, worker browser process, noVNC desktop view | `runtime_phase1/tests/test_docker_sandbox.py` plus disposable Docker worker and Playwright noVNC QA | PASS 2026-06-16; see `qa/glasshive_watch_desktop/reports/2026-06-16-clean-browser-chrome.md`. |

## `GHWATCH-001` - Core User Flow

- Requirement: Live desktop/watch flows expose enough state for takeover without leaking private screen data into public artifacts.
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
- Last run: PASS 2026-05-23 local enterprise watch UI. Playwright verified the watch surface,
  latest result detail, managed project workspace link, pause/resume state, no overlapping overlay
  text, and zero page console errors after reload.

## `GHWATCH-002` - Public-Safe Evidence Record

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
- Last run: PASS 2026-05-23. Public report uses synthetic content and omits tokens, real account
  identifiers, raw DB rows, and private logs.

## `GHWATCH-003` - Completed File Preview Navigation

- Requirement: completed file deliverables must open in a GlassHive preview/landing page first, expose a separate explicit download action, and keep workspace navigation usable from embedded Watch / Steer.
- Risk covered: a generated artifact exists, but the user cannot inspect or navigate it because the preview recursively loads another watch page inside its own iframe.
- Preconditions: a completed GlassHive run has a synthetic public-safe file deliverable and a signed or authenticated Watch / Steer URL.
- Steps:
  1. Launch or open a completed worker whose task is equivalent to: `Create a text file named single-delivery.txt containing exactly GHWATCH_SINGLE_FILE_OK.`
  2. Open the Watch / Steer page through the real browser surface.
  3. Verify the main pane shows the file preview/landing page and the result panel has explicit file actions when applicable.
  4. If the worker output also mentions an external source/check URL, verify the created user file still wins over the incidental URL as the latest deliverable unless the real deliverable is workspace HTML.
  5. Click `Download file` and verify the downloaded bytes match the synthetic marker.
  6. Click `View workspace` from inside the preview page.
  7. Verify the browser navigates the top-level page or project/workspace surface and does not render another Watch / Steer page inside the preview iframe.
- Expected result: the preview is readable, the download is explicit and correct, and workspace navigation does not create nested GlassHive headers/footers or repeated steer controls.
- Forbidden result: clicking `View workspace` inside a preview recursively embeds watch/project UI inside the artifact preview frame, artifact access requires hidden proxy headers after opening from a signed link, or an incidental external URL in worker output is promoted ahead of the actual generated file.
- Evidence to capture: sanitized screenshot/DOM summary showing one top-level watch/workspace surface, download status/content hash or marker, artifact route headers, live payload summary, and relevant logs.
- Automation: artifact route tests plus browser QA on the real Watch / Steer surface.
- Last run: PASS 2026-05-31 on the approved enterprise GlassHive deployment. Browser QA verified
  one top-level watch frame, zero nested preview frames, `target="_top"` on `View workspace`, exact
  synthetic marker preview/download, explicit attachment headers, healthy runtime services, and no
  temporary deployment key left behind. See
  `qa/glasshive_watch_desktop/reports/2026-05-31-artifact-preview-navigation.md`.

## `GHWATCH-004` - Multiple File Delivery Discoverability

- Requirement: artifact delivery must stay general; GlassHive should not force every task into one file or one response shape.
- Risk covered: the UI only handles the latest single-file happy path and strands additional generated files.
- Preconditions: a completed worker has at least two synthetic public-safe file deliverables in its workspace.
- Steps:
  1. Launch or open a completed worker whose task is equivalent to: `Create two files: first.txt containing FIRST_OK and second.txt containing SECOND_OK.`
  2. Open Watch / Steer and verify the latest result or promoted file is usable.
  3. Use `View workspace` or the project workspace surface to inspect the workspace file list.
  4. Open or download both generated files and verify their markers.
- Expected result: the latest result is usable, and workspace navigation exposes the broader project context so multiple deliverables are discoverable.
- Forbidden result: the UI claims the work completed but only exposes a stale or unrelated file, or workspace navigation cannot be used to find additional deliverables.
- Evidence to capture: sanitized file list/counts, marker verification, and visible navigation state.
- Automation: artifact listing/download API tests plus browser QA.
- Last run: PASS 2026-05-31 on the approved enterprise GlassHive deployment. The first run exposed
  a gap: the latest file preview worked, but additional files were discoverable only through API
  evidence, not the user surface. The fix added a general Watch / Steer workspace-file list sourced
  from the runtime artifact inventory. Browser QA then verified `first.txt` and `second.txt` were
  both visible with explicit `Open` and `Download` actions, and both downloads returned the expected
  marker content with attachment and `nosniff` headers.

## `GHWATCH-005` - No-File Result Does Not Invent Artifacts

- Requirement: host and UI must broker data in/out exactly and avoid invented artifacts or forced download formats.
- Risk covered: a text-only or research-only worker result is wrapped in a fake downloadable file because a previous artifact QA case overfit the behavior.
- Preconditions: a completed worker returns a final report without creating a user deliverable file.
- Steps:
  1. Launch or open a completed worker whose task is equivalent to: `Return a final report containing NO_FILE_DELIVERY_OK and do not create any files.`
  2. Open Watch / Steer and inspect the latest result panel.
  3. Verify no `Open file` or `Download file` action appears unless an actual user deliverable exists.
  4. Verify status/callback wording does not claim a file was created.
- Expected result: the user sees the final text/status result directly, with no bogus file actions.
- Forbidden result: GlassHive fabricates a file delivery link, forces a download response, or claims an artifact exists when the worker did not produce one.
- Evidence to capture: visible result panel, live payload deliverable state, and final output marker.
- Automation: live payload tests plus browser QA.
- Last run: PASS 2026-05-31 on the approved enterprise GlassHive deployment. Browser QA verified a
  no-file worker result showed `NO_FILE_DELIVERY_OK` and did not display `Open file`, `Download file`,
  `Workspace files`, result actions, or artifact-list rows.

## `GHWATCH-006` - Latest Workspace Output Affordance

- Requirement: the latest workspace output/status entry point must be visibly actionable and
  understandable without guessing which text is clickable.
- Risk covered: users miss the result/status panel because the clickable area looks like passive
  ribbon text or an inert workspace-tile status block.
- Preconditions: GlassHive operator UI is running with a synthetic public-safe workspace payload or
  an existing local workspace.
- Steps:
  1. Open the Watch / Steer page in a real browser.
  2. Verify the ribbon contains a distinct `Latest workspace output` control with a current status,
     summary, and visible `Open status` action.
  3. Click or keyboard-activate the control.
  4. Verify the result/status panel opens, the control changes to `Close status`, and the panel can
     be closed without leaving the watch surface.
  5. Open the workspace overview and verify each visible workspace tile shows the same latest-output
     area as a clickable status control that opens the full watch/status surface.
- Expected result: the latest-output affordance is visually distinct, keyboard accessible, and
  responsive on desktop and mobile widths.
- Forbidden result: the latest output appears as passive text, only a tiny unlabelled area is
  clickable, the panel cannot be closed predictably, or mobile wrapping hides the action.
- Evidence to capture: browser screenshot or DOM summary for desktop and mobile widths, static test
  result, and no console errors.
- Automation: `frontends/glass-drive-ui/tests/test_server.py::test_launcher_workspace_hive_static_controls`
  plus Playwright browser QA.
- Last run: PASS 2026-06-16 local static UI QA. See
  `qa/glasshive_watch_desktop/reports/2026-06-16-latest-output-affordance.md`.

## `GHWATCH-007` - Desktop Watch Surface Stays Desktop After File Delivery

- Requirement: a Watch URL with `surface=desktop` must keep the live workstation desktop as the
  primary surface; completed files are explicit actions/status, not iframe replacements.
- Risk covered: a completed PDF/DOC/PPT artifact hijacks the desktop frame, so the user sees a file
  preview instead of the worker workspace and cannot visually inspect/control the workstation.
- Preconditions: a completed worker has a live desktop and at least one file deliverable.
- Steps:
  1. Open `/watch/{worker_id}?surface=desktop&project_id={project_id}` in a real browser.
  2. Verify the primary iframe/frame loads `/desktop/{worker_id}` rather than an artifact
     `/artifacts/open` URL.
  3. Verify the latest-output/status panel still exposes the completed file through explicit open
     and download actions.
  4. Verify the embedded desktop shows the worker's visible workstation through noVNC.
- Expected result: live desktop is primary; deliverable actions are visible and intentional.
- Forbidden result: the desktop tab/frame displays a PDF/file preview as the main surface, or the
  menu labels the delivered file as the current desktop.
- Evidence to capture: browser screenshot, frame URL, noVNC asset status, latest-output actions,
  console state.
- Automation: `frontends/glass-drive-ui/tests/test_server.py::test_launcher_workspace_hive_static_controls`
  plus Playwright/Chrome browser QA.
- Last run: PASS 2026-06-16 local browser QA. Public-safe summary:
  `qa/glasshive_watch_desktop/reports/2026-06-16-worker-capability-and-delivery-story.md`;
  screenshot evidence remains local/private unless explicitly reviewed for publication.

## `GHWATCH-008` - noVNC Health Is Required For `view_available`

- Requirement: `view_available` means the noVNC desktop asset path is reachable, not merely that a
  Docker port is mapped.
- Risk covered: Watch says the desktop is available but the browser shows `Desktop reconnecting`
  forever because websockify is resetting connections.
- Preconditions: a Docker workstation worker has a mapped noVNC port.
- Steps:
  1. Query worker live/runtime details and open `/desktop/{worker_id}`.
  2. Fetch `/novnc/{worker_id}/core/rfb.js` through the operator UI proxy.
  3. Simulate or detect a failed noVNC asset path and verify runtime self-heals before advertising
     the desktop as available.
  4. Verify the browser attaches to a noVNC canvas after recovery.
- Expected result: noVNC health succeeds or the UI reports desktop unavailable truthfully; self-heal
  uses service-local `/tmp` and does not rely on mounted worker-home `TMPDIR`.
- Forbidden result: reset/502 noVNC asset path with `view_available=true`, or a worker that remains
  visually black/reconnecting while status says the desktop is ready.
- Evidence to capture: noVNC stderr/stdout summary, asset status, browser screenshot/canvas count,
  targeted regression test output.
- Automation: `runtime_phase1/tests/test_docker_sandbox.py::test_describe_self_heals_novnc_when_service_port_resets`.
- Last run: PASS 2026-06-16 local browser/runtime QA. Public-safe summary:
  `qa/glasshive_watch_desktop/reports/2026-06-16-worker-capability-and-delivery-story.md`;
  screenshot evidence remains local/private unless explicitly reviewed for publication.

## `GHWATCH-009` - LibreChat Callback Result Surfaces After Persistence

- Requirement: a visible GlassHive completion callback must update both the message record and the
  owning conversation metadata/list state so web chat can surface the result after refresh.
- Risk covered: GlassHive outbox marks the callback delivered and Mongo contains the final message,
  but LibreChat's conversation list/current view can miss the new result because `updatedAt` and
  message ids were not advanced.
- Preconditions: a GlassHive run completes with callback metadata for a LibreChat conversation.
- Steps:
  1. Inspect the callback outbox and verify terminal callback delivery.
  2. Inspect the conversation/message store and verify the final callback message exists.
  3. Open the conversation in an authenticated browser session and verify the final result is
     visible without raw tool-call code.
  4. Verify callback receiver tests assert the conversation is touched after visible callback
     persistence.
- Expected result: the chat shows the user-facing final result, artifact links, and View / Steer
  link after refresh/reopen; no raw callback IDs, HMAC fields, or tool-call code appear.
- Forbidden result: delivered callback row with a hidden/stale chat result, duplicate final callback
  branches, or raw GlassHive plumbing shown to the user.
- Evidence to capture: sanitized DB/outbox summary, authenticated browser screenshot, callback
  receiver test output.
- Automation: `LibreChat/api/server/routes/viventium/__tests__/glasshive.spec.js`.
- Last run: PASS 2026-06-16 local Chrome QA and callback receiver test. Public-safe summary:
  `qa/glasshive_watch_desktop/reports/2026-06-16-worker-capability-and-delivery-story.md`;
  screenshot evidence remains local/private unless explicitly reviewed for publication.

## `GHWATCH-010` - Clean Worker Browser Chrome

- Requirement: a worker desktop browser must open with quiet, professional browser chrome by
  default: no bookmark bar and no unsupported `--no-sandbox` command-line warning banner.
- Risk covered: the user-visible desktop looks broken or unsafe before the worker does any work,
  because the Selenium workstation wrapper silently injects `--no-sandbox` or Chromium cannot start
  its own sandbox inside Docker.
- Preconditions: a Docker workstation worker can be created with synthetic public-safe content and
  a noVNC desktop URL.
- Steps:
  1. Create or recreate a disposable Docker workstation worker from the current runtime code.
  2. Verify Docker container security options allow Chromium's user-namespace sandbox and
     `unshare -U` succeeds inside the worker.
  3. Open the worker browser through the same desktop action path the user uses.
  4. Inspect the Chromium process tree and verify no command line contains `--no-sandbox`.
  5. Inspect the worker Chromium profile preferences and verify
     `bookmark_bar.show_on_all_tabs` is `false`.
  6. Open the noVNC desktop in a real browser and capture a screenshot showing the worker browser
     has no bookmark bar and no unsupported command-line warning banner.
- Expected result: the browser displays the requested page/workspace with no bookmarks row and no
  unsupported flag banner; process/profile evidence agrees with the screenshot.
- Forbidden result: a Debian bookmarks row is visible, Chromium shows the unsupported
  `--no-sandbox` warning, or source tests pass while the live worker process still carries
  `--no-sandbox`.
- Evidence to capture: sanitized screenshot, Docker security option summary, `unshare -U` result,
  Chromium process-argument summary, profile preference summary, and regression test output.
- Automation:
  `runtime_phase1/tests/test_docker_sandbox.py::test_create_container_adds_host_gateway_alias_for_broker_reachability`,
  `runtime_phase1/tests/test_docker_sandbox.py::test_browser_desktop_action_uses_clean_chromium_profile_and_no_no_sandbox`,
  and
  `runtime_phase1/tests/test_docker_sandbox.py::test_prime_idle_desktop_uses_clean_chromium_profile_and_no_no_sandbox`.
- Last run: PASS 2026-06-16 local disposable Docker worker and Playwright noVNC QA. See
  `qa/glasshive_watch_desktop/reports/2026-06-16-clean-browser-chrome.md`.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Glasshive Watch Desktop. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `GHWATCH-UC-001` | On GlassHive desktop/watch surface, worker status, callback evidence, verify that live desktop/watch flows expose enough state for takeover without leaking private screen data into public artifacts. | owning requirement for `GHWATCH-001` / `GHWATCH-001` | GlassHive desktop/watch surface, worker status, callback evidence | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to GHWATCH-001. | User-visible behavior matches source, docs, persisted state, and logs | PASS 2026-05-23 local enterprise watch UI. |
| `GHWATCH-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `GHWATCH-002` / `GHWATCH-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to GHWATCH-002. | The user sees an honest setup, retry, or degraded-state result for GHWATCH-002; no fake success is accepted. | PASS 2026-05-23 sanitized report. |
| `GHWATCH-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `GHWATCH-002` / `GHWATCH-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to GHWATCH-002. | GHWATCH-002 remains correct after the persistence or parity step and final wording matches evidence. | PASS 2026-05-23 after runtime reload and report update. |
| `GHWATCH-UC-004` | Create or open a completed single-file GlassHive task, then preview, download, and click `View workspace` from inside the preview. | artifact link semantics / `GHWATCH-003` | Watch / Steer, artifact preview, artifact download, project workspace | Source, route headers, live payload, logs, and downloaded marker content. | File preview and download work; `View workspace` does not recursively embed watch/project UI. | PASS 2026-05-31; see `qa/glasshive_watch_desktop/reports/2026-05-31-artifact-preview-navigation.md`. |
| `GHWATCH-UC-005` | Create or open a completed multi-file GlassHive task and verify the latest result plus project workspace deliverables. | artifact discoverability / `GHWATCH-004` | Watch / Steer and project workspace | Workspace file list, artifact API, logs, and marker content for each file. | Multiple deliverables remain discoverable without hardcoded output assumptions. | PASS 2026-05-31; see `qa/glasshive_watch_desktop/reports/2026-05-31-artifact-preview-navigation.md`. |
| `GHWATCH-UC-006` | Create or open a completed no-file task and verify the result does not invent file actions. | exact data in/out / `GHWATCH-005` | Watch / Steer latest result panel and live payload | Live payload deliverable state, final result text, logs. | Text-only/no-file work shows final output without fake artifact links. | PASS 2026-05-31; see `qa/glasshive_watch_desktop/reports/2026-05-31-artifact-preview-navigation.md`. |
| `GHWATCH-UC-007` | Open Watch / Steer and the workspace overview, then find and activate the latest workspace output/status affordance. | latest-output affordance / `GHWATCH-006` | Watch / Steer ribbon, result panel, workspace overview tile | Static UI source, browser DOM/screenshot, console state, and responsive layout checks. | The user can clearly see where to open status/output, activate it by pointer or keyboard, and close it without leaving the live surface. | PASS 2026-06-16; see `qa/glasshive_watch_desktop/reports/2026-06-16-latest-output-affordance.md`. |
| `GHWATCH-UC-008` | Open a completed file-producing worker through `surface=desktop` and inspect both the live desktop and file actions. | desktop fidelity / `GHWATCH-007` | Watch / Steer, embedded desktop, latest-output file actions | Frame URL, noVNC canvas, asset proxy status, screenshot, console state. | The live desktop remains primary and file actions are explicit. | PASS 2026-06-16; see `qa/glasshive_watch_desktop/reports/2026-06-16-worker-capability-and-delivery-story.md`. |
| `GHWATCH-UC-009` | Reopen a GlassHive-backed LibreChat conversation after completion and verify the final result appears. | callback visibility / `GHWATCH-009` | Authenticated LibreChat web conversation, callback outbox, Mongo/message store | Outbox delivered row, message/conversation metadata, browser screenshot, callback test. | The final callback result is visible after refresh/reopen and no raw tool plumbing leaks. | PASS 2026-06-16; see `qa/glasshive_watch_desktop/reports/2026-06-16-worker-capability-and-delivery-story.md`. |
| `GHWATCH-UC-010` | Open the live worker desktop browser and inspect the browser chrome before doing work. | clean worker browser chrome / `GHWATCH-010` | Docker workstation browser through noVNC | Docker security option, Chromium process args, profile preferences, screenshot, console/network state. | The browser has no bookmark bar and no unsupported `--no-sandbox` warning banner. | PASS 2026-06-16; see `qa/glasshive_watch_desktop/reports/2026-06-16-clean-browser-chrome.md`. |
