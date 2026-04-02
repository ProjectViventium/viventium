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

### Voice Fast-Route Fallback Contract
- The main agent may optionally expose a dedicated voice provider/model, but the shared default must
  remain safe for clean installs.
- If no explicit fast voice provider is configured, runtime should use the main agent provider/model.
- If runtime changes the dedicated voice provider, it must choose a compatible model for that family.

### Call Session Storage
- Persist call sessions with TTL.
- Session fields should include the call identity, user, agent, conversation, room, and expiry.
- Expired or missing sessions must be rejected honestly.

### Wing Mode
- Wing Mode is a passive companion mode for live voice calls.
- The first-enable disclosure should show the current STT route, TTS route, and fast voice LLM route.
- Runtime should use the persisted call-session flag as the source of truth for whether Wing Mode is on.

### Voice Gateway Contract
- `POST /api/viventium/calls` returns the call session id, room name, conversation id, and playground URL.
- `GET /api/viventium/calls/:callSessionId/state` returns the current session state.
- `POST /api/viventium/calls/:callSessionId/state` renews the session TTL and can update Wing Mode.
- Voice gateway requests must carry the shared call-session secret and session identity.

### Live Response Streaming
- Live voice calls should stream the response after the user finishes speaking.
- The gateway should not wait for the full final LLM answer before starting speech.

## Public-Safe Guidance
- Keep browser-visible URLs honest.
- Keep the UI label aligned with the effective provider actually speaking.
- Keep TTS/STT route reporting separate from fallback routing.
- Do not embed personal paths, private machine labels, or secret-store internals into the public doc.
