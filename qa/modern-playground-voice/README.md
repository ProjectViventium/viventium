# Modern Playground Voice QA

## Purpose

Verify that an authenticated LibreChat agent conversation can launch the Viventium modern playground,
connect a LiveKit call, open the transcript panel, and return a real AI response to a synthetic typed
chat message.

## Acceptance Contract

- An authenticated LibreChat conversation on `http://localhost:3190` shows the phone-button voice
  entrypoint.
- Clicking the phone button opens the modern playground on `http://localhost:3300` with a valid
  call-session deep link.
- Clicking `Start chat` connects the browser to LiveKit and the voice agent.
- Toggling the transcript opens the typed chat input.
- Sending a synthetic typed prompt returns an actual assistant answer, not a generic runtime failure.
- Assistant transcript rows preserve per-answer boundaries. A later assistant answer must not append
  onto the prior row, and async display must not add slow audio-paced spacing unless
  `VIVENTIUM_VOICE_SYNC_TRANSCRIPTION=1` is explicitly enabled for caption QA.
- When background agents activate, the modern playground should hear:
  - the immediate main-agent Phase A response
  - only a later persisted main-agent Phase B follow-up, if one is generated
- Raw background insight text must not appear as direct modern-playground transcript/TTS output.
- LibreChat may still surface the same insight inside its background-insight UI card.
- When the flow fails, the report must separate:
  - browser / transport failures
  - LiveKit / dispatch failures
  - backend model-provider credential failures

## Public-Safe Evidence

- Local-only Playwright browser artifacts:
  - `output/playwright/modern-playground-qa/.playwright-cli/`
  - These artifacts are intentionally not committed because they can include private account UI state.
- Runtime logs:
  - `~/Library/Application Support/Viventium/state/runtime/isolated/logs/voice_gateway.log`
- Stack launcher output from:
  - `bin/viventium start --restart`

## Verification Steps

1. Start the canonical isolated stack with `bin/viventium start --restart`.
2. Open an authenticated LibreChat agent conversation on `http://localhost:3190`.
3. Confirm the `Start voice call` phone button is visible.
4. Click `Start voice call` and verify a new modern-playground tab opens on `http://localhost:3300`.
5. In the modern playground, click `Start chat`.
6. Confirm LiveKit connects and the bottom control bar shows the session as active.
7. Toggle the transcript open.
8. Send a synthetic typed prompt such as `Please reply with exactly: modern playground QA successful.`
9. Record whether the assistant returns a real answer or a generic failure string.
10. If background agents activate, compare the LibreChat assistant turn against the modern
    playground transcript:
    - the playground must not show raw `cortex_insight` text as a separate spoken utterance
    - only a real persisted `cortex_followup` may appear as the second spoken assistant turn
11. If the assistant fails, inspect browser network/console plus runtime logs to locate the failing
    layer before changing code.

## Execution Evidence

### 2026-05-01 Follow-Up NTA Fallback Regression

Observed RCA before the fix:
- Backend follow-up generation already told the main agent to output `{NTA}` when there was no new
  user-visible continuation.
- A later persistence resolver refactor cleared `{NTA}` and then allowed deterministic fallback to
  promote raw background insight text into a persisted `cortex_followup`.
- Voice gateway behavior was then technically correct: it spoke the persisted `cortex_followup`.
  The bad persistence decision happened before the voice gateway poll.

Fix verification:
- Resolver regression:
  - non-replacement `{NTA}` with production-shaped background text stays silent
  - replacement/deferred-primary `{NTA}` still may use governed fallback text
  - voice-mode empty generation stays silent instead of speaking raw insight fallback text
- Automated checks:
  - `cd viventium_v0_4/LibreChat/api && npm run test:ci -- server/services/viventium/__tests__/BackgroundCortexFollowUpService.spec.js --runInBand`
    - Result: `16 passed`
  - `cd viventium_v0_4/LibreChat/api && npm run test:ci -- server/routes/viventium/__tests__/voice.spec.js --runInBand`
    - Result: `7 passed`
  - `cd viventium_v0_4/voice-gateway && .venv/bin/python -m unittest tests.test_worker_followup_scheduler -v`
    - Result: `7 passed`

Acceptance conclusion:
- Normal follow-ups now honor `{NTA}` as terminal.
- Modern playground voice still speaks persisted main-agent follow-ups, but raw background insight
  fallback text is no longer promoted when the main agent chose no follow-up or produced empty voice
  follow-up text.

### 2026-05-04 Async Transcript Boundary + Local Route QA

Observed RCA before the fix:
- LiveKit's built-in React session-message helper merges transcription chunks by segment metadata
  that can repeat across adjacent assistant answers.
- LiveKit's default synchronized transcription path paces transcript display with audio playout,
  which made the UI look slow and exposed spacing artifacts when TTS output was still streaming.

Fix verification:
- The modern playground now reads LiveKit transcription text streams directly and keys assistant
  transcript rows by text-stream id.
- `VIVENTIUM_VOICE_SYNC_TRANSCRIPTION` defaults to false; synchronized captions remain available
  only as an explicit QA/diagnostic opt-in.
- Automated checks:
  - `cd viventium_v0_4/agent-starter-react && pnpm run lint`
    - Result: passed
  - `cd viventium_v0_4/agent-starter-react && pnpm exec tsc --noEmit`
    - Result: passed
  - `cd viventium_v0_4/agent-starter-react && pnpm run build`
    - Result: passed
- Runtime smoke after `bin/viventium launch --modern-playground`:
  - LibreChat frontend returned `200`
  - modern playground returned `200`
  - voice gateway registered successfully

Acceptance conclusion:
- The browser transcript display path no longer appends a later assistant answer onto a prior
  answer row.
- Transcript rendering is decoupled from audio pacing by default, so Lyra/Cartesia and local
  Chatterbox routes use the same UI boundary behavior.

Release delivery note:
- This QA proves the active local checkout.
- For future-user release, publish the `agent-starter-react` component update and bump the parent
  component lock entry; the parent repository alone does not ship gitignored nested component
  changes.

### 2026-04-28 Cartesia Sonic-3 Live Join QA

Observed RCA before the final fix:
- The playground could load while the agent still failed to join because the LiveKit worker marked
  itself unavailable during local model warm-up.
- A second local cold-start path let the worker idle process time out before Whisper finished
  initialization.
- The QA account also lacked parity connected accounts for the selected call model, causing the
  backend to reject real model execution until encrypted OpenAI/Anthropic account records were
  copied from the parity source account.

Fix verification:
- The worker registered after restart and remained available.
- Browser flow:
  - opened an authenticated LibreChat agent conversation on `localhost`
  - clicked `Start voice call`
  - verified the modern playground loaded without `fetch failed`
  - verified Cartesia presented named voices (`Megan`, `Lyra`) rather than Sonic model choices
  - selected `Cartesia / Lyra`
  - clicked `Start chat`
  - observed `Agent is listening`
  - opened transcript and sent a synthetic typed call message
- Runtime route:
  - STT: AssemblyAI Universal Streaming
  - TTS: Cartesia Sonic-3 over WebSocket continuation
  - Voice: Lyra
- Markup evidence:
  - raw LLM/TTS text included an LLM-generated `<emotion value="excited"/>` tag
  - Cartesia request retained the tag and sent matching `generation_config.emotion`
  - debug `display_delta` and final browser transcript showed only clean text
- Browser console:
  - `0` errors
  - only LiveKit local-storage warnings from first-run device-choice state

Acceptance conclusion:
- The reported “agent does not join” path is fixed for the local QA route.
- Cartesia voice calls are Sonic-3-only with named voice selection.
- Streaming is preserved; the voice gateway sends incremental WebSocket continuation requests
  instead of waiting for the full final answer and a downloaded WAV.
- Voice-control tags are generated by the LLM, preserved for Cartesia TTS, and kept out of the
  modern playground user transcript.

### 2026-04-21 Phase B Follow-Up Only Hardening

Observed RCA from the live stack before the fix:
- A real conversation stored a recap sentence only inside a `cortex_insight` content part, not in
  the assistant `text` field and not in a persisted `cortex_followup` child message.
- The corresponding call session still spoke that recap in the modern playground, proving the voice
  gateway was voicing internal insight fallback text rather than only main-agent outputs.

Fix verification:
- Worker-level regression: `voice-gateway/tests/test_worker_followup_scheduler.py`
  - persisted `followUp.text` is spoken
  - insight-only payloads stay silent
  - `{NTA}` follow-ups stay silent
- Full suite:
  - `cd viventium_v0_4/voice-gateway && .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v`
  - Result: `Ran 148 tests ... OK`

Acceptance conclusion:
- Modern playground voice now preserves the intended brain-parity contract:
  - hear the immediate Phase A main response
  - hear a later Phase B continuation only if the main agent actually persisted a follow-up
  - never hear raw subconscious/background insight fallback speech
