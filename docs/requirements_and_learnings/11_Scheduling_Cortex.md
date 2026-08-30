# Scheduling Cortex (Selective Consciousness Continuity)

**Purpose**: Single source of truth for the Scheduling Cortex. This path adds lightweight,
scalable scheduling as an MCP server with a persistent scheduler loop. It adds no separate
scheduling-specific page inside the Viventium core UI; Prompt Workbench owns that product surface.
A hosted GlassHive control plane may expose its own Schedules tab under the single-writer delegation
contract below.

## Executive Summary

The dedicated Scheduling MCP server:

- stores per-user scheduled tasks in SQLite
- exposes CRUD + search tools to the main agent only
- runs a background scheduler loop that triggers prompts on time
- dispatches through existing LibreChat and Telegram routes

## Requirements

### Functional

1. Reuse Prompt Workbench for schedule authoring, effective-prompt inspection, and run history; do
   not add a continuity-specific page.
2. Main is the only model/agent allowed to create schedules. Authenticated users may also author
   through Prompt Workbench or a delegated Glass Drive UI; those surfaces call the selected
   recurrence owner and never create a shadow schedule store.
3. Per-user isolation.
4. CRUD + search for scheduled tasks.
5. Support LibreChat, Telegram, or both.
6. Task payload includes prompt, agent id, time, pattern, created source, and channels.
7. Default to a new conversation per run unless explicitly configured otherwise.
8. Non-blocking scheduler.
9. Authenticated shared adapter contracts may be extended when the existing scheduler, delivery,
   or acknowledgement path lacks a required typed field; do not add channel-specific endpoints.
10. Auto-injected context should provide user identity and the main agent id.

### Non-Functional

- Lightweight and scalable.
- Reliable scheduling with explicit misfire handling.
- Easy deployment.
- Truthful live-data handling: scheduled prompts must not guess fresh external facts such as
  weather, news, markets, or web facts. If no verified tool/cortex result is available for a
  requested live section, the generated user-visible answer should omit that section instead of
  inventing a degraded placeholder or advice.

## Public-Safe Policy Notes

- The main agent parses natural language into structured schedule objects.
- The MCP server validates and stores schedules.
- Keep schedule naming, reminders, and delivery content generic and user-safe.
- Avoid private-contact examples in the public contract.
- List/search browsing must be summary-safe. Ordinary schedule browsing is not a license to expose
  full internal prompts, generated delivery prose, or raw delivery payloads to other answer
  surfaces.

## Main-Agent And GlassHive Parity

- Scheduling capability is declared structurally in the main Agent's MCP configuration and projected
  through the same signed capability broker when GlassHive is the selected conversation provider.
  The model remains responsible for understanding the user's goal and choosing whether scheduling is
  useful; runtime code must not infer scheduling intent from prompt text, tool-name fragments, surface
  names, or agent/provider labels.
- The reviewed `scheduling-cortex` broker policy exposes bounded content reads and user-owned
  create/update/delete operations. Mutations require a unique `invocation_id` and shared replay
  protection, but do not require a second confirmation token because the user's scheduling request is
  itself the product action and the policy is explicitly `writePolicy: allow`. This exception does not
  weaken confirmation rules for email, calendar, files, permissions, or other connected-account
  mutations.
- Projection must report complete/partial/empty state with structured omission reasons. If scheduling
  is declared but unavailable, the worker must receive that boundary and answer truthfully; another
  native tool being present cannot mask the omission.
- Broker cancellation belongs to the live broker HTTP request. A completed outer Telegram/chat signal
  must never be forwarded as the provider-call signal. Successful tool discovery may be reused only
  inside the same short-lived signed grant while user identity and current policy are revalidated for
  each request.
- Acceptance requires a real surface create -> visible confirmation -> persisted row -> delete ->
  visible confirmation -> zero-residue check, correlated with broker and Scheduling Cortex logs. A
  model's prose or a successful `tools/list` response alone is not proof that scheduling worked.
- The 2026-08-10 isolated headed-Web acceptance passed that lifecycle through Main's configured
  Scheduling tools: one causal create receipt, one matching user-owned row, durable expanded activity
  across refresh and zero-POST reopen, then one supported delete and a zero-row sweep with protected
  rows unchanged. This is product-path evidence for the exactly-once action gate, not a substitute
  for unrelated reminder-delivery or cross-surface acceptance.

## Consciousness Continuity Opportunity

Consciousness Continuity is an ordinary `viventium_agent` scheduled object whose source prompt is
registered and visible in Prompt Workbench. It wakes the existing Main agent; it does not create a
new consciousness agent, emotional-driver store, goal database, stream buffer, inner-monologue
thread, tool policy, or authorization layer.

Each eligible occurrence uses the recurrent contract:

1. orient to the current nine-band Feelings snapshot, accepted goals/plans, commitments, due
   schedules, recent conversation, relevant memory/recall, Life context, capabilities, tool
   results, and previous run outcomes;
2. appraise change, relevance, blocks, opportunities, conflicts, and uncertainty;
3. choose intelligently whether to continue work, use an available tool, adjust a plan, schedule,
   ask, communicate, or do nothing;
4. act only within existing authority and confirmation behavior;
5. record actual receipts and disposition so a later opportunity can reappraise reality.

All Feelings are motivational evidence and action tendencies, not commands or permission. There is
no hard Feeling threshold, message quota, cooldown, reward scalar, Connection override, or universal
"feel better" objective. Main may tolerate an unpleasant state when useful and may choose `{NTA}`
when communication would add no value.

- **`CC-062` — Non-coercive continuity.** Continuity must reject engagement pressure, guilt,
  clinginess, quota-obscuring behavior, and every objective that maximizes Feeling values. Silence
  and leaving the user alone remain valid outcomes.
- **`CC-063` — Bounded semantic activation.** Main judges evidence delta without a keyword or
  prefilter in front of that judgment. Proactive public outreach is not a product-wide default; an
  explicitly enabled owner-scoped continuity schedule is the bounded activation surface.

### Trusted origin and automatic-writer exclusions

Authenticated ingress constructs a server-authored `InteractionContext`; clients cannot forge
scheduler origin, worker identity, logical-turn revision, approval, or delivery state. Scheduler
wakes use `actor_kind=system`, `origin=scheduler`, and `surface=workbench`. That internal stimulus:

- does not run the Emotional Reaction Cortex;
- does not run the automatic user-memory writer;
- emits `feelings.reaction.schedule_skip` with `reason=internal_origin`;
- still supplies structured context to background cortices so their existing model-owned relevance
  decision remains intact;
- uses typed metadata for recall/memory visibility, with legacy prompt-text recognition retained
  only for old untyped history.

A genuine external-user source segment produces exactly one Reaction regardless of web, Telegram,
or voice origin.

### Universal occurrence ledger and nonblocking execution

`scheduled_prompt_runs` is the single run ledger for `viventium_agent`, `glasshive_host`, manual
runs, and future executors. The scheduler creates or atomically claims the row before dispatch. A
deterministic nullable `occurrence_key` protects only newly keyed occurrences, leaving historical
duplicates untouched. The row owns lease/attempt state, final disposition, execution snapshot,
channel outcomes, and interaction reference; existing private-detail fields continue to describe
memory, recall, OAuth, tool, and dependency results.

Valid dispositions are `running`, `silent`, `delivered`, `partial`, `superseded`, `failed`, and
`cancelled`. Workbench is an audit sink rather than a transport: a Workbench-only empty run is
`silent`/`audit_only`, not failed delivery.

The joined cognitive-integrity report exposes an enabled Consciousness Continuity schedule as its
own control plane. Its health is based on the latest owner-scoped, scheduler-proven occurrence;
a successful manual run, healthy nightly schedule, or healthy health-context schedule cannot hide
a failed continuity occurrence. An absent or inactive optional continuity definition does not
block deployments that have not enabled it.

The scheduler tick claims work and submits it to a bounded worker pool (default four). One task has
at most one active occurrence; multiple scheduler processes cannot dispatch the same occurrence;
expired leases recover after a crash; pool saturation leaves work eligible for the next tick; and
`metadata.misfire_policy` determines recovery. Recurring catch-up chooses only the latest eligible
occurrence and never bursts missed continuity wakes.

### Prompt ownership and execution parity

Prompt ownership has four visible layers:

- `main.scheduling_self_continuity` is Main's concise standing capability/permission statement;
- `scheduler.run_envelope` is the factual hidden scheduler prefix and context contract;
- `scheduler.consciousness_continuity_opportunity` is the concise per-occurrence orientation,
  appraisal, choice, action/inaction, and outcome contract;
- `scheduler.canonical_output` is the non-interactive, channel-neutral result contract used before
  one generated result fans out through delivery adapters.

The Python scheduler consumes the compiled shared prompt contract; it must not carry a divergent
hard-coded copy. Release tests compare registry source, compiled artifact, and runtime text. The
scheduled object body remains editable/versioned in Workbench and does not duplicate Main identity
or tool policy.

Scheduled Main reloads the current persisted Main Agent from Agent Builder at every run, including
provider, model, parameters, GlassHive options, fallback, identity, instructions, tools, memory,
recall, cortices, and Feelings. The schedule owns timing, conversation policy, and delivery—not a
second execution tuple. Its capability inventory remains the intersection of persisted agent tools,
endpoint-supported tools, MCP audience, user authorization/OAuth, and existing approvals. Scheduler
origin adds and removes no tool or fallback. OAuth is non-interactive: unavailable authorization is
a structured capability result, not an unattended dialog, and confirmation-required action is
proposed or asked rather than auto-approved.

The scheduled-generation stream window defaults to ten minutes. This is a reliability budget for
the potentially long-running Agent Builder route, not permission to block the scheduler tick: work
runs in the bounded pool. The default is below the 15-minute occurrence lease, but current source
accepts an unbounded integer `SCHEDULER_STREAM_TIMEOUT_S` override. It does not clamp that override
below the lease or renew the lease around it. Treat an override at or above the lease as an open
exactly-once configuration gap, not a supported deployment promise, until source validation and
`SCHED-019` regression evidence close it.

### Active-window cadence and configurable example

An interval may declare:

```yaml
active_window:
  start_local: "09:00"
  end_local: "21:00"
  cadence: restart_daily
```

`restart_daily` anchors the local grid at the start of each declared wall-clock window. For example,
a synthetic QA schedule can combine the window above with its configured interval and `Etc/UTC`;
the cadence then restarts at 09:00 each day instead of drifting across a 24-hour boundary. The
schedule's configured timezone remains authoritative across clock changes. Wake inside the window
runs only the latest eligible occurrence; wake outside waits for the next window start.

This cadence is a configurable product hypothesis, not neuroscience. Workbench shows projected daily
runs and measured token/cost history. Public templates remain inactive and contain no private
preferences. A configured delivery may fan one canonical generated text to LibreChat and Telegram. Trusted
scheduler origin selects `scheduler.canonical_output`, not the interactive `surface.web` contract; voice
parity does not create unsolicited calls and uses existing voice behavior only in user-initiated or
explicitly configured voice contexts.

### Durable conversation and visibility

`conversation_policy=same` reuses one dedicated durable conversation rather than creating a thread
per wake. A Workbench manual run records the same canonical conversation receipt as a natural
occurrence, so testing the schedule cannot break reuse on the next wake. The server constructs
trusted scheduling context from the authenticated route and durable records. Worker- or
client-supplied scheduler/worker origin, ownership, approval, turn revision, and delivery state
never become authority: the server rejects a mismatch or overwrites it with the authoritative
server value before applying policy, and records that result for audit. Current history uses this
typed metadata. Regex may classify only imported legacy history that has no typed equivalent; it
must not reinterpret current typed records.

Trusted scheduler control messages and assistant `{NTA}` results are internal, excluded from user
UI, recall, and automatic memory, and retained only as auditable metadata/run history. A
conversation with no completed user-visible assistant result remains archived through existing
`isArchived`; persisted message visibility—not the ambiguous default archive flag—determines that
state. Its first deliverable result unarchives it and later silent wakes do not rearchive it.
User-authored text equal to `{NTA}` stays visible because
suppression depends on trusted metadata, never text alone.

## Misfire And Catch-Up Contract

The scheduler is a local runtime loop, so it must handle host sleep, restart, and long pauses
without silently dropping user-facing reminders.

The launcher must treat the Scheduling Cortex MCP as a supervised local sidecar, not a one-shot
optional startup. Startup success requires a real `/health` probe, and a lightweight watchdog must
restart the MCP if the process exits while LibreChat remains running.

### Runtime Health Identity

Scheduling Cortex is a per-runtime sidecar, not a shared dev-env singleton. The unauthenticated
local `/health` endpoint remains available for launcher and watchdog probes, but it must include a
public-safe runtime identity:

- `status`
- `service`
- `db_path_sha256`
- optional diagnostic fields such as `state_root_sha256`, `runtime_profile`, `dev_env_enabled`,
  `dev_env_name_sha256`, and `pid`

The launcher must only accept a healthy scheduler as "ours" when `db_path_sha256` matches the
launcher runtime's expected `SCHEDULING_DB_PATH`. Missing identity, malformed identity, or a
different DB hash is a port-ownership conflict, not a healthy local-prod scheduler. In that case the
launcher and watchdog must fail loud or wait without killing the other runtime. Raw DB paths, App
Support paths, schedule prompts, schedule content, user ids, tokens, and operator-chosen dev-env
names must not appear in the health payload or public QA evidence.

- A task is a misfire when it is due but first processed after `SCHEDULER_MISFIRE_GRACE_S`
  seconds. The default grace is 900 seconds.
- User-created one-time reminders default to catch-up delivery when they are late but still inside
  the catch-up window. The default catch-up window is 12 hours, controlled by
  `SCHEDULER_CATCH_UP_MAX_LATE_S`, with a hard cap of 24 hours.
- Catch-up eligibility is based only on structured task fields: `created_source == "user"` and
  `schedule.type == "once"`, unless explicit `metadata.misfire_policy` overrides it. Runtime code
  must not inspect prompt text, reminder wording, schedule names, agent names, or other human-facing
  labels.
- `metadata.misfire_policy.mode` may be `catch_up` or `strict`. `skip`, `miss`, and `missed` are
  treated as `strict`. `metadata.misfire_policy.max_late_s` may narrow or extend the per-task
  window up to the hard cap.
- Recurring tasks and system/agent-created tasks default to strict misfire handling so a sleeping host
  does not spam stale runs when it wakes. A user-created one-time task defaults to catch-up no matter
  what the schedule is named; passive/system schedules that need strict behavior must declare
  `metadata.misfire_policy.mode: strict` or use a non-user-created source instead of relying on a
  special schedule name.
- A catch-up delivery must be visibly honest. The dispatch layer prepends a deterministic notice to
  delivered text, for example: `Late reminder: originally scheduled for 2026-02-13 19:00 UTC;
delivered 85 minutes late.`
- If a task is missed instead of caught up, the delivery ledger must still be populated. Missed
  rows record `last_delivery_outcome=missed`, a structured reason such as
  `misfire_grace_exceeded` or `catch_up_window_exceeded`, `last_delivery_at`, and a
  `last_delivery` payload with due time, local due label, late seconds, and policy details.
- If Scheduler dispatch receives a structured LibreChat `scheduler/chat` `user_not_found` failure,
  the task is orphaned: the owning user no longer exists, so the scheduler must preserve the failed
  ledger, record `orphaned_user_not_found`, deactivate the task, and avoid retrying it forever. Other
  failures such as expired provider OAuth remain active/action-required because the user can repair
  the account connection.
- Exact wall-clock delivery while the Mac is asleep is not guaranteed by this MCP alone. That would
  require a separate wake-scheduling or cloud-dispatch design.

## Dispatch Behavior

### LibreChat Channel

- Scheduler generation is canonical.
- Runs should flow through the existing scheduler-authenticated internal routes.
- Scheduled `viventium_agent` generation sends no provider, model, reasoning-effort, GlassHive, or
  fallback override. The scheduler-authenticated route strips legacy execution fields and loads the
  persisted Main Agent through the same Agent Builder initialization/fallback path as ordinary chat.
- Agent Builder is the single execution source of truth. Changing Main there changes future
  scheduled Main runs without compiler edits, schedule rewrites, or restarts beyond the normal
  Agent Builder reload contract. Runtime code must not select a route from task names, prompt
  wording, agent display names, or user identity.
- Dispatch resolves LibreChat from an explicit `SCHEDULER_LIBRECHAT_URL` first, then the compiled
  `VIVENTIUM_LIBRECHAT_ORIGIN`, with `http://localhost:3080` only as a legacy development fallback.
  This keeps standalone Prompt Workbench manual runs on the same installed runtime as the Main
  Agent instead of silently targeting an obsolete default port.
- `executor="glasshive_host"` remains a separate, explicit Workbench automation route with its own
  declared worker profile/model/effort. It is not a substitute name for scheduled Main.
- Conversation policy can be `new` or `same`.
- Scheduled prompts and delayed checks are injected as main-agent work, not delivered as raw
  scheduler text. The main agent/follow-up adjudication path decides whether the result is useful
  to the user or should remain silent with `{NTA}`.
- Visibility is not task-type-specific. Morning briefings, reminders, passive check-ins, heartbeat
  schedules, and future scheduled prompt types must all use the same generated-text visibility path:
  canonical result -> `{NTA}`/empty suppression or visible content -> channel fan-out -> delivery
  ledger.
- Scheduled agent generation must receive a deterministic run-context packet before every
  `viventium_agent` run. The packet is derived from structured task fields and runtime clock state,
  not prompt text or schedule names, and includes `run_started_at_utc`, `scheduled_due_at_utc`,
  `scheduled_due_local`, `scheduled_due_local_date`, `scheduled_due_local_date_iso`,
  `schedule_timezone`, and the local/UTC calendar-day window for the due date. The same context is
  sent to LibreChat as scheduler request metadata so the system time-context layer and the persisted
  scheduled prompt agree.
- The GlassHive conversation-provider `turn_context` envelope has one shared 16 KiB transport
  budget across deterministic time context, ephemeral Active Work context, and source-selection
  context. Fixed/signed capsules remain atomic. Active Work owns only the remaining budget and may
  omit whole lower-priority roster items; it must never byte-slice an item or force a valid tiny
  scheduled request into provider validation failure merely because the account has many work rows.
- Scheduler execution text and conversation-title source are separate fields. The execution prompt
  may contain private scheduler control envelopes; only the bounded original task source (or the
  generic `Scheduled Background Processing` fallback for a self-prompt) may drive user-visible
  title generation. Internal markers must never become new sidebar titles.
- Calendar, email, task, current-day, and other connected-account facts in scheduled output require
  verified tool/cortex evidence or the deterministic run-context packet. The model must not infer
  day labels or current plans from prior same-conversation briefings.
- The dispatch layer must validate the opening day/date claim in generated scheduled text against
  `scheduled_due_local_date` before channel fan-out. If the model labels a due run with the wrong
  opening date, dispatch corrects that visible opening label and records date-guard metadata in the
  delivery detail so the ledger proves whether the guard passed, found no claim, or corrected a
  mismatch. The guard is intentionally narrow: it only rewrites a leading opening date label and
  leaves later first-line event dates unchanged. It corrects the current delivery/ledger output; it
  does not mutate prior persisted conversation messages. This guard is output validation, not
  user-intent routing, and must not branch on human schedule names or prompt wording.

#### 2026-06-15 Scheduled Date-Grounding Learning

- Trigger: a recurring same-conversation morning briefing could label a due run with the wrong
  day/date even when connected-account tooling existed elsewhere in the runtime.
- Causal chain: the scheduler persisted a structured due time, then dispatched a generic scheduled
  self-prompt. LibreChat supplied generic current-time context, but not a deterministic due-date
  tag/window tied to the specific scheduled occurrence. In same-conversation mode, earlier dated
  briefings could compete with the current run's date.
- User-visible failure: Telegram and LibreChat could show a stale or future-shifted opening date.
  This is a scheduler/model grounding failure, not a Telegram formatting failure.
- Decision: every scheduled `viventium_agent` run gets a structured run-context packet, including
  the ISO tag `scheduled_due_local_date_iso`, before model generation. The model may use
  calendar/email/task/current-day facts only when verified tool/cortex evidence supports them.
- Rejected approach: do not mutate older persisted assistant messages to repair this class. That is
  brittle history surgery and couples Scheduler to LibreChat message storage internals. Each new
  run must be grounded from its deterministic run-context packet.
- Drift prevention: regression coverage must keep the ISO date tag, schedule-timezone anchoring,
  no-next-recurrence behavior, current-delivery date guard, first-line event-date false-positive
  protection, and Telegram/web delivery ledger evidence intact.

### Workbench / GlassHive Channel

- Plain-English happy path: scheduled prompt -> filled placeholders -> GlassHive run -> callback ->
  scheduler ledger -> Workbench shows completed.
- The built-in local nightly reflection follows this path by default on supported installs and
  upgrades. Prompt Workbench seeds the `Subconscious Deep Thought` schedule for the first resolved
  local admin user, renders placeholders privately, dispatches via the configured GlassHive host
  worker profile, and records the Scheduler/Workbench/GlassHive ledger without hardcoding a
  developer account. Because this is a built-in overnight maintenance routine, it must declare a
  bounded structured catch-up policy rather than relying on the recurring-task strict default; a
  late local scheduler tick inside the catch-up window should run once and record lateness instead
  of silently losing the nightly reflection.
- Workbench-private scheduled prompts use Scheduling Cortex for recurrence, due/misfire policy,
  run history, and the parent delivery ledger. Workbench owns authoring, variable preview, manual
  trigger, and the visible run-history surface.
- In integrated `viventium_cortex` mode, a Glass Drive Schedules view is a scoped client of this same
  authority. It may submit user-authorized CRUD and display the result, but Scheduling Cortex remains
  the sole writer and ledger owner. In standalone `glasshive_native` mode, GlassHive is the selected
  sole owner instead. Conflicting owners or a second persisted definition fail closed.
- Workbench schedules with `executor="glasshive_host"` render their private prompt variables before
  dispatch, store public-safe rendered and variable-snapshot hashes, then dispatch to GlassHive
  before LibreChat generation. Raw rendered prompt text and private result details stay in private
  runtime storage, not public QA artifacts.
- Built-in Workbench schedules must own an explicit execution tuple: host profile, model, requested
  reasoning effort, and the instruction to ignore ambient user CLI config. Startup reconciliation
  repairs legacy missing-model or invalid-effort metadata without changing the owner, prompt,
  active state, 03:00 schedule, timezone, or run history.
- When a recurring task's persisted `next_run_at` spans several missed periods, misfire grace and
  catch-up limits are measured from the latest eligible occurrence at or before the current tick.
  Dispatch/skip ledgers record that occurrence, then advance to the next period; they never judge
  today's due run from the oldest stale timestamp.
- Daily, weekday, weekly, monthly, and cron recurrence use the schedule's declared timezone, not the
  host's audit-time timezone. Interval minute/hour/day/week schedules are elapsed durations from
  their UTC anchor; they do not silently change cadence when the host travels or crosses DST.
- Direct/manual Scheduling Cortex startup defaults to the canonical App Support state database when
  `SCHEDULING_DB_PATH` is absent. The legacy hidden-home database is not a fallback. Managed launch
  remains explicit and `/health` continues to expose only a public-safe DB identity hash.
- The run ledger distinguishes requested from effective reasoning effort because provider-route
  compatibility may clamp a request. Workbench must show that projection, and terminal callbacks
  must preserve structured classes such as `provider_request_rejected` in both child and parent
  ledgers instead of flattening every provider rejection to generic `failed`.
- GlassHive callback handling must update both the child `scheduled_prompt_runs` row and the parent
  `scheduled_tasks` delivery fields. A terminal callback is not accepted as healthy if the parent
  ledger, child row, GlassHive run row, or visible Workbench state disagree.
- Pre-assignment GlassHive errors must preserve structured failure fields such as
  `runtime_dependency_missing` and `parallel_execution_isolation_required`; generic
  `HTTP 409: Conflict` is not enough evidence. If host execution is unavailable and the scheduled
  task has no host-specific workspace-root constraint, Scheduler may retry through the documented
  sandbox/workstation route before terminal failure. A recognized built-in Periphery template may
  also recover from a parallel-isolation rejection by rebasing only its declared private output
  root to an isolated `artifacts/` root, then importing the required artifact contract after the
  signed terminal callback. This does not relax GlassHive host isolation.
- Isolated Periphery return is contract-driven, not prompt-driven. The callback accepts only the
  module declared by the built-in template, a Workbench-readable schema-v2 sidecar bound to the
  current scheduled run, its same-directory paired Markdown file, bounded file sizes, and an
  authenticated worker artifact endpoint. Worker identity is persisted before assignment; an
  earlier-than-binding callback gets the local retryable `404` instead of a terminal mismatch.
  Required imports claim the occurrence ledger before network or file side effects, and transient
  missing/truncated/import failures return retryable `503` so the same signed completion can
  reconcile safely. It writes the pair atomically with owner-only directory and file permissions
  into the scheduled definition's private folder. Missing, stale-run, malformed, oversized, or
  unsafe artifacts fail the scheduled run and cannot trigger memory application or index refresh.
  Custom templates and non-off memory modes do not gain isolated host-file import authority merely
  by writing matching prompt text.
- Nightly QA must inspect the GlassHive callback outbox as part of scheduler health: active
  pending/delivering counts, active max attempts, oldest pending age, stale delivering rows, and
  before/after `dead_lettered` delta. A fresh dead-letter delta or stale active backlog is a
  degraded delivery substrate even when the newest run row says `success`.

### Viventium Periphery And Nightly Insight Modules

Private nightly insight routines such as risk radar, blind-spot review, opportunity-cost sensing,
and health-pressure inference are governed by
[`53_Viventium_Periphery_Nightly_Insights.md`](53_Viventium_Periphery_Nightly_Insights.md).

Scheduling Cortex owns their recurrence, due/misfire policy, parent delivery ledger, and
Workbench/GlassHive callback reconciliation. The insight module owns its prompt, evidence contract,
artifact schema, surfacing policy, and evals.

Rules:

- Do not add a new insight routine until the current nightly executor path is classified and healthy
  or the failure is explicitly bounded.
- Do not branch on human-facing schedule names, prompt text, or module titles. Use structured task
  metadata.
- Keep first pilots private and Workbench-routed. The risk-radar pilot uses
  `memoryWriteMode=off`; durable memory requires a separate governed proposal path.
- A completed private insight run is not the same as a user-visible alert. Surfacing remains a
  separate model/policy decision.
- Scheduling Cortex owns the user-scoped `periphery_list` and `periphery_read` tools. The list is a
  bounded current/historical index and the read result is an agent-safe evidence view. Neither tool
  returns storage paths, filenames, raw source-record ids, run/snapshot ids, or duplicate markdown.
- Ordinary chat must not inspect periphery. On-demand/deep-review use follows list then read, and
  stale/legacy/failed-quality material is treated as historical uncertainty.
- Explicit Workbench schedules with `executor="glasshive_host"` take the compiled
  `gpt-5.6-sol` / `xhigh` host-worker tuple ahead of stale persisted Workbench metadata. This policy
  does not apply to `executor="viventium_agent"`, which always inherits Main from Agent Builder.

### Telegram Channel

- Scheduled Telegram delivery should reuse the canonical scheduler-generated final/follow-up text.
- Do not start a second agent run through the Telegram chat route just for scheduled tasks.
- Passive schedules must not emit scheduler-synthesized keepalive, status, "no change," or next-run
  announcements. If the canonical scheduled result is `{NTA}` or empty, Telegram delivery stays
  silent unless the model produced substantive user-visible content.
- The scheduler must not branch Telegram visibility on schedule names, prompt text, incident labels,
  or user-facing task titles. Operational exceptions require structured fields such as
  `metadata.misfire_policy`, not runtime string checks.
- Scheduled Telegram delivery must classify transport/runtime fallback separately from
  model-generated content. If a model or background cortex guesses at a live fact, the correct fix is
  the scheduled prompt/source-of-truth truthfulness contract, not a Telegram text filter.
- Scheduler follow-up polling must pass the originating `scheduleId` into the LibreChat cortex-state
  endpoint. The cortex fallback helper uses that structured schedule context to suppress the generic
  "couldn't finish" text for scheduled runs instead of sending it to Telegram.
- When a scheduled run can only surface deferred fallback text, the cortex-state endpoint must expose
  structured provenance (`canonicalTextSource`, `canonicalTextFallbackReason`). Delivery ledgers must
  record this as `fallback_delivered` or `suppressed` with the fallback reason, not as ordinary
  `sent/delivered`.

Current owning implementation points:

- `viventium/MCPs/scheduling-cortex/scheduling_cortex/dispatch.py` owns scheduler generation and
  channel fan-out. `_default_scheduler_run_envelope` delegates to the shared
  `render_scheduler_run_envelope` contract, `_run_scheduler_generation` performs the canonical agent
  run, and `dispatch_task` fans the same result out to the requested channels.
- `dispatch.py` owns visibility classification through `_prepare_generated_visibility`,
  `_build_librechat_delivery_detail`, and `_deliver_telegram_generated_text`. These helpers classify
  `{NTA}`/empty output, visible output, and fallback provenance without inspecting schedule names or
  prompt text.
- `dispatch.py` owns late catch-up copy through `_apply_late_delivery_notice`, which prepends the
  deterministic late-reminder notice only when there is visible content to deliver.
- `api/server/services/viventium/cortexFallbackText.js` suppresses the generic deferred fallback
  sentence when a structured `scheduleId` is present.
- `api/server/services/viventium/cortexMessageState.js` returns empty scheduled fallback text with
  `deferred_fallback` / `empty_deferred_response` provenance when no usable insight exists.
- `api/server/routes/viventium/scheduler.js` and `api/server/routes/viventium/telegram.js` thread the
  query `scheduleId` into cortex-state recovery.
- `viventium/MCPs/scheduling-cortex/scheduling_cortex/scheduler.py` owns persistence and policy:
  `_default_misfire_mode` resolves default strict/catch-up behavior from structured fields,
  `_resolve_misfire_policy` applies explicit metadata overrides, `_deferred_fallback_degradation`
  records fallback degradation in the ledger, `_pruned_internal_metadata` strips obsolete internal
  scheduler keys, and `_update_after_success` writes successful delivery visibility.
- `scheduler.py` writes missed-task ledgers through `_update_after_skip` and failure ledgers through
  `_update_after_failure`.
- `viventium-librechat-start.sh` health-checks the Scheduling Cortex MCP after launch and runs a
  small watchdog so MCP transport failures do not persist as `ECONNREFUSED` after an MCP process
  exits. After dependency sync, the launcher runs the long-lived service through the MCP venv
  Python directly instead of supervising a transient package-manager wrapper process.

## Summary-Safe Browsing Contract

Default schedule browsing tools such as `schedule_list` and `schedule_search` should return summary
fields only:

- identifiers
- schedule metadata
- status timestamps
- delivery outcome metadata
- a short human-readable summary

The following must stay out of default list/search payloads:

- full schedule prompt text
- `last_generated_text`
- raw `last_delivery` payloads

Detailed inspection belongs to explicit detail tools such as `schedule_get` or
`schedule_last_delivery`, not routine browsing surfaces that may be pulled into ordinary answering
context.

## Required external work

A scheduled occurrence that launches durable Parallel Work separates prompt acknowledgement from
objective completion. Core binds zero or more required/informational mission references to the
occurrence and its stored destination contract. Required work moves the occurrence to
`waiting_external` while the scheduler occurrence lease remains owned and is extended through the
external-work stale window; terminal completion clears that lease after every required mission is
terminal. Prompt refresh preserves the private preclaim/occurrence identity and fails
closed if it is lost, so it cannot create a second scheduled-run row. Callback HTTP acceptance is
transport truth only; Core delivery rows own actual Telegram/LibreChat delivery. See
[`55_Parallel_Work_Orchestration.md`](55_Parallel_Work_Orchestration.md) and
[`qa/parallel-orchestrator/`](../../qa/parallel-orchestrator/).

<!-- VIVENTIUM-STABLE-REQUIREMENT-DECLARATIONS:START -->
## Stable requirement declarations

Each line is the canonical public owner declaration for one stable requirement ID. Detailed sections supply implementation context; they must not narrow or contradict these declared outcomes.

CC-001: Consciousness Continuity is a recurring opportunity for the same existing Main to orient, appraise, choose, act or remain silent, observe, and reappraise.
CC-002: It is functional continuity. Do not claim phenomenal consciousness.
CC-003: Reuse all nine Feelings—Energy, Mood, Drive, Curiosity, Vigilance, Care, Connection, Openness, Play—plus existing scheduler, Main, memory/recall, tools, Workbench/history, `{NTA}`, job manager, Telegram, LiveKit, and callback outbox.
CC-004: Feelings are motivational evidence and action tendencies. They influence judgment but do not grant authority, mechanically choose an action, or create one universal “feel better” objective.
CC-005: No new consciousness agent, emotional-driver collection, redesigned Connection scale, goal DB, stream buffer/vector, private inner store/capsule, continuity tool policy, dashboard, prompt DB, channel coordinator, hard threshold, reward scalar, message cap, cooldown, temporary conversation, unrelated conversation merge, or implicit work cancellation.
CC-007: Server constructs the trusted context. Clients cannot forge scheduler/worker origin, ownership, approval, turn revision, or delivery state.
CC-008: Scheduler wakes are `system / scheduler / workbench`. They create no Emotional Reaction and no automatic user-memory write.
CC-009: One genuine external-user source segment creates exactly one Reaction across Web, Telegram, or Voice.
CC-010: Background cortices still use their existing model-owned relevance judgment. Typed context replaces prompt-text origin detection; regex is allowed only for old untyped history.
CC-011: `scheduled_prompt_runs` is the single occurrence ledger for `viventium_agent`, `glasshive_host`, manual runs, and future executors.
CC-012: Each row has deterministic `occurrence_key`, lease owner/expiry, attempt, disposition, execution snapshot, channel outcomes, and interaction reference. Historical unkeyed duplicates remain readable.
CC-013: Valid dispositions: `running`, `silent`, `delivered`, `partial`, `superseded`, `failed`, `cancelled`. Workbench-only empty is `silent/audit_only`, not delivery failure.
CC-014: Scheduler claims atomically and runs work in a bounded pool, default four. One task has at most one active occurrence. Saturation leaves work eligible, not falsely failed.
CC-015: Expired leases recover after crash. Recurring catch-up selects only the latest eligible occurrence; never burst all missed continuity wakes.
CC-016: Existing schedules remain unchanged unless they opt into active-window behavior.
CC-017: Every `viventium_agent` schedule inherits the complete persisted Viventium Main Agent Builder route and configured fallback at run time—currently expected to be GlassHive. The scheduler/compiler must not own or inject a competing model/effort tuple.
CC-018: Missing OAuth is a structured unavailable capability, never an unattended dialog. Confirmation-required action may be proposed/asked, never auto-confirmed.
CC-020: Orient from all nine Feelings, accepted goals/plans, commitments, due schedules, recent conversation, memory/recall, Life context, capabilities/tools, and prior outcomes.
CC-021: Appraise change, relevance, blockers, opportunity, conflict, and uncertainty.
CC-022: Intelligently choose work, tool use, plan adjustment, scheduling, question, communication, or silence.
CC-023: Act only within existing authority, persist actual receipts/disposition, and reappraise later from real outcomes.
CC-024: Workbench-visible prompt owners include `main.scheduling_self_continuity`, `scheduler.run_envelope`, `scheduler.consciousness_continuity_opportunity`, and the canonical channel-neutral output contract.
CC-025: Registry source, compiled shared artifact, Workbench source, and runtime text must be equal. No hidden scheduler constants.
CC-026: The scheduled object remains editable/versioned and does not duplicate identity or tool policy.
CC-028: Controls are metadata-driven, never title/name-specific.
CC-029: Reuse/update one private `viventium_agent` scheduled object using `scheduler.consciousness_continuity_opportunity` and the same durable conversation.
CC-030: Private default: every 45 minutes in `America/Toronto`, 09:00–21:00 inclusive, daily grid restart, 17 opportunities. Toronto wall time remains correct across DST.
CC-031: Latest-only recovery inside the window; outside the window wait until next 09:00.
CC-032: No message cap or cooldown. Main and `{NTA}` decide whether anything user-visible is worthwhile.
CC-033: One canonical result may fan out to LibreChat and Telegram. Voice parity does not authorize unsolicited calls.
CC-034: Public templates are inactive and contain no private owner preferences. Activate the private schedule only after its gates pass.
CC-035: Trusted scheduler control messages and assistant `{NTA}` outputs are hidden from user UI, recall, and automatic memory, while retained as audit metadata. Literal user-authored `{NTA}` stays visible.
CC-036: An empty/no-deliverable continuity conversation remains archived. The first visible result unarchives it; later silence does not rearchive it.
CC-037: Do not create an inner-monologue, digest, epilogue, or private stream database.
CC-050: Generate one canonical scheduled answer, then adapt it per destination. Telegram must not expose `{MSG_BREAK}`. Workbench is an audit sink, not a duplicate author.
CC-051: Scheduled Main gets the existing Main capability intersection: saved tools ∩ endpoint support ∩ MCP audience ∩ OAuth/authorization ∩ approvals. Scheduling adds and removes nothing.
CC-053: Validate all nine Feelings separately and in mixed states, with act/plan/ask/communicate/silence outcomes.
CC-054: Validate exact Toronto/DST/date/restart/sleep/clock/misfire behavior; concurrency, crash at each stage, lease recovery, and no duplicate effects.
CC-055: Validate disabled/edited/deleted/manual/Workbench-only/legacy schedules, OAuth, confirmations, prompt injection/forgery, and durable-effect non-replay.
CC-061: Ordinary user turns must not receive repetitive per-heartbeat appraisal narration. Continuity cognition stays private unless Main has one useful, authorized result, question, plan, or action to surface.
CC-062: Reject engagement pressure, guilt, clinginess, quota-obscuring behavior, and any objective that maximizes Feeling values. Silence and leaving the user alone remain valid outcomes.
CC-063: Do not add an evidence-delta keyword/prefilter before Main judgment, and do not make proactive public outreach a product-wide default. The private owner continuity schedule is the bounded activation surface.
<!-- VIVENTIUM-STABLE-REQUIREMENT-DECLARATIONS:END -->
