# Modern Playground Visible Text Before TTS Investigation

Date: 2026-05-19

## Question

Why can the modern LiveKit playground show the assistant response before audible TTS begins?

## Evidence Reviewed

- Runtime status and sanitized LiveKit configuration.
- Voice gateway logs for a recent real playground call.
- Mongo call-session and user voice-route preference state, with raw identifiers and transcript text omitted.
- Modern playground route UI through Playwright, stopping before room join to avoid disrupting an active call.
- Voice gateway, LiveKit transcript, Local Chatterbox, and LibreChat LLM bridge code.
- Current LiveKit/xAI docs, LiveKit Agents source, PyPI versions, and relevant LiveKit community threads.
- Review-only Claude second opinion against sanitized evidence.

## Findings

- The active real playground call was configured as Whisper.cpp local STT plus xAI Eve TTS from saved playground preferences. The no-session landing page still advertised Local Chatterbox as the default route, so root/default route and active call route differed.
- Voice logs for that call selected xAI standalone TTS using the current xAI streaming endpoint. The logs captured STT/end-of-user-turn timing and LibreChat LLM first-token/stream-done timing, but did not capture xAI TTS first-audio or browser first-audio playout.
- Viventium currently starts LiveKit with transcription synchronization disabled. That makes the transcript eligible to render as text before it is paced with audio playout. This exposes TTS latency to the user as "text appeared, then voice started later."
- The exact post-text-to-audio gap is not proven from the current logs because TTS TTFB and browser first-audio timestamps are missing.
- If Local Chatterbox is selected, it has a separate built-in first-audio floor: 1.0 second MLX streaming interval plus 500 ms prebuffer before the first PCM chunk is pushed, with local TTS prewarm disabled by default when local Whisper STT is active.
- LiveKit docs now recommend `RoomOptions` / `TextOutputOptions`; this runtime still uses deprecated `RoomOutputOptions`. The current docs also expose per-turn assistant `tts_node_ttfb`, which this runtime is not yet logging.
- The installed LiveKit Agents packages are behind current PyPI. No specific version-fix claim was proven; this remains an upgrade-review item, not a root cause.
- Current xAI docs expose `optimize_streaming_latency`; the observed LiveKit xAI plugin path did not show that option in the basic endpoint parameters.

## QA Status

- `PASS`: DB route state inspected with raw IDs and private text omitted from this report.
- `PASS`: Playwright verified the pre-call UI showed xAI Eve for the active call and Local Chatterbox on the no-session landing page.
- `PASS`: Voice logs verified xAI TTS route, async transcription setting, deprecation warnings, STT timing, and LLM TTFT/stream-done timing.
- `PARTIAL`: Real user audio playout was not measured. The active room was not joined to avoid disrupting the call, and no scratch-room browser waveform capture was run in this pass.
- `PARTIAL`: TTS TTFB is missing for xAI turns because the current runtime does not log per-plugin/per-turn TTS metrics.

## Recommended Next Evidence

1. Log per-turn `tts_node_ttfb`, `llm_node_ttft`, and `e2e_latency` from current LiveKit metrics surfaces.
2. Add xAI/local-TTS handoff timestamps: first LLM delta, first phrase released to TTS, TTS dispatch, first audio chunk.
3. Capture a scratch-room browser run with visible transcript first-paint and first non-silent audio frame timestamps.
4. Migrate the voice worker from deprecated `RoomOutputOptions` to `RoomOptions(text_output=TextOutputOptions(...))`.
5. Review the `livekit-agents` 1.5.5 to 1.5.10 changelog before making upgrade claims.
