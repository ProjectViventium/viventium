<!-- qa-evidence-exempt: legacy or audit-style report; supersede with the standard run-report template on next rerun. -->
# Prompt Workbench Implementation QA

Date: 2026-05-15

Environment: local development checkout

## Scope

Standalone Prompt Workbench implementation and follow-up QA pass for source/live/evaluated prompt
visibility, private drafts, guarded two-way sync actions, eval editing/run visibility, prompt-frame
observability, system light/dark support, and responsive browser behavior.

## Automated Checks

Passed:

- `tests/release/test_prompt_workbench.py`: current suite now 27 passed.
- `npm run build` in `viventium_v0_4/prompt-workbench`: passed. Vite still emits the expected
  Monaco large-chunk warning because Monaco is bundled locally for offline/local reliability.
- Browser dry-run guard: `POST /api/sync/push-live-dry-run` returned code 0 and a review token;
  reviewed push remained disabled before dry-run and became available only after the token existed.
  No reviewed/non-dry-run live push was performed.
- No-live eval run from the UI: `POST /api/evals/run` returned a public-safe preview and updated
  recent run history.

Full regression bundle result:

- Command:
  `PYTHONPATH=viventium_v0_4/prompt-workbench/backend uv run --with pytest --with PyYAML python -m pytest tests/release/test_prompt_registry.py tests/release/test_config_compiler.py tests/release/test_prompt_architecture_eval_harness.py tests/release/test_prompt_workbench.py -q`
- Result: 146 passed, 1 failed.
- Failure: `test_js_sync_resolves_full_source_agent_yaml_prompt_refs` because the nested LibreChat
  source file `viventium/source_of_truth/local.viventium-agents.yaml` is currently dirty and has
  expanded instruction strings instead of `promptRef` entries. The canonical prompt markdown still
  contains `# Runtime-Owned Background Cards`, but the dirty YAML no longer resolves
  `main.conscious_agent` through the prompt registry. This was treated as protected source drift and
  not silently overwritten.

## Browser QA

Passed with Playwright Chromium after Browser/IAB controls were not available for this local target:

- Desktop dark-mode user flow:
  selected `main.identity`, collapsed/expanded Prompt Atlas families, switched Source/Live/Evals
  modes, verified selected tab state, ran a no-live eval subset, edited Monaco, saved a private
  draft, inspected the patch, discarded the draft, verified draft list privacy, and confirmed
  Prompt Flow plus Prompt Detail lineage remained visible.
- Live drift guard:
  verified reviewed push is disabled before dry-run, ran `Push dry-run`, received a review token,
  and did not perform reviewed push.
- Desktop light-mode visual QA:
  verified automatic light palette, no failed requests, no console errors, no horizontal overflow,
  and no header title/subtitle overlap at a medium desktop viewport.
- Mobile dark-mode visual QA:
  verified no document-level horizontal overflow, flow canvas constrained to viewport width, and
  core atlas/flow surfaces remained reachable.
- Console/request hygiene:
  the final dark-mode interaction pass reported no browser console messages and no failed requests.
- Status API privacy:
  `/api/sync/status` no longer returns `liveArtifactPath`, `ledgerPath`, or local absolute paths; it
  exposes only availability booleans and a sanitized artifact filename.

## Claude Review Follow-Up

The review-only Claude pass raised gaps around inert controls, fake/static graph behavior, eval
traceability, draft review UX, hardcoded agent ids, source/live/evaluated labeling, and privacy
leaks. This pass addressed those findings by wiring import/reviewed-push actions, adding Draft
Review apply/discard, using backend flow graph edges, adding eval filters and run history, removing
the hardcoded main-agent fallback, renaming A/B/C labels to Live/Source/Evaluated, adding Monaco
DiffEditor, and keeping raw live/draft text out of public list/status APIs.

## Public-Safety Notes

Raw prompt text, live agent text, eval outputs, draft bodies, sync ledgers, and review tokens remain
in local private workbench state or transient browser/API responses. This public report records only
sanitized behavior and no private prompt bodies beyond public source prompt ids/headings.

## Residual Risks

- The dirty nested `local.viventium-agents.yaml` file should be explicitly reconciled before
  claiming the broader prompt-registry regression suite is green. Restoring prompt refs may discard
  local live-imported source drift, so it needs human review.
- The small embedded LibreChat Agent Builder badge is still represented by the integration contract
  and local panel, not patched into the LibreChat fork in this pass.
- Promptfoo remains a secondary adapter; the canonical exact-model eval runner is still the source
  of truth for live evals.

## UX Redesign Follow-Up

User feedback addressed:

- Prompt Atlas was visually crowded and not flow-like enough.
- Prompt Flow Dashboard needed movable/closable/reopenable tabs instead of showing too many panels
  at once.
- Sync sidebar needed collapse behavior.
- Machine-level hashes and raw ids were too prominent in scan surfaces.
- System dark mode needed to follow the OS automatically.

Implementation changes:

- Added `flexlayout-react` for a VS Code-like workbench layout with a single focused default
  tabset, movable tabs, close/reopen via Views commands, badges, reset layout, and persisted layout
  versioning.
- Added `react-arborist` for the Prompt Atlas tree. The tree now starts with
  `Main agent instruction`, follows backend include edges in order, and moves non-main-path prompts
  under `Not in main path`.
- Removed visible content/live/hash strings from Atlas, Flow, Drafts, Eval summary, and footer scan
  areas. Technical hashes remain in source metadata/tests rather than main navigation.
- Made include-only prompts open on Rendered view by default so the main agent instruction shows
  what the LLM receives instead of an empty Monaco body.
- Replaced React Flow SVG background with CSS dot-grid after browser QA found `NaN` SVG console
  errors.
- Added explicit reviewed-push blocking when any live-ahead/conflict row exists.
- Updated responsive shell so mobile layouts scroll vertically without document-level horizontal
  overflow.

Latest automated checks:

- `npm run build`: passed. Monaco bundle-size warning remains expected.
- `PYTHONPATH=viventium_v0_4/prompt-workbench/backend uv run --with pytest --with PyYAML python -m pytest tests/release/test_prompt_workbench.py -q`: current suite now 27 passed.
- `uv run --with pytest --with PyYAML python -m pytest tests/release/ -q`: 541 passed, 1 skipped,
  14 failed. Failures are existing prompt/model source-of-truth governance mismatches in the
  LibreChat prompt bundle, not Prompt Workbench UI changes.

Latest Playwright QA:

- Desktop light fresh layout: Flow opens as the focused default tab; Atlas is ordered main flow
  first; Sync/Workbench sidebar visible; no console errors.
- Desktop collapsed sidebar: canvas gains workspace; reset layout remains available; no console
  errors.
- Prompt tab: include-only main prompt opens on Rendered content; content is readable; no console
  errors.
- Evals tab: no-live `Run selected` completes with code 0 and records a public-safe run.
- Draft loop: `main.identity` edit creates a draft, Drafts badge increments, Draft Review shows the
  patch, discard returns to zero drafts; no source markdown or live agent was changed.
- Dark mode: `prefers-color-scheme: dark` renders readable Atlas, dock, draft panel, and inspector;
  no console errors.
- Mobile 390x844: no document-level horizontal overflow; document height exceeds viewport so the
  page scrolls instead of clipping content; no console errors.

## UX Enhancement Pass

User feedback addressed:

- Replaced the placeholder text logo with the Viventium logo asset from the workbench public
  assets.
- Removed the duplicate `Views` command row so the movable FlexLayout tabs are the only primary
  view navigation.
- Added Prompt Flow sidebar collapse from the top bar and `Cmd/Ctrl+B`.
- Added logo-opened Settings for System/Light/Dark theme selection and status bar visibility.
- Made the bottom status bar hidden by default while keeping it available for action logs.
- Added Prompt detail frontmatter/sidebar collapse.
- Changed the Prompt detail header to wrap controls rather than clipping labels when both sidebars
  are visible.
- Added outside-click dismissal for Settings and guarded the global sidebar shortcut so text inputs
  keep normal keyboard focus.

Latest automated checks:

- `npm run build`: passed. Monaco bundle-size warning remains expected.
- `uv run --with pytest --with pyyaml python -m pytest tests/release/test_prompt_workbench.py -q`:
  current suite now 27 passed.

Latest Playwright UX QA:

- Verified logo opens Settings and outside click dismisses it.
- Verified Settings theme controls switch to dark mode and back to system mode.
- Verified the status bar toggle shows/hides the bottom `Ready` strip.
- Verified Prompt Flow sidebar collapses/expands from the icon and `Cmd/Ctrl+B`.
- Verified `Cmd/Ctrl+B` does not collapse the Prompt Flow sidebar while the search input is focused.
- Verified Prompt detail frontmatter sidebar collapses/expands and the editor gains space.
- Verified the duplicate top `Views` button row is gone; only the FlexLayout tab row remains.
- Captured desktop light/dark/collapsed/editor screenshots as local QA evidence.

Claude follow-up:

- Earlier review-only Claude feedback drove the dock reset/reopen, Atlas DAG/tree rule, hash
  removal beyond Atlas, Monaco resize, React Flow resize, stale reviewed-push guard, and mobile
  fallback improvements.
- A final review-only Claude CLI pass completed with no blockers. It raised polish items around
  editable-field shortcut hygiene, outside-click Settings dismissal, narrow editor header wrapping,
  tab reopen ergonomics, and reset-button placement. The first three were addressed in this pass;
  tab reopen currently remains available through Reset layout rather than a second duplicate Views
  row.

## Helper Lifecycle Addendum

User feedback addressed:

- Added `bin/viventium prompt-workbench <open|start|stop|status>` as the supported standalone
  workbench lifecycle command.
- Added helper `Advanced > Prompt Workbench > Open`, `Start`, and `Stop`.
- Scoped workbench stop to the recorded workbench process; it does not call the main Viventium
  stack stop command.
- Refreshed the shipped macOS helper fallback so clean installs and upgrades see the same submenu.

Latest lifecycle QA:

- `bin/viventium prompt-workbench start --json`: passed and reported a loopback URL.
- `GET /api/health` on the reported URL: passed.
- `bin/viventium prompt-workbench stop --json`: passed and stopped only the workbench listener.
- Main Viventium web listener remained up after workbench stop.
- Installed helper binary contains `Prompt Workbench`, `helper-prompt-workbench.log`, and
  `prompt-workbench`.
- System Events menu enumeration showed `Advanced > Prompt Workbench > Open/Start/Stop`.
- Real helper submenu click `Prompt Workbench > Stop`: passed.
- Real helper submenu click `Prompt Workbench > Start`: passed and restored `/api/health`.
- Real helper submenu click `Prompt Workbench > Open` from a stopped state: passed and restored
  `/api/health`.
- Playwright opened the running workbench, verified the Viventium logo, switched Flow -> Prompt ->
  Live Drift -> Flow, confirmed one real visible dock tab row, and found no console warnings or
  failed workbench API requests.

Additional report:

- `qa/stable-dev-runtime/reports/2026-05-15-prompt-workbench-helper-qa.md`

## User-Flow Hardening Pass

User feedback addressed:

- Prompt editing was not yet proven end-to-end like a real user.
- It needed to be obvious what changed, what the history was, which evals/QA applied, and what
  recent eval results existed for a selected prompt.
- Eval editing needed a reviewable draft path.
- Button actions needed visible consequences and no silent live/Mongo writes.
- The implementation needed logs/API/source verification, not just component tests.

Implementation changes:

- Added `GET /api/prompts/{prompt_id}/workbench-context` as an AI-agent-friendly read API for
  prompt path/hash, draft summaries, git history patches, linked eval families/cases, recent eval
  runs, QA coverage, and sync state.
- Added prompt-linked eval metadata in the eval bank and public-safe QA coverage mapping in
  `qa/prompt-workbench/prompt-coverage.yaml`.
- Added Prompt `History` view sections for `What Changed`, `Git History`, `Linked Evals and QA`,
  recent eval runs, and patch preview.
- Made History a focused review surface by hiding the frontmatter sidebar while History is active,
  so linked evals and QA are visible in the first desktop viewport.
- Added eval-case draft editing through the same reviewed draft mechanism used for prompt source
  edits.
- Sanitized eval run public responses so private output directories are represented only by a safe
  artifact name and availability boolean.
- Deduped active drafts, added human-readable change summaries, rejected no-op saves, and kept raw
  draft bodies/absolute target paths out of public list responses.
- Kept Monaco diff models stable after browser QA found a diff-editor disposal page error during
  save-from-diff.

Latest automated checks:

- `npm run build`: passed. Monaco bundle-size warning remains expected.
- `uv run --with pytest --with pyyaml python -m pytest tests/release/test_prompt_workbench.py -q`:
  27 passed.
- `python3 -m json.tool qa/prompt-architecture/evals/prompt-bank.json`: passed.

Latest Playwright user QA:

- Selected `main.identity`, edited the Monaco prompt body with a synthetic public-safe marker,
  opened Diff, and verified the marker plus unsaved state were visible.
- Saved a `source-edit` draft and verified the patch summary and marker in the public draft patch.
- Applied the draft through the UI and verified the source markdown contained the marker.
- Restored the prompt through a second reviewed draft and verified the final source file exactly
  matched the starting text.
- Ran an eval preview and verified the newest eval run was linked to `main.identity` and did not
  expose a local output path.
- Clicked `Push dry-run`, observed dry-run/review status in the UI, and did not run reviewed live
  push.
- Edited a linked eval case, saved an `eval-edit` draft, verified the patch was focused rather than
  broad formatting churn, then discarded the draft.
- Reopened the app after cleanup and verified Prompt History showed source clean, zero identity
  drafts, visible linked evals/QA, visible QA chips, no synthetic marker, and no browser errors.

Logs, API, And Runtime State:

- Inspected the workbench log tail; it showed the expected draft/eval/dry-run routes and no stack
  traces in the inspected window.
- `GET /api/health`, `/api/sync/status`, `/api/prompts/main.identity/workbench-context`,
  `/api/evals/runs`, and `/api/drafts?limit=20` returned successfully with no local
  home-directory path leakage in public JSON.
- Local runtime inspection did not show a Mongo container in this environment. No non-dry-run live
  push was performed; source saves remained reviewed file drafts and live sync remained dry-run
  only.
- One unrelated active local private draft for `main.voice_style` existed before this pass and was
  intentionally left untouched.

Residual Risks:

- The workbench now exposes the core history/eval context clearly for prompt authors and AI agents,
  but the small LibreChat Agent Builder badge remains a future integration surface.
- The broader repo still has unrelated dirty files and known prompt-bundle governance drift outside
  this workbench pass; this report does not claim the entire workspace is release-clean.

Claude hardening follow-up:

- Review-only Claude returned no blockers for the objective.
- It identified two medium defense-in-depth issues that were fixed before closeout:
  draft targets are now limited to prompt source files or the single eval bank file, and reviewed
  live push now re-checks sync status server-side and refuses live-ahead/conflict drift even if the
  UI is bypassed.
- Regression coverage was added for both fixes.
- It also identified polish/backlog items around narrow CORS, eval-link semantics for the main
  agent, route error envelopes, frontmatter serialization churn, cache/token pruning, and deeper
  patch sanitization. Those are not blockers for the current local-only reviewed-draft workflow.

## Pending-Draft Flow Hardening

Date: 2026-05-16

User feedback addressed:

- A prompt draft could be saved, then `Run eval preview` and `Push dry-run` still appeared to
  succeed even though both operations read applied source on disk, not the pending draft.
- The Prompt header could say `source clean` while also showing a pending draft.
- The right Workbench inspector could show reviewed push as `ready` after a dry-run even when a
  draft was still unresolved.
- The flow did not make the next safe action obvious for a human user.

Implementation changes:

- Added backend pending-draft guards for `/api/evals/run`, `/api/sync/push-live-dry-run`, and
  `/api/sync/push-live-reviewed`.
- The guards cover prompt source drafts, live-import drafts, and eval-bank drafts.
- Guard responses use structured 409 details with draft id/kind/prompt/target summaries only; raw
  draft text and absolute target paths stay private.
- Dry-run records now store a source-hash snapshot, and reviewed push refuses stale dry-run tokens
  after source changed.
- The Prompt header now distinguishes `source clean`, `unsaved edits`, and `draft waiting`.
- The Prompt view now shows a visible draft callout and `Review draft` action that opens History
  with the pending patch selected.
- The History layout now keeps the pending patch preview in the first desktop viewport next to the
  change summary and linked eval/QA context.
- Top-level eval/dry-run buttons now explain why they are blocked instead of running against older
  applied source.
- Evals and Live Drift panels show the same block reason; linked eval run buttons read
  `Apply draft first` until the draft is resolved.
- Apply/discard now invalidates prompt context, eval runs, sync state, and draft queries so the UI
  updates immediately after review actions.

Latest automated checks:

- `npm run build`: passed. Monaco bundle-size warning remains expected.
- `python -m pytest tests/release/test_prompt_workbench.py -q` in a temporary test venv: 35 passed.

Latest focused QA:

- Reproduced the broken pre-fix user flow with a real pending `main.voice_style` draft: before the
  fix, eval preview and dry-run produced success notices while the draft remained pending.
- After the fix, the same pending draft blocks eval preview and push dry-run from the UI and from
  direct API calls.
- A separate temporary `main.identity` browser edit was saved as a draft and discarded to verify
  that post-save UI state changes to draft review guidance rather than lingering in a misleading
  unsaved-edit state. The synthetic marker was not written to source.
- The user draft was intentionally left unapplied and undiscarded.
- No reviewed/non-dry-run live push was performed and no cloud state was changed.

Claude follow-up:

- Review-only Claude confirmed the root cause: draft save writes only the private draft ledger,
  while eval and dry-run read applied source files.
- Claude recommended backend parity, eval-edit draft coverage, reviewed-push blocking, dry-run
  source-hash pinning, cache invalidation, and clearer `draft waiting` UX. Those items were
  implemented in this pass.
- A post-fix Claude review found no release blockers and identified residual truthfulness gaps:
  live evals needed all-draft blocking, eval-bank drafts needed Prompt-view visibility, the editor
  buffer needed to reset after saving a reviewed draft, and the reviewed-push inspector badge
  needed to mirror live-drift blocking. Those items were fixed before closeout, with regression
  coverage added.
