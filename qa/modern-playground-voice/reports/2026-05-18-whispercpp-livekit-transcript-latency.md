# 2026-05-18 Whisper.cpp LiveKit Transcript Latency Investigation

## Summary

- Result: PARTIAL investigation pass for local Whisper.cpp transcript latency; product behavior
  change remains pending instrumentation and regression coverage.
- Build/source under test: current local Viventium checkout and nested voice gateway.
- Runtime/artifact under test: local modern playground, local LiveKit voice route, local Whisper.cpp
  STT route, voice gateway logs, and focused automated suites.
- Environment: local development runtime with public-safe synthetic evidence.
- Tester: Codex.
- Related change: investigation record for local transcript latency and proposed next instrumentation.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `MPV-001` | PARTIAL PASS | Playwright surface check, voice gateway logs, local Whisper benchmark, focused tests | Investigation explains latency but does not ship a behavior change. |
| `MPV-UC-001` | PARTIAL PASS | Local playground route and provider state verified | Full user acceptance remains tied to future instrumentation/fix run. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `MPV-UC-001` | Start a call from an authenticated LibreChat conversation and send a simple typed or spoken prompt. | Modern Playground and local voice runtime evidence. | PARTIAL | Playwright confirmed visible route is Whisper.cpp Local `large-v3-turbo`. | Voice gateway logs, local config, recent call-session state, focused tests, and Claude review supported the root cause. | Sub-stage instrumentation and post-fix user acceptance remain pending. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Modern Playground voice transcription.
- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md` and
  `docs/requirements_and_learnings/14_Voice_Latency_and_Memory_RCA.md`.
- Use case: `MPV-UC-001`.
- QA case: `MPV-001`.
- Expected result: transcript latency root cause is proven through the real voice path and supporting
  code/log/config evidence before behavior changes.
- Actual evidence: local route, logs, metrics, benchmark, and focused tests indicate the dominant
  delay is the local Whisper final-only route with a silence gate plus model inference.
- Remaining gap or fix: add sub-stage instrumentation and rerun user acceptance before changing
  product behavior.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Voice call requirements, `MPV-UC-001`, `MPV-001`. |
| Code owning path | Which code path owns the behavior? | Voice gateway local Whisper provider and modern playground transcript rendering path. |
| Docs and nested docs/repos | Which docs or nested repo docs define the expected behavior? | Voice requirements docs and nested voice gateway code. |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | Focused voice gateway tests, local Whisper benchmark, Playwright surface check. |
| Local/external prerequisite state | Which required local service, provider, Docker-backed sidecar, OAuth grant, API key, model, or hosted dependency was proven healthy or degraded? | Local LiveKit and local Whisper route were active; no hosted STT provider was in use. |
| Logs | Which sanitized logs confirm or contradict the result? | Voice gateway latency and VAD logs summarized below. |
| DB/state/persistence | Which sanitized state, DB count/hash, persisted message, config, or artifact confirms it? | Recent call-session state and canonical local config summarized below. |
| Generated/shipped artifact | Which generated config, compiled bundle, prebuilt helper, or installed artifact was inspected when applicable? | Runtime env and canonical local config were inspected. |
| Real user path | Which browser/computer, Telegram, voice, installer, CLI, MCP/tool, scheduler, or GlassHive path was used like a user? | Playwright opened the modern voice playground and confirmed the visible STT route. |
| Visual/UX comparison | Does the visible UI/UX or delivered result match the expected behavior and supporting evidence? | Visible route matched local Whisper configuration; sub-stage latency remains to be instrumented. |
| Not run / blocked | Which required surface was not run, and why is the result partial or blocked? | No product behavior change was shipped in this investigation record. |

## User-Grade Evidence

- Surface exercised: Playwright browser and local Modern Playground voice runtime evidence.
- Real user path: opened the local modern voice playground and inspected visible route state.
- Visible outcome: Whisper.cpp Local `large-v3-turbo` was shown as the listening route.
- Expanded/detail state: route details showed local listening and speaking choices.
- Persistence/reload result: not applicable for this latency investigation record.
- Backend/log/DB confirmation: voice gateway logs, local config, and recent call-session state
  supported the same route and delay attribution.
- Final model/runtime wording check: this report does not claim a behavior fix; it records root cause
  and next instrumentation.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for any required visible-UI, detail-state,
  persistence, or wording step.

## Automated Evidence

```bash
Focused local Whisper provider, worker turn handling, and Silero VAD config tests passed.
Playwright opened the local modern voice playground and observed the visible route.
Claude review-only pass agreed with the root-cause classification and recommended instrumentation before product behavior changes.
```

## Problem Statement

Public-safe preserved task: identify why Whisper.cpp takes about 3 seconds on LiveKit before
transcribed text appears; inspect nested repos, nested docs, logs, telemetry, DB, code, configs,
and env vars; break delay stages into no more than 250 ms per part; run real tests; validate the
breakdown and proposed fix with a review-only Claude pass.

## Result

Root cause: the visible user transcript is gated by the local Whisper.cpp STT architecture, not the
modern playground renderer.

The active route is local `pywhispercpp` / `large-v3-turbo`. That provider is final-only
(`streaming=False`, `interim_results=False`) and is wrapped in LiveKit's Silero `StreamAdapter`.
The local Whisper provider injects a 1.0 s VAD silence gate before it hands audio to Whisper, then
`large-v3-turbo` inference usually takes about 0.9-1.4 s and can spike to about 3.1 s. The
frontend renders `lk.transcription` chunks when they arrive.

## Evidence

- Runtime env confirmed local LiveKit and `VIVENTIUM_STT_PROVIDER=whisper_local`,
  `VIVENTIUM_STT_MODEL=large-v3-turbo`, `VIVENTIUM_VOICE_LOG_LATENCY=1`.
- Canonical local config confirmed `voice.mode=local`, `voice.stt_provider=whisper_local`, and
  `voice.stt_model=large-v3-turbo`; no turn detector, VAD, or endpointing override was present.
- DB check confirmed recent call sessions requested STT provider `pywhispercpp` with
  `large-v3-turbo`; voice ingress event count was zero, so ingress coalescing was not the delay
  source.
- Voice gateway logs showed local Whisper VAD `min_speech=0.35s`, `min_silence=1.0s`,
  `activation=0.4`, `max_buffered_speech=600.0s`.
- Voice gateway logs showed `turn_detection=vad`, `turn_end_reason=vad_silence`,
  `min_endpoint=1.4s`, `max_endpoint=3.0s`, and `sync_transcription=False`.
- Parsed recent LiveKit EOU metrics:
  - `transcription_delay`: n=22, min=1.898 s, p50=2.099 s, p90=2.425 s, max=4.116 s.
  - `pywhispercpp` inference: n=23, min=0.888 s, p50=1.166 s, p90=1.432 s, max=3.073 s.
  - Paired `transcription_delay - inference`: n=22, min=0.953 s, p50=1.008 s, p90=1.043 s,
    max=1.060 s.
- The paired delta matching 1.0 s is consistent with the local Whisper VAD silence gate.
- Synthetic real local Whisper benchmark with generated speech and the actual `large-v3-turbo`
  model showed warm transcription runs of about 0.92-1.03 s for a short utterance.
- Playwright opened the modern voice playground at the local dev URL and confirmed the visible
  listening route is Whisper.cpp Local `large-v3-turbo`; browser console had no application error.
- Focused tests passed: `51 passed, 1 warning` for local Whisper provider, worker turn handling,
  and Silero VAD config tests.
- Claude review-only pass agreed the root cause is structurally correct and recommended making the
  250 ms bucket budget explicit, separating transcript-display latency from agent-reply latency,
  and instrumenting before changing product behavior.

## 250 Ms Timing Budget

Typical p50 visible transcript path, about 2.1 s:

| Window | Stage |
| --- | --- |
| 0-250 ms | Last speech frame reaches VAD; accumulated-speech timing tracks true end of speech. |
| 250-500 ms | Silero silence accumulation continues; local Whisper 1.0 s silence gate not met. |
| 500-750 ms | Silence accumulation continues; no final transcript can emit yet. |
| 750-1000 ms | Silence gate reaches the local Whisper `min_silence=1.0s` threshold. |
| 1000-1250 ms | StreamAdapter merges frames and enters final-only `pywhispercpp` recognition. |
| 1250-1500 ms | `large-v3-turbo` inference is running. |
| 1500-1750 ms | `large-v3-turbo` inference continues. |
| 1750-2000 ms | Inference completes on fast/warm turns; final transcript event is built. |
| 2000-2100 ms | LiveKit publishes `lk.transcription`; browser handler updates React state. |

Tail path, about 3-4.1 s:

| Window | Stage |
| --- | --- |
| 0-250 ms | Last speech frame reaches VAD; silence accumulation starts. |
| 250-500 ms | Silero silence accumulation continues. |
| 500-750 ms | Silence accumulation continues; no final transcript can emit yet. |
| 750-1000 ms | Local Whisper `min_silence=1.0s` threshold is reached. |
| 1000-1250 ms | StreamAdapter merges frames and enters final-only recognition. |
| 1250-1500 ms | `large-v3-turbo` inference begins. |
| 1500-1750 ms | Inference continues. |
| 1750-2000 ms | Inference continues beyond warm p50. |
| 2000-2250 ms | Inference tail continues under longer audio, cold-ish worker, or host contention. |
| 2250-2500 ms | Inference tail continues. |
| 2500-2750 ms | Inference tail continues. |
| 2750-3000 ms | Inference tail continues toward the worst observed local turn. |
| 3000-3250 ms | Worst observed inference tail begins to finish. |
| 3250-3500 ms | Final transcript event/publish can occur for slower turns. |
| 3500-3750 ms | Slowest observed turn is still waiting on inference/publish completion. |
| 3750-4000 ms | Slowest observed turn is still waiting on inference/publish completion. |
| 4000-4100 ms | Worst observed transcript metric finishes and publishes. |

## Proposed Fix Order

1. Add sanitized timing instrumentation first, behind `VIVENTIUM_VOICE_LOG_LATENCY=1`: VAD final
   audio ready, frame duration/count, merge, mono conversion, resample, WAV write, Whisper
   transcribe, post-filter, final event return, LiveKit publish, and browser first-seen/render.
2. Re-baseline cold, warm, and post-idle turns with the new stage logs.
3. Pursue no-product-change latency wins before changing behavior: confirm process/model cache
   survival, prewarm behavior, thread contention, and whether the temp WAV hop can be removed.
4. If product behavior change is acceptable, lower local Whisper VAD silence only with explicit
   regression coverage for chopped utterances and hallucination rate.
5. For sub-second visible text, add a true streaming/interim STT path or offer an explicit
   user-selected faster/quantized local model for live transcription.

## Remaining Gaps

- The current logs do not yet expose sub-stage timings inside `_recognize_impl`; stage attribution
  below the VAD gate and total Whisper inference is inferred from code and benchmark evidence.
- This investigation measured visible user transcript latency. Agent first-audio latency is a
  separate path and includes endpointing, LLM, and TTS timing.

## Findings

- Defects: local transcript latency is primarily gated by final-only local Whisper behavior plus the
  local silence gate and inference time.
- Regressions: none proven by this investigation record.
- Flakes: none recorded.
- Environment issues: no hosted STT route was active; local route behavior explains the result.
- Residual risks: sub-stage instrumentation and user acceptance are required before any product
  behavior change.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
