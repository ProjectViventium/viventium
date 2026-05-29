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

Conversation continuity follows the call-session `agentId`. Provider-backed ephemeral agent
conversations may be stored with provider endpoints such as `xai`; the voice resolver may reuse
them only when the stored conversation `agent_id` exactly matches the active call session. Persisted
non-ephemeral agents still use endpoint `agents`; this carve-out exists for LibreChat's ephemeral
provider-agent storage shape.

Listen-Only Mode is the intentional exception to steps 5-6: the voice route saves the transcribed
turn as a structured ambient transcript record and returns `status=listen_only` without starting an Agents
stream, TTS, follow-up polling, tools, background cortices, title generation, or live memory writes.

### Playground Deep-Link Parameters
- `roomName`: LiveKit room id
- `callSessionId`: authentication context for the voice gateway
- `agentName`: LiveKit dispatch agent name
- `autoConnect=1`: auto-join on load for non-call-session sandbox links. Call-session links still
  show the Start chat gate because browser microphone publication requires a user gesture.

### Explicit Dispatch Startup Contract
- Call-session deep links use LiveKit publisher dispatch: the voice gateway joins only after the
  browser publishes the user's microphone track.
- The playground must not ask LiveKit to publish the microphone while `/api/connection-details` is
  still preparing the call-session token and dispatch metadata. That route may take several seconds
  under load; pre-connect microphone publication can otherwise hit LiveKit's signal-engine timeout
  before the room is connected. For explicit-dispatch calls, audio spoken before the room connects
  is not buffered.
- The browser's voice-settings display fetch is advisory. Slow or unavailable settings must not
  disable the Start chat gate because `/api/connection-details` rehydrates authoritative
  call-session voice settings server-side when the user starts the call.
- Voice-settings startup fetches in the browser, the playground proxy, and token hydration path are
  bounded by timeouts and must surface Viventium-specific recovery text rather than leaving the page
  in an indefinite loading state.
- Launcher-managed local runtimes prewarm the modern-playground startup routes
  `call-session-voice-settings`, `call-session-state`, and `connection-details` after the playground
  is reachable and before the voice worker starts. Prewarm failures are logged as startup evidence
  and should not prevent the rest of the runtime from starting; each prewarm request is bounded so
  route compilation cannot hold startup behind a long hang.
- The helper's steady-state readiness check uses the modern playground's lightweight `/api/health`
  route. It must not use the root page as a recurring health probe, because the root route renders
  the user-facing Next.js app and can create unnecessary dev-server work and log volume while local
  prod is simply staying available.
- The stable sequence is:
  1. fetch connection details with explicit call-session dispatch prepared, then connect the room
     with microphone disabled
  2. enable the microphone after the room is connected
  3. let LiveKit assign the publisher job to `librechat-voice-gateway`
  4. persist the active job/worker ids on the call session
- The Start chat gesture is single-flight. Once the user clicks it, the page should show connection
  and microphone progress, disable duplicate starts, and automatically enable the microphone after
  the room connects. The pre-connect muted state is an internal timeout-avoidance phase, not a user
  default. Browser permission and missing-device failures should be shown as explicit microphone
  errors, not as a connected muted call.
- `dispatchConfirmedAt` is durable call-session state that dispatch was prepared and the participant
  token was issued, not durable proof that LiveKit has already started a worker. The default path
  verifies or creates explicit LiveKit dispatch for call sessions; token-room-config dispatch is an
  opt-in compatibility mode. The authoritative runtime proof is the later publisher job
  receipt plus persisted `activeJobId`/`activeWorkerId`.
- The connection-details request that wins the Viventium dispatch claim force-creates explicit
  LiveKit dispatch. A `ListDispatch` entry from token room config is not enough evidence that a
  local LiveKit worker will be assigned.
- The playground retries transient `/api/connection-details`, call-state, and voice-settings fetch
  failures once during startup and never shows raw browser errors such as `Failed to fetch` as the
  user-facing recovery text.
- Visible-page End Call is intentional. Recovery logic should only restart after a background or
  sleep return, not after the user explicitly disconnects.

## Localhost vs Public Voice Origins
- The modern LiveKit playground (`agent-starter-react`) is the default enabled playground for
  voice-capable Viventium installs and launcher starts.
- The classic `agents-playground` UI is default-off and should only be installed or started for an
  explicit classic playground selection.
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
- Playground deep-link handling: `agent-starter-react/components/app/app.tsx`
- Playground sleep recovery: `agent-starter-react/hooks/useConnectionRecovery.ts`

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
- The installed default `VIVENTIUM_CORTEX_PHASE_A_NOTICE_MODE=any_activated_on_voice` lets voice
  Phase A start after the first true background activation with a generic "background is brewing"
  instruction. Final activation detection continues for Phase B, and text surfaces keep waiting for
  the full detection budget.
- `VIVENTIUM_VOICE_BACKGROUND_AGENT_DETECTION_ASYNC=false` is the shipped default so the main voice
  LLM does not start before Phase A has either seen the first true activation or reached the voice
  Phase A wait budget. Fully async detection remains available only as an explicit opt-in.
- Fully async opt-in detection uses `all_within_budget` semantics in the background so Phase B gets
  the complete activated set; the early `any_activated_on_voice` release applies to the shipped sync
  Phase A path.
- Internal `cortex_insight` content remains available in LibreChat's background-insight UI, but it
  must not be voiced directly into the modern playground transcript/TTS path.
- Voice follow-up requests set `suppressBackgroundCortices=true` to prevent recursion.

## Listen-Only Mode
- Listen-Only Mode is a persisted call-session state, mutually exclusive with Wing Mode.
- It uses the current STT route. Local `pywhispercpp` / WhisperCPP is the intended low-cost route,
  but runtime must not silently remap the user's selected listening provider.
- `/api/viventium/voice/chat` still authenticates the voice worker, resolves the conversation, and
  coalesces rapid or resumed speech. When `listenOnlyModeEnabled` is true, it saves a
  `listen_only_transcript` message with `tokenCount=0` and returns no stream id. Continuation is
  keyed by call session so speech resumed after a short pause updates the same saved transcript row
  even if the first segment already materialized a conversation parent.
- The Listen-Only ingress audit schema must persist `messageId` and `saved`; otherwise real Mongo
  drops the fields needed to update the same transcript row even though unit-test mocks appear to
  pass.
- The Listen-Only save path intentionally returns before `validateConvoAccess` and endpoint-option
  construction because the request is already bound to the server-side call session and no
  browser-supplied conversation target is trusted.
- The LiveKit LLM bridge treats `listenOnly=true` / `status=listen_only` as terminal silence.
- Listen-Only entries are not user-authored chat turns and are excluded from normal conversation
  recall corpus construction and live agent prompt history. The daily memory hardener can read them
  as `ambient_transcript` soft evidence.
- Same-microphone audio is not treated as diarized. Speaker labels come only from structured
  LiveKit participant/track metadata when that metadata is present.

## Agent LLM Routes and Fallback
- The live call LLM defaults to the selected agent provider/model.
- A dedicated Agent Builder `Voice Chat Model` may override the live-call LLM for voice only.
- A dedicated Agent Builder `Fallback Model` is the secondary provider/model route used when the
  primary agent route fails before producing assistant text.
- The `Voice Chat Model` page has its own fallback model. Voice calls use that voice-specific
  fallback first, then inherit the general `Fallback Model` only when the voice fallback is unset or
  unavailable before model initialization.
- Fallback eligibility is validated during call initialization, but fallback agent/tool/MCP
  initialization is lazy. It runs only if the primary route fails before producing assistant text.
  A healthy primary voice turn must not pay fallback MCP startup cost before first audio.
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
- Incremental text chunks sent toward TTS must be speakable phrase fragments. After audio has
  started, a punctuation-only delta such as `.` must not be pushed as an isolated synthesis input,
  because some providers speak it as a literal word. The gateway buffers phrase boundaries and
  drops orphan punctuation that arrives after its owning phrase was already emitted, while keeping
  numeric decimal splits intact. The LLM-side phrase buffer must also hold short unfinished
  post-terminal tails across whitespace when the next token can be a meaningful `?` or `!`; those
  marks must attach to the phrase before text reaches LiveKit TTS. Whitespace and length-driven
  flushes split at a safe whitespace boundary and keep the trailing word buffered, so provider
  continuation does not have to recover a missing word boundary from a leading-space-only next
  chunk.
- The final text emitted to TTS after phrase buffering must be speech-safe. The gateway strips or
  converts source/reference labels, citation remnants, markdown links/images, raw URLs, bare
  domains, emails, code fences, headings, list/table scaffolding, unknown angle tags, and stray
  spaces before punctuation before the chunk is forwarded to LiveKit TTS.
- For incident diagnosis, `VIVENTIUM_VOICE_LOG_TTS_INPUTS=1` emits `[VoiceTTSInput]` at the final
  provider boundary. Those lines show forwarded/dropped/control actions, provider class/transport,
  punctuation-only status, leading/trailing-space flags, and JSON-escaped text, so a spoken `dot`
  report can be traced to the exact chunk that did or did not reach TTS.
- Provider voice controls are preserved only when the active TTS route capability declares inline
  voice-control support. Plain providers and fallbacks such as OpenAI or ElevenLabs receive the
  same speech-safe text with provider markup stripped, without changing the selected model/provider.

## Turn Stability and Endpointing
- Voice ingress requests that resolve to the same `(callSessionId, conversationId, parentMessageId)`
  within the coalescing window are merged onto one launched stream instead of forking sibling turns.
- Coalesced text must preserve ingress order, not whichever request wins the Mongo race first.
- Canonical saved assistant history strips voice-control tags after synthesis so reloads, exports,
  and downstream surfaces do not retain raw `<emotion .../>` markup.
- Modern playground transcripts default to async LiveKit transcript output so the browser shows each
  assistant answer as soon as the LLM completes it instead of pacing words with TTS playout.
  `VIVENTIUM_VOICE_SYNC_TRANSCRIPTION=1` remains available as an opt-in caption QA mode. The
  gateway uses LiveKit `RoomOptions(text_output=TextOutputOptions(...))` for that setting. The
  playground reads LiveKit transcription streams by stream id so adjacent assistant answers cannot
  collapse into one transcript row.
- The gateway posts a per-turn `streamId` to `/api/viventium/voice/chat`, and the voice route
  preserves that id for the SSE subscription path. This keeps transport streams one-turn scoped
  while conversation id and parent message id continue to own persisted history continuity.
- Sequential spoken turns that arrive while a previous Phase B follow-up window is still open must
  use distinct stream ids unless they were intentionally coalesced inside the same ingress window.
  A later turn must not complete, replace, or subscribe to an older turn's stream.
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
  - `VIVENTIUM_VOICE_MIN_INTERRUPTION_WORDS=1` for provider/STT-owned routes such as AssemblyAI
  - `VIVENTIUM_VOICE_MIN_INTERRUPTION_WORDS=0` for local `whisper_local` / `pywhispercpp`,
    including semantic `turn_detector`, because local StreamAdapter transcripts can arrive only
    after VAD/final recognition
  - `VIVENTIUM_VOICE_FALSE_INTERRUPTION_TIMEOUT_S=2.0`
  - `VIVENTIUM_VOICE_RESUME_FALSE_INTERRUPTION=true`
  - `VIVENTIUM_VOICE_MIN_CONSECUTIVE_SPEECH_DELAY_S=0.2` for `stt` / `turn_detector`
  - `VIVENTIUM_VOICE_AEC_WARMUP_DURATION_S=3.0` for provider/STT-owned routes, matching LiveKit's
    AEC warmup protection
  - `VIVENTIUM_VOICE_AEC_WARMUP_DURATION_S=1.0` for local `whisper_local` / `pywhispercpp`; set it
    to `off`/`none` only for explicit local echo/barge-in experiments
- Pure `vad` mode remains available when explicitly configured or when the active STT path does not
  expose endpointing support.
- Semantic turn detection is available through explicit config/env (`turn_detector`), and local
  `whisper_local` / `pywhispercpp` may default to it when the optional plugin, exact cached
  multilingual assets, and LiveKit local inference runner are all ready before worker construction.
  AssemblyAI still defaults to provider endpointing (`stt`) rather than silently switching to
  semantic detection.
- If explicit `turn_detector` mode is requested but the detector weights are not cached locally or
  the LiveKit inference runner is not registered, runtime falls back cleanly to the provider-owned
  route (`stt` for AssemblyAI, local VAD for local Whisper) and logs the concrete downgrade
  status instead of failing mid-call.
- On first install or after a cache purge, local Whisper can start on the local VAD fallback if
  the turn-detector download cannot complete. The launcher retries the exact detector assets on a
  later start, so this is degraded turn-taking, not a broken voice route.
- Worker logs emit normalized turn-end reasons so real calls can be debugged without guessing:
  - `vad_silence`
  - `stt_end_of_turn`
  - `semantic_turn_detector`
- Durable per-call turn logs also come from the LibreChat voice route:
  - `[VIVENTIUM][voice/chat] user_turn_completed ...`
  - keyed by `callSessionId`, `conversationId`, `parentMessageId`, and `requestId`
- When LiveKit closes or cancels a voice LLM stream before the LibreChat final event, the voice
  gateway must post an authenticated abort for that specific `streamId` so barge-in stops backend
  generation instead of only stopping local audio playback.

## Voice-Mode Prompt Contract (Provider-Aware)
Voice-mode instructions are injected by `buildVoiceModeInstructions(voiceProvider)` in
`surfacePrompts.js`. Each TTS provider gets its own branch:

### Cartesia (Sonic 3)
- Live voice calls use Cartesia WebSocket contexts (`/tts/websocket`) so text deltas can be pushed
  as they arrive from the LLM. The bytes endpoint remains for one-request/full-text surfaces.
- Cartesia joins continuation transcripts verbatim. The voice gateway preserves leading and
  trailing whitespace on streamed transcript chunks after markup/nonverbal normalization, including
  whitespace-only deltas, so chunk boundaries do not collapse words such as `What's` + ` up?`.
- Incomplete bracket and angle-tag voice controls are buffered before Cartesia normalization, so
  split markers such as `[laugh` + `ter]` are normalized as `[laughter]` instead of being spoken as
  literal fragments.
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
- `VIVENTIUM_VOICE_LOG_TTS_INPUTS=1` enables the same `[VoiceTTSInput]` provider-bound payload logs
  without requiring broader LLM/display delta logging.

### xAI
- xAI is the user-facing provider label for standalone xAI TTS. The older Grok Voice Agent adapter
  remains opt-in only via `VIVENTIUM_XAI_TTS_API=voice_agent`.
- Inline tags: `[pause]`, `[long-pause]`, `[hum-tune]`, `[laugh]`, `[chuckle]`, `[giggle]`,
  `[cry]`, `[tsk]`, `[tongue-click]`, `[lip-smack]`, `[breath]`, `[inhale]`, `[exhale]`,
  `[sigh]`.
- Wrapping tags: `<soft>`, `<whisper>`, `<loud>`, `<build-intensity>`,
  `<decrease-intensity>`, `<higher-pitch>`, `<lower-pitch>`, `<slow>`, `<fast>`,
  `<sing-song>`, `<singing>`, `<laugh-speak>`, `<emphasis>`.
- xAI tags are not SSML and must not be mixed with Cartesia Sonic-3 tags such as `<emotion>`,
  `<speed>`, `<volume>`, `<break>`, `<spell>`, or `[laughter]`.
- Tone and emotion are controlled by natural wording plus the documented xAI tags; xAI has no
  Cartesia-style emotion parameter.

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
- `VIVENTIUM_STT_VAD_MIN_SPEECH` (default `0.1`; local Whisper fallback defaults to `0.35`
  unless explicitly configured)
- `VIVENTIUM_STT_VAD_MIN_SILENCE` (default `0.5`; local Whisper fallback also defaults to `0.5`
  unless explicitly configured)
- `VIVENTIUM_STT_VAD_ACTIVATION` (default `0.4`)
- `VIVENTIUM_STT_VAD_FORCE_CPU` (optional)

Notes:
- Silero VAD requires `livekit-plugins-silero` and Python <= 3.12.
- The launcher rebuilds the voice-gateway venv if Silero is missing or Python 3.13+ is detected.
- The launcher refreshes the voice-gateway venv when installed package versions no longer satisfy
  `voice-gateway/requirements.txt`; package presence alone is not a valid health check.
- The semantic turn detector plugin is optional. When installed, the launcher pre-downloads the
  exact multilingual detector assets before worker boot. The voice gateway verifies the ONNX model,
  `languages.json`, tokenizer/config files, and the LiveKit local inference runner before reporting
  semantic turn detection as ready. A partial detector snapshot or a cached detector without the
  registered `lk_end_of_utterance_multilingual` runner must fall back to the provider-owned route.
- A missing optional turn-detector package must not crash worker import. The worker treats that as
  `HAS_TURN_DETECTOR=false` and continues with the configured `stt` or `vad` path.
- AssemblyAI endpointing knobs are config-owned and optional. If not set, Viventium leaves the
  provider/plugin defaults intact instead of hardcoding additional silence thresholds.
- `whisper_local` / `pywhispercpp` inherits the shared interruption knobs and saved-route contract,
  but it remains a StreamAdapter + Silero VAD path when semantic turn detection is unavailable. It
  does not get AssemblyAI-native endpointing knobs. Its VAD fallback uses the shared `0.5s` silence
  budget plus a slightly longer minimum speech threshold than remote/STT-owned routes so short
  one-syllable room noise does not become a committed user turn. Local Whisper defaults the
  interruption word guard to `0` so barge-in can be driven by sustained audio activity instead of
  waiting for final local Whisper text.
- Local Whisper recognition feeds pywhispercpp in-memory 16 kHz mono float32 PCM and logs sanitized
  per-stage timings when voice latency logging is enabled. It does not write transcript text to the
  timing log.
- `large-v3-turbo` defaults to `VIVENTIUM_STT_AUDIO_CTX=768`, `VIVENTIUM_STT_SINGLE_SEGMENT=true`,
  and `VIVENTIUM_STT_NO_CONTEXT=true` only for short local LiveKit final chunks. The reduced context
  is duration-gated by `VIVENTIUM_STT_REDUCED_AUDIO_CTX_MAX_AUDIO_S` (default `12.0`) so longer
  chunks use pywhispercpp/whisper.cpp's default audio context. Set `VIVENTIUM_STT_AUDIO_CTX=0` to
  restore the default audio context for every chunk.
- Local Whisper routes default `VIVENTIUM_VOICE_WORKER_LOAD_THRESHOLD=inf`; CPU load during model
  warm-up is not a reliable overload signal and must not make LiveKit stop dispatching jobs to a
  healthy local worker.
- Local Whisper routes default `VIVENTIUM_VOICE_INITIALIZE_PROCESS_TIMEOUT_S=120` so cold-start
  model loading can complete before the idle process is considered failed.
- `VIVENTIUM_VOICE_JOB_MEMORY_WARN_MB` and `VIVENTIUM_VOICE_JOB_MEMORY_LIMIT_MB` pass through to
  LiveKit `WorkerOptions`. The warning value controls when LiveKit logs a large job process; it
  does not change whisper.cpp model memory. The limit value is a hard process limit, and the default
  `0` keeps that limit disabled.
- Local Whisper keeps one warm idle worker on Apple Silicon and prewarms whisper.cpp with a tiny
  inference, not just model load. Replacement prewarm waits for active calls and local Chatterbox TTS
  prewarm is opt-in on this route to avoid competing with active STT.
- LiveKit `transcription_delay` is the elapsed time from LiveKit's last evidence that the user was
  speaking to final transcript availability. For `whisper_local`, it normally includes the local VAD
  silence window plus final-only pywhispercpp recognition. It is not browser render time, DB
  persistence time, or post-recognition publish time.
- `transcription_delay` is useful because it points to the owning delay bucket: endpointing/VAD,
  local STT recognition, or final publish/UI. With `VIVENTIUM_VOICE_LOG_LATENCY=1`, compare it with
  `VoiceLatencyDetail` fields such as VAD silence, merge, recognition, final send, and metric lag.
- Local `large-v3-turbo` timing ballparks from current QA:
  - VAD silence: `~500-525ms` with the shipped `0.5s` local Whisper default.
  - Frame merge, final transcript send, and LiveKit metric event lag: normally sub-10ms; sustained
    values above `50ms` point outside whisper.cpp inference.
  - Warm short-turn pywhispercpp recognition: commonly `650-1000ms` after prewarm. First-call,
    post-idle, long-chunk, or contention tails around `1.8-2.6s` are known warning territory.
  - Warm short-turn LiveKit `transcription_delay`: usually `1.1-1.6s`. A `2-3s` value should be
    decomposed before blaming the browser or LiveKit publish path.

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
- `--modern-playground` launches the agent-starter-react UI from `agent-starter-react`; this is the
  default when no playground flag is supplied.
- `--classic-playground` is an explicit opt-in for the old `agents-playground` UI and is not part of
  the default runtime path.
- The deep-link contract is identical (roomName, callSessionId, agentName, autoConnect).

## Optional Voice Knobs
- `VIVENTIUM_VOICE_MODE_PROMPT` (override voice-mode instructions)
- `VIVENTIUM_CORTEX_PHASE_A_NOTICE_MODE` (default `any_activated_on_voice`)
- `VIVENTIUM_VOICE_BACKGROUND_AGENT_DETECTION_ASYNC` (default `false`; fully async opt-in)
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
- `VIVENTIUM_XAI_TTS_API` (default `tts`; `voice_agent` is legacy)
- `VIVENTIUM_XAI_VOICE` (default `Sal`; supported xAI TTS voices are `Ara`, `Eve`, `Leo`, `Rex`, `Sal`)
- `VIVENTIUM_XAI_LANGUAGE` (default `en`)
- `VIVENTIUM_XAI_TTS_WS_URL` (standalone TTS WebSocket endpoint)
- `VIVENTIUM_XAI_TTS_OPTIMIZE_STREAMING_LATENCY` (default `1`; set `0` to omit xAI websocket latency optimization)
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
- `VIVENTIUM_VOICE_LIVE_TURN_COALESCE_WINDOW_MS`
- `VIVENTIUM_VOICE_LISTEN_ONLY_TURN_COALESCE_WINDOW_MS`
- `VIVENTIUM_VOICE_TURN_COALESCE_WAIT_MS`
- `VIVENTIUM_VOICE_TURN_COALESCE_POLL_MS`
- `VIVENTIUM_VOICE_TURN_COALESCE_RETURN_WINDOW_MS`
- `VIVENTIUM_VOICE_TURN_COALESCE_TTL_S`
- `VIVENTIUM_VOICE_SYNC_TRANSCRIPTION`
- `VIVENTIUM_VOICE_AEC_WARMUP_DURATION_S`
- `VIVENTIUM_VOICE_LOG_LATENCY=1`
- `VIVENTIUM_VOICE_DEBUG_TTS=1`
- `VIVENTIUM_VOICE_LOG_TTS_INPUTS=1`

## Operational Notes
- Use `./viventium-librechat-start.sh` to keep LibreChat + voice gateway secrets aligned.
- Call sessions expire; stale sessions will cause auth failures.
- Live call LLM selection follows the agent primary model by default and only changes when the agent
  has an explicit Voice Chat Model configured.
- Voice transport settings such as STT/TTS provider selection do not change the call LLM route.
- The user-facing hosted provider label is `xAI`; the underlying transport uses standalone xAI TTS
  by default through `livekit-plugins-xai`; the older
  Grok Voice Agent adapter is retained only behind `VIVENTIUM_XAI_TTS_API=voice_agent`.
- Standalone xAI LiveKit calls request `optimize_streaming_latency=1` on the websocket by default
  and can disable it with `VIVENTIUM_XAI_TTS_OPTIMIZE_STREAMING_LATENCY=0`.
- With `VIVENTIUM_VOICE_LOG_LATENCY=1`, inspect `assistant_turn_metrics` for LiveKit
  `llm_node_ttft`, `tts_node_ttfb`, and `e2e_latency`; inspect `tts_provider_metrics` for
  provider-level TTS first-byte/audio-duration timing.
- Recommended Speaking order is Local Chatterbox first when available, then xAI Voice as the
  preferred hosted general-purpose route. As of 2026-05-07, the official xAI TTS pricing page lists
  $4.20 per 1M TTS characters, materially below the effective public Cartesia bundled-character
  cost from Cartesia's pricing page, and local QA found the route fast and high quality. Cartesia
  remains the expressive Sonic-3 route when its emotion/SSML-like controls are specifically needed.
- xAI speech tags are documented in `viventium_v0_4/shared/voice/xai_tts_capabilities.json`.
  They are not SSML and must not be mixed with Cartesia Sonic-3 tags.
- Per-call voice-route overrides recompute the effective turn-taking defaults from the final STT
  provider for that call. A call that overrides from `whisper_local` to `assemblyai` must not keep
  stale VAD-only defaults from the machine route.
- If you previously relied on legacy machine-level `voice.fast_llm_provider`, migrate that choice to
  the agent `Voice Chat Model` fields instead; the machine-level field is ignored for call LLM
  selection.
- Background insights must still be generated in the main system (ensure background agent model/provider config is valid).

## Known Limitations
- Voice insight polling is time-bounded; late insights may require longer timeouts if models are slow.
