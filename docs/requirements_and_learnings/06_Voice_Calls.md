# Voice Calls (LiveKit + Voice Gateway) - Requirements, Specs, and Learnings

## Overview
Voice calls reuse the standard Agents pipeline while streaming audio through the LiveKit voice
gateway. The core requirement is parity with text chat: same agent, same permissions, same
background-cortex behavior.

## Core Requirements
- Call sessions must survive process restarts and multi-instance deployments.
- Voice gateway authentication must rely on a shared secret plus call-session identity.
- Conversation continuity must be preserved.
- Background insights must be surfaced after the main response.
- Voice-mode output must be plain conversational text and strip citation markers before TTS.
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

### Call Session Storage
- Persist call sessions with TTL.
- Session fields should include the call identity, user, agent, conversation, room, and expiry.
- Expired or missing sessions must be rejected honestly.

### Wing Mode
- Wing Mode is a passive companion mode for live voice calls.
- The first-enable disclosure should show the current STT route, TTS route, and effective assistant
  call LLM route for the owning agent.
- The assistant disclosure must show the concrete provider/model and whether that route comes from
  the agent Voice Call LLM or from inheritance of the agent primary LLM.
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
- When a TTS provider does not support native incremental text input, runtime may adapt it to an
  incremental streaming surface, but native continuation/WebSocket APIs are the preferred contract
  for voice-first providers.
- Fallback speech sanitization must be capability-driven and limited to deterministic structural
  parsing of voice-control markup. Do not scatter provider-name heuristics or hardcoded stage-token
  vocabularies across runtime wrapper layers.

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
