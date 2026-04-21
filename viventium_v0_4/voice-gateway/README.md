<!-- === VIVENTIUM START ===
Document: Voice Gateway README
Updated: 2026-01-10
=== VIVENTIUM END === -->

## Viventium Voice Gateway (LiveKit Agent Worker)

This service is the **voice bridge** between:

- **LiveKit room** (audio call via Agents Playground)
- **LibreChat** agent pipeline (Main Agent + Background Cortices)

### How it works

1. LibreChat creates a short-lived `callSessionId` via `POST /api/viventium/calls`.
2. LibreChat opens Agents Playground with:
   - `roomName`
   - `callSessionId`
   - `agentName` (defaults to `librechat-voice-gateway`)
3. Agents Playground calls its `/api/token` route which:
   - mints a participant token
   - creates an **explicit agent dispatch** for `agentName` with dispatch `metadata` containing `{"callSessionId": "..."}`.
4. This worker is registered under `LIVEKIT_AGENT_NAME` and receives the dispatch job.
5. The worker extracts `callSessionId` from `ctx.job.metadata`, then:
   - STT → produces text
   - calls LibreChat `POST /api/viventium/voice/chat` (authenticated by `callSessionId` + shared secret)
   - streams response from `GET /api/viventium/voice/stream/:streamId`
   - TTS → speaks the response

### Required environment variables

- **LiveKit**
  - `LIVEKIT_URL`
  - `LIVEKIT_API_KEY`
  - `LIVEKIT_API_SECRET`
  - `LIVEKIT_AGENT_NAME` (defaults to `librechat-voice-gateway`)

- **LibreChat**
  - `VIVENTIUM_LIBRECHAT_ORIGIN` (e.g. `http://localhost:3180`)
  - `VIVENTIUM_CALL_SESSION_SECRET` (must match LibreChat)

- **STT provider (optional)**
  - `VIVENTIUM_VOICE_STT_PROVIDER` (overrides voice only)
  - `VIVENTIUM_STT_PROVIDER` (fallback)
  - `STT_PROVIDER` (legacy fallback; v1 parity)
  - Allowed: `whisper_local` / `pywhispercpp`, `assemblyai`, `openai`
  - `whisper_local` uses local whisper.cpp + Silero VAD via StreamAdapter.
  - `assemblyai` requires `ASSEMBLYAI_API_KEY`.
  - `openai` uses `VIVENTIUM_OPENAI_STT_MODEL` and is wrapped with VAD when available.

- **TTS provider (optional)**
  - `VIVENTIUM_TTS_PROVIDER`
    - Allowed: `elevenlabs` (default if plugin installed), `openai`, `xai`, `cartesia`
  - `VIVENTIUM_TTS_PROVIDER_FALLBACK`
    - Optional fallback provider used when the primary provider errors at runtime.
    - Allowed: `elevenlabs`, `openai`, `xai`, `cartesia`
    - Set to `none|off|false|0` to disable.
    - Default behavior: when primary is `cartesia` and fallback is unset, fallback defaults to `elevenlabs`
      (or `openai` if ElevenLabs plugin is unavailable).
    - Fallback routing is streaming-aware. Native streaming providers stay native-streaming; non-native
      providers are adapted only when necessary instead of downgrading the whole turn.
  - **Cartesia Sonic-3**
    - Requires: `CARTESIA_API_KEY`
    - Optional knobs:
      - `VIVENTIUM_CARTESIA_API_URL` (default `https://api.cartesia.ai/tts/bytes`)
      - `VIVENTIUM_CARTESIA_WS_URL` (default `wss://api.cartesia.ai/tts/websocket`)
      - `VIVENTIUM_CARTESIA_API_VERSION` (default `2025-04-16`)
      - `VIVENTIUM_CARTESIA_MODEL_ID` (default `sonic-3`)
      - `VIVENTIUM_CARTESIA_VOICE_ID` (default `e8e5fffb-252c-436d-b842-8879b84445b6`)
      - `VIVENTIUM_CARTESIA_SAMPLE_RATE` (default `44100`)
      - `VIVENTIUM_CARTESIA_SPEED` (default `1.0`)
      - `VIVENTIUM_CARTESIA_VOLUME` (default `1.0`)
      - `VIVENTIUM_CARTESIA_EMOTION` (default `neutral`)
      - `VIVENTIUM_CARTESIA_MAX_BUFFER_DELAY_MS` (default `120` for live voice streaming)
      - `VIVENTIUM_CARTESIA_SEGMENT_SILENCE_MS` (default `80`)
        - Silence inserted between `<emotion>` segments (used when multiple emotions appear in one response).
    - Live voice calls use Cartesia WebSocket contexts so TTS can start from incremental LLM deltas.
      `/tts/bytes` remains the full-text path for one-request surfaces.
    - Nonverbal markers (Cartesia-specific parsing):
      - Supported tokens: `[laughter]`, `[sigh]`, `[gasp]`, `[breath]`, `[hmm]`
      - Tokens are split into their own mini-synthesis requests to maximize audibility.
  - **xAI Grok Voice ("Voice Agent API")**
    - Requires: `XAI_API_KEY`
    - Optional knobs:
      - `VIVENTIUM_XAI_VOICE` (default `Eve`; choices in xAI docs include `Ara`, `Rex`, `Sal`, `Eve`, `Leo`)
      - `VIVENTIUM_XAI_WSS_URL` (default `wss://api.x.ai/v1/realtime`)
      - `VIVENTIUM_XAI_SAMPLE_RATE` (default `24000`)
      - `VIVENTIUM_XAI_INSTRUCTIONS` (optional strict prompt override)
    - Docs: `https://docs.x.ai/docs/guides/voice/agent`

- **Turn detection (optional)**
  - `VIVENTIUM_TURN_DETECTION`
    - Allowed: `stt`, `vad`, `realtime_llm`, `manual`
    - Shipped default depends on the active STT route:
      - `assemblyai` defaults to `stt`
      - local `whisper_local` / `pywhispercpp` defaults to `vad`
    - If `vad` is requested while Silero is unavailable, runtime falls back to `stt`.
  - Silero VAD requires Python <= 3.12 and `livekit-plugins-silero`.
  - `VIVENTIUM_STT_VAD_MAX_BUFFERED_SPEECH` (defaults to `600`)
    - Maximum duration of one uninterrupted speech segment kept in the Silero buffer.
    - Applies to `whisper_local` and to `openai` when wrapped with StreamAdapter + VAD.
    - If a caller speaks continuously past this limit without pausing, underlying Silero will drop the overflow audio.

- **Subconscious (background cortex) insight surfacing (optional)**
  - `VIVENTIUM_VOICE_FOLLOWUP_TIMEOUT_S` (defaults to `60.0`)
    - How long the worker will poll in the background for completed insights/follow-up text.
  - `VIVENTIUM_VOICE_FOLLOWUP_INTERVAL_S` (defaults to `1.0`)
    - Poll interval while waiting for cortex insights to be persisted to the DB.
  - `VIVENTIUM_VOICE_FOLLOWUP_GRACE_S` (defaults to `30.0`)
    - Background follow-up window after the DB poller first discovers persisted insights. This gives the backend follow-up LLM time to persist a true Phase B main-agent continuation. Grace timer starts from the first DB poll with insights, not from SSE-captured insights.
  - Follow-ups are delivered asynchronously and never block the main response.
  - Raw background insights stay silent in live voice if no persisted follow-up arrives inside the window.

- **Voice stream resilience (optional)**
  - `VIVENTIUM_VOICE_SSE_MAX_RETRIES` (defaults to `2`)
    - How many times to retry the LibreChat SSE stream if the connection drops.
  - `VIVENTIUM_VOICE_SSE_RETRY_DELAY_S` (defaults to `0.5`)
    - Delay between SSE retry attempts.
  - `VIVENTIUM_VOICE_STREAM_ERROR_MESSAGE`
    - Spoken fallback when the LibreChat stream fails (general).
  - `VIVENTIUM_VOICE_TOOL_ERROR_MESSAGE`
    - Spoken fallback when the stream error looks tool-related (e.g., MCP disconnects).

- **Voice-mode prompt injection (LibreChat)**
  - `VIVENTIUM_VOICE_MODE_PROMPT`
    - Optional override string for voice-mode system instructions.
  - `VIVENTIUM_VOICE_CORTEX_DETECT_TIMEOUT_MS`
    - Override cortex activation detection timeout for voice mode. Set to `0` to skip detection.

- **Latency logging (optional)**
  - `VIVENTIUM_VOICE_LOG_LATENCY=1`
    - Enables voice latency logs in both the Voice Gateway and LibreChat voice routes.
  - `VIVENTIUM_VOICE_DEBUG_TTS=1`
    - Logs Cartesia text normalization, emotion segments, and truncations.

### Run

From repo root:

```bash
python viventium_v0_4/voice-gateway/worker.py start
```
