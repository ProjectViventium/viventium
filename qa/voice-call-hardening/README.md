# Voice Call Hardening QA

Date: 2026-04-20
Scope: LibreChat voice-route stability, Anthropic history sanitization, Cartesia emotion-tag handling, and rapid-turn coalescing.

This QA report covers a coordinated release bundle across:
- `ProjectViventium/viventium`
- `ProjectViventium/viventium-librechat`

## User-Visible Bugs Covered

1. Anthropic voice/chat requests could fail with `messages.N.content.M.thinking.thinking: Field required`.
2. Cartesia emotion markup could be spoken literally when streaming chunks split a tag boundary.
3. One spoken sentence could fork into multiple sibling turns when endpointing submitted too early.
4. Startup emitted duplicate TTL-index warnings from repeated `expiresAt` index declarations.

## Root Causes Confirmed

- Historical/provider-formatted message content could contain malformed Anthropic `thinking` /
  `redacted_thinking` blocks that were not removed before execution.
- Voice persistence stripped control tags only on some save paths; the canonical history needed
  deterministic sanitization on both checkpoint and final saves.
- Cartesia streaming originally parsed only complete tags per chunk; a split tag boundary could leak
  literal `<emotion .../>` text into the outgoing transcript.
- Rapid same-parent voice ingress was keyed correctly, but merged text order depended on Mongo race
  order instead of actual ingress order.
- Several TTL-backed Mongo models declared `expiresAt` indexes twice.

## Checks Executed

### Automated: `ProjectViventium/viventium-librechat`

- `cd viventium_v0_4/LibreChat/api && npm run test:ci -- --runInBand server/routes/viventium/__tests__/voice.spec.js server/services/viventium/__tests__/normalizeTextContentParts.spec.js server/controllers/agents/__tests__/requestPersistence.spec.js`
- `cd viventium_v0_4/voice-gateway && .venv/bin/python -m unittest discover -s tests`

Results:
- LibreChat focused suites: `3 passed / 29 tests`
- Voice gateway suite: `138 passed`

### Live Runtime Validation

All checks were run against the canonical local stack on `localhost` with the real voice route and
Mongo state.

1. Health:
   - `http://localhost:3180/api/health` returned `200`
   - `http://localhost:3190` returned `200`
   - `http://localhost:3300` returned `200`

2. Anthropic + history sanitization (`ProjectViventium/viventium-librechat`):
   - Reused a real voice conversation that previously produced the Anthropic
     `thinking.thinking` failure.
   - Started a fresh worker-authenticated `/api/viventium/voice/chat` run against that
     conversation after the fix.
   - Result: request completed successfully, SSE finished cleanly, and no new provider error was
     returned.

3. Rapid-turn coalescing (`ProjectViventium/viventium-librechat`):
   - Sent two `/api/viventium/voice/chat` requests ~80 ms apart against the same active
     conversation and same call-session identity.
   - Result: both requests resolved to one launched stream, only one new user turn was persisted,
     and the merged text preserved the spoken order:
     - first half
     - second half
   - Result: no extra sibling branch was created under the prior assistant leaf.

4. Persisted assistant sanitization (`ProjectViventium/viventium-librechat`):
   - Inspected the canonical assistant messages created by the live voice-route probes.
   - Result: saved `text` and saved text-content parts contained no raw `<emotion .../>` tags and
     were marked `unfinished: false` after final completion.

5. Cartesia streaming tag handling (`ProjectViventium/viventium`):
   - Confirmed recent live call sessions were explicitly requesting:
     - STT: `assemblyai / universal-streaming`
     - TTS: `cartesia / sonic-3`
   - Replayed the exact user-visible chunk shape through the streaming emotion parser:
     - input chunks:
       - `<emotion value="content"/>Yeah, it feels smoother on my end too. Less choppy.`
       - `<emotion value="curious"/>Anything you want me to test, or just letting me know?`
     - emitted segments:
       - text: `Yeah, it feels smoother on my end too. Less choppy.` / emotion: `content`
       - text: `Anything you want me to test, or just letting me know?` / emotion: `curious`
   - Result: the streaming path preserved emotion state but removed the literal tag text from the
     transcript sent to synthesis.

6. Startup quality (`ProjectViventium/viventium-librechat`):
   - Consolidated duplicate TTL definitions so the affected Mongo schemas now declare a single
     `expiresAt` TTL index each.

## QA Conclusion

- The Anthropic malformed-thinking failure is fixed in the provider-bound path.
- Rapid same-parent voice submissions now coalesce onto one stream without reversing the spoken
  order.
- Canonical saved assistant history is clean after voice synthesis.
- Cartesia streaming now structurally consumes emotion tags across chunk boundaries instead of
  sending the literal markup through to speech.

## Residual Notes

- Live LibreChat chat streaming can still surface raw voice markup during generation because the
  live stream intentionally carries voice-mode text for synthesis. The canonical saved history is
  now clean after completion.
