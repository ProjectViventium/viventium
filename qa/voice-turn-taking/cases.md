# Voice Turn Taking QA Cases

## Case ID Convention

Use stable `VCTURN-NNN` IDs for voice turn taking cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `VCTURN-001` | Interruptions, silence, and end-of-turn detection produce natural call turns and no stale follow-up speech. | User-visible behavior matches source, docs, persisted state, and logs | LiveKit/playground call, VAD/EOT logs, transcript | `tests/release/test_voice_playground_dispatch_contract.py` plus user-grade QA when visible | NOT YET RUN (cataloged 2026-05-17; next feature run required) |
| `VCTURN-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | NOT YET RUN (cataloged 2026-05-17; next feature run required) |
| `VCTURN-003` | Local Whisper turn ending stays fast while barge-in interrupts TTS without implicitly cancelling authoritative work. | Pauses feel responsive; interruption is natural; explicit task cancellation remains separate and truthful | Modern Playground, Voice Gateway, LibreChat task/stream routes, Mongo messages, voice logs | Voice gateway/LibreChat focused tests plus real microphone/audio QA | Historical 2026-05-18 endpointing PASS; current interruption-versus-cancellation path is `PARTIAL` pending real audible rerun |
| `VCTURN-004` | Synthetic speech with natural pauses is injected through the real LiveKit microphone path. | A fast endpointing profile does not split a resumed thought into multiple persisted turns | Modern Playground fake microphone, LiveKit, Whisper.cpp, LibreChat voice route, Mongo | Synthetic TTS fixture generator, fake-microphone QA harness, voice route tests, DB/log inspection | 2026-05-18 PASS |

## `VCTURN-001` - Core User Flow

- Requirement: Interruptions, silence, and end-of-turn detection produce natural call turns and no stale follow-up speech.
- Risk covered: implementation, docs, and user-visible behavior drift apart.
- Preconditions: local Viventium runtime or the specific feature harness is available with synthetic, public-safe data.
- Steps:
  1. Exercise the feature through the real user surface, not only a unit test.
  2. Compare the visible result with source code, generated/runtime config, logs, persisted state, and the owning requirement doc.
  3. Capture a public-safe report with expected result, forbidden result, evidence, residual risk, and follow-up.
- Expected result: the feature behaves as documented and every supporting layer agrees.
- Forbidden result: backend logs, mocks, source inspection, or model completions are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, generated/runtime state summary, and docs/case links.
- Automation: `tests/release/test_voice_playground_dispatch_contract.py` plus any narrower feature tests discovered during implementation.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## `VCTURN-002` - Public-Safe Evidence Record

- Requirement: public QA artifacts must be reproducible and free of secrets, personal data, local paths, raw IDs, and private screenshots.
- Risk covered: a useful local QA run cannot be safely reviewed or published.
- Preconditions: a dated QA report is created for this feature.
- Steps:
  1. Review the report and related diffs for local absolute paths, account identifiers, tokens, raw logs, raw DB rows, private chats, and screenshots with private content.
  2. Keep raw/private evidence outside the public repo and summarize only public-safe counts, statuses, hashes, and conclusions.
  3. Link the report back to this case and the owning requirement doc.
- Expected result: the public report proves the behavior without leaking private/local data.
- Forbidden result: a report includes private transcripts, account identifiers, raw runtime dumps, local home paths, tokens, or secret-bearing command lines.
- Evidence to capture: public-safety scan result and link to the sanitized report.
- Automation: public-safety pattern scan plus relevant release tests.
- Last run: NOT YET RUN (cataloged 2026-05-17; run on each new public report).

## `VCTURN-003` - Fast Local Whisper Endpointing And Barge-In Interruption

- Requirement: local Whisper calls should not wait on a long fixed silence gate before submitting a
  turn, and user barge-in should stop active TTS while authoritative work continues unless the user
  separately cancels the task by id.
- Risk covered: a fast endpointing profile could chop utterances, or ordinary interruption could be
  mislabeled as backend cancellation and silently discard useful work.
- Preconditions: local Whisper route selected; canonical local stack or focused test harness
  available; synthetic public-safe audio/text only.
- Steps:
  1. Verify source/runtime config resolves local Whisper VAD min silence and local endpointing delay.
  2. Run a real local pywhispercpp benchmark with the selected model and record load/inference
     timings.
  3. Start the local playground in a real browser and confirm the selected listening route is visible.
  4. Barge in during audible assistant speech and verify TTS stops within the acceptance budget while
     the authoritative task continues to one linked-chat result.
  5. Separately cancel the task through its task-id control and verify the durable suppression
     barrier, truthful terminal state, and zero late user/memory output.
  6. Inspect logs and DB/state with public-safe summaries only.
- Expected result: the configured local endpointing remains responsive; barge-in stops speech while
  work continues; only explicit cancellation targets backend work and suppresses late output; the
  playground remains reachable with the local route visible.
- Forbidden result: a long hidden fixed silence gate remains; barge-in implicitly aborts useful
  work; interrupt and cancel are shown as the same state; cancellation is claimed without a durable
  barrier; private transcript or identifiers enter public QA.
- Evidence to capture: sanitized timing breakdown in 250ms slices, focused test output, real local
  STT benchmark, browser snapshot summary, runtime config/log summary, DB shape summary, and
  residual gaps.
- Automation: `voice-gateway/tests/test_*turn*`, `voice-gateway/tests/test_librechat_llm.py`,
  LibreChat `routes/viventium/__tests__/voice.spec.js`, and public-safe QA report.
- Last run: historical 2026-05-18 PASS for local Whisper endpointing and Listen-Only pause
  continuation. Current interruption-versus-explicit-cancellation acceptance is `PARTIAL` until the
  post-change audible/browser/persistence path passes under MPV-038.

## `VCTURN-004` - Synthetic Speech Pause Continuation

- Requirement: synthetic speech with natural pauses should exercise the real LiveKit/Whisper path,
  not only route mocks.
- Risk covered: a `0.5s` silence endpoint can correctly submit quickly but still split a resumed
  human thought into multiple persisted turns.
- Preconditions: local runtime running; synthetic public-safe WAV fixtures available; local
  Whisper.cpp route selected.
- Steps:
  1. Generate short, long, `0.7s` pause, and `1.5s` pause fixtures with local TTS or a platform
     fallback.
  2. Open the modern playground in Chromium with the WAV file as fake microphone input.
  3. Start the call, enable the microphone if prompted, and wait for the voice worker to persist
     Listen-Only transcripts.
  4. Assert pause fixtures produce one transcript message containing both clauses.
  5. Verify logs, ingress records, DB cleanup counts, and public-safe report evidence.
- Expected result: short and long speech persist complete synthetic text; `0.7s` and `1.5s` pauses
  persist as one continued transcript message inside the continuation window.
- Forbidden result: worker dispatch relies only on token room config on local LiveKit; real Mongo
  drops continuation fields missing from mocks; a resumed pause creates two transcript rows.
- Evidence to capture: fixture manifest, browser/fake-mic result JSON, screenshot summary, voice
  timing logs, DB row counts, cleanup counts, and public-safety scan.
- Automation: `qa/modern-playground-voice/scripts/generate_synthetic_speech_fixtures.py` and
  `qa/modern-playground-voice/scripts/livekit_synthetic_audio_qa.js`.
- Last run: 2026-05-18 PASS in
  `qa/modern-playground-voice/reports/2026-05-18-synthetic-audio-livekit-continuation.md`.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Voice Turn Taking. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `VCTURN-UC-001` | On LiveKit/playground call, VAD/EOT logs, transcript, verify that interruptions, silence, and end-of-turn detection produce natural call turns and no stale follow-up speech. | owning requirement for `VCTURN-001` / `VCTURN-001` | LiveKit/playground call, VAD/EOT logs, transcript | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to VCTURN-001. | User-visible behavior matches source, docs, persisted state, and logs | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `VCTURN-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `VCTURN-002` / `VCTURN-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to VCTURN-002. | The user sees an honest setup, retry, or degraded-state result for VCTURN-002; no fake success is accepted. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `VCTURN-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `VCTURN-002` / `VCTURN-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to VCTURN-002. | VCTURN-002 remains correct after the persistence or parity step and final wording matches evidence. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
