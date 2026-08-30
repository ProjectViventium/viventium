# Parallel Work: One Always-Available Main, Many Durable Missions

Status: implementation in progress behind a dark availability flag. Do not expose or default on
until every release gate in this document and `qa/parallel-orchestrator/cases.md` passes on the installed
runtime.

Last revised: 2026-08-24.

This document is the product and implementation source of truth for Viventium Parallel Work. It
preserves the existing logical-turn, continuity, callback, scheduler, and GlassHive contracts while
adding bounded durable mission concurrency and provider-native worker teams.

## Product outcome

Viventium Main is one continuous user-facing consciousness that stays available while substantial,
independently completable work continues in the background. Main can answer quick follow-ups,
accept another objective, inspect every mission, and message, steer, pause, resume, stop, retry, or
dismiss exact work without becoming multiple competing authors.

The architecture has two levels and one durable control plane:

1. Main decides, within its existing inference, whether to answer directly, continue or control an
   exact existing mission from the compact roster, create a durable mission for a new independent
   objective, or ask one focused disambiguating question. Existing work is addressed by opaque
   `workRef` through the canonical action interface; Main does not select raw workers, projects, or
   provider sessions. Runtime code must not classify intent with keywords, prompt matching, or fixed
   size thresholds.
2. Each independent durable objective is one GlassHive mission root. GlassHive is authoritative for
   identity, ownership, atomic admission, state, lifecycle, restart recovery, controls, callback
   transport, and cross-provider visibility.
3. A mission root may use Codex or Claude native children, nesting, messaging, and provider-native
   session control. Native state is projected into GlassHive; it is not a competing public registry,
   scheduler, mailbox, or conversational persona.
4. LibreChat keeps only the account preference, trusted origin/delivery relation, compact roster
   projection, and surface delivery ledger needed to support Main and the user interfaces.

Do not introduce a second supervisor, `run_units` planner, provider-specific public API, LangGraph or
Temporal migration, or top-level Claude/Codex registry. Reuse the installed harness primitives under
the GlassHive root.

## Locked Queen Bee and Worker Bee user experience

This product-language contract is normative. **Queen Bee** means Viventium Main. **Worker Bee**
means one durable GlassHive mission root. These names do not add another runtime entity, manager,
memory store, tool plane, or orchestration system. Technical detail in this document may strengthen
this contract but must not weaken it.

### 1. Roles

- **Queen Bee:** one Viventium Main. It is the only manager and speaking personality.
- **Worker Bee:** one saved background mission. It can use internal Codex or Claude helpers.
- Workers never impersonate Queen or receive unrelated sibling work/private chat.

### 2. Queen behavior

- Quick work stays with Queen.
- Independent, substantial work becomes Worker Bees.
- Queen remains responsive while Bees run.
- Queen always sees and controls all active Bees.
- Results return through Queen's voice.

### 3. Rapid A/B/C flow

1. You send large A, large B, then quick C.
2. Queen creates separate Bees for A and B, once each.
3. Queen answers C promptly.
4. A and B run in parallel when capacity exists.
5. Each result and artifact arrives once.
6. Restarting or continuing the chat loses nothing.

### 4. Interrupting Queen

If you send more input before Queen finishes:

- The unfinished reply is revised or removed.
- Queen sends one current reply covering every message.
- You must not receive two competing replies.
- Existing Bees continue unchanged.

### 5. Controlling a Worker Bee

| Action | Expected behavior |
| --- | --- |
| **Queue** | Add later work without interrupting. |
| **Message** | Add guidance without changing the mission. |
| **Steer** | Interrupt that Bee and replace its direction inside the same mission. |
| **Pause / Resume** | Hold or continue the same mission. |
| **Stop** | Cancel only that Bee. Show `Stopping` until confirmed. |
| **Retry** | Continue failed work in the same workspace. |
| **Dismiss** | Hide a finished card without deleting history. |

Steering A must never affect B. If the target is unclear, Queen asks which Bee.

### 6. Truthful states

- `Queued` never means `Running`.
- Work is accepted only after capacity is reserved.
- Capacity, quota, missing login, provider failure, and unavailable status are shown separately.
- No fake acceptance, completion, future-delivery promise, or silent loss.
- Provider fallback must keep the same Bee controls and abilities.

### 7. Surfaces

- **Parallel work** is one account-wide setting for Telegram, Web, and Voice.
- Turning it off stops new automatic Bees. Existing Bees remain visible and controllable.
- **Active Work** belongs in the main Control Panel, not Connected Accounts.

### 8. Required proof journey

Two HTML Bees run with overlapping times; Queen answers a quick question; a late message revises
Queen's reply once; only HTML A is steered; B stays unchanged; both files arrive once and open in
separate browser windows.

### 9. Full capability and reliability parity

- This contract inherits `01_Key_Principles.md` and every owning feature contract. Moving work from
  Queen to a Worker Bee must not reduce the required Quality + Performance outcome, authority,
  context, supported inputs, tools, or result types for the same goal.
- Each Worker Bee receives its exact task and constraints plus the mission-relevant subset of every
  owner-authorized Viventium ability that Queen could lawfully use for that goal. This includes,
  without forming a closed list, saved memory and recall, project instructions, links and sources,
  connected accounts, approvals, host and broker tools, browser/computer access when authorized,
  and file/media understanding and creation.
- Inputs preserve the owning feature contract: text or speech, links, uploads, grouped attachments,
  documents, images, audio, video, and prior artifacts keep their exact identity, bytes, order, and
  owner scope wherever that distinction matters.
- Outputs preserve the owning feature contract: text, citations and source detail, structured
  results, and generated or edited files/media/artifacts return once through Queen. They remain
  visible and downloadable from the origin surface and Active Work. If a surface cannot render an
  output directly, it provides a stable linked-chat or Active Work handoff instead of dropping it.
- In a normal Voice Call, an explicit authorized spoken request can launch and control Bees while
  Queen keeps talking. Queen speaks concise truthful status or completion once; files are delivered
  through the linked chat or Active Work, and ending the call does not cancel accepted work. Wing
  keeps its existing speaker-trust and explicit-engagement limits. Listen-Only never launches or
  controls work. Viventium never places an unsolicited result call.
- The same scoped capability envelope remains reliable through provider fallback, Queue, Message,
  Steer, Pause/Resume, Stop, Retry, continuation, delivery, and restart while authority is unchanged.
  A fallback that cannot preserve a required capability is a visible blocked/unavailable state, not
  a silent downgrade.
- A missing, expired, blocked, or unavailable memory, file, tool, approval, provider, delivery path,
  or account becomes an explicit recoverable state. A Bee never silently bypasses it, invents access,
  loses the task, or claims an artifact was delivered when it was not.
- Unrelated private chat, sibling work, credentials, and extra authority never cross into a Bee.
- Every new Viventium capability is automatically in scope for a Worker Bee parity decision and an
  applicable Telegram, Web, Voice, input, output, fallback, control, and restart QA mapping before
  Parallel Work can be release-ready.
- Reuse the shared context snapshot, owner-scoped retrieval, upload/file pipeline, capability broker,
  artifact/delivery ledger, and durable mission lifecycle. Do not add a second memory, tool, file,
  delivery, or orchestration system.

**Current status:** this remains **PRE-GATE / NOT READY**.

## 2026-08-22 escaped-interaction corrective inventory

This inventory is locked until the original installed Telegram sequence and its degraded branches
pass. `SOURCE DONE` means only that focused source tests pass; it is not user-path or release proof.

| # | Locked invariant and owning fix | Required acceptance | Current state |
|---:|---|---|---|
| 1 | Parallel Work stays dark. The release evaluator fails closed for every open QA gate; an explicit local override is always labelled **PRE-GATE / NOT READY**. Dark or unready Parallel Work never disables Main. | `REL-UC-004`, full release evaluator, installed Telegram restart | SOURCE DONE; installed default restoration and release QA open |
| 2 | Main uses one request-pinned Feelings capsule. The winning native provider records exact hash, count, placement, and semantic receipt. Keep the host plug-in denylist; do not mount private state or add a Feelings MCP. | `EMO-UC-047` | SOURCE DONE; installed Telegram receipt proof open |
| 3 | Every eligible direct worker receives that same pinned capsule exactly once through the shared snapshot resolver; scope-off workers receive none. | `EMO-UC-047`, `PWK-UC-014` | SOURCE DONE; installed two-worker parity proof open |
| 4 | Main receives typed, model-visible current-turn facts for surface, route, selected model, fallback model, and effective effort. It never infers these from tool names or prose. | `PWK-UC-014` | SOURCE DONE; installed wording proof open |
| 5 | Telegram source order wins over delayed host ingestion. A newer source message observed before presentation commit revises the open logical turn; stale preview/final output is removed or suppressed, leaving one current reply. | `TR-026`, `PWK-UC-014` | SOURCE DONE; exact 280 ms installed race open |
| 6 | Durable provider health skips a structurally identified route during a proven quota/rate-limit cooldown and honors authoritative retry time. Main stays available. `presentation_committed_at` is the delivery clock; Mongo `updatedAt` is not. | `PWK-UC-009`, `PWK-UC-016` | SOURCE DONE; load/cooldown installed proof open |
| 7 | A completed cortex insight enters one owner-scoped delivery ledger and becomes `sent` or typed `dropped`; claim, retry, replay, and follow-up creation survive restart. | `EMO-055`, `EMO-UC-048` | SOURCE DONE; installed completed-graph delivery proof open |
| 8 | Capacity is measured and atomically reserved before acceptance/admission. A blocked result reports available, required, shortage, reservation, and next retry; no work is called launchable when it is not. | `PWK-UC-016` | SOURCE DONE; installed reservation/race proof open |
| 9 | Durable lifecycle is `queued -> claimed -> admitted -> running`; `running` requires the matching open attempt, a live unexpired exact lease, and that attempt's immutable `runtime_invoked_at`. Only the live dispatch observer may create that boundary; restart cannot synthesize it. The first `started_at` is permanent across retries. | `PWK-UC-014`–`016` | SOURCE DONE; installed restart and overlap proof open |
| 10 | Capacity-blocked work exposes queue age, blocker, next retry, and timeout; bounded refreshes reach the user and one terminal callback closes the work. No unverified future-delivery promise is allowed. | `PWK-UC-014`–`017` | SOURCE DONE; installed callback/restart proof open |
| 11 | Route choice consumes durable provider health. Worker input contains the exact task, explicit constraints, and required capabilities only—never raw recent private chat or host identifiers. Any configured fallback is explicit and audited. | `PWK-UC-014`, `PWK-UC-016`, `PWK-UC-018` | SOURCE DONE; installed routing/privacy proof open |
| 12 | One owner-scoped, redacted, immutable origin trace correlates source revision, prompt layers, provider authorization preflight, runtime invocation, actual provider forwarding, work, lifecycle attempt, capacity, callback delivery, and artifact. New work pins producer trace V2; legacy V1 history remains readable but cannot prove current completion or release. Unknown, contradictory, partial-page, overflow, or critical storage telemetry fails operational readiness. A typed warning remains visible and blocks public release, but labelled local PRE-GATE execution may continue only through the durable per-mission capacity reservation. | `REL-UC-004`, `PWK-UC-014`–`018` | SOURCE DONE; installed trace and hostile-input proof open |

`HARD-022` applies to every lifecycle control, not only Feeling edits. A stale, invalid, or already
terminal action returns definitive typed conflict truth, including HTTP `409` where the API uses
HTTP. An optimistic acknowledgement, generic success, or later silent correction is forbidden.
`PWK-075` / `PWK-UC-043` owns the cross-component acceptance journey.

Completion requires the chain `requirement -> natural use case -> expected result -> installed
Telegram/browser evidence -> logs/database/artifact trace -> PASS`. Unit tests, source inspection,
model review, and an old successful run cannot replace a missing installed step.

## Verified evidence chronology — 2026-08-15 through 2026-08-24

Parallel Work remains dark and is not release-ready. The current evidence proves two narrow Web
branches without widening that claim:

- A post-fix exact-artifact mission auto-admitted at 13:33:30 and completed at 13:34:15. Its lease
  released as `runtime_returned`. `acceptance.txt` was exactly 30 bytes, with no trailing newline or
  period, and SHA-256
  `fe61354cb902c3e3b35afd12b5cd8c7d2a9bec321ee6aa323231ff55837c64ed`. Headed Web showed one
  authoritative receipt, one Completed card, and a fresh read-only View reporting
  `workstation-desktop · ready`; the same truth persisted after reload. No active leases remained.
- A rapid-input probe actually issued only objective A because the route remounted before B or C
  could be sent. A produced exactly one user message, one authoritative receipt, one origin/external
  binding, and one GlassHive delegation. It completed at 13:41:09 and wrote `alpha.txt` as exactly
  22 bytes containing `alpha mission complete`, with no trailing newline and SHA-256 prefix
  `e00f3340`. B, C, and the quick-C response path were never issued, so this is not evidence for the
  full rapid-input or multi-mission concurrency contract.

The escaped route/authority defects from that probe are repaired in source and covered by focused
regressions. A current-candidate authenticated headed rerun issued distinct A and B mission asks plus
a quick C follow-up on one canonical conversation. It showed exactly one durable receipt and one
distinct Active Work card for each mission ask, returned the exact quick-C answer, and retained the
same messages, receipts, cards, and canonical route after a direct URL reload. Both mission cards then
truthfully moved to `needs_input` because neither provider account was connected in the isolated QA
environment; this proves the rapid-input route/cache/persistence repair, but not provider-backed
mission execution or active-running controls. The repaired contract is now explicit:

- a new-chat start receipt changes the URL, conversation state, and every live stream cache write to
  the canonical conversation in one handoff; the SSE owner remains mounted, and a delayed receipt
  cannot reclaim a route after the user leaves;
- a lost-response retry returns the original job's stream and canonical conversation identity,
  never a retry-local conversation ID;
- presentation supersession cancels the exact owner-scoped native provider operation without
  cancelling a committed GlassHive mission;
- callback Phase B is presentation-only: it receives no tools and strips every bootstrap bearer
  header case-insensitively; and
- broker-enriched mission instructions remain in the full instruction/bootstrap field, while
  bounded API metadata such as goal and worker role uses independently valid defaults.

A 2026-08-18 installed Telegram rerun closes the narrow rapid A/B/C product branch that remained
open above. Two distinct substantial requests produced two exact, durable mission receipts and two
GlassHive missions. A quick third request returned its direct answer while the second substantial
turn was still authoring. Main did not repeat either delegated objective inline. After a full Web
reload, Active Work showed one mission completed and delivered and the remaining independent work
truthfully queued for host capacity with its controls intact. This proves prompt accounting, durable
launch presentation, Main availability, and cross-surface persistence; it does not replace the
separate maximum-load, three-way execution, Voice, owner-isolation, clean-install, or rollback gates.

A later natural-language Telegram rerun closed the adjacent reuse branch without requiring an
explicit “use GlassHive” command. Main matched a new developer-community research/PDF request to one
existing durable mission, completed an exact idempotent Retry followed by Message on that mission's
`workRef`, and created zero new delegations. While that work continued, a separate quick question
returned its exact direct answer. A later natural continuation produced another Message receipt on
the same `workRef`, again with zero new delegations. Headed Chrome showed that mission as the top
running Active Work card before and after reload. This proves the general existing-versus-new
decision boundary and does not claim that the still-running research artifact is complete.

A final installed A/B/C rerun exercised the same boundary under provider quota and real Docker
pressure. Main kept one continued A mission, created one independent B mission, and returned quick C
immediately. Both durable missions survived a full stack restart, auto-admitted after safe idle
workstation compute was released, recovered through the trusted provider fallback, completed once,
and delivered useful Telegram continuations. A produced the requested Markdown comparison and
single-worker recommendation without inheriting a stale PDF suggestion from assistant-only context;
B produced the requested restart/callback checklist. The escaped contracts are structural:

- Core supplies one host-authored current-task constraint source separately from recent conversation
  context. Public MCP/bootstrap ingress always strips that reserved field; only the trusted launch
  courier may project it. The persisted current run instruction remains authoritative after Message,
  Retry, or recovery guidance, with any explicitly labelled recent-conversation block excluded from
  the constraint ledger. The trusted launch source is a fallback when no current run instruction is
  available. The worker may still use the full context for judgment, but stale assistant prose cannot
  silently become a current deliverable requirement.
- When an exact Retry replacement is still queued and Message arrives before it begins, Store replaces
  that queued source atomically with one additive continuation in the same work. Once startup has
  begun, Message retains the existing safe-boundary behavior. Neither branch creates a hidden sibling.
- Under measured Docker resource pressure, GlassHive may release compute only from the oldest other
  workstation with no active, queued, paused, starting, or needs-input work and no live startup lease.
  Durable completed runs and workspace truth remain. Capacity is freshly measured before the first
  release as well as after each release, so a stale cached pressure sample can never pause an idle
  workstation after the host has already recovered. This is pressure relief, not general idle
  deletion or a capacity bypass.
- If terminal compute release encounters an active-session record belonging to an earlier run, it
  must reconcile that exact recorded session rather than synthesize a session for the latest terminal
  run. GlassHive may clear the record only when the recorded run/session exit evidence and immutable
  process or container generation jointly prove it dead, and the clear must compare-and-set that exact
  record. Ambiguous, live, or concurrently replaced sessions remain fenced, and release may remove
  only the container generation captured by the compute claim.

Foreground consultants and background cortices remain useful for an answer Main is authoring in the
current turn. They are not substitutes for durable admission when Main has decided an independently
completable objective belongs in Parallel Work. Main must not say work is running, queued, retried,
or updated until the matching delegation or action receipt settles. Conversely, matching an
existing objective does not create a competing mission merely because the user sent another message.

The durable launch/presentation boundary is therefore also explicit:

- a work-launch acknowledgement is derived only from an exact server-bound durable receipt, never
  from model prose, a tool intention, a display title, a provider label, or unrelated worker state;
- every surface records the exact committed launch/action in the append-only receipt list for the
  originating stream. This list is a replay fence, not presentation authority: Web, Scheduler,
  Telegram, and Voice all use it to prevent provider fallback from repeating committed work;
- only an external adapter whose declared supersession scope is `response_only` receives the
  singular presentation receipt that may close an older response. Web and Scheduler retain normal
  server-authored presentation. If the exact stream state cannot be read while fallback would
  otherwise run, fallback fails closed rather than risking a duplicate mission or action;
- after a durable receipt exists, the originating Main turn is never replayed through another
  provider. Telegram/Voice may close with their neutral receipt; Web/Scheduler may instead show the
  provider error while the committed mission remains truthful and controllable in Active Work. The
  visible error does not mean the background mission was rolled back;
- a response-only turn superseded by a newer source event waits for either that exact receipt or an
  authoritative terminal result. Once the receipt exists, later provider prose cannot replace the
  neutral acknowledgement; if no mission committed, the stale turn still terminates cleanly;
- a live, non-superseded turn remains open after a receipt so one inference may create several
  independent missions and may still answer a separate direct part of the user's request; and
- external delivery may settle as a durable-effect delivery only when the exact receipt is bound.
  An acknowledgement that races ahead of message insertion is reconciled into the persisted message
  after insertion rather than remaining only in the transient stream job.

The same escaped-bug pass also hardens the non-visual authority boundaries:

- in-process admission serializes create-once ownership, fails closed at active capacity, and fences
  creates across destroy/reinitialize epochs; Redis reserves the globally co-slotted stream owner
  before the owner-scoped logical-turn receipt and requires that exact reservation for job creation;
  a duplicate receipt is usable only when the persisted job owner, logical turn, revision, and
  source event all match. Lazy cross-replica hydration is single-flight and waits for abort-channel
  readiness; every multi-await control captures one lifecycle generation, so destroy/reconfigure
  cancels stale reads and actions before they can mutate a fresh same-ID job. Durable abort or
  supersession truth suppresses late authoring even when Pub/Sub delivery is lost, and a failed
  presentation publish after the durable commit cannot unwind the admitted successor;
- GlassHive mutation idempotency accepts a Core-signed delegation identity or one canonical
  event-grade source identity. JSON-RPC request counters, a conversation ID alone, caller-authored
  bootstrap identity, and changing supplemental conversation/stream fields cannot create or change
  mutation authority. A native conversation-provider mutation commits in one exact call: Core
  derives its stable HMAC operation identity from the authenticated owner/turn, canonical tool, and
  canonical arguments. Exact lost-response retries and broker-grant refreshes reuse that identity;
  a new message or changed canonical arguments do not. Legacy short-lived prepared tokens remain
  verifiable for in-flight compatibility, but a model-visible prepare/confirm round trip is not part
  of the normal path;
- local account HTTP, terminal WebSocket, and MCP compatibility routes enforce the same trusted
  owner boundary as enterprise account routes; model-supplied owner/project values are data, never
  authority; and
- automatic conversation-orchestrator admission derives the immutable server-owned
  `parallel-clean-room-v1` policy and `clean-room` bootstrap profile before persistence. Unsafe
  bootstrap profiles, home-scoped files, arbitrary environment, caller credentials, caller MCP,
  caller grants, or caller policy are rejected before mission rows exist. Clean-room bootstrap
  purges stale CLI/git/SSH authority with descriptor-relative no-follow operations.

The clean-room runtime reserves an inert canonical container generation before writing a fresh grant,
rechecks the exact generation and full container policy around boundary inspection and seeding, starts
by immutable container ID, and reattests after startup. Mount propagation and the complete normalized
tmpfs option set are part of that policy; probe uncertainty is unavailable, never absence. The runtime
also requires healthy policy-labeled provider and broker proxies on the internal network.

The current source and isolated QA runtime provision one internal network per mission, attest exact
worker and proxy images, users, commands, namespaces, capabilities, mounts, environment, ports, and
network membership, and project the run grant only after exact-generation boundary checks. A real
hostile worker probe found no ambient authority, host/App Support mount, Docker socket, default route,
metadata access, arbitrary egress, or sibling reachability; reviewed provider/broker health paths
worked and an unauthorised broker call returned 401. Host Docker-administrator authority remains
outside the worker threat boundary and is not claimed as sandbox-contained. This is still not a
release PASS until provider-backed tool success, owner isolation, concurrent lease caps, shipped
artifacts, and clean-install user acceptance pass on the final candidate.

On the exact current tree, the complete GlassHive runtime gate collected 1,437 tests and passed with
ten intentional opt-in live-environment skips. The skipped native Codex/Claude lifecycle and restart
cases were also run separately against the installed CLIs and passed. The clean-room
bootstrap/profile/Docker subset passed 390/390, and the Glass Drive UI suite passed 113/113.
These broad automated results remain subordinate to the installed-runtime and real-user acceptance
gates below.

Restart recovery also treats a freshly inspected matching exact Docker generation in `dead` or
`exited` state as already stopped: it clears only that generation's durable session marker instead
of retrying an impossible in-container stop. Probe failure, generation mismatch, absence, and live
states remain fenced. The escaped-case regression passed in the complete suite, and the isolated
runtime reaper cleared six previously stuck compute-release claims to zero while retaining zero
active host leases and an `ok` database integrity check.

Phase 1–4 lifecycle repairs now automate durable claim, startup handshake, exact control, lifecycle
effect, callback, and revocation replay ownership. The current Phase 4 startup suite passes 25/25,
an independent two-store startup/replay audit passes, and the affected API (240), MCP (148), UI
(107), account, delegation, and lifecycle suites are green. This supporting automation does not
replace user-level control or cross-surface acceptance.

Current-candidate Telegram Desktop and audible Voice runs cover roster visibility, preference
persistence, Queue, Message, Resume, Stop, Dismiss, truthful unavailable Pause, call teardown, and
restart/reload persistence. Provider-backed fallback missions completed and delivered on the current
candidate. Release remains blocked on provider-connected active-running Steer/Pause and lost-control
recovery; scheduler delivery/adjudication; three-way capacity, overflow, load, fairness, and latency;
full Web/Telegram/Voice/artifact parity; two-owner isolation; the final hostile-sandbox and forged-mode
matrix; rollback; and clean install, nested pins, and shipped-artifact parity. The deployment
availability flag therefore remains false and the default remains `focused`.

## Account and surface contract

The canonical user preference is:

```ts
personalization.orchestration_mode: 'focused' | 'parallel'
```

The canonical deployment declaration is:

```yaml
glasshive_options:
  orchestration:
    parallel_available: true
    default_mode: focused
```

This is the agent capability declaration. The separate deployment setting
`integrations.glasshive.orchestration.available` remains `false` until release gates pass; both
must allow Parallel Work before a surface exposes it.

- Existing and new public accounts default to `focused`.
- The Telegram label is **Parallel work**. It writes the linked LibreChat account preference and
  makes no model call.
- Every Telegram command, setting/callback, text, captioned attachment, and uncaptioned attachment
  handler remains nonblocking (`block=False`). Tampered, expired, cross-user, duplicate, or
  already-consumed action capabilities perform no action and return a safe refresh/retry path.
- Web keeps the account-wide preference in **Settings > Account** and presents the authoritative
  **Active work** roster and exact controls as a first-class right **Control Panel** section. The
  section follows contextual builders and precedes reference tools such as Prompts, Feelings, and
  Memories. It remains reachable when admission is disabled if durable work is already known.
  Voice reads the same preference and supports natural-language roster and control through the same
  eager tools; it never initiates an unsolicited call.
- Turning Parallel Work off prevents new automatic delegation. It never cancels or hides existing
  work. Explicit user-requested delegation remains available.
- Missing Telegram account linkage returns the existing safe linking flow.
- The toggle remains hidden while the deployment availability flag is false. A requested-available
  deployment is still fail-closed unless GlassHive's service-authenticated orchestration capability
  snapshot reports `isolatedParallelReady=true`; a live or restart-reconciled host mission makes
  effective availability false without hiding its existing work card.

## Canonical public work model

```ts
type WorkState =
  | 'accepted'
  | 'queued'
  | 'starting'
  | 'running'
  | 'paused'
  | 'needs_input'
  | 'settling'
  | 'stopping'
  | 'completed'
  | 'failed'
  | 'cancelled';

// `stop_failed` is a typed attention/error code on `stopping`, not a second public state.

type WorkAction =
  | 'queue'
  | 'message'
  | 'steer'
  | 'pause'
  | 'resume'
  | 'stop'
  | 'retry'
  | 'dismiss';
```

`WorkSummary` contains only an opaque `workRef`, title, state, safe status summary, typed attention,
provider, origin surface, compact native-team counts, delivery state, timestamps, optional read-only
`viewRef`, and the actions valid for that exact item. It must never expose authorization, prompts,
transcripts, credentials, local paths, tokens, or raw project/worker/run IDs.

Only `completed`, `failed`, and `cancelled` are terminal. Active state is the pin; GlassHive
`favorite` is unrelated. Terminal failures remain until retry/dismiss. Completed work remains until
delivery is acknowledged or intentionally silent.

## Owner-scoped service interfaces

GlassHive provides these first-party service-authenticated interfaces in local and enterprise modes:

- `POST /v1/delegations`: atomically reserve launch capacity and persist a delegation intent,
  project, worker, first run, and queued state. The trusted idempotency key is derived outside the
  model from tenant, account, source event, objective ordinal, and exact goal digest. Same key and
  content replay; changed content conflicts. Return `202 accepted|queued` only after that durable
  reservation commits. If capacity cannot be reserved, create no work and return a typed
  non-acceptance with available, required, shortage, reservation, and next-retry facts.
- `GET /v1/active-work`: indexed, paginated snapshot with `fresh|stale|unavailable`, safe work,
  cursor, and overflow count. Unavailable is never represented as an empty roster.
- `GET /v1/work/{workRef}`: safe detail and native topology.
- `POST /v1/work/{workRef}/actions`: owner-scoped, idempotent, exact-work actions.

For local Web presentation, Core may replace only the origin of an already authorized opaque
`/w/ghr_*` View URL with its trusted configured loopback GlassHive origin. The request surface,
hostname, and socket peer must all prove local Web. Telegram, remote Web, and caller-supplied origins
keep the configured public URL. Query strings, fragments, credentials, and non-opaque paths fail
closed.

LibreChat signs short-lived account assertions. Tenant/owner claims come only from that assertion;
raw caller headers and `workRef` never grant authority. Mutating assertions have replay protection.
The account assertion, bearer, callback, broker, public-link, and bootstrap secrets are distinct and
server-only.

For standalone MCP mutation compatibility, a JSON-RPC request ID is never a source event: SDK
sessions legitimately restart their counters. Prefer the server-signed delegation identity; when
that is unavailable, derive one stable key from exactly one event-grade hierarchy (logical turn plus
revision, message, Telegram update/message, Voice event, or stream as last resort). Conversation and
other supplemental scope may be consistency-checked but cannot independently authorize or perturb a
retry key.

Core's private `ViventiumExternalWork` relation stores the opaque origin/work binding, tenant and
owner, either conversation/logical-turn/revision/source-event identity or schedule occurrence,
whether the mission is required, delivery-binding ID/configured destinations, private provider
worker/run IDs, canonical external state, attention, adjudication, and delivery state. These fields
are never the public WorkSummary and never grant authority. The relation is the durable join for
lost-response repair, scheduler gating, callback verification, and rollback visibility.

Main sees only `active_work_list` and `active_work_action` as the eager control plane. Ordinary fresh
delegation is one atomic GlassHive call. Low-level `worker_*` controls remain operator diagnostics and
must not compete in Main's normal tool list. Watch links are read-only; control needs an authenticated
proxy or short-lived, action-specific, one-use capability.
One canonical action executor serves Main, Telegram, Web, Voice, and Workbench; surfaces cannot
reimplement or bypass delivery gating, reauthorization, idempotency, or post-action invalidation.

## Always-ready Main and logical-turn continuity

Parallel Work extends rather than replaces the existing logical-turn revision contract:

- Every Telegram/Web/Voice source event remains durable and ordered. Rapid source segments visible
  before Main commits are accounted for exactly once; distinct A, B, and quick C may become two
  missions plus one direct answer, never a silent merge or drop.
- A trusted source sequence is compared atomically with the durable source watermark and current
  revision during admission. A delayed lower sequence cannot replace a higher sequence regardless
  of host arrival order. Core returns typed `source_order_superseded`; the source adapter suppresses
  that stale request without exposing a transport conflict or a second answer.
- Stream admission has a first-owner fence independent of the logical-turn receipt. A colliding
  client cannot win by reaching job creation second, and a stale/pre-fix receipt cannot return a job
  unless the persisted user and exact logical-turn/revision/source identity match. When an in-memory
  store is at active capacity it returns a structured retryable capacity condition; it never evicts
  a live generation or leaves its logical-turn indexes detached.
- Installed Parallel Work source ordering uses one Viventium-owned Redis service with Redis Streams,
  a persistent named volume, and an exact loopback-only endpoint. It cannot reuse another product's
  Redis. Missing, unhealthy, wrongly owned, remotely exposed, or secret-bearing Redis configuration
  stops LibreChat startup and keeps Parallel Work unready.
- A delegation accepted in GlassHive survives presentation supersession, a new logical revision,
  connection loss, process restart, and another user message. Only an explicit targeted Stop cancels
  it.
- The initial `/c/new` receipt must atomically bind the canonical route, Recoil conversation, and
  message-query key before subsequent `CREATED`, content, step, final, or error events are written.
  Stream handlers must not retain a `new` query key after settlement. Cleanup may close only the
  stream whose route owner actually left.
- A duplicate generation receipt is authoritative only when it echoes the original job's stream,
  canonical conversation, logical turn, and revision. A retry-local request UUID is never allowed
  to redirect the browser to a different conversation.
- Supersession revokes only the exact owner-scoped provider operation. It cannot infer authority
  from a display title, provider name, prompt text, or conversation-wide mutable state.
- Main makes the direct/delegate/steer decision in the same inference. There is no router model or
  added classification round trip.
- A provider adapter may project the declared atomic delegation and Active Work tools into Main's
  native structured tool-call surface, but that authority is bound to the authenticated
  conversation lane. Mission roots and native children never receive peer-mission spawn authority.
  The adapter supports a bounded set of calls from one turn so a surviving rapid-fire revision can
  launch distinct A/B objectives without inventing another author or classifier.
- Main may say work was delegated, accepted, queued, or running only after the corresponding tool
  call returns a durable mission receipt. Prose, intention, native shell use, or unrelated worker
  activity is never a delegation acknowledgement.
- Receipt presentation is lifecycle state, not intent classification. Runtime may correlate an
  exact owner, source event, response, and durable work reference, but it must not inspect prompt
  wording, provider name, mission title, or output text to decide whether work was delegated. A
  superseded response-only turn normalizes only its stale presentation; a live mixed-answer turn
  remains free to answer unrelated direct content and to launch more than one mission.
- A generic API/process health check is not Parallel Work readiness. Telegram starts when Core can
  serve Main. Every Parallel Telegram turn separately rechecks the exact account-aware orchestration
  boundary before tool projection. When that boundary is dark, warming, degraded, or lacks durable
  source ordering, Core accepts the ordered turn but withholds new mission authority. Main remains
  available for direct conversation and cannot claim delegation. Existing work remains visible and
  controllable through its separate retained-work authority. The shared operational readiness and
  health snapshot also fail with `source_order_not_durable`; a health surface cannot report ready
  while Telegram must strip launch authority. Runtime code never infers readiness or user intent
  from an open port or prompt wording.
- Main's stable tool policy permits automatic durable delegation only when the ephemeral account
  capsule explicitly says `Mode: parallel`. Without that signal, delegation requires an explicit
  user request. This keeps the focused/off fast path deterministic without a preference lookup or
  classifier round trip.
- The compact Active Work capsule begins loading alongside request setup, uses a two-second
  stale-while-revalidate cache, targets local p95 below 50 ms, and has a hard 100 ms cold wait. A
  timeout emits a compact `unavailable` capsule whenever effective Parallel mode or the trusted
  known-work hint requires awareness, rather than delaying Main or implying an empty roster. The
  focused/known-empty path emits no capsule and performs no roster query. Deployment rollback
  always forces effective mode to focused while retaining unavailable/active-work awareness.
- The capsule is capped at 16 KiB. It prioritizes `needs_input`, `stopping`, and recently changed
  work, carries an explicit overflow count, and always points to `active_work_list` for the complete
  roster. Every provider maps the same capsule to nonpersisted system/developer context after the
  cacheable static prefix; the GlassHive conversation-provider header is one adapter, not the
  universal transport.
- Inject the capsule only when Parallel Work is on or Core has unresolved work/delivery. It stays
  outside persisted messages and native authority fingerprints. Voice receives only active count
  and urgent attention plus on-demand tools.
- Status cards use neutral lifecycle language. A worker never speaks as Main. Terminal evidence
  enters the existing Phase-B adjudication path; Main authors any useful continuation in its own
  voice, while redundant/moved-on results may resolve silently with durable status intact.
- Mission-callback Phase B is exempt from ordinary moved-on presentation suppression and bounded
  SSE grace when it can still add useful account-level information; empty, `{NTA}`, redundant, or
  stale synthesis remains silent. Persisted terminal/delivery truth never depends on NTA text.
- A contiguous retry wait episode publishes one `run.waiting_on_capacity` state transition. It also
  publishes bounded, coalesced status refresh intents at the configured visibility interval while
  the wait continues. Each refresh carries measured queue age, structured blocker, next retry, and
  queue deadline; scheduler probes inside the same interval do not grow the user surface or outbox.
  A different structured failure class starts a new episode. User-launched work always has a bounded
  queue deadline. Expiry compare-and-sets the run to terminal `failed` with
  `queue_wait_timeout`, preserves the workspace for explicit Retry, and emits one terminal callback.
  A database claim alone does not close the episode: host lease, capacity, and broker admission may
  still put the same run back into the same wait. The suppression marker clears only at the exact
  runtime-invocation boundary after those preflight checks pass, and that boundary is persisted
  separately from the scheduler's claim timestamp. The same failure class after an actual execution
  attempt may therefore truthfully publish one new wait transition without misclassifying a
  capacity-bounced queued run as executed.
- Main and callback copy may promise only what durable evidence proves. “Will deliver,” “I will
  notify you,” or equivalent future-delivery wording requires a verified callback binding plus a
  persisted admission or next-retry fact. Otherwise report the current blocker and exact user action
  only.
- Phase B is a presentation adjudicator, not an orchestration lane. Before provider invocation it
  removes `x-glasshive-bootstrap-bundle-b64`, `x-glasshive-bootstrap-timestamp`, and
  `x-glasshive-bootstrap-signature` by case-insensitive header name and supplies no tools. Mixed
  header casing must never preserve bearer authority. It uses a distinct native session lane while
  retaining the canonical Main continuity identity and the exact request-pinned
  `MainContextSnapshotV1`. A missing or unbindable snapshot fails before provider invocation. Phase B
  must never rotate, replace, interrupt, or terminate Main's active native session. The provider
  rejects any authority-changing session replacement while the old worker owns nonterminal work and
  returns the typed `conversation_session_authority_conflict` class without changing provider health.

## Exact action semantics

| Action | Required behavior |
| --- | --- |
| Queue | Persist a follow-up behind the current objective without interrupting it. |
| Message | Add noninterrupting guidance while preserving the original mission request, success criteria, response format, deliverable contract, and every earlier user Message that is still queued and has never executed. Use a proven native live channel when available; otherwise queue one additive continuation at the next safe boundary and report that truthfully. Repeated Messages may coalesce into that one queued replacement, but no earlier queued user guidance may disappear. |
| Steer | Interrupt the exact active run and start replacement direction inside the same mission/workspace. Warm resume requires unchanged workspace, model, permissions, tools, and authority fingerprints. |
| Pause | Hold the objective and preserve workspace/session. The current run cannot remain falsely `running`. |
| Resume | Continue the paused objective without creating a competing mission. |
| Stop | Exact-work cancellation that preserves workspace. Return `stopping` until process/provider confirmation proves termination. If termination cannot be proved, keep `stopping` and attach typed attention/error code `stop_failed`; never publish it as a separate terminal state. |
| Retry | Continue retryable terminal work in the same mission workspace. |
| Dismiss | Remove an acknowledged terminal card without deleting history. |

Terminate/archive is a separate operator lifecycle action. It is never the ordinary meaning of Stop.
Every provider-facing action schema, tool description, and compact Voice context must preserve these
distinctions. If the user names an action, Main uses that exact action and reports the durable action
result; it must not relabel Message as Queue, infer success from prose, or speak an operation receipt
as though it were the user-visible outcome.
All completion/cancellation races use compare-and-set terminality; late output is audited and
suppressed after Stop wins.

## Callback, scheduler, and delivery truth

Core creates an opaque origin/delivery binding before launch. GlassHive echoes only that binding;
callback-supplied surface IDs are never trusted. At callback time, Core resolves the persisted
destinations and current account mapping, then creates one idempotent delivery row per surface.

- The trusted callback transport receives the raw `callback_id`, positive `attempt_number`, stable
  positive `callback_ts`, and exact `origin_ref`, `work_ref`, `worker_id`, and `run_id`. Replay keeps
  the original attempt identity and timestamp. Raw callback identity is not exposed by work detail.
- GlassHive persists callback attempt identity. Work detail emits only the canonical
  `callback_sha256:` reference plus matching attempt number, event, transport status, attempt count,
  and created, updated, and accepted timestamps.
- New work pins strict producer trace V2 at creation. Work detail emits a `run_sha256:` reference;
  exact lifecycle, attempt, capacity, callback, runtime-invocation, and provider-authorization
  preflight histories; the fixed `glasshive.worker_prompt_registry` producer scope; and safe
  artifact references with digest, fingerprint, kind, state, and nonnegative size. Legacy V1 detail
  remains readable for history and is never rewritten as V2. Any required-history, trace-page, or
  artifact overflow fails closed instead of returning a partial strict trace.
- `runtime.invoked` identifies the local runtime boundary. It is not a provider call. Core records
  `provider.request.forwarded` only after the upstream provider returns response headers and before
  any response body reaches the Worker. The receipt is bound to the active persisted owner,
  origin, work, and run grant and stores only redacted provider/status facts plus hashed references.
  Revoked or replaced grants fail before credential lookup or network access. If the forwarding
  receipt cannot persist, Core cancels the upstream body and returns a typed retryable failure.
- GlassHive outbox success means `http_accepted`, not user delivery.
- Core separately records callback persistence, target resolution, target enqueue, surface delivery,
  and acknowledgement. A terminal HTTP acceptance with zero resolvable targets alerts.
- Each terminal card is immediate. Useful terminal prose from the same account is coalesced for at
  most two seconds before Main authors it; callbacks remain individually durable and replayable.
- Every mission binding carries the server-owned Main agent identity from the authenticated launch
  request. Legacy bindings that predate that field recover it from the compiled Main-agent setting.
  Background synthesis rebuilds the ordinary authenticated request shape from the persisted user
  record before saving Main's message; a lean database record with only `_id` must not strand a
  completed mission in callback retry.
- A terminal result becomes durably `sent` or intentionally `silent` only from the delivery ledger,
  never by interpreting generated prose or `{NTA}`.
- Recoverable Telegram transport/provider failure is provisional during the configured recovery
  window. Recovery produces one final answer and retracts/replaces stale failure; exhaustion produces
  one truthful terminal error.
- Telegram consumes the server's structured error class rather than substrings. A flattened bridge
  error never acknowledges the logical turn as committed; the durable follow-up poll survives the
  original stream ending and preemption of its in-memory insight listener.
- Provider-fallback classification is attempt-ordered. The structured terminal result from the final
  attempted provider outranks quota, auth, or capacity evidence from an earlier provider in the same
  native transcript. When native output contains several attempts, final-attempt stdout and the
  durable stderr channel are both retained so an exact final auth-projection rejection remains
  actionable needs-input. An otherwise generic structured provider `400` remains retryable in the
  same workspace. Scanning the combined transcript for the oldest or most recognizable error, or
  dropping stderr merely because several starts were recorded, must never relabel the final attempt.
- Main-provider fallback is also effect-ordered. It is eligible only before visible authorship and
  before any exact durable launch/action receipt exists for that stream. The receipt is authoritative
  across the separate host-tool HTTP request, process, and replica boundaries; request-local tool
  callbacks alone are not proof that no durable effect committed. Recovered native output counts as
  authorship and is preserved rather than replayed through another provider. A missing, disallowed, or
  unavailable configured fallback preserves the primary structured provider failure instead of
  replacing it with fallback-preflight internals. An eligible fallback projects orchestration and
  broker capabilities from Main's stable server-owned declaration, not from the failed attempt's
  reduced tool list. It may receive only capabilities Main declared and that current readiness still
  allows; a degraded or disabled capability remains absent.
- In-process graph handoff and external effect authorship are separate boundaries. Graph-owned
  coordination tools receive a server-authored non-effecting class from their graph membership, not
  from a tool-name or prompt heuristic. A failing participant retries its own configured fallback
  before the outer Main route is considered, preserving shared graph state and keeping Main's turn
  available. Every unmarked tool remains fail-closed, and an exact durable receipt always outranks
  request-local coordination metadata.
- For terminal callback adjudication, a current durable `run.completed` or `run.failed` event is the
  authoritative lifecycle source. Older conversational claims about a missing artifact, failure, or
  in-progress state are supporting context and cannot override that current terminal truth.
- Provider authorization is checked after the exact run-scoped grant is minted but before the run
  becomes admitted or invokes a runtime. This preflight resolves the selected provider credential
  for the exact owner without sending a provider request. Missing authorization, a required account
  reconnect, or rejected credentials becomes `needs_input`, closes the active attempt, releases its
  lease, and leaves the same workspace resumable. Core credential-storage/projection failure and
  provider unavailability are typed retryable internal blockers; they must not ask the user to
  reconnect. No provider-auth failure retries automatically with stale authority. After the user
  resolves a user-actionable authorization failure, explicit Retry resumes the same durable
  workspace/session instead of forcing Dismiss or creating a replacement mission. Automatic
  retryability and user-authorized resumability are separate state-machine decisions.
- Every V2 preflight result is one immutable event per exact attempt and provider. Exact replay is
  idempotent; a changed status or failure class under the same event identity is rejected. A V2
  runtime invocation must have a matching earlier authorized preflight. Failed primary and
  authorized configured fallback preflights may coexist in the same attempt; they are not forced
  into a false one-to-one provider/runtime count.
- Provider liveness is structural, durable, run-scoped, and bound to the immutable attempt captured
  by the dispatched runtime. A late event from an older attempt, an event without that identity, or
  an event whose exact lease has expired is rejected; it is never rebound to the current attempt.
  Only exact typed native progress and retry events count; reasoning text, provider prose, unknown
  events, and failed or rate-limited terminal events do not. Three classified internal retries
  without later meaningful progress, or
  15 minutes without meaningful progress, atomically closes the live attempt and lease, releases
  compute, preserves the workspace/session/route, and keeps the wire state `needs_input`. User
  surfaces label that state **Needs attention** with typed code `provider_progress_stalled` and a
  same-work **Resume** action, not terminal Retry. Resume durably locks and re-admits the exact run
  without changing provider, model, route, workspace, or native session; crash or lost-response
  replay is idempotent and wakes the exact worker again. If that exact route is cooling down, the
  run waits for it without consuming retry budget or selecting a fallback. The same durable lock
  also blocks the conversation provider's independent serial-fallback eligibility and atomic claim
  paths after any later quota or rate-limit failure. An optional boolean
  `longMission` launch declaration is pinned
  to the run as `viventium_run_liveness: {version: 1, long_mission: true}`. It bypasses only the
  ordinary maximum duration, only after real progress and only while progress stays fresh. Each
  resumed attempt receives its own ordinary pre-progress window; the run's permanent first
  `started_at` cannot immediately reap a fresh resumed attempt. An explicit caller timeout remains
  authoritative. A declared long mission with no progress earns no extension; stale typed progress
  follows the attention transition. Malformed declarations fail closed. Runtime never infers
  liveness from prompt words and never silently changes provider or model.
- A schedule occurrence that launches required external work enters `waiting_external` and keeps
  renewing its scheduler occurrence lease until every required mission is terminal. A short worker
  compute/run lease may be released independently when that worker is not executing. Acknowledgement
  delivery is not objective completion, and one-to-many required missions gate the occurrence.
- The two schedules observed during the originating incident were legitimate separate tasks, not
  duplicate dispatch.

## Concurrency, isolation, and resource safety

Never enable a capacity bypass. Persist execution leases transactionally with execution mode,
runtime family, lane, tenant, owner, worker, run, executor/process identity, heartbeat, and
timestamps. Docker/workstation missions participate in the same bounded ledger as host execution;
moving the safe lane into a container must not create an unbounded side channel.

Default configurable limits are two conversation slots and three mission slots per CLI family, four
active top-level missions per account, and twelve per tenant. Interactive Main and controls outrank
callbacks and mission retries. Mission execution never consumes the reserved interactive lane.
Every mission has one typed resource class. `standard` remains the default and reserves 3 GiB.
`light` reserves 1,536 MiB only for a complete bounded objective that can safely run inside that
limit. The same immutable byte value controls atomic admission and the Docker memory/swap limits.
Main selects the declared class through the typed launch contract; runtime never infers it from
prompt words, titles, providers, users, or machines. Unknown classes fail validation.
When a rejected `standard` launch includes complete server-measured capacity vectors and those
facts prove that `light` fits every guard, the MCP courier preserves the sanitized vectors and
recommends `light`. Main may retry the same bounded mission once; runtime never silently downgrades,
and unbounded or memory-intensive work must wait for standard capacity.
An initial delegation with no reservable launch capacity is not accepted and creates no mission.
Deployment isolation readiness attests the Docker daemon, image, internal network, and exact proxy
policy only. A transient `top`/`stats` capacity probe during another container's start must not be
cached as deployment unavailability. Each delegation instead measures capacity afresh and holds its
durable reservation through atomic acceptance; an unavailable measurement still fails that exact
admission closed.
Already accepted work may later enter durable `queued/capacity_wait` after restart or when a
post-acceptance prerequisite is lost; it remains there until capacity, explicit Stop, its declared
deadline, or a real unrecoverable failure. A fixed retry count cannot turn capacity into failure.
When the Docker resource guard proves memory pressure, pre-acceptance may reclaim compute from the
oldest safe idle Docker workstation before returning typed non-acceptance. A candidate is safe only when it belongs
to another worker, has no live startup lease or lifecycle claim, and has no active or queued run; its
completed work and workspace remain durable. Reclaim one candidate at a time and remeasure real
capacity after each release. Never infer relief from the release call alone, reclaim paused or
needs-input work, or widen this into unconditional idle cleanup.

Each mission has isolated workspace, `HOME`, `CODEX_HOME`, `CLAUDE_CONFIG_DIR`, temporary/cache
directories, native session state, logs, and process group. Preserve `USER`/`LOGNAME` when platform
credential access requires them. Mutating missions against one repository use worktrees/copies or
serialization. Read-only work may share source state.

Admission uses exact structured provider/runtime status and error codes, never English substring
matching, for capacity, quota, and retry classification. A provider `Retry-After` is a hard lower
bound. The selected model and reasoning effort never downgrade automatically. The shared persisted
retry scheduler applies owner-weighted fairness; it does not create per-run timers. Default global
headroom is at most 64 Viventium child processes, 2,048 threads, and at least 2 GiB available memory,
plus the configured disk floor. Callback synthesis and reconciliation cannot consume or outrank the
reserved interactive/control lane, including under maximum admitted load. Legacy concurrency bypass
flags are rejected rather than treated as release escape hatches.

The exact grant-scoped provider preflight is part of admission, after capacity and isolation are
reserved and before `runtime_invoked_at`. A preflight rejection revokes the fresh grant, releases the
lease, closes the attempt, and records no runtime invocation. Therefore a missing-provider-auth run
is degraded-state evidence, not execution or parallelism evidence.

Filesystem and environment-directory separation is not an OS security boundary. An unsandboxed
host-native worker running as the same Unix user as LibreChat/GlassHive can inspect sibling process
environments and protected application state, even if its `HOME` is unique. Therefore:

- automatic Parallel Work missions use a Core-owned isolated Docker/workstation execution policy;
  model/tool arguments cannot select or forge host execution;
- the isolated runtime has no host PID namespace, Docker socket, service-state/App Support mount,
  or access to another worker's home/workspace; only the exact run-scoped workspace and capability
  projection are mounted;
- before projecting any fresh broker/provider authority, the runtime performs a non-cached,
  tri-state Docker inspect and reserves an inert exact container generation before seeding. It
  requires a valid immutable container ID, the configured image ID and image reference, non-root
  `seluser`, the reviewed entrypoint/command, private PID/IPC modes,
  exactly the dedicated internal network, exactly the expected home/workspace bind sources and
  destinations with private propagation and no other mounts, `cap-drop=ALL`, no added capabilities,
  no privilege, `no-new-privileges`, read-only root, and every reviewed tmpfs target and option.
  It rechecks the same generation after the boundary probe and seed, starts by exact ID, and
  reattests after startup. Timeout, malformed output, uncertain image identity, stale cache,
  replacement-by-name, or any policy drift prevents reuse or launch;
- the internal worker network has no direct host/general egress. A policy-labeled provider proxy is
  the only dual-homed egress member and a separately labeled broker proxy exposes only the exact
  broker route. Ambient subscription credentials or provider keys are never copied as fallback;
  absent proxy projection is a typed unavailable/needs-input state;
- host-native mission roots remain unavailable to Parallel Work until a separate OS identity,
  container boundary, or independently proven OS sandbox denies process inspection and protected
  state access; prompt policy and signed lane metadata are not substitutes;
- enabling the isolated Parallel policy transactionally rejects every new host-native mission
  admission across account, legacy, MCP, retry, and restart paths. Existing host missions are not
  killed, but any still-active/reconciled host mission makes `isolatedParallelReady=false` until it
  is terminal. This mutual exclusion is required because a pre-existing same-UID host process could
  otherwise steal the trusted Main lane's live authority and recursively spawn isolated peers;
- only a durable, server-created provider-session association identifies the interactive
  conversation lane. Model-authored `run_mode`, execution mode, bootstrap fields, and tool
  arguments never grant that lane;
- if a request genuinely requires the user's host browser, desktop, Keychain, or local process
  state and no proven isolated adapter exists, the mission reports a typed blocker/needs-input
  state instead of silently falling back to unsafe host mode;
- release QA must prove that a synthetic marker in the service process environment and protected
  state is invisible from a mission root while the root's invocation-fresh scoped capabilities
  still work. It must also prove full immutable proxy profiles, per-mission peer isolation, and a
  grant that remains unusable after container-generation replacement. A shared worker bridge or a
  grant projected into a reusable bind mount does not satisfy those gates.

Explicit legacy/operator host execution remains a separate, clearly risk-labeled surface and does
not satisfy the Parallel Work isolation or concurrency gate.

Stop/Steer/Pause acts through the durable lease and verified PID start identity, not only an
in-memory process map. Restart reconciliation reclaims stale leases without killing a reused PID.
Admission checks configured child-process, thread, memory, disk, and provider/account limits before
launch and returns structured truth.

## Native Codex and Claude teams

The mission root is the durable unit. Native children never become top-level GlassHive runs.
GlassHive persists the native session ID, capabilities, compact topology, and structured session,
child, and team-message events.

- Codex stays on streaming `codex exec --json` in production. Persist `thread.started` immediately
  and project `collabAgentToolCall`/`subAgentActivity`. App Server remains QA-only until authority,
  compaction, restart, and cancellation tests pass.
- Claude prefers a worker-local native background session and Agent View (`--bg`, JSON roster,
  logs, stop, respawn) only after installed-version isolation, broker environment, result, callback,
  and restart probes pass. Existing process-owned `-p` stream-json is the rollback path.
- Capability-gated Claude cross-session messaging may provide true live Message/Steer after the
  installed version and same-user worker-local inbox policy pass. External messages cannot approve
  actions or expand permissions.
- Ordinary nested agents and sibling messaging ship before experimental Agent Teams. Teams remain a
  separate cost/process/shutdown capability gate.
- Root terminality with a known live child becomes `settling`. Bounded reconciliation ends in either
  a clean terminal state or an explicit degraded/lost-child result within 120 seconds; it cannot
  hang forever. The ordered ledger normalizes `provider.session.started`, `provider.child.started`,
  `provider.child.updated`, `provider.child.stopped`, and `provider.team.message`; public list views
  expose only bounded aggregate topology.
- Direct child controls appear only when stable provider IDs and targeted control are proven.
  Otherwise Main controls the root and the root coordinates its team.
- Explicit local host Codex/Claude roots use isolated per-worker homes and may receive only the
  owner-local access baseline needed by the installed CLI; Claude refresh authority is never
  projected. Enterprise host roots require server-owned authorization and cannot discover or copy
  owner-local login state. Automatic Parallel roots remain Docker clean-room only.

## Context, files, tools, and long-running authorization

The mission root receives the exact triggering source segments, explicit constraints, success
condition, relevant conversation/recall context, links, binary/upload references, workspace roots,
origin correlation, and factual capability manifest. Retrieval remains available for additional
context so every launch need not duplicate the full conversation. Under `all_agents`, an eligible
persona-bearing direct worker receives the request-pinned factual Feeling capsule once. A
non-persona specialist root or background cortex receives no persona/Feeling capsule and records a
structured skip. Under `conscious_agent`, direct workers also skip it. No worker receives Main's
speaking persona or private Feeling store.

Media-group ordering and source-to-file identity are preserved. Recall and upload resolution are
owner-scoped in local and enterprise modes. The courier supplies factual context and available
capabilities but never invents a plan, provider, artifact, success criterion, or claimed tool use.
Prompt policy treats “also do X” as another objective only when Main judges it independently
completable; ambiguous controls such as “stop that” require one focused disambiguation rather than
guessing an active target.

Fresh native children receive focused delegation packets. A full-context fork occurs only when the
native harness intentionally selects it. Missing broker capability never licenses filesystem,
browser, computer, or shell workarounds. Broker `401`, partial-tool availability, refresh failure,
and policy/approval blockers update the mission with distinct typed truth rather than silently
degrading to an unrelated native path.

Authorized connected tools are projected through the existing broker; credentials never enter
prompts or durable events. Native children inherit but cannot exceed the root's workspace, tool,
permission, approval, and network envelope.

When one provider has several independently authenticated account slots, each slot is a distinct
broker server identity even when all slots share the same provider URL and OAuth application. The
source-of-truth config must project every configured slot to Main/Connected Accounts and to the
worker broker with a stable provider ID plus a non-secret slot number. OAuth initiation and callback
use the shared provider endpoint while flow state, tokens, tool names, and audit identity remain
slot-scoped. A generic “all my connected accounts” request means every available slot; the worker
deduplicates repeated evidence instead of silently treating slot 1 as the whole provider.

Disabling a provider removes every server-owned account slot for that provider before runtime
validation; no secondary slot or unresolved provider URL may survive because its display/server name
differs. Account slots are selected through trusted provider identity in source config, never a
prompt, account address, user-visible title, or server-name-prefix heuristic.

External writes remain insert-once and evidence-backed. A successful draft call must return the
persisted draft/message/thread identity and the saved recipient/subject metadata needed to verify
that it is still an unsent draft. If post-write verification is unavailable, the tool preserves the
created identity and explicitly forbids automatic replacement so a recovery cannot create a sibling
draft. Main and callbacks must not convert a verification limitation into a false claim that a
field is missing when the real user surface proves it is present.

Every brokered connected-account tool declares truthful MCP effect annotations. Read tools declare
read-only/idempotent behavior; sends, deletes, moves, label mutations, and other external writes
declare non-read-only behavior (and destructive behavior where applicable). The broker escalates
those annotations to write policy. A content-read grant alone can never authorize mail delivery or
mailbox mutation; reviewed draft-only tools may be explicitly allowed when the user requested an
unsent review draft, while sending remains host-confirmed and operation-identity bound.

Broker grants are minted at execution admission, not while capacity-queued. GlassHive may
authenticate back to Core to revalidate the same live mission, owner, connected account, unchanged
scope, and approval state. Re-mint cannot expand scope. Revocation, missing approval, policy change,
or refresh failure moves work to `needs_input`. The authorization horizon remains 24 hours; later
continuation requires explicit authorized Resume.

## Rollout and completion gates

The executable release rule is:

```bash
python3 scripts/viventium/parallel_work_release_gate.py --mode release
```

The compiler writes a versioned `parallel-work-readiness-facts.json`. Its prompt fact is derived
from the validated source prompt registry and includes the exact producer scope, prompt/layer
counts, public layer names, unknown layers, and a canonical registry hash. Its disk fact is measured
from the compiled-output filesystem and uses the same configurable policy as GlassHive: 90% critical
with a 10-percentage-point warning margin by default. Storage pressure must report version 1,
`healthy`, measured bytes/percentage, and an internally consistent warning/critical threshold.
Missing, malformed, unknown, mismatched, warning, or critical facts fail closed; runtime code never infers
these states from log or status prose.

The compiler also installs `parallel-work-artifact-identity.json`. The evaluator does not accept QA
prose as artifact evidence. It independently measures the tracked root revision/clean state, every
component HEAD against its `components.lock.json` pin, the shipped helper source and binary digests,
and the installed `prompt-bundle.json` digest. A missing component, dirty or mismatched pin, stale
prebuilt, missing receipt, or changed installed bundle is a typed release blocker. Snapshots expose
only public-safe names, revisions, booleans, and hashes; local paths and Git status text are never
serialized.

It reads the living QA catalogs. Every `PWK-*` and `REL-*` row is required, with cross-owner
`TR-026`, `EMO-UC-047`, `EMO-UC-048`, `MPV-061`, and `TGDOC-010`. Markdown status prose does not close a gate. Each `PASS`
requires one fresh, unique, structured receipt bound to the exact candidate and installed-artifact
digests, with the case ID, run time, evidence digest, tested surface, and status. Missing, duplicate,
stale, mismatched, or malformed receipts keep the case open. Missing or unknown status and every `NOT RUN`,
`FAIL`, `PARTIAL`, or `BLOCKED` result keep release/default exposure dark, return a nonzero exit,
and forbid Ready or Complete wording. The source defaults remain
`integrations.glasshive.orchestration.available: false` and `default_mode: focused`; passing all
gates permits a later reviewed exposure change but does not silently change those defaults.

Release/default exposure additionally requires a publisher-pinned asymmetric trust policy, an
independently protected publisher signature, exact producer-signed observation evidence, and exact
service-signed acknowledgements when a case requires restarted services. Every signature binds the
case, surface, candidate, installed artifact, owner, semantic verifier, evidence, and unique nonce.
An externally witnessed append-only outcome ledger prevents an older signed PASS from surviving a
later failure, revocation, or restored local file. Same-user-readable HMAC keys, caller-supplied
hashes, self-created trust roots, unsigned observations, and unwitnessed ledgers are insufficient
for release. The weaker local HMAC contract is restricted to explicit **PRE-GATE / NOT READY** QA;
missing independent trust, signer, producer, service, or witness authority always keeps release dark.
Private publisher signing material must never be generated or stored in the installed user runtime.

The production resolver has one supported external provisioning boundary:
`/Library/Application Support/Viventium/ReleaseAuthority/v1/`. Every directory in that fixed path
must be root-owned, free of symlinks, and not writable by the runtime owner. An independently
authorized publisher or system administrator must install four root-owned, non-writable regular
files: `publisher.allowed_signers`, `bootstrap.json`, `bootstrap.sig`, and `provider.py`.
`publisher.allowed_signers` contains the single independently pinned publisher Ed25519 identity;
the canonical bootstrap must be signed by that identity in the
`viventium-qa-release-authority-bootstrap-v1` namespace and must bind the exact candidate digest,
live owner binding, publisher identity/fingerprint, installed policy digest, provider source
digest, and protected witness identity. The signed provider must expose
`resolve_release_attestation_authority`, return those same exact bindings, and create its own
`externally-protected-compare-and-swap-v1` witness backed by an independently protected,
non-rollbackable service. The evaluator never provisions these files, creates signing keys, accepts
an environment or same-user configuration override, or substitutes an in-memory/owner-controlled
witness. Until that separately managed publisher pin, signed bootstrap, protected provider, and
real witness service are installed, production authority is unavailable and the candidate remains
**BLOCKED / NOT READY**. A signed payload verifier, ad-hoc helper signature, owner-local runtime
state, or another vendor's Developer ID does not satisfy this prerequisite.

`bin/viventium qa-evidence record --manifest <private-result.json>` is the only supported receipt
writer. It accepts proof files only under the private App Support evidence root, verifies each file
digest, requires the explicit local-QA request, and binds the receipt to the active candidate and
installed artifact identity. A receipt records evidence; it cannot convert an open catalog row to
`PASS` or bypass the release evaluator. Full receipts, signer attestations, owner bindings, and
nonces remain in private owner-only storage; command output contains only the recorded case, its
status/surface, public-safe candidate/artifact hashes, time, and total receipt count. Public
readiness and artifact-identity projections expose only validated typed values, never raw producer
errors, filesystem paths, credentials, or private identifiers; command failures expose bounded
error classes only. If the trusted witness records a failure before its private receipt file is
replaced, retry may reconcile only that same fully authenticated, already-revoked case. A forged,
different-owner, different-candidate, different-artifact, or still-current PASS cannot use this
recovery path.

`bin/viventium release-check` is the public claim command. Config compilation writes the evaluator's
typed JSON projection to `parallel-work-release-gate.json`; install and status summaries consume
that projection and do not parse QA Markdown. Open gates report **NOT READY**. An explicit requested
local exposure reports **PRE-GATE / NOT READY**. Existing Web and Telegram readiness surfaces remain
unavailable unless both the compiled release-gate snapshot and their structured operational
orchestration snapshot pass. Missing snapshots and open QA return the same visible label and typed
blockers on Web and Telegram; an explicit local override always reports **PRE-GATE / NOT READY**.
Source, compiled, installed, and prebuilt identities remain separate release evidence; no one
surface may stand in for another.

Explicit local QA is separate:

```bash
bin/viventium release-check --local-qa --json
```

This command uses the exact active owner and canonical runtime inputs, then atomically persists the
local-QA request and `parallel-work-release-gate.json`. The override may exercise current-checkout
behavior while gates are open. It does not change source,
compiled, shipped, or account defaults and must be shown in reports and status as **PRE-GATE / NOT
READY**. The evaluator fails the override too if the source defaults are no longer dark/focused.

Installed fault QA uses one private session at a time through `bin/viventium qa-control`. The
session is bound to the active installed checkout, expires within one hour, stores its token only
under App Support with owner-only permissions, and is projected into services only by the installed
launcher. QA entry points reject every ambient authority/config value and every global authority
option, including a value equal to the canonical path. Private request, artifact, session, and
runtime-environment reads require one owner-owned regular `0600` file and reject a symlink in any
path component. Ambient variables, stale sessions, another checkout, and unknown cases fail closed. The
supported release cases are `TR-026`, `EMO-UC-047`, `EMO-UC-048`, `PWK-UC-016`, `PWK-UC-017`, and `REL-UC-004`.
Activate or clear a session, then restart the installed runtime so every service receives the same
state. Each required service writes an HMAC acknowledgement bound to its live PID, process start,
executable hash, session, and candidate. Status stays `waiting`, mutation entry points fail closed,
and affected `PASS` receipts remain invalid until the exact required set is live. Receipts retain
only the combined `serviceAckDigest`. Component faults remain exact-scope, expiring, atomic, and
one-time; the session alone cannot trigger a fault.

For `EMO-UC-047`, activate and restart first. The verifier accepts the private installed evidence
through one inherited owner-only file descriptor; it never forwards the evidence path or content to
the child command.

```bash
bin/viventium qa-control activate --case-id EMO-UC-047
# Restart the installed runtime so Core and GlassHive acknowledge this session.
bin/viventium qa-control verify-emo-feelings --evidence private-emo-uc-047.json
```

For `TR-026`, activate the case before restart, then arm its exact synthetic event from a private
`0600` JSON file. The parent reads the target from standard input so owner, chat, and message IDs do
not enter process arguments. The file has exactly these fields: `contractVersion: 1`, `caseId:
TR-026`, `ownerUserId`, `chatId`, `threadId`, `staleSourceSequence`, `sourceSequence`, `updateId`, and
`ttlSeconds`. `sourceSequence` must equal `staleSourceSequence + 1`.

```bash
bin/viventium qa-control activate --case-id TR-026
bin/viventium qa-control arm-telegram-race < private-tr026-scope.json
bin/viventium qa-control audit-telegram-race
bin/viventium qa-control cleanup-telegram-race
```

The parent calls the installed Telegram control in-process with the canonical private session
token. Neither the token nor raw target scope is printed. Clearing the parent session also attempts
token-authorized Telegram cleanup first.

For `EMO-UC-048`, the root parent creates a fresh random durable synthetic `User`, `Conversation`,
and parent `Message` through the installed LibreChat Node, Mongoose, and data-schema build. The
fixture follows the exact component contract in
`viventium_v0_4/LibreChat/viventium/EMO-UC-048-local-QA-fault-controls.md`. It is never a real user,
and no operator supplies owner, conversation, parent, token, or Mongo values on the command line.
The parent sends raw scope only through inherited owner-only temporary file descriptors to both the
fixture helper and installed control. Redirected standard input is not used. Output is limited to
hashes, fixed boundary names, timestamps, counts, and redacted references. The root independently
remeasures the installed running-service manifest, binds its component digest to the session,
launcher, fixture marker at `metadata.viventium.localQaFixture.componentArtifactDigest`, and child
environment, and rejects self-attested, missing, stale, mismatched, or echoed component identity.
Node runs from one trusted absolute executable with preload/injection environment removed. Child
output is streamed under hard byte limits and the process group is terminated at a limit. Mongo is
one exact credential-free loopback seed; duplicate config keys, duplicate fixture/control rows,
expired fixture use, ambiguous JSON, and non-canonical timestamps fail closed. Exact destruction
remains available after expiry. Every control timestamp uses exact ISO milliseconds with `+00:00`.

```bash
bin/viventium qa-control activate --case-id EMO-UC-048
# Restart the installed runtime so Core receives the exact mode and token.
bin/viventium qa-control prepare-emo-insight
bin/viventium qa-control arm-emo-insight --boundary cortex_ledger_first_write
bin/viventium qa-control arm-emo-insight --boundary web_replay_persistence
bin/viventium qa-control arm-emo-insight --boundary web_redis_publish_ack
bin/viventium qa-control arm-emo-insight --boundary telegram_promoted_parent_presentation
bin/viventium qa-control query-emo-insight
bin/viventium qa-control clear-emo-insight
bin/viventium qa-control cleanup-emo-insight
```

Prepare is idempotent for one session and uses one fresh random namespace per session. Repeating an
arm with the same boundary and expiry returns the exact existing control instead of creating a
second row. Arm requires
the exact unexpired session, unchanged installed root and artifact identity, and the explicit local-
QA request. Query, clear, and exact cleanup remain available after session expiry or artifact
replacement. Cleanup first clears every control, verifies that no exact control remains armed, and
then removes only the exact three fixture rows. Parent-session clear fails while its private fixture
state exists, so incomplete or interrupted cleanup cannot be hidden.

For `PWK-UC-016` and `PWK-UC-017`, the root parent uses the installed GlassHive control module and
one fresh durable synthetic owner/work/run/artifact fixture. Raw scope, authority, database paths,
and tokens travel only through inherited owner-only file descriptors or the bounded child
environment. Public output contains hashes and redacted references only. Every private request is
bound to the exact active session, the root-measured candidate identity, and the independently
measured installed service digest. Duplicate keys or options, invalid UTF-8, nonregular or linked
files, unsafe path chains, replacement races, and noncanonical timestamps fail closed. Defaults
stay dark.

Arm verifies the selected database already contains one exact local synthetic fixture whose owner,
work, current run, artifact observation, and trusted fixture idempotency identity agree. A durable
hash-only tombstone prevents that exact arm from being recreated after consume, expiry, clear,
cleanup, restart, or concurrent replay. The parent and component reject a symlinked database,
writable path component, path replacement, or changed private-source identity. The installed
launcher clears ambient candidate identity and exports it only from the exact active GlassHive
session. Phase 2 runtime wiring now consumes the exact controls at the owning provider, capacity,
lifecycle, callback, artifact, and trace boundaries. Source tests prove this wiring; installed
Telegram/browser execution remains required before any case or release claim passes.

```bash
bin/viventium qa-control activate --case-id PWK-UC-016
# Restart the installed runtime so GlassHive receives the exact mode and token.
bin/viventium qa-control prepare-glasshive --case-id PWK-UC-016
bin/viventium qa-control arm-glasshive --boundary provider_auth_missing
bin/viventium qa-control query-glasshive
bin/viventium qa-control clear-glasshive
bin/viventium qa-control cleanup-glasshive
```

Use the same commands with `PWK-UC-017` and one of its installed catalog boundaries. Preparation
and arm are idempotent. Token-bound exact cleanup remains available for recovery after expiry or
artifact replacement; arm, query, and clear still require the active canonical authority.
Parent-session clear fails until every exact control and fixture row is cleaned. This source
contract is supporting evidence; it is not an installed-runtime pass.

`REL-UC-004` uses `qa-control inject-release-claim` only under its exact active session. The command
changes the private installed readiness facts to a typed prompt-registry mismatch and synthetic
96% disk threshold result with 4.3 GB available. It writes only bounded JSON; it never fills the
real disk. `restore-release-claim` compares the injected digest before restoring the exact prior
facts. Session clearing is refused until restoration succeeds.

The minimum integrated release journey is `PWK-UC-014`: on installed Telegram, ask for the current
Feeling and verified route/model facts; start two independent HTML artifact missions; keep Main
responsive for a quick turn; revise that open turn with a later Telegram segment; Steer only A;
prove overlapping execution; receive each result once; and open both artifacts in separate headed
browser windows. `PWK-UC-015`–`018` then prove restart, degraded recovery, delivery/artifact
failures, owner isolation, trace integrity, and hostile-artifact safety. `REL-UC-004` proves the
claim path itself fails closed when a QA case, prompt layer, or disk gate is open.

1. Ship callback/delivery/scheduler truth and durable exact-run Stop unflagged.
2. Land owner assertions, atomic delegation, work APIs, compact roster, preference, and dark UI.
3. Land persisted bounded leases, mission isolation, structured capacity, resource guards, and
   admission-time broker authorization. Keep automatic missions on the proven isolated execution
   lane; host-native roots do not qualify merely because per-run homes exist.
4. Prove Codex and Claude native projection/control behind independent capability flags.
5. Validate tracked source, nested component commit, parent pin, compiled/prebuilt artifacts, and
   installed/running artifact separately.
6. Run `qa/parallel-orchestrator/cases.md` through real Telegram Desktop, Playwright Web, voice, scheduler,
   Workbench, API/MCP, logs, database, callbacks, and delivery ledgers. Keep unavailable surfaces `PARTIAL` or
   `BLOCKED`; mocks and source inspection cannot replace user paths.
7. Expose Telegram first behind the availability flag, then Web. Keep default `focused` until real
   multi-user, latency, restart, same-provider concurrency, and clean-install gates pass.

Quality is an independent gate for every execution path: a shared public-safe prompt bank must show
Intelligence, Relevance, Usefulness, and Alignment parity for Direct Main, a GlassHive Codex root,
and a GlassHive Claude root. Aggregate averages cannot conceal one weaker path.

Performance gates are exact: the preference toggle completes server-side in under 100 ms without a
model call; focused/off adds no network/model call and under 25 ms p95 local overhead; active-work
snapshot p95 is under 50 ms with the 100 ms cold ceiling; and durable delegation targets 150 ms p95
with a hard 250 ms release ceiling after tool invocation, excluding harness startup.

Rollback is exercised as a real installed drill: it disables new automatic launches and may lower
capacity without abandoning or hiding existing cards, callbacks, list/control tools, or already
running missions.

## Evidence-Before-Cleanup Contract

`HARD-023` requires a disposable account or private fixture to retain all required visible,
API/log, database/state, and installed-candidate evidence until a candidate-bound sanitized receipt
exists. Cleanup then removes only that exact owner's fixture data, sessions, grants, cached/search
copies, files, and temporary credentials and proves zero residue. Interrupted cleanup remains
visible and safely resumable; cleanup cannot erase required proof, hide a failed branch, or affect
another owner. `ANTI-013`, `EMO-026`, and `EMO-030` own the acceptance cases, with
`ANTI-UC-012` / `EMO-UC-046` as the natural journeys.

<!-- VIVENTIUM-STABLE-REQUIREMENT-DECLARATIONS:START -->
## Stable requirement declarations

Each line is the canonical public owner declaration for one stable requirement ID. Detailed sections supply implementation context; they must not narrow or contradict these declared outcomes.

HARD-001: Parallel Work remains dark or visibly **PRE-GATE / NOT READY** until every gate is closed.
HARD-002: Main uses one request-pinned Feeling capsule; winning provider records exact hash, count, placement, and semantic receipt. Keep the provider plugin denylist; do not mount private state or add a Feelings MCP.
HARD-003: Every eligible direct worker gets that same capsule exactly once; scope-off workers get none.
HARD-004: Current surface, route, actual fallback, model, and effective effort use typed model-visible facts.
HARD-005: Telegram source order wins delayed host ingestion. A newer source before presentation commit revises the open turn; stale preview/final is removed/suppressed.
HARD-006: Provider health skips structurally known cooldown routes and uses `presentation_committed_at` for delivery timing.
HARD-007: Every completed Cortex insight enters one owner-scoped delivery ledger and ends `sent` or typed `dropped`; claim/retry/replay/follow-up survive restart.
HARD-008: Reserve measured capacity before acceptance. A blocker reports available, required, shortage, reservation, and next retry.
HARD-009: Runtime truth is claimed/admitted/running only from the exact immutable attempt and live invocation boundary.
HARD-010: Queued work exposes age, blocker, retry, deadline/timeout, and one terminal callback.
HARD-011: Route choice consumes durable health; workers receive task/constraints/needed capabilities, not raw private chat or host IDs.
HARD-012: One owner-scoped redacted immutable trace correlates source revision, prompt layers, authorization, capacity, runtime invocation, provider forwarding, work/attempt, callback, delivery, and artifact. Unknown/contradictory/overflow/storage-warning state blocks Ready.
HARD-022: Control actions must return definitive typed conflict truth—such as HTTP 409 for stale/invalid lifecycle state—rather than an optimistic action acknowledgement.
HARD-023: Synthetic/private QA cleanup happens only after all required evidence is captured and verified; cleanup itself is exact, scoped, and proves zero residue.
HARD-024: Release evidence must be authenticated and tamper-evident from writer → receipt → evaluator, binding case, owner/surface, candidate, artifact, semantic verifier, evidence, and real service acknowledgement. A SHA-looking value is not authentication. Reject forgery, replay, stale/wrong-scope evidence, and fabricated acknowledgements.
HARD-025: Reliable owner-safe local acceptance may proceed only as labelled **PRE-GATE / NOT READY** and must not be blocked by a separately provisioned public-release authority. Public release stays fail-closed; local acceptance never weakens its gates.
PW-001: **Queen Bee** is the one existing Viventium Main. It is the only manager and speaking personality.
PW-002: A **Worker Bee** is one saved, durable GlassHive mission root for one independent objective.
PW-003: A mission may use native Codex or Claude children internally. Children never become a second public Main, registry, scheduler, or mailbox.
PW-004: GlassHive is the sole durable mission authority for owner, identity, admission, state, lifecycle, recovery, controls, callbacks, and provider projection.
PW-005: LibreChat/Core stores only account preference, trusted origin/delivery relation, compact roster projection, and surface delivery state needed by Main.
PW-006: Do not introduce a second supervisor, `run_units` planner, top-level native-team registry, Temporal/LangGraph migration, or provider-specific public work API.
PW-007: Workers do not impersonate Queen, address the user as independent personalities, or receive unrelated sibling work/private chat.
PW-008: Main remains the completion author. Worker status is neutral evidence; Main decides what useful result to say.
PW-009: Product label is **Parallel work** with one account-wide preference whose values are `focused` and `parallel`. Effective mode is the user override, else the agent/deployment default; the deployment declares availability and default mode.
PW-010: Default is focused/off. Unavailable always resolves safely to focused. Telegram and Web may edit the same setting; Voice consumes it. An unlinked Telegram account enters the existing safe account-link flow instead of failing or creating shadow identity.
PW-011: Turning it off stops only new automatic delegation. Existing work remains visible, controllable, resumable, and deliverable.
PW-012: Explicit user-requested delegation remains available in focused mode.
PW-013: Changing the toggle makes no model call and does not interrupt Main.
PW-014: Quick/current conversational work stays with Queen. Independent substantial, long, research, browser/computer, artifact, or multi-step work may become a Bee.
PW-015: Main decides in the same inference whether to answer, continue/control an exact Bee, create a Bee, queue a follow-up, or ask one focused target question. No extra classifier/model round trip.
PW-016: “Also do X” normally creates a separate objective or queued follow-up unless it changes the current mission’s objective.
PW-017: Main may intelligently assign endless work to an existing exact Bee or a new Bee; runtime must not hardcode complaint phrases.
PW-018: Main’s interactive lane stays available and outranks mission execution and callback synthesis.
PW-019: Main sees a compact authoritative roster and can address exact work by opaque `workRef`. It never selects raw worker/project/provider session IDs.
PW-020: An unavailable or stale roster is labelled `unavailable` or `stale`, never presented as no active work.
PW-021: Main reports only verified current surface, selected/effective route, model, fallback, effort, Feeling, capability, state, and delivery facts.
PW-022: For large A, large B, then quick C: create A and B once each when admitted, run them in parallel when capacity exists, and answer C promptly.
PW-023: Every source segment is durable, ordered, and accounted exactly once.
PW-024: If new input arrives before Queen’s presentation commits, retract/revise unfinished output and produce one current reply covering every unresolved segment.
PW-025: No two competing Queen replies may survive for one open logical turn.
PW-026: Presentation supersession does not cancel or repeat already committed external effects, accepted Bees, background work, or tool receipts.
PW-027: Only an explicit exact-work **Stop** cancels durable work.
PW-028: Restart, reload, reconnect, or chat continuation loses no segment, mission, action, callback, result, or artifact.
PW-029: Canonical public states: `accepted`, `queued`, `starting`, `running`, `paused`, `needs_input`, `settling`, `stopping`, `completed`, `failed`, `cancelled`.
PW-030: Only `completed`, `failed`, and `cancelled` are terminal. Provider `interrupted` is internal, not a conflicting public terminal.
PW-031: Durable lifecycle is queued → claimed → admitted → running; `running` requires the exact open attempt, live unexpired lease, and immutable `runtime_invoked_at`.
PW-032: First `started_at` is permanent across retries. Attempts are immutable records.
PW-033: `Queued` never means `Running`. Work is not called accepted/launchable until real admission capacity is atomically reserved.
PW-034: **Queue** persists later work without interrupting the current run.
PW-035: **Message** adds noninterrupting guidance. If live injection is unsupported, queue it at the next safe boundary and say so.
PW-036: **Steer** interrupts only the exact active run, replaces direction, and stays inside the same mission/workspace.
PW-037: A warm/native resume for Steer is allowed only under the same authority envelope.
PW-038: **Pause** truly holds the same mission and must not display running; **Resume** continues that mission.
PW-039: **Stop** targets only the exact Bee, preserves its workspace/history, and stays `stopping` until process-tree termination is proved. If termination cannot be proved, keep `stopping` and expose `stop_failed` only as a typed action/attention error detail, never as a public WorkState or terminal result.
PW-040: **Retry/Continue** starts a new run in the same mission/workspace.
PW-041: **Dismiss** hides an acknowledged terminal card without deleting history. Terminate/archive is a separate operator action.
PW-042: A targeted action on A cannot alter B. If “that” is ambiguous, Queen asks which Bee.
PW-043: Late child/completion output after cancellation is audited and suppressed from current presentation.
PW-044: Valid actions are item-specific. Read-only view links cannot control work; controls require scoped, signed, one-use authority.
PW-045: State is the “pin.” Do not misuse GlassHive `favorite` as lifecycle truth.
PW-046: **Active Work** is a first-class main Control Panel surface, not Settings → Accounts → Connected Accounts.
PW-047: Settings keeps only the account preference. Active Work shows the authoritative roster, attention, queue truth, delivery state, valid actions, safe detail, and overflow. Actionable terminal failures remain until retry/dismiss; completed work remains until delivery is acknowledged or intentionally silent.
PW-048: Active Work remains reachable for known existing work even when new admission is disabled.
PW-049: Telegram is the first control surface, but the record and behavior are account-wide across Telegram, Web, and Voice.
PW-050: Normal Voice Call keeps Queen speaking and available. Explicit authorized speech may launch, list, Queue, Message, Steer, Pause/Resume, Stop, Retry, or Dismiss exact Bees.
PW-051: Spoken interruption revises Queen’s unfinished speech once; accepted durable work stays unchanged. Hangup/network loss does not cancel it.
PW-052: Queen speaks concise truthful status/completion once. Files appear in linked chat or Active Work with open/download actions. No unsolicited result call.
PW-053: Directly addressed trusted Wing keeps its explicit-engagement/speaker-authority rules. Passive/unverified Wing and Listen-Only cannot launch or control work.
PW-054: A Bee receives the exact task segments, constraints, examples, links, exclusions, format, and success condition.
PW-055: It receives the mission-relevant authorized subset of conversation, project/workspace instructions, saved memory/recall, sources, approvals, blockers, connected accounts, browser/computer, shell, tools, files, and media.
PW-056: Worker context contains no raw recent private chat, unrelated siblings, credentials, host identifiers/secrets, or authority beyond the root mission.
PW-057: Children inherit but cannot expand the mission’s authority envelope. Missing broker support does not permit a native bypass.
PW-058: Feelings rule: when configured scope is `all_agents`, eligible direct workers receive the same request-pinned factual Feeling capsule exactly once; `conscious-only`/off omits it. Workers never inherit Queen’s speaking persona or impersonate her.
PW-059: Main and each eligible worker use truthful current surface, route, selected model, fallback, effort, and capability facts from typed metadata, not inference from prose/tool names.
PW-060: Text/speech, links, documents, images, audio, video, uploads, grouped attachments, captions, same-name files, and prior artifacts preserve exact identity, bytes, order, grouping, and owner scope where relevant.
PW-061: Failed ingestion cannot silently become caption-only work. Missing bytes/parser/access yields one truthful recoverable failure.
PW-062: Text, citations/source detail, structured output, generated/edited files, media, and artifacts return exactly once through Queen.
PW-063: Results remain visible/downloadable on the origin surface and Active Work. Unsupported rendering uses a stable linked-chat/Active Work handoff.
PW-064: Never describe a file that was not created, call a dead link delivered, duplicate a bubble/artifact, or expose another owner’s artifact.
PW-065: Fallback preserves the same mission, workspace, controls, files, authorized tools, authority ceiling, and required result ability. If it cannot, show blocked/unavailable.
PW-066: Authorization is minted at execution admission, revalidated without expansion, and becomes `needs_input` when revoked/expired/approval is missing.
PW-067: Long-running authority lasts at most 24 hours; continuing beyond that needs a user-authorized resume.
PW-068: Delegation is atomic and idempotent. The trusted key uses tenant, account, source event, objective ordinal, and exact goal digest.
PW-069: Same exact digest replay returns the same mission. Changed content under the same key fails closed. Distinct similar asks remain distinct; do not semantically dedupe them.
PW-070: Core persists trusted origin/delivery binding before dispatch. Disconnect before commit creates no mission; after commit reconciles exactly one.
PW-071: Actions, callbacks, delivery rows, and terminal transitions are also atomic/idempotent. CAS terminality prevents resurrection.
PW-072: Core owns origin/delivery binding; callback-provided Telegram or conversation IDs are untrusted.
PW-073: HTTP callback acceptance is transport truth, not persisted/enqueued/delivered/acknowledged truth. Each configured destination owns one durable delivery row.
PW-074: Delivery states are `pending`, `delivered`, `acknowledged`, `failed`, or `silent`. Zero-target terminal callbacks alert and remain undelivered.
PW-075: A scheduled occurrence with required external missions remains `waiting_external` until all required authoritative work is terminal.
PW-076: Redundant/moved-on results may become durably silent. Useful completion comes once through Main; close completions may coalesce within two seconds.
PW-077: Capacity, account cap, resource pressure, provider quota/429, missing login/auth, provider outage, approval denial, tool absence, and roster unavailability remain distinct typed states.
PW-078: Capacity-blocked work exposes available/required/shortage/reservation, queue age, blocker, next retry, and timeout. It never makes an unverified future-delivery promise.
PW-079: Provider health/cooldown is durable and structural. Honor authoritative retry time; do not repeatedly start an exhausted route. Use `presentation_committed_at`, not generic row update time, as delivery truth.
PW-080: No automatic model or effort downgrade.
PW-081: Owner A cannot list, infer, inspect, control, receive, or fetch owner B’s work/artifacts. `workRef` is identity, not authorization.
PW-082: Service APIs require owner-scoped signed service assertions and fail closed. Public summaries expose no prompts, transcripts, credentials, tokens, paths, or raw internal IDs.
PW-083: Each mutating mission has a unique isolated workspace/worktree, home, provider config, temp/cache/log/session, and process group. Preserve only Keychain-required macOS identity variables. Read-only missions may share a checkout; concurrent mutating missions require separate worktrees/copies or serialization.
PW-084: Stop uses PID plus process-start identity and exact process tree, so PID reuse cannot kill unrelated work.
PW-085: Concurrency is persisted and bounded. Never bypass it through same-CLI/native shortcuts.
PW-086: Post-QA defaults from the adopted plan: 2 conversation slots per CLI, 3 mission slots per CLI, 4 top-level missions per account, 12 per tenant.
PW-087: Interactive Main, user approvals, and exact controls share the high-priority lane; callbacks outrank normal missions. One shared persisted scheduler applies weighted account fairness. Queued capacity wait is not terminal after arbitrary fixed retries; do not create per-run retry timers.
PW-088: Resource guards: 64 child processes, 2,048 threads, and 2 GiB memory headroom. Mission execution never consumes the interactive lane.
PW-089: Root remains controllable if native child telemetry is missing. Project only genuinely observed session IDs, capabilities, child counts, and summaries.
PW-090: A root with known live child state becomes `settling`; unknown child state gets at most 120 seconds to reconcile, then shows explicit degraded truth. A valid `deliverable_ready` artifact may reach the user before process settlement, but the mission must not be presented as terminal until settlement is true.
PW-091: Stop terminates the root process tree. Direct child controls appear only after stable provider IDs and targeted control are proved. Roots cannot recursively use a GlassHive spawn API to create peer roots.
PW-092: Toggle server-side latency <100 ms. Focused-mode overhead <25 ms p95 with no extra network/model call.
PW-093: Active snapshot <50 ms p95 locally, 100 ms cold ceiling, with a two-second stale cache.
PW-094: Delegation target 150 ms p95 and hard release ceiling 250 ms after tool invocation, excluding harness startup.
PW-095: Direct, GlassHive-Codex, and GlassHive-Claude paths must each independently pass Intelligence/Relevance/Usefulness/Alignment.
PW-096: Roll out in bounded dark stages. Rollback stops new admission but never kills or hides existing work.
PW-097: Keep default focused and feature dark until every applicable release gate passes. Local override is visibly **PRE-GATE / NOT READY**.
PW-098: Minimum visible proof: two overlapping HTML Bees, quick Queen reply, one late-message revision, A-only Steer, B unchanged, two distinct files delivered once and opened separately.
PW-099: Also prove unhappy/recovery, duplicate/out-of-order, restart, owner isolation, capacity/provider/auth states, Voice, file/media, fallback, native children, callbacks, scheduler, and rollback.
PW-100: Correlate real Telegram Desktop, headed browser, audible Voice, logs, DB, missions, attempts/leases, callbacks/delivery, artifact hashes, generated config, component pins/builds, and installed process. Before agent sync, compare source/live A/B/C drift and validate the dry-run output.
PW-101: Canonical service interfaces are owner-scoped and service-authenticated: `POST /v1/delegations`, `GET /v1/active-work`, `GET /v1/work/{workRef}`, and `POST /v1/work/{workRef}/actions`.
PW-102: Active Work projects indexed current project/run truth, returns fresh/stale/unavailable, safe summaries, valid actions, cursor, overflow, and the full active roster through pagination. It retains actionable terminal failures until retry/dismiss and completed work until delivery acknowledgment or intentional-silence disposition.
PW-103: Main gets only two eager work tools—`active_work_list` and `active_work_action`. Low-level `worker_*` tools remain diagnostics/operator-only, not a competing public control plane.
PW-104: The LibreChat account proxy enriches GlassHive mission truth only with trusted origin and delivery truth. Core owns one `ViventiumExternalWork` relation containing opaque work identity, owner, logical-turn or schedule origin, `required`, delivery binding, external state, private IDs, configured destinations, and delivery state.
PW-105: Build one provider-independent, ephemeral `ViventiumDynamicTurnContext` before provider dispatch. Fetch roster in parallel; map it through each Main provider adapter; never rely only on a GlassHive header.
PW-106: The dynamic roster capsule is at most 16 KiB, prioritizes needs-input/stopping/recent work, includes overflow plus the list-tool path, and is injected only when Parallel is on, active work exists, or unread terminal work needs attention. Voice receives only active count and urgent attention until it asks for more.
PW-107: Dynamic work context is not persisted into conversation text, is excluded from native authority fingerprints, and does not trigger Phase-A activation. Static prompts stay cacheable; dynamic context follows the cached static prefix.
PW-108: Rollout order is L0 unflagged correctness; L1 dark secure control plane; L2 isolated parallel runtime; L3 product surfaces; L4 capability-gated native-team adapters; L5 full release/artifact proof. Codex production uses streamed `codex exec --json` with immediate `thread.started`; App Server stays QA-only. Claude uses proved worker-local background/Agent View, with process-owned `-p stream-json` rollback; cross-session messaging is capability-gated and Agent Teams remains separate/off. Each stage keeps existing work safe during rollback.
PW-109: Useful completion after the user moves on or archives the origin arrives once through a governed Main continuation. A deleted origin is never recreated; use one account-level continuation when useful.
PW-110: Callback-origin completion is not silently lost to short moved-on suppression or stream keepalive windows. Cards update immediately; durable adjudication decides sent versus silent.
PW-111: A recoverable structured bridge/provider condition remains pending and schedules durable follow-up even after the original stream closes; it must not flatten into a committed “Connection error.” One eventual recovery produces one final presentation.
PW-112: Telegram text, callbacks, voice, settings, captioned/uncaptioned attachments, and Active Work handlers remain nonblocking while Core preserves source order and idempotency.
PW-113: Native lifecycle projection uses actual run/session capability fields and ordered provider events—session started; child started/updated/stopped; team message. Codex streams `exec --json` and persists `thread.started` immediately. Claude exposes child truth only after the worker-local background/Agent View or process-owned stream-json probe passes; otherwise capability is false. Stream root output live, tee it to logs, and parse without inventing child truth.
<!-- VIVENTIUM-STABLE-REQUIREMENT-DECLARATIONS:END -->
