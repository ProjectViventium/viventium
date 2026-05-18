# Prompt Workbench Cases

## PW-001 Registry Reuse

Requirement: `docs/requirements_and_learnings/49_Prompt_Architecture_and_Token_Efficiency.md`

User Outcome: Prompt Workbench renders exactly the same prompt text and hashes as the canonical
prompt registry.

Surfaces: API, Web UI

Steps:

1. Run `tests/release/test_prompt_workbench.py::test_workbench_render_matches_existing_prompt_registry`.
2. Open the workbench and select `main.conscious_agent`.

Expected Result: Rendered preview matches registry output. Human-facing scan surfaces use readable
labels; hashes stay in private/source metadata and tests, not in the Atlas or flow overview.

Forbidden Result: A second prompt parser, prompt database, or divergent render output.

Last Run: 2026-05-15, initial local implementation QA.

## PW-002 Sync State Classification

Requirement: two-way sync state model in the owning prompt architecture doc.

User Outcome: Source, live, and conflict states are visually clear.

Surfaces: API, Web UI

Steps:

1. Run sync classifier unit tests.
2. Load the dashboard and inspect the Live Drift Board.

Expected Result: `synced`, `live-ahead`, `source-ahead`, and `conflict` states are distinct and
summarized in counts and agent rows.

Forbidden Result: Silent overwrite or a generic "changed" state that hides which side moved.

Last Run: 2026-05-15, initial local implementation QA.

## PW-003 Live Import Draft Safety

Requirement: LibreChat Agent Builder edit imports must map cleanly or require manual selection, and
public prompt safety scanning must pass before public markdown can be applied.

Surfaces: API

Steps:

1. Run clean one-section import unit test.
2. Run ambiguous multi-section import unit test.
3. Run public safety block unit test.

Expected Result: Clean edits create a private reviewed draft; ambiguous edits return
`requires_manual_target`; private-looking text is refused from public markdown.

Forbidden Result: Guessing across multiple source sections or writing private content into public
source.

Last Run: 2026-05-15, initial local implementation QA.

## PW-004 Source Edit Draft

Requirement: Workbench edits source markdown only and require reviewed idempotency tokens before
apply.

Surfaces: Web UI, API

Steps:

1. Select a prompt.
2. Edit the body in Monaco.
3. Save draft.

Expected Result: A private draft with unified diff and idempotency token is created; no Mongo,
generated runtime file, or live agent is changed.

Forbidden Result: Direct runtime/App Support generated-file edits or silent Mongo write.

Last Run: 2026-05-15, initial local implementation QA.

## PW-005 Eval Visibility

Requirement: Eval cases and results are tied to prompt ids/hashes and remain public-safe.

Surfaces: Web UI, API

Steps:

1. Open the Eval Designer/Results panel.
2. Run the no-live eval subset.
3. Inspect the run summary.

Expected Result: Public-safe eval family/case table is visible; run output is stored under private
workbench evidence; raw private outputs are not written into public QA.

Forbidden Result: Raw prompts, transcripts, or private eval outputs committed into public QA.

Last Run: 2026-05-15, initial local implementation QA.

## PW-006 System Color Scheme

Requirement: Prompt Workbench must support automatic system-synced light and dark mode.

User Outcome: The dashboard is readable and visually coherent when the operating system is in light
or dark mode.

Surfaces: Web UI

Steps:

1. Open the workbench in a real browser with `prefers-color-scheme: light`.
2. Inspect atlas, flow, prompt editor, rendered preview, evals, drift board, and status panels.
3. Repeat with `prefers-color-scheme: dark`.

Expected Result: CSS variables and Monaco theme follow the system scheme automatically with no
manual app toggle required.

Forbidden Result: A dark system showing a light-only editor/canvas, unreadable chips/tables, or
console errors.

Last Run: 2026-05-15, local implementation QA after auto dark-mode support.

## PW-007 Draft Review Apply/Discard UI

Requirement: Workbench edits must create reviewed drafts before markdown changes can be applied.

User Outcome: A user can edit a prompt, see the patch, and either apply or discard it without
touching live agents.

Surfaces: Web UI, API

Steps:

1. Select `main.identity`.
2. Add a synthetic non-private line in Monaco.
3. Save draft.
4. Confirm History/What Changed shows the unified diff.
5. Apply the draft to markdown.
6. Restore the synthetic line through a second reviewed draft and apply it.
7. Separately verify a draft can be discarded without writing source.

Expected Result: `POST /api/drafts` creates a public-safe draft listing with no raw text/path leak;
`POST /api/drafts/:id/apply` writes only the reviewed source file when the idempotency token
matches; `DELETE /api/drafts/:id` marks drafts discarded; the final source file matches the
starting text.

Forbidden Result: Direct source write on save, raw private draft text returned by list APIs, or a
stale draft remaining actionable after discard.

Last Run: 2026-05-15, clean Playwright browser source edit/apply/revert flow.

## PW-008 Reviewed Push Guard

Requirement: No silent Mongo/live push; reviewed live push requires a prior dry-run token.

User Outcome: A user can run a dry-run, review the result, and only then unlock the reviewed push
button.

Surfaces: Web UI, API

Steps:

1. Open the Live Drift Board.
2. Verify reviewed push is disabled before a dry run.
3. Click `Push dry-run`.
4. Confirm the dry-run endpoint returns a review token.

Expected Result: Dry run uses the guarded prompts-only path and enables reviewed push only after
the token exists. The backend also rejects dry-run/reviewed push while source/eval drafts are
waiting, while any live-ahead/conflict drift remains, or when source hashes changed since the
stored dry-run. Do not click reviewed push during QA unless live sync is explicitly approved.

Forbidden Result: Reviewed push enabled before dry run, backend reviewed push bypassing live drift
or pending-draft guards, stale review tokens blessing changed source, or any non-dry-run push
during smoke QA.

Last Run: 2026-05-15, Playwright desktop dry-run guard check.

## PW-009 Flow Graph And Lineage

Requirement: Prompt Flow Dashboard should visualize real source/include/dependent relationships.

User Outcome: Selecting a prompt updates a visual path from source prompt to rendered preview, live
agent, eval bank, and eval results, with included/dependent prompts visible.

Surfaces: Web UI, API

Steps:

1. Select `main.identity`.
2. Inspect Prompt Flow Dashboard.
3. Inspect Prompt Detail.

Expected Result: Flow nodes include Source, Rendered Prompt, Live Agent, Eval Bank, Eval Results,
and real include/dependent nodes from the backend flow graph. Prompt Detail shows frontmatter,
variables, includes, dependents, and git history.

Forbidden Result: Static decorative graph unrelated to backend prompt lineage.

Last Run: 2026-05-15, Playwright desktop dark-mode user flow.

## PW-010 Eval Designer And Results

Requirement: Eval cases and results must be easy to inspect and tied to selected prompts.

User Outcome: A user can filter eval cases by family/surface, run a selected subset, and see recent
run history.

Surfaces: Web UI, API

Steps:

1. Switch to Evals mode.
2. Use the family/surface/max-case controls.
3. Click `Run selected`.
4. Inspect recent run history.

Expected Result: `POST /api/evals/run` records a public-safe preview when live mode is off; recent
runs show run id, mode, selected prompt id, case count, and status.

Forbidden Result: Inert eval controls, raw private prompt/eval output in public UI, or a run with no
prompt/case traceability.

Last Run: 2026-05-15, Playwright desktop dark-mode user flow.

## PW-011 Workbench Navigation And Settings Polish

Requirement: Prompt Workbench should stay visually navigable, avoid duplicate navigation, support
collapsible panels, and expose user-facing settings from the app logo.

User Outcome: A user can focus the workbench by collapsing sidebars, change theme preferences, hide
the status bar, and use the tab strip without a second duplicate button row.

Surfaces: Web UI

Steps:

1. Open the workbench in a real browser.
2. Verify the upper-left app mark uses the Viventium asset and opens Settings.
3. Toggle System/Light/Dark and the status bar setting.
4. Use the Prompt Flow sidebar icon and `Cmd/Ctrl+B`.
5. Open Prompt detail and collapse/expand the frontmatter sidebar.
6. Inspect the dock header for one primary row of tabs, not a duplicate Views button row.

Expected Result: Settings is accessible from the logo, theme/status preferences apply immediately,
sidebars collapse without breaking layout, and the dock relies on FlexLayout tabs as the primary
view navigation.

Forbidden Result: Placeholder logo, permanent useless "Ready" footer with no setting, duplicate tab
and button navigation rows, clipped editor controls, or keyboard shortcuts stealing focus from text
inputs.

Last Run: 2026-05-15, Playwright desktop UX enhancement pass.

## PW-012 Responsive User QA

Requirement: The dashboard should remain usable in desktop and mobile viewports with automatic
system light/dark support.

User Outcome: Users can inspect the core workbench without clipped controls, title overlap, or
document-level horizontal overflow.

Surfaces: Web UI

Steps:

1. Load desktop dark mode and run the main inspect/edit/eval/draft flow.
2. Load desktop light mode and inspect header, atlas, flow, editor, and inspector.
3. Load a mobile dark viewport.

Expected Result: No console errors, no failed API requests, no header title/subtitle overlap, no
document-level horizontal overflow, and flow canvas remains constrained to the viewport.

Forbidden Result: System-dark showing unreadable light-only controls, medium desktop header
overlap, or mobile panels escaping the viewport.

Last Run: 2026-05-16, headed Chrome production-bundle responsive QA after embedded-browser freeze fix.

## PW-019 Embedded Browser Responsiveness

Requirement: Prompt Workbench must remain interactive in embedded app browsers and should not load
heavy editor/runtime bundles before the user opens the relevant tab.

User Outcome: The local workbench opens without freezing, sidebar collapse buttons respond, and
the Prompt editor loads Monaco only when the user opens the Prompt tab.

Surfaces: Web UI, Built Bundle

Steps:

1. Build and start the production workbench bundle.
2. Load `http://127.0.0.1:8781/` in an embedded-width browser viewport.
3. Confirm the initial JS bundle is small enough that the page becomes interactive before opening
   Prompt.
4. Collapse and expand the Prompt Flow sidebar.
5. Collapse and expand the Sync sidebar.
6. Open Settings from the logo, toggle Dark/System, close Settings, and confirm header controls are
   still clickable.
7. Open Prompt, wait for Monaco to load, collapse and expand the prompt metadata sidebar.
8. Run a no-live eval preview and confirm the action message fits inside the header without
   covering the work area.

Expected Result: No page freeze, no console errors, no document-level horizontal overflow,
sidebars toggle within a normal click response, Monaco/PromptEditor assets load only when Prompt is
opened, and the header action message grows the header instead of overlapping the app.

Forbidden Result: A frozen embedded-browser tab, initial load pulling the Monaco editor bundle,
settings popover blocking unrelated header controls after close, or a fixed-height header clipping
action messages.

Last Run: 2026-05-16, headed Chrome production-bundle regression after embedded-browser freeze fix.

## PW-020 Draft Tab Stale Bundle Recovery

Requirement: Clicking Drafts must not freeze the workbench, even when the browser has stale local
bundle state or a lazy-loaded Drafts chunk fails to load.

User Outcome: Users either see the Draft Review view quickly or get a clear reload recovery panel;
the whole UI must not die silently.

Surfaces: Web UI, Static Asset Serving

Steps:

1. Build and start the production workbench bundle.
2. Load `http://127.0.0.1:8781/`, reload once, and confirm `/` returns `200 OK` with
   `Cache-Control: no-store`.
3. Confirm built `/assets/...` responses use immutable hashed-asset caching.
4. Seed a stale old dock layout key, reload, and click the Drafts tab.
5. Confirm the Draft Review view appears and the stale old layout key is cleared.
6. Simulate a missing `DraftPanel-*.js` chunk and click the Drafts tab again.
7. Confirm a recoverable "Drafts could not load" panel appears with a reload action.

Expected Result: Normal Drafts opens within a normal click response; stale layout state is ignored
or cleared; missing chunk errors show a recovery panel while the rest of the workbench remains
interactive.

Forbidden Result: A frozen tab, blank dock panel, uncaught chunk-load crash, stale HTML shell served
as `304 Not Modified`, or old local layout state blocking tab interaction.

Last Run: 2026-05-16, headed Chrome production-bundle QA with stale layout seed and simulated
DraftPanel chunk failure.

## PW-013 Dockable Workbench Layout

Requirement: Prompt Flow Dashboard should use VS Code-like tabs so users can focus one view at a
time, move views around, close them, and restore them.

User Outcome: A user can work in Flow, Prompt, Live Drift, Drafts, Evals, and Prompt Traces without the
default screen trying to show every panel at once.

Surfaces: Web UI

Steps:

1. Load the workbench with a fresh layout.
2. Confirm Flow, Prompt, Live Drift, Drafts, Evals, and Prompt Traces appear as dock tabs in one default
   tabset.
3. Use the dock tab strip to switch tabs.
4. Click Reset layout after changing tabs/layout state.

Expected Result: The default view opens as a single focused workbench tabset; secondary views are
one click away; reset restores the clean default layout.

Forbidden Result: A fixed two-column dashboard that permanently wastes the editor canvas, or a
closed view that cannot be reopened without reloading.

Last Run: 2026-05-15, Playwright desktop light/dark UX pass.

## PW-014 Human-Readable Prompt Atlas

Requirement: Prompt Atlas should represent actual prompt flow in order and avoid machine-level
hash/id noise in the main navigation.

User Outcome: The left tree shows what the main agent sees first, then included prompt layers, then
supporting prompt families that are not in the main path.

Surfaces: Web UI, API

Steps:

1. Load the workbench.
2. Inspect the Prompt Flow tree.
3. Search and select a main-path prompt.

Expected Result: `Main agent instruction` is the root; included prompts appear in source order;
supporting prompts are grouped under `Not in main path`; row labels are human-readable and show
status dots instead of content hashes.

Forbidden Result: Alphabetical prompt dump, repeated hash strings, or a tree that contradicts the
backend include graph.

Last Run: 2026-05-15, Playwright desktop light/dark UX pass.

## PW-015 Helper And CLI Lifecycle

Requirement: Prompt Workbench must be easy to open from Viventium Helper while remaining separate
from the main Viventium runtime.

User Outcome: A user can open, start, or stop Prompt Workbench from
`Advanced > Prompt Workbench` without accidentally stopping Viventium.

Surfaces: CLI, macOS helper, Web UI

Steps:

1. Run `bin/viventium prompt-workbench start --json`.
2. Verify `/api/health` returns `ok` on the reported loopback URL.
3. Run `bin/viventium prompt-workbench stop --json`.
4. Verify only the recorded workbench process is stopped.
5. Reinstall/inspect the macOS helper and confirm `Advanced > Prompt Workbench` exposes `Open`,
   `Start`, and `Stop`.

Expected Result: The CLI records only prompt-workbench PID/port/url metadata under App Support
state; helper actions call the prompt-workbench CLI; stopping the workbench leaves the main
Viventium stack untouched.

Forbidden Result: Helper `Prompt Workbench > Stop` invoking `bin/viventium stop`, killing arbitrary
loopback processes, or writing generated runtime config files.

Last Run: 2026-05-15, local CLI/helper integration QA.

## PW-016 Prompt History And Eval Traceability

Requirement: A user and AI agent must be able to see what changed for a prompt, prior history,
linked evals, relevant QA, recent eval results, and prompt context through a stable read API.

User Outcome: Opening a prompt's History view gives an immediate review surface rather than
scattered machine-level state.

Surfaces: Web UI, API

Steps:

1. Select `main.identity`.
2. Open Prompt `History`.
3. Inspect `What Changed`, `Git History`, `Linked Evals and QA`, recent eval runs, and patch preview.
4. Call `GET /api/prompts/main.identity/workbench-context`.
5. Check that the response includes prompt-linked evals, QA coverage, recent eval runs, and git
   history without local home-directory paths.

Expected Result: The first viewport shows change history, git history, linked eval families/cases,
QA chips, and recent eval runs for the selected prompt; the API returns the same machine-readable
context without raw private draft bodies or absolute local paths.

Forbidden Result: Users must hunt across unrelated tabs to understand a prompt, eval links are not
prompt-specific, or public API responses expose private paths/raw draft text.

Last Run: 2026-05-15, Playwright focused History view plus API privacy check.

## PW-017 Eval Case Draft Editing

Requirement: Eval edits must be reviewable source drafts tied to the eval bank, not direct writes
or noisy whole-file formatting churn.

User Outcome: A user can edit an eval case, review a small focused patch, and discard or apply it
with the same reviewed-draft discipline as prompt markdown.

Surfaces: Web UI, API

Steps:

1. Select a prompt with linked evals.
2. Open `Evals`.
3. Edit the selected eval case prompt/rubric.
4. Save eval draft.
5. Inspect the draft patch summary.
6. Discard the draft.

Expected Result: `POST /api/evals/case-draft` creates an `eval-edit` draft against the eval bank
only when the case changed; the public draft summary is focused on the edited case and does not
expose raw private output or local paths; semantic no-op/format-only edits are refused; eval
preview clearly blocks or routes the user to resolve the pending eval draft; discarding the draft
leaves the eval bank unchanged.

Forbidden Result: Direct eval-bank write on Save, broad formatting-only diffs that obscure the
real change, or private eval run artifact paths in public responses.

Last Run: 2026-05-16, backend regression plus real Chrome eval-editor QA.

## PW-018 Pending Draft Blocks Eval And Push

Requirement: Evals and live sync actions must be truthful about whether they use saved source,
pending drafts, or live state.

User Outcome: After saving a prompt draft, the user cannot accidentally run evals or dry-run a push
against older applied source while believing the draft was included.

Surfaces: Web UI, API

Steps:

1. Select a prompt with no unsaved editor buffer.
2. Save a source-edit draft and leave it unapplied.
3. Verify the prompt header says `draft waiting`, not `source clean`.
4. Click the top `Run eval preview` action.
5. Click the top `Push dry-run` action.
6. Call `POST /api/evals/run` and `POST /api/sync/push-live-dry-run` directly with synthetic
   non-private data or a temp draft root.

Expected Result: The UI explains that eval and push use applied markdown only; top blocked actions
route to the exact review surface instead of behaving like inert buttons; eval preview and push
dry-run are blocked until the draft is applied or discarded; stale already-applied drafts can be
resolved without rewriting source; direct API calls return a structured 409 with draft
ids/kinds/target paths only, no raw draft bodies or absolute local paths.

Forbidden Result: `source clean` while a draft is waiting, dry-run token creation with unresolved
drafts, eval run records that appear to validate the pending draft, or 409 responses leaking raw
prompt text.

Last Run: 2026-05-16, pending-draft hardening plus stale-draft resolution pass.

## PW-021 Draft Review Guidance

Requirement: Users must be able to see what changed, review the exact patch, and understand the
next safe action without hunting through unrelated tabs.

User Outcome: A saved draft creates an obvious review path from the Prompt view and from linked
eval/history surfaces.

Surfaces: Web UI

Steps:

1. Select a prompt with a pending draft.
2. Inspect the Prompt header, review strip, and callout.
3. Click `Review draft`.
4. Inspect History `What Changed`, patch preview, linked evals/QA, and eval run actions.

Expected Result: The Prompt view shows `draft waiting`, a short explanation that eval/push use
applied markdown only, and a `Review/apply draft` button that opens History with the pending patch
selected. Top-level eval/push actions say `Review draft` or `Open drafts` when blocked and route to
the blocking review surface. Linked eval run buttons show `Review draft first` until the draft is
resolved.

Forbidden Result: Users must infer from hash counts or sidebar metrics what to do next, or eval
buttons remain visually primary/actionable for a draft that is not applied.

Last Run: 2026-05-16, pending-draft hardening plus Chrome UX follow-up.

## PW-022 Eval Create And Performance Clarity

Requirement: Users must be able to define, create, edit, run, and understand evals without
confusing no-live selection previews for scored performance runs.

User Outcome: A user can see all evals linked to the selected prompt, create a new case as a
reviewed draft, and understand whether a run produced real model performance.

Surfaces: Web UI, API

Steps:

1. Select `main.voice_style`.
2. Open `Evals`.
3. Confirm the default table shows all linked cases, not only the first web case.
4. Click `New eval case`, enter a synthetic non-private case id, prompt, surface, and rubric.
5. Save the new eval draft and inspect the draft patch.
6. Discard the synthetic eval draft.
7. Run a no-live preview only after all drafts are resolved.

Expected Result: The default Eval view shows linked cases across families/surfaces; `New eval case`
creates a focused `eval-edit` draft without writing the eval bank immediately; preview copy says
`no model call, no score`; live exact-model mode is the path that records scored performance and is
run only when explicit live-model/local-account approval is in scope.

Forbidden Result: Hidden linked cases because a default filter is active, whole-file eval-bank
format churn, a create action that writes directly to public eval source, or preview runs presented
as model-quality performance.

Last Run: 2026-05-16, backend regression plus real Chrome eval create/discard, no-live preview, and
results visibility QA. Live exact-model performance was not run in this local-only pass.

## PW-023 Prompt Traces Meaning

Requirement: Prompt-frame telemetry must be understandable to humans and safe for public UI.

User Outcome: Users understand that the former Frames view is a prompt-run metadata trace, not an
eval, prompt file, or hidden message transcript.

Surfaces: Web UI, API

Steps:

1. Open the `Prompt Traces` tab.
2. Inspect the heading, empty state, and metrics.
3. Confirm the UI explains that traces contain local metadata such as surface, model, layers, token
   estimates, and routing decisions.

Expected Result: The tab and panel are named `Prompt Traces`; empty state copy explains the concept
plainly; raw private prompt text is not shown in the public-safe UI.

Forbidden Result: A tab called `Frames` with no explanation, raw prompt or transcript text in the
trace list, or metrics that look like eval performance.

Last Run: 2026-05-16, real Chrome UX follow-up documented in
`qa/prompt-workbench/reports/2026-05-16-usability-eval-flow-qa.md`.

## PW-024 Sidebar Collapse Storage Resilience

Requirement: Top nav sidebar collapse controls and the prompt metadata collapse control must remain
interactive even when embedded browsers cannot persist local workbench preferences.

User Outcome: Clicking Hide/Show Prompt Flow, Hide/Show Sync, and Hide/Show prompt metadata never
freezes or blanks the app. Preference persistence is optional; interaction is mandatory.

Surfaces: Web UI, Built Bundle

Steps:

1. Build and start the production workbench bundle.
2. Load the workbench in a real browser.
3. Patch browser storage in the QA browser so Viventium preference reads/writes/removes throw.
4. Click Hide Prompt Flow, Hide Sync, Show Prompt Flow, and Show Sync.
5. Press Cmd+B twice to collapse and restore the Prompt Flow sidebar.
6. Click the Drafts tab and return to the Prompt tab.
7. Open the Prompt tab and click Hide prompt metadata and Show prompt metadata.
8. Confirm the app shell remains visible and no page errors are emitted.

Expected Result: All collapse buttons respond; the workbench remains mounted; prompt editing still
opens; the app silently degrades to non-persistent preferences when local storage is unavailable.

Forbidden Result: Blank page, unmounted app shell, page error from storage access, a stuck collapse
state, or inaccessible metadata collapse controls.

Last Run: 2026-05-17, headed Chromium production-bundle QA with storage get/set/remove failures
simulated before and after load, including Drafts tab navigation and Cmd+B sidebar toggle.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Prompt Workbench. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `PW-UC-001` | Open the production Prompt Workbench, search the prompt atlas, select a prompt, and inspect Flow, Prompt, Live Drift, Drafts, Evals, and Prompt Traces. | `49_Prompt_Architecture_and_Token_Efficiency.md` / `PW-001`, `PW-002`, `PW-009`, `PW-014` | Real browser against the built local workbench plus `/api/prompts`, `/api/sync/status`, `/api/drafts`, `/api/evals/runs`, and prompt detail APIs | Source prompt files, workbench API responses, browser console/network, built bundle, release tests, and public-safe QA reports | The atlas is human-readable, prompt detail matches registry output, drift is explicit, no raw private state is exposed, and every network request succeeds or reports a clear blocked state. | 2026-05-18 publish browser QA - passed |
| `PW-UC-002` | Use no-live eval controls and blocked sync controls before any reviewed live push. | `49_Prompt_Architecture_and_Token_Efficiency.md` / `PW-005`, `PW-008`, `PW-010`, `PW-018`, `PW-022` | Real browser Evals and Live Drift panels plus `/api/evals/run` and sync status APIs | Eval bank, private run summary counts/hashes only, pending-draft state, sync state, browser console/network | Preview clearly says no model call/no score, records a sanitized local run summary, and reviewed push stays blocked until the guarded dry-run/review path is satisfied. | 2026-05-18 publish browser QA - passed for no-live preview and blocked state; live push intentionally not run |
| `PW-UC-003` | Refresh/reopen the workbench after an eval preview and confirm the selected prompt, run summary, and API-backed state still agree. | `49_Prompt_Architecture_and_Token_Efficiency.md` / `PW-010`, `PW-012`, `PW-015`, `PW-016` | Real browser reload/reopen plus backend health/build-version APIs | `/api/health`, `/api/build-version`, `/api/evals/runs`, browser requests, static index/cache headers, built artifact hash | The workbench reloads without console errors, the selected prompt can be found again, run history persists through private workbench state, and public API/build metadata omits local absolute paths. | 2026-05-18 publish browser QA - passed |

## Release Test Traceability

- `tests/release/test_prompt_workbench.py`
