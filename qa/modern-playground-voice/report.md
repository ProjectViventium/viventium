# Modern Playground Voice QA Report

## Date

- 2026-04-03

## Build Under Test

- Repo branch: `codex/remote-modern-playground-access`
- Repo commit: `9b36994`
- Nested LibreChat branch: `codex/remote-modern-playground-access`
- Nested LibreChat commit: `307ebfc4`
- Runtime profile: `isolated`

## Checks Executed

1. Auth/session preflight against the active local runtime using an existing local account session.
   - Result: `POST /api/auth/refresh` returned `200` and minted a valid bearer token.
2. Call-session launch preflight against the active local runtime.
   - Result: `POST /api/viventium/calls` returned `200` with `{ callSessionId, roomName, playgroundUrl }`.
3. Real-browser Playwright QA against the canonical local surfaces.
   - LibreChat conversation page: `http://localhost:3190`
   - Modern playground page: `http://localhost:3300`

## Independent QA Pass

### LibreChat Launch Surface

Observed results:

- A clean Playwright-controlled browser accepted the local refresh cookie and loaded the existing
  agent conversation instead of redirecting to `/login`.
- The conversation header showed the `Start voice call` phone button.
- Clicking `Start voice call` opened a second browser tab on the modern playground with a fresh
  call-session deep link.

### Modern Playground Connection

Observed results:

- The modern playground loaded the expected `Start chat` gate for the call-session deep link.
- The pre-call voice route loaded successfully and reflected covered local STT/TTS defaults.
- Clicking `Start chat` connected the browser to LiveKit.
- The connected state showed `Agent is listening, ask it a question`.
- Toggling the transcript opened the typed chat input successfully.

### Typed Transcript Chat

Synthetic prompt used:

- `Please reply with exactly: modern playground QA successful.`

Observed results:

- The prompt was accepted into the transcript timeline.
- The assistant did not return the requested answer.
- The transcript showed:
  - `I'm having trouble reaching the service right now. Please try again.`

## Findings

- The local browser-to-LibreChat-to-modern-playground handoff is working.
- The LiveKit connection path is working.
- The transcript toggle and typed transcript input are working.
- The blocker is in backend generation, not in the browser or LiveKit transport.
- Runtime evidence from the launcher session captured the failing layer:
  - `[api/server/controllers/agents/client.js #sendCompletion] Operation aborted 403 "API key is currently blocked: Blocked due to API key leak"`
  - `[api/server/controllers/agents/client.js #sendCompletion] Unhandled error type 403 "API key is currently blocked: Blocked due to API key leak"`
- Separate runtime evidence also showed an OpenAI credential problem in the recall/embedding path:
  - `File embedding failed ... 401 ... incorrect API key provided`
- Review-only second opinion from the local Claude CLI agreed that:
  - the modern playground path itself is healthy
  - the response failure is caused by backend provider credentials
  - the `403` blocked key and the `401` embedding key are separate issues

## Regressions

- No browser or LiveKit regression was found in the tested launch path.
- The current runtime cannot complete an end-to-end AI response from the modern playground because
  the active model-provider credential used by the main agent path is blocked.

## Follow-Ups

- Rotate the blocked provider key used by the main agent completion path and verify the isolated
  runtime reloads the new value.
- Verify the OpenAI key used by embeddings / conversation recall separately, since it is failing
  with a different `401 invalid_api_key` error.
- Re-run this exact QA flow after the runtime credentials are repaired.
- Do not treat remote/public playground access as verified until the same synthetic transcript test
  returns a real assistant answer on a healthy local runtime first.
