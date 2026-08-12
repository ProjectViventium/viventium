# Agent Streaming Usage Metadata

## Overview
The Agents runtime can request per-chunk usage metadata from providers. Some providers (notably
Perplexity) stream usage fields in multiple chunks, which triggers LangChain merge warnings.

## Core Requirements
- Avoid per-chunk usage streaming for providers that emit duplicate usage fields.
- Preserve usage totals via the final response payload.
- Keep provider-specific logic centralized in the Agents runtime configuration.

## Specifications
- Location: `viventium_v0_4/LibreChat/packages/api/src/agents/run.ts`
- Behavior:
  - `streamUsage` defaults to `true` for standard providers.
  - For providers in `customProviders`, force `streamUsage = false` and `usage = true`.
  - Perplexity must be included in `customProviders` to prevent `completion_tokens` merge warnings.
  - Voice-call requests (`viventiumSurface=voice` or `viventiumInputMode=voice_call`) disable
    `streamUsage` to avoid repeated merge warnings in voice streams.
  - Telegram `voice_note` input is a text-mode turn with optional audio delivery, so it does not
    count as voice-call mode for this policy.
  - `VIVENTIUM_DISABLE_STREAM_USAGE=1` disables `streamUsage` globally and forces `usage = true`.
  - The `viventium-librechat-start.sh` launcher exports `VIVENTIUM_DISABLE_STREAM_USAGE=1` by default (override to re-enable).

## Integration Points
- `viventium_v0_4/LibreChat/packages/api/src/agents/run.ts`
- `viventium_v0_4/LibreChat/librechat.yaml` (custom endpoint definitions)

## Edge Cases
- Custom endpoints that reuse OpenAI-like models may also stream usage; add them to
  `customProviders` as needed.
- Streaming usage should remain enabled for providers that do not emit conflicting usage metadata.

## Learnings
- LangChain’s `_mergeDicts` warns on duplicate `completion_tokens` fields when types differ.
- Disabling per-chunk usage for Perplexity removes log noise without losing final usage totals.

## Cross-Surface Logical-Turn Contract

A logical turn is the canonical conversation-and-interaction-class lifecycle shared by web,
Telegram, voice, callbacks, and future adapters. Interactive external-user input shares one class
across surfaces when they resolve to the same canonical conversation. Internal scheduler wakes and
callbacks use separate actor/origin classes, so background authoring cannot supersede an
interactive response merely because it writes into the same conversation. It is not a
channel-specific debounce buffer.

1. External-user segment A opens logical turn T, revision 1.
2. Assistant presentation B begins.
3. Stable external-user segment C arrives before B commits.
4. The store atomically claims revision 2; B's unfinished presentation is retracted.
5. A and C remain distinct ordered source segments; revision 2 receives A+C and produces one
   current answer D.
6. Stale revision chunks, speech, previews, follow-ups, and natural-language callbacks cannot
   present themselves as current.
7. If B committed before C, C begins a normal follow-up logical turn.

Successful supersession is recorded as a lifecycle disposition and never rendered as `Connection
error. Please retry.` Different users and conversations remain independent. Supersession crosses
surfaces only when those surfaces already resolve to the same canonical conversation; this feature
does not introduce identity-wide merging of unrelated chats.

### Atomic claim and idempotency

The logical-turn record contains a bounded `logical_turn_id`, monotonic `revision`, and
`source_event_id`. The existing GenerationJobManager active-job query, each job's
`conversationId`, abort event transport, and resumable stream remain the execution substrate.
In-memory mode uses a per-user/conversation/interaction-class critical section; Redis mode uses one
atomic claim with an expiring record over that same scope. Actor and origin define the interaction
class; surface is deliberately excluded so canonical interactive A+C behavior survives a
web/Telegram/voice transition. Repeated webhook delivery with the same `source_event_id` is
idempotent within its interaction class.

A superseded job may be best-effort aborted to stop authoring, but its stale finalization cannot
save or emit current assistant prose. An unfinished assistant row is removed from conversation
context and replaced only by content-free audit metadata; refresh must not restore B.

### Adapter capabilities and delivery acknowledgement

Every adapter declares:

```ts
type InteractionAdapterCapabilities = {
  segment_stability: 'immediate' | 'provisional';
  supersede_scope: 'response_and_authoring' | 'response_only';
};
```

Web and Telegram text, finalized Telegram voice-note transcripts, and file/text source segments are
`immediate` + `response_and_authoring`. Live voice is `provisional` + `response_only`: acoustic
barge-in stops speech provisionally, false interruption may resume through the existing LiveKit
mechanism, and only a stable utterance supersedes the old presentation. Speech interruption never
implies durable backend-work cancellation.

Delivery uses one contract with a credential scoped to the presenting adapter:

```ts
type InteractionDeliveryAck = {
  logical_turn_id: string;
  revision: number;
  state: 'committed' | 'partial_removed' | 'failed';
  presentation_ref?: string;
};
```

Telegram and voice receive distinct generated credentials; the core rejects a shared or colliding
credential. The route identifies the authenticated adapter from that credential, then validates the
server-held job's conversation ownership, logical turn, revision, `external_adapter` commit
authority, and matching surface. Client-supplied ownership, scheduler origin, surface, or revision
authority is ignored. A Telegram credential cannot acknowledge voice output, and neither adapter
can acknowledge web or scheduler output.

Web commits only after canonical final persistence plus successful stream completion. Telegram
commits after a successful final send/edit acknowledgement. Voice commits only after positive
audible-playout evidence; a completed speech handle alone is insufficient because terminal TTS,
forwarding, or zero-audio failures may also complete it. Those failures acknowledge `failed`, while
stable supersession acknowledges `partial_removed`. Streaming previews and partial speech are never
commits.

`committed` closes the presentation turn. `failed` is also terminal and closes the current claim,
so the next user segment starts a fresh logical turn rather than superseding a response the adapter
has already declared impossible to deliver. `partial_removed` keeps the current turn open because a
stable replacement segment may still revise it. A `partial_removed` receipt for an older revision
never mutates or closes the current revision.

Telegram and voice retry the exact same idempotent acknowledgement payload up to three times, with
a short backoff, for transport failures, HTTP 408/425/429, and 5xx responses. Semantic rejections
such as stale revision, ownership conflict, or unknown turn are not retried. If all attempts fail,
no outcome is recorded and the response remains provisional until a valid receipt arrives.
Generation completion alone is never evidence that Telegram text was delivered or voice audio was
heard.

This bounded retry removes the ordinary transient-failure gap without adding a persistent adapter
outbox. It cannot make presentation and core persistence atomic across processes: if an adapter
process dies after visible text or audible playout but before any acknowledgement reaches the core,
the core still truthfully knows only that delivery is unconfirmed. A later revision may therefore
supersede that provisional record. Closing that final ambiguity would require durable adapter-side
receipt storage and reconciliation and is intentionally outside this minimal design.

For server-authority web output, canonical final persistence is durable presentation truth. If the
process dies after persisting the replayable final event but before its in-process commit receipt is
recorded, the next claim reconciles that persisted final as committed before opening a fresh
logical turn. This narrow restart recovery never applies to `external_adapter` jobs.

### Presentation versus durable work

Supersession retracts an unfinished response; it does not implicitly cancel committed external
effects, durable GlassHive work, or background tasks. Explicit cancellation remains the only
durable-work cancellation path. Completed tool receipts attach to the surviving logical turn. A
late durable callback is re-attributed to the current revision or delivered as a truthful
completion follow-up; stale natural-language prose is never delivered as current and a committed
effect is never repeated merely because the earlier presentation was interrupted.

### Surface acceptance

- **Web:** new input supersedes an unfinished response; refresh never restores it.
- **Telegram text:** the short `LONG_TEXT` window remains an ingress optimization only; source
  messages stay distinct, stale previews are deleted, deletion failure suppresses later edits and
  records degraded delivery without a false connection error.
- **Telegram voice notes/files:** finalized transcript and file source segments are never deleted as
  assistant output. Pending transcription preserves receipt order; a failed transcription lets the
  later segment proceed with a truthful unavailable-transcription state.
- **Live voice:** stable barge-in stops stale speech permanently while false barge-in may resume;
  only confirmed audible playback commits the presentation, backend work remains durable, and the
  surviving context includes the ordered stable user segments.
- **Callbacks/future adapters:** revision metadata is mandatory; future adapters implement the two
  capabilities and delivery acknowledgement without core channel-name branches.
