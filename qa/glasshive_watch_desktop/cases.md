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
