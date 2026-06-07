<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# Whisper.cpp Local Sub-10ms Telemetry And Resource Contention

Date: 2026-05-19

## Sanitized User Problem Statement

The user asked why local `whisper_local` / whisper.cpp `large-v3-turbo` can take roughly
two to three seconds for completed speech text to appear in the LiveKit playground, whether
Telegram local voice warming is wasting resources, whether Viventium should use one common
whisper.cpp service, and why the final transcript path in LiveKit metrics is so long. They
requested sub-0.01s timing evidence, checks across code/config/logs/docs/online sources, real
tests, and a Claude review-only second opinion.

## What Changed

- Added `VoiceLatencyDetail` instrumentation around the local STT `StreamAdapter` boundary:
  VAD start, VAD end, frame merge, wrapped whisper.cpp recognition, final transcript send, and
  total post-VAD-end time.
- Increased local pywhispercpp recognition timing precision to millisecond decimals for combine,
  mono, resample, float conversion, transcribe, and filter stages.
- Added high-precision LiveKit EOU metrics logging, including `on_user_turn_completed_delay` and
  event lag from metric timestamp to logger receipt.
- Raised the local whisper.cpp default job memory warning threshold from `1400MB` to `2200MB` so
  expected `large-v3-turbo` residency is not logged as abnormal pressure.

## Evidence Summary

Current runtime route:

- STT provider: `pywhispercpp` / `whisper_local`
- STT model: `large-v3-turbo`
- Hardware path reported by whisper.cpp: Metal enabled, Accelerate enabled, Core ML disabled
- Local STT VAD: `min_speech=0.35s`, `min_silence=0.5s`, activation `0.4`
- LiveKit turn handling: VAD mode, endpoint min `0.5s`, max `3.0s`
- LiveKit SDK: `livekit-agents==1.5.5`

Fresh real fake-microphone QA runs through Chromium + LiveKit + browser playground:

| Case | Browser/DB result | VAD silence | Merge | Whisper recognize | Final send | LiveKit metric lag | LiveKit transcription delay |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Short, first post-restart call | PASS, one transcript | 512.000ms | 0.055ms | 1879.368ms | 0.019ms | 11.435ms | 2439.615ms |
| Short, repeat new call | PASS, one transcript | 512.000ms | 0.018ms | 2600.198ms | 0.011ms | 1.544ms | 3086.390ms |
| Pause 700ms, part 1 | PASS, same persisted user transcript | 512.000ms | 0.036ms | 1008.546ms | 0.005ms | 0.293ms | 1463.337ms |
| Pause 700ms, part 2 | PASS, same persisted user transcript | 512.000ms | 0.029ms | 808.086ms | 0.010ms | 0.099ms | 1314.906ms |
| Final promoted-runtime smoke | PASS, one transcript | 512.000ms | 0.053ms | 653.342ms | 0.004ms | 0.229ms | 1157.474ms |

The final transcript handoff itself is not slow. The final send path measured `0.005-0.019ms`.
The visible delay comes from the required silence window plus pywhispercpp inference time. LiveKit's
`transcription_delay` is not an isolated post-STT UI metric in this setup; it includes the silence
window because LiveKit measures from the user-stopped-speaking timestamp to final transcript
availability.

Plain-English read: `transcription_delay` is the stopwatch for "I stopped talking" to "LiveKit has
a final transcript." On `whisper_local`, that stopwatch includes the local silence confirmation and
final-only whisper.cpp recognition. It does not mean LiveKit took seconds to publish after Whisper
finished, and it does not mean the browser or database took seconds to render/save the text.

The promoted-runtime smoke illustrates the breakdown:

- `512.000ms`: local VAD silence confirmation.
- `653.342ms`: pywhispercpp `large-v3-turbo` recognition.
- `0.053ms`: adapter frame merge.
- `0.004ms`: final transcript send from the adapter.
- `0.229ms`: LiveKit metric event lag to the logger.
- `1157.474ms`: LiveKit `transcription_delay`; this is the combined user-stopped-speaking-to-final
  transcript metric, not a post-recognition UI delay.

The memory warning finding is also config-owned: `VIVENTIUM_VOICE_JOB_MEMORY_WARN_MB` changes the
LiveKit worker warning threshold and `VIVENTIUM_VOICE_JOB_MEMORY_LIMIT_MB` changes the optional hard
job limit. Neither setting reduces whisper.cpp model memory; the local Whisper default was raised so
normal `large-v3-turbo` residency does not look like abnormal pressure.

## Resource Findings

- Telegram Viventium was not currently holding whisper.cpp. Its process had no pywhispercpp,
  ggml, whisper, or Metal mappings at inspection time.
- Telegram Codex had pywhispercpp libraries loaded, but no large-v3-turbo model file open and low
  resident memory, so it was not the cause of the measured LiveKit delay.
- Telegram Viventium is still configured for local whisper.cpp and will lazily load its own
  separate `large-v3-turbo` model if a Telegram voice note is transcribed. That can create a real
  future contention problem.
- LiveKit Agents runs local STT in per-job child processes with one warm idle process. Each call
  consumes the warm child, then a replacement child is prepared. This keeps call startup warm, but
  it still means the warm model is process-local, not a shared cross-surface whisper.cpp service.
- The replacement process now delays heavy local STT prewarm while an active call marker exists, but
  it still starts process initialization during the active call. In the observed run, the replacement
  did not load the whisper model until after the call ended.

## Interpretation

The original two to three second delay is not caused by the playground UI, DB persistence, or final
LiveKit publish/send. It is:

1. About `512ms` required silence from local VAD / endpointing.
2. About `808-2600ms` whisper.cpp `large-v3-turbo` recognition, depending on utterance length and
   process/job/machine state.
3. Less than `12ms` for final send plus metrics-path observation in the measured runs.

The current biggest architectural gap is that local whisper.cpp is not a common system service. Each
runtime surface can own its own pywhispercpp model instance. LiveKit's instance is currently the one
that matters for measured delay; Telegram is not the active cause today, but it can become one as
soon as Telegram voice uses local STT.

## Follow-Up Recommendation

- Keep the current 0.5s local VAD silence for `whisper_local`; lowering it further risks splitting
  natural short pauses, and the pause QA already validates same-turn continuation after a 700ms pause.
- Investigate whether pywhispercpp recognition should move off the worker asyncio loop. The current
  synchronous call is the measured recognition stage itself, but while it runs it can starve other
  coroutines in the same job process.
- Revisit warmup shape. A one-second silent warmup loads the model and warms one inference path, but
  it may not cover Metal specialization for normal two-to-six-second utterances or the duration-gated
  audio-context branch.
- Build or adopt a local whisper.cpp manager service before enabling more local-STT surfaces by
  default. It should own one loaded model, expose a local IPC/HTTP API, serialize or prioritize
  requests, give LiveKit calls priority over background Telegram jobs, and publish the same
  high-resolution stage timings. Benchmark IPC overhead before committing to the service boundary.
- Continue the LiveKit Agents 1.5.10 migration separately for newer per-turn `ChatMessage.metrics`,
  dynamic endpointing, adaptive interruption, playback metrics, and websocket/error fixes.
- Keep `VIVENTIUM_VOICE_JOB_MEMORY_WARN_MB` configurable. The shipped local whisper.cpp default is
  now above the observed normal `large-v3-turbo` resident footprint, while local Chatterbox-only
  routes keep the previous `1400MB` default.
- Treat the Telegram finding as a point-in-time snapshot. Telegram Viventium and Telegram Codex both
  lazily own separate local model instances, so a Telegram voice note during a LiveKit call can still
  create intermittent local whisper.cpp contention.

## Verification

- `voice-gateway`: `256 passed, 1 warning, 13 subtests passed`
- Release config and voice dispatch checks: `121 passed`
- Public boundary guard: `1 passed`
- Real fake-microphone Chromium + LiveKit QA:
  - `whispercpp-sub10ms-telemetry-20260519`: PASS
  - `whispercpp-sub10ms-telemetry-repeat-20260519`: PASS
  - `whispercpp-sub10ms-pause700-20260519`: PASS
  - `whispercpp-final-promoted-sub10ms-20260519`: PASS
- Direct pywhispercpp benchmark on the same machine:
  - current `audio_ctx=768`: median `955.6ms` for a 3.572s synthetic clip
  - default audio context: median `1051.1ms`
  - `audio_ctx=768` with multi-segment allowed: median `1004.6ms`
- Claude review-only pass agreed with the main root cause and adapter safety, and resulted in a doc
  correction for the duration-gated `audio_ctx` behavior plus added memory-threshold branch tests.
