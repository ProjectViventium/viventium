# Main Continuity Kernel

**Document Version:** 1.1-draft
**Date:** 2026-08-21
**Owner:** Viventium Core
**Status:** Required; implementation and real-user acceptance are in progress

## Purpose

Viventium Main must remain the same bounded cognitive system across normal chat, Telegram,
schedules, provider fallback, Phase B, and rapid turns. The same agent ID or model route is not
enough. Each logical turn must use one admitted context and capability snapshot, with durable
message ownership and honest dependency state.

This document records the complete public-safe requirement and repair plan from the August 2026
continuity investigation. The private source is identified as `MC-SRC-001`; its task history,
screenshots, prompts, and private runtime values stay outside this repository. Machine-readable
ownership and acceptance live in [`qa/main-continuity/contract.v1.json`](../../qa/main-continuity/contract.v1.json).

## Authored history and Continue source ownership

The current candidate projects persisted text content parts before the legacy `text` mirror. An
intentional empty edited text part remains empty; text-only rows still use their stored `text`.
Structured text values and completed tool outcomes retain the existing shared evidence projection.
Content-only edits therefore invalidate derived accepted history; receipts, activity, feedback and
token bookkeeping do not. Existing accepted-message IDs, positions, revision markers and retained
legacy artifacts are not rewritten. Current reads use the authored evidence; derived summaries must
still satisfy their existing source-digest checks.

Continue submits a normal new visible user turn after the selected assistant. It keeps the previous
response and native FINAL intact. The new native admission carries one optional directly referenced
parent proof captured from the raw history snapshot before mapping or attachment hydration. The
existing source transaction verifies the same current owner, conversation, parent identity and
authored evidence before admission and publication. Parent edits/deletes use the existing source
revocation and replay retirement owners. This does not introduce a whole-history epoch or a new
semantic routing policy. Old native admissions keep their original source digest and identity;
the new optional proof is never inferred onto retained history. Builds, configured-model behavior,
and real Continue/Stop/restart/reload acceptance remain separate gates.

Saved assistant replies with `finish_reason: incomplete` show **Stopped before completion** in
both message render paths once submission ends. The final accessibility announcement uses the same
localized wording. This presentation uses the existing saved reason, including empty and partial
replies after reload; it does not infer why generation stopped or claim that the user cancelled it.
Active replies, errors, normal completion, token limits and content filtering keep their existing
presentation. Content, attachments and Continue eligibility remain unchanged. Renderer and final
handler regression checks support this contract; real Stop, reload and Continue remain browser gates.

## Verdict

The incident was an AI continuity failure, not spoofing.

The schedules usually resolved the configured Main agent and current GlassHive route after the
route repair. They did not execute as the same cognitive Main. Conversation state, replay rules,
capability projection, recall health, native-session identity, and Telegram provenance diverged.

| Expected behavior | Observed behavior |
| --- | --- |
| A Main schedule is “Main later.” | `new` began with little recent Main context; `same` reused only the schedule-owned conversation. |
| A short reply retains its immediate referent. | Worker replacement and bad usage attribution caused a pruned three-message payload to be treated as a full replay. |
| Long histories remain bounded and useful. | Persistent sessions inferred replay from message counts and had no semantic compaction contract; some instructions reached hundreds of thousands of characters. |
| A Telegram reply has durable assistant ownership. | Quoted assistant text was appended to the user body, while direct schedule sends discarded returned Telegram IDs. |
| Recall supplements live continuity. | The RAG API could not authenticate to PostgreSQL. This made continuity worse, but it was not the primary cause. |
| Failure notices state the real next action. | A terminal recurring occurrence claimed it remained available for retry. |

These outcomes violate the same-Main, scheduler, Telegram, recall, and failure-truth requirements
already defined in `01_Key_Principles.md`, `03_Telegram_Bridge.md`, `11_Scheduling_Cortex.md`,
`20_Memory_System.md`, `32_Conversation_Recall_RAG.md`, `49_Prompt_Architecture_and_Token_Efficiency.md`,
and `55_Parallel_Work_Orchestration.md`.

## Root-cause chain

The August 15 cross-surface orchestration and persistent conversation-provider session changes
created the main regression boundary. The new provider layer:

- inferred full versus delta replay from a message count;
- treated mutable developer context as part of the persistent authority fingerprint;
- had no provider-neutral admitted-context object;
- opened independent overlap workers without a commit/reconciliation contract;
- built fallback input separately from the primary input;
- reported native retained-session usage as if it belonged to the current small user turn.

The exact terse-reply incident had a valid Telegram/Mongo parent edge. The provider received only a
small pruned message set, the usage record was grossly inflated, and GlassHive replaced the native
worker. The new worker then received that already-pruned set as a full bootstrap, without the
preceding assistant question. Worker churn and usage-scope corruption caused the amnesia together.

The older Telegram quote-flattening defect was not introduced in this regression window. The new
scheduler and session behavior exposed and amplified it.

The later forensic pass separated the two user-visible events that had initially looked like one
failure. The unexpected question was generated by an enabled Main schedule from that schedule's
saved prompt, through the configured Main Agent Builder route. It was not cross-thread prompt
leakage and it was not an isolated GlassHive worker. The defect was the next Telegram turn: Main
lost the scheduled-message referent and denied authorship instead of recognizing and explaining its
own scheduled output. Product fixes must therefore preserve the intended schedule and repair
provenance and continuity; disabling the schedule or changing its prompt would hide the defect and
remove requested behavior.

## Candidate status and remaining gaps

Incident-path status is `PARTIAL`. The exact final dirty source is registered and activated.
Focused automation closes the group or anonymous Telegram owner-boundary defect and StandardGraph
lost-final defect. A real headed-Chrome offline, resume, and refresh run closes the normal-chat
persistence slice. The exact natural Telegram reply passed on repaired pre-final source, but no new
Telegram generation ran after final activation. The broad Main Continuity program remains `PARTIAL`.

The local candidate now separates stable authority from mutable time, Feelings, Active Work, reply,
memory, and health state; queues overlapping visible turns on one conversation worker; reuses one
admitted instruction for serial fallback; persists request-scoped replay decisions; carries a
bounded owner-and-agent continuity capsule into new visible threads and Main schedules; preserves
typed Telegram reply provenance; records scheduled Telegram chunk receipts; and derives notices
from one Python/TypeScript failure contract. Exact structural schedule creation is also atomic and
idempotent, so future tool replays return the existing schedule instead of adding another copy.
The fingerprint uses authored schedule fields and meaningful user metadata, but excludes owned
runtime state such as recurrence outcomes, failure health, misfire context, lease heartbeats, and
temporary overlap deferral. Runtime execution cannot silently change the schedule's identity.

The first real scheduled-reply run exposed one additional admission defect. Core correctly resolved
the scheduled Telegram receipt, but only stored the reply capsule in the assembled developer
instructions. A resumed native conversation consumes fresh invocation context from the bounded
per-turn channel, so the native run received the terse user question and stale local ancestry but
not the current scheduled referent. The repair makes `ReplyContextV1` the highest-priority atomic
per-turn capsule. It remains separate from user text and persistent native-session identity. The
capsule has a 12 KiB provenance-first bound: attachment evidence text is removed before ownership
IDs or the current quote, and truncation is explicit. Active Work reserves the reply capsule bytes.
Lower-priority time, Active Work, and source-selection capsules are removed first if the shared
16 KiB turn-context budget is still exceeded. The encoded transport also has an explicit aggregate
request-head contract: Uvicorn's pinned h11 buffer and GlassHive's application guard are both
512 KiB, which is larger than the bounded 128 KiB bootstrap, 128 KiB developer-tail, 32 KiB
turn-context headers, and a 64 KiB envelope reserve. A lower runtime override makes GlassHive fail
closed and leaves the optional-service launcher visibly degraded. The application returns HTTP 431
above the aggregate bound, including the full request target and query string and when h11 receives
a complete oversized header event without first exhausting its incomplete-event buffer.

Approved live work on 2026-08-20 paused seven exact duplicate schedules without deletion, repaired
the existing RAG PostgreSQL role after a verified backup, activated the exact local candidate
through the supported developer-runtime path, and ran real private Telegram and non-admin browser
QA. The scheduled-reply defect reproduced before the last repair and passed after it: the same
Telegram question then referred to the scheduled output, while persisted provider evidence showed
the exact typed reply capsule and quote in the native delta instruction. A final restart also proved
20 KiB and 300 KiB request heads returned HTTP 200 while both a 550 KiB header and a 550 KiB query
returned HTTP 431 through the real GlassHive health endpoint, followed by successful Telegram and
browser continuity runs on the same process.

The 2026-08-21 candidate closed two further escaped boundaries. First, a reviewed authority or
model change could create a new physical GlassHive worker while retaining the logical provider
session and its accepted-message ledger. The worker still needs a bounded bootstrap, but those
accepted messages must not be claimed as new admission. `MainContextV1` now separates bootstrap
evidence from newly owned stable message keys. Second, a valid Main-to-specialist-to-Main graph can
invoke Main twice within one logical turn. The final Main invocation now continues the exact
completed graph family only when owner, logical turn, revision, advancement key, response key,
session, and base idempotency family all match. Changed inputs and unrelated key conflicts remain
closed.

The pre-P0 activated candidate then passed a natural user path rather than a marker-only probe. In
Telegram, Main performed a read-only connected-service readiness check, returned one useful answer
with no provider bubble or specialist prose, and made no external change. A terse follow-up kept the
same referent after an occupancy-driven physical-worker rotation. In Chrome, an unsent draft request
used that recent cross-surface referent, a terse follow-up named the intended service, and both turns
survived refresh. Mongo stored one complete, non-error user/assistant pair for each browser turn.
The first connected-service answer took about 57 seconds and the terse turns took about 10 to 18
seconds, so functional continuity passes while performance remains partial.

A later pre-final real browser pass exercised the actual in-process Main-to-Reality-Check-to-Main graph. It
completed three provider requests under one admitted snapshot, retained the specialist evidence,
and presented one Main answer. A separate parallel-comparison pass produced two participant-owned
Mongo text parts and two browser columns that stayed distinct after refresh. Those paths exposed two
last-mile persistence gaps: a visible delta arriving before its run-step could be pruned as ownerless,
and flat consumers joined multiple visible parts without a boundary. The candidate now retains the
first case as explicitly unowned, then reclaims it when the same stable run step gains its structured
owner. A StandardGraph can omit run-step ownership entirely, so persistence stamps that answer to
the graph's sole structural participant. This fail-safe is disabled for every multi-agent graph;
ownerless or specialist text cannot become Main text by default. These rules keep continuous text,
interleaved participant fragments, and split no-response markers intact. One shared visible-content
projection preserves real participant boundaries across the legacy message mirror, provider history,
resumable persistence, and recall without overriding an explicitly sanitized text. The repair passes
focused automation on the registered final dirty source; the personal corpus was cleaned instead of
receiving another synthetic live write.

The exact final dirty source and client build were then activated through the supported runtime path.
In an isolated real headed-Chrome run, a normal Main request went offline while the backend completed,
recovered the final answer without reload, cleared Stop, showed one assistant with no phantom branch
or provider error, and kept one assistant plus the Stop-flow partial after refresh. The live recovery
replayed `FINAL`; exact lost-terminal/404 stays automated-only, and provider abort/tombstone remains
partial or unrun. The exact natural Telegram reply-object pass occurred before the later browser-only
liveness edits. It and its voice output stayed visible after final restart without an error bubble,
but that persistence inspection is not a new final-source Telegram generation.

The following gaps remain:

1. Semantic compaction now has structured, isolated execution and has produced a real accepted
   summary while preserving the three recent turns. Acceptance remains partial until the complete
   pending-ask, commitment, correction, identifier, recurrence, and tool-pair field matrix passes.
2. Stable visible-message admission, accepted/reserved ownership, logical-turn revision checks,
   atomic request/run attachment, and completed-before-acceptance restart reconciliation pass the
   186-case provider/store suite. A forced full process crash during native execution remains unrun.
3. One same-epoch compact-and-retry followed by fail-closed overflow passes automation. A forced
   live provider overflow remains unrun.
4. `RecurrenceStateV1` is implemented and has passed a real recurring Main schedule. Multipart
   delivery crash windows and long manual-versus-scheduled overlap remain partial or unrun.
5. The RAG authentication fault is repaired in place and health plus retained data pass. Grounded
   older-fact retrieval and every unavailable-state variant on a real user surface remain unrun.
6. Seven reviewed exact duplicate schedules remain paused with history. One protected Main
   presentation-policy/graph change and its Connected Accounts return edge were reviewed and
   applied. Fourteen unrelated live-agent drifts remain intentionally untouched.
7. The supported local runtime, helper binding, source checkout, services, Telegram, and browser
   now exercise the changed source. Nested repositories remain dirty and uncommitted, so parent-pin,
   clean-build, install-from-clean-clone, and release-artifact parity remain open.
8. Primary-to-direct fallback carrier parity passes automation, but a forced live configured
   fallback and exact Phase-B snapshot/capability parity remain unrun.
9. Group or anonymous Telegram provenance passes focused final-source automation. Real unknown,
   deleted, foreign, forged, group, and multipart provenance; repeated same-root failure coalescing;
   a full mid-run process crash; and a 100-plus-turn real-surface soak remain open.
10. `MainContextSnapshotV1` still does not represent every memory, recall, Feelings, Active Work,
    recurrence, tool-schema, input-budget, and output-reserve field as one complete typed admission
    contract.
11. Replay and request headers are bounded, but one observed long native binding reached about
    558,000 prompt tokens before occupancy rotation. The next approximately 30,000-token bootstrap
    stayed coherent, but the rotation did not use an accepted semantic compaction. This is a direct
    performance and long-horizon acceptance gap.
12. The first natural connected-service answer took about 57 seconds, and a simple browser turn
    still assembled tens of thousands of instruction tokens. The result quality passed, but the
    user experience does not yet meet the fast-and-smooth side of the outcome metric.
13. The shared scheduled-failure contract is versioned and has a safe embedded server fallback,
    but it is not generated or release-chain validated yet.
14. Memory Hardening is now healthy after the naturally due configured primary route completed.
    This closes the former execution-mismatch gap but does not substitute for the continuity cases
    above.

The same evidence pass found two narrower scheduler/Workbench defects and repaired them without
changing any user prompt or removing a schedule:

- managed memory-off Workbench schedules could retain an obsolete host execution mode after the
  isolation policy changed. Startup reconciliation now recomputes the governed mode and clears a
  host workspace root when the effective mode is Docker. A real existing managed schedule then ran
  in Docker, completed, imported its validated artifact, and remained correct after UI reload;
- `Run Viventium Main` updated only task-level last-result fields, so a successful manual delivery
  could leave an older failed run visible in Workbench. It now creates a durable
  `manual/workbench_manual` receipt before dispatch and closes that same receipt from the canonical
  channel outcome. The receipt ID is also the occurrence and provider idempotency key, so Core,
  Telegram chunk delivery, and Workbench refer to one logical run. Manual receipt creation and
  scheduled occurrence claiming share one atomic task lease, so a run started just before its
  scheduled time cannot author concurrently with that occurrence. The lease renews during local
  dispatch, stays held for queued or `waiting_external` work, and is forcibly cleared by every
  terminal state. A blocked automatic occurrence is kept as an internal deferred occurrence and
  runs once after the blocker closes instead of disappearing at the misfire boundary. Startup
  recovery closes stale `claimed`, `dispatching`, `queued`, `running`, and `waiting_external`
  receipts after the configured recovery window. Workbench and the scheduler now use one shared
  state-root-aware database resolver, so standalone or development starts cannot silently create
  separate scheduling ledgers. One
  real run completed as
  `silent`/`nta` and remained visible after reload. A second real run completed as `delivered`,
  persisted one sent Telegram message ID with schedule/run linkage, and its natural Telegram
  follow-up recognized the output as Viventium's own automated message. The exact active
  Workbench-defined Main schedule was then run with its real registered prompt and configuration;
  it completed `silent`/`nta`, retained the bound receipt across reload, and produced no Telegram
  failure or noise bubble. After a restart, a real one-time scheduler occurrence used
  `viventium_agent`, delivered once to LibreChat and Telegram, persisted one sent Telegram receipt,
  cleared its lease, and deactivated itself. A natural Telegram follow-up correctly identified the
  message as scheduled QA instead of denying authorship. The full defer-after-long-overlap branch
  remains automated acceptance, not a claimed live user-path pass.

## OpenClaw evidence and boundary

Official OpenClaw upstream was fetched as a read-only reference. The original forensic comparison
used commit `267ffc4754a08181f1a15ff7cfbd0f4d817ca25a`. Upstream was refreshed on 2026-08-20 to
`a434545620127a3105699513d662395a43b43eb1`. No OpenClaw commit was merged.

Useful invariants are:

- owner-scoped Main continuity is distinct from isolated automation;
- system activity does not reset user-interaction continuity;
- compaction, recent-turn preservation, and tool-result pruning are separate operations;
- compacted summaries persist while recent turns remain intact;
- overflow compacts and retries once, then fails closed;
- typed reply ancestry stays separate from user-authored text;
- durable admission and recovery use exact persisted state, not partially hydrated projections;
- successor reply admission can continue while an exact failed turn is recovered separately.
- current-session scheduled results commit through the canonical chat writer with an idempotency
  key before success is reported;
- setup and installation do not report success until the destination state has been verified;
- explicit harness selection and session metadata survive repair and list projections.

Wholesale import is rejected. Viventium has different authority, Agent Builder, scheduling,
GlassHive, memory, recall, Feelings, and delivery contracts. The invariants inform the design; the
code does not become a second runtime.

## Ranked options

| Rank | Option | Decision |
| ---: | --- | --- |
| 0 | Preserve and reconcile the current candidate before broader changes. | Mandatory prerequisite. |
| 1 | Add a Viventium-native Main Continuity Kernel. | Selected. |
| 2 | Patch only Telegram, schedule delivery, and notices. | Required early slices, but incomplete alone. |
| 3 | Import OpenClaw. | Rejected because the architectures and fork histories differ. |
| 4 | Start more fresh sessions and inject more history. | Rejected because it increases amnesia and context growth. |

## Required architecture

### One context owner

LibreChat owns context admission after tools, saved memory, recall state, Feelings, schedule state,
and reply provenance are resolved, and before a provider, fallback, Telegram, voice, or GlassHive
adapter is selected.

For each logical turn it creates one immutable `MainContextSnapshotV1` with:

- owner and continuity-domain IDs;
- logical-turn ID and accepted parent/reply relation;
- stable-authority epoch and fingerprint;
- admitted visible turns and persisted compacted summary;
- current saved-memory profile and explicit recall health;
- current Feelings and Active Work context;
- capability ceiling and tool-schema digest;
- scheduler/recurrence context when applicable;
- byte/token budget, output reserve, and projection digest.

Primary, fallback, retry, and Phase B must use the same snapshot digest and cannot increase its
capability ceiling. Primary and fallback carrier reuse is proven by automated `chatCompletion`
wiring; a forced live fallback and Phase B parity remain acceptance gaps. A changed Agent Builder
configuration creates a new authority epoch. A stored provider session is execution state only and
never overrides Agent Builder.

### Stable authority versus per-turn context

Stable agent instructions, policy, tool schemas, declared capabilities, workspace/access binding,
and native provider policy may replace a worker binding. Time, Feelings, Active Work, schedule
metadata, current memory/recall health, and other invocation state travel as per-turn context.
Selected visible ancestry owns native conversation history; a sibling branch cannot inherit
excluded native answers just because the conversation ID is unchanged.

The system must compare exact declared fields. It must not branch on agent names, provider labels,
prompt words, or user identity.

### Explicit replay and compaction

A compaction retry carries the exact rejected candidate together with its typed rejection,
any existing validation or fidelity reason, and the unchanged accepted source. The candidate
remains untrusted repair data. A repaired result must still pass the same size/schema and source-bound semantic review
before promotion; failed attempts never replace accepted history.

A new generation must still carry its current visible turn when source-history deduplication has
already admitted that turn. This also holds when the delta includes newly observed historical
messages: historical answers must not replace the current request. Regenerate does not create a
second accepted source event; request idempotency continues to fence retransmissions of the same
invocation. When Core's typed visible
chain excludes the prior native response and requests a different authored response, the existing
worker starts a native bootstrap from the selected visible history. A private native context epoch
binds the resumed session handle and replay advancement to that branch. The new handle persists
atomically and survives process restart. Same-response graph consultations and ordinary next-turn
chains keep their native context; an active run rejects a conflicting branch change. This never
terminates the worker, revokes its links, disables its schedules, or rewrites accepted user sources.
Legacy callers without Core lineage retain their existing session behavior.

`ReplayDecisionV1` replaces inference from `len(messages)` and declares:

- `mode`: `bootstrap` or `delta`;
- `contextEpoch` and `stableAuthorityDigest`;
- `snapshotDigest` and admitted section IDs;
- input byte/token budget and output reserve;
- protected current turn and last three conversational turns;
- paired tool-call/result preservation;
- summary version and compaction watermark;
- usage-accounting scope.

Initial gates are:

- a bootstrap uses at most 50% of the provider context window;
- compaction begins before 70% projected occupancy;
- old, large tool results are pruned before conversational turns;
- the current turn and last three conversational turns remain intact;
- summaries preserve pending asks, commitments, corrections, durable identifiers, schedule
  outcomes, and paired tool calls/results;
- compaction is persisted, auditable, and rejected when the summary is invalid;
- semantic fidelity is model-judged against the accepted source, including permission, polarity,
  quantities, attribution, uncertainty, pending work and later corrections; lexical overlap is
  not approval;
- a fresh summary is reviewed after structural normalization; acceptance binds the review to both
  the source digest and exact candidate digest, and rejects stale or mismatched approvals;
- rejected or unavailable review keeps the pending source. Render whole reviewed summaries and
  pending source blocks; a context-budget omission must be explicit, never a sliced statement;
- original accepted text and tool results remain in the native owner-scoped Message store. The
  continuity ledger retains source references, not a clipped alternate transcript. Context loading,
  compaction claims and summary acceptance resolve the exact current owner, conversation, agent,
  parent and revision; missing or changed source cannot fall back to a stale snapshot;
- pending references are retained through failure and restart until their exact reviewed batch is
  consumed. Process the oldest whole-turn prefix under the existing compaction input envelope;
  no turn-count eviction may discard unreviewed source. A single larger turn goes whole through
  the existing provider budget/error handling, and remains pending on budget failure;
- the three protected recent turns remain whole. The capsule's older-evidence allowance must not
  become a text-clipping rule for recent instructions; the existing admitted/provider context
  budget still owns overload and its truthful failure behavior;
- automatic accepted-turn compaction batches while all pending source remains intact in the existing
  carrier, then starts at its slot or byte pressure boundary. Explicit compaction stays immediate;
- overflow performs one compact-and-retry with the same authority/capability ceiling;
- observed characters per token are calibrated per binding;
- native cumulative usage is not assigned to one current message;
- fallback never builds a separate uncapped history prompt.

The candidate compaction prompts are owned by `main.continuity_compaction` and
`main.continuity_compaction_review` in Prompt Workbench. Both use the configured Main primary and
fallback route with tools, recall, saved memory and Feelings isolated. A missing compiled prompt
fails explicitly. The fidelity review runs only for compaction proposals. Its behavioral acceptance
requires the calibrated exact-model evaluation in requirement 49, separate from deterministic
source/candidate fencing, restart, concurrency and rendering tests. Candidate implementation and
local model evaluation do not close `MC-008` or the real long-conversation journey.

### Scheduling is Main later

- `viventium_agent` joins the owner-scoped Main continuity domain.
- `new` and `same` keep their visible-conversation meanings. They do not control cognitive
  continuity.
- Trusted scheduler envelopes use internal visibility and cannot enter UI, recall, or saved memory.
- A useful result becomes an ordinary assistant message with durable provenance.
- Every manual Main run creates a durable pre-dispatch receipt, uses that receipt as its occurrence
  and provider idempotency key, holds the same task exclusion lease as a scheduled occurrence, and
  closes the same receipt from its canonical channel outcome, including `silent`/`nta` and
  `delivered` Telegram results. Active leases renew; queued and external work retain ownership;
  terminal states always clear ownership. An automatic occurrence blocked by Run Now is persisted
  as an internal deferral and runs once after the blocker closes. Stale active states reconcile to
  a visible terminal failure after the configured recovery window.
- `glasshive_host` and explicit isolated work stay isolated but receive one bounded authorized
  snapshot and return a typed outcome.
- Recurring work persists `RecurrenceStateV1` with the last outcome, freshness, next intent, and
  compact state, rather than replaying repeated prompts.

### Telegram provenance and delivery

Generalize the existing delivery ledger. Each logical assistant message has one or more durable
transport receipts, including all Telegram chunk IDs, the owning chat, surface, schedule/run when
applicable, and a receipt version.

Ingress resolves `ReplyContextV1` server-side from authenticated owner, chat, and Telegram message
ID. It includes bounded ancestry, logical message/turn, schedule/run, sender role, timestamp, quote,
and attachment descriptors. The new user body remains separate. Local current-chat evidence
outranks stale ancestry. Unknown, deleted, foreign, or forged provenance yields “cannot verify” and
never a denial, spoof claim, or cross-owner lookup.

Transport retries resend the accepted rendered result. They never regenerate the AI turn.

### Governed rapid and parallel turns

Independent heavy work delegates to background workers. Rapid corrections coalesce or supersede
before authorship when safe. An unavoidable sibling uses the same immutable snapshot, has a TTL,
and can commit only through deterministic accepted-turn ordering. It does not become another
unreconciled Main.

Existing native tools, connectors, owner-scoped workspaces, refresh/resume, and worker autonomy must
remain available.

### Recall and memory truth

Recall supplements the admitted live thread; it never replaces it. Health distinguishes healthy
empty, unavailable, authentication failure, timeout, stale corpus, and source-only degraded mode.
The RAG credential must be repaired in place without deleting the vector volume. Internal scheduler
content cannot become owner memory. A pre-compaction memory flush is nonblocking. Main still answers
coherently from live continuity when recall is unavailable.

### Failure truth

Python and TypeScript consume one versioned closed failure contract:

- `failure_class`;
- `retryable`;
- `retry_disposition`: `retry_scheduled`, `next_occurrence_only`, `paused`,
  `terminal_action_required`, or `no_retry`;
- `next_attempt_at`;
- `action`;
- `coalescing_key`;
- `consecutive_count`.

Visible wording is derived from the actual transition. Same-root incidents coalesce. A useful
fallback or Phase B answer is never hidden by a generic failure bubble. Auto-pause after three
same-root recurring failures is a proposed reversible policy and needs explicit live-operation
approval before it is enabled or applied.

## Delivery order and approval boundaries

1. Capture exact source, dirty diff, nested pin, built artifact, installed artifact, running process,
   scheduler, recall, and memory-hardening identities.
2. Preserve the valid time, token-accounting, graph-handoff, fallback-boundary, Active Work, and
   receipt changes already present; revalidate them instead of duplicating them.
3. Land the shared contracts and machine-readable ownership graph.
4. Make stable-authority comparison exclude declared per-turn context.
5. Add explicit admitted snapshots, replay decisions, bounded bootstrap/delta behavior, exact
   fallback reuse, and semantic compaction.
6. Route schedule results through durable delivery and add typed Telegram provenance.
7. Join Main schedules to the continuity domain and add compact recurrence state.
8. Govern overlap, coalescing, and accepted-turn commit.
9. Repair recall credentials in place and diagnose memory-hardening execution mismatch.
10. Reconcile source, pins, builds, installed runtime, restart, and persistence.
11. Run the complete acceptance matrix and an independent review.

Code, public-safe docs, synthetic tests, and side-by-side local development QA can proceed without
a live-state approval. The following stay fail-closed until a reviewed dry run is presented:

- pausing duplicate/noisy schedules;
- synchronizing live agents with protected live/source drift;
- modifying production credentials or database roles;
- restarting or promoting a user-facing installed runtime;
- sending Telegram QA to any real contact.

Schedules are paused, never deleted. Recall data volumes are preserved. Real-contact Telegram QA is
forbidden; use only a synthetic/private approved test chat.

## Line-by-line source coverage

`MC-SRC-001` is the private 135-line incident plan. These ranges account for every material line;
blank lines and Markdown separators are grouped with their enclosing statement.

| Source lines | Public requirement or disposition |
| --- | --- |
| 1–7 | Verdict and compound cognitive-continuity diagnosis. |
| 9–18 | Expected/observed matrix and violated owning requirements. |
| 20–28 | Regression boundary, owning provider/session changes, valid partial repairs, and latent Telegram defect. |
| 30–38 | Terse-reply evidence chain: valid parent, bad usage scope, pruned payload, worker replacement, lost referent. |
| 40–47 | Mutable authority, overlap, fallback, schedule continuity, delivery-ID, and typed-reply gaps. |
| 49–53 | OpenClaw is a pinned read-only reference, not an import. |
| 55 | Owner-scoped Main and explicit automation isolation inform the continuity domain. |
| 56 | Mutable fingerprints must not replace native sessions. |
| 57 | Main reminders/schedules must join Main continuity. |
| 58 | Fresh sessions use bounded calibrated context, not repeated full near-window history. |
| 59 | Admission, compaction, recent-turn protection, tool pruning, and memory tiers stay separate. |
| 60 | Telegram uses typed bounded ancestry; quotes are not user text. |
| 62–70 | Ranked options and decisions are preserved. |
| 72–75 | Phase 0 and Main Continuity Kernel v1 form one delivery program. |
| 76–81 | Preserve candidate; pause only after approval; repair RAG in place; reconcile pins/artifacts; restore hardening. |
| 83–87 | LibreChat is the provider-neutral owner; one immutable snapshot serves all authoring paths. |
| 89–93 | Stable authority is separate from invocation context; Agent Builder remains authoritative. |
| 95–98 | ReplayDecisionV1 is explicit and fail-closed. |
| 99–107 | Bootstrap, recent-turn, tool-pair, semantic-summary, occupancy, calibration, and fallback gates. |
| 109–115 | Main-later scheduling, internal envelopes, useful-result visibility, isolation, and RecurrenceStateV1. |
| 117–121 | Durable 1:N Telegram IDs, ReplyContextV1, separate user body, and cautious unknown provenance. |
| 123–125 | Delegation, coalescing, bounded siblings, TTL, and deterministic commit. |
| 127–129 | Generated failure truth, transition-derived wording, coalescing, optional approved pause, useful-answer precedence. |
| 131 | Real-surface acceptance and 100+ mixed-turn soak are mandatory. |
| 133 | Independent review must challenge the architecture and implementation. |
| 135 | The forensic phase changed no product/live state; later status must distinguish investigation from implementation. |

## September candidate: source retention and semantic compaction

The current local candidate retains original accepted source in the existing native Message store.
The continuity state keeps owner/agent/conversation/message references, logical-turn revisions,
accepted order and scheduler provenance. It does not persist a second clipped transcript. Context
load, compaction claim and promotion resolve those references under the owning user and conversation;
missing, edited, deleted, foreign, mismatched or superseded source prevents stale promotion.

The accepted source merge preserves chronological correction order around existing Message anchors,
including partial pairs; current same-ID content remains authoritative. The post-pruning callback
checks protected Message IDs, roles, complete content digests and relative order on every route.
The native serialized-body guard remains an additional transport check.

Delivery acknowledgement still owns delivery. Hidden server-owned markers on the existing assistant
Messages carry accepted position and logical revision. One small domain record in the existing
continuity collection serializes acceptance across all real configuration epochs. Each epoch owns
only its derived summary, source-generation watermark and compaction lease. Maintenance timestamps
never order accepted history. Promotion writes the domain control, native source Messages and
Conversation in the same short transaction as its final source check and epoch CAS.

The initial root assistant placeholder records the authored Main agent and authority digest captured
before prompt assembly or native dispatch. Its trusted write option binds that identity to the exact
root response ID and authenticated owner; separate worker and follow-up bubbles cannot acquire it.
Ordinary Message saves, edits, bulk writes and metadata-parent changes preserve this reserved stamp
inside the existing mutation transaction. Context loading and fallback use the same captured
identity. Restricted voice turns cannot stamp or schedule accepted-turn compaction. Native final
recovery retains an existing stamp; historical unstamped responses remain unattributed rather than
being assigned the current configuration.

Explicit source changes advance the domain generation and invalidate derived summaries. Both source
Messages participate in acceptance. Actual hard deletion retains a per-logical-turn revision floor
in the existing continuity collection; floors stay outside model context. Missing reads never prove
deletion. Indexed Message history and separately keyed retirement floors replace lifetime arrays in
active epoch records. Retention must keep floors while older saved presentations remain eligible.
System receipts and bookkeeping do not change accepted source generation; source hydration and
invalidation share the same effective text and completed-tool-result projection.

Legacy continuity rows remain immutable typed evidence. Each real epoch reconciles them independently,
using original native source when available and retaining uncertainty where historical coverage is
incomplete. All retained legacy revision fields contribute to stale-replay rejection, including
pending/recent references after the old bounded revision cache evicted an entry. Proven retirement
is distinct from unproven missing source. Artifact order never grants chronology or permission.
The existing epoch cursor now includes a source offset. Each claim reads at most 64 reference
positions from one immutable artifact, then selects a whole-turn prefix under the existing source
target. The lease binds the exact artifact/range/total; completion rehydrates that same range.
An unproven missing reference stops progress before its position, including after reload. A proven
retired-only range can advance without a model only when it has no historical semantic artifact;
even a later range with a retained historical summary still requires reconciliation. No epoch
consumes another epoch's migration evidence. A single indivisible turn can still exceed an actual
provider budget; failure retains it rather than inferring deletion or advancing the cursor.

Compaction uses the owning Workbench generation and review prompts on the exact configured Main
route. The reviewer receives the complete claimed source and final prepared candidate. It judges the
candidate as replacement context: unfinished accepted work needs usable task input, not only a
description of the task. Wording, values or structure under examination remain available without
promoting quoted material into authority; faithful paraphrases and omission of irrelevant examples
remain valid. Runtime acceptance binds both digests and the active lease; semantic judgment belongs
to the model. A
negative or unavailable review retains pending references. The reviewed summary is delivered whole
or marked unavailable, and cannot consume its source if it cannot fit the current context carrier.
Runtime no longer extracts and auto-adds reference-shaped text to the proposal. The model preserves
material references, links and prior valid state; the existing validator enforces structural limits
and supplies those same limits and precise rejection details to the owning Workbench prompts.
Meaningful references can remain verbatim in category text within the existing limits. This change
does not relax Message identity, source/candidate digest, source-generation or authority checks.
Hydration queries execute sequentially when they inherit the acceptance/promotion Mongo session.
Retained visible scheduled results can recover their origin from an internal parent only when its
server-owned actor, conversation, logical turn, revision and schedule/run identities match. The
parent stays internal and contributes no user-authored text or permission. Explicit conflicting
provenance and missing or mismatched identities remain unavailable; stored history is not rewritten.

Accepted-turn compaction defers while every retained pending turn and the prior summary fit intact
in the existing protected Message carrier and reference/summary capsule. Explicit compaction remains immediate. Claims process the oldest whole-turn
prefix with an 80 KiB source target; an indivisible larger turn is supplied whole to the provider,
whose actual input budget remains authoritative. Promotion advances only the claimed prefix watermark; it does not delete native source Messages. The
former 5 KiB accepted-text clipping, 64-pending-turn eviction and 96 KiB compactor clipping are
removed. Provider failure preserves the native source references and records degradation; this is
not a successful semantic-continuity result.

This candidate remains partial. Deterministic source/lease tests, exact-model role evaluation,
provider-route evidence and real browser/Telegram continuation are separate gates. In particular,
whole recent source enters the existing message body with original Message IDs; the turn-context
capsule carries references and semantic state without duplicating raw source. A run-local model
callback checks source after graph pruning. Native transport carries its final identity manifest
in existing request metadata, bounded by the actual message count, and checks final serialized
source before dispatch. Native admission preserves protected source or fails truthfully at its
input budget. These structural checks do not prove a successful later Main turn on a real surface. Original eight-pair model
labels are provisional and model-reviewed, with human calibration still open. Existing historical
source already lost by an earlier candidate is not reconstructed by this change. The remaining
long-horizon, restart, fallback, carrier and real-surface requirements below remain required.

## September candidate: interrupted direct Main completion

An API restart must not discard a completed native Main response or repeat its native work.
The candidate binds the exact serialized request body and hydrated native authority to the
original owner, source Message, response Message, stream incarnation, and logical revision.
GlassHive commits one canonical completion with its terminal state. Its authenticated result
lookup reads that saved artifact only; it cannot start a fallback, healing pass, or native turn.
Failed, cancelled, missing-artifact, and host graph tool-call outcomes are not successful Main
answers. The existing reconciler may repair a completed record with a retained completion
contract; read-only result lookup does not perform that repair.

The host prepares a private candidate on the existing assistant Message in a transaction that
also checks and writes its actual persisted source. The existing Redis logical/source slot
owns one immutable publication digest with a fixed 24-hour deadline. Stop can revoke that
authority before a Message admission exists. Source edits and deletes use the same source
transaction and publication authority. An edit after accepted publication can preserve only
that exact historical candidate; explicit assistant edits and deleted rows cannot be recreated
or overwritten by recovery. Actual Message persistence precedes final replay or delivery
acknowledgement. The delivery adapter still owns its acknowledgement.

Existing job cleanup and stale-message recovery retain eligible native admissions until the
same fixed deadline. The existing recovery pass reads native results and materializes the saved
candidate; it adds no queue, database, producer heartbeat, or model replay. Current owner, agent
access, configured provider capability, and original endpoint origin must still be available.
In-memory job stores provide live-process behavior only and cannot recover a host restart.
When an admitted native response hands back to an ordinary host graph or declared fallback,
the exact revoked binding releases its existing Redis job to the configured running TTL.
Cleanup respects that renewed key expiry; immutable job creation time is not a second execution
deadline. The age failsafe applies only to old jobs missing an expiry, and deletion atomically
rechecks the same job incarnation, running state, and missing expiry. Cleanup cannot remove a
replacement or a concurrently renewed job. An already-expired handoff remains unavailable;
recovery does not recreate it, extend its authority, or repeat the completed provider work.
Periodic recovery avoids a live local producer; cross-replica final/memory timing still requires
independent review and real deployment evidence.

When a new logical revision reuses a conversation's stream ID, the manager captures and
retires the old job before storing the replacement or attaching its abort listener. Old
presentation and cancellation events cannot target the new incarnation. This applies to
ordinary follow-ups, corrections and Regenerate through the same lifecycle owner.

An open browser also retains the accepted submission during transport loss. A successful HTTP
EOF without `FINAL` and a network failure with buffered SSE bytes use the existing reconnect
owner. Exhausted transport attempts do not become an assistant error or remove the accepted job.
The existing active-job query resumes the exact running stream only after a fresh successful
registry result; a successful exact disappearance refreshes canonical messages and releases the
composer. Failed or unreadable registry results are not empty results. The server derives exact
stream/conversation pairs from its existing owner index and current running job rows. Navigation
and accepted `FINAL` close the subscription without reconnecting or starting another model turn.
Actual open-page recovery through an API interruption remains a separate browser gate.
Native completion recovery also reuses the normal typed harness-activity conversion before
materialization and transmission. A positive native admission authorizes this projection; normal
non-harness responses keep genuine reasoning parts. The immutable provider candidate and digest,
answer text, attachments, cortex contributions and delivery metadata remain unchanged. Previously
completed records are not rewritten; their legacy public-read projection is a separate open gate.

This candidate covers direct interactive Main results. Host graph continuation recovery remains
explicitly unsupported. Deterministic native, Mongo, and job-store checks are supporting evidence.
Real API-interruption, Stop/edit/delete races, reload, and channel-delivery acceptance remain
open under `MC-036`; this section is not a shipped or complete recovery claim.

## Acceptance

Completion requires all generated cases in `qa/main-continuity/generated-coverage.md` to have fresh
evidence. At minimum:

- real Telegram scheduled and ordinary reply ownership, terse reply, multi-chunk, unknown/foreign,
  forged, and group-message injection cases;
- Main `new` and `same`, isolated GlassHive, recurrence, one-time/recurring retry, restart, and
  duplicate-suppression cases;
- browser normal chat, rapid revision, background work, Active Work/result, expanded details,
  refresh, and persistence;
- healthy, unavailable, auth-failed, timed-out, stale, source-only, and recovered recall states;
- new native-session bootstrap, session delta, authority epoch, fallback digest equality, overflow
  compact-and-retry, semantic-summary validation, and no unexpected worker replacement;
- 100 or more mixed interactive/scheduled turns with bounded instructions, correct attribution,
  stable bindings, accepted-turn-only advancement, and no duplicate internal envelopes;
- nested tests, parent pin, built artifact, installed process, dev/prod isolation, restart, and
  public/private scan;
- independent review after the proposal and after implementation.

Mocks, unit tests, database rows, or logs cannot replace a required user path. Until those paths are
run against the exact installed candidate, status remains partial and the repair is not complete.

<!-- VIVENTIUM-STABLE-REQUIREMENT-DECLARATIONS:START -->
## Stable requirement declarations

Each line is the canonical public owner declaration for one stable requirement ID. Detailed sections supply implementation context; they must not narrow or contradict these declared outcomes.

CC-006: Ship the continuity opportunity and the shared logical-turn contract together because both preserve one Main across time and interruption.
CC-052: Keep credential, provider, unsupported configuration, timeout, confirmation, healthy-empty, and rejected states distinct. Repair shared transport; do not add continuity-only exceptions.
CC-064: Update the existing private continuity source document, preserve superseded history, and append byte-exact user messages with stable IDs and SHA-256. Public docs retain only sanitized aliases, coverage, and decisions.
<!-- VIVENTIUM-STABLE-REQUIREMENT-DECLARATIONS:END -->


### Direct incomplete parent in per-turn context

An assistant parent with persisted `unfinished: true` and `finish_reason: incomplete` contributes only
its message relationship and those literal status fields to the existing current-turn context. The
host captures this fact from the same authored history read as native parent evidence, before provider
formatting removes empty or Activity-only content. This fact does not claim that background work was
cancelled. It does not copy private native admission fields, Activity, or the prior goal. Completed,
missing, user-authored, and unselected rows do not contribute an incomplete-parent fact.

### Upstream terminal recovery

Provider fallback wrappers preserve the SDK's dynamic property accessors. A handoff or native compaction can invalidate the cached system context; the next invocation must obtain the refreshed context rather than replay a first-call snapshot. An empty-content graph transfer still carries the SDK's current handoff state, with exact retransmission and configured graph limits unchanged.

When a completed Phase B answer replaces an empty failed Main message, the existing promotion owner clears the message error flag with the visible error parts. The original failure remains in recovered-error metadata and native result records. Startup recovery also repairs a stale flag when that exact typed promotion already recorded the recovered error; it does not clear unrelated failed messages.

A failed pre-dispatch admission revokes its native authority. If a fresh read proves no
native admission was persisted, release the exact job binding through the existing unsupported
handoff so normal error delivery can finish the stream. An uncertain persisted admission stays
fenced; cleanup must not authorize ordinary publication over a recoverable native result.

An exact native result that reports failure or cancellation must publish a durable error FINAL and release the current conversation composer. The existing Message admission stores a distinct terminal snapshot marker; it does not assert user Stop or successful Main delivery. Saved terminal content uses the normal public error renderer and audio suppression. Recovery reuses that snapshot and the existing job FINAL, without another model invocation, memory admission, title generation, or continuity-success acknowledgement.

Legacy unmarked terminal admissions are discovery candidates only: the existing current-job identity check rejects retired jobs before provider lookup, and the Mongo transaction verifies current source/parent evidence before accepting the authoritative terminal result. Explicit edits and deletes retire terminal replay; ordinary background augmentation preserves canonical text, error state and delivery disposition.


Native response recovery scans the existing query through Mongo's batched cursor. A full batch of
retired or locally running admissions cannot hide newer recoverable work. The existing typed
recovery service shares one in-flight scan per process, closes its cursor on completion or failure,
and retains exact current-job, source and publication checks for every row. No persisted paging
state, extra timer or retired marker is required; ordinary list callers retain their default limit.

When accepted source hydration meets the selected current user input, it must not restore an
excluded prior assistant answer to that same input. Regenerate keeps the original request as the
current turn and preserves its selected branch. Historical partial source pairs still hydrate
before the current input; the final carrier retains exact source identity and content checks.
