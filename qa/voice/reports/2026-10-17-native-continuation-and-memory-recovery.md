# Native continuation and memory recovery — 2026-10-17

## Summary

Result: scoped functional repair PASS; fast-voice target FAIL; full Voice certification remains open.
Environment: current local development runtime.

QA scope: **blast-radius**. This report covers the native public-text projection and exact
deadline-cleanup repairs, their confirmed consumers, and the existing continuous conversation
flow. It does not claim the complete Voice acceptance bank passed.

Candidate identity: xPerfect merge `d0be7094a98072617f4ff64ccaa575ff6e5bbe38`
([PR 16](https://github.com/xPerfectAI/xPerfect/pull/16)), selected by `components.lock.json`. The reviewed native wheel and loaded source were compared before
acceptance. Existing valid Chat/Telegram and source-test evidence was retained. Raw prompts,
account identifiers, logs, audio, screenshots and source receipts remain private.

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Stream consistency: `VOICE-PERF-002` / `CORE-009`; the completion slice of
  `native-stream-no-polling-delay`; an empty silent envelope precedes eligible speech;
  `test_native_stream_preserves_canonical_leading_bytes` and actual received Voice result;
  the public prefix remains exact through completion; 227 snapshots and no matching terminal
  errors; latency and the wider journey remain open.
- Deadline recovery: `CORE-005` / `GOV-013`; retry a timed-out conversation without losing state;
  `test_deadline_success_preserves_binding_and_native_continuity_for_next_turn` and live memory
  retry; exact cleanup must preserve authority and history; two later runs completed on the same
  worker/session; full backfill remained in progress.
- Result delivery: `PW-052` / `CC-049`; the worker-result/file/End slice of
  `audible-main-and-interruption`; Main receives a worker result during the reply;
  received audio, exact file download and reload agree; wider interruption and endurance checks
  are not newly certified.

## Scope Run

| Requirement / use case | Expected result | Actual result | Remaining gap |
| --- | --- | --- | --- |
| Native streamed reply completes | Live text, final text and audio ranges use one public projection without changing already accepted text. | PASS: a real call exercised an empty silent envelope followed by eligible replies with leading separators. All 227 captured native text snapshots preserved the final public prefix; Main completed and the matching Core error window was clear. | Raw SSE network traffic was not captured. Native replay, durable completion, received audio, logs and visible chat form the proof. |
| Exact deadline recovery | Clean only the retained native generation, preserve failed history and controls, then reuse the conversation. | PASS: normal maintenance retry reused the same worker/session; two successor runs completed and the saved summary cursor advanced. Previous failed run/request and retained input history were unchanged. | Full historical backfill remained in progress. The live maintenance session was stateless; persistent-session continuity was verified by affected tests. |
| Queen → worker → Steer → spoken result | Main can use a real worker, consume its late result during the current reply and present it once. | PASS: injected audio was transcribed; Main answered the arithmetic request, dispatched an actual worker, received its result through Steer, and spoke the result. The later Main-authored NTA correctly avoided duplicate speech. | One observed journey is not exhaustive provider, concurrency or endurance acceptance. |
| File delivery and reload | The actual delivered file opens with exact content and stays attached after reload. | PASS: Chrome file-card downloads returned the exact synthetic 11-byte file in both observed cases; reload preserved the result. | A separate external inline-link tab could not be inspected because the browser rejected an empty/invalid tab URL. No inline-link download pass is claimed. |
| Audio completion and normal End | Received audio covers the final result; End is separate from playback completion. | PASS: the final Main presentation completed; 291 active received PCM frames followed the final worker-result text. The exact call ended normally. | An earlier test runner ended just before a separate callback started; that interrupted playback remains a failed audio check. Physical microphone/speaker quality and glitch-free endurance are not certified. |
| Fast voice without lost capability | Measure actual end-of-input to first received audio. | FAIL: the two latest default High native calls took approximately 42.6 and 79.0 seconds. Native execution overlapped active memory maintenance. | Sub-two-second Voice remains unmet. The effect of maintenance on latency was not isolated. Native/model duration includes tools and continuation and must not be labeled pure inference. |

## Full-View Evidence Checklist

| Evidence surface | Sanitized result |
| --- | --- |
| Requirement and use case | Traceability above names the selected completion, recovery and delivery slices; the scope table records expected and actual outcomes. |
| Code owning path | Pinned xPerfect `conversation_provider.py` owns the public projection; `service.py`, `store.py` and `profile_runtime.py` own exact cleanup and release proof. |
| Docs and nested docs/repos | The canonical cognitive-system diagram, locked Queen/worker contract, Voice capability and xPerfect architecture describe the same owners. |
| Scripts or harnesses | Existing synthetic audio injection and SDK runner, native test fixtures, read-only state readers and actual Chrome interactions were used. |
| Local/external prerequisite state | Configured native providers, local STT, TTS, LiveKit, Core, native service and linked chat were available; all five health endpoints responded successfully. |
| Logs | Matching Core terminal-error window was clear; native text events and durable completion corroborated the actual result. |
| DB/state/persistence | Worker completion, exact delivery, presentation state and linked messages agreed; two maintenance successors advanced saved state without changing old failures. |
| Generated/shipped artifact | Reviewed native wheel/source and active imported source matched; configuration and original development state were preserved. |
| Real user path | Voice input and received PCM, Chrome file download/reload, and retained Web/Telegram journeys were exercised. |
| Visual/UX comparison | Main's result and the file card stayed visible after reload and matched downloaded bytes. |
| Not run / blocked | Wider provider, hardware and endurance coverage were NOT RUN in this batch. The external inline-link tab could not be inspected; its download is not passed. |

## User-Grade Evidence

- Surface exercised: real LiveKit Voice path, linked Chrome chat and file cards; retained Web and Telegram evidence.
- Real user path: speak a synthetic arithmetic and file request, receive a real worker result through Main, download its file, reload and end the call.
- Visible outcome: correct arithmetic response and the exact synthetic file appeared in the same chat.
- Expanded/detail state: the delivered file card was opened and downloaded; the separate inline external-link tab could not be inspected and is not passed.
- Persistence/reload result: the response and attachment remained visible after Chrome reload.
- Local/external prerequisite state: configured native execution, STT, TTS and room transport were working for the observed call; this is not universal provider certification.
- Backend/log/DB confirmation: native completion, exact worker/result binding, presentation completion, received audio and persisted messages agreed; memory successor state advanced.
- Final model/runtime wording check: configured native Grok High produced the actual reply; no downgrade or generic completion receipt was substituted for Main's result. Latency remains failed.
- Substitution check: source tests, logs, state and model review support the evidence; they do not replace the actual Voice PCM, Chrome download or reload. Physical acoustic quality is not certified.

## Automated Evidence

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

## Findings

- Fixed: streamed/final public text disagreement and exact deadline cleanup blocking later admission.
- QA fixture finding: an earlier runner ended at file visibility before callback speech began. The later inline worker/Steer result was actually spoken and required no duplicate callback.
- Open: fast-voice latency, full historical backfill, the uninspected external inline-link download, and wider provider/hardware/endurance acceptance.

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

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies or credential-bearing commands.
- [x] No private chats, prompts, attachments, screenshots, personal emails, account identifiers or client data.
- [x] No conversation, message, call/session, Telegram, database or raw provider identifiers.
- [x] No local absolute paths, hostnames, machine names, private stack traces, state exports or runtime dumps.
- [x] Private evidence is summarized only through sanitized observations, counts and conclusions; the component commit is a public source identifier.
