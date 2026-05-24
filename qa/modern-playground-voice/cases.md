# Modern Playground Voice Cases

## Natural User Use Case Checklist

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `MPV-UC-001` | Start a call from an authenticated LibreChat conversation and send a simple typed or spoken prompt. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `MPV-001` | LibreChat browser plus Modern Playground | Voice gateway logs, LiveKit state, persisted chat message, generated voice config | Call connects, agent joins, transcript shows a real assistant answer. | 2026-05-18 PARTIAL PASS for synthetic microphone/worker dispatch; authenticated answer still required |
| `MPV-UC-002` | Interrupt or send a second turn while prior work or follow-up timing is still active. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `MPV-003` | Modern Playground call | Transcript, stream ids, Mongo message chain, voice gateway timing logs | Turns stay distinct, no stale follow-up is spoken as current conversation state. | 2026-05-15 PARTIAL |
| `MPV-UC-003` | Ask the voice agent to look something up when Web Search appears enabled. | `docs/requirements_and_learnings/06_Voice_Calls.md`, `docs/requirements_and_learnings/10_Open_Source_Web_Search.md` / `MPV-006` | Modern Playground and linked LibreChat browser conversation | Visible transcript/chat, persisted `web_search` tool-call parts, local search backend health, hosted search backend status, request logs, Docker/container state for local providers, browser/local-delegation fallback when available | Voice/search either returns grounded evidence or says the exact degraded provider class without inventing facts; named-entity/current-fact failures use fallback before stopping. | FAIL (escaped 2026-05-18; fix run pending) |
| `MPV-UC-004` | Reload linked chat after a voice turn that used model/tooling. | `docs/requirements_and_learnings/34_Voice_Chat_LLM_Override.md` / `MPV-005` | LibreChat browser conversation | DB message content parts, logs, transcript, generated no-reasoning config | Visible chat persists audible answer only; no reasoning blocks or raw private transcript leak. | 2026-05-21 PASS for recovered provider-error cleanup and route restoration; full spoken audio not rerun |
| `MPV-UC-005` | Open a modern-playground call page while voice settings are cold, slow, or temporarily unavailable. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `MPV-007` | Modern Playground browser page plus launcher/runtime logs | Browser network timing, visible CTA state, retry copy, Next.js route compile logs, call-session DB counts | Start chat remains available, settings loading is bounded/retryable, and cold-route compile is prewarmed on launcher startup. | 2026-05-18 PASS for pre-call gate and bounded settings load; full microphone join not rerun |
| `MPV-UC-006` | Speak a thought, pause for `0.7s` to `1.5s`, then continue speaking in the same LiveKit call. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `MPV-008` | Modern Playground browser with fake microphone WAV, LiveKit, voice worker, Mongo | Voice gateway timing logs, Listen-Only ingress record, Mongo transcript message count, synthetic fixture manifest | Both endpointed STT segments are persisted as one continued transcript turn/message inside the continuation window. | 2026-05-18 PASS with synthetic TTS/fake-mic QA |
| `MPV-UC-007` | Click Start chat once and wait for the call to connect. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `MPV-009` | Modern Playground browser page, LiveKit, voice gateway logs | Button state, browser console/network, LiveKit microphone publish, `JT_PUBLISHER` assignment, call-session DB state | One click starts the call, duplicate clicks are disabled, and the microphone turns on after room connect. | 2026-05-18 PASS for one-click visible UI and duplicate-request prevention; full fresh spoken-turn remains under broader call cases |
| `MPV-UC-008` | Install or bootstrap with the default voice-capable configuration. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `MPV-010` | Installer/bootstrap component selection and launcher help | `bootstrap_components.select_components`, compiled runtime env, launcher flags | Default selection includes `agent-starter-react` and excludes `agents-playground`; classic UI appears only after explicit classic selection. | 2026-05-19 automated release case added |
| `MPV-UC-011` | Reload a linked chat after provider overload was recovered by visible assistant text. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `MPV-011` | LibreChat browser conversation | DB content parts, recovered error-class metadata, renderer tests, runtime logs | Recovered answer is visible, stale provider error card is not visible, refresh keeps the clean state. | 2026-05-21 PASS in `reports/2026-05-21-recovered-provider-error-card-cleanup.md` |
| `MPV-UC-012` | Hear a streamed voice answer whose model deltas split punctuation from the phrase. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `MPV-012` | Modern Playground call with xAI/Cartesia/fallback TTS as available | Voice gateway exact TTS debug logs, transcript, provider metrics, buffer unit tests | The assistant speaks naturally and never says a standalone period as "dot"; transcript remains readable. | 2026-05-21 PASS; see dated TTS orphan punctuation QA report |
| `MPV-UC-013` | Hear a streamed voice answer when model text contains links, emails, references, markdown, or provider markup. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `MPV-013` | Modern Playground call with current TTS route and fallback route | Voice gateway `llm_delta`, `tts_emit`, provider request logs when available, sanitizer/unit tests | TTS receives speech-safe phrase chunks; plain providers do not receive raw tags; provider-supported controls are preserved only on capable routes. | 2026-05-21 PASS; live browser QA plus provider metrics |
| `MPV-UC-014` | Verify a voice/TTS fix after adding logs or instrumentation. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `MPV-014` | Modern Playground call, active voice runtime, logs, DB/state | Runtime artifact proof, audible/delivered voice evidence, sanitized transcript evidence, exact TTS/provider-input logs, DB/state, owning code | The changed runtime is proven active and the post-change call demonstrates the intended audible behavior; instrumentation alone is not accepted. | 2026-05-22 PASS for local Whisper barge-in runtime/browser/log proof |
| `MPV-UC-015` | Interrupt a local Whisper assistant reply while it is speaking. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `MPV-015` | Modern Playground call with local `pywhispercpp` STT | Visible transcript, audible behavior, voice gateway interruption policy/state logs, generated runtime config, DB call-session route | A sustained one-word or short-phrase barge-in pauses/interrupts the agent without waiting for final local Whisper text; AssemblyAI word-guard defaults remain unchanged. | 2026-05-22 PASS in `reports/2026-05-22-local-whisper-bargein-qa.md` |

## MPV-001 Authenticated Call Launch

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`
- User Outcome: An authenticated chat can open a valid modern-playground call session and the voice
  agent joins instead of leaving unexpectedly.
- Surfaces: LibreChat Web UI, Modern Playground, LiveKit, Voice Gateway
- Preconditions: canonical local stack running; authenticated Viventium user; synthetic
  non-personal chat available.
- Steps:
  1. Open an authenticated LibreChat agent conversation.
  2. Click the phone button.
  3. Verify the modern playground opens with a call-session deep link.
  4. Click `Start chat`.
  5. Open transcript and send a synthetic typed prompt.
- Expected Result: LiveKit connects, the voice worker receives the job, and the assistant returns a
  real answer. Forbidden result: `Session ended / Agent left the room unexpectedly`.
- Evidence: `qa/modern-playground-voice/README.md`
- Last Run: 2026-05-18 partial pass for synthetic microphone/worker dispatch in
  `reports/2026-05-18-whispercpp-turn-taking-endpointing.md`; authenticated answer acceptance still
  required.

## MPV-002 Local Whisper Exact-Model Self-Heal

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`
- User Outcome: Local Whisper voice calls preserve the user-selected Whisper.cpp model and repair
  missing or corrupt local model artifacts instead of silently changing models.
- Surfaces: Modern Playground, Voice Gateway capability API, Voice Gateway startup, Telegram local
  transcription helpers
- Preconditions: canonical local stack running with `VIVENTIUM_STT_PROVIDER=whisper_local` or
  equivalent local `pywhispercpp` route.
- Steps:
  1. Query the voice gateway capabilities endpoint.
  2. Open `http://localhost:3300` in a real browser.
  3. Inspect the Listening selector and its dropdown.
  4. Seed a stale generated runtime env with a different local STT model, then start through the
     supported launcher and verify canonical `config.yaml` wins.
  5. Corrupt or remove the cached selected model in a synthetic/temp cache and run the model
     self-heal check across voice gateway and Telegram local transcription helpers.
  6. Check the voice gateway startup log for the selected model preflight and prewarm.
- Expected Result: Current STT preserves the selected local model, including `large-v3-turbo` when
  selected. Missing or corrupt cache files are re-downloaded for that exact model and load-validated
  before worker use. Stale generated runtime env is regenerated from canonical config before launch.
  Forbidden result: runtime silently changes the selected model to `base.en`, `small`, OpenAI STT,
  or any other route to hide the local Whisper.cpp problem.
- Evidence: `qa/modern-playground-voice/README.md#2026-05-12-local-whisper-model-route-regression`
- Last Run: 2026-05-12, updated after exact-model self-heal fix.

## MPV-003 Sequential Voice Turns During Phase B

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`,
  `docs/requirements_and_learnings/02_Background_Agents.md`
- User Outcome: A second spoken turn can be sent while the prior turn's Phase B follow-up window is
  still open, without losing the second turn or speaking a stale follow-up as if the conversation had
  not moved on.
- Surfaces: Modern Playground, Voice Gateway, LibreChat voice route, Agents stream manager, Mongo
  conversation persistence.
- Preconditions: canonical local stack running; voice call route with at least one background cortex
  capable of producing a delayed Phase B follow-up; synthetic non-personal prompt text.
- Steps:
  1. Start an authenticated modern-playground voice call.
  2. Send a first synthetic prompt that activates a background cortex while still receiving an
     immediate Phase A answer.
  3. Before the background follow-up window closes, send a second synthetic prompt in the same call.
  4. Inspect the visible transcript, LibreChat conversation, backend logs, and Mongo messages.
- Expected Result: Both user turns and both assistant turn outcomes persist under the correct
  parent chain. The second stream does not return `Stream not found`. Any Phase B continuation from
  the first turn is adjudicated with the newer visible exchange and may resolve to silence. Distinct
  generated turns use distinct one-turn stream ids unless the requests were intentionally coalesced
  inside the same ingress window.
- Forbidden Result: the second user turn appears only in the playground transcript but not in Mongo;
  the voice gateway speaks a generic service error; a stale first-turn follow-up is generated with
  moved-on state missing; a later turn subscribes to or completes an older turn's stream.
- Evidence: `qa/modern-playground-voice/reports/2026-05-15-livekit-parity-latency-followup-qa.md`
- Last Run: 2026-05-15 partial browser/DB regression. Fresh multi-turn Phase B overlap timing is
  still needed for the full MPV-003 stress case.

## MPV-004 Voice Latency Timing Profile

- Requirement: `docs/requirements_and_learnings/14_Voice_Latency_and_Memory_RCA.md`,
  `docs/requirements_and_learnings/06_Voice_Calls.md`
- User Outcome: A simple directly addressed voice turn should start speaking quickly enough to feel
  natural, and logs must show where any remaining delay occurred.
- Surfaces: Modern Playground, LiveKit, Voice Gateway, LibreChat voice route, Voice Call LLM provider
  route, TTS.
- Preconditions: canonical local stack running; voice latency logging enabled; authenticated
  modern-playground call session; main agent Voice Call LLM route selected.
- Steps:
  1. Start an authenticated modern-playground voice call.
  2. Speak a simple non-tool prompt such as `Hey, can you hear me clearly?`.
  3. Capture STT final transcript timing, `/api/viventium/voice/chat` ready time, SSE subscribe time,
     Phase A async/forced-off decision, provider first-text timing, TTS first-audio timing, and Phase
     B follow-up timing.
  4. Repeat with a current-data prompt such as a weather/web question and record whether the route
     used local web-search tooling or a provider-native search path.
  5. Compare transcript, Mongo persistence, and logs to confirm the visible answer matches the
     recorded timing path.
- Expected Result: The simple turn avoids synchronous background detection when direct-action holds
  are either absent or owned, uses the voice provider's no-reasoning parameter shape, and produces a
  complete per-stage timing record. For xAI Chat Completions, provider-fetch telemetry shows
  `reasoning_effort="none"` on the actual outbound request, not only on the intermediate voice
  config. Current-data turns identify tool latency separately from model first-token latency.
  Healthy primary turns do not eagerly initialize the fallback agent before first audio; fallback
  initialization appears only when primary fails. OAuth-pending MCP servers either report an
  isolated `oauth_pending` probe or a later `oauth_pending_memo_hit`, not repeated opaque multi-second
  retries in the same hot path.
- Forbidden Result: generic "service unavailable" speech without a provider/tool error class;
  missing per-turn stream id; voice-only prompt/context truncation that breaks parity; hidden model
  remap; raw private transcript or call-session identifiers copied into public QA artifacts.
- Evidence: `qa/modern-playground-voice/reports/2026-05-15-livekit-parity-latency-followup-qa.md`
- Last Run: 2026-05-19 in `reports/2026-05-19-livekit-tts-misalignment-fixes.md` applied the
  LiveKit API, latency logging, package-pin, and xAI first-audio optimization fixes while preserving
  async transcript output. Browser first audible-frame capture and current-data/tool-call timing
  remain open.

## MPV-005 Voice Transcript Must Not Persist Reasoning Blocks

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`,
  `docs/requirements_and_learnings/34_Voice_Chat_LLM_Override.md`
- User Outcome: A live voice call transcript shows only the audible assistant response, not provider
  reasoning/thinking internals.
- Surfaces: Modern Playground, LibreChat conversation view, Agents stream manager, Mongo
  conversation persistence.
- Preconditions: canonical local stack running; voice call route with a Voice Call LLM configured
  for no reasoning, such as xAI Chat Completions `reasoning_effort: "none"`.
- Steps:
  1. Start an authenticated modern-playground voice call.
  2. Send a simple non-tool prompt.
  3. Inspect the modern-playground transcript during the turn.
  4. Open the linked LibreChat conversation after the turn completes.
  5. Inspect Mongo message content for the assistant message.
  6. Inspect voice latency logs for provider reasoning-delta suppression and sanitized provider
     request knobs.
- Expected Result: The spoken/transcript answer is present, but no visible `Thoughts` block appears
  in the conversation, no assistant message content part with `type: "think"` is persisted for the
  voice turn, provider-fetch telemetry confirms the no-reasoning request shape when the provider
  supports it, and logs show `voice_reasoning_delta_suppressed` if a provider emits reasoning
  anyway.
- Forbidden Result: Visible LibreChat `Thoughts` cards from a voice call; persisted voice assistant
  content containing `type: "think"`; raw prompt/message text copied into public QA evidence.
- Evidence: `qa/modern-playground-voice/reports/2026-05-15-livekit-parity-latency-followup-qa.md`
- Last Run: 2026-05-15 fresh authenticated LiveKit typed-transcript run, LibreChat reload, and Mongo
  inspection passed for a new simple voice turn.

## MPV-006 Voice Web-Search Request Must Not Escape The Checklist

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`,
  `docs/requirements_and_learnings/10_Open_Source_Web_Search.md`, and
  `qa/feature-user-use-case-checklist.md`.
- User Outcome: When the user naturally asks the voice agent to look up current information, the
  transcript/chat result proves a real search path or gives honest degraded-provider wording.
- Surfaces: Modern Playground, linked LibreChat conversation, Web Search tool, SearXNG/Firecrawl or
  hosted provider, Mongo message persistence, API logs.
- Preconditions: local stack running; selected agent has Web Search capability enabled; synthetic
  public-safe current-data prompt; provider health state intentionally recorded before the run.
- Steps:
  1. Start an authenticated modern-playground call from LibreChat or use the linked conversation
     produced by that call.
  2. Ask a synthetic current-data prompt such as `Please look up the current public date and venue for
     Example Summit and answer only from search results.`
  3. Observe the modern-playground transcript and the linked LibreChat visible answer.
  4. Inspect persisted assistant content for `web_search` tool-call parts and web-search artifacts.
  5. Probe local/hosted search and scrape provider health. For local SearXNG/Firecrawl, explicitly
     record Docker daemon and container state before interpreting the failure.
  6. Inspect API/tool logs for returned sources or failure class.
  7. If the prompt is a named-entity/contact/date/current-fact lookup and search fails operationally,
     verify the assistant uses available browser/local-delegation fallback or states why fallback is
     unavailable.
  8. Compare the final spoken/text wording with actual provider health and persisted state.
- Expected Result: healthy provider state yields a grounded answer with fetched evidence. Degraded
  provider state yields explicit degraded-service wording and a retry/setup path, without pretending
  the event was not searchable or asking the user for data only because QA failed to verify search.
- Forbidden Result: the UI/voice answer says only that search is not pulling while QA has not proven
  provider health, Docker/local-service state where relevant, tool-call persistence, and logs; the
  Web Search checkbox is treated as proof of usable search; a non-browser/unit-only check is
  accepted for this browser/voice feature; an available browser/local-delegation fallback is skipped
  after an operational search failure on a current-fact lookup.
- Evidence: public-safe report with visible observation, DB/tool-call counts, search provider health,
  API log failure class or returned-source count, generated config state, and privacy review.
- Last Run: FAIL (escaped 2026-05-18 from live local browser evidence; regression case added, product
  fix and full rerun pending).

## MPV-007 Voice Settings Loading Must Not Block Start Chat

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`
- User Outcome: Opening a call deep link should not feel stuck just because optional voice-settings
  display data is still loading. The user can start the call while settings finish loading or retry.
- Surfaces: Modern Playground browser page, playground API proxy, LibreChat call-session voice
  settings route, launcher startup logs, Mongo call-session collection.
- Preconditions: local stack running; synthetic active call-session deep link available; no private
  prompt, call id, or user identifier copied into evidence.
- Steps:
  1. Open a synthetic modern-playground call deep link in a real browser.
  2. Simulate or observe a slow `/api/call-session-voice-settings` response.
  3. Confirm the primary button is enabled as `Start chat` while the settings panel still shows a
     loading or retry state.
  4. Let the settings request time out or recover and verify the visible text is Viventium-specific
     recovery copy, not a raw browser fetch exception.
  5. Inspect launcher/runtime logs for cold compile or prewarm evidence for
     `call-session-voice-settings`, `call-session-state`, and `connection-details`.
  6. Inspect call-session DB counts and indexes only as supporting evidence; DB hygiene cannot
     replace the browser-visible gate check.
- Expected Result: `Start chat` remains available during settings loading. Slow settings fetches are
  timeout-bounded with a retry path. Launcher-managed startup prewarms the voice startup routes so a
  first real call page is not the route compiler's first hit.
- Forbidden Result: the page stays indefinitely at `Loading your voice settings...`; the primary
  call action is disabled only because voice settings are still loading; raw `Failed to fetch` or
  stack text is shown to users; public QA artifacts contain real call-session ids, local usernames,
  or secret-bearing URLs.
- Evidence: `qa/modern-playground-voice/reports/2026-05-18-voice-settings-startup-loading.md`
- Last Run: 2026-05-18 PASS for the pre-call browser gate and timeout wording; full microphone join
  was not rerun because this case targets the pre-call loading gate.

## MPV-008 Synthetic Audio Pause Continuation

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`
- User Outcome: Local Whisper can use a responsive `0.5s` silence target without forcing a human
  resumed thought into multiple persisted transcript turns.
- Surfaces: Modern Playground, LiveKit, Voice Gateway, LibreChat voice route, Mongo transcript
  persistence.
- Preconditions: local runtime running from the current checkout; local Whisper.cpp route available;
  synthetic non-personal TTS WAV fixtures generated under `output/qa/`.
- Steps:
  1. Generate synthetic speech fixtures for short speech, long speech, a `0.7s` pause, and a `1.5s`
     pause.
  2. Launch the modern playground with Chromium fake microphone audio.
  3. Start the call, enable the microphone if the UI requests it, and wait for real LiveKit STT
     persistence.
  4. Assert the pause fixtures match expected text and produce at most one Listen-Only transcript
     row inside the continuation window.
  5. Inspect voice logs for VAD/transcription timing and DB cleanup counts for synthetic records.
- Expected Result: Pause fixtures with `0.7s` and `1.5s` silence persist as one transcript message
  with both clauses. Short and long fixtures still persist complete expected text. Explicit LiveKit
  dispatch is created for the claim winner, and the worker job is assigned.
- Forbidden Result: `Session ended / Agent did not join the room`; two transcript rows for a resumed
  thought inside the continuation window; schema/mocks disagree about fields required for
  continuation; public QA artifacts contain raw call IDs or local absolute paths.
- Evidence: `qa/modern-playground-voice/reports/2026-05-18-synthetic-audio-livekit-continuation.md`
- Last Run: 2026-05-18 PASS for short, long, `0.7s` pause, and `1.5s` pause with synthetic
  TTS/fake-microphone LiveKit QA. The visible playground transcript panel was not proven in this
  harness; persistence/log evidence is the accepted backend proof for this case.

## MPV-008B Local Whisper Large-Turbo Latency Budget

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`
- User Outcome: Local `large-v3-turbo` Whisper.cpp transcripts appear promptly after completed
  speech without changing the selected model or weakening pause-continuation behavior.
- Surfaces: Modern Playground, LiveKit, Voice Gateway, pywhispercpp, Mongo transcript persistence,
  voice latency logs.
- Preconditions: canonical local runtime running from the current checkout; `whisper_local` /
  `pywhispercpp` selected with `large-v3-turbo`; synthetic non-personal TTS WAV fixtures include
  short, long, and pause-continuation speech plus leading silence for fake-microphone readiness.
- Steps:
  1. Run direct pywhispercpp benchmarks for current and optimized transcribe parameters.
  2. Promote/restart the local runtime and verify worker prewarm performs a real inference warmup.
  3. Run fake-microphone LiveKit QA for short speech, a `0.7s` pause continuation, and longer
     speech.
  4. Capture per-stage voice logs for VAD silence, PCM conversion/resample, whisper.cpp inference,
     LiveKit `transcription_delay`, Listen-Only persistence, and DB cleanup.
  5. For long fixtures above the reduced-context duration gate, assert transcript text equality or a
     tight WER bound so the latency optimization cannot silently truncate tail audio.
- Expected Result: Short and long fixtures persist one complete transcript row; the `0.7s` pause
  persists as one continued row; local Whisper conversion stages are sub-250ms; visible delay is
  dominated by the intentional `0.5s` VAD silence and measured whisper.cpp inference. Reduced
  `audio_ctx=768` applies only to short chunks unless explicitly configured.
- Forbidden Result: silently switching away from `large-v3-turbo`; raw transcript text in latency
  logs; temp-file STT roundtrips; default reduced audio context on long chunks; local TTS prewarm
  competing with active local Whisper STT; claiming UI delay without LiveKit/backend timing evidence.
- Evidence: `qa/modern-playground-voice/reports/2026-05-19-whispercpp-large-v3-turbo-local-optimization.md`
- Last Run: 2026-05-19 PASS for direct benchmarks plus real browser/fake-microphone LiveKit QA.

## MPV-009 Start Chat Is One Click And Mic Auto-Enables

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`
- User Outcome: The user clicks Start chat once, sees startup progress, and arrives in a call with
  the microphone on unless browser permission is denied.
- Surfaces: Modern Playground browser page, LiveKit server, voice gateway, call-session DB.
- Preconditions: local stack running; active synthetic call-session deep link available; browser can
  grant microphone access or the permission-denied state is explicitly recorded.
- Steps:
  1. Open a modern-playground call deep link in a real browser.
  2. Click `Start chat` exactly once.
  3. Confirm the primary button changes to startup progress and is disabled while connection is in
     flight.
  4. Confirm the room connects and the microphone publishes automatically after room connect.
  5. Inspect LiveKit logs for user microphone track publish and `JT_PUBLISHER` worker assignment.
  6. Inspect call-session DB state for active job/worker evidence when a full live call is run.
- Expected Result: The first click owns the whole startup. The UI never requires a second Start chat
  click. The temporary pre-connect muted state is not presented as the call default; after connect,
  the microphone is enabled automatically or a clear microphone permission error is shown.
- Forbidden Result: a second Start chat click is needed; duplicate `/api/connection-details`
  requests race each other; the call lands connected but muted without a permission error; public QA
  artifacts contain real call-session ids, participant ids, local usernames, or secret-bearing URLs.
- Evidence: `qa/modern-playground-voice/reports/2026-05-18-start-chat-single-click-mic-auto-on.md`
- Last Run: 2026-05-18 PASS for real-browser one-click UI state and duplicate-request prevention;
  supporting local runtime logs show the mic-publish path, and fresh full spoken-turn QA remains
  covered by `MPV-001`, `MPV-004`, and `MPV-008`.

## MPV-010 Modern Playground Is Default And Classic Is Opt-In

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`,
  `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`
- User Outcome: A new or upgrading public install receives the modern LiveKit playground by default
  and does not clone, install, start, or pin the old `agents-playground` UI unless classic mode is
  explicitly selected.
- Surfaces: `bootstrap_components.py`, config compiler output, `bin/viventium start`, full-stack
  launcher help/flags.
- Preconditions: public checkout with `components.lock.json`; default or minimal public config.
- Steps:
  1. Run the component-selection release tests for no-config, voice-enabled modern, explicit
     classic, and voice-disabled configs.
  2. Compile a default runtime config and inspect `PLAYGROUND_VARIANT` /
     `VIVENTIUM_PLAYGROUND_VARIANT`.
  3. Inspect launcher flag handling to confirm no supplied playground flag resolves to modern and
     `--classic-playground` is the only old-UI opt-in.
  4. During release review, confirm `components.lock.json` pins only the nested repos intentionally
     shipped in the default runtime path.
- Expected Result: Default and no-config component selection includes `agent-starter-react` and
  excludes `agents-playground`. Voice-disabled selection excludes both playground repos. Explicit
  classic selection includes `agents-playground` and excludes `agent-starter-react`.
- Forbidden Result: old `agents-playground` is selected by default, cloned because config is absent,
  started by the launcher without an explicit classic flag, or pinned into a default release solely
  because a local fallback branch exists.
- Evidence: `tests/release/test_bootstrap_components.py`,
  `tests/release/test_config_compiler.py`,
  `tests/release/test_voice_playground_dispatch_contract.py`
- Last Run: 2026-05-19 automated release case added; targeted run required before release merge.

## MPV-011 Recovered Provider Error Cards Stay Hidden

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`,
  `docs/requirements_and_learnings/01_Key_Principles.md`
- User Outcome: If the primary model provider fails but Viventium later recovers useful visible
  assistant text for the same turn, the linked chat does not keep showing a fatal provider error
  card beside the recovered answer.
- Surfaces: LibreChat browser conversation, Agents stream manager, background-cortex follow-up
  promotion, Mongo message persistence, chat content renderer.
- Preconditions: local runtime running; authenticated QA account; synthetic public-safe conversation
  fixture or real recovered turn with visible answer text plus structured provider error metadata.
- Steps:
  1. Create or locate a recovered assistant message with visible text and a structured recoverable
     provider error class such as `provider_temporarily_unavailable`.
  2. Open the conversation in a real browser through LibreChat.
  3. Confirm the recovered assistant answer is visible.
  4. Confirm no `Something went wrong` provider-error card is visible in the same assistant message.
  5. Refresh the browser and confirm the clean visible state persists.
  6. Inspect DB content parts and recovered error-class metadata.
- Expected Result: The assistant answer remains visible; stale provider error parts are stripped or
  renderer-suppressed; recovered error class remains available in metadata/log evidence.
- Forbidden Result: visible recovered answer and `Something went wrong` provider error card are both
  shown for the same assistant message; cleanup drops the recovered answer; unstructured tool/MCP
  failures are hidden as if they were provider recovery.
- Evidence: `qa/modern-playground-voice/reports/2026-05-21-recovered-provider-error-card-cleanup.md`
- Last Run: 2026-05-21 PASS with local Viventium QA account browser refresh, DB inspection, and
  targeted API/client/voice-gateway tests.

## MPV-012 Streaming TTS Must Not Speak Orphan Punctuation

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`
- User Outcome: A live voice answer sounds conversational even when provider/model streaming splits
  punctuation into separate deltas.
- Surfaces: Modern Playground, Voice Gateway `LibreChatLLM`, LiveKit TTS stream, xAI/Cartesia/OpenAI
  or ElevenLabs TTS routes, transcript display.
- Preconditions: canonical local runtime running from the current checkout; exact TTS debug logging
  enabled only for the private local run; synthetic non-personal prompt that yields short sentences.
- Steps:
  1. Start an authenticated modern-playground call.
  2. Send a synthetic prompt that asks for two short plain sentences.
  3. Listen to the spoken answer and verify it does not say "dot", "period", or other literal
     punctuation names for sentence-ending punctuation.
  4. Inspect sanitized voice gateway logs for exact JSON-escaped TTS deltas and final text.
  5. Verify no TTS-bound chunk is punctuation-only after speech has started.
  6. Repeat or simulate the delta sequence with the unit regression for `[" Good", " to", " hear",
     " you", "."]`, standalone `"."`, and numeric `3` + `.14`.
- Expected Result: TTS receives speakable phrase fragments; orphan punctuation is not pushed as an
  isolated synthesis input; decimal splits remain intact; transcript text remains readable.
- Forbidden Result: the voice says `dot` or `period` for a sentence-ending punctuation chunk; the
  runtime fixes the issue by changing the agent's selected model/provider; public QA artifacts
  include raw private transcripts, call-session ids, or account identifiers.
- Evidence: dated report under `qa/modern-playground-voice/reports/`, targeted
  `tests.test_librechat_llm.TestVoiceTtsDeltaBuffer`, fallback provider-bound logging tests, and
  sanitized voice gateway `[VoiceTTSInput]` lines.
- Last Run: 2026-05-21 PASS. Local Modern Playground call connected through the live voice worker,
  accepted a synthetic text turn, and emitted phrase-sized TTS chunks only; unit and full
  voice-gateway discovery tests passed. 2026-05-22 follow-up PASS for automated provider-input
  boundary tests: no standalone `"."` reaches the fake streaming provider; decimal splits remain
  intact; wired `_LibreChatLLMStream._run` regression proves a standalone period after a flushed
  phrase is not emitted as its own TTS chunk; live stack restarted from the fixed checkout.
  2026-05-22 follow-up added exact provider-bound `[VoiceTTSInput]` instrumentation and automated
  assertions that forwarded and dropped chunks are logged with JSON-escaped text; second-opinion
  edge cases for standalone decimal points and split clause punctuation now pass.

## MPV-013 Streaming TTS Must Not Speak Raw Artifacts

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`
- User Outcome: A live voice answer does not read raw links, emails, source/reference labels,
  markdown/code scaffolding, detached internal citation ids such as `turn0search4`, unknown tags,
  or unsupported provider markup as literal spoken text.
- Surfaces: Modern Playground, Voice Gateway `LibreChatLLM`, LiveKit TTS stream, selected TTS route
  and configured fallback route, transcript display.
- Preconditions: canonical local runtime running from the current checkout; exact TTS debug logging
  enabled only for local QA; synthetic non-personal prompts/fixtures.
- Steps:
  1. Start an authenticated modern-playground call.
  2. Send a synthetic prompt that causes or simulates links, email addresses, source/reference
     labels, markdown links, code fences, split citation markers, detached `turn<N><kind><N>` ids,
     and voice-control tags in streamed model deltas.
  3. Inspect `llm_delta` debug lines to confirm the raw model/debug side may contain artifacts.
  4. Inspect `tts_emit` debug lines and provider request logs when available.
  5. Verify plain-provider/fallback routes strip voice-control tags, while provider-capable routes
     preserve only supported voice controls and still remove generic non-speech scaffolding.
  6. Verify the transcript display remains free of provider markup and the selected model/provider
     was not silently changed to make the test pass.
- Expected Result: TTS-bound chunks contain natural speech or deterministic placeholders such as
  `link available` / `email available`; no punctuation-only chunk, raw URL/domain/email, source
  label, markdown syntax, code fence, detached internal citation id, unknown angle tag, or
  unsupported provider tag reaches TTS.
- Forbidden Result: TTS says raw `dot`, URL/domain fragments, email addresses, `Sources:`, markdown
  syntax, code fence markers, detached `turn0search4`-style ids, or raw tags on a provider that
  does not support them; the fix changes the user's configured provider/model; QA artifacts expose
  private transcript content.
- Evidence: dated report under `qa/modern-playground-voice/reports/`, targeted
  `tests.test_sse.TestSSEParser`, `tests.test_librechat_llm.TestVoiceTtsDeltaBuffer`, affected
  voice-gateway suite, sanitized voice gateway debug scan, and browser QA when live runtime is
  restarted.
- Last Run: 2026-05-21 PASS. Local Modern Playground QA created a call, clicked Start chat, opened
  transcript/chat, sent a synthetic artifact-heavy prompt, observed a visible response, and confirmed
  the aggregate raw stream contained a URL, email address, source label, markdown link, and split
  punctuation while aggregate `tts_emit` and provider-completed TTS input contained zero forbidden
  TTS artifacts. Sanitizer/buffer/fallback/provider route unit coverage also passed. 2026-05-21
  follow-up for detached `turn0search4` artifacts passed automated sanitizer, full voice-gateway,
  TypeScript, and build checks; live browser run reached transcript/provider metrics but exact
  `tts_emit` chunk evidence was partial because opt-in debug chunk logging did not propagate.
  2026-05-22 follow-up PASS for automated missing-space provider-boundary regressions, including a
  wired `_LibreChatLLMStream._run` SSE regression reproducing `clearedis`, `what'syour`,
  `thisthem`, `tryingto`, and `somethingbefore`-style splits without emitting those joins; browser
  QA provider metrics completed but exact debug chunks are still blocked by the same instrumentation
  gap.

## MPV-014 Voice Fixes Need Post-Change User-Grade Proof

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`,
  `qa/README.md#user-grade-qa-bar`, and `AGENTS.md`.
- User Outcome: A user does not receive a claimed voice/TTS fix that was only instrumented or
  inspected. The tested call proves the current running voice runtime actually carries the fix and
  produces the intended audible behavior, or the intended delivered transcript behavior for
  STT/transcription-only fixes.
- Surfaces: Modern Playground, active voice gateway runtime, LiveKit, selected TTS route and
  fallback route when relevant, Mongo or call-session DB/state, generated runtime config, owning
  source code.
- Preconditions: canonical local runtime running from the checkout under test; any debug logging is
  enabled only for local QA; synthetic non-personal prompt/fixture; public QA artifacts redact raw
  call ids, account identifiers, private transcript text, local absolute paths, and secrets.
- Steps:
  1. Prove the active runtime artifact carries the change before the call counts: inspect the source
     checkout, generated config, built artifact when present, and the installed/running process or
     startup log.
  2. Start an authenticated Modern Playground call through a real browser path.
  3. Send or play a synthetic prompt that exercises the changed voice/TTS behavior.
  4. Listen to or otherwise verify the delivered audio outcome. For STT/transcription-only fixes,
     verify the delivered transcript path instead. Record public-safe timestamped evidence of what
     was heard or delivered.
  5. Inspect the visible transcript using synthetic or sanitized text only.
  6. Correlate the turn with exact TTS/provider-input logs, latency/log visibility, DB/state
     persistence, generated config, and owning code.
  7. When interruption/cancel behavior is in scope, interrupt mid-speech and verify the actual
     delivered behavior plus logs/state.
  8. If the audible or delivered path cannot be run, mark the result `BLOCKED` or `PARTIAL` and name
     the missing prerequisite.
- Expected Result: The post-change call proves the intended behavior on the real surface and the
  supporting logs/DB/config/code agree with the visible, audible, or delivered transcript outcome.
- Forbidden Result: accepting "the next call should show it", "instrumentation is ready", source
  inspection, unit tests, logs, DB rows, or a model/Claude review as completion without a
  post-change real user-grade voice/browser run; publishing raw private transcript, call-session id,
  account identifier, local path, or secret-bearing evidence.
- Evidence: dated public-safe report under `qa/modern-playground-voice/reports/` with runtime
  artifact proof, user-path observation, sanitized transcript/audio-delivery note, supporting
  log/DB/config/code correlation, automated checks, and second-opinion summary when available.
- Last Run: 2026-05-22 PASS for local Whisper interruption fix. The run proved the active runtime
  policy, Modern Playground browser path, fake-mic barge-in behavior, voice gateway state logs, and
  cleanup/DB evidence; see `reports/2026-05-22-local-whisper-bargein-qa.md`.

## MPV-015 Local Whisper Mid-Speech Barge-In

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`
- User Outcome: During a Modern Playground call using local Whisper STT, the user can interrupt the
  assistant while it is speaking without waiting for Whisper to produce a final transcript.
- Surfaces: Modern Playground, local voice gateway worker, LiveKit turn handling, generated runtime
  config, call-session DB/state.
- Preconditions: canonical local runtime running from the checkout under test; active STT route is
  `whisper_local` or `pywhispercpp`; synthetic non-personal prompt that produces a long spoken
  assistant reply.
- Steps:
  1. Prove the active worker runtime is from the checkout under test and logs
     `min_interrupt_words=0` for the local Whisper call.
  2. Start a Modern Playground call in a real browser.
  3. Prompt the assistant to speak for long enough to interrupt naturally.
  4. During the first reply, attempt one early barge-in shortly after the first second of audible
     speech to prove the local Whisper AEC default is not a multi-second block.
  5. During a later long reply, say a sustained short phrase such as `stop` or `wait` while the
     assistant is audibly speaking.
  6. Confirm the assistant pauses or stops promptly and the new user turn is captured.
  7. Inspect logs for the effective policy, user/agent state transitions, false-interruption or
     overlap evidence when emitted, and sanitized call-session route metadata.
  8. Verify an AssemblyAI/default route test or unit assertion still keeps provider STT
     `min_interrupt_words=1`.
- Expected Result: Local Whisper barge-in works from sustained audio activity; the gateway does not
  require an interim transcript word before interrupting; normal response start latency is not
  increased; effective local policy logs `min_interrupt_words=0` and `aec_warmup_duration=1.0`;
  `sync_transcription` remains unchanged.
- Forbidden Result: the assistant keeps speaking until local Whisper finalizes the user audio; the
  fix changes the selected STT/TTS/model route; endpointing delays are increased to hide the issue;
  public QA artifacts include raw private transcripts, call ids, account identifiers, local paths,
  or secrets.
- Evidence: dated public-safe report under `qa/modern-playground-voice/reports/`, targeted
  turn-handling tests, generated config proof, runtime logs, browser/user-path observation, and DB
  route metadata.
- Last Run: 2026-05-22 PASS. Real Modern Playground browser QA with a synthetic fake microphone WAV
  observed effective local policy `min_interrupt_words=0` and `aec_warmup_duration=1.0`, then saw
  `agent_speaking`, `user_speaking`, and `agent_paused` in the voice gateway state sequence with no
  browser console errors; see `reports/2026-05-22-local-whisper-bargein-qa.md`.

## Release Test Traceability

- `tests/release/test_voice_playground_dispatch_contract.py`
