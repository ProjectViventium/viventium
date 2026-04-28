# Voice Call Hardening QA

Date: 2026-04-20, updated 2026-04-28
Scope: LibreChat voice-route stability, Anthropic history sanitization, Cartesia emotion-tag handling, worker startup capacity, and rapid-turn coalescing.

This QA report covers a coordinated release bundle across:
- `ProjectViventium/viventium`
- `ProjectViventium/viventium-librechat`

## User-Visible Bugs Covered

1. Anthropic voice/chat requests could fail with `messages.N.content.M.thinking.thinking: Field required`.
2. Cartesia emotion markup could be spoken literally when streaming chunks split a tag boundary.
3. One spoken sentence could fork into multiple sibling turns when endpointing submitted too early.
4. Startup emitted duplicate TTL-index warnings from repeated `expiresAt` index declarations.
5. A LiveKit voice worker could register and then become unavailable immediately on local Whisper
   routes because the CPU load threshold was too low for model warm-up.
6. Local Whisper worker prewarm could exceed the idle-process initialization timeout, so the agent
   never joined even though the playground and LiveKit room loaded.

## Root Causes Confirmed

- Historical/provider-formatted message content could contain malformed Anthropic `thinking` /
  `redacted_thinking` blocks that were not removed before execution.
- Voice persistence stripped control tags only on some save paths; the canonical history needed
  deterministic sanitization on both checkpoint and final saves.
- Cartesia streaming originally parsed only complete tags per chunk; a split tag boundary could leak
  literal `<emotion .../>` text into the outgoing transcript.
- Live transcript display used per-delta regex stripping, which could not safely classify incomplete
  SSML fragments such as `<em` before the rest of the tag arrived.
- Rapid same-parent voice ingress was keyed correctly, but merged text order depended on Mongo race
  order instead of actual ingress order.
- Several TTL-backed Mongo models declared `expiresAt` indexes twice.
- The worker load threshold was calibrated as if CPU load were an overload signal for remote
  providers. Local STT/TTS warm-up can legitimately push host load near `1.0`, causing LiveKit to
  stop dispatching jobs to an otherwise healthy local worker.
- The idle-process initialization timeout was shorter than local Whisper warm-up on some supported
  machines.

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

### 2026-04-28 Live Call Loading + Cartesia Sonic-3 QA

Automated checks:
- `voice-gateway/.venv/bin/python -m unittest discover -s voice-gateway/tests -v`
  - Result: `171 passed`
- `uv run --with pytest --with PyYAML python -m pytest tests/release/test_config_compiler.py tests/release/test_voice_playground_dispatch_contract.py tests/release/test_detached_librechat_supervision.py -q`
  - Result: `85 passed`
- `bash -n viventium-librechat-start.sh`
- `python3 -m py_compile` for the config compiler, worker, SSE helpers, and LibreChat LLM bridge.

Live browser QA:
- Used the local QA account, after copying encrypted OpenAI and Anthropic connected-account records
  from the parity source account in Mongo. No raw key values were printed or stored in this report.
- Launched a fresh LibreChat call through the phone-button entrypoint.
- Confirmed the modern playground loaded without `fetch failed`.
- Confirmed the speaking picker showed `Cartesia / Lyra`; the Cartesia submenu is a voice picker,
  not a Sonic model picker.
- Clicked `Start chat`; the page entered the connected call state and showed `Agent is listening`.
- Sent a synthetic typed call turn through the transcript panel.

Runtime evidence, sanitized:
- Worker health endpoint returned `ok`.
- Voice gateway log showed a fresh `registered worker` after restart.
- No fresh `worker is at full capacity`, `timed out waiting`, or idle-process initialization errors
  appeared after the load-threshold and timeout patch.
- The selected TTS route logged:
  - provider: `cartesia`
  - model: `sonic-3`
  - voice: Lyra's configured voice id
  - API version: `2026-03-01`
  - transport: Cartesia WebSocket continuation path
- LLM debug logging showed:
  - raw/TTS text included `<emotion value="excited"/>`
  - display text omitted the tag
  - Cartesia WebSocket requests preserved the emotion tag in `transcript` and sent
    `generation_config.emotion=excited`
- Browser transcript showed only the user-facing sentence, with no `<emotion>` tag fragments.

## QA Conclusion

- The Anthropic malformed-thinking failure is fixed in the provider-bound path.
- Rapid same-parent voice submissions now coalesce onto one stream without reversing the spoken
  order.
- Canonical saved assistant history is clean after voice synthesis.
- Cartesia streaming now structurally consumes emotion tags across chunk boundaries instead of
  sending the literal markup through to speech.
- Local Whisper-backed workers no longer mark themselves unavailable during normal model warm-up,
  and the initialization timeout now covers supported local STT cold starts.
- Live transcript display now uses a stateful structural filter, so Cartesia tags remain available
  to TTS while incomplete tag fragments stay out of user-visible text.

## Residual Notes

- Debug logging is intentionally opt-in through `VIVENTIUM_VOICE_DEBUG_TTS=1`; public QA artifacts
  should record only sanitized provider/model/route facts, never secrets, account identifiers, or
  call-session ids.
