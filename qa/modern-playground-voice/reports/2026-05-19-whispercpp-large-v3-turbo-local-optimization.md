# Whisper.cpp Large-v3-turbo Local Optimization QA - 2026-05-19

## Scope

Investigate why local Whisper.cpp `large-v3-turbo` text can appear about 2 seconds after completed
speech in the Modern Playground / LiveKit path, identify the exact delay stages, apply safe config
and runtime fixes, and validate with real browser/fake-microphone LiveKit QA.

## Findings

- The frontend receives LiveKit transcription events without a meaningful extra render delay. The
  visible delay is owned by the local STT/turn path.
- The default local route is `pywhispercpp` / `large-v3-turbo`, wrapped by LiveKit's StreamAdapter
  and Silero VAD.
- The intentional end-of-speech budget is `0.5s` VAD silence. LiveKit's VAD endpointing delay is
  effectively `max(VAD silence, min_endpoint)` for this mode, so the configured `0.5s` endpoint does
  not add another full `0.5s`.
- Temp WAV write/read was not the main delay, but it was unnecessary. Direct in-memory 16 kHz mono
  float32 PCM removes that surface and exposes clean per-stage timings.
- The largest avoidable delay was pywhispercpp/whisper.cpp doing more encoder context work than the
  short local LiveKit final-chunk path needs. Direct benchmarks showed `audio_ctx=768` with
  `single_segment=true` and `no_context=true` substantially reduces short/pause inference. After
  review, the reduced context is now duration-gated so long chunks fall back to the default
  whisper.cpp audio context instead of risking silent tail truncation.
- Local Chatterbox TTS prewarm and replacement Whisper prewarm can contend with active local STT on
  the same machine. TTS prewarm is now opt-in for local Whisper, and replacement Whisper prewarm is
  delayed while active calls run.
- Setting local Whisper idle processes to zero is not acceptable on this machine: real fake-mic QA
  showed early audio can be missed while the job process cold-loads.

## Changes Validated

- `pywhispercpp_provider.py`
  - in-memory PCM path instead of temp WAV files
  - sanitized stage timing log: combine, mono, resample, float32, transcribe, filter
  - prewarm performs a small real inference
  - `large-v3-turbo` defaults to `VIVENTIUM_STT_AUDIO_CTX=768`,
    `VIVENTIUM_STT_SINGLE_SEGMENT=true`, and `VIVENTIUM_STT_NO_CONTEXT=true` for short chunks only;
    `VIVENTIUM_STT_REDUCED_AUDIO_CTX_MAX_AUDIO_S=12.0` gates the default reduced-context path
- `worker.py`
  - local Whisper keeps a warm idle worker
  - local Chatterbox TTS prewarm defaults off for local Whisper
  - replacement local-model prewarm waits while active voice jobs are present; active markers are
    cleared by job shutdown rather than generic participant-disconnect events

## Real QA Evidence

All LiveKit QA used synthetic non-personal TTS WAV fixtures through Chromium fake microphone into
the real Modern Playground, LiveKit server, voice worker, LibreChat route, and Mongo persistence.
Fixture variants with leading silence were used so the fake microphone did not start speech before
the agent subscribed.

| Case | Result | Persisted transcript | Key timing evidence |
| --- | --- | --- | --- |
| Short speech | PASS | one Listen-Only transcript row | `transcription_delay=1.128s`; `transcribe_ms=619.2`; conversion/resample/float32 `1.3ms` total |
| 0.7s pause continuation | PASS | one continued transcript row with both clauses | first segment `transcription_delay=1.345s`, `transcribe_ms=839.9`; second segment `transcription_delay=1.684s`, `transcribe_ms=1149.1` |
| Long speech | PASS | one complete transcript row | `transcription_delay=1.765s`; `transcribe_ms=1251.4`; resample `4.1ms` |

Follow-up post-restart short calls also passed, but showed machine-load sensitivity:

| Case | Result | Key timing evidence | Observed cause |
| --- | --- | --- | --- |
| Short immediately after restart | PASS | `transcription_delay=2.533s`; `transcribe_ms=1965.6` | runtime/browser startup plus high host CPU/GPU load |
| Short while host load remained high | PASS | `transcription_delay=3.591s`; `transcribe_ms=3069.2` | concurrent host processes (`replayd`, browser/WindowServer/camera/other apps) consumed CPU/GPU/ANE resources |
| Short after Claude fixes + final restart | PASS | `transcription_delay=1.078s`; `transcribe_ms=623.9`; one transcript row; expected text matched; Whisper.cpp Local `large-v3-turbo` route confirmed | validates the patched runtime is live after duration-gate and marker fixes |

These runs confirm the code path is improved, but this computer can still produce 2-3.5s tails when
the host is busy. The timing logs correctly attribute those tails to whisper.cpp inference, not VAD,
temp files, Mongo, or frontend rendering.

Direct pywhispercpp benchmark on this machine:

| Fixture | Current-style params | Optimized params |
| --- | ---: | ---: |
| Short | `1878-2891ms` | `1010-1232ms` |
| 0.7s pause | `2586-2942ms` | `1126-1418ms` |
| Long | `1266-1498ms` | `1250-1628ms` |

Post-Claude duration-gate regression:

| Fixture | Result | Key timing evidence |
| --- | --- | --- |
| 19.704s generated TTS speech | PASS | `HAS_AUDIO_CTX=false`; `transcribe_ms=1469.9`; tail marker words preserved |

## 250ms Delay Breakdown

Optimized short path, measured from completed speech to final transcript:

| Window | Stage |
| --- | --- |
| `0-250ms` | Silero VAD is accumulating post-speech silence |
| `250-500ms` | VAD silence reaches the local `0.5s` threshold |
| `500-750ms` | StreamAdapter sends final audio to pywhispercpp; PCM combine/resample/float32 is under `2ms`; Whisper inference begins |
| `750-1000ms` | `large-v3-turbo` inference continues |
| `1000-1128ms` | final transcript publishes through LiveKit metrics path |

Optimized pause continuation:

| Window | Stage |
| --- | --- |
| `0-500ms` | VAD silence gate for first clause |
| `500-1000ms` | first Whisper final inference |
| `1000-1345ms` | first final transcript/event/persist path |
| `1345-1845ms` | user continuation after `0.7s` pause is treated as the same persisted Listen-Only message |
| `1845-2345ms` | VAD silence gate for second clause |
| `2345-3000ms` | second Whisper final inference |
| `3000-3529ms` | second final transcript updates the same persisted message |

## Remaining Gaps

- pywhispercpp is still final-only. It cannot display true interim tokens. Sub-second final text for
  every turn would require either a smaller/quantized model tradeoff or true streaming/interim STT.
- The current local VAD fallback can produce multiple STT final chunks for human pauses. Listen-Only
  persistence coalesces the 0.7s continuation into one message, but a full route-mode "edit the same
  user turn while canceling/resuming AI" behavior still needs the higher-level continuation-turn
  design.
- Reduced `audio_ctx=768` remains a short-chunk optimization. The default path now falls back to the
  full/default audio context for chunks longer than `12.0s`; long ambient Listen-Only accuracy should
  still get a dedicated >20s WER/text-equality regression.
- The installed LiveKit Agents SDK is still `1.5.5`; upstream `1.5.10` should be tested in a
  controlled branch for newer interruption, endpointing, and metrics fixes.
- The harness proves backend persistence and screenshots the playground, but the closed transcript
  panel means `pageMatchedExpected=false`; future UI QA should explicitly open the transcript panel
  before asserting visible body text.

## Claude Review Follow-up

Review-only Claude flagged two concrete patch risks that were accepted and fixed before closeout:

- The reduced `audio_ctx=768` optimization needed a duration gate to avoid long-chunk truncation.
- Active-call markers should not be cleared by generic participant-disconnect events. The marker now
  clears on shutdown or after disconnect only when the room has no remaining remote participants.

Both are now covered by unit tests. Claude also correctly narrowed the remaining host-load tail to
"inference-stage wall clock scales with general host load"; this report should not claim a
Metal/CPU/ANE sub-root-cause beyond that evidence.

Final fake-microphone logs after the marker refinement showed replacement prewarm delayed while the
call was active and then started shortly after the final participant disconnected, avoiding both
active-call contention and the earlier full `20s` post-call wait.

## Commands Run

- `python -m pytest tests/test_pywhispercpp_provider.py tests/test_worker_turn_handling.py -q`
- `python -m pytest tests -q`
- direct pywhispercpp real-inference run on generated 19.704s TTS WAV
- `bin/viventium dev-runtime activate-current --validate --restart --allow-protected-folder --allow-dirty-local-testing`
- `node qa/modern-playground-voice/scripts/livekit_synthetic_audio_qa.js ...`
