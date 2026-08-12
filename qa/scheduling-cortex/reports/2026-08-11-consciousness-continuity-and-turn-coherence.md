# Consciousness Continuity And Turn Coherence — 2026-08-11

## Outcome

The existing Main agent now has a registered, Workbench-visible continuity opportunity that can
appraise all nine Feelings with current goals, plans, commitments, memory/recall, capabilities, and
outcomes, then act, plan, ask, communicate, or intentionally remain silent. It introduces no new
agent, emotional scalar, goal store, tool policy, or channel-specific coordinator.

The same delivery also adds one logical-turn lifecycle for web, Telegram, voice, callbacks, and
future adapters. A stable user segment received before presentation commit supersedes unfinished
assistant presentation, preserves the ordered user segments, and produces one current answer.
Presentation interruption remains distinct from durable-work cancellation.

## Real User-Path Evidence

| Surface | Result | Evidence |
| --- | --- | --- |
| Prompt Workbench | PASS for discovery, editing controls, prompt lineage, schedule configuration, history, refresh, terminal-state truth, silence, and durable-conversation reuse | Headed browser showed the active private schedule, 45-minute Toronto cadence, 09:00–21:00 daily window, 17 projected opportunities, destinations, effective model, and all registered prompt links. Three post-fix Main opportunities completed `silent`; the latest two remained visible after refresh with Sol/xHigh provenance and reused one durable conversation. Mongo showed four internal, memory-ineligible messages, zero visible/unfinished messages, and an archived conversation. |
| Web A → unfinished B → C | PASS | A headed browser submitted C while B streamed. One current D reflected ordered A+C, the composer cleared, refresh did not restore B, and Mongo contained the two user revisions, one current assistant revision, and a content-free supersession tombstone. |
| Telegram text A → unfinished B → C | PASS | A real rapid two-message path produced one coherent current response with no stale `Connection error`. The stale preview was retracted; Mongo showed one canonical conversation/logical turn, revisions 1 and 2, and only the revision-2 assistant result. |
| Voice ordinary playback | PASS | A real headed playground call used the installed local STT/TTS path, matched one synthetic transcript, delivered 6.81 seconds of audio, completed playback, returned to listening, and removed all synthetic call/chat records. |
| Voice stable barge-in | PASS | A second real audible call spoke C during B. Two user segments were finalized, old speech stopped, one surviving assistant row remained, D was played, 12.62 seconds of delivered audio were measured, and synthetic records were removed. |
| Restart/persistence | PASS | The current checkout was reactivated and the installed local stack restarted. Web, Telegram, voice playground, scheduler, and Workbench returned healthy; web/Workbench refresh and voice/Telegram persistence checks used the restarted runtime. |

The 0.32-second false-barge probe completed normally with one user turn and 7.58 seconds of audio,
but it did not cross the configured VAD minimum and therefore is not counted as false-interruption
evidence. A later detected `wait` probe was safely handled as a stable second utterance rather than
a false interruption. It therefore also does not prove false-barge resume; that live half remains
outstanding.

## Escaped Defects Found And Repaired

1. Rapid web input was blocked by the composer and the client could lose the canonical first-turn
   conversation binding. The shared resumable-stream receipt now binds the canonical conversation
   immediately, supersession is permitted while authoring, stale placeholders are removed, and
   pending drafts migrate correctly.
2. Web supersession depended on an optional search dependency. Conversation cleanup now uses the
   owning Mongo collection directly, so an unavailable search service cannot strand a turn.
3. Telegram's first message used literal `new` while the next message used the canonical UUID.
   Server-authored interaction context now binds the canonical conversation before the atomic
   logical-turn claim.
4. External-adapter output could be persisted as final before Telegram/voice presentation commit.
   It now remains provisional until a scoped delivery acknowledgement commits it; superseded
   presentation is deleted by revision and failed delivery stays truthful.
5. Workbench could leave a failed manual run visibly `running`. Terminal failures now write
   `disposition=failed`, and startup repairs the historical impossible state.
6. Scheduled Main's inherited 120-second stream ceiling was shorter than real governed
   high-reasoning runs. The shared scheduled-generation window is now ten minutes, below the
   15-minute occurrence lease and isolated by the four-worker pool.
7. Local Chatterbox cached an MLX model across fresh per-sentence threads. Because MLX streams are
   thread-local, the second sentence could terminate the native process. Model load, prewarm, WAV,
   and streaming generation now share one process-local synthesis executor; forked workers discard
   inherited executor/model state.
8. Replacement voice prewarm could race an active call, and authoritative state lookup used an
   unrealistically small local timeout. Replacement prewarm now waits for active calls without a
   premature ceiling; state lookup remains bounded but tolerates normal local scheduling delay.
9. Mongo/Meilisearch query middleware treated model `updateOne` results like hydrated documents.
   When no document hook existed it also failed to invoke Mongoose's continuation, leaving internal
   visibility persistence waiting forever. Save/update/delete middleware now always continues when
   the optional document hook is absent; the exact timeout regression and full plugin suite pass.
10. A scheduled generation timeout could leave backend authoring and its provisional placeholder
    alive after Workbench had truthfully failed the run. The dispatcher now explicitly cancels only
    its owned scheduler stream on timeout; the authenticated route rejects interactive jobs and
    removes only unfinished scheduler-owned presentation, never durable work.
11. Workbench manual runs wrote a conversation receipt only to run history, not back to a
    `conversation_policy=same` task, and a default `isArchived=false` value was indistinguishable
    from a conversation unarchived by useful output. Manual and natural runs now persist the same
    canonical conversation fields. Archive decisions use completed visible assistant history, so a
    new silent thread stays archived while a historically useful thread stays unarchived.

## Automated Evidence

- LibreChat affected backend: 483/483 passed.
- LibreChat affected client streaming/message tests: 57/57 passed.
- Logical-turn/usage/manager Redis integration: 63/63 passed.
- Redis store: 37 passed, 1 existing skip.
- Scheduler full suite: 159 passed plus 8 subtests; affected scheduler/interaction API: 184/184
  passed.
- Mongo/Meilisearch plugin: 52/52 passed; data-schema production build passed.
- Telegram repository: 376/376 passed.
- Voice delivery integration: 106 passed plus 24 subtests.
- Full voice gateway after the MLX fix: 493 passed plus 84 subtests; MLX-focused 27/27 passed.
- Production package and client builds passed.
- Prompt Workbench release checks: 179/179 passed; config-compiler checks: 182/182 passed.
- Parent/nested diff checks and public-safety scans passed.
- Parallel independent QA plus a review-only Claude pass challenged scheduler idempotency,
  cross-surface commit truth, Redis revision handling, archive/persistence ordering, voice audible
  acknowledgement, and scoped adapter authorization. Supported findings were reproduced and fixed;
  the final read-only review found no remaining code-level release blocker.

The broader shared-tree release suite finished with 1,323 passed and 8 skipped. Six unrelated
pre-existing/shared-worktree assertions remain red: one memory-hardening state mismatch, two native
network-address expectation mismatches, and three QA-inventory/report-ownership assertions. They do
not contradict this feature's targeted evidence, but they prevent a whole-repository green claim.

The Redis Jest harness retains an open handle after successful assertions and requires explicit
runner cleanup. This is test-harness hygiene, not a failed product assertion.

## Current Acceptance State

- Blocking foundations, shared interfaces, trusted origin, scheduler ledger/leases, prompt
  registry/compiled contract, all-Feelings appraisal, capability parity, channel-neutral fanout,
  web/Telegram logical turns, installed ordinary voice playback, stable voice supersession,
  Workbench visibility, and restart are accepted.
- Three fresh post-fix continuity opportunities completed intentionally silent. The latest two
  survived Workbench refresh, reused one durable archived conversation, and left zero visible or
  unfinished messages. One useful delivered opportunity, a natural active-window tick, and a
  detected false-barge resume remain required before the entire rollout checklist is marked
  complete.
- The current-build Workbench passed its headed discovery, editing, prompt-link, Run Now, history,
  terminal-state, and refresh paths. A dedicated 320-pixel light/dark and screen-reader pass remains
  partial and is not represented as complete.
- No public template proactively messages users. No unsolicited voice call, new Feeling schema,
  hard threshold, message cap, continuity-only tool rule, or identity-wide conversation merge was
  introduced.

## Privacy And Cleanup

Only synthetic non-personal QA content was used. Raw screenshots, logs, database rows, local paths,
adapter credentials, private prompts, and account identifiers remain outside the public repository.
The voice harness removed its synthetic users, sessions, messages, ingress rows, speaker segments,
and conversations after every completed run. Final cleanup removed the browser test account plus
its exact dependent messages, transactions, conversations, and sessions with zero residue; closed
the synthetic browser tabs; removed the isolated Redis container; and moved temporary voice
evidence to the system Trash so it remains recoverable until the owner empties it.
<!-- qa-evidence-exempt: Historical or specialized supporting artifact retained without retroactively inventing missing evidence; current release acceptance requires a fresh full-view report. -->
