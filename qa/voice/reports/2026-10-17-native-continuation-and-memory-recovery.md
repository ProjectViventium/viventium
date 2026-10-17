# Native continuation and memory recovery — 2026-10-17

QA scope: **blast-radius**. This report covers the native public-text projection and exact
deadline-cleanup repairs, their confirmed consumers, and the existing continuous conversation
flow. It does not claim the complete Voice acceptance bank passed.

Candidate identity: xPerfect merge `d0be7094a98072617f4ff64ccaa575ff6e5bbe38`
([PR 16](https://github.com/xPerfectAI/xPerfect/pull/16)), selected by `components.lock.json`. The reviewed native wheel and loaded source were compared before
acceptance. Existing valid Chat/Telegram and source-test evidence was retained. Raw prompts,
account identifiers, logs, audio, screenshots and source receipts remain private.

## Repairs and evidence

| Requirement / use case | Expected result | Actual result | Remaining gap |
| --- | --- | --- | --- |
| Native streamed reply completes | Live text, final text and audio ranges use one public projection without changing already accepted text. | PASS: a real call exercised an empty silent envelope followed by eligible replies with leading separators. All 227 captured native text snapshots preserved the final public prefix; Main completed and the matching Core error window was clear. | Raw SSE network traffic was not captured. Native replay, durable completion, received audio, logs and visible chat form the proof. |
| Exact deadline recovery | Clean only the retained native generation, preserve failed history and controls, then reuse the conversation. | PASS: normal maintenance retry reused the same worker/session; two successor runs completed and the saved summary cursor advanced. Previous failed run/request and retained input history were unchanged. | Full historical backfill remained in progress. The live maintenance session was stateless; persistent-session continuity was verified by affected tests. |
| Queen → worker → Steer → spoken result | Main can use a real worker, consume its late result during the current reply and present it once. | PASS: injected audio was transcribed; Main answered the arithmetic request, dispatched an actual worker, received its result through Steer, and spoke the result. The later Main-authored NTA correctly avoided duplicate speech. | One observed journey is not exhaustive provider, concurrency or endurance acceptance. |
| File delivery and reload | The actual delivered file opens with exact content and stays attached after reload. | PASS: Chrome file-card downloads returned the exact synthetic 11-byte file in both observed cases; reload preserved the result. | A separate external inline-link tab could not be inspected because the browser rejected an empty/invalid tab URL. No inline-link download pass is claimed. |
| Audio completion and normal End | Received audio covers the final result; End is separate from playback completion. | PASS: the final Main presentation completed; 291 active received PCM frames followed the final worker-result text. The exact call ended normally. | An earlier test runner ended just before a separate callback started; that interrupted playback remains a failed audio check. Physical microphone/speaker quality and glitch-free endurance are not certified. |
| Fast voice without lost capability | Measure actual end-of-input to first received audio. | FAIL: the two latest default High native calls took approximately 42.6 and 79.0 seconds. Native execution overlapped active memory maintenance. | Sub-two-second Voice remains unmet. The effect of maintenance on latency was not isolated. Native/model duration includes tools and continuation and must not be labeled pure inference. |

## Retained checks

- Public projection: 148 distinct affected passing cases using retained valid evidence and the
  latest six confirmed plain-stream, Responses and secret-redaction consumers. This was not one
  fresh 148-case run.
- Deadline lifecycle: 121 distinct passing cases with retained evidence; the final focused
  36-case run passed. Earlier code reproduced cleanup-error escape and persistent-session rebind.
- Earlier in the same readiness lap, actual Chrome computer-use work produced the correct page
  heading and a downloaded file. Telegram returned the correct synthetic arithmetic answer,
  persisted it on reload and preserved an unsent draft. Those unchanged cases were reused rather
  than described as fresh post-load sends.
- Configured models and efforts, credentials, original source history and unrelated development
  work were preserved. No task-specific route, new manager, forced callback, model downgrade or
  database repair was added.

## Guardrails for future changes and tests

Follow the [continuous relationship diagram](../../../docs/architecture/cognitive-system.md#continuous-relationship)
and [Queen/worker contract](../../../docs/requirements_and_learnings/55_Parallel_Work_Orchestration.md#locked-queen-bee-and-worker-bee-user-experience).
The existing [Voice delivery contract](../../../docs/requirements_and_learnings/capabilities/voice.md)
permits either a separate Main-authored completion or a result merged into active Main. NTA after
an already delivered result is valid; tests must not force a duplicate announcement.

File visibility and temporary silence do not prove speech completion. Correlate the exact
presentation state and received audio before ending a test call. Keep superseded attempts and
failures distinct from later success. Do not drop the public-prefix guard, process identity proof,
owner authority, memory, Feelings, tools or cognitive work to improve a timing result.
