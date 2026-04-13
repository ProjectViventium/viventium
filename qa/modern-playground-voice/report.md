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

---

## Date

- 2026-04-04

## Build Under Test

- Repo branch: `codex/remote-modern-playground-access`
- Repo commit: `dcabc27`
- Nested LibreChat branch: `codex/remote-modern-playground-access`
- Nested LibreChat commit: `1fcacfb2`
- Runtime profile: `isolated`

## Scope

- Regression target: when the agent-level `Voice Call LLM` / `voice_llm_provider` +
  `voice_llm_model` are unset, LiveKit voice calls must inherit the agent primary LLM instead of
  leaking to a hidden machine/env xAI route.

## Checks Executed

1. Automated regression checks for the implementation.
   - `python3 -m pytest tests/release/test_config_compiler.py -q`
   - `python3 -m pytest tests/release/test_wizard.py -q`
   - `npm exec jest -- --runInBand server/services/viventium/__tests__/voiceLlmOverride.spec.js test/scripts/viventium-agent-runtime-models.test.js`
   - `cd viventium_v0_4/agent-starter-react && npm run build`
2. Live call-session launch against the local backend.
   - Result: `POST /api/viventium/calls` returned `200` with `requestedVoiceRoute` still null for
     both STT and TTS and a valid modern-playground deep link.
3. Real-browser Playwright pass against the modern playground.
   - Result: the playground loaded, showed the updated assistant-copy contract, and surfaced covered
     local STT/TTS defaults.
4. Worker-authenticated voice-route probe against `POST /api/viventium/voice/chat`.
   - Result: the request reached the real voice route with a live `callSessionId`, synthetic
     `jobId`, and the same headers/body shape the voice gateway uses in production.

## Findings

- Source of truth for `agent_viventium_main_95aeb3` is still:
  - primary provider/model: `anthropic` / `claude-opus-4-6`
  - `voice_llm_provider: null`
  - `voice_llm_model: null`
- The call-session launch response kept the voice route unset:
  - `requestedVoiceRoute.stt.provider = null`
  - `requestedVoiceRoute.tts.provider = null`
- The live voice route reached backend initialization without any voice-override swap log.
  - There was no `[voiceLlmOverride] Swapping model for voice call: ... -> xai/...`
  - There was no `Incorrect API key provided ... console.x.ai` error during the live voice-route
    probe.
- The backend logs for the live voice-route probe showed:
  - `[VIVENTIUM][voice/chat] Request: ... agentId=agent_viventium_main_95aeb3`
  - `[VoiceLatency][LC] stage=initialize_client_validate_primary_done ...`
  - This confirms the request advanced through the real voice-call model-selection path with the
    main agent id while the voice-call fields were still null.
- A separate, unrelated runtime blocker stopped the probe before a full assistant reply completed:
  - `Failed to fetch models from xai API ... 400`
  - `[ResumableAgentController] Initialization error: {"type":"no_user_key"}`
- The xAI 400 observed here is not the original hard-route symptom.
  - It occurs during broader model-config discovery while initializing the agent environment.
  - It did not present as a voice override swap, and it did not produce the previous
    `Incorrect API key provided ... console.x.ai` voice-call failure.

## QA Conclusion

- The original bug is fixed at the product boundary that matters:
  - with Voice Call LLM unset, the live voice-call request no longer gets silently swapped onto the
    hidden xAI override path.
- The remaining failure in this runtime is a separate initialization issue (`no_user_key` plus
  provider/model discovery noise), not evidence that the unset Voice Call LLM still routes to xAI.

## Residual Gaps

- The Playwright browser environment on this machine did not keep a healthy published microphone
  track, so the typed transcript path could not be used as the decisive end-to-end probe.
- The live backend probe reached the correct voice-call route and selection path, but the unrelated
  initialization error prevented a completed assistant response from being streamed back.

## Follow-Ups

- Fix the unrelated runtime initialization blocker causing `{"type":"no_user_key"}` during agent
  startup.
- Investigate the background `Failed to fetch models from xai API ... 400` model-discovery noise
  separately from the voice-call override contract.
- After those are resolved, re-run:
  - `POST /api/viventium/calls`
  - modern-playground `Start chat`
  - worker-authenticated `/api/viventium/voice/chat`
  - transcript reply verification with a short synthetic prompt

---

## Date

- 2026-04-05

## Build Under Test

- Repo branch: `codex/remote-modern-playground-access`
- Repo commit: `dcabc27`
- Nested LibreChat branch: `codex/remote-modern-playground-access`
- Nested LibreChat commit: `1fcacfb2`
- Runtime profile: `isolated`

## Scope

- Follow-up verification for the Voice Call LLM inheritance fix and the remaining cleanup work:
  - Wing Mode disclosure must show the effective assistant call route for the owning agent.
  - With agent `voice_llm_provider` / `voice_llm_model` unset, the disclosure and live backend
    must inherit the agent primary LLM.
  - Legacy machine-level `voice.fast_llm_provider` values must stay ignored.

## Checks Executed

1. Parent release checks.
   - `python3 -m pytest tests/release/test_wizard.py -q`
   - `python3 -m pytest tests/release/test_config_compiler.py -q`
2. LibreChat regression checks in the real API test harness.
   - `cd viventium_v0_4/LibreChat/api && npm run test:ci -- --runInBand server/services/viventium/__tests__/CallSessionService.spec.js server/routes/viventium/__tests__/calls.spec.js server/services/viventium/__tests__/voiceLlmOverride.spec.js test/scripts/viventium-agent-runtime-models.test.js test/scripts/viventium-seed-agents.test.js`
3. Modern playground build validation.
   - `cd viventium_v0_4/agent-starter-react && npm run build`
4. Live backend voice-settings probe against an active call session on the isolated runtime.
   - Result: `GET /api/viventium/calls/:callSessionId/voice-settings` returned
     `assistantRoute.primary = anthropic / claude-opus-4-6`,
     `assistantRoute.voiceCallLlm = null`,
     `assistantRoute.effective = anthropic / claude-opus-4-6`,
     `assistantRoute.inheritsPrimary = true`.
5. Clean modern-playground dev-server QA on `http://localhost:4302` using the same runtime env as
   the isolated stack plus a real live `callSessionId`.
   - Result: the pre-call route loaded successfully, and the Wing Mode disclosure rendered the
     effective assistant route from the live call-session agent.
6. Browser automation with Playwright CLI against the clean dev server.
   - Result: after opening the Wing Mode disclosure, the Assistant row showed:
     `Anthropic • claude-opus-4-6 (agent primary LLM)` with a `Covered` badge.

## Findings

- The product contract is now aligned across backend payloads, browser state, and disclosure copy:
  when Voice Call LLM is unset, the live call session inherits the agent primary LLM.
- The Wing Mode disclosure no longer falls back to a generic sentence for the Assistant route.
  It shows the concrete effective route for the actual owning agent on the live call session.
- The cleanup items from review are also covered:
  - dead legacy env fixtures were removed from the touched Jest baselines
  - the wizard no longer writes the ignored legacy `fast_llm_provider` field
  - docs now include a migration note for older installs that previously relied on
    `voice.fast_llm_provider`
- Browser QA still hit an unrelated microphone-permission denial in Playwright:
  - `Call failed to start`
  - `Permission denied`
  This did not block verification of the Wing Mode disclosure because the control bar and first-time
  Wing Mode modal both rendered after connection setup.

## Independent Runtime Issues Found During QA

- The launcher-managed playground on `http://localhost:3300` was not trustworthy for acceptance on
  this machine during this pass.
  - Direct requests to `/` returned `500`.
  - The rendered error payload showed a stale Next module-loader failure:
    `__webpack_modules__[moduleId] is not a function`.
- A separate production-style one-off server on `http://localhost:4301` exposed another local
  playground runtime issue:
  - `Cannot find module './537.js'`
  - `Cannot find module './774.js'`
- Those two playground runtime failures are independent of the Voice Call LLM inheritance fix.
  The clean dev server on `:4302` and the live LibreChat backend both validated the intended
  contract successfully.

## QA Conclusion

- The Voice Call LLM inheritance bug is fixed and verified with live runtime evidence:
  - backend `voice-settings` resolves the effective assistant route from the real call-session
    agent
  - Wing Mode disclosure shows that same effective route in the browser
  - the unset Voice Call LLM path now displays and uses the agent primary model instead of a hidden
    machine-level route

## Follow-Ups

- Investigate why the launcher-managed modern playground on `:3300` is serving a stale Next module
  failure on this machine.
- Investigate why a fresh `next start` instance on `:4301` cannot resolve generated server chunks
  even after a successful `npm run build`.
- Re-run the same browser QA on the canonical launcher-managed playground once those independent
  runtime issues are repaired, so the acceptance evidence includes the exact shipped local port in
  addition to the clean dev-server proof.

---

## Date

- 2026-04-12

## Build Under Test

- Repo branch: `codex/public-safe-recall-install-20260410`
- Runtime profile: `isolated`

## Scope

- Verify that the Agent Builder Voice Chat Model path is actually honored in the live local
  runtime.
- Make new installs and reviewed syncs preserve the dedicated voice parameter bag instead of
  relying only on inheritance from the primary model parameters.
- Inspect a real local modern-playground voice session for the reported startup delay.

## Checks Executed

1. Live Mongo inspection for the main agent and the relevant call-session records.
2. Runtime log inspection in:
   - `~/Library/Application Support/Viventium/logs/helper-start.log`
   - `~/Library/Application Support/Viventium/logs/native/livekit.log`
3. Targeted LibreChat regression checks:
   - `npm exec jest -- --runInBand models/Agent.spec.js -t "persist dedicated voice parameters"`
   - `npm exec jest -- --runInBand test/scripts/viventium-sync-agents.test.js`
4. Parent release contract check:
   - `/usr/bin/python3 -m pytest tests/release/test_background_agent_governance_contract.py -q`
5. Live reviewed sync:
   - `node scripts/viventium-sync-agents.js push --env=local --model-config-only --agent-ids=agent_viventium_main_95aeb3 --compare-reviewed`
6. Live post-sync verification:
   - direct Mongo read of `agent_viventium_main_95aeb3`
   - direct `resolveVoiceModelParameters()` probe against the persisted live agent
   - fresh `compare --env=local --json`

## Findings

- The live voice route is being picked up correctly in runtime:
  - helper logs show the main agent swapping from `anthropic / claude-opus-4-6` to
    `anthropic / claude-haiku-4-5` during voice-call initialization.
- The install/bootstrap gap was real:
  - source-of-truth had no dedicated persisted `voice_llm_model_parameters` bag for the main
    voice route
  - seed/sync tooling did not preserve that field
  - the compiled `packages/data-schemas/dist` bundle used by the running runtime was stale and did
    not expose `voice_llm_model_parameters` on the live `Agent` schema
- After fixing seed/sync, rebuilding `packages/data-schemas`, and re-running the bounded live
  sync, the local main agent now persists the dedicated voice bag at the top level:
  - `voice_llm_provider = anthropic`
  - `voice_llm_model = claude-haiku-4-5`
  - `voice_llm_model_parameters = { model: "claude-haiku-4-5", thinking: false }`
- Direct runtime resolution against the persisted live agent now returns:
  - `model = claude-haiku-4-5`
  - `thinking = false`
- The inspected slow local voice session was not explained solely by reasoning/thinking:
  - the session reused an existing conversation and loaded prior history
  - startup reconnected multiple MCP surfaces before the call stabilized
  - background-cortex activation still ran during the session startup path
  - in the inspected session, Phase A finished in roughly half a second, so it contributed but was
    not the whole delay

## QA Conclusion

- The Voice Chat Model route and its parameter bag are now wired end to end for the local main
  agent on this machine.
- New installs and reviewed syncs can now preserve the dedicated voice `thinking: false` setting as
  first-class product state instead of depending on indirect inheritance from the main model bag.
- The remaining live-vs-source drift after this fix is limited to the two intentionally preserved
  background-agent `execute_code` tool differences.

## Follow-Ups

- If voice startup still feels slow in day-to-day use, profile and reduce the remaining startup
  overheads separately:
  - conversation-history reuse
  - MCP reconnect churn
  - background-cortex startup policy for voice calls
