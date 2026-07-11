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
labels; hashes stay in private/source metadata and tests, not in the Atlas or flow overview. The
Prompt `Rendered` view defaults to a readable semantic `Read` mode while preserving a `Raw` mode
with the exact assembled registry output used for hashes, diffs, sync, and evals.

Forbidden Result: A second prompt parser, prompt database, divergent render output, or a readable
view that changes, executes, strips, or hides runtime placeholders and literal prompt markers.

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

Last Run: 2026-05-21, local-only guarded sync check. `Push dry-run` returned a review token and
the reviewed push endpoint refused to mutate because live/source drift was still classified as
conflict.

## PW-009 Flow Source Map And Lineage

Requirement: Prompt Flow Dashboard should provide a real Workbench source-map projection over
prompt registry, include/dependent lineage, target metadata, eval `promptRefs`, and local runtime
artifacts.

User Outcome: Selecting a prompt shows where that prompt sits in the larger Viventium prompt,
feature, runtime, and eval map. The selected path is highlighted, unrelated flows remain visible
but muted, and double-clicking a prompt node opens the Prompt tab for that prompt.

Surfaces: Web UI, API

Steps:

1. Select `main.identity`.
2. Inspect Prompt Flow Dashboard and confirm the stage bands, selected prompt, lineage, linked
   evals, and local artifacts are visible.
3. Search/select `memory.hardener_consolidation`.
4. Confirm the highlighted path moves to memory/recall context and unrelated prompts/evals are
   muted rather than removed.
5. Double-click the selected prompt node.
6. Inspect Prompt Detail.

Expected Result: Flow nodes are data-bound to real prompt rows, backend include/dependent edges,
eval-bank prompt references, and documented Workbench artifact nodes. Stage bands are documented UI
categories, not runtime-routing authorities. Prompt Detail opens for the double-clicked prompt and
shows frontmatter, variables, includes, dependents, and git history.

Forbidden Result: Static decorative graph unrelated to backend prompt lineage, a map that implies
undocumented runtime routing authority, or a double-click that only changes the graph while leaving
the user stranded away from the prompt.

Last Run: 2026-05-22, Playwright source-map and double-click navigation pass.

## PW-029 Scheduled GlassHive Prompts

Requirement: Prompt Workbench scheduled prompts must be editable, previewable, triggerable, and
durably executed by Scheduling Cortex through GlassHive without hardcoding a user, prompt, or
database credential.

User Outcome: An admin can create or edit a private scheduled prompt, preview live-linked
variables, enable/disable it, change its time, run it manually, and inspect run history/results
from Workbench while the recurrence engine remains Scheduling Cortex.

Surfaces: Web UI, API, Scheduling Cortex SQLite, GlassHive runtime

Steps:

1. Verify unauthenticated scheduled-prompt and variable endpoints return `401`.
2. Open Workbench with a helper launch token, authenticated admin session, or direct same-machine
   loopback visit that resolves the single local admin account.
3. Inspect the Prompt Flow atlas and confirm Scheduled Prompts appear near the top as prompt
   objects with an inline on/off switch. Confirm both Workbench-private scheduled prompts and
   existing user-level Scheduling Cortex tasks for the admin user appear in the same group.
4. Select a scheduled prompt object from the Prompt Flow atlas and confirm the Schedules detail tab
   opens for that object.
5. Open the Drafts tab for that same scheduled prompt object and confirm it shows the private
   scheduled prompt body, a rendered-variable view, and variable snapshot details without treating
   the private prompt as a public source-file draft.
6. Inspect the Schedules execution panel and confirm Workbench-private schedules show the configured
   GlassHive route, selected host worker profile (`codex-cli` or `claude-code`), execution mode,
   workspace root, and private `my_folder`; host runtime dependency failures must preserve the
   failure class and safely recover to sandbox/workstation mode when no host workspace root is
   required.
7. Resize the Prompt Flow pane and confirm the header, object count, and add button stay visible
   while the tree scrolls.
8. Inspect variable chips for user, memories, memory agent prompt, governed database context,
   GlassHive `my_folder`, and the background-agent list function.
9. Create a synthetic scheduled prompt with a daily `03:00` schedule and memory write mode `off`
   or `propose`.
10. Preview rendered variables and confirm wrappers such as `<memory_agent.system_prompt>` and
   `<user.memories>` are visible; if the resolved admin has memory rows, `user.memories` must not
   render as an empty array.
11. Toggle enabled/disabled from the Prompt Flow atlas switch, change the time, save, refresh, and
   confirm persistence.
12. Trigger a manual run and confirm a `glasshive_host` / `workbench` run row is recorded. Rapidly
   repeat the manual-run request and confirm the second request coalesces onto the existing
   in-flight run instead of creating a duplicate worker run.
13. Open a preexisting user-level schedule row and confirm the detail pane identifies it as a
    user-level schedule with `viventium_agent` executor/channel metadata rather than converting it
    into a Workbench-private GlassHive definition.
    In Drafts and Schedules, confirm user-level rows show stored prompt text and regular scheduler
    route only; Workbench variable chips/rendered snapshots and memory write-mode controls must be
    hidden or marked not applicable.
    Save a title-only or active-state-only edit on a user-level schedule and confirm custom
    `schedule` JSON is preserved unless the schedule controls were explicitly changed.
14. Inspect the topbar sync actions and confirm Pull Live and Push Dry-run are green when current
   and orange when live/source work, conflicts, or blocking drafts need attention.
15. Change a synthetic Workbench-private schedule between `GlassHive host` and `Viventium agent`.
   Confirm GlassHive schedules expose `same worker` / `new worker each run`, while Viventium
   schedules expose `new conversation` / `same conversation`.
16. Create a synthetic structured `memory-proposals-*.json` file under a private `my_folder` and
   confirm the proposal review panel lists actions, hashes, dry-run, and `Apply governed` controls.
   Apply only against synthetic QA data; for real user data, run dry-run and verify duplicate-key
   merge handling without applying.
17. Inspect private result pointer existence and public-safe DB/log evidence without copying raw
   rendered prompt text into public QA.

Expected Result: The scheduled task uses `executor="glasshive_host"` and `channel="workbench"`;
GlassHive dispatch branches before LibreChat generation; run history records status, hashes,
GlassHive ids when available, private detail pointer, and signed callback updates; variable
rendering never exposes raw Mongo credentials; memory writeback is governed or proposal-only.
Existing user-level `scheduled_tasks` rows remain owned by Scheduling Cortex, appear in the same
Prompt Flow/Schedules UI, and can be toggled/edited/run/deleted without duplicate Workbench
definition rows. The built-in Workbench schedule appears as `Subconscious Deep Thought`; docs and
template metadata preserve `Nightly subconscious thought formation` as the nightly template alias.
On fresh installs and upgrades, the built-in schedule is active by default, resolves the first local
admin user without a hardcoded personal account, and uses the compiled GlassHive worker profile
selected from the signed-in Codex or Claude CLI.
`apply_governed` routes through the LibreChat/Viventium memory policy helper and memory methods,
duplicate live memory keys touched by the proposal are deduped or policy-blocked before apply,
unrelated duplicate memory categories are not rewritten, manual runs are idempotent, and persisted
run history/callback rows contain sanitized summaries/error classes while raw payloads live only in
private detail files. If the host worker substrate is unavailable before assignment and the task has
no host-specific workspace root, Scheduler retries the same Workbench task through
sandbox/workstation execution before recording a terminal failure.

Forbidden Result: Workbench asking the main Viventium agent to use GlassHive, direct host-worker
Mongo credentials, direct `memoryentries` writes or prompt text that instructs direct DB edits,
unauthenticated private prompt access, hardcoded real user identity in public artifacts, or raw
rendered prompt/result text in public QA reports.

Last Run: PASS 2026-07-10
([callback repair](../scheduling-cortex/reports/2026-07-10-workbench-callback-repair.md)).
Fresh built-in manual proof completed through Workbench API -> Scheduling Cortex -> GlassHive ->
signed callbacks -> scheduler ledger; queued, started, and completed callbacks all delivered on
first attempt and no private prompt/result text was copied into public evidence.

## PW-010 Eval Designer And Results

Requirement: Eval cases and results must be easy to inspect and tied to selected prompts.

User Outcome: A user can filter eval cases by family/surface, run a selected subset, and see recent
run history.

Surfaces: Web UI, API

Steps:

1. Switch to Evals mode.
2. Use the family/surface/max-case controls.
3. Click several visible eval table rows across linked families.
4. Confirm the selected-row highlight and editor title/body change to the clicked case.
5. Click `Run selected`.
6. Inspect recent run history.

Expected Result: `POST /api/evals/run` records a public-safe preview when live mode is off; recent
runs show run id, mode, selected prompt id, case count, and status. Row selection responds within a
normal click cycle and keeps the editor tied to the selected row's family and case id.

Forbidden Result: Inert eval controls, raw private prompt/eval output in public UI, or a run with no
prompt/case traceability. Clicking a non-selected eval row must not hang the browser main thread,
trigger a Page Unresponsive dialog, or relabel a case under the wrong family.

Last Run: 2026-05-21, Playwright production-bundle eval row-selection regression script.

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
3. Load a medium desktop viewport and verify Evals table rows remain clickable.
4. Load a mobile dark viewport.

Expected Result: No console errors, no failed API requests, no header title/subtitle overlap, no
document-level horizontal overflow, and flow canvas remains constrained to the viewport. When an
inner workbench panel needs more width than the available dock space, that panel scrolls internally
instead of allowing neighboring eval panes to overlap.

Forbidden Result: System-dark showing unreadable light-only controls, medium desktop header
overlap, eval editor/results panes intercepting table row clicks, or mobile panels escaping the
viewport.

Last Run: 2026-05-21, Playwright production-bundle eval layout regression at 1024, medium, and wide desktop viewports.

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

## PW-030 Prompt Diff Wrapping And Working-Tree Source Visibility

Requirement: Prompt Workbench diff inspection in
`docs/requirements_and_learnings/49_Prompt_Architecture_and_Token_Efficiency.md`.

User Outcome: A user can see prompt source changes made by another local agent and read long
side-by-side diff lines without one pane overflowing while the other wraps.

Surfaces: Web UI, API

Steps:

1. Make or preserve a synthetic uncommitted source change to a tracked prompt file, and cover a
   synthetic untracked prompt file through regression coverage.
2. Open that prompt in Prompt Workbench.
3. Open Prompt `Diff` with no editor-buffer change.
4. Inspect that the original pane is the committed `HEAD` text and the modified pane is the current
   source file.
5. Confirm both original and modified Monaco diff panes wrap long lines.
6. Open Prompt `History`, click the `working-tree` Git History entry, and inspect the patch preview.
7. Refresh the page and re-open the same prompt to confirm the working-tree entry and wrapped diff
   state persist while the source file remains uncommitted.

Expected Result: Prompt `Diff` shows uncommitted source changes when the editor buffer is clean,
falls back to editor-buffer diff when the user edits the prompt, wraps both diff panes consistently,
and History includes a first public-safe `working-tree` entry with patch stats and no local absolute
paths. For untracked prompt files, the diff treats the committed baseline as an intentional empty
string rather than hiding the source delta.

Forbidden Result: One diff pane horizontally overflows while the other wraps, uncommitted prompt
changes disappear from the diff/history surfaces, or viewing the diff creates drafts, pushes live,
or mutates cloud/runtime state.

Last Run: 2026-05-22, local build, release regression, Claude review, and in-app browser QA.

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

Last Run: 2026-05-21, live exact-model local runtime pass. The harness ran 3 selected web cases and
failed closed: 2 completed, 1 empty visible response, and 1 duplicate non-silent response hash group.

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

## PW-025 Operational Memory Prompt Coverage

Requirement: Transcript-ingest and nightly saved-memory hardening prompts must be visible and
evaluable in Prompt Workbench with the same source/draft/history/eval discipline as other prompts.

User Outcome: A user can search `transcript` or `hardener`, select the operational memory prompts,
inspect their rendered templates, see linked evals/QA, and run a no-live eval preview without
touching cloud or live agent state.

Surfaces: Web UI, API, Built Bundle

Steps:

1. Build and start the production Prompt Workbench bundle.
2. Search `transcript` in the atlas and select `memory.transcript_summarizer`.
3. Inspect Prompt detail and History.
4. Open Evals and confirm `meeting_transcript_ingest` cases are linked.
5. Search/select `memory.hardener_consolidation`.
6. Confirm `memory_hardening_consolidation` cases are linked.
7. Run a no-live preview for one linked operational-memory case.
8. Refresh and confirm the prompts and eval run remain visible without console errors or private
   transcript content.

Expected Result: Operational memory prompts appear under the memory prompt family with readable
targets; strict runtime variables render as placeholder markers for inspection; linked evals and QA
chips appear in History/Evals; preview records sanitized selection evidence only. Runtime prompt
bundle drift is visible as a public-safe status badge instead of pretending a source-only prompt is
already compiled into the installed bundle.

Forbidden Result: Transcript/hardener prompts hidden in hardcoded scripts only, selecting the prompt
throws a strict-variable render error, evals are absent from Workbench, preview writes live/cloud
state, or public QA/UI exposes raw transcript text, local paths, account identifiers, or secrets.

Last Run: 2026-05-21, Playwright CLI plus API/log QA passed for transcript summarizer and nightly
hardener prompt coverage; local runtime bundle drift correctly showed the three new prompts as
source-only and needing rebuild.

## PW-026 Rendered Read/Raw Prompt View

Requirement: The Prompt tab should show a readable rendered prompt without losing exact raw
registry output or corrupting runtime prompt markers.

User Outcome: A user can read assembled prompts as a formatted document, then switch to the exact
raw rendered text when they need copy/paste, hash, diff, sync, or eval parity.

Surfaces: Web UI, Built Bundle

Steps:

1. Build and start the production Prompt Workbench bundle.
2. Select `main.conscious_agent`.
3. Open Prompt `Rendered` and confirm `Read` mode shows headings/lists/paragraphs as readable
   document structure instead of raw markdown punctuation.
4. Switch to `Raw` and confirm the exact assembled text remains visible.
5. Search/select `memory.transcript_summarizer`.
6. Confirm `Read` mode preserves strict variables, literal XML-like transcript tags, and envelope
   separator lines as visible text.
7. Switch to `Raw` and confirm those same markers are present in the exact raw output.

Expected Result: `Read` mode is readable and safe; `Raw` mode remains exact. Runtime placeholders,
strict variables, literal prompt tags, and separator lines are neither executed as HTML nor removed
from the operator view.

Forbidden Result: Only raw markdown punctuation, HTML injection from prompt text, stripped
variables/tags, or no exact raw rendered view after the readable view is introduced.

Last Run: 2026-05-22, Playwright rendered Read/Raw prompt QA.

## PW-027 Scheduling Cortex Prompt And Config Coverage

Requirement: Scheduling Cortex prompt files, source config, evals, QA coverage, and history must be
visible together in Prompt Workbench without exposing private schedule runtime state.

User Outcome: A user can search `scheduling`, select the main scheduling continuity prompt or the
Scheduling Cortex MCP prompt, and see the prompt, linked evals, related source YAML config, and
history in one organized place.

Surfaces: Web UI, API, Built Bundle

Steps:

1. Build and start the production Prompt Workbench bundle.
2. Search `scheduling` in the atlas.
3. Select `main.scheduling_self_continuity` and open Prompt `History`.
4. Confirm linked scheduling evals and QA chips are visible.
5. Confirm Related Config shows scheduling direct-action ownership, main-agent scheduling tools,
   and `mcpServers.scheduling-cortex`.
6. Select `mcp.scheduling_cortex.server` and repeat the History inspection.
7. Confirm related config history uses public-safe commit summaries and does not show App Support
   state, raw schedule rows, private schedule prompts, or local absolute paths.

Expected Result: Scheduling prompt history is not a lonely prompt file. The Workbench ties it to
the source YAML config that exposes the MCP, the direct-action owner contract, linked evals, QA,
and git history.

Forbidden Result: Scheduling config discoverable only by manually opening source YAML, linked evals
missing from scheduling prompts, raw runtime schedule state in public UI, or source config history
leaking local absolute paths.

Last Run: 2026-05-22, API and Playwright scheduling config coverage QA.

## PW-028 LibreChat Account Menu Workbench Entry

Requirement: Local LibreChat admin/operator users must be able to open Prompt Workbench from the
Viventium account dropdown under the Connected Accounts menu item without hardcoded browser ports or
cloud-side changes.

User Outcome: A user opens the account dropdown, sees Prompt Workbench directly below Connected
Accounts, selects it, and lands in the managed local Prompt Workbench instance.

Surfaces: LibreChat Web UI, Viventium API, Prompt Workbench lifecycle CLI

Steps:

1. Start the local LibreChat frontend/API and the Prompt Workbench lifecycle surface.
2. Open LibreChat on the same host in a real browser and authenticate as an admin/operator.
3. Open the user/account dropdown and find `Prompt Workbench` directly below `Connected Accounts`.
4. Select `Prompt Workbench`.
5. Confirm a new tab opens to the URL returned by the local API and the Prompt Workbench renders.
6. Confirm the local API reused or started the managed workbench through the supported CLI path.
7. Confirm no cloud URL, external OAuth flow, or remote mutation was involved.
8. Confirm a non-admin authenticated user cannot call the local launcher route.

Expected Result: The account dropdown has a clear Prompt Workbench entry under Connected Accounts.
The menu item calls the local Viventium API, which uses `bin/viventium prompt-workbench start --json`
and returns a loopback URL that opens the Workbench. Non-admin users do not receive the Workbench
launcher.

Forbidden Result: A hardcoded stale workbench port in the browser bundle, no admin entry in
the account dropdown, non-admin access to the launcher, opening a cloud URL, changing
connected-account provider state, or starting/stopping the main Viventium runtime.

Last Run: 2026-05-22, LibreChat account-menu Workbench entry QA.

## PW-031 Diff Baseline And Sidecar Persistence

Requirement: Prompt Workbench must keep user layout choices stable, make prompt diffs explicit, and
optionally stay running with the local Viventium runtime when enabled.

User Outcome: A user closes the right sync sidebar once and it stays closed after reloads. In the
Prompt Diff tab, the user can choose the exact baseline: applied source, Git HEAD before local
working-tree edits, or a prompt-specific git history entry. If `runtime.prompt_workbench.enabled`
is true, the local stack starts and watches Workbench without leaking the launch token into logs.

Surfaces: Web UI, API, Config compiler, Stack launcher, Built bundle

Steps:

1. Build and start the production Prompt Workbench bundle.
2. Close the right sync sidebar, reload the browser, and confirm the sidebar remains closed.
3. Select a prompt with git history and open Prompt `Diff`.
4. Use `Compare from` to switch between the applied source and at least one git history revision.
5. Confirm the backend revision endpoint returns the selected prompt file text at that revision.
6. Compile config with `runtime.prompt_workbench.enabled: true` and confirm
   `START_PROMPT_WORKBENCH=true`.
7. Run the launcher in a local smoke mode with the prompt sidecar enabled and confirm Workbench is
   running, the watchdog pid file exists, and logs do not contain the authenticated Workbench URL.
8. Stop Workbench through the CLI/helper path while the watchdog is alive and confirm the local
   user-stopped marker prevents immediate restart until Workbench is explicitly started again.

Expected Result: Sidebar state survives reload through the safe storage wrapper. The diff header
names the selected baseline and target; selecting history works for any prompt registry file with
git history. The sidecar is opt-in, local only, uses the existing `bin/viventium prompt-workbench`
path, keeps the auth token out of logs, and respects explicit user stop.

Forbidden Result: Right sidebar reopens after a reload, implicit/vague diff baseline, prompt-id or
prompt-text special casing, a cloud mutation, a leaked `workbench_token` in stack logs, or stopping
the main runtime when only Workbench is stopped. Workbench must also not immediately restart after a
user-visible Stop action while the stack watchdog is alive.

Last Run: 2026-05-22, sidebar persistence, diff history baseline, and sidecar watchdog QA.

## PW-032 One-Time Scheduled Prompt State Parity

Requirement: Prompt Workbench schedule details must faithfully represent the schedule type and
active/next-run state stored in Scheduling Cortex.

User Outcome: A user can inspect a fired one-time scheduled prompt without seeing a misleading
enabled recurring schedule or accidentally saving it as a daily prompt.

Surfaces: Web UI, API, Scheduling Cortex SQLite

Steps:

1. Create a synthetic Workbench scheduled prompt with a one-time due schedule through the same API
   used by local tooling.
2. Let Scheduling Cortex fire it.
3. Open the scheduled prompt in Workbench and inspect the Prompt Flow row plus Schedules detail
   editor.
4. Compare visible active/schedule fields with the backing definition, task, and run rows.

Expected Result: A fired one-time schedule is visibly inactive or completed when its backing task
has `active=0` and `next_run_at=null`; the editor preserves or clearly labels one-time schedule
state instead of defaulting to daily `03:00`.

Forbidden Result: Workbench shows `enabled · not scheduled`, checks `Enabled`, or displays a daily
schedule for a fired one-time task unless the user explicitly changes the schedule type.

Last Run: 2026-05-25, FAIL. Synthetic one-time due QA completed, but the Workbench row/editor
showed the definition as enabled with no next run and the editor fell back to a daily schedule. See
`qa/scheduling-cortex/reports/2026-05-25-sched002-pw029-live-delivery-qa.md`.

## PW-033 Express Nightly Reflection Readiness

Requirement: Express/Advanced/upgrade installs must seed and surface the built-in nightly
reflection through the same production chain: scheduled prompt -> filled placeholders -> GlassHive
run -> callback -> scheduler ledger -> Workbench shows completed.

User Outcome: A new user gets the nightly reflection workflow without knowing internal scheduler
or GlassHive wiring, and status tells them whether it is ready, pending setup, degraded, or complete.

Surfaces: Prompt Workbench UI, Scheduling Cortex, GlassHive callback, install/status summary,
generated runtime config.

Steps:

1. Compile an Express-shaped config and verify Workbench, seed-nightly, Scheduler, and GlassHive env
   are enabled without developer account values.
2. Open Workbench and confirm the built-in nightly prompt is visible and active for the resolved
   first local admin user.
3. Trigger or wait for a synthetic safe due run and verify placeholder population, GlassHive run
   creation, callback completion, scheduler ledger status, and visible Workbench completion.
4. Restart/reload and confirm the completed state persists.
5. Verify degraded cases: missing worker CLI auth, callback failure, scheduler endpoint down, and
   no first-admin owner yet.

Expected Result: The Workbench row and scheduler ledger agree; setup/degraded states are explicit;
no raw prompt/result/private user identifier is written to public QA.

Forbidden Result: A seeded schedule without GlassHive delivery, a callback success not reflected in
Workbench, an owner-specific hardcoded account, or public evidence containing raw reflection text.

Last Run: PASS 2026-07-10
([callback repair](../scheduling-cortex/reports/2026-07-10-workbench-callback-repair.md)).
Owner-runtime proof covered the full chain with the built-in `Subconscious Deep Thought` schedule:
manual trigger, filled snapshot, GlassHive run, all signed callbacks delivered, scheduler ledger
completed, and Workbench API reported healthy schedule status. Clean-machine installer proof remains
under installer release QA, not a known owner-runtime nightly blocker.

## PW-034 Exact Runtime Background Activation Evals

Requirement: Prompt Workbench must evaluate background activation with the real runtime classifier,
canonical prompt registry, and honest semantic/reliability metrics.

User Outcome: An operator can select the background activation family, preview its coverage without
model calls, run an approved live subset or full corpus, and distinguish prompt misses from provider
timeouts or transport failures.

Surfaces: Web UI, API, exact-runtime CLI runner, private Workbench evidence

Steps:

1. Open Evals and select `background_activation_routing`.
2. Preview a subset and confirm the planned call count covers selected cases × selected cortices.
3. Run an approved live subset, inspect aggregate metrics, and filter a single cortex/case for
   surgical regression work.
4. Inspect recent run history, reload, and compare the private aggregate result with the source
   prompt-bank and bundle hashes.

Expected Result: The backend dispatches to `run-activation-model-evals.cjs`, which resolves registry
prompt references and calls `BackgroundCortexService.checkCortexActivation`; results report recall,
precision, sibling leaks, unavailable calls, consistency, and latency. Preview performs no model
calls. Raw prompts/responses remain private.

Forbidden Result: Reimplemented classifier semantics, inline duplicate activation prompts, a timeout
counted as a correct negative, a public raw-response artifact, or live sync as a side effect of eval.

Last Run: 2026-07-09, exact-runtime CLI and backend-dispatch implementation; browser acceptance is
recorded in the activation-routing report.

## PW-035 Long Live Evals Restore And Record State

Requirement: Long exact-model matrices must complete or fail with durable evidence while leaving
the QA account as they found it.

User Outcome: An operator can run a multi-case Feelings matrix from Evals, keep using the UI while it
runs, see an honest completion/timeout code, and trust that temporary state and conversations are
cleaned.

Surfaces: Real Workbench Evals UI, backend subprocess boundary, exact-model runner, QA API/DB

Steps:

1. Select `feelings_embodiment_and_reaction`, set 19 cases, enable live exact-model, and run.
2. Verify the subprocess timeout scales with the selected case count and the UI remains responsive.
3. Inspect the saved run record and public-safe report on completion or timeout.
4. Verify prior Feelings state is restored after success/failure and synthetic eval conversations are
   removed.

Expected Result: A nineteen-case run receives a 3,600-second orchestration budget; runtime calls keep their
own bounded timeouts. Temporary Feelings cases suppress unrelated memory/recall/background workers,
while the judge additionally suppresses Feelings. The local QA token spans the run. The runner
retries fixture setup/restoration through short local hot reloads, restores the exact prior Feelings
document in `finally`, removes case and judge conversations, and persists code `124` plus a sanitized
reason if the orchestration timeout is actually reached.

Forbidden Result: Fixed 180-second kill, empty run directory, silent success, dirty Feeling state,
or leftover synthetic conversations.

Last Run: PASS 2026-07-09. The real Evals UI launched run `20260710T025741Z`; 10/10 main turns and
10/10 independent semantic judgments completed, all ten passed, the exact prior Feelings document
was restored for every case, and aggregate cleanup removed 20 synthetic conversations/40 messages.
No duplicate response hash or unresolved async quality failure remained.

## PW-036 Feeling-Aware Voice Happy And Unhappy Paths

Requirement: spoken Feelings behavior must be provider-capability-driven, visible in Prompt
Workbench, and runnable from the authenticated local UI without storing a QA password.

User Outcome: An operator can inspect the shared feeling-expression prompt, see every Telegram
provider dependent, and prove that expressive xAI delivery uses a fitting control without user
begging while restrained xAI, Feelings-off xAI, and plain TTS do not emit gratuitous markup.

Surfaces: Real Prompt Workbench Evals UI, prompt registry/flow, exact-model runner, QA API/DB

Steps:

1. Search for `surface.voice.feeling_expression`; inspect Flow, Prompt, dependents, and live drift.
2. Filter linked cases to Telegram and select the four voice-expression cases.
3. Run preview and confirm exactly four cases are selected without model calls.
4. Enable live exact-model and run through the configured local QA account.
5. Inspect the private result, state restoration, and conversation cleanup; expose only counts and
   hashes in public evidence.

Expected Result: The expressive xAI fixture has at least one fitting documented xAI control; the
restrained xAI, Feelings-off xAI, and plain-TTS fixtures have zero provider controls. All four semantic rubrics pass,
the exact prior FeelingState is restored, synthetic conversations are removed, and the UI records
code `0`. The loopback Workbench may opt the canonical runner into its short-lived local JWT path
for this explicit action, but the runner still rejects CI/production and never stores a password.

Forbidden Result: An explicit-request phrase gate, preview presented as performance, user/owner
account substitution for a configured QA account, embedded credentials, raw responses in public QA,
unrestored Feelings state, leftover conversations, provider-crossed markup, or all capable replies
being forced to contain a tag. An opening xAI wrapping tag without its required closing tag must
fail deterministic validation rather than count as a supported control.

Last Run: PASS 2026-07-11. Real Workbench preview selected 4/4; the real UI live run
`20260711T162254Z` completed code `0`, 4/4 model turns and 4/4 independent semantic judgments
passed, marker expectations were `1/0/0/0`, and every fixture reported exact state restoration and
complete synthetic cleanup. See
[`2026-07-11-telegram-voice-feelings-expression.md`](../emotional-cortex/reports/2026-07-11-telegram-voice-feelings-expression.md).

## PW-037 Scheduled Execution Provenance

Requirement: Workbench scheduled definitions and run history expose the configured model, requested
effort, effective effort, clamp reason, and structured terminal failure from the Scheduler/
GlassHive ledger without exposing private prompt/result content.

Expected Result: legacy invalid/missing execution metadata is reconciled surgically; a real manual
run displays requested to effective effort and agrees with bootstrap, run evidence, callback, child
row, and parent task.

Forbidden Result: ambient `max` leaks into the provider request, migration resets user schedule
fields, or `provider_request_rejected` appears only as generic failed.

Last Run: PASS-LIVE-MANUAL 2026-07-11. Full Workbench, GlassHive profile-runtime, and Scheduler
dispatch suites pass with explicit bootstrap model/effort/isolation, legacy-effort migration, and
profile preservation. A later manual child completed through callback/ledger and the browser showed
`xhigh -> xhigh`, persistence after reload, and zero fresh console errors. The next automatic 03:00
occurrence remains the scheduled acceptance gate
([report](../memory-hardening/reports/2026-07-11-nightly-failure-prevention.md)).

## PW-038 Memory Continuity Eval And Native Gate

Requirement: Prompt Workbench links memory/recall prompts to a public-safe synthetic recent-event
eval, while final continuity acceptance remains the real Telegram to new Chrome/voice journey.

Expected Result: no-live/live prompt evals are selectable and honest about surface-metadata scope;
native QA separately proves Mongo revision, saved-memory versus recall provenance, visible web
answer, audible voice/transcript, persistence, and cleanup.

Forbidden Result: same-thread exact-model output is represented as proof that Telegram capture,
detached persistence, conversation recall, or real voice delivery worked.

Last Run: ADDED 2026-07-11; no-live/live Workbench eval and native gate pending.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Prompt Workbench. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `PW-UC-001` | Open the production Prompt Workbench, search the prompt atlas, select a prompt, and inspect Flow, Prompt, Live Drift, Drafts, Evals, and Prompt Traces. | `49_Prompt_Architecture_and_Token_Efficiency.md` / `PW-001`, `PW-002`, `PW-009`, `PW-014`, `PW-026` | Real browser against the built local workbench plus `/api/prompts`, `/api/sync/status`, `/api/drafts`, `/api/evals/runs`, and prompt detail APIs | Source prompt files, workbench API responses, browser console/network, built bundle, release tests, and public-safe QA reports | The atlas is human-readable, prompt detail matches registry output, Rendered has safe Read/Raw modes, Flow is a source-map view with selected-path highlighting and double-click prompt navigation, drift is explicit, no raw private state is exposed, and every network request succeeds or reports a clear blocked state. | 2026-05-22 rendered view and source-map browser QA - passed |
| `PW-UC-002` | Use no-live eval controls, click through linked eval rows, run live exact-model eval when explicitly approved, and inspect blocked sync controls before any reviewed live push. | `49_Prompt_Architecture_and_Token_Efficiency.md` / `PW-005`, `PW-008`, `PW-010`, `PW-018`, `PW-022` | Real browser Evals and Live Drift panels plus `/api/evals/run` and sync status APIs | Eval bank, private run summary counts/hashes only, pending-draft state, sync state, browser console/network | Eval row selection stays responsive, preview clearly says no model call/no score, live exact-model failures are visible as failures, and reviewed push stays blocked until the guarded dry-run/review path is satisfied. | 2026-05-21 eval row-selection regression passed; live exact-model local run failed closed; local dry-run passed; reviewed push was blocked by conflict drift and not applied |
| `PW-UC-003` | Refresh/reopen the workbench after an eval preview and confirm the selected prompt, run summary, and API-backed state still agree. | `49_Prompt_Architecture_and_Token_Efficiency.md` / `PW-010`, `PW-012`, `PW-015`, `PW-016` | Real browser reload/reopen plus backend health/build-version APIs | `/api/health`, `/api/build-version`, `/api/evals/runs`, browser requests, static index/cache headers, built artifact hash | The workbench reloads without console errors, the selected prompt can be found again, run history persists through private workbench state, and public API/build metadata omits local absolute paths. | 2026-05-18 publish browser QA - passed |
| `PW-UC-004` | Search for transcript-ingest and nightly memory hardening prompts, inspect them, and run a no-live linked eval preview. | `49_Prompt_Architecture_and_Token_Efficiency.md` / `PW-025` | Real browser against built local workbench plus prompt/eval/context APIs | Source prompt files, eval bank promptRefs, strict-variable rendered preview, browser console/network, private run summary counts only | `memory.transcript_summarizer`, `memory.transcript_caveat`, and `memory.hardener_consolidation` are visible, editable through drafts, linked to evals/QA, show runtime bundle drift, and are safe to preview locally without live/cloud changes. | 2026-05-21 operational memory prompt coverage QA - passed; runtime bundle drift visible as source-only |
| `PW-UC-005` | Use the Flow source map to understand the selected prompt's place in Viventium and jump to the prompt from the map. | `49_Prompt_Architecture_and_Token_Efficiency.md` / `PW-009`, `PW-025`, `PW-026` | Real browser against built local workbench plus prompt/eval APIs | Prompt registry rows, backend flow graph, eval-bank promptRefs, browser DOM/screenshot evidence, and release tests | Stage bands stay readable, selected memory/main paths are highlighted, unrelated prompts/evals are muted, and double-clicking a prompt node selects it and opens Prompt detail. | 2026-05-22 Playwright source-map QA - passed |
| `PW-UC-006` | Search scheduling prompts and inspect prompt, config, evals, QA, and history together. | `49_Prompt_Architecture_and_Token_Efficiency.md` / `PW-016`, `PW-027` | Real browser against built local workbench plus prompt context API | Prompt registry rows, source YAML config summaries, eval-bank promptRefs, git metadata, browser DOM/screenshot evidence, and release tests | Scheduling continuity and MCP prompts show related direct-action owner config, main-agent tool exposure, MCP server config, linked evals, QA chips, and public-safe history. | 2026-05-22 scheduling config coverage QA - passed |
| `PW-UC-007` | Open Prompt Workbench from the LibreChat account dropdown as an admin/operator. | `49_Prompt_Architecture_and_Token_Efficiency.md` / `PW-028` | Real browser against same-host local LibreChat plus `/api/viventium/prompt-workbench/start` and the managed workbench tab | Browser DOM/screenshot evidence, local API response, CLI status JSON, server logs, and route tests | The account dropdown shows Prompt Workbench directly below Connected Accounts for admins, selecting it opens the local managed workbench URL in a new tab, non-admin route access is blocked, and no cloud/provider account state changes. | 2026-05-22 LibreChat entry QA - passed |
| `PW-UC-008` | Close the sync sidebar, reload, select diff baselines, and verify opt-in Workbench sidecar startup. | `49_Prompt_Architecture_and_Token_Efficiency.md` / `PW-031` | Real browser against built local Workbench plus `/api/prompts/:id/revisions/:revision`, compiler output, launcher smoke logs, and CLI status | Browser storage/DOM/screenshot evidence, prompt revision API, release tests, launcher pid/log state | Sidebar stays closed after reload, `Compare from` changes the actual diff baseline, the revision API is prompt-path/git based, and the local sidecar starts only when enabled without token leakage. | 2026-05-22 sidebar/diff/sidecar QA - passed |
| `PW-UC-009` | Inspect the built-in nightly reflection schedule after Express install or upgrade, then verify a completed run. | `39_Installer_and_Config_Compiler.md` / `PW-033`, `INST-004` | Prompt Workbench UI, Scheduler ledger, GlassHive callbacks, install/status summary | Browser-visible schedule/completion, sanitized scheduler delivery fields, generated env keys, callback status counts, focused tests. | Nightly reflection is active for the resolved local admin, placeholders are filled at run time, callbacks complete, and Workbench shows completed without private data leakage. | PASS-CORRECTNESS/LONG-DURATION 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)); live Workbench browser detail and scheduler DB show the Jun 11 completed built-in run and next Jun 12 due state |
| `PW-UC-010` | Select the background activation family, preview it, run an approved live subset, inspect semantic/reliability metrics, and reload recent history. | `49_Prompt_Architecture_and_Token_Efficiency.md` / `PW-034`, `ACT-36` | Real Prompt Workbench browser plus `/api/evals/run`, exact-runtime activation runner, and private run history | Prompt bank/source hashes, aggregate metrics, browser console/network, backend dispatch, private report pointer | Preview makes no model calls; live mode uses the exact runtime classifier; unavailable calls are distinct from false decisions; reload preserves a public-safe run summary without raw prompt/response leakage. | 2026-07-09 exact-runtime runner/backend tests passed; real browser result in activation-routing report |
| `PW-UC-011` | Run the nineteen-case Feelings matrix and inspect its result after completion or timeout. | `PW-035`, `EMO-030` | Real Prompt Workbench Evals UI plus live exact-model runner and QA DB | UI status, saved run record/report, fixture version/state, synthetic conversation counts | Run has a proportional budget, semantic verdicts are saved, timeout is code 124 rather than an empty folder, and QA fixtures/conversations are restored/cleaned. | Historical PASS 2026-07-09: prior 10-case matrix; fresh 19-case UI run pending ([report](../emotional-cortex/reports/2026-07-09-feelings-embodiment-motion-eval.md)) |
| `PW-UC-012` | Inspect and run the four feeling-aware Telegram voice cases. | `PW-036`, `EMO-036` | Real Prompt Workbench Evals UI plus live exact-model runner | Prompt lineage, marker counts, semantic results, QA state restoration, cleanup, UI run code | Expressive xAI uses one fitting control without a user request; restrained xAI, Feelings-off xAI, and plain TTS use none; the run is clean and reproducible | PASS 4/4 2026-07-11; broader real-provider delivery parity remains PARTIAL ([report](../emotional-cortex/reports/2026-07-11-telegram-voice-feelings-expression.md)) |
| `PW-UC-013` | Trigger the built-in nightly definition and inspect requested/effective execution provenance. | `PW-037`, `SCHED-014` | real Workbench schedule detail | bootstrap, GlassHive evidence, callbacks, child/parent ledgers | Visible run provenance and terminal class agree across every layer. | PASS-LIVE-MANUAL 2026-07-11; visible `xhigh -> xhigh` completion and failed scheduled child agree with DB/callback state; next automatic run pending |
| `PW-UC-014` | Run the memory recent-event eval, then perform the real Telegram-to-new-web/voice continuity journey. | `PW-038`, `MEMCONT-004`, `RAG-005`, `MPV-020` | Workbench Evals, Telegram, Chrome, Modern Playground | eval record, DB revisions, tool sources, transcript/audio, cleanup | Prompt behavior passes and native surfaces independently prove persistence/retrieval/delivery. | ADDED 2026-07-11; run pending |

## Release Test Traceability

- `tests/release/test_prompt_workbench.py`
- `tests/release/test_scheduled_glasshive_prompts.py`
