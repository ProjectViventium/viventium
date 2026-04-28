# Agent and Voice Fallback Model QA - 2026-04-28

## Scope
- Agent Builder exposes a general `Fallback Model` from Model Parameters.
- Agent Builder exposes a separate `Voice Fallback Model` from Voice Chat Model.
- Live voice calls disclose and use the voice fallback route before the general fallback route.
- Provider rate-limit failures fail fast enough for fallback to take over instead of surfacing a generic service outage.

## Root Cause
- The original voice failure path depended only on the primary call LLM. When that provider was rate-limited, the voice gateway surfaced a generic reachability message.
- The first fallback implementation covered text chat but did not give the Voice Chat Model its own user-visible fallback route.
- The initialization path also needed to keep walking fallback candidates when a voice-specific fallback was configured but unavailable before model initialization.

## Fix Summary
- Added persisted fallback fields for both general and voice-specific model routes.
- Added Agent Builder nested panels for both fallback routes, reusing the existing model/provider parameter UI.
- Added runtime fallback preparation and one retry when the primary provider fails before assistant text is produced.
- Added Anthropic fast-fail defaults so provider limits do not wait through long SDK retries before fallback.
- Updated voice error copy so rate limits are described as provider limits, not generic service outages.

## Browser QA
- Signed in with the local QA account.
- Opened Agent Builder for the main Viventium agent.
- Verified Model Parameters shows `Fallback Model` and opens a nested OpenAI `gpt-5.4` route.
- Opened Voice Chat Model.
- Verified Voice Chat Model shows `Fallback Model`, opens `Voice Fallback Model`, and saves OpenAI `gpt-5.4`.
- Verified persisted agent fields:
  - primary route: Anthropic `claude-opus-4-7`
  - general fallback route: OpenAI `gpt-5.4`
  - voice fallback route: OpenAI `gpt-5.4`

## Live QA
- Sent a browser chat message through the main Viventium agent and received a normal assistant response instead of the prior generic service-failure message.
- Started a voice call from the browser UI.
- The modern playground loaded voice settings, removed the prior `fetch failed` state, and showed the Start chat control.
- The call session voice-settings proxy returned an assistant route containing both general and voice-specific fallback routes.
- After Start chat, the browser connected to the local LiveKit room and the voice worker accepted the room job.

## Automated Checks
- `npm run build:api`
- `cd api && npm run test:ci -- --runTestsByPath server/services/viventium/__tests__/agentLlmFallback.spec.js server/services/viventium/__tests__/CallSessionService.spec.js server/routes/viventium/__tests__/calls.spec.js models/Agent.spec.js`
- `cd client && npm run test:ci -- --runTestsByPath src/components/SidePanel/Agents/__tests__/AgentPanel.helpers.spec.ts src/components/SidePanel/Agents/__tests__/AgentSelect.spec.tsx`
- `cd packages/api && npm run test:ci -- --runTestsByPath src/endpoints/anthropic/llm.spec.ts`
- `cd voice-gateway && ./.venv/bin/python tests/test_librechat_llm.py`

## Residual Notes
- Browser automation could verify LiveKit connection and worker dispatch. It did not provide a clean synthetic microphone utterance, so spoken fallback generation remains covered by the voice route and LLM unit tests rather than a full audio transcript assertion.
- The direct backend voice-settings endpoint correctly rejects unauthenticated requests; the playground proxy is the supported browser path.
