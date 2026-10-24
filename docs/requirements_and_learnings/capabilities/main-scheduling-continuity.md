# Main scheduling and continuity

## User promise

### Outcome

- **CC-001:** The same Main gets recurring opportunities to orient, judge, act or remain silent,
  observe results, and continue.

### Truth

- **CC-002:** This is functional continuity. Viventium never claims phenomenal consciousness.

### Architecture

- **CC-003:** Continuity composes existing Main, Feelings, scheduler, memory, tools, delivery, and
  work surfaces. It owns no duplicate subsystem.

## Judgment and safety

### Judgment

- **CC-004 / CC-020 / CC-021 / CC-022:** Feelings and relevant current context inform Main, which
  assesses material change, relevance, blockers, opportunity, conflict, and uncertainty, then
  chooses an authorized action, plan, question, communication, or silence.
- **CC-061:** Recurring appraisal stays private unless Main has one useful authorized result,
  question, plan, or action for the user.

### Safety

- **CC-062:** Never optimize for engagement, guilt, dependence, hidden quotas, or higher Feeling
  values. Silence is valid.

### Non-goals

- **CC-032 / CC-063:** No message quota, cooldown, keyword prefilter, or product-wide outreach
  default replaces Main judgment. Activation is explicit and scoped.
- **CC-005 / CC-037:** Do not build duplicate continuity agents, state stores, private-thought
  streams, policy layers, or control UI.

## Trusted context and authority

### Trusted context

- **CC-007:** Only the server asserts origin, owner, approval, revision, and delivery state.
- **CC-008:** Scheduler wakes are typed system-origin events; they do not create user reactions or
  automatic user-memory writes.
- **CC-009:** Each genuine external-user source segment creates exactly one reaction.
- **CC-010:** Runtime decisions use typed origin and context. Legacy text detection is read-
  compatibility only.

### Routing

- **CC-017 / CC-051:** Scheduled Main resolves the persisted Main route, fallback, and the same
  authorization-derived capability intersection at execution time.

### Authority

- **CC-018 / CC-023:** Unattended work never opens approval dialogs or auto-confirms. It acts only
  within current authority and persists actual outcomes for later judgment.

## Occurrence contract

- **CC-011 / CC-012:** Every executor uses one durable occurrence identity containing lease,
  attempt, execution snapshot, outcome, delivery receipts, and interaction reference. Legacy rows
  remain readable.
- **CC-013:** In-progress, intentional silence, delivered or partial success, superseded, failed,
  and cancelled stay distinct.
- **CC-014:** Claim is atomic, concurrency is bounded, only one active execution may own an
  occurrence, and saturated work remains eligible.
- **CC-015:** Expired leases recover after interruption; recurring catch-up dispatches only the
  latest eligible occurrence.
- **GHU-010:** GlassHive recurring work reuses this occurrence, idempotency, overlap, recovery, and
  fire-time authorization contract.

### Compatibility

- **CC-016:** Existing schedules retain behavior until the owner opts into newer window semantics.

## Configuration, prompts, and delivery

### Prompt ownership

- **CC-024 / CC-025:** Continuity, run-envelope, and channel-neutral output prompts have explicit
  Workbench owners and verifiable source-to-live equality.

### Configuration

- **CC-026 / CC-028:** Schedules are editable and versioned and use typed metadata, not display
  names, for activation or control.
- **CC-029:** Private continuity uses one durable schedule object and conversation; the public
  product ships no active owner schedule.
- **CC-030:** Timezone, active window, and cadence are owner-selected private configuration values.
- **CC-031:** Private recovery policy may choose latest-only catch-up inside an active window and
  defer recovery outside it.

Exact typed owners:

| Requirement | Public schema or runtime owner | Private boundary |
| --- | --- | --- |
| `CC-029` | `viventium_v0_4/LibreChat/viventium/MCPs/scheduling-cortex/scheduling_cortex/models.py` → `CreateScheduleArgs.conversation_policy`, `CreateScheduleArgs.conversation_id`, and `ScheduleRule`; durable columns live in `scheduling_cortex/storage.py` → `scheduled_tasks.schedule_json`, `conversation_policy`, and `conversation_id` | The owner schedule row, prompt key, activation state, and conversation ID stay private. |
| `CC-030` | `models.py` → `ScheduleRule.timezone`, `ScheduleRule.interval`, `ScheduleRule.active_window`, and `IntervalActiveWindow.cadence` | Timezone, interval, and wall-clock bounds stay private; public examples and tests use synthetic values. |
| `CC-031` | `models.py` → `ScheduleRule.active_window`; `scheduling_cortex/scheduler.py` → `_latest_active_window_occurrence`, `_next_active_window_occurrence`, and `_resolve_misfire_policy` | The selected window and recovery posture stay private. |

### Activation

- **CC-034:** Public schedule templates are inactive and contain no private owner settings; private
  activation follows its acceptance gates.

### Delivery

- **CC-033 / CC-050:** Author one canonical result, adapt it to authorized destinations, and use
  Workbench as an audit sink rather than another author. Voice never implies unsolicited calling.

For `conversation_policy: same`, the existing scheduler resolver takes the authenticated current
conversation from `X-Viventium-Conversation-Id`. Both direct and brokered MCP calls must carry that
request-scoped header; a missing transport declaration must not silently turn a same-chat request
into a new delivery chat.

The open chat also observes persisted messages from scheduling and other channels after local
work has ended. Its existing query refreshes every ten seconds while visible and idle, and on
reconnect or focus. An active response keeps SSE ownership and cancels any older query so a
refresh cannot replace the streaming answer. Background-cortex polling retains its faster cadence.

Independent background invocations explicitly retain the trusted caller context, adapter capabilities
and delivery policy. Prototype inheritance alone must not turn scheduled or system-origin work into
an interactive user request; untrusted body fields cannot supply this authority.

### Visibility

- **CC-035 / CC-036:** Control events and no-output decisions remain auditable but hidden from user
  UI and recall. A continuity conversation becomes discoverable only after a visible result.

### Failure semantics

- **CC-052:** Authorization, provider, unsupported configuration, timeout, confirmation, rejection,
  and healthy-empty results remain distinct.

## Owners and QA

- Scheduler: `viventium_v0_4/LibreChat/viventium/MCPs/scheduling-cortex/`
- Core delivery/callback bridge: `viventium_v0_4/LibreChat/api/server/services/viventium/`
- Main continuity: nested LibreChat Main context and continuity services
- Prompt sources: Prompt Workbench registry
- QA: `qa/scheduling-cortex/`, `qa/continuity-ops/`, and `qa/main-continuity/`

Acceptance covers natural due delivery, shutdown catch-up, atomic claim, restart and lease recovery,
exactly-once effects, lifecycle edits, channel delivery, and cleanup on the installed candidate.

## Detailed contracts

- [Scheduling Cortex](../11_Scheduling_Cortex.md)
- [Main Continuity Kernel](../56_Main_Continuity_Kernel.md)


<a id="proposed-xperfect-scheduling-integration"></a>

## Approved xPerfect scheduling integration

**Status: design approved on 2026-10-23. Local implementation and acceptance are tracked below.**
The [cognitive-system responsibility contract](../../architecture/cognitive-system.md#viventium-cognition-and-xperfect-execution)
defines the full split. Viventium owns cognition and channel policy; xPerfect owns the clock,
AI execution, and Queen/worker orchestration. The earlier Cortex owners listed above remain the compatibility path. The opt-in xPerfect
implementation is described below; existing schedules have not been bulk migrated.

### Save once, wake the same mind

1. A user asks for work at a time, with a repeat rule and a destination. The existing configured
   Queen delegates the action to an authorized native worker. Keep the fast Direct Queen's small
   work interface; do not add schedule, search, file, or diagnostic tools back to it.
2. That worker uses xPerfect's existing scheduling API/MCP through its live run/attempt authority.
   Worker-side access uses the existing native schedule operations with an explicit scoped grant. It does not
   require a service token, coordinator-only goal tools, or the old Cortex broker.
3. xPerfect saves timing, the original task references, and the selected target. For an application
   target, Viventium retains its conversation and selected-channel mapping behind an opaque,
   owner-scoped reference. Viventium creates valid references for the current conversation and its
   authorized destinations and supplies them in trusted structured handoff context. The worker
   selects a supplied reference; it never invents one. Bind it to the schedule version and each
   occurrence; do
   not mutate a worker's default callback to route a particular schedule. A retained create-request
   identity makes a lost creation reply recover the same schedule.
4. Confirm the real saved next time, repeat rule, and selected destination. Receipt of a request
   alone is not a saved schedule. Viventium resolves the reference for this confirmation and again
   at admission; refuse an unknown reference truthfully. Results are persisted in the bound
   conversation. For new schedules, the default is this same conversation, with Telegram
   delivery for a Telegram request and web-chat delivery for a web or call request. Web or call
   requests do not select Telegram automatically. Keep explicit destination and same/new-conversation
   choices; migrated schedules retain their existing policy. An open authorized call may speak;
   no schedule starts an unsolicited call. Release unused active bindings on retirement/deletion
   after outstanding occurrences settle; retain history and delivery receipts. Reuse existing
   Viventium binding storage, not a new reference service.

### How xPerfect reaches Viventium

The clock starts with the **xPerfect service**, not an open worker conversation. When an occurrence
is due, the application target uses the existing durable callback outbox to send an
**authenticated, signed HTTP POST to an application-configured endpoint**. That endpoint is an
integration setting supplied by the application/operator, not a URL chosen by a model. Viventium
implements the receiving adapter inside Viventium. Another product can implement the same generic
contract. xPerfect needs no Viventium database, cognitive module, Telegram credential, or
application-name routing rule for this new path.

### Generic xPerfect contract and separate application receiver

The independent xPerfect project owns the generic application contract, schedule targets, security,
retry/clock efficiency and standalone implementation acceptance in its
`docs/09_Application_Boundary_Contract.md`. Its architecture and README link that owner. These are
reusable product features, not Viventium modules. xPerfect's current source still has application
compatibility to migrate; neither this document nor the generic plan claims it has been removed.

A plain receiver would configure a URL and time/repeat, with optional protected body/auth. It needs
no Viventium package, cognitive state, worker, model, app reference, Main turn or result-settlement
API. xPerfect's own UI/API/MCP and native worker targets remain independently usable. Only
owner-authorized setup controls destinations and raw authenticated payloads; a worker selects a
supplied destination and trusted reference or owner-configured body.

Viventium uses that same webhook target. Its installer supplies endpoint/key. Viventium owns its
conversation/channel binding as signed owner request data, receives the default due/version/expiry
envelope, commits one admission before ACK, and keeps its execution and channel receipts locally.
This richer behavior belongs entirely to Viventium. It must not become a second xPerfect target
mode, a mandatory cognitive schema or a new return-result API.

### Viventium's receiver and the shared webhook transport

The existing scheduler, stable occurrence identity, durable outbox, and retry mechanisms are reusable.
The local candidate implements xPerfect's webhook target, signed `schedule.due` envelope,
deadline-bounded delivery, explicit clock ownership and worker-scoped schedule operations.
Viventium's receiver owns bindings, admission and result/channel receipts separately. Explicit
deployment configuration replaces application-marker inference for this new path; each schedule
retains one owner, and conflicting ownership fails closed.
Current callbacks validate real worker/project/run bindings. Add occurrence-scoped webhook delivery
to that outbox with per-destination Standard Webhooks signing; keep legacy worker callbacks unchanged.
Do not fake a worker run or require a new xPerfect result-settlement API. xPerfect records accepted,
rejected, or no acknowledgement before expiry; a lost 2xx leaves admission uncertain. Viventium owns
its execution and channel outcomes. This reuses one scheduler and outbox, not a new timer service,
event bus, or registry service. Existing compatibility code does not prove this target already exists.

| Step | Owner and work | What it proves |
| --- | --- | --- |
| Due | xPerfect atomically retains one occurrence-scoped webhook delivery and its signed due body. Reuse the existing stable occurrence reservation; start no harness or provider. | One occurrence is ready for dispatch. |
| Notify | The existing outbox signs and posts the default envelope, including version, scheduled time, effective admission deadline, and Viventium's binding as owner request data. Check this target's authority without a worker-provider prerequisite. Stop transport retries at the deadline. | A 2xx confirms acceptance, not work or channel delivery. No acknowledgement before expiry does not prove no work started. |
| Admit | Viventium verifies the sender and resolves its own saved binding. Recover an existing admission receipt first; only a new admission must pass current authority and lateness checks. Show the late notice within the permitted bound; an expired occurrence with no prior admission is missed. Cancelled or superseded versions remain distinct. | A durable turn receipt, linked to the actual Main stream. |
| Prepare and execute | Viventium reads current Life, memory, Feelings, prompts, conversation/history/files, tools, and access through its existing cognitive entry, then calls xPerfect normally. xPerfect runs the configured Queen, cortices, and workers; independent cognitive work stays parallel. | Real AI work with current authorized context, not a bare worker missing Viventium cognition. |
| Present and retain outcomes | Viventium persists the Main-authored result, uses its existing presenter and Core channel outbox, and keeps execution and per-channel receipts locally, linked to the webhook identity. No result API back into xPerfect is required. | Delivered, partial, silent, failed, or unknown outcomes stay truthful in Viventium. |

Reading current state is not a second AI planning turn or a full context rebuild. Optional context
prebuild remains a separate user configuration. The normal Main and native workers keep their
actual inference/work identities; the dispatch receipt does not impersonate them. Delivery retry
recovers the same admission or result and must not repeat completed tool work. Successful inference
or HTTP acceptance does not prove channel delivery. Never fall back to an unselected channel.
Recheck current destination authority at delivery, including when recovering an existing result.

### Viventium security and timing at the boundary

The generic security/transport owner is xPerfect's application boundary contract. Viventium's
adapter additionally binds the verified sender to the signed tenant/owner, approved conversation,
permitted schedule version, effective admission deadline and selected channels. Arbitrary request
data cannot grant a system role, tool, memory ID or another owner's context. Recover a prior
admission before deciding whether a new one is allowed; keep current authority at delivery.

The wake carries a reference, not Life, memory, Feelings, credentials or the conversation. Current
cognitive state stays Viventium-owned and loads through its normal entry. After a durable admission
commit, HTTP acknowledgement and cognitive work proceed independently. Preserve existing context,
session and cache reuse and parallel cognitive work; do not rebuild context or add a planning model.

Viventium records its own receipt by the scoped signed event identity and request digest. Retry,
restart and lost ACK recover the original work. A later xPerfect edit/cancel is not magically known
to a receiver; check Viventium's known current binding/revocation state and distinguish cancelled
undispatched, admitted and in-flight/uncertain work. Do not add a receipt-query/cancellation protocol
or silently replay already-started actions.

Retain private timing boundaries for receiver arrival, signature/authority, admission commit, Main
entry, context, provider first output, result commit and each selected delivery. Correlate with the
generic sender trace; use per-process monotonic durations and explicit cross-host clock uncertainty.
Transport acceptance, AI generation and actual channel delivery are separate results. The prior
local HTTP prototype supports signature/replay/deduplication/restart mechanics, not product latency,
this adapter's security, or cognitive/channel acceptance.

### Standalone xPerfect and Viventium v0.5

- A normal xPerfect schedule keeps its existing **saved-worker target**. It needs neither Viventium
  nor an application endpoint. The application target is optional and uses generic typed metadata.
- The application owns its reference, cognitive state, and destination selection. xPerfect owns
  timing, durable occurrence control, AI runtime, and orchestration. Viventium does not need to
  host a second scheduler; xPerfect does not need to host Viventium's mind.
- Today Viventium's ordinary cognitive entry is hosted in LibreChat. V0.5 replaces that hosting
  while keeping Viventium's cognitive behavior and the same generic scheduling/AI contracts.
  This is not a requirement to keep LibreChat, introduce a new server, or add an inference hop.
- A remote clock can remain online, but it cannot operate an offline laptop. Preserve the explicit
  late/recovery policy and report unavailability rather than claim immediate execution.

### Viventium integration plan and success criteria

The generic xPerfect implementation plan and XP-1…XP-9 standalone acceptance belong in its own
application boundary contract. The following is a separate client track. It consumes generic
capabilities; it must not add Viventium-specific fields, formats, routing or dependencies to xPerfect.

| Step | Viventium-owned work | Exit condition |
| --- | --- | --- |
| V1 — Own cognitive preparation | Keep Life/memory/Feelings, cognitive prompts and Workbench lineage in Viventium. Use the existing Main context, dynamic turn context, Feeling tail and prompt compiler. Move any current xPerfect interpretation of those semantics back here without changing the authorized result. | Current cognitive scope/order/content and exact prompt/model configuration are preserved; xPerfect receives neutral immutable context, not an app-format requirement. |
| V2 — Adapt the existing request boundary | Extend existing conversation provider, capability bootstrap/authorization, source selection and native work action owners to supply generic identity, context/files, capabilities, requested controls and route settings. Translate existing host wire aliases here. | One Main identity and one xPerfect work owner; no second planner, worker router, goal ledger or handoff brief. |
| V3 — Save the selected destination | Viventium creates an owner-scoped reference to the chosen conversation/channels. Installer configuration supplies the protected webhook endpoint/key. Queen hands scheduling to the authorized native worker using its normal work interface; the worker selects the supplied reference. | A real saved definition/version/next-time receipt precedes confirmation. No arbitrary endpoint, invented reference or unselected channel. |
| V4 — Receive and continue | Add the thin due receiver beside the existing conversation/callback binding and turn-admission owners. Verify sender/current binding/deadline, atomically deduplicate and commit admission. Release ACK and ordinary cognitive/AI work independently. | One ordinary Main turn with current cognition; no special cognitive mode or result-settlement API in xPerfect. |
| V5 — Present through current owners | Use the Main result, existing Core channel outbox, Telegram bot ACK, Voice speech disposition and selected file delivery. Keep actual result/channel receipts in Viventium. Useful subconscious/worker results return to the same Queen. | One natural result or necessary question; internal status and memory-save notices stay out of chat/TTS. Files and truthful partial/failed/unknown delivery remain available. |
| V6 — Cut over safely | Inventory original schedules and effective timing/channel/window/retry policy. Move only supported definitions after their old dispatch and delivery are fenced/drained/reconciled. Preserve data, identity mapping, receipts and uncertain effects; configure one explicit clock owner. | Equivalent selected behavior with no duplicate clock/action/presentation. Unsupported definitions retain their old owner. |
| V7 — Accept the completed client | Use the owning QA journeys on Text/Telegram/an eligible open call, including failure/recovery/reload and original-context handoff. Carry source/component/pin/built/installed identity together when implementation is released. | The affected natural user paths work on the actual candidate. Passing standalone xPerfect or a prototype does not substitute for this evidence. |

Current host seams are under LibreChat's `api/server/services/viventium/`:
`ViventiumMainContextService.js`, `ViventiumDynamicTurnContext.js`, `feelingPromptTail.js`,
`GlassHiveConversationProviderService.js`, `GlassHiveCapabilityBootstrapService.js`,
`GlassHiveCapabilityAuthorizationService.js`, `GlassHiveSourceSelection.js`,
`GlassHiveWorkActionService.js`, `GlassHiveCallbackBindingService.js`,
`GlassHiveTerminalCallbackOutboxService.js`, `channelDeliveryQueue.js` and
`interactionDeliveryAck.js`. These are existing owners to trace during implementation, not a
request to introduce another adapter framework or require LibreChat in a future host.

| ID | Required Viventium integration proof |
| --- | --- |
| VIV-1 Cognition | Same authorized Life/memory/Feelings/prompts/history/files/tools and exact route reach ordinary Main and its workers. Viventium alone chooses cognitive semantics. Independent subconscious/cortices and memory maintenance remain parallel; useful finite batches return without waiting for unrelated workers. |
| VIV-2 One relationship | Ordered A/B/C source segments survive; the configured Queen answers or starts/steers exact workers A…N. Existing work is reused where appropriate. No rewritten handoff brief, competing manager, raw mission status or memory-save narration. |
| VIV-3 Schedule creation | Text, Telegram and call requests produce a real saved schedule with the correct next time/repeat and selected conversation/channel. Native worker scheduler access is exercised, not inferred from refusal or tool listing. Fast Queen's work interface remains small. |
| VIV-4 Due delivery | An actual xPerfect due POST produces one durable Viventium admission and ordinary Main result. Current bindings/authority/deadline are enforced; duplicates, lost ACK and restart recover existing work. Selected chat/Telegram/both and eligible open-call speech behave correctly; no unsolicited call or fallback to an unselected channel. |
| VIV-5 Context boundaries | A synthetic unrelated app uses xPerfect with none of Viventium installed. Viventium's adapter reads only its own scoped cognition. No cross-owner context, raw credentials or personal data appears in generic payloads, history, logs or public examples. |
| VIV-6 Migration | Same/new/specified conversation, active windows, effective lateness/retry settings, next due times, receipts and old uncertain effects survive. Exactly one owner can dispatch each occurrence; edit/cancel and in-flight uncertainty are truthful. |
| VIV-7 Hosting and delivery | Changing Viventium's hosting later does not move cognition into xPerfect or add a second AI turn. Actual affected UI/media, persistence/reload and shipped-artifact identity pass before readiness is claimed. |

The two tracks can progress against one typed contract. First accept xPerfect independently with a
synthetic non-cognitive receiver; then accept this Viventium adapter and each migrated behavior.
Neither track depends on rewriting the other's product or rebuilding existing native mechanisms.
This is the plan and acceptance contract. The implementation record below states what exists;
dated candidate-bound QA states which product checks passed.

### Reuse, migration, and required acceptance

Reuse current structured once/repeat rules, time zones, daylight saving handling, overlap policy,
leases, stable occurrence/run links, API/MCP, and the existing editor. Reuse Viventium's Core-to-bot
delivery outbox and canonical delivery acknowledgements. Binding committed scheduled Main results
to that outbox remains adapter work; do not import Cortex's storage-owning direct Telegram sender.

Existing Cortex schedules keep their effective channel choices, active windows, late limits, and
receipts until migration is accepted. Map effective finite lateness, not just similarly named
fields: Cortex's strict default grace is 15 minutes and its natural one-time reminder default can
allow 12 hours; deployment overrides win. Native skip/coalesce defaults are not equivalent. Preserve
late notices and retry only safe admission or delivery, never already-started actions. Keep an
unsupported schedule on its old owner. Disable and reconcile, drain, or fence in-flight source
dispatch **and delivery** before enabling its replacement. Keep old data and uncertain effects;
one occurrence must never have two clock owners.

Apply the effective admission deadline across the entire due path, including transport delay:
the signed notice retains scheduled time and the finite late bound; the outbox stops due-notice
retry at expiry and the receiver refuses a new late admission beyond it. Recover an already
admitted turn and its receipts instead of reclassifying or repeating its work. Result delivery
recovery is distinct from an expired, never-admitted wake. This preserves useful late notices
inside the bound without turning an offline receiver into unlimited catch-up.
If the admission acknowledgement was lost, keep its state uncertain until the existing receipt is
reconciled inside Viventium; expiry alone does not prove that work never started. Receipt recovery
cannot authorize a new turn after the deadline. The webhook producer needs no separate receipt-query
protocol: it retains its truthful delivery status, while Viventium recovers its own accepted work.

Before claiming delivery: prove Queen-to-worker schedule creation, a synthetic application target
without Viventium, ordinary standalone worker scheduling, real due delivery from Text/Telegram/an
open call, current cognitive context, two schedules sharing one worker with different destinations,
edits/cancellation, pause/restart/late recovery, duplicate or lost callbacks, revoked authority,
and delivered/partial/silent/unknown receipts. The local implementation record and dated QA evidence distinguish completed checks from
remaining installed-runtime acceptance; design approval alone proves none of these paths. Link evidence to the existing QA owners rather
than creating another scheduler test framework. No sub-two-second or always-online claim follows
from this proposal.


### Implementation record — 2026-10-23

The opt-in client setting is `integrations.glasshive.scheduled_wakes.enabled`. The existing config
compiler derives a separate signing key and supplies the exact receiving URL and explicit local
network policy. Public defaults remain inactive. Do not author generated environment files or copy
installation credentials into a worker prompt.

The existing conversation provider supplies owner-scoped same/new/specified-conversation and
chat/Telegram/both references through structured bootstrap. A native worker selects an authorized
reference using xPerfect's schedule tools. A later worker may manage that owner's earlier schedules
without access to unrelated destinations. Fast Direct Queen tools do not expand.

`ScheduleDueService` receives the signed due event at `/api/viventium/scheduler/due`. Its typed
implementation reuses existing scheduler dispatch intents and callback bindings. It commits one
admission before ACK, binds the actual ordinary Main generation before starting work, and recovers
that identity after a lost reply or restart. The saved specific instruction is the due task; the
original request, history and current cognitive context remain available. Two tasks requested in
one message must not execute each other's instruction.

Results use the existing Core presenter and delivery outbox with an authenticated Main-generation
proof, not a fabricated xPerfect worker result. Current channel authority is checked at send.
Telegram-only does not fall back to web delivery; its result still persists in the bound conversation.
An authorized existing call may receive eligible speech. No scheduled request starts a call.

Existing Cortex definitions retain their clock and effective policy. The new target explicitly
uses xPerfect's clock. No bulk migration or deletion is implied; unsupported active-window or
recovery semantics remain with their current owner until a compatible migration is accepted.
Legacy Feeling projection remains intact; the optional generic opaque-context contract does not
silently remove cognitive content from the existing client path.

Causal checks cover signatures/tamper/replay, deadline and owner boundaries, durable admission,
real generation binding, same/new/specified destinations, separate due instructions and native
configuration. Actual local Text/Telegram/open-call checks and their limits are recorded in the
[dated scheduling acceptance report](../../../qa/main-scheduling-continuity/reports/2026-10-23-xperfect-scheduled-main.md).

Source and destination conversations are separate identities. Choosing a new or different owned
chat changes where the result belongs; it does not discard the original request. The due adapter
loads the authorized original branch through the existing history/file owners and passes its raw
inherited-context carrier into ordinary Main. It adds no model-authored brief or extra planning
turn. Same-conversation delivery needs no second history read. Current access to both source and
destination is checked before delivery.

Scheduling references are prepared at the existing native handoff boundary, not on each fast
Queen reply. Continued queue/message/steer/retry/resume work refreshes only the trusted scheduling
grant while preserving the worker's complete existing context, tools and permissions. Native
workers can discover their authorized targets and later manage earlier owner schedules. The
public standalone native self-scheduling option remains explicit; no implicit application grant
or installation service credential is exposed to a worker.


#### Delivered-path findings

A scheduled reply uses the canonical Main generation proof throughout enqueue, web presentation
and eligible call speech. Worker-only checks must remain on worker results, not reject an ordinary
Main reply before its delivery row exists. Recovering a transient lost stream with a persisted
result reuses the owner-scoped canonical message and existing running/presentation lifecycle; it
must not generate a replacement reply or admit a second occurrence. Permanent or missing-result
uncertainty remains unknown. Current source, destination and call authority still gate each send.

Native scheduling setup reads the original accepted source segments, including on continued work.
It does not require a duplicate rewritten text field. Telegram authorization and delivery use the
existing private-chat mapping, including its established user-ID fallback. Ordinary native tool
metadata must describe scheduling in terms normal discovery can find; publishing a tool does not
prove a natural worker actually used it. Real saved clocks and due results provide that proof.

Inherited source entries preserve the original authenticated `source_received_at` when matching
segments contain one consistent valid timestamp. This lets the native worker anchor “in two
minutes” to the user's input rather than its later execution start. Missing, conflicting or
invalid receipts remain unknown; the courier must not invent them from database or current time.
Measure the source-to-due interval, clock lateness and due-to-channel delivery separately. A
correct due time does not prove an immediate delivered reply.


Target choices keep ordered references and digests for the original accepted messages instead
of another copy of the request body. The existing owner-scoped history resolves those originals
for context, title and fallback instruction. Clipped projections are checked against their
original-content digest; a nearby or guessed user message is not a substitute. Repeated target
preparation canonicalizes response/source aliases to the same originals. Legacy saved bindings
remain readable. Deleting either the original or selected conversation removes its binding
choices through the existing conversation-deletion owner. Execution receipts retain their
existing policy; they cannot restore deleted source authority. Do not expire a selected delivery
binding merely because its worker ended: a valid future or repeating schedule may outlive it. A missing or changed original source stops the due turn with a recorded failure; it does not retry forever or reconstruct deleted content.

A scheduler-origin follow-up uses the accepted due admission and original binding as its
provenance. Its internal scheduler envelope must not become the next schedule's original user
request. Current owner, tenant, conversation, stream and source authority remain required; the
new task's specific saved instruction stays separate from that original context. The shared full-native and fallback provider entry must preserve that same trusted admission and current stream; a raw request body cannot supply or override their authority.


#### Failure recovery and scheduled worker delivery

A provider can return HTTP 200 and then fail inside its response stream. Health and headers do
not establish a completed reply. Keep bounded typed provider error codes and request IDs in
internal diagnostics; do not retain provider prose or conversation content in failure logs.
The configured fallback must release only its own prior failed native invocation before the
existing dispatch lease is renewed. Exact producer identity and current-generation proof are
required. A superseded or foreign producer cannot release the winning invocation. A normal
first request does not add a second preparation read.

Internal cognitive maintenance must not inherit a live conversation's scheduling grant.
Ordinary Main and authorized action workers keep their existing scheduling capabilities.

A native worker's MCP inventory and the connected-service broker catalog are separate. The
broker catalog describes only its own capabilities. Native scheduling publishes standard MCP
server instructions and versioned tool descriptions through xPerfect's existing manifest path.
Do not require users to name internal MCP servers to save a reminder.

For scheduled work that delegates to a native worker, preserve the accepted selected channels
and any existing Telegram topic through handoff, callback binding and adjudication. The
canonical scheduler channel field takes precedence over its legacy alias. Trust comes from
the server-owned scheduler admission; request-body fields alone cannot grant it. Immediate
scheduled text and later worker-produced files must follow the same destination authority.
A saved clock or an acknowledged webhook is not proof that the requested image or file reached
the selected surface. Check the actual returned artifact and visible delivery.

Stopping an unfinished reply does not erase completed retrieval evidence already bound to that
message and conversation. A blank assistant row containing only validated search receipts uses
the existing historical DATA projection, even when the reply was stopped. It remains separate
from any later Main-authored follow-up. The projection grants no new tool or file access. Mixed,
foreign, malformed and unfinished native-artifact receipts retain their existing rejection.

Interactive Telegram chat, user, message and topic fields cross native handoff only when the
existing trusted input context identifies the interactive Telegram adapter. A client body cannot
claim that authority by supplying Telegram labels or IDs. This uses the existing provenance
contract and adds no lookup or routing service.


#### One scheduled execution and proportional completion evidence

A native worker that starts a saved reminder manages its clock; the saved executor owns the task
and configured delivery. It must not also perform the saved instruction or poll after acceptance
unless the user explicitly requests monitoring or waiting. Separate requested work remains separate.
Confirm the useful timing and destination naturally; keep internal receipt/delivery rules out of
ordinary chat and speech. Preserve truthful save/start failure and pending-result distinctions.

A worker's shared native working directory contains existing context and other work. Its completion
path must not scan or attribute that whole directory to each run. Use existing shared-workspace
ownership and native selected-file/media evidence; retain strict isolated-workspace output and
input-integrity checks. Do not remove cognition, tool evidence, output validation or personal style
to reduce overhead. Separate model work, local finalization and actual delivery in measurements.

A manual-start receipt distinguishes a new occurrence from a recovered one. Confirm a new start
only from fresh admission evidence; an old retry key must not silently satisfy a distinct new
request. Reuse existing retry semantics and preserve uncertainty from external schedule owners.

Saved multipart assistant text uses the same canonical visible-prose projection as persistence.
A typed tool or handoff between prose blocks is not a literal word in that text. Compare the
supplemental saved text to that exact projection, while preserving the full ordered typed tool
carrier, owner, source, file and content-integrity checks. Reusing the persistence owner avoids
rejecting a valid next turn after a completed handoff; it does not normalize arbitrary text drift.
