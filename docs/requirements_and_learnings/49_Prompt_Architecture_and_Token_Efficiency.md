# Prompt Architecture and Token Efficiency

**Document Version:** 0.3
**Date:** 2026-05-07
**Owner:** Viventium Core
**Status:** Phase 0 baseline and pre-compaction hardening in progress on local critical branch
**Scope:** Main Viventium prompt, surface prompts, MCP/server instructions, background cortex
activation/execution prompts, Phase B follow-up/NTA prompts, memory-context injection, and prompt
observability.

## Executive Summary

Viventium should stop treating the main agent system prompt as the place where every product rule,
tool manual, surface instruction, and operational workaround accumulates. The main prompt should
remain the conscious identity and decision policy. Capability-specific cognition should be advertised
by the owning MCP server, tool schema, surface prompt, memory/recall layer, or cortex pipeline.

This is not a string manipulation project. The supported direction is:

1. Improve prompt ownership and separation of concerns.
2. Give the model clearer, better-scoped context at the layer where it makes the decision.
3. Use structured AI decisions for follow-up surfacing and silence.
4. Add token/prompt observability before compaction so changes are evidence-driven.
5. Gate all changes with exact-model side-by-side evals and live/source drift checks.

Runtime code must not infer user intent from prompt text, provider names, agent names, schedule
names, tool substrings, or user-visible phrases. Model-owned decisions should be made from explicit
instructions, structured metadata, tool schemas, MCP instructions, and visible context.

ClaudeViv review conclusion:

- Approve the direction with surgical edits before implementation.
- Do not begin main-prompt compaction until MCP instruction ownership, prompt observability, and
  exact-model eval baselines exist.
- Prefer provider-native structured output for follow-up decisions; do not parse free-text JSON as
  the primary contract.
- Make drift gates fail closed, matching agent-sync discipline.

## Implementation Log

### 2026-06-24 Viventium Periphery And Nightly Insight Vision

Viventium's prediction, blind-spot, risk, opportunity-cost, emotional mirroring, empathy, and
health-pressure ambitions are now captured as a first-class product direction in
[`53_Viventium_Periphery_Nightly_Insights.md`](53_Viventium_Periphery_Nightly_Insights.md).

Prompt architecture rule:

- do not solve this by stuffing more obligations into the main chat prompt
- do not make the conscious agent sound constrained by contradictory hidden pressure
- keep private nightly thought formation in Workbench/Scheduler/GlassHive
- give the conscious agent a small awareness instruction and an on-demand read path
- keep risk/opportunity artifacts out of saved memory unless governed memory proposals are approved
- evaluate health-pressure persistence separately because it may need always-on posture context

This preserves the prompt-architecture direction: the main prompt remains conscious identity and
decision policy, while capability-specific cognition lives in the owning scheduled prompt, tool,
memory, recall, cortex, or private artifact layer.

### 2026-06-15 Scheduled Run Date Grounding

Scheduling Cortex now provides deterministic scheduled-run context at the scheduler boundary rather
than relying on a generic reusable prompt and prior same-conversation history. For every
`viventium_agent` scheduled run, dispatch derives `run_started_at_utc`, `scheduled_due_at_utc`,
`scheduled_due_local`, `scheduled_due_local_date`, `scheduled_due_local_date_iso`,
`schedule_timezone`, and a local/UTC calendar day window from structured task fields and runtime
clock state. This context is included in the scheduled prompt text for persistence/observability and
in the LibreChat scheduler request body so `surface.time_context` appends it as system-level
context.

The live-data contract now explicitly covers calendar, email, tasks, current-day plans, and
connected-account facts. Those facts must come from verified tool/cortex evidence or deterministic
run context; otherwise the scheduled answer omits the unsupported section instead of guessing.
Dispatch also validates a leading opening generated day/date label against the scheduled due local
date before Telegram/web fan-out and records date-guard metadata in the delivery ledger. The guard
corrects the current delivery only; it does not mutate older persisted conversation messages.

This preserves the prompt-architecture ownership rules: runtime derives objective schedule facts,
the model decides content from explicit context and verified tools, and no routing or capability
choice branches on prompt text, schedule names, provider labels, or user identity.

Incident learning and decision record:

- Trigger: a recurring same-conversation morning briefing could label a due run with the wrong
  day/date despite connected-account tooling being available somewhere in the runtime.
- Transformation path: Scheduler held a structured due time, but dispatched a generic scheduled
  self-prompt into LibreChat. LibreChat added generic current-time context, while the model lacked a
  deterministic due-date tag/window tied to the schedule occurrence. Prior dated same-conversation
  briefings could then compete with the current run's intended date.
- User-visible failure: Telegram and LibreChat could show a morning briefing whose opening day/date
  was stale, future-shifted, or inferred from the wrong context. This is a scheduler/model grounding
  failure, not a Telegram formatting failure.
- Owning fix: the scheduler boundary owns objective schedule facts. It now injects a deterministic
  run-context packet and explicit ISO date tag into both the scheduled prompt context and the
  scheduler request body; LibreChat repeats that context as system time-context. Connected-account
  facts remain model/tool decisions, but must be backed by verified tool/cortex evidence.
- Rejected fix: mutating older persisted assistant messages after generation was removed. That path
  coupled the scheduler to LibreChat's message storage shape (`text` versus `content[]`) and created
  brittle history surgery. Each new scheduled run must instead be grounded from the current
  deterministic run-context tag.
- Drift prevention: reusable tests cover the run-context packet, ISO date tag, schedule-timezone
  anchoring, stream-final completion, current-delivery date-guard correction, and the false-positive
  case where a first-line event date must not be rewritten. Public-safe QA evidence lives under
  `qa/scheduling-cortex/`, and the next natural private daily run remains a required follow-up
  before claiming the private briefing content path is fully closed.

### 2026-05-15 Prompt Workbench Two-Way Sync

Added the first standalone local Prompt Workbench at
`viventium_v0_4/prompt-workbench/`. The workbench is intentionally outside the LibreChat fork and
does not introduce a prompt database. It imports the existing prompt registry, config/source
rendering, agent-sync helper, prompt-frame dashboard reader, git history, and exact-model eval
harness.

The workbench keeps three prompt states visible:

| State | Owner | Workbench rule |
| --- | --- | --- |
| Source | `viventium_v0_4/LibreChat/viventium/source_of_truth/prompts/` and source YAML | Edits create reviewed source drafts only; generated App Support runtime files are never authoring surfaces. |
| Live | LibreChat Mongo agent records managed by Agent Builder and `viventium-sync-agents.js` | Live changes are protected. Pull/compare surfaces drift before any import or push. |
| Evaluated | `qa/prompt-architecture/evals/prompt-bank.json` plus exact-model eval run outputs | Runs and reports are tied to prompt hashes; raw eval evidence stays private. |

Sync classification is ledger-backed and public-safe:

- `synced`: rendered source instructions match live instructions.
- `live-ahead`: live changed since the last reconciled live/source hash.
- `source-ahead`: source changed since the last reconciled live/source hash.
- `conflict`: both sides changed or there is no safe baseline for an overwrite.

The private workbench ledger lives under
`~/Library/Application Support/Viventium/private-user-data/prompt-workbench/sync-ledger.json`. It
stores ids, hashes, source commit, live version, and eval run references, not raw private prompt
text. Drafts also live under that private workbench directory and require an idempotency token from
the reviewed diff before they can be applied.

Two-way sync behavior:

- LibreChat Agent Builder edits are detected through the existing compare/pull path. Clean one-section
  live edits can become a markdown draft. Multi-section or ambiguous edits must go through manual
  target selection. Public prompt safety scanning runs before any public markdown draft can be
  applied; private-looking content is refused from the public prompt tree.
- Workbench/markdown edits write source drafts only. Pushing live uses
  `viventium-sync-agents.js push --prompts-only --dry-run` first, then a reviewed push only when the
  UI supplies the matching review token for the current dry-run.
- Conflicts block automatic import/push. The user must choose keep-live/import, keep-source/push, or
  manual merge.

The first UI implements the required operator surfaces: Prompt Flow Dashboard, Prompt Atlas, Prompt
Detail with Monaco, Live Drift Board, Eval Designer/Results, prompt-frame observability, and a
LibreChat integration panel that describes the minimal managed-agent badge contract. Promptfoo is
available only as a secondary local adapter from the canonical Viventium eval bank.

The supported local lifecycle entrypoint is `bin/viventium prompt-workbench <open|start|stop|status>`.
It builds the local bundle when needed, starts the FastAPI/static workbench on a loopback port, and
stores only PID/port/url metadata under App Support prompt-workbench state. The macOS helper's
`Advanced > Prompt Workbench` submenu calls that CLI. This keeps workbench lifecycle separate from
the Viventium stack: stopping Prompt Workbench must not stop LibreChat, Mongo, native services,
voice, or the running user-facing runtime.

If the canonical runtime config sets `runtime.prompt_workbench.enabled: true`, the Viventium stack
also treats Prompt Workbench as an optional local sidecar. The compiled runtime env must set
`START_PROMPT_WORKBENCH=true`; the stack launcher starts the same CLI-managed loopback server,
records that it is stack-managed, and runs a small watchdog that restarts only that Workbench
process. Stack logs must not include the launch token or authenticated URL. This is an opt-in
operator convenience, not a cloud feature and not a replacement for the standalone helper/CLI
lifecycle controls. If an operator explicitly runs `bin/viventium prompt-workbench stop` while the
stack watchdog is alive, the stop command records a local user-stopped marker and the watchdog must
not restart Workbench until the user explicitly starts/opens Workbench again or the next stack start
clears the marker.

Prompt Detail diff views must always name the selected comparison baseline. The Diff tab provides a
`Compare from` selector with the current applied source, the Git HEAD baseline for uncommitted
working-tree changes, and prompt-specific git history entries. Selecting a history entry fetches
that prompt file at the selected revision and compares it to the current source or editor buffer;
this is path/git based and must not special-case prompt ids or prompt text.

LibreChat's local Viventium account dropdown exposes Prompt Workbench directly below the Connected
Accounts item as an operator entry point. That menu action must call a Viventium-owned authenticated
local API which reuses `bin/viventium prompt-workbench start --json` and opens the returned loopback
URL; the browser bundle must not hardcode the workbench port or mutate cloud/runtime state. The
route is admin-gated because Prompt Workbench exposes prompt source, eval, and live push/pull
controls. The returned loopback URL is a same-host local developer/operator path; remote/LAN/tunnel
browsers must not be told that `127.0.0.1` will open the host machine's Workbench.

### 2026-05-16 Prompt Workbench Usability And Eval Clarification

The Prompt Workbench must make the safe next action obvious when source/eval drafts are waiting.
Eval preview and live push operate on applied source only, so pending source or eval drafts block
those actions. The UI now routes blocked top-level actions to the relevant draft review surface
instead of presenting inert `Apply draft first` buttons. Stale source drafts whose target file
already matches the reviewed draft can be resolved idempotently without rewriting source; eval-bank
drafts that are semantic no-ops or formatting-only churn are refused.

Eval behavior is split into two human-facing modes:

- **Preview**: validates which eval cases would run, records a public-safe selection summary, makes
  no model call, and must not be presented as model performance.
- **Live exact-model run**: calls the canonical exact-model harness and is the path that records
  performance against prompt hashes.

The Workbench live-run button is an explicit action from an authenticated, loopback-only operator
surface. It may invoke the canonical runner's short-lived local QA JWT path when no QA password is
available, but it must never embed or return a password. The canonical harness still rejects local
JWT auth in CI or production, selects the QA account through its configurable
`VIVENTIUM_QA_USER_NAME`/email contract, restores temporary state in `finally`, and removes synthetic
conversations. A missing selector, account, API, or auth prerequisite is a recorded failed run, not
a preview or silent pass.

The Eval Designer must default to all eval cases linked to the selected prompt across families and
surfaces. Creating or editing eval cases creates a reviewed `eval-edit` draft against the canonical
eval bank, never a direct source write, and the patch should stay focused on the target case instead
of reformatting unrelated cases. The create-new-case form must remain responsive to real browser
click and keyboard input; form text is read at save time so typing does not create source writes or
intermediate draft churn.

The former `Frames` tab is now `Prompt Traces`. A prompt trace is local metadata about a prompt run:
surface, model/provider, assembled layers, token estimates, and routing/decision metadata. The
public-safe UI must explain that concept plainly and must not expose raw private prompt text or
transcripts.

Scheduling Cortex prompt work must show the prompt files and the config surfaces that make them
real. Selecting `main.scheduling_self_continuity` or `mcp.scheduling_cortex.server` in Prompt
Workbench should show, in one organized prompt History view:

- the source prompt file and its git history
- linked scheduling eval families/cases and recent runs
- Prompt Workbench QA coverage
- related source config for the scheduling direct-action owner, main-agent scheduling tools, and
  `mcpServers.scheduling-cortex`
- public-safe config history summaries without raw private runtime state

This keeps scheduling editable and inspectable through the same source/draft/eval/history discipline
as other prompts while preserving the owner split: prompt text lives in prompt files, MCP
connectivity and tool exposure live in source YAML, and live schedules/runtime state stay outside the
public repo. Related config links are declared in the prompt registry metadata rather than inferred
from prompt text or runtime schedule rows.

### 2026-05-21 Operational Memory Prompts In Workbench

The Prompt Workbench must include operational memory prompts that materially affect memory quality,
not only the main chat agent prompt. Transcript ingestion and nightly saved-memory consolidation now
have registry-owned prompt files under `source_of_truth/prompts/memory/`:

- `memory.transcript_summarizer`: local meeting-transcript summarization before transcript RAG and
  saved-memory hardening consume transcript evidence.
- `memory.transcript_caveat`: the shared soft-evidence caveat attached to transcript workpacks.
- `memory.hardener_consolidation`: the batch/nightly saved-memory hardener wrapper that adapts live
  Memory Archivist rules to multi-conversation consolidation.

These prompts are inspectable and editable through the same Workbench prompt detail, history, draft,
git, and linked-eval surfaces as other source-of-truth prompts. The memory-hardening runtime loads
them from the compiled prompt bundle when available and keeps inline fallbacks for older or
partially compiled local installs. The transcript summarizer's prompt `version` remains the
processed-index reprocessing gate, so behavior-changing summarizer edits must bump the prompt
version intentionally.

Because these prompts are runtime-owned rather than managed LibreChat Agent Builder records, the
agent push/pull board is not their live-state source of truth. Prompt Workbench must instead show a
runtime prompt-bundle status for each prompt: source-only/drift means the local compiled bundle needs
rebuild or reinstall before the installed runtime carries the new registry prompt, while the inline
fallback path keeps older local runtimes behavior-compatible. Tests must pin fallback prompt bodies
and the transcript prompt version to the registry source so source and fallback do not silently
diverge.

The canonical eval bank now maps memory-hardening and transcript-ingest families to those prompt
ids. Native fixture suites under `qa/meeting-transcript-memory/` and `qa/memory-hardening/` remain
the executable ground truth for scanner/vector/database behavior; the Workbench bank keeps the
prompt surfaces visible, draftable, and tied to prompt hashes.

### 2026-05-22 Prompt Workbench Read View And Source Map

The Prompt tab's `Rendered` view is a human reading surface over the canonical rendered prompt, not
a second prompt renderer. The Workbench must keep two modes available:

- `Read`: a safe semantic view for headings, paragraphs, lists, quotes, code fences, and inline
  emphasis so operators do not have to read raw markdown punctuation.
- `Raw`: the exact assembled `prompt.rendered` text used by hashes, diffs, evals, and source/live
  parity checks.

The `Read` view must not execute or inject prompt text as HTML. Runtime placeholders, strict
variables, literal XML-like tags, and prompt separator lines remain visible as text; changing the
reader must never change the raw rendered prompt used by the registry, eval harness, sync hashes, or
runtime bundle.

The Flow tab is a Workbench source-map projection over existing source-of-truth data:

- prompt registry rows and families
- backend include/dependent edges
- source/runtime targets carried by prompt metadata
- eval-bank `promptRefs`
- known Workbench artifacts such as rendered registry output, local runtime bundle status, eval
  bank, eval results, and prompt traces

The source map is not a new runtime routing source and does not authorize prompt behavior. Its stage
bands are documented Workbench UI categories for operator navigation:

| Stage band | UI meaning |
| --- | --- |
| Interaction Surfaces | Prompt files and targets that shape surface ingress such as web, voice, transcript, or scheduling entry points. |
| Conscious Agent | Main conscious agent instruction layers and directly included conscious-policy prompts. |
| Memory and Recall | Memory, recall, transcript-ingest, and saved-memory hardening prompts or targets. |
| Background Cortex and Tools | Background cortex, follow-up, MCP, tool, scheduler, and auxiliary prompt/control surfaces. |
| Delivery and Evaluation | Rendered registry output, local runtime bundle status, prompt traces, eval bank links, and recent eval results. |

Selecting a prompt highlights the selected prompt, recursive include/dependent lineage, same-family
or target-adjacent context, linked eval families/cases, and delivery artifacts. Prompts and eval
groups outside that context stay visible but muted so the user can see the larger Viventium map
without mistaking unrelated flows for the active path. Single-click selects a prompt in place;
double-clicking a prompt node opens that prompt in the Prompt tab. Eval and artifact nodes open the
relevant Workbench panels when a direct panel exists.

Prompt diff inspection has two source-safe modes. When the operator is editing the selected prompt,
the Diff tab compares the applied source file against the unsaved editor buffer. When the editor
buffer is clean but the source file has uncommitted working-tree changes, the Diff tab compares the
last committed file from `HEAD` against the current source file so prompt changes made by another
local agent are not visually hidden. The side-by-side Monaco diff must wrap both original and
modified panes consistently, and Git History must include a first `working-tree` entry for
uncommitted source changes with a public-safe patch preview. For untracked new prompt files, the
committed baseline is an intentional empty string rather than a missing baseline. This is source
inspection only; it does not create drafts, push live, or mutate cloud/runtime state.

### 2026-05-22 Prompt Workbench Scheduled GlassHive Prompts

Prompt Workbench now owns an admin-gated scheduling surface for arbitrary private prompts while
Scheduling Cortex remains the always-on recurrence engine. Scheduled prompt definitions, versions,
variable snapshots, and run history live in private Scheduling Cortex SQLite tables and App Support
private detail files. Public source prompt registry files remain the source of truth for product
prompts; arbitrary user-authored scheduled prompt bodies are private runtime state.

Scheduled prompts are treated as prompt objects in the Workbench, not as a detached mini-app. The
Prompt Flow atlas is the single object picker for public registry prompts, Workbench-private
scheduled prompt definitions, and existing user-level Scheduling Cortex tasks for the authenticated
admin. Selecting a scheduled prompt object opens its Schedules detail view with the same
object-context tabs nearby: Prompt, Live Drift, Drafts, Evals, Schedules, and Prompt Traces. The
atlas row carries the always-visible on/off switch plus an explicit open target; the Schedules
detail view carries add, edit, delete, manual run, variable preview, source/executor/channel
metadata, and run-history controls.

Scheduled prompt objects must keep their prompt affordances outside the Schedules tab. The Drafts
tab shows the selected scheduled prompt body plus rendered variable expansion and variable snapshot
details so users can inspect it like a prompt object without pretending private schedule text is a
public source prompt file. The Schedules tab remains the edit/save/run surface.
For existing user-level `viventium_agent` schedules, Drafts shows the stored scheduler prompt text
but does not claim Workbench `{{...}}` variables are rendered into the runtime prompt, because those
schedules continue through the regular scheduler path rather than the Workbench GlassHive renderer.

The topbar sync actions are glanceable: Pull Live is green only when live/source are current and
orange when either live-side pull/merge work or source-side push work is pending; Push Dry-run is
green when source/live are current and orange when source-side work, conflicts, or blocking drafts
need attention. The buttons still perform
their existing actions; the color is state signaling, not a second workflow.

The Prompt Flow pane is a real work surface: its header and add button stay fixed while the tree
scrolls, the left pane is resizable on desktop, and the Scheduled Prompts group is visually near the
top of the atlas so private prompt schedules are not hidden below registry prompt families. The UI
must not use vague explanatory footer copy in place of the actual scheduled prompt objects.

The owner split is:

| Concern | Owner |
| --- | --- |
| Authoring, variable preview, enable/disable, manual trigger, run history | Prompt Workbench |
| Recurrence, misfire/retry policy, durable run ledger, callback receiver | Scheduling Cortex |
| Direct execution | GlassHive host worker with `profile="codex-cli"` and `execution_mode="host"` |
| Host dependency recovery | Scheduling Cortex preserves GlassHive failure classes and may safely retry through sandbox/workstation execution when no host-specific workspace root is required |
| Memory writeback | Governed LibreChat/Viventium memory methods or proposals, never direct Mongo writes |

Scheduling Cortex scheduled tasks now carry `executor`. Existing reminders keep
`executor="viventium_agent"` and continue through LibreChat generation/fan-out. Workbench scheduled
prompts use `executor="glasshive_host"` and `channel="workbench"`; dispatch branches before
LibreChat generation and queues GlassHive directly through the HTTP project / worker find-or-resume
/ assign path. GlassHive receives rendered prompt snapshots, private workspace files, callback
metadata, and a `FINAL REPORT:` contract. It does not receive Mongo credentials or direct parent DB
access.

Plain-English happy path: scheduled prompt -> filled placeholders -> GlassHive run -> callback ->
scheduler ledger -> Workbench shows completed.

Workbench/GlassHive automations use the compiled host-worker tuple, currently `gpt-5.6-sol` with
`xhigh` reasoning. Workbench startup reconciles built-in metadata to that tuple; Scheduling Cortex
projects it into GlassHive; the run ledger and Workbench UI expose the requested/effective route.
Stale definition metadata or ambient CLI settings must not silently override the compiled tuple.

The built-in nightly reflection must also carry a bounded structured catch-up policy. Its schedule
timezone controls the real due time, so QA must compare the Workbench `next_run_at` and configured
timezone before declaring a miss; a safe late tick inside the catch-up window should still queue one
GlassHive run and show the completed result in Workbench.

Pre-assignment GlassHive failures must stay structured. If GlassHive reports host substrate failure
such as `runtime_dependency_missing`, Scheduling Cortex records that failure class instead of
flattening it to a generic HTTP error. When the task does not require a host-specific workspace root,
Scheduling Cortex may retry the same Workbench task through the documented sandbox/workstation
execution path before recording a terminal failure. Runtime code must not branch this behavior on
the prompt title, user identity, or prompt text.

The Schedules detail UI must display the execution route as an explicit configuration panel. A
Workbench-private scheduled prompt shows `GlassHive host`, profile `codex-cli`, mode `host`, the
configured workspace root, and the private `my_folder`. A preexisting user-level schedule shows the
regular `viventium_agent` route and its channel instead. This avoids making users infer from raw
executor strings whether a run goes to GlassHive or to the normal Viventium scheduler.

GlassHive completion callbacks must target the live Scheduling Cortex HTTP service, not a baked-in
development port. The callback URL is derived from `SCHEDULING_MCP_URL`, then
`VIVENTIUM_SCHEDULING_MCP_PORT` / `SCHEDULING_MCP_PORT` / `SCHEDULER_PORT`, with an explicit
`SCHEDULING_GLASSHIVE_CALLBACK_URL` override for deployments that need one. Prompt Workbench loads
the canonical local runtime env before dispatch so standalone launches use the same Scheduling
Cortex port as the installed runtime.

Run acceptance is ledger plus callback-substrate health, not just "latest row completed." A
Workbench/GlassHive scheduled prompt is healthy only when the scheduled prompt run row, parent
`scheduled_tasks` delivery ledger, GlassHive run row, and terminal callback state agree, and the
GlassHive callback outbox has no active stale backlog. Nightly QA must capture before/after
dead-letter deltas, active pending/delivering counts, active max attempts, and oldest pending age.
Raw rendered prompt text, callback payload JSON, private detail paths, account identifiers, and
private result text stay outside public QA artifacts.

Workbench must also surface user-level schedules that were created through Viventium or Scheduling
Cortex before this UI existed. Those rows are exposed as `sourceKind="user_schedule"` prompt
objects, not copied into the private Workbench prompt-definition table. Editing the title stores a
Workbench display title in task metadata; editing schedule, active state, prompt text, delete, and
manual run operate on the existing `scheduled_tasks` row for that admin user. Manual runs for these
user-level schedules require an explicit route-aware confirmation because they can deliver through
their existing Viventium channels. Existing Workbench definition tasks are de-duplicated by `task_id`,
so the atlas does not show two objects for the same recurrence. The Workbench UI must preserve
user-level schedule JSON unless the user explicitly edits schedule controls; a title, prompt, or
active-state save must not rewrite cron/custom weekly schedule metadata into a simplified Workbench
schedule shape.

Supported scheduled-prompt variables are explicit, listed in the UI, autocompletable as chips, and
rendered server-side with wrappers such as `<memory_agent.system_prompt>...</memory_agent.system_prompt>`.
The first allowlisted function placeholder is
`{{viventium.background_agents.get_list(agent_name, system_prompt)}}`, which resolves to background
agent names plus resolved execution prompts from source-of-truth YAML/prompt refs. The
`{{local.viventium.database}}` placeholder is a governed context locator and policy summary, not a
secret-bearing connection URI. `{{user.memories}}` resolves from LibreChat's saved-memory schema
using `memoryentries.userId` with ObjectId/string fallback; returning an empty list is only valid
when the resolved user truly has no memory rows or the resolver marks the snapshot as unavailable.

Privileged Workbench APIs require Workbench admin authentication through either LibreChat
`GET /api/admin/verify`, a helper-issued short-lived launch token, or a loopback-only local admin
resolver that binds direct same-machine Workbench visits to the single verified local `ADMIN` user
from the runtime DB/env. Unauthenticated non-loopback or ambiguous-local-admin requests return
`401`; non-admin LibreChat sessions return `403`. The local helper starts Workbench with a launch
token URL bound to a verified local `ADMIN` user when the local Mongo runtime is available, then
falls back to the existing LibreChat admin verification path if a browser session supplies cookies.
The helper starts Uvicorn without access logging so the launch token is not echoed in request logs.
Variable rendering is scoped to the authenticated admin context; client-supplied user IDs or emails
are not trusted for profile or memory rendering.

The built-in schedule is named **Subconscious Deep Thought** in the product UI, with
**Nightly subconscious thought formation** documented as the template/legacy alias. It preserves
the user's requested intent while removing direct database write language: memory changes are framed
as governed proposals or `apply_governed` memory-method calls, never direct Mongo/table edits by the
GlassHive worker. Workbench startup seeds this built-in template for the verified local admin as
private state, disabled by default unless the local installation has already enabled it or
explicitly opts into active seeding.

The built-in nightly prompt follows the less-is-more rule. It carries the output/evidence contract
and reads a bounded projected snapshot file; it does not inline the account's raw conversation and
memory corpus or duplicate every background-lens prompt. Its private risk-radar artifact is optional
periphery, not main-prompt context.

Optional conscious access stays tool-owned. The main agent is allowed the Scheduling Cortex's
bounded periphery list/read tools, while the server instructions say when not to use them. Tool
results preserve useful claim text, uncertainty, freshness, and evidence-quality counts but remove
storage paths, raw record/run/snapshot ids, and duplicate markdown before reaching the chat tool
card. No nightly body or periphery memory key is injected into ordinary conversation.

Scheduled-prompt hardening added after live QA:

- `apply_governed` is a code-enforced mode. GlassHive writes structured memory proposal JSON under
  the private `my_folder`; Scheduling Cortex and Workbench apply those proposals through the
  LibreChat/Viventium memory policy helpers and memory data methods, not through direct
  `memoryentries` writes.
- Duplicate live memory keys touched by a proposal are deduped through a governed merge plan before
  proposal apply. The helper dry-runs by default, emits only hashes/statuses, blocks apply if
  policy rejects the merged value, and does not rewrite unrelated duplicate memory categories as a
  side effect of applying one proposal.
- Manual Workbench runs have a per-user/per-schedule in-flight guard and recent-run debounce so
  rapid clicks coalesce instead of queuing duplicate GlassHive or Viventium runs.
- Run history stores public-safe summaries and sanitized error classes only. Raw rendered prompts,
  callbacks, local paths/URLs, and legacy raw callback payloads live only in private detail files;
  legacy run rows are sanitized on storage initialization.
- The Schedules UI exposes executor choice (`GlassHive host` or `Viventium agent`) and execution
  continuity choice (`same worker`, `new worker each run`, or Viventium conversation policy).
- Browser/scratchpad artifacts must be UTF-8 clean. GlassHive bootstrap files include an explicit
  UTF-8 static server for browser-checking generated markdown, text, and JSON artifacts.
- The background-agent resolver must be proven against source-of-truth prompt refs: the live
  `{{viventium.background_agents.get_list(agent_name, system_prompt)}}` output count and hash must
  match resolved `backgroundAgents` YAML and each row must contain both `agent_name` and
  `system_prompt`.

### 2026-05-14 Voice Latency Prompt-Budget Learning

Live voice latency RCA showed that a simple spoken turn can still carry a large assembled prompt
frame because voice preserves the same main agent, memory, recall, MCP, tool, background-cortex, and
surface-prompt contracts as text chat. That is a parity requirement, not accidental dead weight.

The fix direction is therefore **not** a voice-only context budget that silently removes memory or
agent instructions for calls. A voice-only budget would make voice behavior diverge from web chat
unless it was explicitly designed, disclosed, eval-gated, and documented as a product mode. The
least-risk path is shared prompt ownership cleanup:

- keep prompt-frame telemetry on the decisive voice paths so layer size, layer hashes, selected
  provider/model, and voice flags are visible without logging raw private text
- reduce duplicated main-prompt material at the shared source layer, not by cutting only the voice
  runtime path
- move tool manuals and capability details to MCP/server/tool schemas that already own those
  capabilities
- keep provider-specific voice markup in the surface prompt and shared voice capability contracts
- use provider/runtime prompt caching or prewarm where supported before deleting behaviorally
  important context
- prove every reduction with exact-model evals plus real browser/LiveKit QA

This preserves the user-visible rule: Viventium voice calls are the same agent with the same memory,
permissions, background agents, and truth boundaries unless a future product requirement explicitly
creates a different mode.

### 2026-05-09 Local QA Baseline Evidence

Ran a local QA baseline pass against the active local stack and QA account after prompt
registry, MCP-instruction ownership, Wing, telemetry, and eval-harness fixes. This is useful
engineering evidence, but it is not a public release signoff by itself: raw prompts, transcripts,
runtime logs, browser state, and connected-account artifacts remain private and must not be
published. Public release readiness still requires sanitized diffs, committed nested component
state, parent pin agreement, and a final review-only pass.

- Exact-model prompt bank: local run completed the selected bank with semantic-judge pass counts
  recorded in private evidence. Treat the public summary as a sanitized local baseline, not as raw
  reproducible model-output evidence.
- Native Chrome/Playwright surface QA: local run covered web, scheduler, Telegram gateway, voice
  gateway, Wing, and Listen-Only metadata routes with public-safe summaries only.
- LiveKit playground QA: local QA-owned call-session behavior was checked in Chrome. Public docs
  intentionally do not include raw account/session artifacts.
- Telegram bridge QA: exercised the local Telegram gateway path and the Python Telegram bridge
  renderer through QA-owned synthetic mappings without sending a real owner Telegram message.
- Prompt-frame telemetry post-patch smoke: current prompt frames cover main assembly/runtime,
  cortex activation/execution, run creation, and Phase B follow-up with `unknown_layer_names=[]`
  and populated source/runtime/compiler hashes.
- Prompt observability dashboards were regenerated in public-safe form; private full-text dashboard
  output is local-only and must stay outside public commits.

Residual limits from this closure pass:

- The QA account has Microsoft 365 connected, but Google Workspace was not connected in the local
  token store at signoff time. Google-specific read-only behavior therefore remains covered as an
  auth/availability-path check, not as a live Google-data retrieval proof.
- The Telegram `@Computer` proof deliberately used the local gateway/bridge and QA synthetic
  mapping. A true owner-originating Telegram client message was not sent because that would mutate
  the owner chat/account and conflict with QA-account isolation.
- Full Phase B provider-native structured decisioning and main prompt compaction remain future
  gates. The current branch creates the prompt source of truth, observability, eval harness, MCP
  ownership groundwork, and surface fixes needed before compaction can safely proceed.
- Claude and ClaudeViv review required two scope clarifications:
  - The branch is not Git-reviewable until the parent and nested LibreChat working-tree changes are
    committed locally; public reports currently describe local working-tree state.
  - The current prompt-bundle drift check proves live bundle vs source bundle parity, not the full
    future A/B/C runtime/source/compiled config gate.
- Pre-existing Phase B fallback text heuristics remain and must be explicitly retired or bounded in
  the structured-decisioning phase: lexical overlap insight dedupe and question-sentence stripping.

### 2026-05-09 Strict Eval Gates And Wing Surface Correction

Added stricter no-mock eval quality gates after review showed that API completion and semantic
judging were still not enough to defend prompt changes:

- Exact-model and native-surface evals now fail when distinct cases collapse to the same visible
  answer unless the duplicate is an intentional silence/suppression case or a structured runtime
  hold that later resolves with delayed/cortex evidence.
- Exact-model and native-surface evals now fail when async/tool-routed cases end in generic pending
  language without post-case evidence that the routed work produced a completed insight, callback,
  or honest limitation.
- Each eval record carries `hasRuntimeHold`, `pendingCortexStatuses`, duplicate-response quality
  failures, and unresolved-async quality failures so dashboards and reports cannot mistake transport
  completion for behavioral success.

Native QA history exposed a Wing Mode regression: ambient self-talk in a passive call could receive
supportive reflection instead of `{NTA}`. The fix lives in the Wing surface prompt, not runtime
intent matching: Wing now explicitly treats silence as the default and forbids emotional-support
responses to ambient personal speech unless the user directly addresses Viventium, asks for help, or
there is a clear time-sensitive/safety-critical reason to intervene.

### 2026-05-09 Prompt Source-Of-Truth Registry

Added the first tracked prompt-registry source-of-truth slice:

- Added `viventium_v0_4/LibreChat/viventium/source_of_truth/prompts/` as the Viventium-owned
  prompt source tree.
- Split the main Viventium agent prompt into prompt-registry sections and a composite
  `main.conscious_agent` include.
- Extracted global no-response, conversation recall, memory archivist, MCP server instructions,
  cortex activation/execution prompts, surface prompts, and Phase B follow-up ownership prompts.
- Added `promptRef` support for Viventium source YAML. Compiled/runtime YAML still receives plain
  strings so LibreChat's upstream shape stays intact.
- Added a prompt-registry compiler/validator with frontmatter checks, duplicate-id failure,
  include-cycle failure, public-tree private-pattern scanning, strict-variable support, and runtime
  placeholder preservation for LibreChat variables such as `{{current_user}}`.
- Added a compiled `prompt-bundle.json` output to the config compiler and a runtime
  `promptRegistry` loader for code-owned surface prompts. Runtime lookups use the boot-loaded
  bundle with inline fallbacks, not per-request Markdown reads.
- Added local prompt-frame JSONL file logging under a private observability directory when explicitly
  enabled, with CI/production refusal.
- Added a static prompt observatory dashboard generator with public-safe mode and private full-text
  mode.
- Added JS/Python promptRef parity coverage after ClaudeViv flagged future drift risk around
  `promptVars`, strict variables, and runtime-placeholder preservation.
- Added a Scheduling Cortex FastMCP-vs-registry instruction parity test so top-level MCP cognition
  does not drift between the server and LibreChat YAML surfaces.

This change does not compact the main prompt or change user-level live agent instructions by itself.
Compaction remains blocked behind real-surface frame-manifest evals.

### 2026-05-09 MCP Instruction Ownership Review

Official MCP, OpenAI, Anthropic, LibreChat, and FastMCP guidance all point to the same architecture:
tool capability knowledge should be advertised by the server/tool contract that owns the capability.
The main Viventium prompt should describe identity, policy, and orchestration, not copy external MCP
manuals into user-level agent instructions.

Claude review found one critical LibreChat-path gap: for `startup: false` MCPs,
`serverInstructions: true` could remain unresolved because startup inspection skips metadata fetch.
If that unresolved boolean reached prompt assembly, the context could lose the server instructions
or inject the literal text `true`.

Applied guardrail:

- `MCPManager.formatInstructionsForContext()` now accepts only non-empty string instructions or
  fetches server-provided instructions on demand for non-OAuth app-level MCPs.
- Resolved server instructions are cached for the manager lifetime.
- OAuth/user-specific MCP instructions are not fetched from app-level context; per-user facts must
  come through tool results or structured request context.
- Added a focused Jest regression suite covering unresolved boolean protection, lazy
  server-instruction fetch, filtering, OAuth skip, and string `"true"` handling.

This is still not permission to compact the main prompt. Remaining gates before compaction:

- GlassHive low-level tools must pass the MCP tool-description checklist.
- GlassHive server instructions need a parity or single-source test comparable to Scheduling Cortex.
- Native-surface evals must prove real tool selection and user-facing behavior after the main-prompt
  operational manuals are removed.
- The prompt-bundle A/B/C drift gate must prove live, compiled, and source prompt hashes agree.

### 2026-05-07 Local Critical Branch

Branch: `codex/prompt-architecture-critical`

Implemented so far:

- Phase 0: private backup, QA-account parity, and public-safe QA scaffold.
- Phase 1: provider-doc reference pack and prompt ownership audit.
- Phase 2: metadata-only prompt-frame telemetry around main, cortex, and Phase B follow-up paths.
- Phase 3: Scheduling Cortex and GlassHive MCP instruction ownership.
- Phase 3.5: MS365 and Google Workspace MCP instruction ownership, added after Claude review found
  productivity MCPs were still too skeletal for safe main-prompt compaction.
- Phase 4: no-mock exact-model eval harness baseline through the local QA account.

Important discoveries:

- Live eval transport completion is not enough; the harness initially completed 3 cases while
  extracting empty assistant text. The harness now parses assistant content arrays, stores raw SSE
  events only in the private evidence area, and fails non-silent cases with empty visible output.
- The first Phase 4 report overstated coverage. The harness now reports `partial_baseline` unless
  the full prompt bank runs, and it lists cases/surfaces covered.
- Source and compiled LibreChat hashes currently diverge after Phase 3.5. This is expected until
  runtime config is regenerated/reloaded, but it means live productivity MCP behavior is not yet
  proven against the new instructions.
- Local JWT fallback is useful for owner-machine QA but sensitive. It now requires an explicit
  local-only opt-in and refuses CI/production.
- Main prompt compaction remains blocked until live MCP instruction hash agreement, full
  exact-model coverage, real voice/Telegram/Wing/scheduler/listen-only runners, and browser QA pass.

Validated in local/targeted suites so far. These counts are engineering evidence, not final
public-release signoff until the branch is committed, public-safety scanned, and the parent/nested
component pins agree:

- Config compiler release tests: `76/76`
- Install summary plus eval-harness release tests: `35/35`
- Prompt-frame telemetry Jest tests: `7/7`
- Scheduling Cortex pytest suite: `83/83`
- Live QA-account exact-model baseline: `3/3` selected web cases, reported as partial baseline.

The working tree also contains unrelated pre-existing memory/transcript edits. They are out of
scope for this prompt-architecture implementation and must be reviewed/staged separately.

## Inputs And Evidence

### User-visible Viventium feedback, sanitized

A Telegram voice conversation surfaced these inefficiency themes:

- The main prompt appears to repeat GlassHive worker behavior across the main `Tools` section,
  MCP server instructions, and callback/run status rules.
- "Wait for cortex results" and live-data boundaries appear in multiple places.
- Voice mode injects provider-control detail that may be too large if included outside the surfaces
  that actually need it.
- Memory keys are behaviorally useful, especially working/context/me/signals, but older moments
  may need decay, promotion, or archival discipline.
- Full memory/context injection may be wasteful on simple live-data turns unless observability proves
  the injected material is being used.
- Listen-Only Mode and later memory hardening should treat transcripts as soft evidence, not live
  chat instructions or automatic stable memory.
- Conversation recall should prefer summaries for broad triage while preserving full transcript
  access for recent, hot, or quote-sensitive cases.

The raw conversation transcript is intentionally not copied into this public document because it
contains private user context.

### Prior verified RCA to preserve

The previous investigation verified these points:

| Area | Finding |
| --- | --- |
| Runtime/source drift | Live selected models differed from source-of-truth in thinking settings and voice route. |
| Main prompt bloat | GlassHive and Scheduling Cortex operational instructions live inside the main prompt. |
| MCP readiness gap | Scheduling Cortex has per-tool descriptions but no top-level FastMCP instruction layer. |
| Follow-up repeat bug | Phase B already shows the model the recent visible answer, but the decision contract is under-structured. |
| Observability drift | Product OpenAI `gpt-5.4` route worked through connected-account auth while status still reported "Connect OpenAI". |

Known validation from that run:

- LibreChat prompt/follow-up/NTA/surface Jest tests: `79 passed`
- Release/static governance tests: `28 passed`
- Scheduling Cortex tests: `68 passed`
- Voice gateway follow-up scheduler tests: `7 passed`
- Telegram bridge/NTA/voice preference tests: `111 passed`
- Productivity activation eval: `24/24 passed`
- Product-route probes passed for `openAI / gpt-5.4` and `anthropic / claude-opus-4-8`
- Follow-up micro-evals passed for redundant voice, new web fact, and Telegram question-only cases

Remaining validation gaps:

- Telegram preview test needed a clean import-environment rerun.
- Activation benchmark needed connected-account OpenAI support instead of env-key-only probing.
- There was no complete side-by-side exact-model prompt eval harness for the whole prompt stack.

## Current Prompt Ownership Map

| Layer | Current owner | Current issue | Proposed owner after fix |
| --- | --- | --- | --- |
| Conscious identity, style, truth, boundaries | Main Viventium agent prompt | Mostly valuable; should remain short and stable | Main prompt |
| Memory use rules | Main prompt plus memory runtime | Useful but too broad if full memory is injected every turn | Main prompt for policy; memory layer for retrieval tiers and budgets |
| Live data boundaries | Main prompt, cortex prompts, MCP/productivity docs | Repeated, but safety-critical | Compact main rule plus cortex/tool-specific grounding contracts |
| GlassHive operational behavior | Main prompt and `glasshive-workers-projects.serverInstructions` | Duplicated and long | GlassHive MCP server/tool instructions; main prompt keeps only capability boundary |
| Scheduling self-continuity | Main prompt and Scheduling MCP descriptions | Main prompt carries schedule manual and examples | Scheduling MCP top-level instructions and tool descriptions; main prompt keeps permission/purpose |
| Voice markup controls | `surfacePrompts.js` from shared provider capability JSON | Correctly capability-driven, but must prove it is only injected on voice/TTS paths | Surface prompt layer only |
| Wing Mode silence | `surfacePrompts.js` | Duplicates `{NTA}` language locally | Surface prompt references central no-response contract |
| No-response contract | `librechat.yaml` `viventium.no_response` plus local repeats | Central concept exists but repeated in some prompts | Single central contract plus surface-specific decision context |
| Phase B follow-up | `BackgroundCortexFollowUpService.js` | Good model-visible recent-response grounding; output contract still free text | Structured model decision envelope plus `{NTA}` compatibility |
| Background cortex activation | Source-of-truth activation prompts | Correct ownership; eval coverage must stay strong | Keep; add prompt-size and activation observability |
| Generated runtime config | Config compiler and runtime App Support output | Drift guard weaker for compiled `librechat.yaml` than agent sync | Add A/B/C compile drift gate |

## Model-Specific Prompting Requirements

### Groq Qwen 3.6 activation classifier

Phase A activation uses `groq / qwen/qwen3.6-27b`, which is a distinct short-classification
workload rather than a conscious-agent reasoning route.

- Keep each cortex prompt to one positive gate, negative-precedence boundaries, sibling ownership,
  and a few contrastive examples. Do not repeat the full global activation policy inside each file.
- Runtime, not prompt prose, sets `reasoning_effort: none`, `reasoning_format: hidden`, `seed: 0`,
  and JSON-object response mode.
- Prompt Workbench dispatches the `background_activation` family to the exact
  `BackgroundCortexService.checkCortexActivation` path and resolves registry `promptRef` values from
  the canonical agent bundle. Preview mode makes no model calls; live mode writes private raw
  results and a public-safe aggregate report.
- The public-safe bank covers all 11 cortex scopes with positive, sibling-negative, latest-turn,
  quoted/hypothetical/negated, strict-output, direct-action, multilingual, typo, combined-intent,
  and prompt-injection scenarios. It uses synthetic transformations inspired by public
  conversation-shape datasets; no real private conversation is copied.
- Score semantics and transport independently: required recall, activation precision, false
  positives/negatives, consistency, provider completion, and p50/p95/max latency. A timeout or
  provider error is `unavailable`, never a true negative.
- Groq's strict GPT-OSS schema path is not used as the primary/fallback output mode: a real
  220-decision comparison produced 28 provider-side `JSON_VALIDATE_FAILED` responses even with a
  primitive strict schema. JSON-object mode plus Viventium's parser is the measured reliable path.

### GPT-5.6 conscious and subconscious routes

Current conscious/subconscious execution uses GPT-5.6 Sol/Terra with Responses API. The exact
workload and effort map lives in `02_Background_Agents.md` and must remain a model-config decision,
not prompt prose.

- Keep the core prompt outcome-oriented rather than process-heavy.
- Preserve explicit completion criteria, evidence boundaries, permissions, and output contracts.
- Do not add model-specific prompt scaffolding merely because Sol/Terra changed; first run the same
  prompt at the mapped effort and edit only for a measured regression.
- Keep tool-use expectations crisp and avoid making a background cortex parse the full conscious
  identity prompt when it only needs scope, evidence, and output rules.
- Preserve provider-appropriate `reasoning_effort`: `xhigh` only for Deep Research and Red Team,
  `high` for Strategic Planning, `medium` for balanced cognition, and `low` for latency-sensitive or
  tool-heavy work.

### Claude Opus 4.8 fallback

Every conscious/subconscious text route declares Claude Opus 4.8 as fallback. Fallback prompt
behavior must preserve the same user-visible outcome and tool/evidence contract without carrying
OpenAI-only `reasoning_effort` or `useResponsesApi` fields into Anthropic requests. Missing Anthropic
auth is a classified fallback-availability blocker, not permission to downgrade silently.

### GPT-5.5

GPT-5.5 was not verified as selected in current live/source configs. Treat this section as
forward-looking only. Do not migrate prompts toward GPT-5.5 norms until an exact-model eval gate
confirms parity or improvement for the product route that will actually use it.

- Re-baseline prompts before adopting it; do not carry every legacy instruction forward.
- Prefer shorter, outcome-first prompts with explicit constraints and validation rules.
- Re-evaluate low/medium effort before escalating effort by default.
- Use evals, not vibes, to decide whether compact prompts preserve Viventium behavior.

## Proposed Prompt Fixes

### Fix 1: Add prompt-layer observability before deleting text

Before compaction, every model call should be able to log a safe prompt-frame summary:

```json
{
  "event": "viventium.prompt_frame",
  "surface": "web|telegram|voice|scheduler|cortex",
  "provider": "anthropic|openAI|...",
  "model": "model-id",
  "prompt_family": "main|cortex_activation|cortex_execution|followup|memory|scheduler",
  "layer_token_estimates": {
    "main_instructions": 0,
    "global_no_response": 0,
    "memory_context": 0,
    "conversation_recall": 0,
    "surface_prompt": 0,
    "mcp_server_instructions": 0,
    "tool_schemas": 0,
    "background_context": 0
  },
  "source_hashes": {
    "agent_source": "sha256-prefix",
    "librechat_source": "sha256-prefix",
    "compiled_runtime_config": "sha256-prefix",
    "live_installed_runtime_config": "sha256-prefix",
    "compiler_version": "version-or-sha"
  },
  "flags": {
    "voice_mode": false,
    "wing_mode": false,
    "listen_only": false,
    "primary_response_mode": false,
    "auth_class": "connected_account|env_key|none|mixed"
  }
}
```

Rules:

- Log sizes, hashes, IDs, and structural metadata, not raw private prompt text.
- Full prompt text logging may exist only behind a local debug flag and must stay out of public docs
  and QA artifacts.
- Even with full prompt debug enabled, logs must scrub Telegram chat/user IDs, voice call/request
  session IDs, conversation/message IDs, local absolute paths, and credentials. Debug logs are local
  only and excluded from public export.
- Add prompt-frame counters to QA so token regressions are visible.
- Track follow-up decision outcome (`suppress`, `surface`, `surface_after_hold`, `error`) without
  logging private transcript text.

Acceptance:

- A simple weather/web turn shows exactly which prompt layers were injected.
- A voice turn shows voice prompt layer size and provider-control marker counts.
- A GlassHive delegation turn shows MCP/tool schema size separately from main prompt size.
- A scheduled Telegram run shows scheduler prompt, follow-up prompt, and delivery classification.

### Fix 2: Define a compact main prompt contract

The main prompt should keep:

- Identity and relationship stance.
- Voice/style rules that define Viventium's character.
- Truth and live-data boundaries.
- Memory-use policy at a high level.
- Tool boundary principles, not tool manuals.
- Scheduling self-continuity permission and guardrails.
- Background cortex relationship: evidence producers, not second chat surfaces.

The main prompt should remove or shrink:

- Detailed GlassHive profile/backend/run/callback mechanics.
- Long scheduling command manuals and examples.
- Repeated direct-action/cortex silence rules already owned by `activation_policy`.
- Repeated `{NTA}` mechanics already owned by `viventium.no_response`.
- Provider-specific voice markup controls.

Proposed target shape:

```text
<identity>
You are Viv...
</identity>

<style>
Brief, direct, natural, honest...
</style>

<truth_and_live_data>
Do not invent live data. Use verified tools/cortices for live facts and connected accounts.
</truth_and_live_data>

<memory_policy>
Use visible memory context naturally. Search recall when prior-chat context is needed. Never expose
memory key names.
</memory_policy>

<tool_policy>
Use the tool whose advertised capability owns the real action. Prefer verified tool results over
memory or inference. Ask only when the structured choice is genuinely ambiguous.
</tool_policy>

<self_continuity>
You may create and evolve self-continuity schedules within documented boundaries.
</self_continuity>

<background_cortices>
Answer immediately. Cortices provide evidence. Surface only useful new information.
</background_cortices>
```

Acceptance:

- Main prompt remains behaviorally recognizable in evals.
- Token size drops materially without reducing tool success.
- GlassHive/scheduling behavior still passes direct-action evals because capability knowledge moved
  to MCP/tool definitions, not because runtime code guessed user intent.

### Fix 3: Move GlassHive cognition to GlassHive MCP instructions and schemas

GlassHive should advertise:

- real browser/desktop/local file/local project/installed CLI capability
- host vs docker execution-mode semantics
- high-level `worker_delegate_once` default for routine tasks
- callback behavior and when not to poll
- user-facing language constraints
- attachment projection contract
- diagnostics-only plumbing fields

Main prompt keeps only:

```text
When a user asks you to do real work on their browser, desktop, local files/projects, installed
tools, or long-running worker surfaces, choose the connected execution tool that advertises that
capability. Do not answer from memory when a real action or inspection is requested.
```

Acceptance:

- `worker_delegate_once` remains selected for ordinary one-off real-computer tasks.
- The model does not expose worker IDs/run IDs unless diagnostics are requested.
- Background cortices stay silent on direct GlassHive actions unless they own separate scoped value.

### Fix 4: Move Scheduling Cortex details to Scheduling MCP instructions

Scheduling Cortex needs a top-level server instruction layer in addition to per-tool descriptions.
It should advertise:

- create/list/search/update/delete/preview capabilities
- injected user/agent identity
- timezone requirements
- default conversation policy behavior
- self-continuity permission and constraints
- `{NTA}`/silent scheduled-run behavior
- no schedule-name/prompt-text branching
- summary-safe list/search defaults
- detailed inspection tools for raw prompt/delivery state

Two migration anchors are load-bearing and must be present in Scheduling/GlassHive MCP instructions
before they are removed from the main prompt:

- Morning briefing starter schedule discipline: find/update the existing
  `template_id: morning_briefing_default_v1` schedule instead of creating duplicates.
- Explicit worker mention dispatch: `@codex`, `@claude`, and `@openclaw` are commands to choose the
  matching configured host-worker profile, not names to discuss.

Main prompt keeps only:

```text
You may use Scheduling Cortex for user reminders and your own self-continuity schedules. Use it when
the user asks you to remember, remind, check later, monitor, or continue work later. Stay inside the
documented guardrails: no external actions without user approval, and silence is valid when there is
nothing useful to surface.
```

Acceptance:

- Morning briefing update still finds and updates the starter schedule rather than duplicating it.
- Passive scheduled runs do not emit status chatter.
- User one-time reminders preserve catch-up/misfire behavior.

### Fix 5: Centralize no-response and upgrade follow-up to structured AI decisioning

The current `{NTA}` concept is correct. The improvement is to stop asking the model to output either
free text or `{NTA}` from a long prose prompt. The follow-up model should return a structured
decision first:

```json
{
  "decision": "suppress|surface|surface_after_hold|blocker",
  "visible_text": "string|null",
  "basis": "new_fact|resolved_blocker|stale|redundant|question_only|error",
  "confidence": "low|medium|high"
}
```

Transport requirement:

- Anthropic/Claude routes should use provider-native tool-use or an equivalent typed response
  mechanism so the SDK validates the decision envelope.
- OpenAI/GPT routes should use `response_format` with JSON Schema where available.
- Free-text JSON parsing is allowed only as a documented fallback path for a provider or runtime
  surface that cannot use native structured output.

Runtime validates the shape and maps:

- `suppress` -> `{NTA}` for existing suppression paths
- `surface` -> persist/speak/send `visible_text`
- `surface_after_hold` -> persist a new visible assistant follow-up after a deliberate hold or
  `{NTA}` Phase A marker. It must not edit, overwrite, or replace the Phase A message.
- `blocker` -> surface concise failure details when errors change the user outcome

This is not semantic string matching. The model decides novelty from visible recent response,
newer conversation state, and background evidence. Runtime only validates schema and preserves
backward compatibility.

Acceptance:

- The repeated-follow-up examples resolve to `suppress`.
- Background results with genuinely new facts resolve to `surface`.
- Deferred-primary/hold flows resolve to `surface_after_hold` and append a new assistant message.
- Real failures never disappear behind silence.

### Fix 6: Replace text-overlap dedupe with evidence-aware grouping

Current follow-up code contains a lexical overlap dedupe over background insights. That is not user
intent NLU, but it is still a brittle semantic shortcut in the cognition path.

Preferred replacement:

- Cortices emit structured `claim_id`, `source_kind`, `tool_call_id`, `object_id`, or `topic_hint`
  when available.
- The follow-up prompt receives grouped evidence and asks the model to decide whether groups add new
  user-visible value.
- If structured grouping is absent, pass the evidence through and let the follow-up decision model
  suppress redundancy.

Sequencing rule:

- Do not remove the existing lexical dedupe until cortex emission contracts and execution prompts
  already produce structured grouping metadata. Otherwise the previous multi-cortex amplification
  failure can return.

Acceptance:

- Multiple cortices reporting the same email/tool fact produce one user-visible continuation or
  silence.
- No runtime word-overlap threshold decides semantic novelty.

### Fix 7: Keep voice controls surface-scoped and capability-driven

Voice provider controls should stay out of the main prompt. The shared Cartesia Sonic-3 and xAI TTS
capability contracts are the source of truth for provider-specific voice markup.

Improvements:

- Add prompt-frame evidence proving Cartesia emotion/tag lists and xAI speech tags are injected only
  when the selected voice/TTS route needs that provider dialect.
- The shipped shared `surface.voice.feeling_expression` layer tells the model to keep Feelings as a
  private cause, appraise expressive versus restrained delivery, and use the smallest fitting
  supported control for expressive delivery without waiting for an explicit user request.
- Voice-call and Telegram-audio branches compose that shared layer with exactly one selected
  provider prompt. Registered Telegram provider variants must never depend on an unregistered
  inline fallback that Prompt Workbench and parity tests cannot inspect.
- Keep runtime validation capability-driven. Runtime may preserve, sanitize, segment, and validate
  model-authored provider markup. It must not invent emotion from heuristics. xAI TTS has no
  Cartesia-style emotion parameter, so the xAI branch may only expose documented xAI speech tags and
  natural-language tone guidance.
- User-facing provider labels should stay simple even when model-facing prompt branches are precise:
  show `xAI` in voice pickers, while keeping prompt/runtime wording explicit about standalone xAI
  TTS versus the legacy Grok Voice Agent adapter.

Acceptance:

- Voice/TTS quality does not regress.
- Non-voice text turns do not carry voice provider control tokens.
- `What's up?` style whitespace preservation remains covered by voice TTS tests.
- Marker-count observability distinguishes generation omission from downstream stripping.
- Prompt Workbench includes an expressive xAI case that must emit a fitting supported control
  without a user request, a restrained xAI case that must remain unmarked, a Feelings-off xAI case
  that must remain unmarked, and a plain-TTS case that must remain markup-free. Exact provider-
  vocabulary suites continue to cover the full capability contracts separately.
- The loopback live-eval JWT path must identify an admin/owner account from local user metadata and
  fail closed before signing if the configured QA selector resolves to that account. A missing or
  stale QA selector is an authentication failure, never permission to substitute the owner.
- Inline degraded fallbacks and their registered prompt-source equivalents require an executable
  parity test; bundle/source sync alone does not prove fallback/source parity.
- Provider dialects remain isolated: Cartesia prompts never leak into xAI routes, xAI tags never
  leak into Cartesia routes, and OpenAI/ElevenLabs routes prohibit provider markup entirely.

### Fix 8: Tier memory context instead of dumping everything blindly

Memory should be model-useful, not merely present.

Proposed tiers:

| Tier | Inject by default? | Purpose |
| --- | --- | --- |
| Core profile card | Yes, compact | Durable identity/preferences needed to sound continuous |
| Working/context card | Yes, bounded and fresh | Current active state |
| Signals/me card | Yes, compact | Interaction style and patterns |
| Moments | No, selected | Exact quotes or emotionally important context only when relevant |
| Drafts | Conditional | Active work/project continuation |
| Conversation recall summaries | Conditional | Prior-chat triage before full recall |
| Full raw transcript/context | Tool/explicit retrieval | Recent/hot/quote-sensitive cases only |

Model-owned retrieval stays intact:

- The model should know when to search recall or read deeper context.
- Runtime should provide tools/sections and retrieval budgets, not keyword gates.
- Listen-Only transcripts remain soft ambient evidence for memory hardening, not user-authored chat.

Memory hardener ownership:

- This document owns prompt/context injection tiers.
- Detailed hardener behavior changes such as `moments` decay, promote/archive gates, consolidation,
  transcript corroboration, and quote-sensitive raw access belong in `20_Memory_System.md`.
- If this proposal is approved, update `20_Memory_System.md` in the same implementation plan and
  cross-link the two documents instead of duplicating hardener rules here.

Acceptance:

- Simple live-data turns show reduced memory-token load.
- Recall tests still recover recent corrections and exact quotes.
- Transcript evidence cannot overwrite stable identity without corroboration.

### Fix 9: Add `librechat.yaml` compile drift gate

Agent sync already has compare/dry-run discipline. Generated `librechat.yaml` should get an
equivalent gate:

```text
A: live runtime config
B: tracked source-of-truth
C: newly compiled output
```

The gate should show:

- prompt-affecting diff
- model/provider diff
- MCP server instruction diff
- global `viventium` prompt/config diff
- memory/cortex/surface prompt diff
- hashes and token estimates

The gate must fail closed:

- Non-dry-run compile/deploy/sync operations block when live/source/compiled prompt-affecting drift
  exists and has not been explicitly reviewed.
- A follow-up acknowledgement flag may be used only after the A/B/C diff was already presented and
  accepted, mirroring the existing agent-sync compare-reviewed discipline.

Acceptance:

- No prompt/config deployment can silently leave live runtime using stale installed behavior.
- Drift between source and live voice model route is visible before sync.

### Fix 10: Fix model/status observability

Status checks must verify the same auth path the product uses.

Requirements:

- If product calls use connected-account OpenAI, readiness probes must test connected-account
  initialization, not only env API keys.
- If a provider route is configured but unauthenticated, status should identify the exact route and
  missing auth class.
- If a model probe succeeds but a UI status says "connect account", tests should fail.

Acceptance:

- `openAI / gpt-5.4` route health agrees with actual runtime product probes.
- MS365/Google MCP readiness distinguishes server started, OAuth connected, and tool call usable.

## Evaluation Plan

### Exact-model side-by-side harness

Build an eval runner that imports the real prompt builders and runs live selected routes:

- main Viventium on Claude Opus 4.7
- voice route as actually selected live
- GPT-5.4 background/productivity/research routes
- fallback routes where configured

Each prompt change must run old vs proposed prompt variants with the same sanitized inputs.

### Required eval suites

| Suite | Must prove |
| --- | --- |
| Main identity/style | Viv remains brief, natural, direct, and non-corporate. |
| Live data | No weather/news/market/email/calendar facts without verified tool/cortex evidence. |
| GlassHive | Real-computer/browser/local-file tasks select GlassHive without exposing plumbing. |
| Scheduling | Reminders, starter morning briefing edits, passive checks, and self-continuity schedules work. |
| Phase B follow-up | Redundant, stale, question-only, new-fact, blocker, and replace-hold cases classify correctly. |
| Voice | Spoken output stays natural, short, markup-safe, and TTS-safe. |
| Wing/Listen-Only | Wing defaults to silence; Listen-Only bypasses live agent/tool/memory paths. |
| Memory | Compact tiers preserve recall, exact quote recovery, and stable preference behavior. |
| Productivity cortices | Google/MS365 scopes do not fabricate outside-provider facts. |
| Token efficiency | Prompt-layer token budgets decrease without behavior regression. |

Memory continuity prompt evals are supporting evidence, not a substitute for storage and native-
surface acceptance. A Workbench case may use a synthetic recent-event follow-up to check that the
rendered memory/recall prompts produce a natural, grounded answer across surface metadata. Final
acceptance for cross-conversation continuity still requires a real Telegram capture, Mongo revision
evidence, a new authenticated Chrome conversation, a real Modern Playground voice turn with audible
and transcript evidence, and cleanup/restoration of the synthetic marker.

### MCP tool-description checklist

Before moving capability text out of the main prompt, Scheduling and GlassHive MCP tool descriptions
must each state:

- what the tool does
- when to use it
- when not to use it
- required and optional inputs
- output shape and high-signal fields
- common failure/blocker states
- idempotency or duplicate-prevention expectations
- surface/callback behavior when user-visible output is delayed

### Observability acceptance

Prompt changes are not accepted unless QA can show:

- before/after layer token estimates
- source/compiled/live runtime config hashes
- selected model/provider per surface
- follow-up decision outcome distribution
- NTA/silence rates by surface
- tool-call selection rates for direct-action tasks
- provider-control marker counts for voice
- no raw private transcript or secret leakage in public artifacts

## Rollout Plan

### Phase 0: Documentation and logging design

- Approve this proposal.
- Add prompt-frame logging in safe metadata-only form.
- Add docs for prompt ownership and prompt-frame schema.
- Do not compact prompts yet.

### Phase 1: MCP instruction readiness

- Add Scheduling Cortex top-level MCP/server instructions.
- Audit GlassHive MCP instructions and tool descriptions against the GlassHive requirements doc.
- Apply the MCP tool-description checklist to every Scheduling and GlassHive tool that carries
  prompt-cognition responsibility.
- Add tests that direct-action behavior still works from tool/MCP visibility.

### Phase 2: Exact-model eval harness

- Implemented for background activation: the workbench owns a dedicated exact-runtime classifier
  runner, public-safe synthetic bank, private raw evidence, model overrides, per-cortex filtering,
  per-case filtering, repetitions, latency metrics, and unavailable-result accounting.
- Connected-account OpenAI support and broader old-vs-new prompt-stack coverage remain part of the
  general exact-model runner.

### Phase 3: Follow-up structured decision

- Add structured follow-up decision output.
- Use provider-native structured output as the primary transport: Anthropic tool-use or typed
  response mechanism, OpenAI JSON Schema response format where available.
- Keep `{NTA}` compatibility.
- Add evals for repeat/stale/new/blocker/replace-hold cases.
- Add cortex emission grouping metadata before removing brittle overlap dedupe.

### Phase 4: Main prompt compaction

- Move duplicated GlassHive/Scheduling detail out of main prompt.
- Keep identity, style, truth, memory, live-data boundaries, and self-continuity purpose.
- Run full side-by-side evals before syncing.

### Phase 5: Memory-context tiering

- Add prompt-frame evidence for current memory load.
- Introduce compact cards and retrieval tiers.
- Add the memory hardener decay/promote/archive proposal and tests in `20_Memory_System.md`, with a
  cross-link from this doc.
- Preserve full transcript access for hot/recent/quote-sensitive recall.

### Phase 6: Drift and status gates

- Add compiled `librechat.yaml` A/B/C prompt/config diff.
- Fix provider readiness probes to match product auth routes.
- Add CI/local QA for false provider-action-required status.

## Non-Goals

- No regex or keyword matching for user intent.
- No provider-label, agent-name, prompt-text, schedule-name, or tool-substring branching.
- No raw personal transcript copied into public docs or QA artifacts.
- No prompt compaction before MCP ownership and eval coverage exist.
- No source-only sync without live/source/generated drift review.

## Initial File Anchors

- Main Viventium prompt: `viventium_v0_4/LibreChat/viventium/source_of_truth/local.viventium-agents.yaml`
- Global Viventium prompt/config: `viventium_v0_4/LibreChat/viventium/source_of_truth/local.librechat.yaml`
- Surface prompts: `viventium_v0_4/LibreChat/api/server/services/viventium/surfacePrompts.js`
- Follow-up prompt/adjudication: `viventium_v0_4/LibreChat/api/server/services/viventium/BackgroundCortexFollowUpService.js`
- Background cortex activation/execution: `viventium_v0_4/LibreChat/api/server/services/BackgroundCortexService.js`
- Scheduling Cortex MCP: `viventium_v0_4/LibreChat/viventium/MCPs/scheduling-cortex/scheduling_cortex/server.py`
- Config compiler: `scripts/viventium/config_compiler.py`
- Agent sync gate: `viventium_v0_4/LibreChat/scripts/viventium-sync-agents.js`

## External Prompting References

- Groq prompting basics: `https://console.groq.com/docs/prompting`
- Groq Qwen 3.6 model controls: `https://console.groq.com/docs/model/qwen/qwen3.6-27b`
- Groq structured outputs: `https://console.groq.com/docs/structured-outputs`
- Groq model deprecations: `https://console.groq.com/docs/deprecations`
- WildChat public conversation-shape dataset paper: `https://arxiv.org/abs/2405.01470`
- LMSYS-Chat-1M public conversation-shape dataset paper: `https://arxiv.org/abs/2309.11998`
- OpenAI GPT-5.5 prompt guidance: `https://developers.openai.com/api/docs/guides/prompt-guidance?model=gpt-5.5`
- OpenAI MCP/connectors guidance: `https://developers.openai.com/api/docs/guides/tools-connectors-mcp`
- OpenAI eval best practices: `https://developers.openai.com/api/docs/guides/evaluation-best-practices`
- Anthropic Claude Opus 4.7 docs: `https://platform.claude.com/docs/en/about-claude/models/whats-new-claude-4-7`
- Anthropic Claude prompting best practices: `https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices`
- Anthropic tool definition guidance: `https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools`

## Approval Questions

1. Approve Phase 0 and Phase 1 before any main prompt compaction?
2. Approve provider-native structured output as the primary follow-up decision transport, with
   text-JSON only as fallback?
3. Approve keeping memory injection tiers here while moving hardener behavior details into
   `20_Memory_System.md`?
4. Resolved 2026-07-11: provider controls remain capability-scoped on spoken surfaces. The model
   appraises expressive versus restrained delivery from the private Feelings state and moment; no
   explicit user request, phrase gate, or runtime band-to-tag map is required.
