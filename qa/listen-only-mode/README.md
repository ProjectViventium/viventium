# Listen-Only Mode QA

## Scope

Validates the LiveKit Listen-Only Mode path:

- modern playground control-bar button and tooltip
- persisted call-session state
- mutual exclusion with Wing Mode
- voice-route bypass before `AgentController`
- ambient transcript persistence with `listen_only_transcript` metadata
- exclusion from normal conversation recall corpus
- exclusion from live agent prompt history after Listen-Only is turned off
- daily memory-hardener treatment as soft `ambient_transcript` evidence

## Acceptance Criteria

1. The control bar shows an icon-sized Listen-Only button that matches the current LiveKit control
   style and has a tooltip explaining what is saved and what does not run. User-facing copy must
   avoid forensic or surveillance language and present Viventium as present, quiet, and
   remembering later.
2. Enabling Listen-Only clears Wing Mode; enabling Wing Mode clears Listen-Only.
3. While Listen-Only is active, typed chat input is hidden and voice turns return
   `status=listen_only` with no `streamId`.
4. No live assistant answer, TTS, tools, background cortex follow-up, title-generation LLM, or live
   LibreChat Memory Agent path runs for Listen-Only turns.
5. Transcript entries are saved with `isCreatedByUser=false`, `sender="Listen-Only"`,
   `tokenCount=0`, and `metadata.viventium.type="listen_only_transcript"`.
6. Normal conversation recall skips Listen-Only transcript entries.
7. Live agent history skips Listen-Only transcript entries, so resuming normal mode does not send
   ambient transcripts as prior assistant context.
8. The memory hardener sees Listen-Only entries as `ambient_transcript` soft evidence and applies
   transcript corroboration gates before stable-memory writes. Stable-memory corroboration counts
   distinct ambient sources, not adjacent rows from the same call session.
9. Same-microphone audio is not claimed as true diarization; speaker labels depend on structured
   LiveKit participant or track identity.
10. Each final LiveKit transcript stream is rendered once in the transcript panel; the same utterance
    must not appear as duplicate bubbles when LiveKit sends updates for the same transcription
    segment across more than one text-stream id.
11. Consecutive Listen-Only transcript entries in a conversation are saved as a linear transcript
    lane. They must not create one LibreChat sibling branch per utterance.
12. Listen-Only rows are not Meili-indexed and cannot surface through source-only conversation
    recall fallback.

## Automated Evidence

Run from the public repo root:

```bash
cd viventium_v0_4/LibreChat/api
npm test -- --runInBand \
  server/services/viventium/__tests__/CallSessionService.spec.js \
  server/routes/viventium/__tests__/calls.spec.js \
  server/routes/viventium/__tests__/voice.spec.js \
  server/services/viventium/__tests__/conversationRecallFilters.spec.js \
  server/services/viventium/__tests__/conversationRecallService.spec.js \
  server/services/viventium/__tests__/conversationThreading.spec.js \
  app/clients/specs/BaseClient.test.js

cd ../../agent-starter-react
npm run lint
npm run build

cd ../..
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

## Browser QA

1. Start the local stack with a QA account, not the owner account.
2. Open a call session in the modern LiveKit playground.
3. Hover the Listen-Only button and verify the tooltip text fits at desktop and mobile widths.
4. Toggle Listen-Only on and confirm the active visual state is clear, Wing Mode is off, and chat
   input is hidden while the transcript control remains available.
5. Speak a synthetic phrase. Expected: the transcript appears, no assistant speech plays, and the
   backend returns no `streamId`. The final transcript appears as exactly one bubble.
6. Speak at least three synthetic phrases while Listen-Only remains on. Expected: saved transcript
   entries remain in one linear ambient lane, not `1 / N` branches for each utterance.
7. Toggle Listen-Only off. Expected: normal voice behavior can resume. A single live/Listen-Only
   boundary sibling may exist because live replies intentionally skip ambient transcripts, but the
   transcript entries themselves must not fan out as one branch per utterance.

Keep screenshots and logs public-safe: no private transcripts, account identifiers, call-session
ids, local absolute paths, or secrets.
