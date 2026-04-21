# Voice Streaming First Report

Date: 2026-04-20

## Change Under Test
- `voice-gateway/cartesia_tts.py`
- `voice-gateway/fallback_tts.py`
- `voice-gateway/sse.py`
- `voice-gateway/worker.py`
- `LibreChat/api/server/services/viventium/surfacePrompts.js`
- `voice-gateway/tests/test_cartesia_tts.py`
- `voice-gateway/tests/test_fallback_tts.py`
- `voice-gateway/tests/test_sse.py`
- `voice-gateway/tests/test_worker_ref_audio_validation.py`
- `LibreChat/api/server/services/viventium/__tests__/surfacePrompts.spec.js`

## Test Plan
1. Verify the edited Python modules compile.
2. Run the targeted LibreChat surface-prompt unit test for transcript/persistence stripping.
3. Run the full voice-gateway unit suite.
4. Measure live Cartesia TTFA on the incremental stream path after the fallback sanitization refactor.
5. Check whether the local browser voice surface is available for end-to-end QA.
6. Verify the browser voice surface with real browser automation when the port appears up.

## Commands Run
```bash
python3 -m py_compile \
  viventium_v0_4/voice-gateway/cartesia_tts.py \
  viventium_v0_4/voice-gateway/fallback_tts.py \
  viventium_v0_4/voice-gateway/sse.py \
  viventium_v0_4/voice-gateway/worker.py \
  viventium_v0_4/voice-gateway/tests/test_cartesia_tts.py \
  viventium_v0_4/voice-gateway/tests/test_fallback_tts.py \
  viventium_v0_4/voice-gateway/tests/test_sse.py \
  viventium_v0_4/voice-gateway/tests/test_worker_ref_audio_validation.py

node --check viventium_v0_4/LibreChat/api/server/services/viventium/surfacePrompts.js

cd viventium_v0_4/LibreChat/api
npm run test:ci -- server/services/viventium/__tests__/surfacePrompts.spec.js

cd viventium_v0_4/voice-gateway
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'

bash "$HOME/.codex/skills/playwright/scripts/playwright_cli.sh" open http://localhost:3300 --headed
```

### 2026-04-21 Re-validation Commands
```bash
cd /path/to/viventium/viventium_v0_4/voice-gateway
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'

cd /path/to/viventium/viventium_v0_4/LibreChat/api
npm run test:ci -- server/services/viventium/__tests__/surfacePrompts.spec.js

cd /path/to/viventium
python3 -m pytest tests/release/test_voice_playground_dispatch_contract.py -q

bash "$HOME/.codex/skills/playwright/scripts/playwright_cli.sh" open http://127.0.0.1:3300 --headed
bash "$HOME/.codex/skills/playwright/scripts/playwright_cli.sh" snapshot
bash "$HOME/.codex/skills/playwright/scripts/playwright_cli.sh" click e30
```

## Results

### 1. Compile Check
- Pass

### 2. LibreChat Targeted Unit Test
- Pass
- Result: `42` tests passed in `surfacePrompts.spec.js`

### 3. Voice-Gateway Unit Suite
- Pass
- Result: `Ran 132 tests in 0.105s`

### 4. Live Cartesia Benchmark
Environment:
- Local runtime env loaded from the active Viventium runtime
- Incremental chunks: `["<emotion value=\"exc", "ited\"/>Hello ", "[laughter", "] world"]`
- Buffer setting: `VIVENTIUM_CARTESIA_MAX_BUFFER_DELAY_MS=120`

Measured on the native Cartesia stream path after the fallback sanitization refactor:
- `cartesia_stream_first_audio_ms=348.5`
- `cartesia_stream_done_ms=761.0`

Observed impact:
- The structural sanitization refactor did not break native streaming. Speech still began in well
  under half a second on this machine for the sampled utterance.

### 5. Browser Surface Availability
- Real browser automation was attempted against `http://localhost:3300`
- Result: Playwright hit `net::ERR_CONNECTION_TIMED_OUT` twice while waiting for
  `domcontentloaded`
- Interpretation: the modern playground port was not healthy enough for browser E2E verification in
  this session, even though the local process appeared to be listening

### 6. 2026-04-21 Browser Re-validation
- Re-ran the modern playground against `http://127.0.0.1:3300`
- Result: page loaded successfully with title `Viventium Voice Assistant`
- Verified the default listening and speaking selectors rendered with the expected covered local
  providers
- Expanded the listening selector and confirmed the menu opened with visible provider choices
- Captured a fresh browser screenshot at `.playwright-cli/page-2026-04-21T01-25-58-923Z.png`
- Observed one console error from the Next.js dev HMR WebSocket
  (`/_next/webpack-hmr` handshake). This is dev-server noise, not a product-surface failure.

## Limitations
- Full microphone/call-session interaction was not exercised in browser QA during this pass; the
  verified scope was the live modern playground render plus selector interaction.
- Live fallback-to-OpenAI was not re-run in this pass; fallback correctness is covered by unit
  tests, including streaming failure -> fallback and chunk-boundary markup stripping for plain-text
  fallback providers.

## Conclusion
- Acceptance criteria are met for the streaming-first Cartesia fix and for the follow-up refactor
  that removed the new hardcoded fallback token regex.
- Browser QA is no longer blocked at the page-load layer. The remaining gap is full microphone and
  call-session interaction E2E, not basic modern playground availability.
