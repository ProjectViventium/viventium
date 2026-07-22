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
| `MPV-UC-007` | Click Start chat once and wait for the call to connect. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `MPV-009` | Modern Playground browser page, LiveKit, voice gateway logs | Button state, browser console/network, LiveKit microphone publish, publisher job assignment, call-session DB state | One click starts the call, duplicate clicks are disabled, and the microphone turns on after room connect. | 2026-05-18 PASS for one-click visible UI and duplicate-request prevention; full fresh spoken-turn remains under broader call cases |
| `MPV-UC-008` | Install or bootstrap with the default voice-capable configuration. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `MPV-010` | Installer/bootstrap component selection and launcher help | Component selector, compiled runtime env, exact `/api/health` identity, launcher flags | Default selection includes `agent-starter-react` and excludes `agents-playground`; classic UI appears only after explicit classic selection; stale or wrong listeners are rejected. | PASS 2026-07-21: exact identity verifier and real browser show the modern Viventium UI; wrong variant and stale source refs are rejected; final installed-artifact rerun remains a release gate |
| `MPV-UC-011` | Reload a linked chat after provider overload was recovered by visible assistant text. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `MPV-011` | LibreChat browser conversation | DB content parts, recovered error-class metadata, renderer tests, runtime logs | Recovered answer is visible, stale provider error card is not visible, refresh keeps the clean state. | 2026-05-21 PASS in `reports/2026-05-21-recovered-provider-error-card-cleanup.md` |
| `MPV-UC-012` | Hear a streamed voice answer whose model deltas split punctuation from the phrase. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `MPV-012` | Modern Playground call with xAI/Cartesia/fallback TTS as available | Voice gateway exact TTS debug logs, transcript, provider metrics, buffer unit tests | The assistant speaks naturally, never says a standalone period as "dot", and preserves delayed question/exclamation prosody; transcript remains readable. | 2026-05-25 PASS automated regression; live audible rerun pending after runtime restart |
| `MPV-UC-013` | Hear a streamed voice answer when model text contains links, emails, references, markdown, or provider markup. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `MPV-013` | Modern Playground call with current TTS route and fallback route | Voice gateway `llm_delta`, `tts_emit`, `[VoiceRendering][voice_gateway]`, provider request logs when available, sanitizer/unit tests | TTS receives speech-safe phrase chunks; plain providers do not receive raw tags; provider-supported controls are preserved only on capable routes. | PARTIAL 2026-07-15: prior live browser/artifact path passed; metadata-only provider/fallback rendering regression passes, but a post-change audible provider-matrix run remains required |
| `MPV-UC-014` | Verify a voice/TTS fix after adding logs or instrumentation. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `MPV-014` | Modern Playground call, active voice runtime, logs, DB/state | Runtime artifact proof, audible/delivered voice evidence, sanitized transcript evidence, exact TTS/provider-input logs, DB/state, owning code | The changed runtime is proven active and the post-change call demonstrates the intended audible behavior; instrumentation alone is not accepted. | 2026-05-22 PASS for local Whisper barge-in runtime/browser/log proof |
| `MPV-UC-015` | Interrupt a local Whisper assistant reply while it is speaking. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `MPV-015` | Modern Playground call with local `pywhispercpp` STT | Visible transcript, audible behavior, voice gateway interruption policy/state logs, generated runtime config, DB call-session route | A sustained one-word or short-phrase barge-in pauses/interrupts the agent without waiting for final local Whisper text; AssemblyAI word-guard defaults remain unchanged. | 2026-05-22 PASS in `reports/2026-05-22-local-whisper-bargein-qa.md` |
| `MPV-UC-016` | Open the Listening picker, select `AssemblyAI` → `Universal-3 Pro streaming (u3-rt-pro)`, then start a call and speak. | `docs/requirements_and_learnings/06_Voice_Calls.md` (AssemblyAI Streaming Engine Selection) / `MPV-017` | Modern Playground browser, voice gateway worker, LiveKit, `ASSEMBLYAI_API_KEY` configured | Listening dropdown options, voice gateway `connecting to AssemblyAI model=...` log, `/capabilities` payload, transcript, worker STT-selection tests | `Universal-3 Pro streaming (u3-rt-pro)` is selectable, the call connects, and the worker runs the selected `u3-rt-pro` engine with a real STT transcript. | 2026-05-29 PARTIAL: automated plumbing PASS + live `/capabilities` shows `u3-rt-pro` `available=True` + real-browser confirm that the picker lists and applies `Universal-3 Pro streaming (u3-rt-pro)`; only the audible-call transcript remains |
| `MPV-UC-017` | Receive a streamed answer whose server emits growing text snapshots instead of pure incremental token deltas. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `MPV-018` | Modern Playground browser, voice gateway stream, LibreChat voice route, Mongo/chat reload | Gateway chunks, visible transcript, persisted assistant text/content parts, follow-up decision metadata | The assistant text appears once, `{NTA}` remains silent, and the linked LibreChat chat reload never shows malformed control tags or adjacent duplicate words. | 2026-05-30 PARTIAL PASS in `reports/2026-05-30-cumulative-delta-snapshot-rca.md`; artifact fixed and linked chat cleaned on read, but healthy primary-provider stream rerun blocked by local provider failures |
| `MPV-UC-021` | In a real call, ask the agent to launch a synthetic GlassHive browser task, then speak a terse status/wait request and a deferred artifact request. | `docs/requirements_and_learnings/06_Voice_Calls.md`, `docs/requirements_and_learnings/07_MCPs.md` / `MPV-021`, `AGCFG-005`, `MPV-014` | Authenticated Modern Playground call and linked LibreChat conversation | audible audio, transcript, provider-bound tools, scoped `tool_search`, Mongo tool-call parts, GlassHive run/events, runtime logs, linked-chat reload | Voice uses the same eager launch/status/wait gateway as web and Telegram, discovers deferred artifacts in the same invocation, and speaks a truthful result without a false unavailable claim. | PASS 2026-07-13: real launch/wait/file creation plus a real deferred-discovery call that invoked scoped `tool_search` and `workspace_artifacts` in the same turn; transcript, persistence, and nonzero audio passed |
| `MPV-UC-022` | Ask the configured voice model to recall a prior browser event while conversation recall and transcript fixtures are both available. | `docs/requirements_and_learnings/32_Conversation_Recall_RAG.md`, `docs/requirements_and_learnings/34_Voice_Chat_LLM_Override.md` / `MPV-022`, `MPV-014` | isolated browser, Modern Playground, linked LibreChat conversation | audible audio, expanded file-search sources, provider/controller logs, fixture DB/search state, runtime config | Voice answers from the strongest prior-chat evidence, does not cite the active prompt or blend an unrelated transcript, persists after reload, and does not crash in final-run telemetry. | PASS-AUTOMATED/PARTIAL 2026-07-14; focused ranking/controller fixtures pass, but isolated-account audible/persistence acceptance is NOT RUN |
| `MPV-UC-023` | Open a public call from outside a synthetic lab LAN and speak. | `docs/requirements_and_learnings/47_Remote_Access_and_Tunneling.md` / `MPV-023`, `MPV-014`, `REMOTE-004` | Public Playground browser, LiveKit lab media, voice worker | selected ICE pair, generated/runtime node address, LiveKit/worker logs, fixture transcript row, cleanup | The browser selects a public media path, the worker receives audio, and the expected transcript is delivered; a loaded page alone is not accepted. | NOT RUN for this public candidate; requires an isolated lab edge/router and synthetic account |
| `MPV-UC-024` | Upgrade or start with the unsupported legacy xAI `voice_agent` TTS compatibility value configured. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `MPV-024` | Config compiler and voice-gateway startup | Compiler/runtime error, capability contract, source inventory, standalone xAI provider tests | Startup fails closed with an actionable migration to `tts`; it explains that Voice Agent is a separate conversational API and never silently remaps the setting. | PASS automated 2026-07-15; wording corrected against current xAI documentation 2026-07-20; post-change installed-runtime restart intentionally not run in this source-only slice |
| `MPV-UC-025` | Enable Docker-backed Voice after install, then upgrade from an older Viventium-managed LiveKit container. | `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md` / `MPV-025` | Full-stack launcher and Docker LiveKit runtime | Optional runtime lock, container image/source labels, health, TURN config, Docker disk usage | Exact multi-arch digest starts; an exact managed container is reused; a stale managed container is replaced; unrelated/external LiveKit is not deleted. | PARTIAL 2026-07-21: real arm64 Docker pull/start/health/restart, stale replacement, external preservation, and cleanup pass; Intel, TURN selected-pair, and microphone/TCC remain |
| `MPV-UC-026` | Open the Modern Playground URL directly without first opening Voice from a conversation. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `MPV-027` | Modern Playground browser with no call-session parameters or standalone agent | Visible CTA/help text, console, network requests, exact `/api/health` identity | The start action stays disabled and immediately explains that Voice must be opened from a Viventium conversation; the page does not contact personal/provider state. | PASS 2026-07-21: isolated headed Chromium showed the recovery guidance, exact modern identity, zero console warnings/errors, and no non-loopback/backend requests. |
| `MPV-UC-028` | Open the Modern Playground directly using keyboard navigation, a narrow viewport, forced colors, and Reduce Motion. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `MPV-028` | Modern Playground direct-entry browser page | `qa/modern-playground-voice/scripts/direct-entry-accessibility-browser-qa.cjs`; named focus order, viewport bounds/overflow, computed motion durations, console/network, exact source identity | Recovery guidance and controls remain perceivable and keyboard-operable; tall content scrolls downward without clipping; Reduce Motion removes retained animation/transition durations; requests stay loopback-only. | PASS 2026-07-22 against exact reviewed head: headed Chromium passed ten named keyboard stops, `320 x 760` reflow, forced colors, zero horizontal overflow, zero retained motion durations, and first-graphic `y=40`. VoiceOver, real call/audio, and exact signed installed artifact remain separate blocked rows. |

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
  real answer. The typed input cannot be submitted until the agent participant is available; pressing
  Enter obeys the same availability guard as the disabled Send button. Forbidden result:
  `Session ended / Agent left the room unexpectedly`, or a browser/harness action marking
  `promptSent=true` without a corresponding voice worker/chat route hit.
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
  inside the same ingress window. If the Phase B adjudicator resolves to `{NTA}`, empty, skipped, or
  otherwise terminal-silent, the persisted follow-up decision is visible to the voice poller and the
  poller exits early instead of waiting the whole follow-up window.
- Forbidden Result: the second user turn appears only in the playground transcript but not in Mongo;
  the voice gateway speaks a generic service error; a stale first-turn follow-up is generated with
  moved-on state missing; a later turn subscribes to or completes an older turn's stream.
- Evidence: `qa/modern-playground-voice/reports/2026-05-15-livekit-parity-latency-followup-qa.md`
- Last Run: 2026-05-30 PARTIAL. Automated voice follow-up scheduler regression passed and a real
  fake-microphone LiveKit run proved the active playground/worker path. A fresh spoken multi-turn
  Phase B overlap run is still needed for the full MPV-003 stress case.

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
  5. Inspect LiveKit logs for user microphone track publish and publisher worker assignment.
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
  launcher help/flags, legacy `viventium-start-all.sh` compatibility entrypoint.
- Preconditions: public checkout with `components.lock.json`; default or minimal public config.
- Steps:
  1. Run the component-selection release tests for no-config, voice-enabled modern, explicit
     classic, and voice-disabled configs.
  2. Compile a default runtime config and inspect `PLAYGROUND_VARIANT` /
     `VIVENTIUM_PLAYGROUND_VARIANT`.
  3. Inspect launcher flag handling to confirm no supplied playground flag resolves to modern and
     `--classic-playground` is the only old-UI opt-in.
  4. Start the modern candidate with its exact 40-character source ref, verify `/api/health`, then
     prove that a classic identity and a stale modern source ref are both rejected.
  5. During release review, confirm `components.lock.json` identifies the reviewed modern commit and
     that default component selection does not fetch the separately inventoried classic fallback.
  6. Execute the legacy launcher's safe argument mapping against a synthetic canonical launcher and
     prove that no arguments selects modern, `--no-playground` maps to `--skip-playground`, and the
     old dependency/build mutation flags fail before delegation.
- Expected Result: Default and no-config component selection includes `agent-starter-react` and
  excludes `agents-playground`. Voice-disabled selection excludes both playground repos. Explicit
  classic selection includes `agents-playground` and excludes `agent-starter-react`. The legacy
  wrapper owns no LiveKit image, package installation, environment mutation, broad process cleanup,
  or alternative runtime logic.
- Forbidden Result: old `agents-playground` is selected by default, cloned because config is absent,
  or started by the launcher without an explicit classic flag. Merely inventorying its reviewed
  fallback commit in the complete component lock must not activate or fetch it. A legacy command
  must not run a floating `livekit/livekit-server`, install `livekit-server-sdk`, or append secrets
  to a tracked-checkout `.env` file.
- Evidence: `tests/release/test_bootstrap_components.py`,
  `tests/release/test_config_compiler.py`,
  `tests/release/test_voice_playground_dispatch_contract.py`,
  `tests/release/test_optional_runtime_provenance.py`
- Last Run: PASS 2026-07-21. A clean modern candidate served an exact source-bound identity; the
  verifier rejected classic and stale-source identities. Real Chromium showed `Viventium Voice
  Assistant`, the Viventium home view, and expanded Listening providers after refresh. Focused
  identity, selector, compiler, CLI, and legacy-wrapper tests passed. The compatibility wrapper now
  delegates to the canonical locked runtime and rejects mutation-only options. See
  `reports/2026-07-21-modern-playground-default-release-regression.md`. Final installed-artifact
  identity remains part of the release-wide alignment gate.

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
  punctuation into separate deltas, including delayed question/exclamation marks after a whitespace
  boundary.
- Surfaces: Modern Playground, Voice Gateway `LibreChatLLM`, LiveKit TTS stream, xAI/Cartesia/OpenAI
  or ElevenLabs TTS routes, transcript display.
- Preconditions: canonical local runtime running from the current checkout; exact TTS debug logging
  enabled only for the private local run; synthetic non-personal prompt that yields short sentences.
- Steps:
  1. Start an authenticated modern-playground call.
  2. Send a synthetic prompt that asks for two short plain sentences.
  3. Listen to the spoken answer and verify it does not say "dot", "period", or other literal
     punctuation names for sentence-ending punctuation, and that short questions still sound like
     questions when the displayed transcript ends in `?`.
  4. Inspect sanitized voice gateway logs for exact JSON-escaped TTS deltas and final text.
  5. Verify no TTS-bound chunk is punctuation-only after speech has started.
  6. Repeat or simulate the delta sequence with the unit regression for `[" Good", " to", " hear",
     " you", "."]`, standalone `"."`, delayed `["Good morning. Sleep okay ", "?"]`, delayed
     exclamation, a long single-sentence delayed question, quote-wrapped delayed `?”`, numeric `3`
     + `.14`, and whitespace/max-length phrase splits that should keep the trailing word buffered
     instead of relying on provider-leading whitespace.
- Expected Result: TTS receives speakable phrase fragments; orphan periods are not pushed as isolated
  synthesis input; delayed `?`/`!` remain attached to their phrase; decimal splits remain intact;
  transcript text remains readable.
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
  edge cases for standalone decimal points and split clause punctuation now pass. 2026-05-25
  automated follow-up PASS: delayed `?`/`!` after whitespace no longer become orphan punctuation,
  while standalone-period and decimal regressions still pass. 2026-05-25 second automated follow-up
  PASS: whitespace and length-driven flushing now split at safe whitespace and keep the trailing
  word buffered; long single-sentence delayed questions, delayed quote-wrapped questions, and split
  `[laughter]` markers are covered by regression tests; live audible rerun remains required before
  release-ready closure.

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
  4. Inspect `tts_emit` debug lines and provider request logs when available; correlate the turn with
     metadata-only `[VoiceRendering][voice_gateway]` attempt/input/selection events.
  5. Verify plain-provider/fallback routes strip voice-control tags, while provider-capable routes
     preserve only supported voice controls and still remove generic non-speech scaffolding. The
     metadata event must identify primary versus fallback and `preserved` versus `stripped` without
     containing the synthetic transcript.
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
  gap. 2026-07-15 automated provider-boundary regressions additionally prove metadata-only
  attempt/input/selection events for preserved expressive controls and stripped plain-provider
  fallback controls; a runtime reload plus post-change audible provider-matrix call is still open.

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

## MPV-016 Streaming TTS Must Preserve Inter-Word Spacing (xAI)

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md` (xAI Standalone TTS Contract).
- User Outcome: On an xAI standalone voice call, the spoken audio keeps normal word spacing; the
  assistant says "Hello there, how are you?" — not a glued "Hellothere,howareyou?" — while the chat
  transcript already reads correctly.
- Surfaces: Modern Playground, Voice Gateway `LibreChatLLM` deltas, `FallbackTTS` boundary
  normalizer, `livekit-plugins-xai` streaming TTS (`wss://api.x.ai/v1/tts`), transcript display.
- Preconditions: canonical local runtime from the checkout under test; active Speaking route is xAI
  standalone (`VIVENTIUM_XAI_TTS_API` unset/`tts`); synthetic non-personal multi-sentence prompt;
  exact TTS-input debug logging enabled only for local QA.
- Steps:
  1. Confirm the active worker constructs the xAI plugin with a `retain_format=True` word tokenizer
     (`worker._build_xai_tts_word_tokenizer`).
  2. Start an authenticated Modern Playground call on the xAI route and send a multi-sentence prompt.
  3. Compare the visible transcript spacing against the audible speech (and, when available, the
     `[VoiceTTSInput]`/provider request text reconstructed from the `text.delta` frames).
  4. Verify the model/provider route was not silently changed to make the test pass.
- Expected Result: The text reconstructed from the xAI `text.delta` frames equals the transcript
  spacing; no inter-word spaces are dropped; first delta of each segment has no spurious leading
  space.
- Forbidden Result: words glue together in the spoken audio while the transcript looks fine;
  whitespace is "fixed" by mangling `sse.py`/`fallback_tts.py` sanitizers (which already preserve
  spacing); the fix flips the selected provider/model; QA artifacts expose private transcript
  content or session/call ids.
- Evidence: `viventium_v0_4/voice-gateway/tests/test_xai_standalone_tts.py`
  (`test_injected_tokenizer_preserves_word_spacing_for_xai_deltas`,
  `test_default_plugin_tokenizer_would_drop_spacing`,
  `test_xai_tts_constructed_with_space_preserving_tokenizer`), plus a dated public-safe report and
  browser/audio observation when the live runtime is restarted.
- Last Run: 2026-05-30 PASS. (1) Deterministic reproduction against the pinned
  `livekit-plugins-xai` `WordTokenizer` and the real `_VoiceTtsDeltaBuffer` +
  `_ProviderTextBoundaryNormalizer` chain: default `retain_format=False` produced
  `"Hellothere,Icheckedyourinvoiceanditcleared.What'snext?"` while the injected `retain_format=True`
  tokenizer produced the transcript-matching `"Hello there, I checked your invoice and it cleared.
  What's next?"`. New regression tests pass; full voice-gateway suite (316 tests) green. (2) Live
  user-path proof: the voice gateway worker was restarted on this branch (fixed `worker.py`,
  registered as `librechat-voice-gateway`) with opt-in `text.delta` debug logging; a real
  authenticated LibreChat call (same `roomName/callSessionId/agentName/autoConnect` URL shape as the
  reported bug) on the `xAI - Eve` standalone route returned a spoken multi-sentence answer. The
  logged per-word `text.delta` payloads sent to `wss://api.x.ai/v1/tts` carried a leading space on
  every continuation token (first token none), reassembling to the transcript-matching
  `"I'm Viventium, your second brain and force multiplier ... keeping momentum without fluff"`;
  provider metrics `label=livekit.plugins.xai.tts.TTS characters=134`. Audio waveform animated and
  the visible transcript matched. Audible spacing verified via the exact websocket payload + active
  TTS playback (not human listening). Debug logging was then turned off and the worker relaunched
  clean. Residual (pre-existing, not this fix): orphan sentence-terminal `.` is dropped before xAI
  per `MPV-012`.

## MPV-017 AssemblyAI Universal-3 Pro Streaming Engine Selection

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md` (AssemblyAI Streaming Engine
  Selection).
- User Outcome: In the Modern Playground "Listening" picker the user can choose
  `AssemblyAI` → `Universal-3 Pro streaming (u3-rt-pro)`, start a call, and the call runs on the
  selected `u3-rt-pro` engine that was proven in R&D — not a silent plugin default.
- Surfaces: Modern Playground `voice-route-control` Listening selector, `useVoiceRoute` fallback
  capabilities, voice gateway capability catalog + `_apply_requested_voice_route` +
  `build_stt_selection`, `livekit-plugins-assemblyai` `STT(model=...)`, LiveKit transcript.
- Preconditions: canonical local runtime from the checkout under test; `ASSEMBLYAI_API_KEY`
  configured so AssemblyAI is `available`; synthetic non-personal prompt.
- Steps:
  1. Confirm the active worker advertises the AssemblyAI engine variants in `/capabilities`
     (`u3-rt-pro` first, then `universal-streaming-english`, `universal-streaming-multilingual`;
     legacy `universal-streaming` absent).
  2. Open the Listening picker in a real browser; confirm `AssemblyAI` lists
     `Universal-3 Pro streaming (u3-rt-pro)` and select it.
  3. Start a call and speak (or play a synthetic fake-microphone WAV).
  4. Confirm the voice gateway logs `connecting to AssemblyAI model=u3-rt-pro` (or the selected
     engine when a different one is chosen) and a real STT transcript appears.
  5. Switch to `Universal Streaming (Multilingual)` and confirm the worker applies the newly
     selected engine on the next call rather than ignoring it.
- Expected Result: The picker selection is carried end-to-end; the worker constructs
  `assemblyai.STT` with the selected `model`; the default with no override is `u3-rt-pro`; an
  unknown engine normalizes back to `u3-rt-pro` instead of failing the call.
- Forbidden Result: the picker shows an engine that the runtime never applies (cosmetic variant);
  the catalog advertises a non-plugin id such as `universal-streaming`; selecting an engine has no
  effect on the actual AssemblyAI model; QA artifacts leak private transcript content, call ids,
  account identifiers, local paths, or secrets.
- Evidence: `viventium_v0_4/voice-gateway/tests/test_worker_stt_assemblyai.py`
  (`test_build_stt_selection_passes_model_to_plugin`,
  `test_apply_requested_route_applies_selected_variant`,
  `test_catalog_lists_u3_rt_pro_and_drops_legacy_id`,
  `test_default_model_is_u3_rt_pro`), `tests/release/test_config_compiler.py`
  (`VIVENTIUM_ASSEMBLYAI_STT_MODEL` default + override assertions),
  `tests/release/test_voice_playground_dispatch_contract.py`, plus a dated public-safe report and
  live browser/audio observation when the gateway is restarted on this branch.
- Last Run: 2026-05-29 PARTIAL. Automated end-to-end plumbing proven:
  `build_stt_selection(...).model == "u3-rt-pro"`, the requested AssemblyAI variant is applied (was
  previously dropped), the catalog drops the invalid `universal-streaming` id, the compiler emits the
  `VIVENTIUM_ASSEMBLYAI_STT_MODEL` default/override, and the full voice-gateway suite (329 tests) plus
  the touched release suites are green. Live runtime confirmed: the running Viventium voice gateway
  (health port 8301, started after the edit) serves `GET /capabilities` with the AssemblyAI engine
  `available=True` and `variants=['u3-rt-pro', 'universal-streaming-english',
  'universal-streaming-multilingual']` — the exact feed the picker reads. Visible browser confirmed:
  in the real playground the Listening → AssemblyAI submenu lists `Universal-3 Pro streaming
  (u3-rt-pro)` and selecting it updates the Listening row (badge flips COVERED→METERED); reverted to
  the prior local route afterward. Remaining: an audible `model=u3-rt-pro` call transcript; see
  `reports/2026-05-29-assemblyai-u3-rt-pro-listening-engine.md`.

## MPV-018 Cumulative Voice Stream Snapshots Must Not Duplicate Text

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md` (Live Response Streaming).
- User Outcome: When a provider or LibreChat stream sends a growing assistant message snapshot
  through the delta event shape, the live voice call speaks and displays the final sentence once,
  and the linked LibreChat conversation persists the same clean text.
- Surfaces: Voice Gateway `LibreChatLLM` stream, LibreChat voice route message-delta boundary,
  resumable generation replay, content aggregation, Modern Playground transcript, linked LibreChat
  conversation, Mongo messages.
- Preconditions: canonical local runtime running from the checkout under test; synthetic
  non-personal prompt that elicits a short answer; debug logs may be enabled locally but public
  artifacts must use sanitized hashes/text.
- Steps:
  1. Run the unit regressions that simulate cumulative `on_message_delta` snapshots for normal text,
     quoted repeated text, `{NTA}`, mid-word snapshots such as `Hel` -> `Hello`, resumable replay,
     and legitimate repeated incremental text such as `ha` followed by `haha`.
  2. Restart the active voice runtime from the patched checkout.
  3. Start an authenticated Modern Playground call in a real browser and send a synthetic prompt only
     after the Send control becomes enabled by an available agent participant.
  4. Inspect the visible transcript and linked LibreChat chat after reload.
  5. Inspect Mongo assistant rows for the call and the voice gateway/LibreChat logs for the same
     turn.
- Expected Result: Growing snapshots are normalized to missing suffixes before SSE/resumable
  fan-out, replay, content aggregation, speech/display/save, and recent-response context. The final
  assistant answer has no adjacent duplicate words such as `Tell Tell`, no malformed no-response
  text such as `{N{NTATA}}`, and a terminal `{NTA}` follow-up remains silent. Meaningful repetition
  inside quote-wrapped text, markdown blockquotes, inline code, fenced code, or true incremental
  output such as `ha` + `haha` remains unchanged and does not trigger duplicate-artifact QA failure.
  Mid-word cumulative snapshots reconstruct the intended word once.
- Forbidden Result: any internal no-response marker is spoken, displayed, or persisted; cumulative
  snapshots are appended verbatim and create duplicated text; a cleanup step repairs only the final
  persisted message after raw bad chunks already reached browser/TTS/replay; old persisted corrupted
  messages are treated as proof that the runtime fix failed instead of being handled by an explicit
  data-repair decision; the QA harness reports a transcript/artifact result without proving the
  worker route was actually exercised.
- Evidence: dated public-safe report under `qa/modern-playground-voice/reports/`, gateway and
  LibreChat regression tests, real-browser run, sanitized DB/log correlation, and any data-repair
  recommendation kept separate from the product-code fix.
- Last Run: 2026-05-31 PASS for artifact behavior, Redis replay still BLOCKED in
  `reports/2026-05-31-boundary-delta-normalizer-root-fix.md`. The root-path fix moved cumulative
  snapshot normalization to the LibreChat message-delta boundary before SSE/resumable fan-out,
  aggregation, TTS/display, and persistence; the stale downstream duplicate-repair helper and
  gateway-side duplicate normalizer were removed so the boundary remains the owner. The artifact
  condition inventory now lives in product code at
  `viventium_v0_4/LibreChat/api/server/services/viventium/voiceArtifactText.js`, with QA importing
  it through `scripts/voice_artifact_contract.cjs`. ClaudeViv's follow-up gap on inline markdown
  emphasis/decorative markers was added to that contract plus the voice TTS sanitizer, and live QA
  then exposed the first-save owner: `BaseClient.saveMessageToDatabase` saved voice assistant rows
  before request-controller normalization. That first-save path now uses the same product sanitizer.
  A later ClaudeViv review caught non-voice content-to-text parity, Python sanitizer drift, and
  dot-heavy technical-token risks; non-voice parity was restored, and LiveKit/Telegram TTS tests now
  load the shared JavaScript artifact contract for sanitizer-owned classes while preserving `.NET`,
  `asp.net`, `node.js`, and version-like tokens.
  The active runtime was restarted from the checkout under test; Chrome plus the automated browser
  harness exercised the call path with the expected cleaned assistant response and zero
  page/persisted artifact counts. Redis replay infrastructure remains unavailable, so replay-specific
  acceptance is still BLOCKED.
  Earlier context:
  2026-05-30 PARTIAL PASS in
  `reports/2026-05-30-cumulative-delta-snapshot-rca.md`. Regression/unit checks passed, local prod
  was restarted from the patched checkout, the reported linked chat no longer renders the malformed
  marker or duplicate-word artifacts, and the Modern Playground harness proved a real call route with
  clean visible/persisted/log artifacts. Claude review flagged a missing write-path duplicate case;
  that regression was added and passed. 2026-05-31 quote-aware regression pass added protected-span
  coverage for quoted, blockquoted, and code-formatted repeated words in
  `reports/2026-05-31-quoted-text-artifact-coverage.md`. Full PASS is still blocked until a healthy
  primary model provider streams a normal assistant answer through this path after the local provider
  failures are resolved.

## MPV-019 GPT-5.6 Primary Must Not Rewrite the xAI Voice Transport

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md` (Voice Call LLM Ownership
  Contract).
- User Outcome: An agent can use GPT-5.6 through OpenAI Responses for text chat while its dedicated
  live-call model remains Grok 4.3 on the configured low-latency xAI voice route.
- Surfaces: Agent Builder primary and Voice Chat Model profiles, LibreChat voice model override,
  Agents graph initialization, Modern Playground transcript/audio, xAI LLM and TTS providers.
- Preconditions: authenticated Viventium QA account; primary route `openAI/gpt-5.6-sol` with
  `useResponsesApi=true`; voice route `xai/grok-4.3` with `reasoning_effort=none`; synthetic
  non-personal prompt.
- Steps:
  1. Confirm the primary and voice-specific source-of-truth profiles retain their configured models.
  2. Run the voice-override regression with an OpenAI GPT-5.6 primary parameter bag and an xAI Grok
     4.3 voice parameter bag.
  3. Confirm inherited `useResponsesApi` and primary `reasoning` are absent from the resolved voice
     request, while an explicit voice-level xAI Responses selection remains supported.
  4. Mount the optional voice panel while its watched provider is temporarily empty, then hydrate
     the persisted xAI provider/model/parameter bag as an agent switch or async form reset would.
  5. Reload the active LibreChat API from the patched checkout.
  6. Start an authenticated Modern Playground call in real Chrome, open the transcript, and send a
     short synthetic typed voice turn.
  7. Confirm visible assistant text, delivered browser audio, xAI TTS metrics, token-bearing LLM
     stream completion, and persisted assistant text. Compare the result with the escaped failure's
     no-token timeout.
- Expected Result: Grok 4.3 produces visible text and xAI audio without a provider error; the voice
  override logs or regression evidence show Chat Completions provenance (`useResponsesApi` unset)
  unless the voice profile explicitly opted into xAI Responses.
- Forbidden Result: the GPT-5.6 primary's Responses setting silently changes the xAI voice request;
  transient empty-to-value hydration clears the persisted voice parameter bag or appears unset;
  the call waits for the provider timeout with zero token events; the fix changes Grok 4.3 or xAI
  Eve to a different configured route; public evidence exposes credentials, account identifiers,
  raw call ids, or local paths.
- Evidence: `viventium_v0_4/LibreChat/api/server/services/viventium/__tests__/voiceLlmOverride.spec.js`
  and `qa/modern-playground-voice/reports/2026-07-09-grok-4-3-voice-transport-provenance.md`.
- Last Run: 2026-07-09 PASS. The escaped turn ended after 101.040 seconds with no token events. The
  post-fix real Chrome turn emitted its first token at 7.335 seconds, completed the stream at 7.735
  seconds with token events, displayed the requested synthetic sentence, and delivered 1.61 seconds
  of unmuted xAI audio. Focused voice-override tests passed 13/13; adjacent provider suites,
  packages API checks, and the full voice gateway also passed. Claude Opus 4.8 found no must-fix
  issue in the parameter-provenance design. Reconfirmed 2026-07-14 after an escaped Agent Builder
  provider-switch regression: switching OpenAI Responses to xAI now clears the OpenAI parameter
  bag, live/source config remains `xai/grok-4.3` plus the OpenAI Terra voice fallback, and the fresh
  real-Chrome call reached xAI Chat Completions with `reasoning_effort=none`, no Responses flag,
  HTTP 200, visible persisted text, and non-cancelled xAI audio. ClaudeViv then identified the
  mounted empty-to-value hydration edge; the guard now preserves that restored parameter bag. Its
  final review also prompted a reachable agent-switch check: optional route panels are now keyed to
  the form agent id, so switching agents while the panel remains open cannot reuse the previous
  agent's provider history. In the real signed-in browser, a second agent received an unsaved OpenAI
  selection while the panel remained open; returning to the original agent and reloading preserved
  xAI/Grok/None with Responses disabled and the OpenAI Terra fallback. Mongo showed the original
  route unchanged and the second agent still unset. The focused component/helper suites pass 17/17.
  A final max-effort ClaudeViv review confirmed all five post-delta claims and found no must-fix
  defect in the agent-scoped lifecycle boundary.

## MPV-020 Cross-Conversation Memory And Recall From Telegram

- Requirement: `20_Memory_System.md` ordered saved memory and
  `32_Conversation_Recall_RAG.md` hybrid recall; reuse the audible acceptance gate in `MPV-014`.
- Preconditions: dedicated isolated browser and channel QA accounts; synthetic durable marker and
  separate natural-event marker; fixture state captured for cleanup.
- Steps:
  1. Send both synthetic turns in Telegram and prove the durable marker advances a memory revision
     while the natural event is absent from saved memory but present in recall-eligible history.
  2. Start a new Modern Playground call, open Transcript, and ask naturally about each marker.
  3. Confirm visible transcript, audible delivered answer, `file_search` evidence for the recall
     lane, saved-memory prompt-frame evidence for the durable lane, persistence after reload, and
     aligned DB/log/runtime config.
  4. Restore/delete all synthetic state through supported paths and confirm cleanup.
- Expected Result: both answers are correct and natural; saved memory and recall have distinct
  evidence; audio and transcript agree.
- Forbidden Result: typed-only API proof, fake browser/audio, same-conversation history, a model
  guess without retrieval evidence, or synthetic state left behind.
- Last Run: PASS-AUTOMATED/PARTIAL 2026-07-14. Synthetic writer, retrieval, prompt-frame,
  persistence, and cleanup regressions pass. The dedicated isolated channel-to-browser-to-audible-
  voice journey is NOT RUN and no personal profile/channel history is public evidence.

## MPV-021 Spoken GlassHive Gateway And Deferred Discovery

- Requirement: `06_Voice_Calls.md` same-agent/same-permission contract, `07_MCPs.md` MCP-owned
  discovery contract, `AGCFG-005`, and the post-change audible gate in `MPV-014`.
- Preconditions: the active runtime is the checkout under test; authenticated Modern Playground;
  healthy GlassHive; synthetic public-safe task; no private browser/account interaction.
- Steps:
  1. Start a real call and prove the agent participant and microphone/audio path are active.
  2. Speak a request to open `https://example.com`, record the exact heading, and save a public-safe
     workspace note.
  3. After launch, speak a terse status or wait request.
  4. Ask for artifacts so the host must discover the deferred `workspace_artifacts` capability with
     `tool_search` scoped to `glasshive-workers-projects` and invoke it in the same turn.
  5. Verify nonzero delivered audio, visible transcript, linked-chat persistence/reload, provider-
     bound launch/status/wait definitions, Mongo tool-call parts, GlassHive run/events, and logs.
- Expected Result: the audible answer and transcript agree with real GlassHive state; launch,
  status/wait, and deferred discovery work without channel-specific routing or a false unavailable
  claim.
- Forbidden Result: typed-only proof, silent/zero-byte audio, source/tests/logs substituted for the
  call, voice using different agent permissions, a deferred schema reported unavailable without
  scoped discovery, or private data in evidence.
- Last Run: PASS 2026-07-13 for the real Modern Playground launch/wait/file journey and a separate
  real deferred-artifact request. The worker completed and created the exact synthetic note;
  transcript, TTS provider metrics, linked persistence, 17 unique eager provider-bound tools, and
  artifact checks passed. On the deferred request the same voice turn invoked scoped `tool_search`,
  rebound with 22 provider tools, invoked `workspace_artifacts`, rendered the visible transcript,
  persisted the tool parts without error, and delivered nonzero audio. The observed one-shot stream
  duration was 8.187 seconds and delivered audio duration was 4.478 seconds. The generic custom-
  prompt acceptance harness also passed after its semantic-health gate was corrected to use
  provider completion plus visible and persisted output rather than canned response vocabulary.
  These are acceptance observations, not percentile measurements.

## MPV-022 Mixed-Corpus Recall Must Stay Grounded On The Configured Voice Route

- Requirement: `32_Conversation_Recall_RAG.md` mixed-resource ranking and active-thread exclusion,
  `34_Voice_Chat_LLM_Override.md` route ownership, and the audible post-change gate in `MPV-014`.
- User Outcome: A fresh voice call remembers an earlier chat event accurately even when meeting
  transcripts are also searchable, without treating its own question as prior evidence.
- Surfaces: isolated browser, Agent Builder, Modern Playground, LibreChat voice controller and
  `file_search`, linked-chat source detail, Mongo, Meilisearch, recall metadata, voice gateway.
- Preconditions: authenticated isolated QA browser; configured synthetic voice route; recall
  enabled; synthetic prior event in a separate fixture conversation; saved memory unchanged.
- Steps:
  1. Confirm Agent Builder still shows the configured voice model and continuity toggles.
  2. Enter a synthetic event in an ordinary browser conversation and wait for aligned recall
     source/upload digests.
  3. Start a fresh call and ask the agent to search prior conversations for the event details.
  4. Confirm `file_search` executes, the prior chat ranks before unrelated transcripts, and the
     active thread/prompt is absent from returned evidence.
  5. Hear the answer, open the linked chat's tool detail, refresh it, and correlate the visible
     result with provider, controller, TTS, Mongo, and recall evidence.
  6. Remove the synthetic event/call and verify zero residual state across Mongo, Meilisearch,
     saved memory, and rebuilt recall.
- Expected Result: configured xAI Chat Completions returns only the grounded prior-event fields;
  source detail and answer persist after refresh; xAI TTS delivers non-cancelled audio.
- Forbidden Result: a provider/model flip; inherited Responses transport; final-run Feelings
  `ReferenceError`; transcript source-class override; blended unrelated meeting details; current
  prompt as evidence; silent or typed-only acceptance; or residual synthetic state.
- Evidence: `fileSearch.test.js`, agent controller/feelings/voice tests, focused Prompt Workbench
  recall eval, isolated browser/audible call when run, linked-chat refresh, provider/TTS logs, and
  fixture DB/search cleanup.
- Last Run: PASS-AUTOMATED/PARTIAL 2026-07-14. File-search regressions passed 49/49 and adjacent
  controller/feelings/voice suites passed 178/178. Isolated-account audible delivery, detail-state
  persistence, and runtime cleanup are NOT RUN.

## MPV-023 Public Call Must Establish Off-LAN Media

- Requirement: `docs/requirements_and_learnings/47_Remote_Access_and_Tunneling.md` and the
  post-change user-grade proof gate in `MPV-014`.
- User Outcome: opening a Telegram `/call` link away from home starts a real voice session instead
  of loading settings and then failing with `could not establish pc connection`.
- Surfaces: public Playground HTTPS, public LiveKit signaling and TCP/UDP media, voice gateway,
  Mongo call-session/transcript state, canonical and generated runtime config.
- Preconditions: local-prod runtime compiled from canonical config; synthetic public-safe audio and
  session; independently routed browser path; local-only raw evidence.
- Steps:
  1. Prove the active LiveKit process advertises the intended public media address and that the
     public HTTPS and TCP media ports are externally reachable.
  2. Route Chromium's public page/signaling traffic through an off-LAN SOCKS proxy and disable
     non-proxied UDP so LAN media cannot satisfy the case.
  3. Start the call with the synthetic microphone fixture and require connected TCP ICE pairs.
  4. Verify the voice worker joins, expected STT transcript persists once, and the visible call UI
     remains active.
  5. Correlate LiveKit selected-pair logs, worker activity, DB persistence, generated config, and
     targeted synthetic cleanup.
  6. Test TURN/TLS independently when it is relied on; a listener, certificate, or gathered relay
     candidate does not pass unless a relay pair is selected.
  7. Test the same public hostname from the serving Wi-Fi separately and report NAT loopback/split
     DNS as its own network prerequisite.
- Expected Result: the off-LAN public browser selects LiveKit TCP media, the worker receives the
  fixture, the expected transcript is delivered, and synthetic records are cleaned.
- Forbidden Result: private-only server candidates; page/settings/signaling-only acceptance;
  assuming TURN works because its TLS listener is reachable; hiding same-Wi-Fi NAT failure inside
  the application result; retaining synthetic users, sessions, messages, or ingress rows.
- Evidence: isolated lab Playwright evidence, sanitized selected-pair summary, synthetic transcript,
  fixture cleanup ledger, and generated-config alignment.
- Last Run: NOT RUN for this public candidate. A dedicated isolated lab edge/router and synthetic
  account are required; non-lab network observations are excluded from public evidence.

## MPV-024 Unsupported Voice-Agent-As-TTS Compatibility Route Fails Closed

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md` xAI standalone TTS contract.
- User Outcome: Old configuration cannot silently run a different xAI product or be mistaken for
  the supported standalone TTS renderer.
- Surfaces: config compiler, generated runtime env, voice-gateway startup, shared provider/model
  contract, xAI prompt dialect.
- Steps:
  1. Compile a synthetic config with `voice.tts.xai.tts_api: voice_agent`.
  2. Start the worker unit boundary with `VIVENTIUM_XAI_TTS_API=voice_agent`.
  3. Verify both fail with an actionable migration to `tts`, without starting or remapping a route.
  4. Verify the shared xAI runtime model list contains only `xai-tts` at `/v1/tts`, the legacy
     adapter source/test are absent, and the prompt branch still exposes only documented standalone
     xAI TTS controls.
- Expected Result: unsupported legacy TTS configuration fails closed; supported standalone xAI TTS remains
  selectable and capability-aligned.
- Forbidden Result: `/v1/realtime` starts; the setting silently becomes `/v1/tts`; legacy adapter
  instructions or catalog entries remain active; standalone xAI tag coverage regresses.
- Evidence: `test_config_compiler_rejects_retired_xai_grok_voice_agent_route`,
  `test_load_env_rejects_retired_xai_voice_agent_route`,
  `test_xai_voice_runtime_exposes_only_standalone_tts`, voice provider contract tests, and
  `surfacePrompts.spec.js`.
- Last Run: PASS automated 2026-07-15. The failure-first runtime test was RED before the worker
  guard and GREEN after; compiler/runtime rejection, source absence, one-model catalog, and
  standalone prompt contract pass. No local installed runtime was restarted in this source-only
  slice.

## MPV-025 LiveKit Docker Runtime Is Immutable And Upgrade-Safe

- Requirement: `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md` and
  `docs/requirements_and_learnings/52_Voice_Component_Fork_Modification_Inventory.md`.
- User Outcome: Enabling Voice or upgrading cannot silently run a floating or older LiveKit server.
- Surfaces: optional runtime manifest, full-stack launcher, Viventium-managed LiveKit container,
  TURN configuration, and Docker storage.
- Steps:
  1. Verify the optional runtime manifest records the exact version, upstream source commit,
     multi-architecture index digest, child digests, provenance class, license, and signature truth.
  2. Start from no image/container and prove the exact reference is pulled and becomes healthy.
  3. Restart and prove the exact managed container is reused without churn.
  4. Seed an older synthetic Viventium-managed container and prove it is replaced without volumes.
  5. Bind an unrelated or explicitly configured external LiveKit endpoint and prove Viventium does
     not delete or relabel it.
  6. Exercise v1.13 TURN configuration with TTL-aware credentials and classify any legacy no-TTL
     configuration as migration-required rather than healthy.
  7. Record logical and physical Docker disk usage before and after; remove only named QA resources.
- Expected Result: runtime identity matches the immutable lock; exact containers are stable; stale
  managed containers upgrade automatically; external/unrelated state is preserved; TURN and storage
  evidence are truthful.
- Forbidden Result: `latest` or an unqualified repository name; treating the nested placeholder SHA
  as the Docker artifact; silently reusing a stale managed container; deleting unrelated resources;
  calling digest provenance a publisher signature; or accepting TURN from a listening port alone.
- Evidence: `release/optional-runtime-components.json`,
  `tests/release/test_optional_runtime_provenance.py`, sanitized container inspect/health evidence,
  TURN selected-pair evidence, and a bounded cleanup ledger.
- Last Run: PARTIAL 2026-07-21. Eight focused provenance/identity tests and launcher syntax pass.
  After a validated continuity backup and controlled Docker recovery, the exact index digest pulled
  and ran on arm64; health and same-container restart passed; the real launcher replaced a stale
  managed source label and preserved an unrelated healthy external container. All named synthetic
  containers were deleted and the volume count stayed unchanged. Intel, TURN selected-pair, and
  microphone/TCC remain NOT RUN. See
  `reports/2026-07-21-livekit-immutable-runtime-docker-qa.md`.

## MPV-026 Custom Settings Never Runs An Unverified Native LiveKit Binary

- Requirement: `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md` and
  `docs/requirements_and_learnings/52_Voice_Component_Fork_Modification_Inventory.md`.
- User Outcome: Enabling Voice from Custom Settings cannot silently execute an unrelated or stale
  `livekit`/`livekit-server` binary inherited from the user's shell.
- Surfaces: `scripts/viventium/native_stack.sh`, full-stack launcher, Custom Settings Native/source
  runtime, exact Docker runtime, and deliberately configured external LiveKit endpoint.
- Steps:
  1. Put synthetic `livekit` and `livekit-server` executables first on `PATH`.
  2. Start the launcher with Native install mode and Voice enabled.
  3. Verify the launch path ignores both executables and selects the exact digest-pinned Docker
     artifact when Docker is available.
  4. Repeat with `--skip-docker`, no reachable configured endpoint, and confirm startup fails before
     either executable runs.
  5. Verify the failure explains the supported choices: enable Docker, configure
     `LIVEKIT_API_HOST`, or use `--skip-livekit` to start without Voice.
  6. Configure an unreachable explicit endpoint and occupy the unconfigured default port in separate
     runs; verify both fail without starting Docker, adopting the listener, or deleting it.
  7. Directly request LiveKit from the early Native dependency stack and verify it fails before
     starting other dependencies or installing/executing a local server binary; the supported CLI
     must keep delegating Voice startup to the full launcher.
- Expected Result: only the exact managed Docker artifact or an explicitly configured reachable
  external endpoint can own LiveKit startup; the no-Docker missing-endpoint path is actionable.
- Forbidden Result: any `command -v livekit*` discovery, `PATH` executable launch, silent fallback,
  implicit Docker fallback from an unhealthy explicit endpoint, adoption/deletion of an unrelated
  listener, floating Docker image, or success message for an unverified runtime.
- Evidence: `tests/release/test_optional_runtime_provenance.py`,
  `tests/release/test_native_stack_helpers.py`, both shell syntax checks, and exact Docker/external
  endpoint QA under `MPV-025`.
- Last Run: 2026-07-21 PASS for source contract and shell syntax. The regression was RED while the
  launcher still accepted arbitrary `PATH` binaries and GREEN after removing that fallback. Exact
  Docker behavior remains covered by `MPV-025`; a signed native macOS LiveKit artifact does not
  exist and is not claimed.

## MPV-027 Direct Playground Entry Explains The Safe Recovery Path

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`.
- User Outcome: A non-technical user who opens the voice URL directly understands why the call
  cannot start and what to do next.
- Surfaces: Modern Playground browser home view and exact `/api/health` identity.
- Steps:
  1. Start the current modern candidate on an isolated loopback port with synthetic secrets, an
     unreachable loopback backend, and no standalone agent name.
  2. Open the root URL in headed Chromium without call-session query parameters.
  3. Verify the primary action is disabled and the adjacent help text says to open Voice from a
     Viventium conversation.
  4. Inspect console and requests, refresh, and verify the exact modern source identity.
- Expected Result: refusal is actionable, branded, stable after refresh, and local-only.
- Forbidden Result: a disabled `Open from Viventium` button with no explanation; a generic LiveKit
  page; an automatic provider/backend request; raw error text; or adoption of a stale listener.
- Evidence: `tests/release/test_playground_identity.py` and
  `reports/2026-07-21-modern-playground-default-release-regression.md`.
- Last Run: PASS 2026-07-21. The regression test failed before the guidance was added and passed
  afterward; headed Chromium showed the guidance with no console warning/error or external request.

## MPV-028 Direct Playground Entry Is Inclusive At Narrow And Reduced-Motion Settings

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`.
- User Outcome: A keyboard or reduced-motion user can understand and configure the direct voice
  surface without clipped content or unnecessary motion.
- Surfaces: Modern Playground direct browser entry, viewport layout, forced colors, focus order, and
  motion preferences.
- Steps:
  1. Open the isolated modern candidate in headed Chromium and traverse every enabled control with
     Tab.
  2. Apply a `320 x 760` viewport, forced colors, dark scheme, and Reduce Motion.
  3. Verify named focus targets, zero horizontal overflow, a non-negative top bound for the first
     setup graphic, downward document growth, and zero retained animation/transition durations.
  4. Inspect console and request destinations.
- Expected Result: controls are named and keyboard reachable; tall content begins in the viewport
  and scrolls downward; Reduce Motion removes motion durations; only loopback assets load.
- Forbidden Result: a setup surface centered above the viewport, unnamed focus target, horizontal
  scroll, retained transform/opacity motion, external request, or console warning/error.
- Evidence: `tests/release/test_playground_identity.py` and
  `qa/installer-resilience/reports/2026-07-21-accessibility-and-fault-matrix-closeout.md`.
- Last Run: PASS 2026-07-21 for the isolated source page. Headed Chromium first reproduced nine
  retained transition durations and a clipped top graphic, then passed after the fixes with zero
  motion durations, zero horizontal overflow, and the first graphic at `y=40`. VoiceOver, an actual
  call/microphone, and the exact signed installed artifact remain separate blocked rows.

## MPV-029 Call Start Fails Safely Before Durable Session Creation

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md` and
  `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`.
- User Outcome: Starting Voice never adopts a stale playground, buffers an unbounded health
  response, or exposes raw server diagnostics; recoverable failure copy tells the user what to do.
- Surfaces: LibreChat call button, `POST /api/viventium/calls`, and modern/classic `/api/health`.
- Steps:
  1. Build both playground variants with exact synthetic 40-character source refs and inspect the
     compiled health route rather than trusting source text.
  2. Attempt call creation against wrong-variant, stale-source, oversized declared, oversized
     chunked, malformed, and unreachable health responses.
  3. Verify no durable call session is created and the button renders concise inline recovery copy
     linked to the retry button for assistive technology.
  4. Verify the response body is bounded while streaming and an oversized `Content-Length` is
     rejected before the body is read.
  5. Separately verify LiveKit server, registered gateway worker, selected STT/TTS provider, and an
     audible synthetic call before promoting this case to full release `PASS`.
- Expected Result: compiled source identity cannot be changed by runtime environment drift; unsafe
  responses fail closed before persistence; the user sees actionable public-safe inline copy.
- Forbidden Result: runtime identity echo, unbounded `response.text()`, raw JSON alert, durable call
  session creation after a failed guard, or a claim that playground health proves end-to-end Voice.
- Evidence: `tests/release/test_playground_identity.py`,
  `tests/release/test_voice_call_startup_guard.py`, LibreChat call route/component tests, and
  `reports/2026-07-21-modern-playground-default-release-regression.md`.
- Last Run: 2026-07-22 `PARTIAL`. Both clean hosted playground heads built successfully and their
  compiled routes contained only the build-time source refs. Exact modern-playground head
  `fd778562af199f7fb503bd4a0d106e22c282b16b` also passed headed Chromium keyboard, 320 px,
  forced-colors, reduced-motion, loopback-only, and reload checks. Corrected LibreChat review head
  `44ac1f7a...` passed 59 stream tests, 216 Viventium route tests, and all 15 hosted checks, including
  actual Redis. The headed retry/error path, registered LiveKit worker, selected provider readiness,
  and audible synthetic call remain unrun; end-to-end Voice readiness is not claimed.

## Release Test Traceability

- `tests/release/test_voice_call_startup_guard.py`
- `tests/release/test_playground_identity.py`
- `tests/release/test_optional_runtime_provenance.py`
- `tests/release/test_playground_loopback_contract.py`
- `tests/release/test_voice_playground_dispatch_contract.py`
- `tests/release/test_config_compiler.py` (`VIVENTIUM_ASSEMBLYAI_STT_MODEL` default + override)
- `viventium_v0_4/voice-gateway/tests/test_worker_stt_assemblyai.py` (AssemblyAI engine selection)
