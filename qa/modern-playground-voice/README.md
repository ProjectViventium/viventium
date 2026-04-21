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
