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
- If no follow-up exists, the gateway keeps raw background insights silent in live voice and ends
  the turn without an extra spoken message.
- The shipped background follow-up window is shared with LibreChat and Telegram:
  - `runtime.background_followup_window_s`
  - default `30` seconds
- This preserves the Phase A / Phase B contract:
  - Phase A: immediate main-agent response is heard right away
  - Phase B: only a true main-agent follow-up conclusion is heard later
- Internal `cortex_insight` content remains available in LibreChat's background-insight UI, but it
  must not be voiced directly into the modern playground transcript/TTS path.
- Voice follow-up requests set `suppressBackgroundCortices=true` to prevent recursion.

## Agent LLM Routes and Fallback
- The live call LLM defaults to the selected agent provider/model.
- A dedicated Agent Builder `Voice Chat Model` may override the live-call LLM for voice only.
- A dedicated Agent Builder `Fallback Model` is the secondary provider/model route used when the
  primary agent route fails before producing assistant text.
- The `Voice Chat Model` page has its own fallback model. Voice calls use that voice-specific
  fallback first, then inherit the general `Fallback Model` only when the voice fallback is unset or
  unavailable before model initialization.
- Fallback is retry-once and user-configured. Runtime does not silently choose a hidden model from
  machine defaults, account identity, prompt text, or provider labels.
- Fallback uses the normal provider auth path, including connected accounts. A valid connected
  OpenAI account can therefore recover from an Anthropic rate limit when the agent fallback route is
  set to an OpenAI model.
- If fallback is unset or fails too, the voice gateway should speak an honest error class. Provider
  rate limits use the rate-limit message, not the generic service outage message.
- Assistant route disclosure reports the effective call LLM separately from STT/TTS settings and
  may include the configured fallback route as secondary route information.

## Streaming-First TTS Contract
- Live voice calls must begin speech from incremental LLM output; they must not wait for the full
  final assistant answer before TTS starts.
- If a provider supports native incremental input streaming, the voice gateway must use that native
  stream directly.
- If a provider does not support native incremental input streaming, the gateway may adapt it to a
  streaming surface, but wrapper layers must not downgrade a native-streaming provider back to
  sentence-buffered fallback behavior.

## Turn Stability and Endpointing
- Voice ingress requests that resolve to the same `(callSessionId, conversationId, parentMessageId)`
  within the coalescing window are merged onto one launched stream instead of forking sibling turns.
- Coalesced text must preserve ingress order, not whichever request wins the Mongo race first.
- Canonical saved assistant history strips voice-control tags after synthesis so reloads, exports,
  and downstream surfaces do not retain raw `<emotion .../>` markup.
- AssemblyAI-backed calls now default to provider endpointing plus VAD:
  - `VIVENTIUM_TURN_DETECTION=stt` when the active STT provider supports endpointing
  - Silero VAD remains attached for interruption responsiveness
  - the default `AgentSession` endpointing guardrail is reduced for this mode so runtime does not
    stack a second large delay on top of AssemblyAI end-of-turn detection
  - the compiler now emits explicit AssemblyAI endpointing defaults for the shipped path using the
    documented Universal Streaming baseline rather than leaving plugin/API defaults ambiguous:
    - `VIVENTIUM_ASSEMBLYAI_END_OF_TURN_CONFIDENCE_THRESHOLD=0.01`
    - `VIVENTIUM_ASSEMBLYAI_MIN_END_OF_TURN_SILENCE_WHEN_CONFIDENT_MS=100`
    - `VIVENTIUM_ASSEMBLYAI_MAX_TURN_SILENCE_MS=1000`
  - the env/config surface still uses the older `MIN_END_OF_TURN_SILENCE_WHEN_CONFIDENT` name for
    backward compatibility, but the worker now maps that value onto AssemblyAI's current
    `min_turn_silence` provider parameter
- Default turn-handling profile:
  - `VIVENTIUM_VOICE_MIN_INTERRUPTION_DURATION_S=0.5`
  - `VIVENTIUM_VOICE_MIN_ENDPOINTING_DELAY_S=0.0` for `stt`
  - `VIVENTIUM_VOICE_MAX_ENDPOINTING_DELAY_S=1.8` for `stt`
  - `VIVENTIUM_VOICE_MIN_INTERRUPTION_WORDS=1` for `stt` / `turn_detector`
  - `VIVENTIUM_VOICE_FALSE_INTERRUPTION_TIMEOUT_S=2.0`
  - `VIVENTIUM_VOICE_RESUME_FALSE_INTERRUPTION=true`
  - `VIVENTIUM_VOICE_MIN_CONSECUTIVE_SPEECH_DELAY_S=0.2` for `stt` / `turn_detector`
- Pure `vad` mode remains available when explicitly configured or when the active STT path does not
  expose endpointing support.
- Semantic turn detection is available through explicit config/env (`turn_detector`), but it is not
  silently forced on for every AssemblyAI install.
- If explicit `turn_detector` mode is requested but the detector weights are not cached locally,
  runtime falls back cleanly to `stt` and logs the downgrade instead of failing mid-call.
- Worker logs emit normalized turn-end reasons so real calls can be debugged without guessing:
  - `vad_silence`
  - `stt_end_of_turn`
  - `semantic_turn_detector`
- Durable per-call turn logs also come from the LibreChat voice route:
  - `[VIVENTIUM][voice/chat] user_turn_completed ...`
  - keyed by `callSessionId`, `conversationId`, `parentMessageId`, and `requestId`

## Voice-Mode Prompt Contract (Provider-Aware)
Voice-mode instructions are injected by `buildVoiceModeInstructions(voiceProvider)` in
`surfacePrompts.js`. Each TTS provider gets its own branch:

### Cartesia (Sonic 3)
- Live voice calls use Cartesia WebSocket contexts (`/tts/websocket`) so text deltas can be pushed
  as they arrive from the LLM. The bytes endpoint remains for one-request/full-text surfaces.
- Cartesia joins continuation transcripts verbatim. The voice gateway preserves leading and
  trailing whitespace on streamed transcript chunks after markup/nonverbal normalization, including
  whitespace-only deltas, so chunk boundaries do not collapse words such as `What's` + ` up?`.
- Current default request contract:
  - `Cartesia-Version: 2026-03-01`
  - `model_id: sonic-3`
  - `voice.mode: id`
  - default `voice.id: e8e5fffb-252c-436d-b842-8879b84445b6` (Megan)
- The playground Cartesia submenu is a voice selector, not a model selector. Cartesia calls always
  use Sonic-3; the public voice choices are Megan and Lyra
  (`6ccbfb76-1fc6-48f7-b71d-91ac6298247b`).
- Prompt instructions expose the complete Sonic-3 emotion list from Cartesia docs. Primary
  high-reliability values are `neutral`, `angry`, `excited`, `content`, `sad`, and `scared`.
- Preferred tag form: self-closing `<emotion value="excited"/>` (state change applies to subsequent text).
- Wrapper form also supported: `<emotion value="excited">TEXT</emotion>` (scoped to wrapped text).
- SSML tags: `<break time="1s"/>`, `<speed ratio="1.2"/>`, `<volume ratio="0.8"/>`, `<spell>TEXT</spell>`.
- Nonverbal token: `[laughter]` (sent as literal token to Cartesia).
- Non-Cartesia HTML tags are stripped; Cartesia SSML tags are preserved through synthesis.
- With `VIVENTIUM_VOICE_DEBUG_TTS=1`, Cartesia request logs include JSON-escaped transcript chunks
  and joined continuation text so leading/trailing spaces can be inspected without logging API keys.

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
- Fallback routing is streaming-aware: if the primary provider fails before audio starts, the
  gateway preserves streaming with the next provider instead of forcing the whole turn back through
  a non-streaming wrapper.
- Fallback sanitization is capability-driven and uses structural parsing of completed markup
  regions; runtime wrappers must not own hardcoded provider-name or token-vocabulary logic.

## Cartesia Emotion Handling
- Cartesia accepts one `generation_config.emotion` per API request.
- The LLM owns emotional markup generation. Runtime does not infer user intent or invent emotion
  tags; it only parses LLM-selected Cartesia tags so provider requests stay valid.
- The voice gateway splits `<emotion>` segments and synthesizes each with its own emotion.
- For LLM-selected emotion segments, the Cartesia request includes both:
  - the selected `<emotion value="..."/>` SSML prefix in `transcript`
  - the same value in `generation_config.emotion`
- Self-closing `<emotion value="..."/>` acts as a state change for subsequent text.
- Nonverbal markers (`[laughter]`) are split into their own mini synthesis calls.
- Non-Cartesia HTML tags and structural bracket stage directions are stripped for fallback
  providers.
- Modern playground transcript display uses a separate stateful structural filter:
  - TTS receives the original LLM text with Cartesia markup.
  - The user-visible transcript receives display-sanitized deltas.
  - Partial fragments such as `<em` or `[laugh` are buffered until the tag/stage direction can be
    classified, so voice-control markup never flashes in the transcript.

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
- The launcher refreshes the voice-gateway venv when installed package versions no longer satisfy
  `voice-gateway/requirements.txt`; package presence alone is not a valid health check.
- The semantic turn detector plugin is optional. When installed, the launcher pre-downloads the
  exact multilingual detector assets (`onnx/model_q8.onnx` and `languages.json`) before worker
  boot. The voice gateway also loads that plugin lazily, only when semantic turn detection is
  actually selected, so a normal local `vad` route does not boot-noise on an unused detector cache.
- A missing optional turn-detector package must not crash worker import. The worker treats that as
  `HAS_TURN_DETECTOR=false` and continues with the configured `stt` or `vad` path.
- AssemblyAI endpointing knobs are config-owned and optional. If not set, Viventium leaves the
  provider/plugin defaults intact instead of hardcoding additional silence thresholds.
- `whisper_local` / `pywhispercpp` inherits the shared interruption knobs and saved-route contract,
  but it remains a StreamAdapter + Silero VAD path. It does not get AssemblyAI-native endpointing
  knobs or semantic turn-detector behavior.
- Local Whisper routes default `VIVENTIUM_VOICE_WORKER_LOAD_THRESHOLD=inf`; CPU load during model
  warm-up is not a reliable overload signal and must not make LiveKit stop dispatching jobs to a
  healthy local worker.
- Local Whisper routes default `VIVENTIUM_VOICE_INITIALIZE_PROCESS_TIMEOUT_S=120` so cold-start
  model loading can complete before the idle process is considered failed.

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
- `VIVENTIUM_CARTESIA_API_VERSION` (default `2026-03-01`)
- `VIVENTIUM_CARTESIA_MODEL_ID` (Sonic-3 only; non-`sonic-3` values are rejected by compiled config and ignored with a warning at runtime)
- `VIVENTIUM_CARTESIA_VOICE_ID` (default Megan: `e8e5fffb-252c-436d-b842-8879b84445b6`; Lyra: `6ccbfb76-1fc6-48f7-b71d-91ac6298247b`)
- `VIVENTIUM_CARTESIA_WS_URL`
- `VIVENTIUM_CARTESIA_MAX_BUFFER_DELAY_MS` (default `120` for live voice)
- `VIVENTIUM_CARTESIA_SEGMENT_SILENCE_MS`
- `VIVENTIUM_VOICE_MIN_INTERRUPTION_DURATION_S`
- `VIVENTIUM_VOICE_MIN_INTERRUPTION_WORDS`
- `VIVENTIUM_VOICE_MIN_ENDPOINTING_DELAY_S`
- `VIVENTIUM_VOICE_MAX_ENDPOINTING_DELAY_S`
- `VIVENTIUM_VOICE_FALSE_INTERRUPTION_TIMEOUT_S`
- `VIVENTIUM_VOICE_RESUME_FALSE_INTERRUPTION`
- `VIVENTIUM_VOICE_MIN_CONSECUTIVE_SPEECH_DELAY_S`
- `VIVENTIUM_TURN_DETECTION` (`vad`, `stt`, `turn_detector`)
- `VIVENTIUM_ASSEMBLYAI_END_OF_TURN_CONFIDENCE_THRESHOLD`
- `VIVENTIUM_ASSEMBLYAI_MIN_END_OF_TURN_SILENCE_WHEN_CONFIDENT_MS`
- `VIVENTIUM_ASSEMBLYAI_MAX_TURN_SILENCE_MS`
- `VIVENTIUM_ASSEMBLYAI_FORMAT_TURNS`
- `VIVENTIUM_VOICE_INITIALIZE_PROCESS_TIMEOUT_S`
- `VIVENTIUM_VOICE_IDLE_PROCESSES`
- `VIVENTIUM_VOICE_WORKER_LOAD_THRESHOLD`
- `VIVENTIUM_VOICE_JOB_MEMORY_WARN_MB`
- `VIVENTIUM_VOICE_JOB_MEMORY_LIMIT_MB`
- `VIVENTIUM_VOICE_PREWARM_LOCAL_TTS`
- `VIVENTIUM_VOICE_TURN_COALESCE_ENABLED`
- `VIVENTIUM_VOICE_TURN_COALESCE_WINDOW_MS`
- `VIVENTIUM_VOICE_TURN_COALESCE_WAIT_MS`
- `VIVENTIUM_VOICE_TURN_COALESCE_POLL_MS`
- `VIVENTIUM_VOICE_TURN_COALESCE_RETURN_WINDOW_MS`
- `VIVENTIUM_VOICE_TURN_COALESCE_TTL_S`
- `VIVENTIUM_VOICE_LOG_LATENCY=1`
- `VIVENTIUM_VOICE_DEBUG_TTS=1`

## Operational Notes
- Use `./viventium-librechat-start.sh` to keep LibreChat + voice gateway secrets aligned.
- Call sessions expire; stale sessions will cause auth failures.
- Live call LLM selection follows the agent primary model by default and only changes when the agent
  has an explicit Voice Chat Model configured.
- Voice transport settings such as STT/TTS provider selection do not change the call LLM route.
- Per-call voice-route overrides recompute the effective turn-taking defaults from the final STT
  provider for that call. A call that overrides from `whisper_local` to `assemblyai` must not keep
  stale VAD-only defaults from the machine route.
- If you previously relied on legacy machine-level `voice.fast_llm_provider`, migrate that choice to
  the agent `Voice Chat Model` fields instead; the machine-level field is ignored for call LLM
  selection.
- Background insights must still be generated in the main system (ensure background agent model/provider config is valid).

## Known Limitations
- Voice insight polling is time-bounded; late insights may require longer timeouts if models are slow.
