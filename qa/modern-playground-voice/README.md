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
10. If the assistant fails, inspect browser network/console plus runtime logs to locate the failing
    layer before changing code.
