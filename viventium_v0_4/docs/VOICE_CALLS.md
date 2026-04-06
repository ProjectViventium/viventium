<!-- === VIVENTIUM START ===
Document: Voice Calls (LiveKit + Voice Gateway)
Added: 2026-01-09
=== VIVENTIUM END === -->

# Voice Calls (LiveKit + Voice Gateway)

This document explains how voice calls are integrated and how they preserve the same background-agent behavior as text chat.
The design intentionally opens the LiveKit Agents Playground instead of rebuilding a custom call UI.

## High-Level Flow
1. User clicks the call button in LibreChat.
2. `POST /api/viventium/calls` creates a short-lived call session and returns a Playground deep-link.
3. The LiveKit Agents Playground connects to the room using `roomName` + `callSessionId`.
4. LiveKit dispatches the voice gateway agent to the room.
5. Voice Gateway streams audio → LibreChat `/api/viventium/voice/chat` and speaks the response.
6. Background insights are surfaced after the main response (same contract as text).

### Playground Deep-Link Parameters
- `roomName`: LiveKit room id
- `callSessionId`: authentication context for the voice gateway
- `agentName`: LiveKit dispatch agent name
- `autoConnect=1`: auto-join on load

## Localhost vs Public Voice Origins
- Localhost remains the canonical default:
  - LibreChat launches the playground on `localhost`
  - the modern playground must keep `ws://localhost:7888` for localhost callers
- When a configured public playground origin is in use, `api/connection-details` may return the
  configured public LiveKit WSS URL instead.
- Public-browser voice access also depends on the non-HTTP media path:
  - direct LiveKit TCP/UDP media when the network allows it
  - TURN/TLS fallback when the public HTTPS edge is enabled

## Key Code Paths
- Call button: `LibreChat/client/src/components/Viventium/CallButton.tsx`
- Call session API: `LibreChat/api/server/routes/viventium/calls.js`
- Call session storage/auth: `LibreChat/api/server/services/viventium/CallSessionService.js`
- Voice endpoints: `LibreChat/api/server/routes/viventium/voice.js`
- Voice insight retrieval: `LibreChat/api/server/services/viventium/VoiceCortexInsightsService.js`
- Voice gateway worker: `voice-gateway/worker.py`
- Voice gateway LLM bridge: `voice-gateway/librechat_llm.py`
- SSE parsing helpers: `voice-gateway/sse.py`
- Playground deep-link handling: `agents-playground/src/pages/index.tsx`

## Voice Parity with Background Agents
- Voice calls use the same backend orchestration as text (`AgentClient` + `BackgroundCortexService`).
- The voice gateway streams the main response first, then retrieves background insights.
- After the main response completes, the voice gateway polls:
  - `GET /api/viventium/voice/cortex/:messageId`
- If a follow-up message exists, it is spoken verbatim for natural parity.
- If no follow-up exists, the gateway falls back to a formatted summary of insights.
- Voice follow-up requests set `suppressBackgroundCortices=true` to prevent recursion.

## Voice-Mode Prompt Contract (Provider-Aware)
Voice-mode instructions are injected by `buildVoiceModeInstructions(voiceProvider)` in
`surfacePrompts.js`. Each TTS provider gets its own branch:

### Cartesia (Sonic 3)
- Recommended emotions: `neutral`, `excited`, `content`, `sad`, `angry`, `scared`, `curious`, `calm`, `surprised`, `contemplative`.
- Preferred tag form: self-closing `<emotion value="excited"/>` (state change applies to subsequent text).
- Wrapper form also supported: `<emotion value="excited">TEXT</emotion>` (scoped to wrapped text).
- SSML tags: `<break time="1s"/>`, `<speed ratio="1.2"/>`, `<volume ratio="0.8"/>`, `<spell>TEXT</spell>`.
- Nonverbal token: `[laughter]` (sent as literal token to Cartesia).
- Non-Cartesia HTML tags are stripped; Cartesia SSML tags are preserved through synthesis.

### xAI (Grok Voice)
- Allowed nonverbal markers: `[laugh]`, `[sigh]`, `[gasp]`, `[whisper]`, `[hmm]`, `[chuckle]`.
- No XML/SSML tags (`<emotion/>`, `<break/>`, etc.).
- Tone is expressed naturally via word choice and pacing.

### Chatterbox (Local MLX)
- Allowed nonverbal markers: `[laugh]`, `[sigh]`, `[gasp]`.
- No emotion SSML tags.

### ElevenLabs / OpenAI (Fallback)
- No emotion tags, no bracket stage directions.
- Prompt explicitly prohibits both to prevent literal readout.

## Cartesia Emotion Handling
- Cartesia accepts one `generation_config.emotion` per API request.
- The voice gateway splits `<emotion>` segments and synthesizes each with its own emotion.
- Self-closing `<emotion value="..."/>` acts as a state change for subsequent text.
- Nonverbal markers (`[laughter]`) are split into their own mini synthesis calls.
- Non-Cartesia HTML tags and bracket nonverbal markers are stripped for fallback providers.

## Call Session Security
- Voice gateway requests are authenticated via:
  - `X-VIVENTIUM-CALL-SESSION` (callSessionId)
  - `X-VIVENTIUM-CALL-SECRET` (shared secret)
- The secret is configured with `VIVENTIUM_CALL_SESSION_SECRET` and must match across LibreChat and the voice gateway.
- Call sessions are stored in MongoDB with a TTL index (see `CallSessionService.js`).

## Required Environment Variables (Voice)
- LiveKit:
  - `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `LIVEKIT_URL`, `LIVEKIT_API_HOST`
  - `NEXT_PUBLIC_LIVEKIT_URL`
- Viventium voice:
  - `VIVENTIUM_PLAYGROUND_URL`
  - `VIVENTIUM_VOICE_GATEWAY_AGENT_NAME`
  - `VIVENTIUM_CALL_SESSION_SECRET`
- TTS providers:
  - `ELEVEN_API_KEY` (or `ELEVENLABS_API_KEY`)
  - `OPENAI_API_KEY`
  - `XAI_API_KEY` (optional)
  - `CARTESIA_API_KEY` (Cartesia Sonic-3)

<!-- === VIVENTIUM START ===
Section: Voice STT providers + VAD (v1 parity)
Added: 2026-01-11
=== VIVENTIUM END === -->
## STT Providers (Streaming + VAD)
Voice calls must use a streaming-capable STT or wrap non-streaming STT with VAD.
Defaults mirror v1:
- `VIVENTIUM_STT_PROVIDER=whisper_local` (alias of `pywhispercpp`, local whisper.cpp)
- `VIVENTIUM_VOICE_STT_PROVIDER` overrides STT provider just for voice calls.
- `STT_PROVIDER` (legacy) is honored if `VIVENTIUM_STT_PROVIDER` is unset.

Supported providers:
- `whisper_local` / `pywhispercpp` (local whisper.cpp, wrapped in StreamAdapter+Silero VAD)
- `assemblyai` (requires `ASSEMBLYAI_API_KEY`)
- `openai` (uses `VIVENTIUM_OPENAI_STT_MODEL`, wrapped in StreamAdapter+VAD when available)

VAD tuning (shared with v1):
- `VIVENTIUM_STT_VAD_MIN_SPEECH` (default `0.1`)
- `VIVENTIUM_STT_VAD_MIN_SILENCE` (default `0.5`)
- `VIVENTIUM_STT_VAD_ACTIVATION` (default `0.4`)
- `VIVENTIUM_STT_VAD_FORCE_CPU` (optional)

Notes:
- Silero VAD requires `livekit-plugins-silero` and Python <= 3.12.
- The launcher rebuilds the voice-gateway venv if Silero is missing or Python 3.13+ is detected.

<!-- === VIVENTIUM START ===
Section: Voice concurrency bypass + LiveKit idempotency
Added: 2026-01-11
=== VIVENTIUM END === -->
## Voice Concurrency and LiveKit Idempotency
- LibreChat's concurrent limiter can stall voice streams; voice sessions bypass it by default.
- Override with `VIVENTIUM_VOICE_BYPASS_CONCURRENCY=false` if you want standard limits.
- LiveKit startup is idempotent:
  - If a Viventium LiveKit container is running, the launcher reuses it.
  - If port 7880 is occupied by another stack, the launcher waits for readiness and uses it.
  - The launcher will not spawn a second LiveKit mid-session.

<!-- === VIVENTIUM START ===
Section: Modern playground
Added: 2026-01-11
=== VIVENTIUM END === -->
## Modern Playground Variant
- `--modern-playground` launches the agent-starter-react UI from `agent-starter-react`.
- The deep-link contract is identical (roomName, callSessionId, agentName, autoConnect).

## Optional Voice Knobs
- `VIVENTIUM_VOICE_MODE_PROMPT` (override voice-mode instructions)
- `VIVENTIUM_VOICE_CORTEX_DETECT_TIMEOUT_MS` (0 = disable for voice)
- `VIVENTIUM_VOICE_FOLLOWUP_TIMEOUT_S`
- `VIVENTIUM_VOICE_FOLLOWUP_INTERVAL_S`
- `VIVENTIUM_VOICE_FOLLOWUP_GRACE_S`
- `VIVENTIUM_CALL_SESSION_TTL_MS` (override call session TTL)
- `VIVENTIUM_CARTESIA_SEGMENT_SILENCE_MS`
- `VIVENTIUM_VOICE_LOG_LATENCY=1`
- `VIVENTIUM_VOICE_DEBUG_TTS=1`

## Operational Notes
- Use `./viventium-librechat-start.sh` to keep LibreChat + voice gateway secrets aligned.
- Call sessions expire; stale sessions will cause auth failures.
- Live call LLM selection follows the agent primary model by default and only changes when the agent
  has an explicit Voice Chat Model configured.
- Voice transport settings such as STT/TTS provider selection do not change the call LLM route.
- If you previously relied on legacy machine-level `voice.fast_llm_provider`, migrate that choice to
  the agent `Voice Chat Model` fields instead; the machine-level field is ignored for call LLM
  selection.
- Background insights must still be generated in the main system (ensure background agent model/provider config is valid).

## Known Limitations
- Voice insight polling is time-bounded; late insights may require longer timeouts if models are slow.
