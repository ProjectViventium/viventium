# Main Continuity Kernel

Active owners: [`capabilities/main-scheduling-continuity.md`](capabilities/main-scheduling-continuity.md)
and [`capabilities/interaction-delivery.md`](capabilities/interaction-delivery.md). This preserved page
contains implementation detail and history; its dated status is not current acceptance.


**Document Version:** 1.1-draft
**Date:** 2026-08-21
**Owner:** Viventium Core
**Status:** Required; implementation and real-user acceptance are in progress

Only stable agent instructions, policy, tool schemas, declared capabilities, workspace/access
binding, and native provider policy may replace a native session. Time, Feelings, Active Work,
reply ancestry, schedule metadata, current memory/recall health, and other invocation state travel
as per-turn context.

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

The completed-cohort candidate also retains exact background evidence on its canonical assistant
parent in `metadata.viventium.backgroundInputs`. Each immutable record binds the Main invocation,
delivery ID, original context bytes and digest, and cortex source IDs and insight digests. Preparation
uses the existing accepted-source transaction and generation fence before native transport. Foreground
snapshots preserve this source, and later hydration, quoted continuity context and compaction use it.
It remains background evidence; it does not replace authored user text or invent a tool result.
Later Main graph or fallback dispatch reads this exact current parent again before the native body
is hashed. It adds newly accepted evidence through the existing quoted context carrier, once per
source identity. Owner, source, logical-turn, Stop and incarnation checks remain in force; a completed
initial native step does not by itself discard evidence while the owning Core turn still runs.
After that step reports unsupported, the shared host save guard still preserves canonical inputs,
transport receipts, Native admission and completed cortex cards. The host graph owns its text and
completion flags. Foreground snapshots retain presentation acknowledgements; a failed acknowledgement
also survives background augmentation. A successful empty-parent promotion can start a new presentation.

`backgroundInputReceipts` stores transport state separately. Offered, queued and pending do not prove
model consumption or user presentation. Receipt changes do not alter the accepted source digest or
generation. The existing after-Main relevance, NTA and durable surface-delivery path remains active.
Recent raw source stays complete; existing context budgets and compaction still apply. Native
generation framing and real Voice/Text/Telegram acceptance remain separate delivery gates.

Required Main continuity must remain in the selected instruction context or fail with the existing
typed source-context error. Every declared native graph route, including lazy handoffs and its
configured graph fallbacks, uses the existing JSON `metadata.turn_context` carrier. Its default
allocation is 128 KiB UTF-8. A larger allocation requires a positive complete-source fit against
every declared route and uses only the proven remaining native body budget, up to the existing
512 KiB hard ceiling. The factual converter removes the context header before transport
and invocation hashing. Only Main applies its accepted-source manifest, authority stamps and
invocation-fresh background-input guard; a specialist does not gain Main source authority. The
selected provider, model, effort, stateless setting and surface permissions remain unchanged. Routes that
send a real context header retain the 16 KiB bound. Neither lane silently omits required accepted
background evidence; context above its applicable bound remains a typed failure.

The Main context carrier uses the provider formatter's stored-user-text normalization and its
shared typed delivery/status exclusions. A completed assistant row containing only internal
status parts contributes no answer text, but remains in the raw owner/conversation ancestry proof.
A real answer mixed with internal status retains its exact authored text. Missing or altered
answers, unfinished rows, foreign ownership and incomplete raw ancestry still fail admission.
Exact Feeling-state mirrors are permitted only when each declared instruction field carries the
same capsule and both instruction bodies end with the complete, identical declared request tail.
Additional legitimate tail context does not create a second authority source.

Saved failed answers and call turns with saved restricted speaker authority remain historical
context. They do not become accepted Main source or force legacy-history protection. A genuine
unreconciled legacy branch still requires exact ordered text, owner, conversation and ancestry;
failed context may be carried in that branch without clearing its saved error or delivery state.
Unfinished, deleted, internal, missing, reordered or changed source still fails that admission.
Ordinary restricted history keeps the existing bounded replay and truthful omission behavior.

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
remains untrusted repair data. Rejection feedback describes the compaction process, not the
conversation: it must not become conversation history. Repair the cited defect against source
evidence and retain every other part of the rejected candidate unless source evidence requires
a change. Actual conversation evidence about reviews remains eligible. A repaired result must
still pass the same size/schema and source-bound semantic review before promotion; failed
attempts never replace accepted history.

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
- Direct billing retains the SDK run's summed usage. Resident-context pressure and byte/token
  calibration use the last actual SDK model response's input usage, including its materialized
  context and tool results. A missing or inconsistent last-response receipt uses the run input
  total only as an explicit pressure upper bound; without that bound it uses the selected context
  window. Ordinary tool results produced after the last model response also require the window
  bound, because no observed request yet includes that tail. Upper bounds never calibrate bytes per token. Current epoch and measurement-order fences
  apply when a later verified response replaces a bound; no history or usage rows are rewritten.
- fallback never builds a separate uncapped history prompt.

The TypeScript continuity owner compares typed `(callId, toolName)` identities from the exact
claim source and candidate. Invented candidate identities fail the existing structural repair
path before model review and again at fenced completion. The review receives exact matches,
missing source pairs and source locations. Missing pairs may reflect an evidenced retirement;
that remains model judgment. Exact matches prove identity bytes only: the independent model
still checks each outcome against its own source, unfinished-work constraints, attribution and
all other meaning. No text parser, review-reason override or extra retry bypasses that gate.


The candidate compaction prompts are owned by `main.continuity_compaction` and
`main.continuity_compaction_review` in Prompt Workbench. Both use the configured Main primary and
fallback route with tools, recall, saved memory and Feelings isolated. The authorized Main route is
retained before a request-local Voice override. Internal generation and review use that Main tuple,
including its parameters and fallback; the public Voice turn keeps its own configured route. A
request-local snapshot avoids a new foreground lookup and retains the selection accepted for that
request when configuration changes concurrently. A missing compiled prompt
fails explicitly. The fidelity review runs only for compaction proposals. Its behavioral acceptance
requires the calibrated exact-model evaluation in requirement 49, separate from deterministic
source/candidate fencing, restart, concurrency and rendering tests. Candidate implementation and
local model evaluation do not close `MC-008` or the real long-conversation journey.

### Scheduling is Main later

- `viventium_agent` joins the owner-scoped Main continuity domain.
- `new` and `same` keep their visible-conversation meanings. They do not control cognitive
  continuity.
- Trusted scheduler envelopes use internal visibility and cannot enter UI, recall, or saved memory.
- Every Agents turn omits trusted scheduler envelopes and hidden scheduler outputs from Main
  message history by their retained type, including later web, Telegram and Voice turns. The loaded chain keeps them so the builder's
  parent walk reaches every visible answer; they stay stored and accounted as skipped in the raw
  ancestry proof. Every visible prior answer remains source under the protected-history guard, so
  the wake either carries it faithfully or fails typed (`source_context_unavailable`). Row counts
  are not knowledge delivered to Main.
- Main answer history recognizes the Message owner's captured authored identity
  (`agentId` and `stableAuthoritySha256`) through that owner's validator, including supported
  older stamps. A stamp proves source authority, never transport capacity.
- Historical attachment hydration completes in `BaseClient.loadHistory` before continuity
  admission. Native capacity uses the installed formatter and completion serializer with the
  actual hydrated media, ordered file context, formatter names, exact reviewed prefix capsule,
  and required peer reserve. File references and generated output metadata stay intact in their
  existing owners; metadata alone does not prove overflow. A pending current upload, gateway
  injection, unresolved RAG context, malformed media or unknown route cannot prove a conservative fit.
- A reviewed prefix plus every newer row may be reused on a strictly positive conservative fit.
  A false or unavailable estimate keeps the existing reconciliation/admission path; it cannot
  force compaction of stamped history or reject a turn. The default 128 KiB allocation applies to
  `metadata.turn_context`, not historical base64 media; a proven remaining body allocation may
  be larger. xPerfect owns its existing rendered-source
  replay budget, including its truthful protected-source failure. Discovery exposes that same
  model/config budget at minimum bytes-per-token calibration; it has no separate 192 KiB clamp.
  Core allocates the remaining body space from the smallest advertised primary/fallback limit.
  The stored summary contract remains bounded by 128 KiB. Actual native admission honors the
  selected harness's effective half-window, explicit operator cap and existing 512 KiB hard
  bound; a valid model/epoch-bound native observation can only reduce that window. The catalog
  limit is not a guarantee for an unknown smaller session window. Native Codex GPT-6.1 Sol uses
  its reported effective 475,000-token window; the Direct API route has its own catalog entry.
  An oversized indivisible packet still fails typed; whole-source reduction and fidelity review
  remain authoritative, with no source or candidate clipping. Native
  rendering carries image/file labels while the existing file broker retains the original bytes.
- Legacy conversation continuity: when unstamped legacy history cannot fit the protected carrier,
  its oldest whole-turn prefix is reconciled into a reviewed semantic summary by the existing
  compaction runner (owning Workbench generation and review prompts, exact configured Main route),
  bound to each covered visible row's ID and content digest. Main receives that summary as a
  required turn-context section plus the newest visible rows intact. The carrier bound is unchanged,
  stored history is never rewritten, truncated or reset, a changed or missing covered row
  invalidates the summary, and an unapproved summary is never used; the turn then fails typed. The
  turn that needs it reconciles in the foreground, once per new covered prefix.
- Native per-turn-header Main receives its request-pinned saved-memory snapshot, with explicit
  availability status, in the per-turn developer tail; primary and retry reuse the same snapshot.
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

Accepted internal compaction uses its own isolated, tool-free signed request and claim. It does not
inherit the triggering live-call permission frame. The configured native model and effort remain
unchanged; read-only maintenance receives no tools, worker controls or speaker action authority.

Explicit source changes advance the domain generation and invalidate derived summaries. Both source
Messages participate in acceptance. Actual hard deletion retains a per-logical-turn revision floor
in the existing continuity collection; floors stay outside model context. Missing reads never prove
deletion. Indexed Message history and separately keyed retirement floors replace lifetime arrays in
active epoch records. Retention must keep floors while older saved presentations remain eligible.
System receipts and bookkeeping do not change accepted source generation; source hydration and
invalidation share the same effective text and completed-tool-result projection.

Recoverable account cleanup routes message tombstones through this same native source mutation
transaction. Owner, revision and source timestamp compare-and-swap checks remain mandatory. Internal
admission status updates preserve source timestamps so they cannot invalidate a valid source CAS.
Stale source edits remain conflicts. This source repair does not prove that a live account cleanup,
legacy summary reconciliation, producer retirement, or search/RAG cleanup has completed.

Recovery verifies owner-bound scheduler snapshots using their existing schema. Selected schedules
also require cleanup revision and source timestamp checks. Message-only cleanup can use a legacy
scheduler snapshot when no schedules are selected.

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
negative or unavailable review retains pending references. The reviewed summary is delivered whole;
carrier overflow requires guarded recovery or blocks admission, and cannot consume its source.
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
in the actual full-text Core capsule. Explicit compaction remains
immediate. Claims process the oldest whole-turn prefix with a default 80 KiB source target. When a
claim exhausts its bounded attempts without an accepted proposal, the next claim takes at most half
of that claimed source, with one indivisible whole turn as the floor. An epoch durably degraded by
an unaccepted proposal starts at half the default after process-local learning is lost; a provider
or transport failure does not change that default. Promotion restores the default source target.
An indivisible larger turn is supplied whole to the provider, whose actual input budget remains
authoritative. The server allocates semantic output from the actual serialized consumer: the
existing selected 16 KiB header consumer or native compaction output contract capped at
128 KiB, shared by Core and legacy conversation context. The stored contract stays capped even
when a turn has a larger proven body allocation. Current, recent, authority and framing costs
are reserved before allocation.
Core reserves its three actual recent full-text turns, including escaped tool/background evidence,
the existing bounded pending-unavailable marker and reconciliation framing. Pending source keeps
its existing bounded inclusion and guarded compaction policy. A reference-only capsule cannot
substitute for full source unless the message courier actually delivers that source.
The former 12 KiB Core bound is a conservative legacy-allocation floor, not a separate full-source
ceiling. Legacy allocation hydrates Core once and reserves the larger of that floor and its actual
serialized bytes. Final Main admission reuses that request's exact identity/version and hydrated
source snapshot under the selected carrier's remaining space, including the final legacy capsule,
peer sections, attempt authority and separators. It is a pinned request snapshot, not a fresh read
after another turn commits. Ordinary recent-source growth within the existing aggregate transport
retains the accepted summary without a new model call. The unused reference-only view cannot reject
the actual full-text consumer.
This is a current-source allocation, not a guarantee for every future legal source size. Genuine
aggregate carrier overflow returns a typed budget state with full hydrated source and the complete
reviewed summary retained. Admission reuses the existing foreground compactor once and reloads;
a summary-only claim is permitted when that exact state needs reallocation. Failure blocks source
admission explicitly. Both domains share the selected carrier; neither can claim its full allowance
without reserving the other mandatory sections. On the 16 KiB carrier, allocation first reserves
full Core, reviewed legacy continuity, current call and attempt authority. The existing atomic
combiner then retains optional peer sections only within the remaining room. The admitted snapshot
retains an optional work projection only when its whole capsule remains in that selection, so final
attempt encoding cannot reintroduce an omitted peer. An optional peer cannot
cause false source overflow or force recompression of accepted state. Native body allocations retain
the existing all-peer reservation and serialization. Optional
reply and active-work capsules keep their existing atomic retention policy.
The retained outer contract binds that allocation to the lease, validator, prompt constraints,
failure identity, semantic review and persisted replacement. All nine semantic fields and item
constraints remain required. A ceiling is not a requested length. A short faithful summary stays
short. The complete escaped candidate must fit before review and again at promotion. Reload
validates the retained contract and preserves the full accepted summary; it does not clip its tail
or silently replace it with an unavailable marker when recent source consumes the carrier.


Private structured compaction and review results use the existing signed zero-tool native
capability. Its typed response contract admits only an authenticated internal, stateless,
read-only system actor with no tools, graph transfers or audio. Validation accepts one optional
JSON code fence, matching the existing semantic parser; malformed or multiple envelopes and
duplicate object keys still fail. The exact complete JSON object
travels from the owner-bound native terminal to the private state consumer; local references
and other authorized private state remain intact for independent fidelity review. The request
persists that contract for terminal reconciliation and reload. Partial public previews are not
machine-state results. Public answers, run output, activity and diagnostics retain their existing
redaction and owner checks. This changes transport only, not prompts, models or fidelity approval.

Generation, review and transport-retry waits use the store-owned claim lease and any enclosing
scheduler authoring deadline. The enclosing deadline is shared across claims. Its remaining time
protects Main completion and any measured review reserve. Generation and review each retain their own slowest
observed duration for subsequent admission. An unobserved stage has no measured estimate and may
use any positive time within the existing call ceiling, live claim lease and enclosing Main reserve.
Generation reserves only an observed review duration; one stage never supplies the other's estimate.
The same admission owner applies to converging size repairs. Convergence and the four-attempt
limit determine eligibility. Each generation and review prepares its prompt, then admits the stage
once inside its existing error handler. The third and fourth attempts compute their repair timeout
from the current lease after that admission and any exact renewal. A failed renewal closes the
exact claim; Stop after the await prevents child dispatch. Fidelity approval remains required.
The actual issued stage budget and settled elapsed/outcome are recorded with opaque claim/run hashes,
known stage timings, lease/deadline remaining time and renewal disposition, without source content.
Each call remains bounded by the existing compactor timeout. If a live five-minute lease alone blocks
an otherwise admissible stage, its exact owner may renew it through the existing store CAS. The
renewal matches the lease ID, source digest and prior expiry, never revives an expired or replaced
lease, and is capped by both the existing five-minute stale-holder duration and the same enclosing
deadline minus Main completion reserve. A missing enclosing deadline retains the original lease.
Foreground and scheduler-enclosed work keeps those existing bounds. Detached private structured
maintenance with a real renewal store may use the exact admitted Native response deadline. Its
successful authenticated response carries the stored deadline and request ID; missing, invalid,
past or late admission metadata keeps the legacy guard. Core's guard ends at that deadline plus
the existing execution guard grace, rather than imposing an earlier independent model deadline.
Before detached stage dispatch, the same live claim may replenish its existing five-minute lease
through CAS; an expired or replaced claim cannot start. Only an admitted stage then keeps its
exact live claim current through existing lease-ID, source-digest
and expected-expiry CAS. One unref timer renews at half the existing five-minute lease, with at most
one renewal in flight; each expiry stays bounded by both deadline plus grace and the existing
five-minute stale-holder window. A lease already covering the target needs no extension. Version-CAS
contention is not ownership loss: before admission it keeps the old bounded guard; an active stage
keeps its known live lease and checks again no later than its expiry. Only expiry or a genuine
ownership failure cancels the stage. Actual
ownership loss cancels and releases the exact Native request. Stage completion closes new renewal and settles pending CAS only within the last confirmed lease
expiry or intentional cancellation; an unresolved CAS cannot hold cleanup forever. The same timer
checks expiry even while CAS is pending, and late completion cannot restore an aborted stage. Process death stops renewal, so the existing
five-minute crash expiry remains. Each producer and reviewer owns its own admitted deadline.
This adds no new attempt, provider budget, model downgrade or carrier ceiling.
An authenticated scheduler timeout uses the existing intentional generation cancel with the exact
owner. Its Stop acknowledgement waits for the compactor child's native capacity release. A rejected or
unresolved acknowledgement uses eight seconds of the existing ten-second scheduler cancel wait,
leaving two seconds for cleanup and receipt delivery; the exact
unfinished scheduler presentation is retracted and a typed release-unconfirmed result does not
claim native capacity release. Item-level size errors retain same-source bounded correction. The
durable scheduler run still records the actual timeout; cancellation is not successful completion.
Generation, review and transport-retry waits also use the store-owned claim lease. Additional size
repairs are bounded by a shrinking proposal, a four-attempt ceiling and remaining time for review.
The current process remembers an identical failed source/contract/compactor claim so that unchanged
failure does not incur another model run; its degraded state stays explicit. Smaller or changed
claims remain eligible. A typed whole-object, summary or carrier byte-size rejection moves directly to the existing
smaller-source planner when it proves
a smaller whole prefix; an indivisible claim retains bounded shape, fidelity and size repair.
Same-source whole-proposal, summary, and carrier size repair can reuse its rejected draft inside
the current claim. The complete rendered source, typed feedback and parsed draft must fit the
existing native message serializer's conservative byte projection under the smallest cached
admission floor of the configured route and its fallbacks. This reads discovery metadata only;
it makes no provider call and raises no limit. Unknown or insufficient capacity retains numeric-only
feedback and full-source regeneration. Native admission remains authoritative. The canonical prompt
allows size repair to shorten wording throughout while retaining source-supported facts,
qualifications and consequential identifiers, adding nothing. Other repairs retain their existing
candidate behavior. Independent fidelity review and the existing attempt/deadline bounds remain required.
Legacy conversation reconciliation can use the learned smaller target in the same wake only when the next whole-turn prefix has fewer source bytes and a different digest,
within the existing six-claim turn bound and each store-owned lease. Transport, lease and
indivisible-source failures end that wake. Promotion advances only the reviewed prefix watermark and never deletes
native source Messages. The former 5 KiB accepted-text clipping, 64-pending-turn eviction and 96 KiB
compactor clipping are removed. Failure retains unconsumed source and records degradation; it is
not a successful semantic-continuity result.

This candidate remains partial. Deterministic source/lease tests, exact-model role evaluation,
provider-route evidence and real browser/Telegram continuation are separate gates. In particular,
Core's whole recent source and reviewed summary enter the actual full-text turn-context capsule.
The separate reference/summary serializer and protected-message projection are not evidence that
the production courier delivers accepted cross-conversation source. A run-local model
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

A successful host-graph answer with an explicit newer message revision retires only the older
nonfailed presentation receipt. The shared Message write binds the prior revision and exact
receipt across transaction retries. A changed receipt aborts promotion and the existing follow-up
owner publishes a separate child. Failed receipts and completed Native answers retain their
authority.

A failed pre-dispatch admission revokes its native authority. If a fresh read proves no
native admission was persisted, release the exact job binding through the existing unsupported
handoff so normal error delivery can finish the stream. An uncertain persisted admission stays
fenced; cleanup must not authorize ordinary publication over a recoverable native result.

An exact native result that reports failure or cancellation must publish a durable error FINAL and release the current conversation composer. The existing Message admission stores a distinct terminal snapshot marker; it does not assert user Stop or successful Main delivery. Saved terminal content uses the normal public error renderer and audio suppression. Recovery reuses that snapshot and the existing job FINAL, without another model invocation, memory admission, title generation, or continuity-success acknowledgement.

If canonical Native persistence fails because that exact row was removed, preserve the internal
missing-row error type through the message boundary. The existing revoked-response failure owner
may terminate only the matching current, cancelled, unfinished job with revoked commit authority.
It must not recreate the row or replace a stored Stop FINAL. Normal producer cleanup still runs
after that terminal failure.

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

Saved assistant plain text remains historical evidence when its persisted content array is empty
or consists entirely of known internal status parts. The shared source and provider projection
carries that full text and every original status part without changing the stored row, terminal
flags, role or authority. A populated text, tool, media or unknown part prevents supplemental
display-text projection. Protected admission still rejects missing or changed
prior words, foreign source, internal history and invalid terminal state. A saved progress display is
retained evidence, not a new answer or speech delivery.
Any change to this shared source projection invalidates a covered prefix whose saved digests no
longer match. Full owned source may travel intact through the admitted native body lane without
using that stale summary. When reconciliation is needed, the existing continuity owner reclaims
that whole source under its version and lease CAS, generates and independently reviews it, then
verifies source again before promotion. An old
record stays durable but cannot supply a stale summary; rejected recovery leaves source untouched.


### Native whole-source admission

A declared native Core protocol and stable session-authority route may carry the full owned
message history through its existing JSON body courier. Admission uses the installed completion
serializer and the smallest cached replay limit of every declared native route. The early
whole-history fit check reserves the default 128 KiB for dynamic context. Final admission may
allocate more only from the proven remaining body space after complete message evidence,
attachments and framing are counted. Neither step increases native replay or model limits.
Unknown, mixed and header-only routes retain the existing
128-row and 32 KiB encoded-header bounds. A valid reviewed prefix and its existing tail-growth
path are retained. An absent or stale prefix may travel whole when it fits; true overflow keeps
the existing reviewed whole-prefix compaction path. Final native source identity and replay guards remain authoritative.



### Native conversation history does not wait for opportunistic migration

A transport-bound native Main route carries visible history as protected messages in its existing
body courier. The 128 KiB default turn-context allowance is separate from the whole-history
and model-window limits. Final native admission may use a larger proven remaining body allocation,
while stored compaction contracts stay capped at 128 KiB. The early whole-history estimate is
positive-only: a false or
unavailable estimate cannot prove that the final native source cannot be carried.

When the current transport and every declared alternate support the native source protocol and
its complete projected replay fits the smallest declared native byte floor, conversation-prefix
migration uses the existing per-domain idle deferral and bounded compaction runner. Authenticated
model discovery exposes that floor from the same native budget owner at its minimum calibration.
A redundant lower discovery clamp previously forced foreground reconciliation even when the
complete source and required carrier fit native admission. Removing that clamp reuses the existing
allocation and guards; it adds no reserve scan or alternate compaction path.
The existing cached model loader discovers this capability even with a fixed model menu; model
choices stay unchanged. Admission reads that cache only, costs the fields rendered by the native
history reader, the existing final native turn-context byte cap, source/delivery framing and the
selected upload ledger with its workspace paths. Reserving the final cap covers every later dynamic
section and summary without trusting an earlier size forecast. Original messages, tool evidence and source-integrity guards remain unchanged;
this sizing projection does not edit them. Static native system instructions are configured
separately. The existing selected-history file resolver pins one owner/conversation/parent/selection
promise per request for early sizing and later signed projection. Another request rechecks current
File ownership/deletion; a rejected promise is removed. Missing model metadata, pending hydration, mixed carriers or an over-budget replay
retain foreground reconciliation. Native admission remains the final source-integrity guard. Foreground assembly immediately retains the exact validated reviewed prefix plus every
newer authorized row, or all original rows when no valid prefix exists. It never accepts an
unfinished candidate, edits stored history, clips a tool result, or marks unreviewed source covered.
Each background claim reloads its durable record; only a reviewed commit advances the prefix.
Idle work uses its own background response and budget, without the finished request's scheduler
deadline or abort signal.
The same foreground fences, fresh active-call checks, Call End continuation, finite batch/deadline,
and failure-stop policy apply. A lazy declared fallback need not initialize its tools merely to
classify the current primary's native courier; its actual dispatch still checks source authority.

Header-only, mixed or unproved routes retain required foreground reconciliation. Genuine aggregate
turn-context overflow retains the existing foreground carrier recovery and reload; its limits and
final source-integrity guards are unchanged. Native provider/model capacity remains authoritative;
this change does not enlarge a context window or guarantee arbitrary history fits every provider.

### Bounded idle continuation of reviewed legacy history

Background accepted-turn maintenance and the existing Call End flush reuse the same claim runner
for up to four claims within a shared twenty-minute deadline. A completed
store-owned claim signals continuation only while its legacy cursor remains incomplete. The runner
yields the event loop between claims, checks the existing interactive admission fence before each
claim, and keeps the existing in-flight cancellation and native capacity-release checks. Required
foreground carrier recovery still performs only its own claim.

The finite idle batch also uses the existing authenticated Native admission receipt and claim
heartbeat. It can replace the short per-stage guard only when the admitted Native deadline,
existing execution-guard grace and Main completion reserve all fit inside that same enclosing
batch deadline. A later producer or reviewer cannot reset the batch budget. A deadline that does
not fit keeps the existing short stage guard; foreground recovery, unknown capabilities and
claims without renewal retain their prior policy. Every renewal stays within the enclosing
budget. Measured producer and reviewer durations remain unchanged. Native-capable background
planning compares them with the enclosing budget while retaining the short initial guard inside
the live claim lease and the measured review reserve. A stage already measured above that guard
must also fit its previously accepted Native admission window; a declined receipt never becomes
a planning allowance. Producer receipt admission also retains the measured review reserve.
After reviewed progress, an insufficient budget for the next claim exhausts this batch and uses
the same idle continuation owner. A concrete fidelity repair may also continue as described below;
provider/review transport failures do not re-arm continuation.
Foreground admission still cancels the exact maintenance attempt and waits for its capacity-release
acknowledgment. Only independently reviewed output can promote the summary or advance a source cursor.

A whole-proposal, summary or rendered-carrier byte overflow can use the same batch's next claim
when the existing source planner proves a smaller whole prefix. The failed result carries its
source digest, byte count, domain and learned smaller target. Before any next provider request,
the new store-owned claim must belong to the same domain, have a different digest and contain
strictly fewer source bytes. An unchanged or indivisible source releases that claim and stops;
it never repeats model work merely because the target number decreased. Field/item errors,
provider or review failures and cancellation do not qualify. These reductions consume the same
four claims and deadline, yield to foreground admission, and retain every unreviewed source.
Failure alone never re-arms an exhausted idle batch. Summary promotion and source-cursor movement
still require the existing independent fidelity review.

When an enclosing budget pauses a completed fidelity correction or a shrinking whole-proposal,
summary, or carrier byte-size correction, the existing epoch/lease CAS may retain
`pendingCompactionRepair`. Fidelity repair contains its structurally valid rejected candidate and
reviewer feedback. Size repair contains only typed byte counts, the exact size issue and shrinking
progress; it never stores an oversized draft. Both retain the exact source digest,
configured route/output contract, source window and consumed attempt counters. The checkpoint is
separate from accepted context and is never presented or spoken. Saving it requires a live exact
lease and confirmed native capacity release. The existing semantic cap and four-size-attempt cap
remain distinct and span batches. Malformed feedback, nonconvergence, exhaustion, cancellation,
provider failures and unconfirmed release do not qualify. The store's acknowledgement alone lets
the existing thirty-second idle deferral re-arm; no queue or timer is added.

The next ordinary bounded batch reclaims the exact source prefix and legacy range. Append-only
user turns remain pending instead of expanding the repair source; edits/deletions invalidate its
source generation. Fidelity retains its same-route pinned contract within the same carrier class.
Size feedback can resume only under the same route and compatible equal or tighter allocation;
its issue is rebased to that current binding target. It restores both consumed attempts and the
existing shrinking-size state, so another batch does not restart its attempt budget. The model
receives the complete original source and exact typed feedback; a resumed size claim does not
recover the prior transient draft. Any new rejected candidate is eligible for the same in-claim
admission check. The canonical compaction prompt defines `maxJsonUtf8Bytes`
as the whole serialized JSON limit, including all fields and JSON syntax/escaping. Individual
field caps are additional constraints. Recompression protects the facts of prior valid state,
not its narrative wording or layout. When the whole object is too large, the model shortens the
summary narrative first, retaining qualifications and exact consequential identifiers. Facts
belong in one place across the complete object, including the summary and category arrays,
unless repetition is necessary for meaning or attribution. Related structured entries are merged rather than dropping pending work,
corrections, decisions, recurrence outcomes, tool pairs or other protected facts to make room.
The typed limits and independent fidelity review remain unchanged.

Promotion still checks the complete current carrier and requires independent fidelity review.
Pausing cannot weaken either check or advance a source cursor. Foreground pre-emption before a
new attempt or transport retry is consumed preserves a matching checkpoint only after confirmed
native release; it does not re-arm cancelled work. Source, route, carrier or incompatible budget
mismatch, exhaustion and provider/transport failure clear the checkpoint. Promotion clears it
normally. Each batch keeps its deadline; an explicitly inherited deadline never re-arms.

After genuine size nonconvergence or exhaustion, the existing failed-claim owner suppresses the
same source and configured route under an equal or tighter compatible output allocation. A larger
allocation, changed source or route, or runtime reload permits reconsideration. Enclosing-budget
pauses are not terminal exhaustion: their checkpoint carries progress instead of silently blocking
memory. Suppression prevents repeated failed provider work; it does not claim that the backlog is
complete. Approved memory and all original source remain available while maintenance is degraded.

Provider or review failure, cancellation, contention, stale source, an exhausted deadline, or the
four-claim cap stops the batch. After successful reviewed legacy progress exhausts only that batch
budget, the existing per-domain Call/idle deferral owner re-arms one continuation after thirty idle
seconds, without requiring another user turn. It waits while the existing foreground fence is held;
required foreground recovery or a newer schedule discards the old timer. Before each historical
background claim, the Call Session owner checks fresh owner/agent session status, expiry and fatal
state across conversations. A new active or connecting call moves that work back to the existing
Call End deferral, including when the idle timer was armed before the call began. An unavailable
liveness read starts no maintenance claim. Ordinary memory admission and Feelings remain parallel.
An inherited enclosing
deadline is never extended by re-arming. Provider/review transport errors, cancelled work and source contention
stop continuation. The current reviewed summary and durable source cursor remain available.
This reuses the same bounded claims, source cursor and scheduling owner, not a second memory service
or an automatic retry of failed provider work. Actual cursor movement and final historical
completeness still require real-state acceptance.

The positive Native history-fit estimate charges inline image/file content by the exact label
that Native `_message_text` renders, rather than charging its base64 payload as replay text.
The original wire, authorized upload ledger, Native image/file input bytes, media limits and
source proofs remain unchanged. Unknown non-string media labels cannot prove a fit; actual
text overflow and unknown route capacity retain foreground reconciliation. Historical attachment
hydration must be included in sizing checks; raw persisted rows alone do not prove the live path.

A label-only replay fit also retains Native inline image ingress: the existing24-image,
32MiB aggregate and8MiB per-image limits, supported MIME signatures and valid base64 are
checked before a positive estimate. Unknown or oversized inline inputs retain the existing
foreground reconciliation path. This estimate may conservatively count duplicate images;
the Native media owner remains authoritative for actual admission and deduplication.
