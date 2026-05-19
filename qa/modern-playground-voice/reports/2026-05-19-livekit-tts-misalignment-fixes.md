# LiveKit TTS Misalignment Fixes

Date: 2026-05-19

## Scope

Applied the fix set from the visible-text-before-TTS investigation while preserving the shipped
async transcript contract. `sync_transcription` remains false/unset by default and true only by
explicit operator opt-in.

## Changes Verified

- Voice gateway now uses current LiveKit Python `RoomOptions(text_output=TextOutputOptions(...))`
  instead of deprecated `RoomOutputOptions`.
- Session-level deprecated `metrics_collected` usage was removed from the voice worker. Runtime
  latency logging now uses `conversation_item_added` per-turn fields and provider TTS metrics when
  the selected TTS implementation emits them.
- xAI standalone TTS now defaults `optimize_streaming_latency=1` through the shared capability
  contract, config compiler, launcher env propagation, and worker runtime. Operators can disable it
  with `VIVENTIUM_XAI_TTS_OPTIMIZE_STREAMING_LATENCY=0`.
- The xAI LiveKit plugin wrapper now feature-detects the private `_connect_ws` hook before patching
  it. If a future plugin release removes or changes that private hook, the worker logs a warning and
  continues without claiming the optimization was applied.
- LiveKit agent/plugin pins are updated to `1.5.10`.
- Voice requirements and runtime docs were updated to record the current LiveKit API shape,
  non-deprecated latency metric contract, and xAI latency optimization tradeoff.

## Evidence

- Current docs checked:
  - LiveKit text/transcription docs use `RoomOptions(text_output=TextOutputOptions(sync_transcription=False))`.
  - LiveKit session docs state Python uses unified `RoomOptions`.
  - LiveKit observability docs mark session-level `metrics_collected` as deprecated and document
    `conversation_item_added` per-turn latency fields.
  - xAI TTS docs document websocket `optimize_streaming_latency` values `0` and `1`.
- Local package check verified `livekit-agents`, `livekit-plugins-openai`, `livekit-plugins-xai`,
  `livekit-plugins-silero`, `livekit-plugins-elevenlabs`, `livekit-plugins-turn-detector`, and
  `livekit-plugins-assemblyai` at `1.5.10`.
- Current LiveKit xAI plugin code still lacks a public constructor option for
  `optimize_streaming_latency`, so the temporary private-hook wrapper is still required.
- A post-fix real call before log rotation emitted the new xAI and per-turn metrics. Sanitized
  values: xAI provider TTFB was about `254ms`; LiveKit assistant metrics showed LLM TTFT about
  `2355ms`, TTS TTFB about `411ms`, and E2E latency about `4264ms`. This supports that the
  remaining perceived delay is not primarily xAI first audio, but browser first-audio playout still
  needs direct measurement.
- Detached runtime restart completed after the final code change. Health probes returned:
  LibreChat API `200`, LibreChat frontend `200`, modern playground `200`, and voice gateway `ok`.
- Playwright browser QA opened the modern playground root page after restart. The page title was
  `Viventium Voice Assistant`, voice settings were visible, and browser console output had no
  errors or warnings beyond the standard React DevTools informational message.
- Review-only Claude pass found no blockers. It called out the private xAI hook risk, the by-design
  async text/audio ordering, and browser first-audio measurement as residual risks. The private-hook
  risk was mitigated with feature detection and a regression test in this pass.

## Automated Checks

- `python -m py_compile` for the voice worker and updated worker test file: `PASS`.
- Targeted voice tests after private-hook guard: `39 passed`.
- Full voice gateway test suite: `263 passed`, `13 subtests passed`, with one existing Python
  `audioop` deprecation warning.
- Full config compiler suite: `92 passed`.
- `git diff --check`: `PASS`.

## Status

- `PASS`: requested misalignment fixes applied while leaving `sync_transcription` behavior unchanged.
- `PASS`: docs, config compiler, launcher propagation, package pins, and worker tests align.
- `PASS`: local browser root page and runtime health verified after detached restart.
- `PARTIAL`: exact user-perceived first audible browser frame was not measured in this pass. Server
  metrics now expose the missing attribution needed for that next measurement.
- `PARTIAL`: the private xAI wrapper is guarded but should be retired once LiveKit exposes a public
  `optimize_streaming_latency` parameter.
