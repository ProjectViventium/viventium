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
- Assistant transcript rows preserve per-answer boundaries. A later assistant answer must not append
  onto the prior row, and async display must not add slow audio-paced spacing unless
  `VIVENTIUM_VOICE_SYNC_TRANSCRIPTION=1` is explicitly enabled for caption QA.
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

## Autonomous Off-LAN Media QA

`scripts/livekit_synthetic_audio_qa.js` can reproduce a cellular-style public call without using the
operator's phone. Run Chromium through an independently routed SOCKS proxy, point the browser at the
public Playground while keeping DB preflight local, and disable non-proxied UDP:

```bash
MONGO_URI=mongodb://127.0.0.1:27117/LibreChatViventium \
VIVENTIUM_QA_BROWSER_PLAYGROUND_URL=https://playground.app.example.com \
VIVENTIUM_QA_BROWSER_PROXY=socks5://127.0.0.1:19050 \
VIVENTIUM_QA_DISABLE_NON_PROXIED_UDP=1 \
node qa/modern-playground-voice/scripts/livekit_synthetic_audio_qa.js \
  --audio <synthetic-wav> \
  --expect "<synthetic transcript>" \
  --case-id public-browser-off-lan \
  --result output/playwright/remote-access/public-browser-off-lan.json \
  --screenshot output/playwright/remote-access/public-browser-off-lan.png
```

Acceptance requires all of the following, not merely a loaded public page:

- `browserProxyMediaSelected=true`
- a connected selected ICE pair using TCP or TURN over TCP/TLS
- the real voice worker is present
- the expected synthetic transcript persists exactly within the case limit
- targeted cleanup removes the synthetic user, call session, ingress row, transcript, and linked
  conversation

The same harness also supports two narrower diagnostics:

- `VIVENTIUM_QA_TURN_PROXY_URL` plus `VIVENTIUM_QA_TURN_PROXY_HOST_RULE` and
  `VIVENTIUM_QA_FORCE_RELAY=1` force the runtime-issued TURN credentials through an external TCP
  proxy. This passes only when a relay pair is selected.
- `VIVENTIUM_QA_PUBLIC_MEDIA_CANDIDATE` plus `VIVENTIUM_QA_PUBLIC_MEDIA_PROXY` rewrite only the
  named public TCP candidate to a controlled external ingress proxy.

Keep proxy processes, JSON, screenshots, raw candidate addresses, session IDs, and transcripts
local under `output/`; commit only sanitized status, candidate type/protocol, counts, and conclusions.

## Escaped Cross-Surface Case

Voice QA must include natural current-data prompts, not only simple greeting/latency prompts. If a
voice or linked chat user asks Viventium to look something up while Web Search appears enabled, the
run must prove the visible transcript/chat result, persisted `web_search` tool-call parts, provider
health or failure class, API logs, and generated config state. `MPV-006` and `WEB-004` own this
cross-surface regression until a full user-path rerun passes.

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

### 2026-05-15 LiveKit Voice Parity and Latency Follow-Up QA

Report: `qa/modern-playground-voice/reports/2026-05-15-livekit-parity-latency-followup-qa.md`

What this run covered:
- checked-out parent and nested LibreChat worktrees were inventoried; checked-out worktree commits
  are already ancestors of the active work
- generated runtime env now includes `VIVENTIUM_VOICE_LOG_LATENCY=1` as compiler-owned output
- a fresh authenticated modern-playground call opened from LibreChat, connected through LiveKit, and
  returned a real answer to a synthetic typed-transcript prompt
- the linked LibreChat conversation persisted and reloaded the same assistant answer
- Mongo persisted the new voice assistant turn as text-only content with no `type: "think"` part
- backend and gateway timing records now show a simple-turn first-text path around `5.2s` versus
  about `1.0s` on raw xAI `grok-4.3` no-reasoning requests
- official xAI and LiveKit docs were checked for Grok 4.3 reasoning, xAI Web Search, and LiveKit
  transcription/endpointing behavior

What remains:
- actual audio waveform capture was not recorded; transcript/TTS text sanitization was verified by
  browser, DB, and regression tests
- simple-turn latency is still not natural enough; the next proposed fix is raw provider and
  gateway audio timing instrumentation, primary tool/MCP init breakdown, and only then a narrow
  Phase A fast no-activation bypass if the evidence still points there

### 2026-05-14 Voice Latency Fast-Profile Partial QA

Report: `qa/modern-playground-voice/reports/2026-05-14-voice-latency-fast-profile-qa.md`

What this run covered:
- compiler output for documented voice fast-profile env
- live experimental Voice Call LLM config shape
- xAI no-reasoning Chat Completions direct provider timing
- xAI Responses built-in web-search timing probe
- targeted unit/regression suites for Phase A async policy, xAI parameter normalization, per-turn
  stream ids, and compiler env output
- real-browser modern-playground load and expired-session rejection behavior

What remains:
- a fresh authenticated LiveKit call for full MPV-004 end-to-end timings, because the old call URL
  used during the browser pass had expired and correctly returned `Unknown or expired call session`

### 2026-05-01 Follow-Up NTA Fallback Regression

Observed RCA before the fix:
- Backend follow-up generation already told the main agent to output `{NTA}` when there was no new
  user-visible continuation.
- A later persistence resolver refactor cleared `{NTA}` and then allowed deterministic fallback to
  promote raw background insight text into a persisted `cortex_followup`.
- Voice gateway behavior was then technically correct: it spoke the persisted `cortex_followup`.
  The bad persistence decision happened before the voice gateway poll.

Fix verification:
- Resolver regression:
  - non-replacement `{NTA}` with production-shaped background text stays silent
  - replacement/deferred-primary `{NTA}` still may use governed fallback text
  - voice-mode empty generation stays silent instead of speaking raw insight fallback text
- Automated checks:
  - `cd viventium_v0_4/LibreChat/api && npm run test:ci -- server/services/viventium/__tests__/BackgroundCortexFollowUpService.spec.js --runInBand`
    - Result: `16 passed`
  - `cd viventium_v0_4/LibreChat/api && npm run test:ci -- server/routes/viventium/__tests__/voice.spec.js --runInBand`
    - Result: `7 passed`
  - `cd viventium_v0_4/voice-gateway && .venv/bin/python -m unittest tests.test_worker_followup_scheduler -v`
    - Result: `7 passed`

Acceptance conclusion:
- Normal follow-ups now honor `{NTA}` as terminal.
- Modern playground voice still speaks persisted main-agent follow-ups, but raw background insight
  fallback text is no longer promoted when the main agent chose no follow-up or produced empty voice
  follow-up text.

### 2026-05-04 Async Transcript Boundary + Local Route QA

Observed RCA before the fix:
- LiveKit's built-in React session-message helper merges transcription chunks by segment metadata
  that can repeat across adjacent assistant answers.
- LiveKit's default synchronized transcription path paces transcript display with audio playout,
  which made the UI look slow and exposed spacing artifacts when TTS output was still streaming.

Fix verification:
- The modern playground now reads LiveKit transcription text streams directly and keys assistant
  transcript rows by text-stream id.
- `VIVENTIUM_VOICE_SYNC_TRANSCRIPTION` defaults to false; synchronized captions remain available
  only as an explicit QA/diagnostic opt-in.
- Automated checks:
  - `cd viventium_v0_4/agent-starter-react && pnpm run lint`
    - Result: passed
  - `cd viventium_v0_4/agent-starter-react && pnpm exec tsc --noEmit`
    - Result: passed
  - `cd viventium_v0_4/agent-starter-react && pnpm run build`
    - Result: passed
- Runtime smoke after `bin/viventium launch --modern-playground`:
  - LibreChat frontend returned `200`
  - modern playground returned `200`
  - voice gateway registered successfully

Acceptance conclusion:
- The browser transcript display path no longer appends a later assistant answer onto a prior
  answer row.
- Transcript rendering is decoupled from audio pacing by default, so Lyra/Cartesia and local
  Chatterbox routes use the same UI boundary behavior.

Release delivery note:
- This QA proves the active local checkout.
- For future-user release, publish the `agent-starter-react` component update and bump the parent
  component lock entry; the parent repository alone does not ship gitignored nested component
  changes.

### 2026-04-28 Cartesia Sonic-3 Live Join QA

Observed RCA before the final fix:
- The playground could load while the agent still failed to join because the LiveKit worker marked
  itself unavailable during local model warm-up.
- A second local cold-start path let the worker idle process time out before Whisper finished
  initialization.
- The QA account also lacked parity connected accounts for the selected call model, causing the
  backend to reject real model execution until encrypted OpenAI/Anthropic account records were
  copied from the parity source account.

Fix verification:
- The worker registered after restart and remained available.
- Browser flow:
  - opened an authenticated LibreChat agent conversation on `localhost`
  - clicked `Start voice call`
  - verified the modern playground loaded without `fetch failed`
  - verified Cartesia presented named voices (`Megan`, `Lyra`) rather than Sonic model choices
  - selected `Cartesia / Lyra`
  - clicked `Start chat`
  - observed `Agent is listening`
  - opened transcript and sent a synthetic typed call message
- Runtime route:
  - STT: AssemblyAI Universal Streaming
  - TTS: Cartesia Sonic-3 over WebSocket continuation
  - Voice: Lyra
- Markup evidence:
  - raw LLM/TTS text included an LLM-generated `<emotion value="excited"/>` tag
  - Cartesia request retained the tag and sent matching `generation_config.emotion`
  - debug `display_delta` and final browser transcript showed only clean text
- Browser console:
  - `0` errors
  - only LiveKit local-storage warnings from first-run device-choice state

Acceptance conclusion:
- The reported “agent does not join” path is fixed for the local QA route.
- Cartesia voice calls are Sonic-3-only with named voice selection.
- Streaming is preserved; the voice gateway sends incremental WebSocket continuation requests
  instead of waiting for the full final answer and a downloaded WAV.
- Voice-control tags are generated by the LLM, preserved for Cartesia TTS, and kept out of the
  modern playground user transcript.

### 2026-05-07 Public Edge LiveKit Node-IP Reuse Hardening

Observed behavior before the fix:
- Public-edge state could remain internally self-consistent after a network change:
  - `livekit_node_ip=<stale-lan-ip>`
  - `router.local_ip=<stale-lan-ip>`
- The helper reused that state while Caddy was still running, even when `<stale-lan-ip>` was no
  longer assigned to the Mac.
- LiveKit then advertised the stale node IP as its WebRTC media candidate. Signaling and dispatch
  setup succeeded, but the browser could not establish the peer connection because ICE checks
  received no media response.

### 2026-05-12 Local Whisper Model Route Regression

Observed RCA before the fix:
- The modern playground could display `Whisper.cpp Local / Best quality - large-v3-turbo` even when
  the local cache contained a corrupt or wrong `ggml-large-v3-turbo.bin` artifact.
- The cached artifact did not match the official whisper.cpp checksum for `large-v3-turbo`. The
  bundled pywhispercpp native path aborted when asked to transcribe with it. LiveKit interpreted the
  worker exit as the agent leaving the room, so the browser showed
  `Session ended / Agent left the room unexpectedly`.
- A stale generated App Support `runtime.env` could also make a direct source launch advertise a
  different local STT model than canonical `config.yaml`, even after the selected model artifact was
  repaired.
- The TTS selection was not the cause; the crash happened in local STT before the turn could complete.

Fix verification:
- Local whisper.cpp preserves the selected model, including `large-v3-turbo`.
- The voice gateway now checks the selected model against the official whisper.cpp SHA-1, atomically
  re-downloads that exact artifact if it is missing or corrupt, and load-validates it in an isolated
  subprocess before the worker uses it.
- The voice gateway and Telegram local-whisper paths use the same shared Whisper.cpp model registry,
  exact-model checksum, cache override, and atomic replacement discipline.
- A local Whisper.cpp prewarm failure now fails the worker startup honestly instead of registering a
  worker that will leave the LiveKit room on first use.
- Local Whisper.cpp downloads now run with an explicit timeout, and diagnostic escape hatches that
  weaken exact-model validation log visible warnings when used.
- Supported `bin/viventium start` launches regenerate runtime outputs before startup, and direct
  source launches do the same unless they are already being called from that canonical entrypoint.
- The modern playground and call-session route no longer silently remap saved/requested
  `large-v3-turbo` selections to another model.

Automated checks:
- `python3 -m py_compile viventium_v0_4/shared/whisper_cpp_models.py viventium_v0_4/voice-gateway/pywhispercpp_provider.py viventium_v0_4/voice-gateway/worker.py viventium_v0_4/telegram-codex/app/config.py viventium_v0_4/telegram-codex/app/transcribe_local.py viventium_v0_4/telegram-viventium/TelegramVivBot/config.py`
  - Result: passed
- `cd viventium_v0_4/voice-gateway && .venv/bin/python -m pytest tests/test_pywhispercpp_provider.py tests/test_worker_turn_handling.py tests/test_silero_vad_config.py tests/test_worker_ref_audio_validation.py -q`
  - Result: `83 passed`, `1 warning`
- `cd viventium_v0_4/telegram-codex && uv run python -m pytest tests/test_config.py tests/test_transcribe_local_models.py -q`
  - Result: `7 passed`
- `cd viventium_v0_4/agent-starter-react && pnpm exec tsc --noEmit`
  - Result: passed
- `cd viventium_v0_4/LibreChat/api && npm run test:ci -- --runInBand server/services/viventium/__tests__/CallSessionService.spec.js server/routes/viventium/__tests__/telegram.spec.js`
  - Result: `2 passed`, `47 tests passed`
- `uv run --with pytest --with PyYAML python -m pytest tests/release/test_config_compiler.py -q`
  - Result: `92 passed`
- `cd viventium_v0_4/telegram-viventium/TelegramVivBot && uv run python -m pytest ../tests/test_config_numeric_env.py ../tests/test_stt_env.py ../tests/test_stt_telegram_assemblyai.py ../tests/test_voice_preferences.py -q`
  - Result: `48 passed`

Runtime evidence:
- Voice-specific live health passed for the LibreChat API, LibreChat frontend, modern playground,
  and LiveKit-adjacent voice gateway. This MPV-002 run does not claim full optional-sidecar signoff.
- Voice gateway capabilities must report the selected local STT model and include
  `large-v3-turbo` as a normal local Whisper.cpp variant.
- Voice gateway startup logs must show exact-model preflight/self-heal followed by selected-model
  prewarm and worker registration.
- The selected cached model's SHA-1 must match the official whisper.cpp checksum for the advertised
  variant.
- Real-browser Playwright verification must show the selected local Whisper.cpp model in the
  Listening selector. A standalone playground opened without a LibreChat call-session deep link may
  still show the launch button disabled; that is separate from the model self-heal path.
- Latest live verification showed `Whisper.cpp Local / Best quality - large-v3-turbo (Recommended)`
  in the browser and `Whisper.cpp Local • large-v3-turbo` from the capability API after launcher
  regeneration.
- The same "preserve selected model" behavior is covered in LibreChat call-session service tests so
  saved voice routes cannot be silently rewritten.
- ClaudeViv review classified the core selected-model, checksum self-heal, isolated validation,
  fail-honest startup, and docs/QA claims as confirmed. It flagged Telegram's lack of voice-gateway
  depth load-validation as a non-blocking release-slice follow-up, not a contradiction of this
  modern-playground fix.

Residual scope:
- This run verified the modern playground route selector, live worker registration, and model
  catalog. It did not claim a full microphone utterance transcript, because the standalone playground
  page was opened without a LibreChat call-session deep link.
- Telegram local-whisper helpers are aligned at the shared registry, checksum, cache override, and
  atomic file replacement layer. The deeper isolated subprocess load-validation retry is currently
  voice-gateway-only and should be lifted into a shared helper in a follow-up if Telegram local voice
  QA becomes a release blocker.

Fix verification target:
- With no explicit `runtime.network.livekit_node_ip` override, public-edge state is reusable only
  when the saved LiveKit node IP is still assigned to a local interface.
- A self-consistent stale state must be stopped and rebuilt before LiveKit starts.
- Explicit operator node-IP overrides remain valid even when the override differs from the current
  default LAN interface, and first-run state persists that override instead of silently replacing it
  with the discovered public IP.

Executed QA:
- Added release coverage for self-consistent stale state where the cached node IP equals cached
  router local IP but does not appear in the current local interface set.
- Added release coverage for the positive current-interface path and the explicit override path.
- Added parser-level coverage for macOS `ifconfig`, Linux `ip -4 addr show`, and hostname fallback
  interface discovery.
- Ran the full remote-call tunnel release test module.
- Ran the modern playground dispatch-contract release tests to guard the prior
  `/api/connection-details` startup behavior.
- Ran the remote-call config compiler release subset that covers public LiveKit and node-IP env
  generation.
- Ran a dry runtime check against the current generated state without mutating it; the fixed helper
  rejected the stale saved node IP and would rebuild state on the next supported startup.

Acceptance conclusion:
- The fix is structural and source-owned. It does not edit generated App Support state, Mongo data,
  LiveKit room state, or local browser leftovers.
- The fix does not change the Modern playground explicit-dispatch sequence, worker type, local
  Whisper route, Listen-Only mode, or memory behavior.

### 2026-05-05 Transcript Text Parity + Local Whisper False-Positive Hardening

Observed behavior before the fix:
- Modern playground connected to LiveKit and the transcript button opened the typed chat panel.
- Sending the synthetic typed prompt `Voice transcript QA. Reply exactly: modern playground
  transcript ok` returned the expected assistant text in the same transcript.
- The same call then kept accepting microphone audio and persisted short room fragments as normal
  user turns. That is correct for an open live microphone, but too easy to trigger accidentally on
  the local Whisper VAD fallback because the fallback used the shared `0.1s` minimum speech
  threshold.
- The transcript input also focused only when the agent was unavailable, which made the opened
  transcript feel less direct than the normal LibreChat text box.

Fix verification target:
- The local Whisper fallback keeps the existing longer silence budget and now also uses a less-eager
  minimum speech threshold unless `VIVENTIUM_STT_VAD_MIN_SPEECH` is explicitly configured.
- The shared VAD defaults remain unchanged for remote/STT-owned routes.
- The transcript input focuses when the transcript is open and the agent is available.
- Typed transcript sends trimmed text so accidental surrounding whitespace is not persisted.

Acceptance conclusion:
- Typed Modern playground transcript chat and ordinary LibreChat text chat must both preserve the
  normal user-message -> assistant-message path.
- Ambient open-mic behavior is still governed structurally by voice route and VAD settings, not by
  prompt text or transcript keyword filtering.

Executed QA:
- Restarted the supported local stack with the modern playground enabled.
- Verified the generated LiveKit runtime advertises a local/LAN node address for local browser
  calls while keeping the public edge URL available for public callers.
- Verified LiveKit logs show room connection, user microphone track publish, publisher job
  assignment, voice gateway job receipt, and voice gateway `activeJobId` / `activeWorkerId`
  persistence.
- Verified Modern transcript chat from the LibreChat voice-call button:
  - the playground loaded from the LibreChat call entrypoint
  - `Start chat` connected the room
  - the transcript panel accepted typed text
  - the assistant response appeared in the transcript
  - the same assistant response was persisted in LibreChat message content and reloaded from the
    corresponding LibreChat conversation URL
- Verified ordinary LibreChat Viventium text chat with the same synthetic token pattern:
  - the assistant response appeared in the web chat
  - the assistant response was persisted in LibreChat message content and reloaded from the
    corresponding conversation URL
- After second-opinion review flagged a possible regression in the transcript boundary hook,
  restored the playground to the custom LiveKit transcription stream reader keyed by stream id.
  A follow-up two-turn Modern transcript QA verified two adjacent assistant answers remained
  separately visible in the transcript, persisted in message content, and reloaded from LibreChat
  history.
- Verified the Listen-Only control through the Modern playground user path:
  - the icon control was visible after the call connected
  - enabling it switched the user-facing status copy into listening-only mode
  - the typed transcript input was hidden while Listen-Only was enabled
  - disabling it restored the typed transcript input
  - persisted call-session state ended with Wing Mode off and Listen-Only off after the toggle was
    returned to normal chat mode
- Browser console result: no Playwright-observed page errors or console errors on the passing run.

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
