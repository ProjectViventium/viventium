# Listen-Only Mode QA Report

Date: 2026-05-06

## Result

Pass for the current implementation and QA pass.

## 2026-05-06 Continuity Regression

Result: pass.

### RCA

- Normal voice drift was not caused by Listen-Only itself. Recent live DB rows showed normal voice
  turns saved as provider-backed conversations with endpoint values such as `xai`, two messages per
  conversation, and `NO_PARENT` roots.
- The voice resolver correctly rejected non-`agents` conversations, but provider-backed ephemeral
  agent conversations can still carry the same structured `agent_id` as the active call session.
  Because the call session kept pointing at the rejected conversation, each next turn resolved to
  `new` again and created another conversation.
- The fix keeps the endpoint invariant for unrelated surfaces, but voice may now reuse a
  provider-backed conversation only when its stored `agent_id` exactly matches the call-session
  `agentId`.
- A related Listen-Only stale-session path was closed: if a stored call-session conversation id was
  rejected, Listen-Only now claims/replaces a fresh concrete conversation id instead of falling back
  to the stale provider conversation.
- If Listen-Only cannot claim a fresh concrete conversation id from the live call session, it now
  fails closed and does not write orphan transcript rows.
- The playground transcript dedupe now covers same local transcript text arriving through different
  stream ids without collapsing different speakers or later repeated phrases.
- A background-cortex crash path was closed by snapshotting request, response, agent, and message
  ids before async Phase A/B work can outlive LibreChat client cleanup.

### Added Regression Coverage

```bash
cd viventium_v0_4/LibreChat/api
npm test -- --runInBand \
  server/routes/viventium/__tests__/voice.spec.js \
  server/services/viventium/__tests__/conversationThreading.spec.js \
  server/services/viventium/__tests__/CallSessionService.spec.js \
  server/services/viventium/__tests__/conversationRecallFilters.spec.js

cd ../../agent-starter-react
pnpm exec tsc --noEmit

cd ../..
node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON --experimental-strip-types \
  qa/listen-only-mode/session-message-utils.test.mjs
```

Observed:

- Voice route, conversation-threading, call-session, and recall-filter suites: 52 passed.
- Modern playground TypeScript: passed.
- Session message utility QA: passed.
- Modern playground Prettier check on touched files: passed.
- LibreChat backend formatting was not used as a gate for `client.js`/`voice.js` because those
  upstream-shaped files are not currently clean under whole-file Prettier; the fix keeps their diffs
  surgical to avoid unrelated formatting churn.

### Live Runtime Evidence

Live runtime QA used synthetic QA-account data only.

1. Provider-backed voice conversation with matching `agent_id`:
   - `/api/viventium/voice/chat` returned `status=listen_only`.
   - The response had no `streamId`.
   - The saved transcript reused the existing provider-backed conversation and parented to the
     latest prior assistant row.
   - The saved row had `sender="Listen-Only"`, `isCreatedByUser=false`, `tokenCount=0`,
     `_meiliIndex=false`, and `metadata.viventium.mode="listen_only"`.
2. Stale provider-backed conversation with a different `agent_id`:
   - `/api/viventium/voice/chat` returned `status=listen_only`.
   - The response had no `streamId`.
   - The call session was updated to a fresh conversation id.
   - The transcript was saved under that fresh id, not the rejected provider conversation.
3. Browser control QA with fake media:
   - Start chat connected without the previous `could not establish pc connection` failure.
   - The Listen-Only button was visible, icon-sized, and 36px by 36px in the active control bar.
   - Tooltip copy used human presence wording and included the operational boundaries: no answer,
     speech, tools, or live memory update.
   - Toggling Listen-Only changed the control state and showed the quiet presence message.
4. Post-QA health:
   - LibreChat API, modern playground, and LibreChat frontend returned HTTP 200.
   - No recurrence of the voice async `client.options.req` crash was found after the live QA pass.

### Final Review Closure

- Review-only Claude validated the main design and asked for added guarantees around the exact
  two-turn fork symptom, transient lookup errors, and unclaimed Listen-Only writes.
- Added coverage now proves:
  - the first stale voice turn updates the call session to the generated conversation id;
  - the next voice turn reuses that generated id instead of starting another conversation;
  - transient conversation lookup errors do not replace the call-session conversation id;
  - Listen-Only fails closed when a fresh session conversation cannot be claimed.

## Root Cause Corrections

- Duplicate transcript bubbles came from rendering LiveKit transcription updates more than once.
  The playground now uses LiveKit's session-message path once and applies defensive dedupe for same
  message ids and same transcription segment ids.
- Conversation history branches came from saving each Listen-Only row under the same live/root
  parent. Listen-Only persistence now resolves the transcript tail and writes a linear ambient lane.
- Old root/fanout transcript tails are repaired before the next Listen-Only save.
- Completed Listen-Only coalescing used to return the old saved payload for later same-key turns.
  It now only suppresses duplicates inside the short return window when the incoming text is already
  captured by the saved text; later or different turns save new rows.
- New Listen-Only sessions now atomically claim the concrete call-session conversation id before
  transcript save, preventing concurrent first-turn splits.
- Listen-Only rows opt out of Meili indexing, conversation recall excludes them before the raw
  message-limit window, source-only conversation recall fallback excludes them by metadata, and
  Meili cleanup removes legacy indexed Listen-Only rows.
- Memory hardening now counts distinct ambient sources, not adjacent rows from one call session,
  before stable-memory writes.
- Mobile browser QA caught tooltip overflow at 375px and 320px. The tooltip now uses fixed mobile
  positioning and passed the same viewport assertions.

## Browser Evidence

Real browser QA used synthetic network responses, a synthetic local WebSocket hold server, and a
synthetic call session. No private call audio, private transcript, account id, call-session id, or
secret was recorded.

Checked at 1440px, 375px, and 320px:

1. Listen-Only control is active from persisted call-session state.
2. Tooltip uses human presence copy: Viventium can be here without interrupting.
3. Tooltip states the operational boundaries: no answer, speech, tools, or live memory update.
4. Tooltip contains no evidence/surveillance/forensic wording.
5. Tooltip and button fit inside the viewport with no horizontal page overflow.
6. Tooltip is attached with `aria-describedby`.
7. Typed chat input is hidden while Listen-Only is active.

## Automated Evidence

```bash
cd viventium_v0_4/LibreChat/api
npm test -- --runInBand \
  server/routes/viventium/__tests__/voice.spec.js \
  app/clients/tools/util/fileSearch.test.js \
  server/services/viventium/__tests__/conversationRecallFilters.spec.js \
  server/services/viventium/__tests__/conversationThreading.spec.js \
  app/clients/specs/BaseClient.test.js \
  server/services/viventium/__tests__/conversationRecallService.spec.js

cd viventium_v0_4/agent-starter-react
npm run lint && npm run build

cd viventium_v0_4/LibreChat/packages/data-schemas
npx jest --runInBand src/models/plugins/mongoMeili.spec.ts
npm run build

cd ../../../..
node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON --experimental-strip-types \
  qa/listen-only-mode/session-message-utils.test.mjs
node qa/listen-only-mode/memory-hardening-gate.test.cjs

uv run --with pytest --with pyyaml python -m pytest \
  tests/release/test_memory_hardening_contract.py -q

cd viventium_v0_4/voice-gateway
.venv/bin/python -m pytest tests -q
```

Observed:

- LibreChat Listen-Only/recall/threading suite: 136 passed.
- Data-schemas Meili plugin suite: 45 passed.
- Frontend lint: passed.
- Frontend production build: passed.
- Data-schemas build: passed.
- Session message utility QA: passed.
- Listen-Only memory gate QA: passed.
- Memory hardening release contract: 13 passed.
- Voice gateway suite: 205 passed, with one existing `audioop` deprecation warning.

## Second Opinion

Review-only Claude and ClaudeViv passes were run after the primary RCA. They confirmed the main
fix and identified two concrete gaps: corpus-query starvation by Listen-Only rows and stale cached
payloads for different parentless ambient turns inside the duplicate-return window. Both gaps were
fixed, covered by the 136-test LibreChat suite above, and documented here. A targeted follow-up
review found no code-level blockers; remaining notes were release-gate and hardening items.

## Residual Risk

- Same-microphone audio is still not true diarization. Speaker separation remains limited to
  structured LiveKit participant or track identity.
- Release readiness still requires nested component commits and parent component pins to be updated;
  source-level QA alone does not ship nested repo changes.
