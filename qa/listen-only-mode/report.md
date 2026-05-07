# Listen-Only Mode QA Report

Date: 2026-05-05

## Result

Pass for the current implementation and QA pass.

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
