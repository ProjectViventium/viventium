# Voice Calls (LiveKit + Voice Gateway) - Requirements, Specs, and Learnings

## Overview
Voice calls reuse the standard Agents pipeline while streaming audio through the LiveKit voice
gateway. The core requirement is parity with text chat: same agent, same permissions, same
background-cortex behavior.

## Core Requirements
- Call sessions must survive process restarts and multi-instance deployments.
- Voice gateway authentication must rely on a shared secret plus call-session identity.
- Conversation continuity must be preserved.
- Premature endpointing must not fork one spoken sentence into multiple sibling user turns.
- Turn-taking must balance two failure modes across short and long speech:
  - do not interrupt the user mid-thought because a short reflective pause looked like end-of-turn
  - do not wait so long after a true stop that the system feels sluggish or unresponsive
- Background insights must be surfaced after the main response without leaking raw internal insight
  text into live voice speech.
- The shipped background follow-up window should stay in parity across LibreChat, live voice, and
  Telegram unless a future doc explicitly splits those defaults.
- Voice-mode output must be plain conversational text and strip citation markers before TTS.
- Provider-bound Anthropic histories must drop malformed thinking blocks before execution.
- Voice input mode must be propagated to main agents and background cortices.
- A connected call must not die just because the user is quiet for a long time.
- Wing Mode must be a simple opt-in voice behavior, not a separate hardcoded agent path.
- Only one LiveKit worker may speak for a call session at a time.

## Public-Safe Specifications

### Voice Call LLM Ownership Contract
- The main agent provider/model is the default LLM for live voice calls.
- The agent may optionally expose a dedicated Voice Call LLM via explicit `voice_llm_provider` and
  `voice_llm_model` fields.
- If the Voice Call LLM is unset, runtime must use the agent's primary provider/model exactly as
  selected in Agent Builder.
- Machine-level voice transport settings such as STT/TTS configuration must not silently rewrite the
  call LLM route.
- Legacy machine-level config fields such as `voice.fast_llm_provider` /
  `VIVENTIUM_VOICE_FAST_LLM_PROVIDER` must not override the agent-visible Voice Call LLM contract.
- If an explicit Voice Call LLM is invalid or lacks a required server credential, runtime should log
  the skip and fall back to the agent primary model/provider.

### Agent Fallback LLM Contract
- Agent Builder must expose a user-visible `Fallback Model` route from the Model Parameters page.
  It uses explicit `fallback_llm_provider`, `fallback_llm_model`, and
  `fallback_llm_model_parameters` fields.
- Agent Builder must also expose a fallback route inside the Voice Chat Model page. It uses
  explicit `voice_fallback_llm_provider`, `voice_fallback_llm_model`, and
  `voice_fallback_llm_model_parameters` fields so voice calls can recover independently of the
  text-chat fallback route.
- The fallback route is a secondary provider/model for recoverable primary-route failures before
  any assistant text is produced, including provider rate limits, credential failures, and temporary
  provider outages.
- For live voice calls, runtime chooses fallback candidates in this order:
  1. the voice-specific fallback route, when configured
  2. the general agent fallback route, when the voice-specific route is unset or unavailable before
     model initialization
- Runtime may retry once with the configured fallback route. It must not silently remap to hidden
  machine defaults or infer a fallback from a user identity, provider label, or prompt text.
- The fallback route must support connected-account auth with the same precedence as the primary
  agent route: user connected account first, then server env key where the endpoint supports it.
- If no fallback route is configured or the fallback route is invalid, voice must surface an honest
  provider-specific failure. A provider rate limit must not be voiced as a generic service outage.
- If primary output has already produced substantive assistant text, runtime must not switch models
  mid-answer; that would create an incoherent mixed-provider response.

### Call Session Storage
- Persist call sessions with TTL.
- Session fields should include the call identity, user, agent, conversation, room, and expiry.
- Expired or missing sessions must be rejected honestly.

### Wing Mode
- Wing Mode is a passive companion mode for live voice calls.
- A live call must not be treated as blanket permission to answer every overheard utterance.
  Bare spoken questions or comments in the room default to silence unless they are clearly addressed
  to the assistant or obviously require the assistant's memory, tools, or role in the call.
- Even when the user is talking to the assistant, Wing Mode should default to `{NTA}` unless the
  assistant has a clear, useful, additive contribution to make.
- The first-enable disclosure should show the current STT route, TTS route, and effective assistant
  call LLM route for the owning agent.
- The assistant disclosure must show the concrete provider/model and whether that route comes from
  the agent Voice Call LLM or from inheritance of the agent primary LLM.
- When configured, the assistant disclosure may also show the fallback provider/model separately
  from the effective call LLM so users understand resilience without confusing it with STT/TTS
  route selection.
- Runtime should use the persisted call-session flag as the source of truth for whether Wing Mode is on.

### Voice Gateway Contract
- `POST /api/viventium/calls` returns the call session id, room name, conversation id, and playground URL.
- `GET /api/viventium/calls/:callSessionId/state` returns the current session state.
- `POST /api/viventium/calls/:callSessionId/state` renews the session TTL and can update Wing Mode.
- Voice gateway requests must carry the shared call-session secret and session identity.
- Agent dispatch metadata for modern-playground calls must be hydrated from the authoritative
  call-session voice settings server-side before dispatch creation; do not rely on the browser's
  async voice-settings fetch completing first.

### Live Response Streaming
- Live voice calls should stream the response after the user finishes speaking.
- The gateway should not wait for the full final LLM answer before starting speech.
- Native provider streaming must be preserved end to end. Fallback wrappers or route-selection
  layers must not downgrade a provider that supports incremental speech continuations back to a
  non-streaming sentence-buffered path.
- Rapid same-parent voice ingress requests must coalesce onto one launched stream in ingress order
  when they land inside the configured turn-coalescing window.
- Voice persistence may keep provider markup in the live synthesis path, but the canonical saved
  assistant text/content used for history and reloads must not retain raw voice-control tags.
- When Cartesia is the call-mode TTS provider, the model-facing voice prompt may instruct the LLM
  to emit Sonic-3 SSML-like tags. Runtime must not invent emotion tags from heuristics; it may only
  preserve, segment, sanitize-for-display, and route LLM-selected provider markup.
- Cartesia live calls must use the WebSocket continuation path for incremental LLM deltas. The
  `/tts/bytes` WAV endpoint is reserved for full-text one-request surfaces and must not become the
  default live-call path.
- The Cartesia public request contract is Sonic-3-only: `Cartesia-Version=2026-03-01`
  and `model_id=sonic-3`. Voice selection is by named persona in the UI, backed by Cartesia
  voice IDs: Megan (`e8e5fffb-252c-436d-b842-8879b84445b6`) and Lyra
  (`6ccbfb76-1fc6-48f7-b71d-91ac6298247b`).
- Cartesia emotion handling must pass both surfaces when the LLM selected an emotion tag:
  the `<emotion value="..."/>` prefix remains in the transcript sent to Cartesia, and the same value
  is sent as `generation_config.emotion`.
- Modern playground transcript display must use a stateful structural filter for provider markup.
  Incomplete streaming fragments such as `<em` or `[laugh` must be buffered until they can be
  classified, then stripped from user-visible text while the original LLM text continues to feed
  Cartesia TTS.
- Debug logging for voice markup must be opt-in and non-secret-bearing. With
  `VIVENTIUM_VOICE_DEBUG_TTS=1`, logs should show LLM raw text, TTS text, display-sanitized text,
  and Cartesia request transcripts without API keys.
- When a TTS provider does not support native incremental text input, runtime may adapt it to an
  incremental streaming surface, but native continuation/WebSocket APIs are the preferred contract
  for voice-first providers.
- Fallback speech sanitization must be capability-driven and limited to deterministic structural
  parsing of voice-control markup. Do not scatter provider-name heuristics or hardcoded stage-token
  vocabularies across runtime wrapper layers.
- In live voice, only the main agent's user-facing outputs may be spoken:
  - the immediate Phase A main response
  - a persisted Phase B `cortex_followup` main-agent continuation, when one exists
- Raw `cortex_insight` content is background cognition. It may be shown in LibreChat's
  background-insight UI, but it must not be spoken directly into the modern playground transcript
  or TTS path as a fallback.

### Turn-Taking Ownership Contract
- AssemblyAI-backed voice calls must default to provider endpointing (`turn_detection=stt`) instead
  of pure VAD-only turn ending.
- Silero VAD remains attached even when STT endpointing owns turn completion so the runtime keeps
  responsive interruption handling.
- Viventium must not silently stack a second large endpointing delay on top of provider endpointing.
  When AssemblyAI STT endpointing is active, the local `AgentSession` endpointing delay should stay
  near-zero/small and act only as a guardrail.
- Semantic turn detection is a higher-capability option, but it is an explicit config/runtime choice,
  not the default fallback for every AssemblyAI install.
- When the semantic turn-detector plugin is installed, launcher/runtime checks must verify the exact
  required cached assets, not just the presence of a generic Hugging Face cache directory.
- The turn-detector plugin must load lazily. Installing the package alone must not make an unrelated
  local `vad` route boot with inference-runner initialization errors for an unused detector path.
- Local whisper.cpp (`whisper_local` / `pywhispercpp`) remains a StreamAdapter + Silero VAD path:
  - it inherits shared interruption handling and saved-route plumbing
  - it does not gain AssemblyAI-native endpointing knobs or semantic turn-detector behavior
- Optional voice-gateway plugins must never crash worker boot at module import time:
  - plugin availability checks must treat a missing parent package the same as a missing leaf module
  - semantic turn detection may downgrade at runtime, but the LiveKit worker must still register
    for `stt` and `vad` routes
- Voice-gateway dependency installation must compare installed package versions against
  `voice-gateway/requirements.txt`, not just test package presence. An already-created venv with
  older LiveKit packages must be refreshed during startup/upgrade instead of silently reusing stale
  packages.
- Turn-ending behavior must be config-owned and observable:
  - LiveKit interruption knobs compile from canonical config
  - AssemblyAI endpointing knobs compile from canonical config
    - when unset, the shipped compiler now emits the documented Universal Streaming baseline rather
      than relying on implicit plugin/API defaults
  - the background follow-up window compiles from canonical config
  - worker/runtime capacity knobs compile from canonical config:
    - `VIVENTIUM_VOICE_INITIALIZE_PROCESS_TIMEOUT_S`
    - `VIVENTIUM_VOICE_IDLE_PROCESSES`
    - `VIVENTIUM_VOICE_WORKER_LOAD_THRESHOLD`
    - `VIVENTIUM_VOICE_JOB_MEMORY_WARN_MB`
    - `VIVENTIUM_VOICE_JOB_MEMORY_LIMIT_MB`
    - `VIVENTIUM_VOICE_PREWARM_LOCAL_TTS`
  - local Whisper routes default to an unlimited LiveKit worker load threshold because CPU load is
    expected during model warm-up and must not make the worker disappear from dispatch
  - local Whisper routes default to a longer initialization timeout so cold-start model loading does
    not kill the idle process before the worker can accept calls
  - runtime logs must state why a user turn completed, using normalized reason labels such as
    `vad_silence`, `stt_end_of_turn`, or `semantic_turn_detector`
- Per-call requested voice-route overrides must recompute the effective turn-taking defaults from the
  final STT provider for that call. Do not keep VAD/STT defaults derived from the machine default
  provider when a call overrides onto a different STT route.
- For AssemblyAI `stt`, the shipped default should follow current LiveKit guidance:
  - keep local `min_endpointing_delay` near zero
  - let AssemblyAI own endpointing timing with explicit provider knobs
  - prefer explicit compiler-emitted defaults over leaving the plugin/API path ambiguous
- The same ownership contract must work for both short exchanges and long continuous speech; fixes
  must widen the structural runtime contract, not hardcode one reproduced sentence shape.

### Remote Browser Voice Contract
- Enabling remote access must not break the canonical localhost voice path.
- The modern playground must choose the LiveKit URL by browser origin:
  - localhost callers keep `ws://localhost:7888`
  - configured public playground origins receive the configured public LiveKit WSS URL
- The launcher-managed modern playground must keep its live `next dev` output isolated from normal
  build output so local validation work does not corrupt the active browser voice surface into
  `500 Internal Server Error`.
- When the modern playground is served through configured public browser origins in development,
  those origins must be explicitly allowed as Next dev origins instead of relying on implicit
  cross-origin tolerance.
- Public-browser access also needs the non-HTTP media path:
  - direct LiveKit TCP/UDP media where available
  - TURN/TLS fallback when the public HTTPS edge is active
- The stable public answer for arbitrary browsers is the public HTTPS edge with explicit custom
  domains; private mesh modes remain separate operator-owned access modes for enrolled devices.

## Public-Safe Guidance
- Keep browser-visible URLs honest.
- Keep the UI label aligned with the effective provider actually speaking.
- Keep TTS/STT route reporting separate from fallback routing.
- Do not embed personal paths, private machine labels, or secret-store internals into the public doc.
