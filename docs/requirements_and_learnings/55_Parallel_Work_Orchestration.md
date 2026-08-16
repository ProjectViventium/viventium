# Parallel Work: One Always-Available Main, Many Durable Missions

Status: implementation in progress behind a dark availability flag. Do not expose or default on
until every release gate in this document and `qa/parallel-orchestrator/cases.md` passes on the installed
runtime.

Last revised: 2026-08-16.

This document is the product and implementation source of truth for Viventium Parallel Work. It
preserves the existing logical-turn, continuity, callback, scheduler, and GlassHive contracts while
adding bounded durable mission concurrency and provider-native worker teams.

## Product outcome

Viventium Main is one continuous user-facing consciousness that stays available while substantial,
independently completable work continues in the background. Main can answer quick follow-ups,
accept another objective, inspect every mission, and message, steer, pause, resume, stop, retry, or
dismiss exact work without becoming multiple competing authors.

The architecture has two levels and one durable control plane:

1. Main decides, within its existing inference, whether to answer directly, create a durable mission,
   add guidance, steer, or ask one focused disambiguating question. Runtime code must not classify
   intent with keywords, prompt matching, or fixed size thresholds.
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

## Current verified boundary — 2026-08-16

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
  mutation authority;
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

The exact public delivery stack now passes a clean-clone installer and runtime audit. Parent commit
`4a10643b911f147a917f2623b5e0d2e09308f82e` pins LibreChat
`2842e7b9534fb6ade7050d14f3a191c8caccfe00` and GlassHive
`6167132ad0aa1d8d6d30746fe9c9631f56310d9f`. The public installer reproduced those commits in a new
checkout, compiled the client and package artifacts, generated the configured local GlassHive API,
MCP, and operator origins, started healthy processes from that checkout, and exposed the deployment
as dark with a focused default. With no runtime-port override in the QA input, the compiler derived
the non-default API bind from the provider origin and an authenticated account-API read returned 200.
The run found and closed three startup credential/configuration
leaks before acceptance: interpolated custom configuration is no longer dumped, launcher status
reports credentials only as configured, and the compiler derives a LiveKit-only 64-character secret
instead of passing a potentially invalid call-session secret to the server. Recovery also remains
one-way: a derived LiveKit secret cannot be mistaken for the base call-session secret. The final scan
covered 13 persisted service logs plus the launcher stream and contained no configured credential
value, private instruction dump, or duplicate package-key warning. Teardown closed every isolated
listener.

A headed isolated Web drill also proves account preference enablement and reload persistence. When
deployment availability was disabled again, the toggle disappeared but an existing failed work card
remained visible and dismissible; Dismiss persisted after reload. This is truthful rollback evidence,
but not a full `PWK-032` pass because no provider-backed mission was already running and callback,
delivery, capacity-reduction, Telegram, and Voice parity were not exercised.

Current-candidate Telegram Desktop and audible Voice runs cover roster visibility, preference
persistence, Queue, Message, Resume, Stop, Dismiss, truthful unavailable Pause, call teardown, and
restart/reload persistence. Release remains blocked on provider-connected mission completion;
active-running Steer/Pause and lost-control recovery; scheduler delivery/adjudication; three-way
capacity, overflow, load, fairness, and latency; two-owner isolation; the remaining provider-backed
sandbox/concurrent-cap matrix; and rollback with running work. The deployment availability flag
therefore remains false and the default remains `focused`.

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
- Web reads and writes the same preference. Voice reads it and supports natural-language roster and
  control through the same eager tools; it never initiates an unsolicited call.
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

- `POST /v1/delegations`: atomically persist a delegation intent, project, worker, first run, and
  queued state. The trusted idempotency key is derived outside the model from tenant, account,
  source event, objective ordinal, and exact goal digest. Same key and content replay; changed
  content conflicts. Return `202 accepted|queued` immediately after commit.
- `GET /v1/active-work`: indexed, paginated snapshot with `fresh|stale|unavailable`, safe work,
  cursor, and overflow count. Unavailable is never represented as an empty roster.
- `GET /v1/work/{workRef}`: safe detail and native topology.
- `POST /v1/work/{workRef}/actions`: owner-scoped, idempotent, exact-work actions.

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
- Stream admission has a first-owner fence independent of the logical-turn receipt. A colliding
  client cannot win by reaching job creation second, and a stale/pre-fix receipt cannot return a job
  unless the persisted user and exact logical-turn/revision/source identity match. When an in-memory
  store is at active capacity it returns a structured retryable capacity condition; it never evicts
  a live generation or leaves its logical-turn indexes detached.
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
- Phase B is a presentation adjudicator, not an orchestration lane. Before provider invocation it
  removes `x-glasshive-bootstrap-bundle-b64`, `x-glasshive-bootstrap-timestamp`, and
  `x-glasshive-bootstrap-signature` by case-insensitive header name and supplies no tools. Mixed
  header casing must never preserve bearer authority.

## Exact action semantics

| Action | Required behavior |
| --- | --- |
| Queue | Persist a follow-up behind the current objective without interrupting it. |
| Message | Deliver noninterrupting guidance through a proven native live channel, otherwise queue it at the next safe boundary and report that truthfully. |
| Steer | Interrupt the exact active run and start replacement direction inside the same mission/workspace. Warm resume requires unchanged workspace, model, permissions, tools, and authority fingerprints. |
| Pause | Hold the objective and preserve workspace/session. The current run cannot remain falsely `running`. |
| Resume | Continue the paused objective without creating a competing mission. |
| Stop | Exact-work cancellation that preserves workspace. Return `stopping` until process/provider confirmation proves termination. |
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

- GlassHive outbox success means `http_accepted`, not user delivery.
- Core separately records callback persistence, target resolution, target enqueue, surface delivery,
  and acknowledgement. A terminal HTTP acceptance with zero resolvable targets alerts.
- Each terminal card is immediate. Useful terminal prose from the same account is coalesced for at
  most two seconds before Main authors it; callbacks remain individually durable and replayable.
- A terminal result becomes durably `sent` or intentionally `silent` only from the delivery ledger,
  never by interpreting generated prose or `{NTA}`.
- Recoverable Telegram transport/provider failure is provisional during the configured recovery
  window. Recovery produces one final answer and retracts/replaces stale failure; exhaustion produces
  one truthful terminal error.
- Telegram consumes the server's structured error class rather than substrings. A flattened bridge
  error never acknowledges the logical turn as committed; the durable follow-up poll survives the
  original stream ending and preemption of its in-memory insight listener.
- A schedule occurrence that launches required external work releases its scheduler lease and enters
  `waiting_external`. Acknowledgement delivery is not objective completion. One-to-many required
  missions gate the occurrence until every required mission is terminal.
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
Excess missions remain durably `queued/capacity_wait` until capacity, explicit Stop, a declared
deadline, or a real unrecoverable failure; a fixed retry count cannot turn capacity into failure.

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
context so every launch need not duplicate the full conversation. Main's persona/Feeling capsule is
not copied into specialist roots.

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

Broker grants are minted at execution admission, not while capacity-queued. GlassHive may
authenticate back to Core to revalidate the same live mission, owner, connected account, unchanged
scope, and approval state. Re-mint cannot expand scope. Revocation, missing approval, policy change,
or refresh failure moves work to `needs_input`. The authorization horizon remains 24 hours; later
continuation requires explicit authorized Resume.

## Rollout and completion gates

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
